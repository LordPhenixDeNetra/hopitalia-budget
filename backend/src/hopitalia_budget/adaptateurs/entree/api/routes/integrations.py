"""Intégrations (lot 7, T-200 à T-202, T-207) : journal des échanges avec Hopitalia et
reprises (INT-07), commandes de la pharmacie à rattacher aux engagements (INT-03, EF-REC-07).

Les échanges eux-mêmes sont dans adaptateurs/sortie/integrations_hopitalia.py ; la tâche
planifiée `python -m hopitalia_budget.outils.integrations` les lance chaque jour.
"""

from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import JSONResponse
from pydantic import Field
from sqlalchemy import func, select

from hopitalia_budget.adaptateurs.entree.api.crud import (
    JournalDep,
    flush_unique,
    tracer,
)
from hopitalia_budget.adaptateurs.entree.api.dependances import (
    ClientHopitaliaDep,
    HorlogeDep,
    ParametresDep,
    SessionDep,
    UtilisateurDep,
)
from hopitalia_budget.adaptateurs.entree.api.idempotence import (
    empreinte_requete,
    executer_idempotent,
)
from hopitalia_budget.adaptateurs.entree.api.pagination import (
    TAILLE_MAXIMALE,
    Page,
    PageCurseur,
    PageQuery,
    Pagination,
    PaginationCurseur,
    TailleQuery,
    decoder_curseur,
    encoder_curseur,
    lien_page_suivante,
    parametres_autorises,
)
from hopitalia_budget.adaptateurs.entree.api.schemas import Montant, Schema
from hopitalia_budget.adaptateurs.sortie import integrations_hopitalia as echanges
from hopitalia_budget.adaptateurs.sortie.commandes_sql import numero_suivant, total_commande
from hopitalia_budget.adaptateurs.sortie.engagements_sql import DepotEngagementsSql
from hopitalia_budget.adaptateurs.sortie.modeles import (
    ApprovisionnementPharmacieModele,
    BonCommandeModele,
    CommandePharmacieModele,
    EngagementModele,
    ExerciceModele,
    JournalIntegrationModele,
    LigneCommandeModele,
)
from hopitalia_budget.application import engagements, receptions
from hopitalia_budget.application.receptions import ENGAGEMENTS_COMMANDABLES
from hopitalia_budget.domaine.commandes import LigneCommande, TypeOrdre, verifier_lignes_commande
from hopitalia_budget.domaine.erreurs import ErreurMetier
from hopitalia_budget.domaine.habilitations import Droit, Operation
from hopitalia_budget.domaine.utilisateur import Utilisateur

router = APIRouter(tags=["integrations"])
J, CP = JournalIntegrationModele, CommandePharmacieModele
AP = ApprovisionnementPharmacieModele
Quantite = Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=3)]


# --- Journal d'intégration et reprises (T-200, INT-07) ------------------------------------------


class EchangeSortie(Schema):
    id: int
    systeme_externe: str
    direction: str
    type_donnees: echanges.TypeEchange
    identifiant_unique: str
    etablissement_id: UUID | None
    parametres: dict[str, str]
    statut: echanges.StatutEchange
    erreur: str | None
    resultat: dict[str, int] | None
    tentatives: int
    declenche_par_code: str | None
    cree_le: datetime
    date: datetime


class EchangeLancement(Schema):
    type_donnees: echanges.TypeEchange


def _visibles(utilisateur: Utilisateur) -> frozenset[UUID] | None:
    """Journal lisible par qui paramètre ou consulte le paramétrage (matrice : ADM, RB, AUD)."""
    visibles = utilisateur.etablissements_autorises(Operation.PARAMETRER, Droit.CONSULTER)
    if visibles is not None and not visibles:
        raise ErreurMetier("ACCES_REFUSE")
    return visibles


def _exiger_lancement(utilisateur: Utilisateur, etablissement_id: UUID | None) -> None:
    # Fournisseurs : référentiel commun, donc administrateur de tous les établissements.
    if not utilisateur.peut(Operation.PARAMETRER, Droit.SAISIR, etablissement_id):
        raise ErreurMetier("ACCES_REFUSE")


@router.get(
    "/journal-integration",
    response_model=PageCurseur[EchangeSortie],
    dependencies=[Depends(parametres_autorises("typeDonnees", "statut"))],
)
def lister_echanges(
    session: SessionDep,
    utilisateur: UtilisateurDep,
    apres: str | None = None,
    taille: int = Query(100, ge=1, le=TAILLE_MAXIMALE),
    type_donnees: Annotated[echanges.TypeEchange | None, Query(alias="typeDonnees")] = None,
    statut: echanges.StatutEchange | None = None,
) -> PageCurseur[EchangeSortie]:
    """Échanges du plus récent au plus ancien, par curseur (section 11)."""
    visibles = _visibles(utilisateur)
    requete = select(J).order_by(J.cree_le.desc(), J.id.desc()).limit(taille)
    if visibles is not None:
        requete = requete.where(J.etablissement_id.is_(None) | J.etablissement_id.in_(visibles))
    if type_donnees:
        requete = requete.where(J.type_donnees == type_donnees)
    if statut:
        requete = requete.where(J.statut == statut)
    if (curseur := decoder_curseur(apres)) is not None:
        requete = requete.where(
            (J.cree_le < curseur[0]) | ((J.cree_le == curseur[0]) & (J.id < curseur[1]))
        )
    lignes = list(session.scalars(requete))
    suivant = encoder_curseur(lignes[-1].cree_le, lignes[-1].id) if len(lignes) == taille else None
    return PageCurseur[EchangeSortie](
        donnees=[EchangeSortie.model_validate(lg, from_attributes=True) for lg in lignes],
        pagination=PaginationCurseur(taille=taille, suivant=suivant),
    )


@router.post("/journal-integration", response_model=EchangeSortie)
def lancer_echange(
    corps: EchangeLancement,
    session: SessionDep,
    utilisateur: UtilisateurDep,
    client: ClientHopitaliaDep,
    parametres: ParametresDep,
    horloge: HorlogeDep,
) -> EchangeSortie:
    """Lance l'échange du jour sans attendre la tâche planifiée ; relancé, il est rejoué sur la
    même ligne du journal (sans doublon)."""
    type_echange = corps.type_donnees
    etablissement_id = (
        None
        if type_echange == echanges.TypeEchange.FOURNISSEURS
        else echanges.etablissement_cible(session, parametres)
    )
    _exiger_lancement(utilisateur, etablissement_id)
    ligne = echanges.executer(
        session,
        client,
        parametres,
        horloge,
        type_echange,
        echanges.parametres_du_jour(
            type_echange, horloge.maintenant().date(), parametres.integration_fenetre_jours
        ),
        utilisateur.code_agent,
    )
    session.commit()
    return EchangeSortie.model_validate(ligne, from_attributes=True)


@router.post("/journal-integration/{echange_id}/reprises", response_model=EchangeSortie)
def reprendre_echange(
    echange_id: int,
    session: SessionDep,
    utilisateur: UtilisateurDep,
    client: ClientHopitaliaDep,
    parametres: ParametresDep,
    horloge: HorlogeDep,
) -> EchangeSortie:
    """Reprise manuelle d'un échange en échec, avec ses paramètres d'origine (INT-07)."""
    ligne = session.get(J, echange_id)
    visibles = _visibles(utilisateur)
    if ligne is None or (
        visibles is not None
        and ligne.etablissement_id is not None
        and ligne.etablissement_id not in visibles
    ):
        raise ErreurMetier("RESSOURCE_INTROUVABLE")
    _exiger_lancement(utilisateur, ligne.etablissement_id)
    ligne = echanges.reprendre(session, client, parametres, horloge, ligne, utilisateur.code_agent)
    session.commit()
    return EchangeSortie.model_validate(ligne, from_attributes=True)


# --- Commandes de la pharmacie (T-202, EF-REC-07) -------------------------------------------


class LignePharmacie(Schema):
    code_produit: str
    nom_produit: str
    quantite: Quantite
    montant: Montant


class PropositionEngagement(Schema):
    engagement_id: UUID
    numero: str
    objet: str
    reste_a_commander: Montant


class CommandePharmacieSortie(Schema):
    id: UUID
    etablissement_id: UUID
    numero: str
    date_commande: date
    code_fournisseur: str | None
    fournisseur_id: UUID | None
    service: str | None
    lignes: list[LignePharmacie]
    montant: Montant
    bon_commande_id: UUID | None
    approvisionnements_en_attente: int
    propositions: list[PropositionEngagement]


class Rattachement(Schema):
    engagement_id: UUID


def _reste_a_commander(
    depot: DepotEngagementsSql, session: Any, ids: list[UUID]
) -> dict[UUID, Decimal]:
    """Montant net de l'engagement moins ses commandes (EF-CMD-01)."""
    restes: dict[UUID, Decimal] = {}
    for e in session.scalars(select(EngagementModele).where(EngagementModele.id.in_(ids))):
        bons = list(
            session.scalars(
                select(BonCommandeModele.id).where(BonCommandeModele.engagement_id == e.id)
            )
        )
        restes[e.id] = (
            e.montant
            - sum(depot.annule_par_imputation(e.id).values(), Decimal("0"))
            - sum(total_commande(session, bons).values(), Decimal("0"))
        )
    return restes


def _propositions(session: Any, m: CommandePharmacieModele) -> list[PropositionEngagement]:
    """Engagements validés du même fournisseur dont le reste à commander couvre la commande,
    du plus juste au plus large."""
    if m.bon_commande_id is not None or m.fournisseur_id is None:
        return []
    candidats = list(
        session.scalars(
            select(EngagementModele).where(
                EngagementModele.etablissement_id == m.etablissement_id,
                EngagementModele.fournisseur_id == m.fournisseur_id,
                EngagementModele.statut.in_(list(ENGAGEMENTS_COMMANDABLES)),
            )
        )
    )
    restes = _reste_a_commander(DepotEngagementsSql(session), session, [e.id for e in candidats])
    retenus = sorted(
        (e for e in candidats if restes[e.id] >= m.montant), key=lambda e: restes[e.id]
    )
    return [
        PropositionEngagement(
            engagement_id=e.id, numero=e.numero, objet=e.objet, reste_a_commander=restes[e.id]
        )
        for e in retenus[:5]
    ]


def _sortie(session: Any, m: CommandePharmacieModele) -> dict[str, Any]:
    attente = session.scalar(
        select(func.count()).where(
            AP.etablissement_id == m.etablissement_id,
            AP.numero_commande == m.numero,
            AP.reception_id.is_(None),
            AP.supprime.is_(False),
        )
    )
    donnees: dict[str, Any] = CommandePharmacieSortie(
        **{
            c: getattr(m, c)
            for c in CommandePharmacieSortie.model_fields
            if hasattr(m, c) and c != "lignes"
        },
        lignes=[
            LignePharmacie(
                code_produit=lg["codeProduit"],
                nom_produit=lg["nomProduit"],
                quantite=Decimal(lg["quantite"]),
                montant=Decimal(lg["montant"]),
            )
            for lg in m.lignes
        ],
        approvisionnements_en_attente=attente or 0,
        propositions=_propositions(session, m),
    ).model_dump(mode="json", by_alias=True)
    return donnees


def _visibles_pharmacie(utilisateur: Utilisateur) -> frozenset[UUID] | None:
    visibles = utilisateur.etablissements_autorises(
        Operation.RATTACHER_COMMANDE_PHARMACIE, Droit.CONSULTER
    )
    if visibles is not None and not visibles:
        raise ErreurMetier("ACCES_REFUSE")
    return visibles


@router.get(
    "/commandes-pharmacie",
    response_model=Page[CommandePharmacieSortie],
    dependencies=[Depends(parametres_autorises("rattachee", "page", "taille"))],
)
def lister_commandes_pharmacie(
    request: Request,
    session: SessionDep,
    utilisateur: UtilisateurDep,
    rattachee: bool | None = None,
    page: int = PageQuery,
    taille: int = TailleQuery,
) -> dict[str, Any]:
    """Commandes importées de la pharmacie ; `rattachee=false` : la liste « à rattacher »."""
    visibles = _visibles_pharmacie(utilisateur)
    requete = select(CP)
    if visibles is not None:
        requete = requete.where(CP.etablissement_id.in_(visibles))
    if rattachee is not None:
        requete = requete.where(
            CP.bon_commande_id.is_not(None) if rattachee else CP.bon_commande_id.is_(None)
        )
    total = session.scalar(select(func.count()).select_from(requete.subquery())) or 0
    lignes = session.scalars(
        requete.order_by(CP.date_commande.desc(), CP.numero)
        .offset((page - 1) * taille)
        .limit(taille)
    )
    return {
        "donnees": [_sortie(session, m) for m in lignes],
        "pagination": Pagination(
            page=page,
            taille=taille,
            total=total,
            suivant=lien_page_suivante(request, page, taille, total),
        ).model_dump(by_alias=True),
    }


@router.post(
    "/commandes-pharmacie/{commande_id}/rattachement",
    response_model=CommandePharmacieSortie,
    status_code=201,
)
def rattacher_commande_pharmacie(
    commande_id: UUID,
    corps: Rattachement,
    session: SessionDep,
    utilisateur: UtilisateurDep,
    journal: JournalDep,
    horloge: HorlogeDep,
    parametres: ParametresDep,
    empreinte: Annotated[str, Depends(empreinte_requete)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> JSONResponse:
    """Rattache la commande à un engagement validé (EF-REC-07) : le bon de commande du module
    est créé, puis les approvisionnements déjà importés deviennent des réceptions validées."""

    def action() -> tuple[int, object]:
        m = session.get(CP, commande_id)
        visibles = _visibles_pharmacie(utilisateur)
        if m is None or (visibles is not None and m.etablissement_id not in visibles):
            raise ErreurMetier("RESSOURCE_INTROUVABLE")
        receptions.exiger(utilisateur, Operation.RATTACHER_COMMANDE_PHARMACIE, m.etablissement_id)
        if m.bon_commande_id is not None:
            raise ErreurMetier("COMMANDE_DEJA_RATTACHEE")
        depot = DepotEngagementsSql(session)
        engagement = engagements.obtenir(depot, utilisateur, corps.engagement_id)
        if engagement.etablissement_id != m.etablissement_id:
            raise ErreurMetier("REFERENCE_INVALIDE", champ="engagementId")
        if m.fournisseur_id is not None and engagement.fournisseur_id != m.fournisseur_id:
            raise ErreurMetier("FOURNISSEUR_DIFFERENT")
        # Montant d'une ligne Hopitalia = total de la ligne ; prix unitaire déduit, au centime.
        lignes = [
            LigneCommande(
                UUID(int=0),
                i + 1,
                f"{lg['codeProduit']} — {lg['nomProduit']}"[:300],
                Decimal(lg["quantite"]),
                (Decimal(lg["montant"]) / Decimal(lg["quantite"])).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
                if Decimal(lg["quantite"])
                else Decimal("0"),
                Decimal("0"),
            )
            for i, lg in enumerate(m.lignes)
        ]
        verifier_lignes_commande(lignes)
        bons = list(
            session.scalars(
                select(BonCommandeModele.id).where(BonCommandeModele.engagement_id == engagement.id)
            )
        )
        receptions.verifier_emission(
            engagement,
            sum(depot.annule_par_imputation(engagement.id).values(), Decimal("0")),
            sum(total_commande(session, bons).values(), Decimal("0")),
            sum((lg.montant_ttc for lg in lignes), Decimal("0")),
        )
        exercice = session.get_one(
            ExerciceModele, session.get_one(EngagementModele, engagement.id).exercice_id
        )
        bon = BonCommandeModele(
            etablissement_id=m.etablissement_id,
            engagement_id=engagement.id,
            fournisseur_id=engagement.fournisseur_id,
            numero=numero_suivant(
                session, BonCommandeModele, m.etablissement_id, "BC", exercice.code
            ),
            type=TypeOrdre.BON_COMMANDE,
            date_emission=m.date_commande,
            lieu_livraison=m.service,
            date_livraison_prevue=None,
            cree_par_id=utilisateur.id_hopitalia,
            cree_par_code=utilisateur.code_agent,
            cree_le=horloge.maintenant(),
        )
        session.add(bon)
        flush_unique(session, bon.numero)
        for lg in lignes:
            session.add(
                LigneCommandeModele(
                    bon_commande_id=bon.id,
                    rang=lg.rang,
                    designation=lg.designation,
                    quantite=lg.quantite,
                    prix_unitaire=lg.prix_unitaire,
                    taux_taxe=lg.taux_taxe,
                )
            )
        m.bon_commande_id = bon.id
        session.flush()
        tracer(
            journal,
            utilisateur,
            "RATTACHEMENT",
            "CommandePharmacie",
            m.id,
            None,
            {
                "numero": m.numero,
                "engagementId": str(engagement.id),
                "bonCommande": bon.numero,
                "montant": format(m.montant, "f"),
            },
            m.etablissement_id,
        )
        en_attente = session.scalars(
            select(ApprovisionnementPharmacieModele)
            .where(
                ApprovisionnementPharmacieModele.etablissement_id == m.etablissement_id,
                ApprovisionnementPharmacieModele.numero_commande == m.numero,
            )
            .order_by(ApprovisionnementPharmacieModele.date_approvisionnement)
        )
        for appro in en_attente:
            echanges.creer_reception(session, journal, horloge.maintenant(), appro)
        return 201, _sortie(session, m)

    reponse = executer_idempotent(
        session,
        horloge,
        timedelta(hours=parametres.duree_cle_idempotence_heures),
        utilisateur.id_hopitalia,
        idempotency_key,
        empreinte,
        action,
    )
    session.commit()
    return reponse
