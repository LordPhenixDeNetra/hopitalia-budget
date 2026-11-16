"""Recette blanche : répétition de la recette sur la pile Docker complète, avant la séance réelle.

À lancer depuis `backend/`, la pile de simulation démarrée sur une base vide
(docs/recette/recette-blanche.md) :
    .venv/Scripts/python ../simulation/recette_blanche.py

Sur un serveur, le script tourne dans un conteneur de la pile (service `demonstration` de
docker-compose.dokploy.yml), réglé par des variables : RECETTE_API, RECETTE_SIMULE, RECETTE_COURRIER
(adresses des services), RECETTE_JWT_CLE (clé secrète des jetons), RECETTE_DANS_LA_PILE=oui (outils du
module lancés directement) et RECETTE_SI_BASE_VIDE=oui (rien n'est fait si la base est déjà remplie).

Le paramétrage passe par l'API, comme le ferait l'administrateur ; le jeu d'essai de l'annexe 18.2
est saisi et vérifié par les mêmes étapes que les tests automatisés (REC-14), mais contre la vraie
pile (nginx exclu) : base PostgreSQL, Hopitalia simulé, tâches planifiées, serveur de courrier de
test. Le résultat est écrit dans docs/recette/repetition-recette.md.

Une répétition ne remplace ni la séance avec la DAF ni sa signature : elle trouve les anomalies
avant elles.
"""

import os
import subprocess
import sys
import time
import traceback
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / "backend"))

from tests import conftest  # noqa: E402  (après l'ajout du chemin des tests)
from tests.conftest import entetes  # noqa: E402
from tests.test_commandes import REC_A  # noqa: E402
from tests.test_contrats import GMC_A  # noqa: E402
from tests.test_engagements import AF_A  # noqa: E402
from tests.test_lot1 import (  # noqa: E402
    ADMIN,
    AUDITEUR,
    LEC_B,
    ORD_A,
    RB_A,
    VAL_A,
    VAL_ORD_A,
)
from tests.test_paiements import CPT_A, VAL_CPT_A  # noqa: E402
from tests.test_recette_chaine_depense import test_rec14_jeu_d_essai_de_l_annexe_18_2  # noqa: E402

API = os.environ.get("RECETTE_API", "http://127.0.0.1:8000")
SIMULE = os.environ.get("RECETTE_SIMULE", "http://127.0.0.1:8090")
COURRIER = os.environ.get("RECETTE_COURRIER", "http://127.0.0.1:8025")
DANS_LA_PILE = os.environ.get("RECETTE_DANS_LA_PILE") == "oui"
# Sur un serveur, la clé des jetons est secrète : les jetons de la répétition sont signés avec elle.
if cle := os.environ.get("RECETTE_JWT_CLE"):
    conftest.jeton.__defaults__ = (*(conftest.jeton.__defaults__ or ())[:-1], cle)
COMPOSE = [
    "docker",
    "compose",
    "-p",
    "hopitalia-budget-simulation",
    "-f",
    "docker-compose.yml",
    "-f",
    "docker-compose.simulation.yml",
]
RAPPORT = RACINE / "docs" / "recette" / "repetition-recette.md"

client = httpx.Client(base_url=API, timeout=120)
resultats: list[tuple[str, str, str, str]] = []
s: dict[str, Any] = {}


def etape(reference: str, intitule: str) -> Callable[[Callable[[], str]], None]:
    """Exécute l'étape et note son résultat ; une anomalie n'arrête pas la répétition."""

    def lancer(fonction: Callable[[], str]) -> None:
        try:
            constat = fonction()
            resultats.append((reference, intitule, "Conforme", constat))
        except Exception as exc:  # noqa: BLE001  (toute anomalie est notée au procès-verbal)
            trace = traceback.format_exception_only(type(exc), exc)[-1].strip()
            resultats.append((reference, intitule, "Non conforme", trace[:400]))
        print(f"{resultats[-1][2]:<13} {reference} {intitule}")

    return lancer


def creer(utilisateur: int, url: str, corps: Any) -> dict[str, Any]:
    reponse = client.post(
        url,
        json=corps,
        headers=entetes(utilisateur, **{"Idempotency-Key": f"{time.time_ns()}"}),
    )
    assert reponse.status_code == 201, (url, reponse.status_code, reponse.text[:300])
    resultat: dict[str, Any] = reponse.json()
    return resultat


def outil(service: str, module: str, *arguments: str) -> str:
    """Outil du module (`python -m …`) : dans le conteneur du service sur un poste, directement
    quand le script tourne lui-même dans la pile."""
    commande = (
        [sys.executable, "-m", module, *arguments]
        if DANS_LA_PILE
        else [*COMPOSE, "exec", "-T", service, "python", "-m", module, *arguments]
    )
    sortie = subprocess.run(
        commande, cwd=RACINE, capture_output=True, encoding="utf-8", check=True
    )
    return sortie.stdout.strip()


def attendre_api() -> None:
    for _ in range(60):
        try:
            if client.get("/health").status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(2)


# Déploiement : la démonstration remplit la base au premier démarrage seulement.
if os.environ.get("RECETTE_SI_BASE_VIDE") == "oui":
    attendre_api()
    deja = client.get("/api/v1/etablissements", headers=entetes(ADMIN))
    if deja.status_code == 200 and deja.json()["donnees"]:
        print("Base déjà remplie : rien à faire.")
        sys.exit(0)


# --- Préparation : paramétrage par l'API, comme l'administrateur -----------------------------


@etape("PREP-01", "Pile démarrée, premier administrateur attribué sur le serveur")
def _() -> str:
    attendre_api()
    outil(
        "api",
        "hopitalia_budget.outils.habiliter",
        "--utilisateur-id",
        str(ADMIN),
        "--code-agent",
        f"AG{ADMIN:03d}",
        "--profil",
        "ADM",
    )
    return "API saine ; ADM attribué par la commande `habiliter`."


@etape("PREP-02", "Établissements, profils de chaque agent (annuaire Hopitalia simulé)")
def _() -> str:
    for code in ("CHU-A", "CHU-B"):
        s[code] = creer(
            ADMIN, "/api/v1/etablissements", {"code": code, "nom": f"CHU {code[-1]}"}
        )
    s["a"], s["b"] = s["CHU-A"]["id"], s["CHU-B"]["id"]
    profils = [
        (RB_A, "RB", "a"),
        (VAL_A, "VAL", "a"),
        (ORD_A, "ORD", "a"),
        (VAL_ORD_A, "VAL", "a"),
        (VAL_ORD_A, "ORD", "a"),
        (LEC_B, "LEC", "b"),
        (AUDITEUR, "AUD", None),
        (GMC_A, "GMC", "a"),
        (AF_A, "AF", "a"),
        (REC_A, "REC", "a"),
        (CPT_A, "CPT", "a"),
        (VAL_CPT_A, "VAL", "a"),
        (VAL_CPT_A, "CPT", "a"),
    ]
    for utilisateur, profil, etablissement in profils:
        corps: dict[str, Any] = {"codeAgent": f"AG{utilisateur:03d}", "profil": profil}
        if etablissement:
            corps["etablissementId"] = s[etablissement]
        creer(ADMIN, "/api/v1/habilitations", corps)
    return f"{len(profils)} profils attribués par l'écran Habilitations (API), noms lus dans l'annuaire."


@etape("REC-01", "Nomenclature, référentiels, exercice et budget avec ses crédits")
def _() -> str:
    nomenclature = (
        RACINE / "docs" / "cadrage" / "nomenclature-budgetaire.csv"
    ).read_text("utf-8")
    rapport = client.post(
        "/api/v1/nomenclature/imports",
        content=nomenclature.encode(),
        headers=entetes(ADMIN, **{"Content-Type": "text/csv"}),
    )
    assert rapport.status_code == 200, rapport.text[:300]
    comptes = {
        n["code"]: n["id"]
        for n in client.get(
            "/api/v1/nomenclature?niveau=PARAGRAPHE", headers=entetes(ADMIN)
        ).json()
    }
    s["comptes"] = comptes
    s["centre"] = creer(
        ADMIN,
        "/api/v1/centres-responsabilite",
        {
            "etablissementId": s["a"],
            "code": "PHARMA",
            "libelle": "Pharmacie",
            "type": "MEDICO_TECHNIQUE",
        },
    )
    s["source"] = creer(
        ADMIN,
        "/api/v1/sources-financement",
        {
            "code": "ETAT",
            "libelle": "Budget de l'État",
            "typeFinancement": "BUDGET_ETAT",
        },
    )
    s["exercice"] = creer(
        ADMIN,
        "/api/v1/exercices",
        {"code": "2026", "dateOuverture": "2026-01-01", "dateCloture": "2026-12-31"},
    )
    s["budget"] = creer(
        RB_A,
        "/api/v1/budgets",
        {
            "exerciceId": s["exercice"]["id"],
            "etablissementId": s["a"],
            "reference": "BP-2026",
        },
    )
    for cle, code, dotation in (
        ("med", "604-MED", "90000000.00"),
        ("cmd", "604-CMD", "40000000.00"),
    ):
        s[cle] = creer(
            RB_A,
            "/api/v1/lignes-budgetaires",
            {
                "budgetId": s["budget"]["id"],
                "code": code,
                "libelle": code,
                "compteBudgetaireId": comptes[code],
                "centreId": s["centre"]["id"],
                "sourceId": s["source"]["id"],
                "dotationInitiale": dotation,
            },
        )
    s["fournisseur"] = creer(
        ADMIN,
        "/api/v1/fournisseurs",
        {"code": "PHARMA-TEST", "raisonSociale": "Pharma Test SA"},
    )
    s["type_depense"] = creer(
        ADMIN,
        "/api/v1/types-depenses",
        {
            "code": "FONCT",
            "libelle": "Fonctionnement",
            "seuilHorsMarche": "1000000000.00",
        },
    )
    s["mode"] = creer(
        ADMIN, "/api/v1/modes-reglement", {"code": "VIR", "libelle": "Virement"}
    )["id"]
    s["compte"] = creer(
        ADMIN,
        "/api/v1/comptes-tresorerie",
        {"code": "BQ1", "libelle": "Banque", "typeCompte": "BANQUE"},
    )["id"]
    return f"{rapport.json()['crees']} nœuds de nomenclature ; budget BP-2026 : 604-MED 90 M, 604-CMD 40 M."


@etape(
    "COUR-01",
    "Courriels : adresses des agents et règle « crédit insuffisant » par courriel",
)
def _() -> str:
    url = "/api/v1/moi/preferences"
    for utilisateur, langue in ((RB_A, "fr"), (AF_A, "en")):
        reponse = client.put(
            url,
            json={"langue": langue, "courriel": f"agent{utilisateur:03d}@chu-a.test"},
            headers=entetes(utilisateur),
        )
        assert reponse.status_code == 200, reponse.text[:200]
    reponse = client.put(
        f"/api/v1/regles-alertes/CREDIT_INSUFFISANT?etablissementId={s['a']}",
        json={"actif": True, "notifierParEmail": True},
        headers=entetes(ADMIN),
    )
    assert reponse.status_code == 200, reponse.text[:300]
    return "RB (français) et AF (anglais) ont donné leur adresse ; la règle envoie par courriel."


# --- Chaîne de dépense : jeu d'essai de l'annexe 18.2 ------------------------------------------


@etape(
    "REC-14",
    "Jeu d'essai de l'annexe 18.2 (REC-02, 03, 05, 06, 08, 09, 10, 11 compris) et ses contrôles",
)
def _() -> str:
    test_rec14_jeu_d_essai_de_l_annexe_18_2(client, s)  # type: ignore[arg-type]
    return (
        "Marché M-2026-001 et ses pièces saisis et validés profil par profil ; synthèse, lignes, "
        "restes et statuts identiques à l'annexe ; plafond, crédit, doublon et trop-payé bloqués."
    )


@etape("REC-17", "Un agent d'un autre établissement ne voit rien de CHU-A")
def _() -> str:
    engagements = client.get("/api/v1/engagements", headers=entetes(LEC_B)).json()
    assert engagements["donnees"] == [], engagements
    budget = client.get(f"/api/v1/budgets/{s['budget']['id']}", headers=entetes(LEC_B))
    assert budget.status_code == 404, budget.status_code
    return "Liste vide et fiche introuvable (404) pour le lecteur de CHU-B."


@etape("REC-18", "État PDF produit en anglais pour un agent anglophone")
def _() -> str:
    pdf = client.get(
        f"/api/v1/etats/budget?exerciceId={s['exercice']['id']}&format=pdf",
        headers=entetes(AF_A, **{"Accept-Language": "en"}),
    )
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF"), pdf.status_code
    assert pdf.headers["Content-Language"] == "en"
    assert b"Initial and revised budget" in pdf.content
    return f"PDF de {len(pdf.content)} octets, titre en anglais."


# --- Intégration Hopitalia (simulé) ----------------------------------------------------------


def _lancer(type_donnees: str) -> dict[str, Any]:
    reponse = client.post(
        "/api/v1/journal-integration",
        json={"typeDonnees": type_donnees},
        headers=entetes(ADMIN),
    )
    assert reponse.status_code == 200, reponse.text[:300]
    echange: dict[str, Any] = reponse.json()
    assert echange["statut"] == "SUCCES", echange
    return echange


@etape(
    "INT-01", "Fournisseurs et services importés d'Hopitalia, deux fois sans doublon"
)
def _() -> str:
    premier = _lancer("FOURNISSEURS")["resultat"]
    second = _lancer("FOURNISSEURS")["resultat"]
    services = _lancer("SERVICES")["resultat"]
    assert "crees" not in second, second
    httpx.post(f"{SIMULE}/simulation/jour", timeout=30).raise_for_status()
    retrait = _lancer("FOURNISSEURS")["resultat"]
    assert retrait.get("desactives") == 1, retrait
    return (
        f"Fournisseurs : {premier} puis {second} ; services : {services} ; "
        f"après un jour : {retrait} (fournisseur retiré désactivé)."
    )


@etape(
    "INT-03", "Pharmacie : commandes importées, rattachement, réceptions, suppression"
)
def _() -> str:
    import_1 = _lancer("PHARMACIE")["resultat"]
    a_rattacher = client.get(
        "/api/v1/commandes-pharmacie?rattachee=false&taille=100", headers=entetes(AF_A)
    ).json()
    assert a_rattacher["pagination"]["total"] >= 80, a_rattacher["pagination"]
    # Une commande déjà livrée, d'un fournisseur connu : son rattachement crée ses réceptions.
    commande = next(
        c
        for c in a_rattacher["donnees"]
        if c["fournisseurId"] and c["approvisionnementsEnAttente"] > 0
    )
    fournisseur = commande["fournisseurId"]
    engagement = creer(
        GMC_A,
        "/api/v1/engagements",
        {
            "etablissementId": s["a"],
            "origine": "DECISION_AUTORISEE",
            "dateEngagement": "2026-11-01",
            "objet": "Achats de pharmacie",
            "montant": "5000000.00",
            "centreId": s["centre"]["id"],
            "fournisseurId": fournisseur,
            "imputations": [{"ligneId": s["cmd"]["id"], "montant": "5000000.00"}],
        },
    )
    soumission = client.post(
        f"/api/v1/engagements/{engagement['id']}/soumissions", headers=entetes(GMC_A)
    )
    assert soumission.status_code == 201, soumission.text[:300]
    for valideur in (AF_A, VAL_A, ORD_A):
        visa = client.post(
            f"/api/v1/engagements/{engagement['id']}/validations",
            json={"decision": "VALIDE"},
            headers=entetes(valideur),
        )
        assert visa.status_code == 201, visa.text[:300]
    # Relue après validation : l'engagement doit figurer parmi les propositions.
    relues = client.get(
        "/api/v1/commandes-pharmacie?rattachee=false&taille=100", headers=entetes(AF_A)
    ).json()["donnees"]
    propositions = next(c for c in relues if c["id"] == commande["id"])["propositions"]
    assert engagement["id"] in [p["engagementId"] for p in propositions], propositions
    rattachement = client.post(
        f"/api/v1/commandes-pharmacie/{commande['id']}/rattachement",
        json={"engagementId": engagement["id"]},
        headers=entetes(AF_A, **{"Idempotency-Key": f"{time.time_ns()}"}),
    )
    assert rattachement.status_code == 201, rattachement.text[:300]
    rattachee = rattachement.json()
    assert rattachee["approvisionnementsEnAttente"] == 0, rattachee
    receptions = client.get(
        f"/api/v1/bons-commande/{rattachee['bonCommandeId']}/receptions",
        headers=entetes(VAL_A),
    ).json()
    assert receptions and all(r["statut"] == "VALIDE" for r in receptions), receptions
    httpx.post(f"{SIMULE}/simulation/jour", timeout=30).raise_for_status()
    import_2 = _lancer("PHARMACIE")["resultat"]
    # Un approvisionnement déjà reçu est supprimé dans Hopitalia : sa réception est annulée.
    numero = int(commande["numero"].removeprefix("BCP-"))
    httpx.delete(
        f"{SIMULE}/simulation/approvisionnements/{10 * numero}", timeout=30
    ).raise_for_status()
    import_3 = _lancer("PHARMACIE")["resultat"]
    assert import_3.get("annulations") == 1, import_3
    statuts = sorted(
        r["statut"]
        for r in client.get(
            f"/api/v1/bons-commande/{rattachee['bonCommandeId']}/receptions",
            headers=entetes(VAL_A),
        ).json()
    )
    assert "ANNULE" in statuts, statuts
    return (
        f"Premier import : {import_1} ; {a_rattacher['pagination']['total']} commandes à rattacher ; "
        f"{len(propositions)} engagement(s) proposé(s) ; rattachement de {commande['numero']} : "
        f"{len(receptions)} réception(s) validée(s) créée(s) ; "
        f"après un jour : {import_2} ; approvisionnement reçu supprimé dans Hopitalia : "
        f"{import_3}, réceptions {statuts}."
    )


# --- Recettes et courriels -------------------------------------------------------------------


@etape(
    "RCT-01", "Volet recettes : activation, recette, facturé, encaissé, tableau de bord"
)
def _() -> str:
    url = f"/api/v1/etablissements/{s['a']}"
    version = client.get(url, headers=entetes(ADMIN)).headers["ETag"]
    active = client.patch(
        url,
        json={"voletRecettesActif": True},
        headers=entetes(ADMIN, **{"If-Match": version}),
    )
    assert active.status_code == 200, active.text[:300]
    debiteur = creer(
        ADMIN,
        "/api/v1/debiteurs",
        {"code": "ETAT", "nom": "Trésor public", "type": "ETAT"},
    )
    recette = creer(
        RB_A,
        "/api/v1/recettes",
        {
            "etablissementId": s["a"],
            "exerciceId": s["exercice"]["id"],
            "nature": "SUBVENTION_DOTATION",
            "libelle": "Subvention de fonctionnement 2026",
            "montantPrevisionnel": "120000000.00",
            "sourceId": s["source"]["id"],
            "debiteurId": debiteur["id"],
        },
    )
    for type_, montant in (("FACTURE", "60000000.00"), ("ENCAISSEMENT", "45000000.00")):
        creer(
            RB_A,
            f"/api/v1/recettes/{recette['id']}/mouvements",
            {"type": type_, "date": "2026-06-30", "montant": montant},
        )
    tableau = client.get(
        f"/api/v1/tableaux-de-bord/recettes?exerciceId={s['exercice']['id']}",
        headers=entetes(RB_A),
    ).json()["totaux"]
    assert (tableau["resteARecouvrer"], tableau["tauxRecouvrement"]) == (
        "15000000.00",
        "75.00",
    )
    return f"Recette {recette['numero']} : reste à recouvrer 15 M, recouvrement 75 %."


@etape("COUR-02", "Courriel d'alerte reçu dans la langue de chaque destinataire")
def _() -> str:
    sortie = ""
    for _ in range(3):
        sortie = outil("courriels", "hopitalia_budget.outils.courriels")
        time.sleep(1)
    messages = httpx.get(f"{COURRIER}/api/v1/messages", timeout=30).json()["messages"]
    recus = {m["To"][0]["Address"]: m["Subject"] for m in messages}
    assert (
        recus.get(f"agent{RB_A:03d}@chu-a.test")
        == "[Hopitalia Budget] Crédit insuffisant"
    ), recus
    assert (
        recus.get(f"agent{AF_A:03d}@chu-a.test")
        == "[Hopitalia Budget] Insufficient credit"
    ), recus
    return (
        f"{len(messages)} courriel(s) dans la boîte de test ; dernier envoi : {sortie}."
    )


# --- Procès-verbal de répétition ---------------------------------------------------------------


def ecrire_rapport() -> None:
    version = subprocess.run(
        ["git", "describe", "--tags", "--always", "--dirty"],
        cwd=RACINE,
        capture_output=True,
        text=True,
    ).stdout.strip()
    conformes = sum(1 for r in resultats if r[2] == "Conforme")
    lignes = [
        "# Répétition de la recette (recette blanche)",
        "",
        f"**Projet :** Hopitalia Budget · **Date :** {datetime.now(UTC):%d/%m/%Y %H:%M} UTC · "
        f"**Version :** `{version}` · **Statut :** répétition, sans valeur de procès-verbal",
        "",
        "Produit par `simulation/recette_blanche.py` sur la pile Docker de simulation "
        "(`docker-compose.simulation.yml`) : base PostgreSQL neuve, Hopitalia simulé, serveur de "
        "courrier de test. Mode d'emploi : [recette-blanche.md](recette-blanche.md).",
        "",
        f"**Résultat :** {conformes} étape(s) conforme(s) sur {len(resultats)}.",
        "",
        "| Réf. | Étape | Résultat | Constat |",
        "|---|---|---|---|",
        *[
            f"| {ref} | {intitule} | {resultat} | {constat.replace('|', '/')} |"
            for ref, intitule, resultat, constat in resultats
        ],
        "",
        "## Ce que cette répétition ne remplace pas",
        "",
        "- La séance de recette avec la DAF (T-198), ses constats et sa signature (T-286).",
        "- La vérification sur une instance Hopitalia réelle : la forme des réponses simulées suit la "
        "note d'intégration, pas des réponses observées (T-201, T-202).",
        "- Le serveur de messagerie de l'hôpital et l'environnement de recette sur ses serveurs (T-254).",
        "",
    ]
    RAPPORT.write_text("\n".join(lignes), encoding="utf-8", newline="\n")
    print(
        f"\n{conformes}/{len(resultats)} conformes ; procès-verbal de répétition : {RAPPORT}"
    )


if __name__ == "__main__":
    ecrire_rapport()
    sys.exit(0 if all(r[2] == "Conforme" for r in resultats) else 1)
