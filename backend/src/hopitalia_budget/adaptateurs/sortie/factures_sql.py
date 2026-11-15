"""Factures et liquidations en base : montants liquidés (6.3), cumuls par ligne et par contrat,
état lu par les contrôles de la liquidation, dépôt."""

from collections import defaultdict
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from hopitalia_budget.adaptateurs.sortie.commandes_sql import accepte_valide, lignes_commande
from hopitalia_budget.adaptateurs.sortie.modeles import (
    AnnulationLigneModele,
    BonCommandeModele,
    ContratModele,
    DeductionModele,
    EngagementModele,
    FactureModele,
    ImputationEngagementModele,
    LiquidationModele,
    LiquidationReceptionModele,
    ReceptionModele,
)
from hopitalia_budget.adaptateurs.sortie.workflow_sql import pieces_obligatoires_presentes
from hopitalia_budget.domaine.commandes import StatutReception, montant_ttc
from hopitalia_budget.domaine.engagements import StatutEngagement
from hopitalia_budget.domaine.erreurs import ErreurMetier
from hopitalia_budget.domaine.factures import (
    ZERO,
    EtatLiquidation,
    Facture,
    Liquidation,
    StatutFacture,
    StatutLiquidation,
    TypeFacture,
    statut_apres_liquidation,
)
from hopitalia_budget.domaine.indicateurs import (
    Deduction,
    MontantsLiquidation,
    calculer_liquidation,
)

F, L, Imp, E = FactureModele, LiquidationModele, ImputationEngagementModele, EngagementModele


def deductions(session: Session, liquidation_ids: list[UUID]) -> dict[UUID, list[Deduction]]:
    resultat: defaultdict[UUID, list[Deduction]] = defaultdict(list)
    for d in session.scalars(
        select(DeductionModele).where(DeductionModele.liquidation_id.in_(liquidation_ids))
    ):
        resultat[d.liquidation_id].append(Deduction(d.type, d.montant))
    return resultat


def montants(
    session: Session, liquidations: list[LiquidationModele]
) -> dict[UUID, MontantsLiquidation]:
    """6.3 pour chaque liquidation : liquidé, déductions, net à payer, consommation budgétaire."""
    toutes = deductions(session, [m.id for m in liquidations])
    return {m.id: calculer_liquidation(m.montant_base, toutes[m.id]) for m in liquidations}


def _validees(session: Session, *filtre: object) -> list[LiquidationModele]:
    return list(session.scalars(select(L).where(L.statut == StatutLiquidation.VALIDE, *filtre)))  # type: ignore[arg-type]


def liquide_par_imputation(session: Session, imputation_ids: list[UUID]) -> dict[UUID, Decimal]:
    """Montant liquidé validé par imputation (RG-17 : chaque liquidation en a une seule)."""
    validees = _validees(session, L.imputation_id.in_(imputation_ids))
    resultat: defaultdict[UUID, Decimal] = defaultdict(lambda: ZERO)
    for m, mt in zip(validees, montants(session, validees).values(), strict=True):
        resultat[m.imputation_id] += mt.montant_liquide
    return resultat


def liquide_et_net_par_ligne(
    session: Session, ligne_ids: list[UUID]
) -> tuple[dict[UUID, Decimal], dict[UUID, Decimal]]:
    """6.1 : consommation budgétaire et nets à payer des liquidations validées, par ligne."""
    lignes = dict(
        session.execute(select(Imp.id, Imp.ligne_id).where(Imp.ligne_id.in_(ligne_ids))).all()
    )
    validees = _validees(session, L.imputation_id.in_(list(lignes)))
    liquide: defaultdict[UUID, Decimal] = defaultdict(lambda: ZERO)
    net: defaultdict[UUID, Decimal] = defaultdict(lambda: ZERO)
    for m, mt in zip(validees, montants(session, validees).values(), strict=True):
        liquide[lignes[m.imputation_id]] += mt.consommation_budgetaire
        net[lignes[m.imputation_id]] += mt.net_a_payer
    return liquide, net


def factures_par_contrat(
    session: Session, contrat_ids: list[UUID]
) -> tuple[dict[UUID, Decimal], dict[UUID, Decimal], dict[UUID, Decimal]]:
    """6.2 : facturé (net des avoirs, hors factures rejetées), liquidé et net à payer validés."""
    facture: defaultdict[UUID, Decimal] = defaultdict(lambda: ZERO)
    for contrat, ttc in session.execute(
        select(E.contrat_id, func.sum(F.montant_ttc))
        .join(E, E.id == F.engagement_id)
        .where(E.contrat_id.in_(contrat_ids), F.statut != StatutFacture.REJETEE)
        .group_by(E.contrat_id)
    ):
        if contrat is not None:
            facture[contrat] += ttc
    contrats = {
        imputation: contrat
        for imputation, contrat in session.execute(
            select(Imp.id, E.contrat_id)
            .join(E, E.id == Imp.engagement_id)
            .where(E.contrat_id.in_(contrat_ids))
        )
        if contrat is not None
    }
    validees = _validees(session, L.imputation_id.in_(list(contrats)))
    liquide: defaultdict[UUID, Decimal] = defaultdict(lambda: ZERO)
    net: defaultdict[UUID, Decimal] = defaultdict(lambda: ZERO)
    for m, mt in zip(validees, montants(session, validees).values(), strict=True):
        liquide[contrats[m.imputation_id]] += mt.montant_liquide
        net[contrats[m.imputation_id]] += mt.net_a_payer
    return facture, liquide, net


def deductions_du_contrat(session: Session, contrat_id: UUID) -> list[Deduction]:
    """Déductions des liquidations validées du contrat (avance récupérée, retenues)."""
    ids = list(
        session.scalars(
            select(L.id)
            .join(Imp, Imp.id == L.imputation_id)
            .join(E, E.id == Imp.engagement_id)
            .where(E.contrat_id == contrat_id, L.statut == StatutLiquidation.VALIDE)
        )
    )
    return [d for liste in deductions(session, ids).values() for d in liste]


def vers_facture(m: FactureModele) -> Facture:
    return Facture(
        m.id,
        m.etablissement_id,
        m.engagement_id,
        m.fournisseur_id,
        m.numero,
        TypeFacture(m.type),
        m.date_emission,
        m.montant_ttc,
        StatutFacture(m.statut),
        m.bon_commande_id,
        m.facture_origine_id,
    )


class DepotFacturesSql:
    def __init__(self, session: Session) -> None:
        self.session = session

    def liquidation(self, liquidation_id: UUID) -> Liquidation | None:
        m = self.session.get(L, liquidation_id)
        if m is None:
            return None
        facture = self.session.get_one(F, m.facture_id)
        engagement = self.session.get_one(E, facture.engagement_id)
        receptions = tuple(
            self.session.scalars(
                select(LiquidationReceptionModele.reception_id).where(
                    LiquidationReceptionModele.liquidation_id == m.id
                )
            )
        )
        return Liquidation(
            m.id,
            m.etablissement_id,
            m.facture_id,
            m.imputation_id,
            m.numero,
            m.montant_base,
            montants(self.session, [m])[m.id].montant_liquide,
            StatutLiquidation(m.statut),
            m.cree_par_id,
            engagement.centre_id,
            receptions,
        )

    def facture(self, facture_id: UUID) -> Facture | None:
        m = self.session.get(F, facture_id)
        return vers_facture(m) if m else None

    def etat(self, liquidation: Liquidation, verrouiller: bool) -> EtatLiquidation:
        """Contexte des contrôles ; en validation finale, l'imputation est verrouillée (RG-20)."""
        s = self.session
        requete = select(Imp).where(Imp.id == liquidation.imputation_id)
        imputation = s.scalar(requete.with_for_update() if verrouiller else requete)
        if imputation is None:
            raise ErreurMetier("RESSOURCE_INTROUVABLE")
        facture = s.get_one(F, liquidation.facture_id)
        annule = s.scalar(
            select(func.coalesce(func.sum(AnnulationLigneModele.montant), 0)).where(
                AnnulationLigneModele.imputation_id == imputation.id
            )
        )
        autres = _validees(s, L.imputation_id == imputation.id, L.id != liquidation.id)
        deja_liquide = sum((mt.montant_liquide for mt in montants(s, autres).values()), ZERO)
        base_autres = s.scalar(
            select(func.coalesce(func.sum(L.montant_base), 0)).where(
                L.facture_id == facture.id,
                L.id != liquidation.id,
                L.statut != StatutLiquidation.REJETE,
            )
        )
        commandes = (
            [facture.bon_commande_id]
            if facture.bon_commande_id
            else list(
                s.scalars(
                    select(BonCommandeModele.id).where(
                        BonCommandeModele.engagement_id == facture.engagement_id
                    )
                )
            )
        )
        filtre_factures = (
            F.bon_commande_id == facture.bon_commande_id
            if facture.bon_commande_id
            else F.engagement_id == facture.engagement_id
        )
        facture_cumulee = s.scalar(
            select(func.coalesce(func.sum(F.montant_ttc), 0)).where(
                filtre_factures, F.statut != StatutFacture.REJETEE
            )
        )
        receptionne = ZERO
        for bc in commandes:
            accepte = accepte_valide(s, bc)
            receptionne += sum(
                (
                    montant_ttc(accepte.get(lc.id, ZERO), lc.prix_unitaire, lc.taux_taxe)
                    for lc in lignes_commande(s, bc)
                ),
                ZERO,
            )
        validees = s.scalar(
            select(func.count())
            .select_from(ReceptionModele)
            .where(
                ReceptionModele.id.in_(liquidation.reception_ids),
                ReceptionModele.statut == StatutReception.VALIDE,
            )
        )
        return EtatLiquidation(
            liquidation=liquidation,
            type_facture=TypeFacture(facture.type),
            exige_service_fait=bool(commandes),
            receptions_validees=validees or 0,
            reste_du_imputation=imputation.montant - Decimal(annule or 0) - deja_liquide,
            reste_facture=facture.montant_ttc - Decimal(base_autres or 0),
            facture_cumulee=Decimal(facture_cumulee or 0),
            receptionne=receptionne,
        )

    def changer_statut(self, liquidation_id: UUID, statut: StatutLiquidation) -> None:
        """Statut de la liquidation ; une fois validée, la facture et l'engagement suivent."""
        s = self.session
        m = s.get_one(L, liquidation_id)
        m.statut = statut
        s.flush()
        if statut is not StatutLiquidation.VALIDE:
            return
        facture = s.get_one(F, m.facture_id)
        base_validee = s.scalar(
            select(func.coalesce(func.sum(L.montant_base), 0)).where(
                L.facture_id == facture.id, L.statut == StatutLiquidation.VALIDE
            )
        )
        facture.statut = statut_apres_liquidation(vers_facture(facture), Decimal(base_validee or 0))
        engagement = s.get_one(E, facture.engagement_id)
        if engagement.statut in (StatutEngagement.VALIDE, StatutEngagement.PARTIELLEMENT_EXECUTE):
            imputations = list(s.scalars(select(Imp.id).where(Imp.engagement_id == engagement.id)))
            liquide = sum(liquide_par_imputation(s, imputations).values(), ZERO)
            annule = s.scalar(
                select(func.coalesce(func.sum(AnnulationLigneModele.montant), 0)).where(
                    AnnulationLigneModele.imputation_id.in_(imputations)
                )
            )
            # Section 8.1 : exécuté quand le liquidé atteint l'engagé (net des annulations).
            engagement.statut = (
                StatutEngagement.EXECUTE
                if liquide >= engagement.montant - Decimal(annule or 0)
                else StatutEngagement.PARTIELLEMENT_EXECUTE
            )
        s.flush()

    def avance_restant_a_recuperer(
        self, facture_id: UUID
    ) -> tuple[Decimal | None, Decimal | None, Decimal]:
        """Taux de retenue et d'avance du contrat de la facture, et avance restant à récupérer."""
        from hopitalia_budget.adaptateurs.sortie.contrats_sql import mouvements_contrats
        from hopitalia_budget.domaine.indicateurs import (
            calculer_avance_retenue,
            calculer_indicateurs_contrat,
        )

        facture = self.session.get_one(F, facture_id)
        engagement = self.session.get_one(E, facture.engagement_id)
        if engagement.contrat_id is None:
            return None, None, ZERO
        contrat = self.session.get_one(ContratModele, engagement.contrat_id)
        actualise = calculer_indicateurs_contrat(
            mouvements_contrats(self.session, [contrat])[contrat.id]
        ).montant_actualise
        suivi = calculer_avance_retenue(
            actualise, contrat.taux_avance, deductions_du_contrat(self.session, contrat.id)
        )
        return contrat.taux_retenue_garantie, contrat.taux_avance, suivi.avance_restant_a_recuperer

    def pieces_obligatoires_presentes(self, type_objet: str, id_objet: UUID) -> bool:
        return pieces_obligatoires_presentes(self.session, type_objet, id_objet)
