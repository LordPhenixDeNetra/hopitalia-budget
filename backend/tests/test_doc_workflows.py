# ruff: noqa: E501  (texte du document généré : une phrase par ligne)

"""Description des workflows et matrice des habilitations (T-281), produites depuis le domaine.

Cycles de référence (`TRANSITIONS_REFERENCE`), opérations (`OPERATIONS`), circuits par défaut et
matrice (`MATRICE`) sont lus dans le code : le document ne peut pas s'en écarter. Le test échoue si
`docs/conception/workflows-et-habilitations.md` n'est plus à jour. Régénérer depuis `backend/` :
`python -m tests.test_doc_workflows`.
"""

from pathlib import Path

from hopitalia_budget.domaine.habilitations import MATRICE, Droit, Operation, Profil
from hopitalia_budget.domaine.workflow import (
    CIRCUIT_PAR_DEFAUT,
    CIRCUITS_PAR_DEFAUT,
    JUSTIFIABLES_SANS_CIRCUIT,
    OPERATIONS,
    ORDONNATEUR_FINAL,
    TRANSITIONS_REFERENCE,
)
from tests.test_domaine import LIBELLES

RACINE = Path(__file__).parents[2]
DOCUMENT = RACINE / "docs" / "conception" / "workflows-et-habilitations.md"

PROFILS = {
    Profil.ADM: "Administrateur fonctionnel",
    Profil.RB: "Responsable budgétaire",
    Profil.AF: "Agent financier",
    Profil.GMC: "Gestionnaire de marchés et contrats",
    Profil.SD: "Service demandeur",
    Profil.REC: "Réceptionnaire",
    Profil.VAL: "Valideur (responsable de service, DAF)",
    Profil.ORD: "Ordonnateur",
    Profil.CPT: "Comptable, agent de paiement",
    Profil.AUD: "Auditeur",
    Profil.LEC: "Lecteur de tableaux de bord",
}
OBJETS = {
    "RevisionBudgetaire": "Révision budgétaire",
    "Contrat": "Contrat",
    "Avenant": "Avenant",
    "Engagement": "Engagement",
    "Derogation": "Dérogation",
    "Reception": "Réception (service fait)",
    "Liquidation": "Liquidation",
    "Facture": "Facture",
}
ACTIONS = {
    "SOUMETTRE": "Soumettre",
    "VISER": "Viser (d'autres étapes restent)",
    "VALIDER": "Valider (dernière étape : l'opération prend effet)",
    "REJETER": "Rejeter",
    "RETOURNER": "Retourner pour correction",
}
DROITS = {Droit.SAISIR: "S", Droit.VALIDER: "V", Droit.CONSULTER: "L"}
LIBELLE_OPERATION = {operation: libelle for libelle, operation in LIBELLES.items()}

# Cycles sans circuit de validation : décrits ici, appliqués par leurs routes.
AUTRES_CYCLES = """## Cycles sans circuit de validation

| Objet | Statuts | Qui le fait avancer |
|---|---|---|
| Facture | `RECUE`, `EN_CONTROLE` (une liquidation saisie), `RETOURNEE`, `REJETEE`, `LIQUIDEE`, `MISE_EN_PAIEMENT`, `PARTIELLEMENT_PAYEE`, `PAYEE` | L'agent financier l'enregistre ; ses statuts suivent ses liquidations et ses paiements. Un doublon est bloqué, sauf levée motivée (RG-16). |
| Bon de commande | Émis, sans circuit | Le gestionnaire de marchés l'émet sur un engagement validé, dans la limite de son montant net (EF-CMD-01). Une commande de la pharmacie est rattachée par l'agent financier (EF-REC-07). |
| Ordonnancement | `PREPARE`, `TRANSMIS`, `COMPLEMENT_DEMANDE`, `SUSPENDU`, `REJETE`, `PRIS_EN_CHARGE` | L'ordonnateur prépare et transmet ; le comptable prend en charge, demande un complément, suspend ou rejette. |
| Paiement | `EXECUTE`, `ANNULE` | Le comptable l'enregistre une fois exécuté ; une annulation est motivée et tracée. |
| Annulation d'une opération validée | Enregistrée, sans circuit | Un agent habilité (AF, VAL ou ORD) l'enregistre avec un motif, tracée (RG-18). La matrice prévoit une demande par AF validée par VAL ou ORD : circuit propre reporté (`POINTS_REPORTES.md`). |
| Clôture d'exercice | Close, rouverte | Le responsable budgétaire ou l'ordonnateur clôt et rouvre, avec motif ; les engagements non soldés sont reportés. |
| Réception importée de la pharmacie | `VALIDE`, `ANNULE` | Créée validée par l'import d'Hopitalia (preuve : bon de livraison) ; annulée si l'approvisionnement est supprimé dans Hopitalia. |
"""

SEPARATION = """## Séparation des tâches (RG-13)

Pour une même opération, une même personne ne peut pas cumuler :

| Rôle 1 | Rôle 2 | Raison |
|---|---|---|
| Demander l'engagement | Valider l'engagement | On ne valide pas sa propre demande. |
| Contrôler l'engagement | Valider l'engagement | Contrôle et décision distincts. |
| Enregistrer la réception | Valider le service fait | La preuve est confirmée par une autre personne. |
| Liquider | Valider la liquidation | On ne valide pas son propre calcul. |
| Valider la liquidation | Enregistrer le paiement | Celui qui reconnaît la dette ne la paie pas. |
| Ordonnancer | Enregistrer le paiement | Séparation ordonnateur et comptable. |
| Demander une dérogation | Accorder la dérogation | On ne s'autorise pas soi-même. |

Ces règles valent aussi par délégation : le délégataire ne valide pas une opération qu'il a saisie. Un circuit marqué « séparation des tâches » refuse le visa de l'auteur de la pièce.
"""


def _profils(operation: Operation, droit: Droit) -> str:
    retenus = [p.value for p, d in MATRICE[operation].items() if d is droit]
    return ", ".join(retenus) or "aucun"


def document() -> str:
    lignes = [
        "# Workflows et matrice des habilitations",
        "",
        "**Projet :** Hopitalia Budget · **Tâche :** T-281 · **Référence :** cahier des charges V3, "
        "sections 7.6, 8 et 17 ; matrice validée le 13/11/2026 (`docs/cadrage/matrice-habilitations.md`)",
        "",
        "Produit depuis le domaine (`domaine/workflow.py`, `domaine/habilitations.py`). Ne pas le "
        "modifier à la main : le régénérer depuis `backend/` par `python -m tests.test_doc_workflows`. "
        "Le test `test_doc_workflows.py` échoue si ce fichier n'est plus à jour.",
        "",
        "**Statut :** à valider par la DAF (critère de fin de T-281).",
        "",
        "## Profils",
        "",
        "| Code | Profil |",
        "|---|---|",
        *[f"| {p.value} | {libelle} |" for p, libelle in PROFILS.items()],
        "",
        "## Matrice des habilitations",
        "",
        "S : saisir ; V : valider ; L : consulter ; — : aucun accès. Le droit vaut dans le "
        "périmètre de l'agent (son ou ses établissements).",
        "",
        "| Opération | " + " | ".join(p.value for p in Profil) + " |",
        "|---|" + "---|" * len(Profil),
    ]
    for operation in Operation:
        cases = [DROITS.get(MATRICE[operation].get(p), "—") for p in Profil]  # type: ignore[arg-type]
        lignes.append(f"| {LIBELLE_OPERATION[operation]} | " + " | ".join(cases) + " |")
    lignes += ["", "## Objets validés par circuit", ""]
    lignes += [
        "Une pièce se saisit, se soumet, puis passe les étapes de son circuit. Chaque étape est un "
        "profil qui a le droit « Valider » dans la matrice. Un établissement peut paramétrer ses "
        "circuits (par service et par seuil de montant) ; pour les objets marqués ci-dessous, la "
        "dernière étape revient toujours à l'ordonnateur (section 17, point 16).",
        "",
    ]
    for type_objet, transitions in TRANSITIONS_REFERENCE.items():
        saisie, validations = OPERATIONS[type_objet]
        circuit = CIRCUITS_PAR_DEFAUT.get(type_objet, CIRCUIT_PAR_DEFAUT)
        etapes = " ; ".join(f"{e.ordre}. {e.libelle} ({e.profil.value})" for e in circuit.etapes)
        valideurs = sorted(
            {p.value for o in validations for p, d in MATRICE[o].items() if d is Droit.VALIDER}
        )
        lignes += [
            f"### {OBJETS[type_objet]}",
            "",
            f"- Saisie : {LIBELLE_OPERATION[saisie].lower()} — profils {_profils(saisie, Droit.SAISIR)}.",
            f"- Profils qui peuvent viser : {', '.join(valideurs)}.",
            f"- Circuit par défaut : {etapes}.",
            f"- Ordonnateur en dernière étape obligatoire : {'Oui' if type_objet in ORDONNATEUR_FINAL else 'Non'}.",
            "",
            "| Depuis | Action | Vers |",
            "|---|---|---|",
            *[f"| `{t.depuis}` | {ACTIONS[t.action.value]} | `{t.vers}` |" for t in transitions],
            "",
        ]
    for type_objet in sorted(JUSTIFIABLES_SANS_CIRCUIT):
        saisie, _ = OPERATIONS[type_objet]
        lignes += [
            f"### {OBJETS[type_objet]}",
            "",
            f"Porte des pièces justificatives sans circuit propre : saisie par {_profils(saisie, Droit.SAISIR)} ; "
            "ses liquidations sont validées par leur circuit.",
            "",
        ]
    lignes += [AUTRES_CYCLES, SEPARATION]
    return "\n".join(lignes).rstrip("\n") + "\n"


def test_document_workflows_a_jour() -> None:
    """Critère de T-281 (partie code) : le document suit le domaine."""
    assert DOCUMENT.read_text(encoding="utf-8") == document()


if __name__ == "__main__":
    DOCUMENT.write_text(document(), encoding="utf-8", newline="\n")
    print(f"{DOCUMENT} écrit.")
