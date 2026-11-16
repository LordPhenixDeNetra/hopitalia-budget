"""Environnement de démonstration, pour présenter l'application et faire valider ce qui attend une
décision (docs/presentation/parcours-de-validation.md).

À lancer depuis `backend/`, la pile de simulation démarrée sur une base vide :
    .venv/Scripts/python ../simulation/demonstration.py

Rejoue d'abord la recette blanche (jeu d'essai de l'annexe 18.2, intégrations, recettes, courriels),
puis ajoute ce qu'une présentation doit montrer : pièces en attente de visa, alertes planifiées,
courriels reçus, un échange Hopitalia en échec à reprendre devant l'assistance, plusieurs recettes.
Rien n'est masqué : chaque fonction à valider est activée et remplie.
"""

import time
from typing import Any

import httpx
import recette_blanche as rb  # rejoue la recette blanche à l'import
from recette_blanche import (
    ADMIN,
    AF_A,
    COURRIER,
    GMC_A,
    ORD_A,
    RB_A,
    SIMULE,
    VAL_A,
    client,
    compose,
    creer,
    entetes,
    s,
)


def _note(etape: str, constat: str) -> None:
    print(f"{etape:<44} {constat}")


def adresses() -> None:
    """Courriel de chaque profil qui reçoit des alertes, et règles envoyées par courriel."""
    for utilisateur in (VAL_A, ORD_A, GMC_A):
        client.put(
            "/api/v1/moi/preferences",
            json={"courriel": f"agent{utilisateur:03d}@chu-a.test"},
            headers=entetes(utilisateur),
        ).raise_for_status()
    # Seuil des marchés et délai des échéances : valeurs par défaut de la section 14.3.
    regles: dict[str, dict[str, Any]] = {
        "SEUIL_MARCHE": {"seuilPourcent": "80"},
        "DEPASSEMENT_MARCHE": {},
        "FACTURE_DOUBLON": {},
        "ECHEANCE_CONTRAT": {"delaiJours": 60},
    }
    for type_alerte, reglages in regles.items():
        client.put(
            f"/api/v1/regles-alertes/{type_alerte}?etablissementId={s['a']}",
            json={"actif": True, "notifierParEmail": True, **reglages},
            headers=entetes(ADMIN),
        ).raise_for_status()
    # Interface en français pour la séance (la recette blanche avait mis l'agent financier en anglais).
    client.put(
        "/api/v1/moi/preferences", json={"langue": "fr"}, headers=entetes(AF_A)
    ).raise_for_status()
    _note(
        "Courriels",
        "VAL, ORD et GMC ont une adresse ; quatre règles envoient par courriel.",
    )


def pieces_a_valider() -> None:
    """Une révision et un engagement en attente de visa : à valider en séance."""
    revision = creer(
        RB_A,
        "/api/v1/revisions-budgetaires",
        {
            "budgetId": s["budget"]["id"],
            "type": "VIREMENT",
            "ligneSourceId": s["med"]["id"],
            "ligneCibleId": s["cmd"]["id"],
            "montant": "5000000.00",
            "motif": "Besoins en consommables du second semestre",
        },
    )
    engagement = creer(
        GMC_A,
        "/api/v1/engagements",
        {
            "etablissementId": s["a"],
            "origine": "DECISION_AUTORISEE",
            "dateEngagement": "2026-11-10",
            "objet": "Maintenance des équipements de stérilisation",
            "montant": "3500000.00",
            "centreId": s["centre"]["id"],
            "fournisseurId": s["fournisseur"]["id"],
            "imputations": [{"ligneId": s["cmd"]["id"], "montant": "3500000.00"}],
        },
    )
    client.post(
        f"/api/v1/engagements/{engagement['id']}/soumissions", headers=entetes(GMC_A)
    ).raise_for_status()
    client.post(
        f"/api/v1/engagements/{engagement['id']}/validations",
        json={"decision": "VALIDE"},
        headers=entetes(AF_A),
    ).raise_for_status()
    _note(
        "Pièces en attente de visa",
        f"révision {revision['id'][:8]} (VAL puis ORD) ; engagement {engagement['numero']} "
        "contrôlé par AF, en attente du visa DAF.",
    )


def alertes_et_courriels() -> None:
    planification = client.post(
        "/api/v1/alertes/planifications", headers=entetes(ADMIN)
    )
    planification.raise_for_status()
    time.sleep(1)
    sortie = compose(
        "exec", "-T", "courriels", "python", "-m", "hopitalia_budget.outils.courriels"
    )
    recus = httpx.get(f"{COURRIER}/api/v1/messages", timeout=30).json()[
        "messages_count"
    ]
    _note(
        "Alertes planifiées et courriels",
        f"{planification.json()['signaux']} signal(aux) ; envoi : {sortie} ; {recus} courriel(s) reçus.",
    )


def engagements_pharmacie() -> None:
    """Engagements validés pour trois fournisseurs de la pharmacie : leurs commandes ont alors un
    engagement proposé, à rattacher devant l'assistance."""
    commandes = client.get(
        "/api/v1/commandes-pharmacie?rattachee=false&taille=100", headers=entetes(AF_A)
    ).json()["donnees"]
    fournisseurs = list(
        dict.fromkeys(c["fournisseurId"] for c in commandes if c["fournisseurId"])
    )[:3]
    for rang, fournisseur in enumerate(fournisseurs, start=1):
        engagement = creer(
            GMC_A,
            "/api/v1/engagements",
            {
                "etablissementId": s["a"],
                "origine": "DECISION_AUTORISEE",
                "dateEngagement": "2026-11-02",
                "objet": f"Approvisionnement de la pharmacie, lot {rang}",
                "montant": "5000000.00",
                "centreId": s["centre"]["id"],
                "fournisseurId": fournisseur,
                "imputations": [{"ligneId": s["med"]["id"], "montant": "5000000.00"}],
            },
        )
        client.post(
            f"/api/v1/engagements/{engagement['id']}/soumissions",
            headers=entetes(GMC_A),
        ).raise_for_status()
        for valideur in (AF_A, VAL_A, ORD_A):
            client.post(
                f"/api/v1/engagements/{engagement['id']}/validations",
                json={"decision": "VALIDE"},
                headers=entetes(valideur),
            ).raise_for_status()
    proposees = sum(
        1
        for c in client.get(
            "/api/v1/commandes-pharmacie?rattachee=false&taille=100",
            headers=entetes(AF_A),
        ).json()["donnees"]
        if c["propositions"]
    )
    _note(
        "Commandes de la pharmacie",
        f"{proposees} commande(s) avec un engagement proposé.",
    )


def echange_a_reprendre() -> None:
    """Un échange Hopitalia en échec, à reprendre devant l'assistance (écran Intégrations). La
    tâche quotidienne, qui reprendrait l'échec d'elle-même, ne tourne pas dans la pile de
    simulation (docker-compose.simulation.yml)."""
    httpx.post(f"{SIMULE}/simulation/panne?active=true", timeout=30).raise_for_status()
    echec = client.post(
        "/api/v1/journal-integration",
        json={"typeDonnees": "SERVICES"},
        headers=entetes(ADMIN),
    ).json()
    httpx.post(f"{SIMULE}/simulation/panne?active=false", timeout=30).raise_for_status()
    _note(
        "Échange à reprendre",
        f"services : {echec['statut']} ({echec['erreur']}), panne levée.",
    )


def recettes() -> None:
    assurance = creer(
        ADMIN,
        "/api/v1/debiteurs",
        {"code": "ASSUR-SN", "nom": "Assurances du Sénégal", "type": "ASSURANCE"},
    )
    lignes: list[
        tuple[str, str, str | None, list[tuple[str, str, str, str | None]]]
    ] = [
        (
            "PRESTATION_HOSPITALIERE",
            "Consultations et hospitalisations 2026",
            None,
            [
                ("FACTURE", "2026-03-31", "18000000.00", None),
                ("ENCAISSEMENT", "2026-04-30", "12000000.00", None),
            ],
        ),
        (
            "REMBOURSEMENT_ASSURANCE",
            "Remboursements des assurances 2026",
            assurance["id"],
            [
                ("FACTURE", "2026-05-31", "10000000.00", None),
                ("ENCAISSEMENT", "2026-07-15", "2500000.00", None),
                (
                    "ENCAISSEMENT",
                    "2026-07-20",
                    "-500000.00",
                    "Encaissement saisi deux fois",
                ),
            ],
        ),
    ]
    for nature, libelle, debiteur, mouvements in lignes:
        corps: dict[str, Any] = {
            "etablissementId": s["a"],
            "exerciceId": s["exercice"]["id"],
            "nature": nature,
            "libelle": libelle,
            "montantPrevisionnel": "25000000.00",
            "sourceId": s["source"]["id"],
            "centreId": s["centre"]["id"],
        }
        if debiteur:
            corps["debiteurId"] = debiteur
        recette = creer(RB_A, "/api/v1/recettes", corps)
        for type_, date, montant, motif in mouvements:
            mouvement = {"type": type_, "date": date, "montant": montant}
            if motif:
                mouvement["motif"] = motif
            creer(RB_A, f"/api/v1/recettes/{recette['id']}/mouvements", mouvement)
    _note("Recettes", "deux recettes de plus, dont un contre-mouvement motivé.")


if __name__ == "__main__":
    anomalies = [r for r in rb.resultats if r[2] != "Conforme"]
    if anomalies:
        raise SystemExit(
            f"Recette blanche non conforme, démonstration arrêtée : {anomalies}"
        )
    print("\nEnrichissement pour la présentation :")
    adresses()
    pieces_a_valider()
    engagements_pharmacie()
    alertes_et_courriels()
    echange_a_reprendre()
    recettes()
    print(
        "\nDémonstration prête : interface http://127.0.0.1:8080 (comptes agentNNN / recette), "
        "courriels http://127.0.0.1:8025."
    )
