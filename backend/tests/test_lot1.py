"""Lot 1 : référentiels, exercices, budgets et crédits (T-080 à T-095)."""

import uuid
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from hopitalia_budget.domaine.habilitations import Profil
from hopitalia_budget.domaine.indicateurs import (
    BaseTaux,
    MouvementsLigne,
    ParametresCalcul,
    calculer_indicateurs_ligne,
)
from tests.conftest import creer_etablissement, entetes, habiliter

NOMENCLATURE = Path(__file__).parents[2] / "docs" / "cadrage" / "nomenclature-budgetaire.csv"
ADMIN, RB_A, VAL_A, ORD_A, VAL_ORD_A, LEC_B, AUDITEUR = 1, 2, 3, 4, 5, 6, 7
M = Decimal


def poster(client: TestClient, utilisateur: int, url: str, corps: Any) -> Any:
    cle = {"Idempotency-Key": uuid.uuid4().hex}
    return client.post(url, json=corps, headers=entetes(utilisateur, **cle))


def creer(client: TestClient, utilisateur: int, url: str, corps: Any) -> dict[str, Any]:
    reponse = poster(client, utilisateur, url, corps)
    assert reponse.status_code == 201, reponse.json()
    resultat: dict[str, Any] = reponse.json()
    return resultat


def csv(client: TestClient, utilisateur: int, url: str, contenu: str) -> Any:
    return client.post(
        url,
        content=contenu.encode(),
        headers=entetes(utilisateur, **{"Content-Type": "text/csv"}),
    )


@pytest.fixture
def socle(client: TestClient, session: Session) -> dict[str, Any]:
    """Établissements, profils, nomenclature réelle, centres, source, exercice et budget."""
    a = creer_etablissement(session, "CHU-A")
    b = creer_etablissement(session, "CHU-B")
    habiliter(session, ADMIN, Profil.ADM)
    habiliter(session, RB_A, Profil.RB, a)
    habiliter(session, VAL_A, Profil.VAL, a)
    habiliter(session, ORD_A, Profil.ORD, a)
    habiliter(session, VAL_ORD_A, Profil.VAL, a)
    habiliter(session, VAL_ORD_A, Profil.ORD, a)
    habiliter(session, LEC_B, Profil.LEC, b)
    habiliter(session, AUDITEUR, Profil.AUD)
    session.commit()
    rapport = csv(client, ADMIN, "/api/v1/nomenclature/imports", NOMENCLATURE.read_text("utf-8"))
    assert rapport.status_code == 200, rapport.json()
    comptes = {
        n["code"]: n["id"]
        for n in client.get("/api/v1/nomenclature?niveau=PARAGRAPHE", headers=entetes(ADMIN)).json()
    }
    centre = creer(
        client,
        ADMIN,
        "/api/v1/centres-responsabilite",
        {
            "etablissementId": str(a.id),
            "code": "PHARMA",
            "libelle": "Pharmacie",
            "type": "MEDICO_TECHNIQUE",
        },
    )
    source = creer(
        client,
        ADMIN,
        "/api/v1/sources-financement",
        {"code": "ETAT", "libelle": "Budget de l'État", "typeFinancement": "BUDGET_ETAT"},
    )
    exercice = creer(
        client,
        ADMIN,
        "/api/v1/exercices",
        {"code": "2026", "dateOuverture": "2026-01-01", "dateCloture": "2026-12-31"},
    )
    budget = creer(
        client,
        RB_A,
        "/api/v1/budgets",
        {"exerciceId": exercice["id"], "etablissementId": str(a.id), "reference": "BP-2026"},
    )

    def ligne(code: str, compte: str, dotation: str) -> dict[str, Any]:
        return creer(
            client,
            RB_A,
            "/api/v1/lignes-budgetaires",
            {
                "budgetId": budget["id"],
                "code": code,
                "libelle": code,
                "compteBudgetaireId": comptes[compte],
                "centreId": centre["id"],
                "sourceId": source["id"],
                "dotationInitiale": dotation,
            },
        )

    # Lignes du jeu d'essai validé (docs/cadrage/jeu-essai-marche-fournitures.md).
    med = ligne("604-MED", "604-MED", "90000000.00")
    cmd = ligne("604-CMD", "604-CMD", "40000000.00")
    return {
        "a": str(a.id),
        "b": str(b.id),
        "rapport": rapport.json(),
        "comptes": comptes,
        "centre": centre,
        "source": source,
        "exercice": exercice,
        "budget": budget,
        "med": med,
        "cmd": cmd,
    }


def disponibilite(client: TestClient, ligne_id: str) -> dict[str, Any]:
    reponse = client.get(
        f"/api/v1/lignes-budgetaires/{ligne_id}/disponibilite", headers=entetes(ADMIN)
    )
    indicateurs: dict[str, Any] = reponse.json()["indicateurs"]
    return indicateurs


# --- T-093 : formules de la section 6.1 (sans base) ------------------------------------------


def test_formules_6_1_sur_le_jeu_d_essai() -> None:
    """Ligne 604-MED du jeu d'essai : engagé 65 M, liquidé 40 M, payé 25 M."""
    i = calculer_indicateurs_ligne(
        MouvementsLigne(
            dotation_initiale=M("90000000.00"),
            engage=M("65000000.00"),
            liquide=M("40000000.00"),
            net_a_payer=M("40000000.00"),
            paye=M("25000000.00"),
        )
    )
    assert i.budget_revise == M("90000000.00")
    assert i.disponible_apres_engagements == M("25000000.00")
    assert i.engage_restant_a_liquider == M("25000000.00")
    assert i.reste_a_payer == M("15000000.00")
    assert i.taux_engagement == M("72.22")


def test_formules_revisions_et_parametres() -> None:
    m = MouvementsLigne(
        dotation_initiale=M("100.00"),
        modifications_positives=M("30.00"),
        modifications_negatives=M("10.00"),
        engage=M("60.00"),
        en_cours_validation=M("20.00"),
    )
    defaut = calculer_indicateurs_ligne(m)
    assert defaut.budget_revise == M("120.00")
    assert defaut.disponible_apres_engagements == M("60.00")
    assert defaut.disponible_previsionnel == M("40.00")
    assert defaut.taux_engagement == M("50.00")
    autre = calculer_indicateurs_ligne(
        m,
        ParametresCalcul(
            disponible_previsionnel_deduit_en_cours=False,
            base_taux_execution=BaseTaux.BUDGET_INITIAL,
        ),
    )
    assert autre.disponible_previsionnel == M("60.00")
    assert autre.taux_engagement == M("60.00")
    assert (
        calculer_indicateurs_ligne(MouvementsLigne(dotation_initiale=M("0.00"))).taux_engagement
        is None
    )


# --- T-080, T-081 : sites et centres ---------------------------------------------------------


def test_sites_par_etablissement(client: TestClient, socle: dict[str, Any]) -> None:
    site = creer(
        client,
        ADMIN,
        "/api/v1/sites",
        {"etablissementId": socle["a"], "code": "S1", "libelle": "Site principal"},
    )
    refus = poster(
        client, RB_A, "/api/v1/sites", {"etablissementId": socle["a"], "code": "S2", "libelle": "x"}
    )
    assert (refus.status_code, refus.json()["code"]) == (403, "ACCES_REFUSE")
    doublon = poster(
        client,
        ADMIN,
        "/api/v1/sites",
        {"etablissementId": socle["a"], "code": "S1", "libelle": "x"},
    )
    assert (doublon.status_code, doublon.json()["code"]) == (409, "CODE_DEJA_UTILISE")
    assert client.get("/api/v1/sites", headers=entetes(LEC_B)).json()["donnees"] == []
    url = f"/api/v1/sites/{site['id']}"
    modifie = client.patch(
        url, json={"libelle": "Site Fann"}, headers=entetes(ADMIN, **{"If-Match": '"1"'})
    )
    assert modifie.json()["libelle"] == "Site Fann"
    assert client.get(url, headers=entetes(LEC_B)).status_code == 404


def test_centres_hierarchie(client: TestClient, socle: dict[str, Any]) -> None:
    racine = socle["centre"]
    enfant = creer(
        client,
        ADMIN,
        "/api/v1/centres-responsabilite",
        {
            "etablissementId": socle["a"],
            "code": "PHARMA-1",
            "libelle": "Stock",
            "type": "LOGISTIQUE",
            "parentId": racine["id"],
        },
    )
    cycle = client.patch(
        f"/api/v1/centres-responsabilite/{racine['id']}",
        json={"parentId": enfant["id"]},
        headers=entetes(ADMIN, **{"If-Match": f'"{racine["version"]}"'}),
    )
    assert (cycle.status_code, cycle.json()["code"]) == (422, "HIERARCHIE_INVALIDE")
    autre = poster(
        client,
        ADMIN,
        "/api/v1/centres-responsabilite",
        {
            "etablissementId": socle["b"],
            "code": "X",
            "libelle": "X",
            "type": "AUTRE",
            "parentId": racine["id"],
        },
    )
    assert (autre.status_code, autre.json()["code"]) == (422, "REFERENCE_INVALIDE")
    filtre = client.get(
        f"/api/v1/centres-responsabilite?parentId={racine['id']}", headers=entetes(ADMIN)
    )
    assert [c["code"] for c in filtre.json()["donnees"]] == ["PHARMA-1"]


# --- T-082, T-086 : référentiels simples ------------------------------------------------------


@pytest.mark.parametrize(
    ("chemin", "corps", "attendu"),
    [
        (
            "programmes",
            {"code": "PNLP", "libelle": "Paludisme", "dateDebut": "2026-01-01"},
            {"dateDebut": "2026-01-01"},
        ),
        ("familles-achats", {"code": "MED", "libelle": "Médicaments"}, {"libelle": "Médicaments"}),
        (
            "types-depenses",
            {"code": "PA", "libelle": "Petits achats", "seuilHorsMarche": "1000000"},
            {"seuilHorsMarche": "1000000.00"},
        ),
        ("modes-reglement", {"code": "VIR", "libelle": "Virement"}, {"code": "VIR"}),
        (
            "comptes-tresorerie",
            {"code": "BQ1", "libelle": "Banque", "typeCompte": "BANQUE"},
            {"typeCompte": "BANQUE"},
        ),
        ("types-pieces", {"code": "PV", "libelle": "Procès-verbal"}, {"dureeConservationAns": 10}),
    ],
)
def test_referentiels(
    client: TestClient,
    socle: dict[str, Any],
    chemin: str,
    corps: dict[str, str],
    attendu: dict[str, Any],
) -> None:
    cree = creer(client, ADMIN, f"/api/v1/{chemin}", corps)
    assert attendu.items() <= cree.items()
    liste = client.get(f"/api/v1/{chemin}?code={corps['code']}", headers=entetes(LEC_B)).json()
    assert [e["code"] for e in liste["donnees"]] == [corps["code"]]
    assert poster(client, RB_A, f"/api/v1/{chemin}", corps | {"code": "AUTRE"}).status_code == 403


def test_referentiels_separes_par_type(client: TestClient, socle: dict[str, Any]) -> None:
    source = socle["source"]
    assert (
        client.get(f"/api/v1/programmes/{source['id']}", headers=entetes(ADMIN)).status_code == 404
    )


def test_programme_dates_incoherentes(client: TestClient, socle: dict[str, Any]) -> None:
    reponse = poster(
        client,
        ADMIN,
        "/api/v1/programmes",
        {"code": "P", "libelle": "P", "dateDebut": "2026-06-01", "dateFin": "2026-01-01"},
    )
    assert (reponse.status_code, reponse.json()["code"]) == (422, "DATES_INCOHERENTES")


# --- T-083, T-084 : nomenclature et comptes ---------------------------------------------------


def test_import_de_la_nomenclature(client: TestClient, socle: dict[str, Any]) -> None:
    assert socle["rapport"] == {"crees": 85, "misAJour": 0, "anomalies": []}
    nouveau = csv(
        client, ADMIN, "/api/v1/nomenclature/imports", NOMENCLATURE.read_text("utf-8")
    ).json()
    assert (nouveau["crees"], nouveau["misAJour"]) == (0, 85)
    assert len(socle["comptes"]) == 45
    tout = client.get("/api/v1/nomenclature", headers=entetes(LEC_B)).json()
    assert len(tout) == 85


def test_correspondance_dans_les_deux_sens(client: TestClient, socle: dict[str, Any]) -> None:
    paragraphe = client.get("/api/v1/nomenclature?niveau=PARAGRAPHE", headers=entetes(ADMIN)).json()
    med = next(n for n in paragraphe if n["code"] == "604-MED")
    assert med["compteComptableCode"] == "604"
    compte = client.get("/api/v1/comptes-comptables/604", headers=entetes(ADMIN)).json()
    assert {c["code"] for c in compte["comptesBudgetaires"]} >= {"604-MED", "604-CMD", "604-REA"}


def test_nomenclature_anomalies_et_droits(client: TestClient, socle: dict[str, Any]) -> None:
    contenu = (
        "niveau;code;libelle;code_parent;compte_syscohada\n"
        "PARAGRAPHE;999-X;Sans parent;INCONNU;999\n"
        "FOO;1;;;\n"
    )
    rapport = csv(client, ADMIN, "/api/v1/nomenclature/imports", contenu).json()
    assert [(a["ligne"], a["code"]) for a in rapport["anomalies"]] == [
        (2, "PARENT_INVALIDE"),
        (3, "LIGNE_INCOMPLETE"),
    ]
    assert csv(client, RB_A, "/api/v1/nomenclature/imports", contenu).status_code == 403


# --- T-085 : fournisseurs et coordonnées chiffrées -------------------------------------------


def test_coordonnees_chiffrees_et_masquees(
    client: TestClient, socle: dict[str, Any], session: Session
) -> None:
    fournisseur = creer(
        client, ADMIN, "/api/v1/fournisseurs", {"code": "F1", "raisonSociale": "Pharma Test SA"}
    )
    url = f"/api/v1/fournisseurs/{fournisseur['id']}/coordonnees"
    numero = "SN012010100100000012345678"
    reponse = client.post(
        url,
        json={
            "etablissementId": socle["a"],
            "banque": "Banque Test",
            "numeroCompte": numero,
            "parDefaut": True,
        },
        headers=entetes(ADMIN),
    )
    assert reponse.status_code == 201
    assert reponse.json()["numeroMasque"] == "•••• 5678"
    stocke = session.scalar(text("SELECT numero_compte_chiffre FROM coordonnee_paiement"))
    assert numero not in stocke
    journal = session.scalar(
        text(
            "SELECT nouvelle_valeur::text FROM journal_audit "
            "WHERE type_objet = 'CoordonneePaiement'"
        )
    )
    assert numero not in journal
    assert client.get(url, headers=entetes(LEC_B)).json() == []


# --- T-087, T-088 : exercices et budgets ------------------------------------------------------


def test_exercice_et_ses_periodes(
    client: TestClient, socle: dict[str, Any], session: Session
) -> None:
    assert socle["exercice"]["statut"] == "OUVERT"
    periodes = session.execute(
        text(
            "SELECT type, count(*) FROM periode WHERE exercice_id = :e GROUP BY type ORDER BY type"
        ),
        {"e": socle["exercice"]["id"]},
    ).all()
    assert [tuple(p) for p in periodes] == [
        ("ANNUELLE", 1),
        ("MENSUELLE", 12),
        ("TRIMESTRIELLE", 4),
    ]
    incoherent = poster(
        client,
        ADMIN,
        "/api/v1/exercices",
        {"code": "2027", "dateOuverture": "2027-12-31", "dateCloture": "2027-01-01"},
    )
    assert (incoherent.status_code, incoherent.json()["code"]) == (422, "DATES_INCOHERENTES")


def test_un_seul_budget_primitif(client: TestClient, socle: dict[str, Any]) -> None:
    corps = {
        "exerciceId": socle["exercice"]["id"],
        "etablissementId": socle["a"],
        "reference": "BP-BIS",
    }
    doublon = poster(client, RB_A, "/api/v1/budgets", corps)
    assert (doublon.status_code, doublon.json()["code"]) == (409, "BUDGET_PRIMITIF_EXISTANT")
    modificatif = poster(client, RB_A, "/api/v1/budgets", corps | {"type": "MODIFICATIF"})
    assert modificatif.status_code == 201
    autre = poster(client, RB_A, "/api/v1/budgets", corps | {"etablissementId": socle["b"]})
    assert (autre.status_code, autre.json()["code"]) == (403, "ACCES_REFUSE")


# --- T-089 : lignes budgétaires ---------------------------------------------------------------


def test_lignes_axes_controles_et_filtres(client: TestClient, socle: dict[str, Any]) -> None:
    base = {
        "budgetId": socle["budget"]["id"],
        "code": "X",
        "libelle": "X",
        "centreId": socle["centre"]["id"],
        "sourceId": socle["source"]["id"],
    }
    chapitre = next(
        n
        for n in client.get("/api/v1/nomenclature?niveau=CHAPITRE", headers=entetes(ADMIN)).json()
        if n["code"] == "60"
    )
    refus = poster(
        client, RB_A, "/api/v1/lignes-budgetaires", base | {"compteBudgetaireId": chapitre["id"]}
    )
    assert (refus.status_code, refus.json()["champ"]) == (422, "compteBudgetaireId")
    liste = client.get(
        f"/api/v1/lignes-budgetaires?budgetId={socle['budget']['id']}&tri=code",
        headers=entetes(RB_A),
    )
    assert [lg["code"] for lg in liste.json()["donnees"]] == ["604-CMD", "604-MED"]
    med = socle["med"]
    modifie = client.patch(
        f"/api/v1/lignes-budgetaires/{med['id']}",
        json={"libelle": "Médicaments", "dotationInitiale": "1.00"},
        headers=entetes(RB_A, **{"If-Match": '"1"'}),
    )
    assert modifie.json()["libelle"] == "Médicaments"
    assert modifie.json()["dotationInitiale"] == "90000000.00"


# --- T-090 : import asynchrone des dotations --------------------------------------------------


def test_import_des_dotations_avec_anomalies(client: TestClient, socle: dict[str, Any]) -> None:
    contenu = (
        "code;libelle;compte;centre;source;programme;dotation\n"
        "604-REA;Réactifs;604-REA;PHARMA;ETAT;;12000000\n"
        "605-ELE;Électricité;605-ELE;PHARMA;ETAT;;8 500 000,50\n"
        "604-MED;Doublon;604-MED;PHARMA;ETAT;;1\n"
        "X-1;Compte inconnu;999-ZZZ;PHARMA;ETAT;;1\n"
        "X-2;Montant;604-GAZ;PHARMA;ETAT;;abc\n"
        "X-3;Centre;604-GAZ;INCONNU;ETAT;;1\n"
    )
    reponse = csv(client, RB_A, f"/api/v1/budgets/{socle['budget']['id']}/imports", contenu)
    assert reponse.status_code == 202
    suivi = client.get(reponse.headers["Location"], headers=entetes(RB_A)).json()
    assert suivi["statut"] == "TERMINE"
    assert suivi["lignesImportees"] == 2
    assert [(a["ligne"], a["code"]) for a in suivi["anomalies"]] == [
        (4, "CODE_DEJA_UTILISE"),
        (5, "COMPTE_INCONNU"),
        (6, "MONTANT_INVALIDE"),
        (7, "CENTRE_INCONNU"),
    ]
    situation = client.get(
        f"/api/v1/budgets/{socle['budget']['id']}/situation", headers=entetes(RB_A)
    ).json()
    ele = next(lg for lg in situation["lignes"] if lg["code"] == "605-ELE")
    assert ele["indicateurs"]["budgetInitial"] == "8500000.50"


def test_import_du_jeu_d_essai(client: TestClient, socle: dict[str, Any]) -> None:
    """Critère de T-090 : les lignes de départ du jeu d'essai T-015 s'importent sans anomalie."""
    budget = creer(
        client,
        RB_A,
        "/api/v1/budgets",
        {
            "exerciceId": socle["exercice"]["id"],
            "etablissementId": socle["a"],
            "reference": "BM-JEU",
            "type": "MODIFICATIF",
        },
    )
    contenu = (
        "code;libelle;compte;centre;source;programme;dotation\n"
        "604-MED;Médicaments;604-MED;PHARMA;ETAT;;90000000\n"
        "604-CMD;Consommables médicaux;604-CMD;PHARMA;ETAT;;40000000\n"
    )
    reponse = csv(client, RB_A, f"/api/v1/budgets/{budget['id']}/imports", contenu)
    suivi = client.get(reponse.headers["Location"], headers=entetes(RB_A)).json()
    assert (suivi["statut"], suivi["lignesImportees"], suivi["anomalies"]) == ("TERMINE", 2, [])
    situation = client.get(
        f"/api/v1/budgets/{budget['id']}/situation", headers=entetes(RB_A)
    ).json()
    assert situation["totaux"]["budgetInitial"] == "130000000.00"


# --- T-091 : notifications de crédits ---------------------------------------------------------


def test_notification_rattachee_a_ses_lignes(client: TestClient, socle: dict[str, Any]) -> None:
    corps = {
        "budgetId": socle["budget"]["id"],
        "reference": "NC-2026-01",
        "dateNotification": "2026-01-15",
        "montant": "130000000.00",
        "objet": "Notification initiale",
        "sourceId": socle["source"]["id"],
        "lignes": [
            {"ligneId": socle["med"]["id"], "montant": "90000000.00"},
            {"ligneId": socle["cmd"]["id"], "montant": "40000000.00"},
        ],
    }
    cree = creer(client, RB_A, "/api/v1/notifications-credits", corps)
    assert len(cree["lignes"]) == 2
    incoherente = poster(client, RB_A, "/api/v1/notifications-credits", corps | {"montant": "1.00"})
    assert (incoherente.status_code, incoherente.json()["code"]) == (
        422,
        "NOTIFICATION_INCOHERENTE",
    )
    liste = client.get(
        f"/api/v1/notifications-credits?budgetId={socle['budget']['id']}", headers=entetes(RB_A)
    )
    assert [n["reference"] for n in liste.json()["donnees"]] == ["NC-2026-01"]


# --- T-092 : paramètres de calcul -------------------------------------------------------------


def test_parametres_de_calcul(client: TestClient, socle: dict[str, Any]) -> None:
    url = f"/api/v1/etablissements/{socle['a']}/parametres-calcul"
    defaut = client.get(url, headers=entetes(RB_A)).json()
    assert defaut == {
        "disponiblePrevisionnelDeduitEnCours": True,
        "baseTauxExecution": "BUDGET_REVISE",
        "baseTauxConsommationMarche": "ENGAGE",
        "consommationDeduitAvanceRecuperee": True,
    }
    nouveau = defaut | {"baseTauxExecution": "BUDGET_INITIAL"}
    assert client.put(url, json=nouveau, headers=entetes(RB_A)).status_code == 403
    assert client.put(url, json=nouveau, headers=entetes(ADMIN)).json() == nouveau
    assert client.get(url, headers=entetes(RB_A)).json() == nouveau


# --- T-094, T-095 : disponibilité et révisions -------------------------------------------------


def _virement(client: TestClient, socle: dict[str, Any], montant: str) -> dict[str, Any]:
    return creer(
        client,
        RB_A,
        "/api/v1/revisions-budgetaires",
        {
            "budgetId": socle["budget"]["id"],
            "type": "VIREMENT",
            "ligneSourceId": socle["med"]["id"],
            "ligneCibleId": socle["cmd"]["id"],
            "montant": montant,
            "motif": "Besoins en consommables",
        },
    )


def _decider(
    client: TestClient,
    utilisateur: int,
    revision: dict[str, Any],
    decision: str = "VALIDE",
    motif: str | None = None,
) -> Any:
    return client.post(
        f"/api/v1/revisions-budgetaires/{revision['id']}/validations",
        json={"decision": decision, "motif": motif},
        headers=entetes(utilisateur),
    )


def test_virement_sans_effet_avant_validation(client: TestClient, socle: dict[str, Any]) -> None:
    """Critère de T-095 : un virement non validé ne change pas les disponibles."""
    avant = disponibilite(client, socle["med"]["id"])
    revision = _virement(client, socle, "10000000.00")
    assert revision["statut"] == "SOUMISE"
    assert disponibilite(client, socle["med"]["id"]) == avant
    assert _decider(client, VAL_A, revision).json()["statut"] == "EN_VALIDATION"
    assert disponibilite(client, socle["med"]["id"]) == avant
    validee = _decider(client, ORD_A, revision).json()
    assert validee["statut"] == "VALIDEE"
    assert [(v["etape"], v["decision"]) for v in validee["visas"]] == [
        ("VAL", "VALIDE"),
        ("ORD", "VALIDE"),
    ]
    med = disponibilite(client, socle["med"]["id"])
    cmd = disponibilite(client, socle["cmd"]["id"])
    assert (med["budgetRevise"], med["modificationsNegatives"]) == ("80000000.00", "10000000.00")
    assert (cmd["budgetRevise"], cmd["modificationsPositives"]) == ("50000000.00", "10000000.00")


def test_circuit_et_separation_des_taches(client: TestClient, socle: dict[str, Any]) -> None:
    revision = _virement(client, socle, "1.00")
    premier = _decider(client, ORD_A, revision)
    assert (premier.status_code, premier.json()["code"]) == (403, "ETAPE_NON_AUTORISEE")
    assert _decider(client, RB_A, revision).status_code == 403
    assert _decider(client, VAL_ORD_A, revision).json()["statut"] == "EN_VALIDATION"
    meme = _decider(client, VAL_ORD_A, revision)
    assert (meme.status_code, meme.json()["code"]) == (403, "SEPARATION_DES_TACHES")
    assert _decider(client, ORD_A, revision).json()["statut"] == "VALIDEE"
    deja = _decider(client, ORD_A, revision)
    assert (deja.status_code, deja.json()["code"]) == (409, "OPERATION_DEJA_TRAITEE")


def test_rejet_motive(client: TestClient, socle: dict[str, Any]) -> None:
    revision = _virement(client, socle, "1.00")
    sans_motif = _decider(client, VAL_A, revision, "REJETE")
    assert (sans_motif.status_code, sans_motif.json()["code"]) == (422, "MOTIF_OBLIGATOIRE")
    rejetee = _decider(client, VAL_A, revision, "REJETE", "Pièce manquante").json()
    assert rejetee["statut"] == "REJETEE"
    assert rejetee["visas"][0]["motif"] == "Pièce manquante"


def test_credit_insuffisant_a_la_validation(client: TestClient, socle: dict[str, Any]) -> None:
    revision = _virement(client, socle, "95000000.00")
    _decider(client, VAL_A, revision)
    refus = _decider(client, ORD_A, revision)
    assert (refus.status_code, refus.json()["code"]) == (422, "CREDIT_INSUFFISANT")
    assert refus.json()["disponible"] == "90000000.00"
    assert (
        client.get(f"/api/v1/revisions-budgetaires/{revision['id']}", headers=entetes(RB_A)).json()[
            "statut"
        ]
        == "EN_VALIDATION"
    )


def test_budget_modificatif_et_situation(client: TestClient, socle: dict[str, Any]) -> None:
    for sens, montant in (("AUGMENTATION", "5000000.00"), ("DIMINUTION", "2000000.00")):
        revision = creer(
            client,
            RB_A,
            "/api/v1/revisions-budgetaires",
            {
                "budgetId": socle["budget"]["id"],
                "type": "BUDGET_MODIFICATIF",
                "sens": sens,
                "ligneCibleId": socle["cmd"]["id"],
                "montant": montant,
                "motif": "Décision modificative",
            },
        )
        _decider(client, VAL_A, revision)
        _decider(client, ORD_A, revision)
    situation = client.get(
        f"/api/v1/budgets/{socle['budget']['id']}/situation", headers=entetes(VAL_A)
    ).json()
    cmd = next(lg for lg in situation["lignes"] if lg["code"] == "604-CMD")["indicateurs"]
    assert cmd["budgetRevise"] == "43000000.00"
    assert situation["totaux"]["budgetRevise"] == "133000000.00"
    assert situation["totaux"]["disponibleApresEngagements"] == "133000000.00"


def test_revisions_cloisonnees_et_tracees(client: TestClient, socle: dict[str, Any]) -> None:
    revision = _virement(client, socle, "1.00")
    _decider(client, VAL_A, revision)
    assert (
        client.get("/api/v1/revisions-budgetaires", headers=entetes(LEC_B)).json()["donnees"] == []
    )
    assert (
        client.get(
            f"/api/v1/revisions-budgetaires/{revision['id']}", headers=entetes(LEC_B)
        ).status_code
        == 404
    )
    journal = client.get(
        f"/api/v1/journal-audit?idObjet={revision['id']}", headers=entetes(AUDITEUR)
    ).json()
    assert [e["action"] for e in journal["donnees"]] == ["CREATION", "VALIDATION"]
