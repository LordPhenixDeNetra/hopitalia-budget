"""Cas d'utilisation du workflow transverse (T-111 à T-116), communs à tous les objets validables.

Circuit figé à la soumission ; visa à l'étape ouverte par le profil de l'étape (ou par délégation) ;
séparation des tâches selon le circuit (RG-13) ; rejet et retour motivés ; transitions de statut
limitées à celles paramétrées ; objet validé immuable (RG-18).
"""

from dataclasses import dataclass

from hopitalia_budget.domaine.alertes import Alerteur, Signal, TypeAlerte, signaux_des_controles
from hopitalia_budget.domaine.controles import ResultatControle
from hopitalia_budget.domaine.erreurs import ErreurMetier
from hopitalia_budget.domaine.habilitations import Profil
from hopitalia_budget.domaine.ports import EvenementAudit, Horloge, JournaliseurAudit
from hopitalia_budget.domaine.utilisateur import Utilisateur
from hopitalia_budget.domaine.workflow import (
    CIRCUIT_PAR_DEFAUT,
    CIRCUITS_PAR_DEFAUT,
    TRANSITIONS_REFERENCE,
    Action,
    Circuit,
    Decision,
    DepotWorkflow,
    Etape,
    Justifiable,
    ObjetValidable,
    Transition,
    Validable,
    Visa,
    appliquer,
    choisir_circuit,
    cycle_courant,
    etapes_ouvertes,
)


@dataclass(frozen=True)
class EtatValidation:
    statut: str
    circuit: Circuit
    visas: list[Visa]
    etapes_ouvertes: list[Etape]
    peut_decider: bool


def _transitions(depot: DepotWorkflow, o: ObjetValidable) -> list[Transition]:
    # Sans paramétrage propre à l'établissement, le cycle de vie de référence s'applique.
    return depot.transitions(o.etablissement_id, o.type_objet) or list(
        TRANSITIONS_REFERENCE[o.type_objet]
    )


def _references(depot: DepotWorkflow, o: ObjetValidable) -> dict[str, str]:
    references = {s: s for t in TRANSITIONS_REFERENCE[o.type_objet] for s in (t.depuis, t.vers)}
    return references | depot.statuts_personnalises(o.etablissement_id, o.type_objet)


def _circuit(depot: DepotWorkflow, o: ObjetValidable) -> Circuit:
    """Circuit figé ; avant la première soumission, celui qui s'appliquerait (aperçu)."""
    return depot.circuit_fige(o.type_objet, o.id) or choisir_circuit(
        depot.circuits(o.etablissement_id, o.type_objet),
        o.montant,
        o.centre_id,
        CIRCUITS_PAR_DEFAUT.get(o.type_objet, CIRCUIT_PAR_DEFAUT),
    )


def _statut(depot: DepotWorkflow, o: ObjetValidable) -> str:
    return depot.statut_courant(o.type_objet, o.id) or o.statut_reference


def profils_effectifs(
    depot: DepotWorkflow, horloge: Horloge, utilisateur: Utilisateur, o: ObjetValidable
) -> dict[Profil, str | None]:
    """Profils propres de l'agent, puis ceux reçus par délégation active (code du délégant)."""
    profils: dict[Profil, str | None] = {}
    jour = horloge.maintenant().date()
    for profil, delegant in depot.profils_delegues(
        utilisateur.id_hopitalia, o.etablissement_id, jour
    ):
        profils.setdefault(profil, delegant)
    for h in utilisateur.habilitations:
        if h.etablissement_id in (None, o.etablissement_id):
            profils[h.profil] = None
    return profils


def engager(depot: DepotWorkflow, o: ObjetValidable) -> None:
    """À la première soumission : le circuit applicable est figé pour toute la vie de l'objet."""
    depot.figer(o.type_objet, o.id, _circuit(depot, o), o.statut_reference)


def etat(
    depot: DepotWorkflow, horloge: Horloge, utilisateur: Utilisateur, cible: Validable
) -> EtatValidation:
    o = cible.objet()
    circuit = _circuit(depot, o)
    visas = depot.visas(o.type_objet, o.id)
    cycle = cycle_courant(visas)
    statut = _statut(depot, o)
    # En circuit : le statut (personnalisé ou non) se rattache à un statut de référence d'où un
    # visa est possible.
    reference = _references(depot, o).get(statut)
    en_cours = any(
        t.depuis == reference and t.action in (Action.VISER, Action.VALIDER)
        for t in TRANSITIONS_REFERENCE[o.type_objet]
    )
    ouvertes = (
        etapes_ouvertes(
            circuit, {v.ordre for v in cycle if v.ordre and v.decision is Decision.VALIDE}
        )
        if en_cours
        else []
    )
    profils = profils_effectifs(depot, horloge, utilisateur, o)
    deja = {o.createur_id} | {v.utilisateur_id for v in cycle}
    peut = any(e.profil in profils for e in ouvertes) and not (
        circuit.separation_taches and utilisateur.id_hopitalia in deja
    )
    return EtatValidation(statut, circuit, visas, ouvertes, peut)


def decider(
    depot: DepotWorkflow,
    journal: JournaliseurAudit,
    horloge: Horloge,
    utilisateur: Utilisateur,
    cible: Validable,
    decision: Decision,
    motif: str | None,
    visa: str | None,
) -> EtatValidation:
    o = cible.objet()
    courant = etat(depot, horloge, utilisateur, cible)
    if not courant.etapes_ouvertes:
        raise ErreurMetier("OPERATION_DEJA_TRAITEE")
    profils = profils_effectifs(depot, horloge, utilisateur, o)
    etape = next((e for e in courant.etapes_ouvertes if e.profil in profils), None)
    if etape is None:
        attendue = next(e for e in courant.etapes_ouvertes if e.obligatoire)
        raise ErreurMetier("ETAPE_NON_AUTORISEE", profil=attendue.profil.value)
    cycle = cycle_courant(courant.visas)
    if courant.circuit.separation_taches and utilisateur.id_hopitalia in (
        {o.createur_id} | {v.utilisateur_id for v in cycle}
    ):
        raise ErreurMetier("SEPARATION_DES_TACHES")
    if decision is not Decision.VALIDE and not (motif and motif.strip()):
        raise ErreurMetier("MOTIF_OBLIGATOIRE")

    derniere = etape.ordre == courant.circuit.etapes[-1].ordre
    action = {
        Decision.REJETE: Action.REJETER,
        Decision.A_CORRIGER: Action.RETOURNER,
        Decision.VALIDE: Action.VALIDER if derniere else Action.VISER,
    }[decision]
    nouveau = appliquer(_transitions(depot, o), courant.statut, action, set(profils))
    if decision is Decision.VALIDE:
        if isinstance(cible, Justifiable) and not cible.pieces_obligatoires_presentes():
            raise ErreurMetier("PIECES_MANQUANTES")
        if derniere:
            cible.controler_validation_finale()

    depot.ajouter_visa(
        o.type_objet,
        o.id,
        Visa(
            ordre=etape.ordre,
            etape=etape.profil,
            decision=decision,
            motif=motif,
            visa=visa,
            utilisateur_id=utilisateur.id_hopitalia,
            code_agent=utilisateur.code_agent,
            delegant_code=profils[etape.profil],
            horodatage=horloge.maintenant(),
        ),
    )
    _changer(depot, o, cible, nouveau)
    journal.tracer(
        EvenementAudit(
            action={Decision.VALIDE: "VALIDATION", Decision.REJETE: "REJET"}.get(
                decision, "RETOUR"
            ),
            type_objet=o.type_objet,
            id_objet=str(o.id),
            ancienne_valeur={"statut": courant.statut},
            nouvelle_valeur={
                "statut": nouveau,
                "etape": etape.ordre,
                "profil": etape.profil.value,
                "motif": motif,
                "delegant": profils[etape.profil],
            },
            utilisateur_id=utilisateur.id_hopitalia,
            code_agent=utilisateur.code_agent,
            etablissement_id=o.etablissement_id,
        )
    )
    return etat(depot, horloge, utilisateur, cible)


def _changer(depot: DepotWorkflow, o: ObjetValidable, cible: Validable, nouveau: str) -> None:
    depot.changer_statut_courant(o.type_objet, o.id, nouveau)
    cible.changer_statut(_references(depot, o)[nouveau])


def soumettre(
    depot: DepotWorkflow,
    journal: JournaliseurAudit,
    horloge: Horloge,
    utilisateur: Utilisateur,
    cible: Validable,
) -> EtatValidation:
    """Par l'auteur : première soumission d'un brouillon (le circuit est alors figé), ou renvoi
    au début du même circuit après correction."""
    o = cible.objet()
    if utilisateur.id_hopitalia != o.createur_id:
        raise ErreurMetier("ACCES_REFUSE")
    cible.controler_soumission()
    if depot.circuit_fige(o.type_objet, o.id) is None:
        engager(depot, o)
    statut = _statut(depot, o)
    profils = set(profils_effectifs(depot, horloge, utilisateur, o))
    nouveau = appliquer(_transitions(depot, o), statut, Action.SOUMETTRE, profils)
    _changer(depot, o, cible, nouveau)
    journal.tracer(
        EvenementAudit(
            action="SOUMISSION",
            type_objet=o.type_objet,
            id_objet=str(o.id),
            ancienne_valeur={"statut": statut},
            nouvelle_valeur={"statut": nouveau},
            utilisateur_id=utilisateur.id_hopitalia,
            code_agent=utilisateur.code_agent,
            etablissement_id=o.etablissement_id,
        )
    )
    return etat(depot, horloge, utilisateur, cible)


def signaler(
    alerteur: Alerteur, o: ObjetValidable, resultats: list[ResultatControle]
) -> list[ResultatControle]:
    """T-221 : chaque écart ouvert d'un contrôle crée son alerte, même si l'opération est
    refusée ; renvoie les résultats inchangés."""
    for s in signaux_des_controles(resultats, o.type_objet, o.id, o.etablissement_id):
        alerteur.signaler(s)
    return resultats


def exiger_modifiable(
    depot: DepotWorkflow, o: ObjetValidable, code_agent: str | None = None
) -> None:
    """RG-18 : seul un objet retourné pour correction (qui attend d'être resoumis) se modifie."""
    corrigeables = {
        t.depuis for t in TRANSITIONS_REFERENCE[o.type_objet] if t.action is Action.SOUMETTRE
    }
    if _references(depot, o).get(_statut(depot, o)) not in corrigeables:
        depot.signaler(
            Signal(
                TypeAlerte.MODIFICATION_APRES_VALIDATION,
                o.type_objet,
                o.id,
                o.etablissement_id,
                cle=None,
                details={"statut": o.statut_reference},
                code_agent=code_agent,
            )
        )
        raise ErreurMetier("OPERATION_NON_MODIFIABLE", statut=o.statut_reference)
