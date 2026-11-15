"""Lot 2 : engagements et contrôles (T-140 à T-149), dérogations (T-118), annulations (T-117).

Les tests d'API sont paramétrés : chacun passe avec un engagement sur décision et avec une
dépense hors marché (substitution de Liskov, ARC-L).
"""

import threading
import time
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, delete
from sqlalchemy.orm import Session

from hopitalia_budget.adaptateurs.sortie.engagements_sql import DepotEngagementsSql
from hopitalia_budget.adaptateurs.sortie.modeles import (
    BudgetModele,
    CentreResponsabiliteModele,
    EngagementModele,
    EtablissementModele,
    ExerciceModele,
    ImputationEngagementModele,
    LigneBudgetaireModele,
    NoeudNomenclatureModele,
    ReferentielModele,
)
from hopitalia_budget.application.engagements import EngagementValidable
from hopitalia_budget.domaine.controles import (
    MoteurControles,
    NatureDerogation,
    ResultatControle,
    exiger_conformite,
)
from hopitalia_budget.domaine.engagements import (
    ControleCredits,
    DepenseHorsMarche,
    Engagement,
    ImputationEngagement,
    InfosContrat,
    Origine,
    StatutEngagement,
    reliquats,
    verifier_montant,
)
from hopitalia_budget.domaine.erreurs import ErreurMetier
from hopitalia_budget.domaine.habilitations import Profil
from tests import test_contrats, test_lot1
from tests.conftest import entetes, habiliter
from tests.doubles import HorlogeFixe
from tests.test_contrats import GMC_A, _contrat_valide, _synthese
from tests.test_lot1 import ADMIN, AUDITEUR, ORD_A, VAL_A, creer, disponibilite, poster

socle = test_lot1.socle  # fixtures partagées avec les lots précédents
lot2 = test_contrats.lot2
AF_A = 12
M = Decimal
ORIGINES = ["DECISION_AUTORISEE", "HORS_MARCHE"]


# --- Sans base : moteur de contrôles, règles ----------------------------------------------------


class ControleDeTest:
    """Contrôle ajouté pour le test : le moteur ne change pas (ARC-O, critère de T-141)."""

    def s_applique(self, operation: str) -> bool:
        return operation.startswith("A")

    def verifier(self, operation: str) -> list[ResultatControle]:
        return [ResultatControle("ECART_DE_TEST", NatureDerogation.CREDIT, M("10"))]


def test_moteur_extensible_et_derogation_limitee() -> None:
    moteur = MoteurControles([ControleDeTest()])
    assert moteur.controler("B") == []
    assert [r.code for r in moteur.controler("A")] == ["ECART_DE_TEST"]
    # RG-19 : la dérogation couvre sa nature et son montant, pas plus.
    assert moteur.controler("A", {NatureDerogation.CREDIT: M("10")})[0].leve
    assert not moteur.controler("A", {NatureDerogation.CREDIT: M("9.99")})[0].leve
    assert not moteur.controler("A", {NatureDerogation.DOUBLON: M("100")})[0].leve
    with pytest.raises(ErreurMetier) as exc:
        exiger_conformite(moteur.controler("A"))
    assert exc.value.code == "CONTROLE_BLOQUANT"


class ContexteFixe:
    def disponible(self, ligne_id: uuid.UUID) -> tuple[str, Decimal]:
        return "604-MED", M("50")

    def contrat(self, contrat_id: uuid.UUID, engagement_id: uuid.UUID) -> InfosContrat | None:
        return None

    def seuil_hors_marche(self, type_depense_id: uuid.UUID) -> Decimal | None:
        return None

    def doublons(self, engagement: Engagement) -> list[str]:
        return []


@pytest.mark.parametrize("classe", [Engagement, DepenseHorsMarche])
def test_rg02_controle_credits_identique_pour_les_sous_classes(classe: type[Engagement]) -> None:
    """ARC-L : la règle écrite pour un engagement vaut telle quelle pour une dépense hors marché."""
    imputation = ImputationEngagement(uuid.uuid4(), uuid.uuid4(), M("60"))
    engagement = classe(
        uuid.uuid4(),
        uuid.uuid4(),
        "ENG-1",
        date(2026, 3, 1),
        "Achat",
        Origine.DECISION_AUTORISEE,
        M("60"),
        (imputation,),
        StatutEngagement.SOUMIS,
        1,
        uuid.uuid4(),
    )
    (ecart,) = ControleCredits(ContexteFixe()).verifier(engagement)
    assert (ecart.code, ecart.depassement) == ("CREDIT_INSUFFISANT", M("10"))
    with pytest.raises(ErreurMetier):
        verifier_montant(M("60"), [M("50")])
    assert reliquats(engagement, {imputation.id: M("20")}, {}) == {imputation.id: M("40")}


# --- Avec base -----------------------------------------------------------------------------------


@pytest.fixture
def lot2d(client: TestClient, session: Session, lot2: dict[str, Any]) -> dict[str, Any]:
    """Contrôleur financier en plus, et un type de dépense hors marché avec un seuil large."""
    a = session.get_one(EtablissementModele, uuid.UUID(lot2["a"]))
    habiliter(session, AF_A, Profil.AF, a)
    session.commit()
    type_depense = creer(
        client,
        ADMIN,
        "/api/v1/types-depenses",
        {"code": "FONCT", "libelle": "Fonctionnement", "seuilHorsMarche": "1000000000.00"},
    )
    return lot2 | {"type_depense": type_depense}


def _corps(
    s: dict[str, Any], origine: str, montant: str = "10000000.00", **autres: Any
) -> dict[str, Any]:
    corps: dict[str, Any] = {
        "etablissementId": s["a"],
        "origine": origine,
        "dateEngagement": "2026-03-01",
        "objet": f"Achat {uuid.uuid4().hex[:6]}",
        "montant": montant,
        "centreId": s["centre"]["id"],
        "fournisseurId": s["fournisseur"]["id"],
        "imputations": [{"ligneId": s["med"]["id"], "montant": montant}],
    }
    if origine == "HORS_MARCHE":
        corps |= {"typeDepenseId": s["type_depense"]["id"], "natureHorsMarche": "PETIT_ACHAT"}
    return corps | autres


def _soumettre(client: TestClient, e: dict[str, Any]) -> Any:
    return client.post(f"/api/v1/engagements/{e['id']}/soumissions", headers=entetes(GMC_A))


def _viser(client: TestClient, ressource: str, identifiant: str, valideurs: tuple[int, ...]) -> Any:
    reponse = None
    for v in valideurs:
        reponse = client.post(
            f"/api/v1/{ressource}/{identifiant}/validations",
            json={"decision": "VALIDE"},
            headers=entetes(v),
        )
        assert reponse.status_code == 201, reponse.json()
    return reponse


def _valide(client: TestClient, s: dict[str, Any], origine: str, **autres: Any) -> dict[str, Any]:
    e = creer(client, GMC_A, "/api/v1/engagements", _corps(s, origine, **autres))
    assert _soumettre(client, e).status_code == 201, _soumettre(client, e).json()
    _viser(client, "engagements", e["id"], (AF_A, VAL_A, ORD_A))
    lu: dict[str, Any] = client.get(f"/api/v1/engagements/{e['id']}", headers=entetes(VAL_A)).json()
    return lu


@pytest.mark.parametrize("origine", ORIGINES)
def test_rg15_engagement_incoherent_refuse(
    client: TestClient, lot2d: dict[str, Any], origine: str
) -> None:
    """Critère de T-140."""
    corps = _corps(lot2d, origine, imputations=[{"ligneId": lot2d["med"]["id"], "montant": "1.00"}])
    refus = poster(client, GMC_A, "/api/v1/engagements", corps)
    assert (refus.status_code, refus.json()["code"]) == (422, "ENGAGEMENT_INCOHERENT")
    sans_origine = poster(client, GMC_A, "/api/v1/engagements", _corps(lot2d, "CONTRAT"))
    assert sans_origine.json()["champ"] == "contratId"
    e = creer(client, GMC_A, "/api/v1/engagements", _corps(lot2d, origine))
    assert (e["statut"], e["numero"]) == ("BROUILLON", "ENG-2026-00001")


@pytest.mark.parametrize("origine", ORIGINES)
def test_circuit_engage_et_immuabilite(
    client: TestClient, lot2d: dict[str, Any], origine: str
) -> None:
    """Engagé et en cours (6.1) ; API-04 : un engagement validé répond 409 (T-116)."""
    e = creer(client, GMC_A, "/api/v1/engagements", _corps(lot2d, origine))
    _soumettre(client, e)
    assert disponibilite(client, lot2d["med"]["id"])["enCoursValidation"] == "10000000.00"
    etat = _viser(client, "engagements", e["id"], (AF_A,)).json()
    assert (etat["statut"], [x["libelle"] for x in etat["etapes"]]) == (
        "EN_CONTROLE",
        ["Contrôle financier", "Visa DAF", "Ordonnateur"],
    )
    _viser(client, "engagements", e["id"], (VAL_A, ORD_A))
    med = disponibilite(client, lot2d["med"]["id"])
    assert (med["engage"], med["enCoursValidation"], med["disponibleApresEngagements"]) == (
        "10000000.00",
        "0.00",
        "80000000.00",
    )
    lu = client.get(f"/api/v1/engagements/{e['id']}", headers=entetes(GMC_A)).json()
    modif = client.patch(
        f"/api/v1/engagements/{e['id']}",
        json={"objet": "Autre"},
        headers=entetes(GMC_A, **{"If-Match": f'"{lu["version"]}"'}),
    )
    assert (modif.status_code, modif.json()["code"]) == (409, "OPERATION_NON_MODIFIABLE")


@pytest.mark.parametrize("origine", ORIGINES)
def test_rg02_credit_insuffisant_et_derogation_limitee(
    client: TestClient, lot2d: dict[str, Any], origine: str
) -> None:
    """Critères de T-142 (dépassement bloqué sans dérogation) et T-118 (RG-19)."""
    e = creer(client, GMC_A, "/api/v1/engagements", _corps(lot2d, origine, montant="95000000.00"))
    refus = _soumettre(client, e)
    assert (refus.status_code, refus.json()["code"]) == (422, "CONTROLE_BLOQUANT")
    assert refus.json()["ecarts"][0] | {"ligne": ""} == {
        "code": "CREDIT_INSUFFISANT",
        "nature": "CREDIT",
        "depassement": "5000000.00",
        "ligne": "",
        "disponible": "90000000.00",
    }
    url = f"/api/v1/engagements/{e['id']}/derogations"
    petite = creer(
        client,
        GMC_A,
        url,
        {"nature": "CREDIT", "montantDepassement": "4000000.00", "motif": "Urgence"},
    )
    _viser(client, "derogations", petite["id"], (VAL_A, ORD_A))
    assert _soumettre(client, e).status_code == 422
    suffisante = creer(
        client,
        GMC_A,
        url,
        {"nature": "CREDIT", "montantDepassement": "5000000.00", "motif": "Urgence"},
    )
    _viser(client, "derogations", suffisante["id"], (VAL_A, ORD_A))
    controles = client.get(
        f"/api/v1/engagements/{e['id']}/controles", headers=entetes(VAL_A)
    ).json()
    assert [(c["code"], c["leve"]) for c in controles] == [("CREDIT_INSUFFISANT", True)]
    assert _soumettre(client, e).status_code == 201
    # La dérogation ne couvre que son objet : le même dépassement ailleurs reste bloqué.
    autre = creer(
        client, GMC_A, "/api/v1/engagements", _corps(lot2d, origine, montant="95000000.00")
    )
    assert _soumettre(client, autre).json()["code"] == "CONTROLE_BLOQUANT"


def test_rec03_plafond_du_marche(client: TestClient, lot2d: dict[str, Any]) -> None:
    """RG-04 et REC-03, critère de T-144 : engagement lié au marché, crédits et plafond
    contrôlés."""
    marche = _contrat_valide(client, lot2d, "MARCHE")
    imputations = [
        {"ligneId": lot2d["med"]["id"], "montant": "50000000.00"},
        {"ligneId": lot2d["cmd"]["id"], "montant": "30000000.00"},
    ]
    _valide(
        client,
        lot2d,
        "CONTRAT",
        contratId=marche["id"],
        montant="80000000.00",
        imputations=imputations,
    )
    assert _synthese(client, marche)["engage"] == "80000000.00"
    assert _synthese(client, marche)["tauxConsommation"] == "80.00"
    trop = creer(
        client,
        GMC_A,
        "/api/v1/engagements",
        _corps(
            lot2d,
            "CONTRAT",
            contratId=marche["id"],
            montant="30000000.00",
            imputations=[{"ligneId": lot2d["med"]["id"], "montant": "30000000.00"}],
        ),
    )
    ecarts = _soumettre(client, trop).json()["ecarts"]
    assert [(x["code"], x["depassement"]) for x in ecarts] == [("PLAFOND_DEPASSE", "10000000.00")]


def test_coherence_contrat_et_fournisseur(client: TestClient, lot2d: dict[str, Any]) -> None:
    """Critère de T-145 : un bénéficiaire autre que le titulaire est refusé, sans dérogation."""
    marche = _contrat_valide(client, lot2d, "MARCHE")
    autre = creer(
        client, ADMIN, "/api/v1/fournisseurs", {"code": "AUTRE", "raisonSociale": "Autre SA"}
    )
    e = creer(
        client,
        GMC_A,
        "/api/v1/engagements",
        _corps(lot2d, "CONTRAT", contratId=marche["id"], fournisseurId=autre["id"]),
    )
    ecarts = _soumettre(client, e).json()["ecarts"]
    assert [(x["code"], x["nature"]) for x in ecarts] == [("FOURNISSEUR_INCOHERENT", None)]


@pytest.mark.parametrize("origine", ORIGINES)
def test_doublon_signale(client: TestClient, lot2d: dict[str, Any], origine: str) -> None:
    """Critère de T-146."""
    corps = _corps(lot2d, origine, objet="Réactifs de laboratoire")
    premier = creer(client, GMC_A, "/api/v1/engagements", corps)
    _soumettre(client, premier)
    second = creer(client, GMC_A, "/api/v1/engagements", corps | {"dateEngagement": "2026-03-20"})
    ecarts = _soumettre(client, second).json()["ecarts"]
    assert [(x["code"], x["engagements"]) for x in ecarts] == [
        ("DOUBLON_PROBABLE", premier["numero"])
    ]


def test_seuil_hors_marche(client: TestClient, lot2d: dict[str, Any]) -> None:
    """Critère de T-147 et section 17, point 9 : sans seuil, la dérogation est exigée."""
    sans_seuil = creer(
        client, ADMIN, "/api/v1/types-depenses", {"code": "MISSION", "libelle": "Missions"}
    )
    e = creer(
        client,
        GMC_A,
        "/api/v1/engagements",
        _corps(lot2d, "HORS_MARCHE", typeDepenseId=sans_seuil["id"]),
    )
    assert _soumettre(client, e).json()["ecarts"][0]["code"] == "SEUIL_NON_DEFINI"
    petit = creer(
        client,
        ADMIN,
        "/api/v1/types-depenses",
        {"code": "PETIT", "libelle": "Petits achats", "seuilHorsMarche": "5000000.00"},
    )
    depasse = creer(
        client,
        GMC_A,
        "/api/v1/engagements",
        _corps(lot2d, "HORS_MARCHE", typeDepenseId=petit["id"]),
    )
    ecart = _soumettre(client, depasse).json()["ecarts"][0]
    assert (ecart["code"], ecart["depassement"]) == ("SEUIL_HORS_MARCHE_DEPASSE", "5000000.00")
    dans_le_seuil = creer(
        client,
        GMC_A,
        "/api/v1/engagements",
        _corps(lot2d, "HORS_MARCHE", montant="5000000.00", typeDepenseId=petit["id"]),
    )
    assert _soumettre(client, dans_le_seuil).status_code == 201


@pytest.mark.parametrize("origine", ORIGINES)
def test_idempotence_de_la_creation(
    client: TestClient, lot2d: dict[str, Any], origine: str
) -> None:
    """Critère de T-149 : un rejeu avec la même clé ne crée pas de doublon."""
    corps = _corps(lot2d, origine)
    cle = {"Idempotency-Key": uuid.uuid4().hex}
    premier = client.post("/api/v1/engagements", json=corps, headers=entetes(GMC_A, **cle))
    rejeu = client.post("/api/v1/engagements", json=corps, headers=entetes(GMC_A, **cle))
    assert premier.json()["id"] == rejeu.json()["id"]
    liste = client.get("/api/v1/engagements", headers=entetes(VAL_A)).json()
    assert liste["pagination"]["total"] == 1


@pytest.mark.parametrize("origine", ORIGINES)
def test_annulation_partielle_puis_totale(
    client: TestClient, lot2d: dict[str, Any], origine: str
) -> None:
    """RG-09 et RG-18 : annulation motivée et tracée, l'engagement initial reste intact.
    Critères de T-117 (initial visible avec son annulation) et annulation de T-148."""
    e = _valide(client, lot2d, origine)
    url = f"/api/v1/engagements/{e['id']}"
    imputation = e["imputations"][0]["id"]
    assert poster(client, GMC_A, f"{url}/annulations", {"motif": "x"}).status_code == 403
    partielle = client.post(
        f"{url}/annulations",
        json={
            "motif": "Besoin réduit",
            "lignes": [{"imputationId": imputation, "montant": "3000000.00"}],
        },
        headers=entetes(AF_A),
    )
    assert partielle.status_code == 201, partielle.json()
    assert disponibilite(client, lot2d["med"]["id"])["engage"] == "7000000.00"
    trop = client.post(
        f"{url}/annulations",
        json={"motif": "Erreur", "lignes": [{"imputationId": imputation, "montant": "8000000.00"}]},
        headers=entetes(AF_A),
    )
    assert (trop.status_code, trop.json()["code"]) == (409, "ANNULATION_IMPOSSIBLE")
    cloture = client.post(f"{url}/clotures", json={"motif": "Fin"}, headers=entetes(AF_A))
    assert cloture.json()["code"] == "ANNULATION_IMPOSSIBLE"  # rien d'exécuté avant le lot 4
    client.post(f"{url}/annulations", json={"motif": "Abandon"}, headers=entetes(VAL_A))
    lu = client.get(url, headers=entetes(VAL_A)).json()
    assert (lu["statut"], lu["montant"], lu["montantAnnule"]) == (
        "ANNULE",
        "10000000.00",
        "10000000.00",
    )
    historique = client.get(f"{url}/annulations", headers=entetes(VAL_A)).json()
    assert [(a["type"], a["montant"]) for a in historique] == [
        ("ANNULATION", "3000000.00"),
        ("ANNULATION", "7000000.00"),
    ]
    assert disponibilite(client, lot2d["med"]["id"])["engage"] == "0.00"
    journal = client.get(
        f"/api/v1/journal-audit?idObjet={e['id']}", headers=entetes(AUDITEUR)
    ).json()
    assert [x["action"] for x in journal["donnees"]][-2:] == ["ANNULATION", "ANNULATION"]


# --- T-143 : contrôle atomique du crédit (RG-20, REC-16) ------------------------------------------


def test_rec16_deux_engagements_simultanes_un_seul_passe(moteur: Engine) -> None:
    """RG-20 et REC-16, critère de T-143 : deux validations concurrentes sur le même crédit,
    une seule passe.

    Données validées en base (deux connexions réelles), puis supprimées.
    """
    suffixe = uuid.uuid4().hex[:8]
    with Session(moteur) as s:
        etablissement = EtablissementModele(code=f"R16-{suffixe}", nom="Concurrence", actif=True)
        s.add(etablissement)
        s.flush()
        exercice = ExerciceModele(
            code=f"X{suffixe[:5]}",
            date_ouverture=date(2026, 1, 1),
            date_cloture=date(2026, 12, 31),
            statut="OUVERT",
        )
        noeud = NoeudNomenclatureModele(niveau="PARAGRAPHE", code=f"R16-{suffixe}", libelle="Test")
        source = ReferentielModele(
            type="SOURCE_FINANCEMENT",
            code=f"S{suffixe}",
            libelle="Source",
            type_financement="BUDGET_ETAT",
        )
        centre = CentreResponsabiliteModele(
            etablissement_id=etablissement.id, code=f"C{suffixe}", libelle="Centre", type="AUTRE"
        )
        s.add_all([exercice, noeud, source, centre])
        s.flush()
        budget = BudgetModele(
            exercice_id=exercice.id,
            etablissement_id=etablissement.id,
            reference=f"B{suffixe}",
            type="PRIMITIF",
        )
        s.add(budget)
        s.flush()
        ligne = LigneBudgetaireModele(
            budget_id=budget.id,
            etablissement_id=etablissement.id,
            code="L1",
            libelle="Ligne",
            compte_budgetaire_id=noeud.id,
            centre_id=centre.id,
            source_id=source.id,
            dotation_initiale=M("100.00"),
        )
        s.add(ligne)
        s.flush()
        ids = []
        for n in (1, 2):
            e = EngagementModele(
                etablissement_id=etablissement.id,
                exercice_id=exercice.id,
                numero=f"E{n}",
                date_engagement=date(2026, 3, n),
                objet=f"Achat {n}",
                origine="DECISION_AUTORISEE",
                montant=M("80.00"),
                centre_id=centre.id,
                statut="EN_CONTROLE",
                cree_par_id=1,
                cree_par_code="AG001",
                cree_le=datetime.now(UTC),
            )
            s.add(e)
            s.flush()
            s.add(
                ImputationEngagementModele(
                    engagement_id=e.id, ligne_id=ligne.id, montant=M("80.00")
                )
            )
            ids.append(e.id)
        nettoyage = [
            (ImputationEngagementModele, ImputationEngagementModele.engagement_id.in_(ids)),
            (EngagementModele, EngagementModele.id.in_(ids)),
            (LigneBudgetaireModele, LigneBudgetaireModele.id == ligne.id),
            (BudgetModele, BudgetModele.id == budget.id),
            (CentreResponsabiliteModele, CentreResponsabiliteModele.id == centre.id),
            (ReferentielModele, ReferentielModele.id == source.id),
            (NoeudNomenclatureModele, NoeudNomenclatureModele.id == noeud.id),
            (ExerciceModele, ExerciceModele.id == exercice.id),
            (EtablissementModele, EtablissementModele.id == etablissement.id),
        ]
        s.commit()

    depart = threading.Barrier(2)
    resultats: list[str] = []

    def valider(engagement_id: uuid.UUID) -> None:
        with Session(moteur) as s:
            depot = DepotEngagementsSql(s)
            cible = EngagementValidable(depot, HorlogeFixe(), depot.engagement(engagement_id))  # type: ignore[arg-type]
            depart.wait()
            try:
                cible.controler_validation_finale()
                time.sleep(0.3)  # l'autre validation attend le verrou de la ligne
                cible.changer_statut("VALIDE")
                s.commit()
                resultats.append("VALIDE")
            except ErreurMetier as exc:
                s.rollback()
                resultats.append(exc.code)

    try:
        fils = [threading.Thread(target=valider, args=(i,)) for i in ids]
        for f in fils:
            f.start()
        for f in fils:
            f.join(timeout=30)
        assert sorted(resultats) == ["CONTROLE_BLOQUANT", "VALIDE"]
    finally:
        with Session(moteur) as s:
            for modele, condition in nettoyage:
                s.execute(delete(modele).where(condition))
            s.commit()


def test_rg01_engagement_rattache_a_un_exercice_et_a_ses_lignes(
    client: TestClient, lot2d: dict[str, Any]
) -> None:
    """RG-01 : l'engagement prend l'exercice de ses lignes ; des lignes de deux exercices, ou
    une ligne inconnue, sont refusées."""
    from tests.test_audit_cloture import _exercice_2027

    suivant = _exercice_2027(client, lot2d, ["604-MED"])
    melange = poster(
        client,
        GMC_A,
        "/api/v1/engagements",
        _corps(
            lot2d,
            "DECISION_AUTORISEE",
            montant="2.00",
            imputations=[
                {"ligneId": lot2d["med"]["id"], "montant": "1.00"},
                {"ligneId": suivant["604-MED"]["id"], "montant": "1.00"},
            ],
        ),
    )
    assert (melange.status_code, melange.json()["champ"]) == (422, "imputations")
    inconnue = poster(
        client,
        GMC_A,
        "/api/v1/engagements",
        _corps(
            lot2d,
            "DECISION_AUTORISEE",
            montant="1.00",
            imputations=[{"ligneId": str(uuid.uuid4()), "montant": "1.00"}],
        ),
    )
    assert inconnue.json()["champ"] == "imputations"
    e = creer(client, GMC_A, "/api/v1/engagements", _corps(lot2d, "DECISION_AUTORISEE"))
    assert e["exerciceId"] == lot2d["exercice"]["id"]
