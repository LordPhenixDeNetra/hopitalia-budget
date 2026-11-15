"""Engagements en base : cumuls (engagé, en cours), contexte des contrôles, dépôt.

Engagé (6.1) : imputations des engagements validés (date de validation renseignée), moins leurs
annulations et clôtures. En cours de validation : imputations des engagements soumis ou en
contrôle.
"""

from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.orm import Session

from hopitalia_budget.adaptateurs.sortie.derogations_sql import accordees
from hopitalia_budget.adaptateurs.sortie.modeles import (
    AnnulationLigneModele,
    AnnulationModele,
    ContratModele,
    EngagementModele,
    ImputationEngagementModele,
    LigneBudgetaireModele,
    ReferentielModele,
)
from hopitalia_budget.adaptateurs.sortie.workflow_sql import pieces_obligatoires_presentes
from hopitalia_budget.domaine.controles import NatureDerogation
from hopitalia_budget.domaine.engagements import (
    EN_COURS,
    DepenseHorsMarche,
    Engagement,
    ImputationEngagement,
    InfosContrat,
    NatureHorsMarche,
    Origine,
    StatutEngagement,
)

E, Imp, AL = EngagementModele, ImputationEngagementModele, AnnulationLigneModele
ZERO = Decimal("0")


def engage_par_ligne(session: Session, ligne_ids: list[UUID]) -> dict[UUID, Decimal]:
    resultat: defaultdict[UUID, Decimal] = defaultdict(lambda: ZERO)
    for ligne, montant in session.execute(
        select(Imp.ligne_id, func.sum(Imp.montant))
        .join(E, E.id == Imp.engagement_id)
        .where(Imp.ligne_id.in_(ligne_ids), E.date_validation.is_not(None))
        .group_by(Imp.ligne_id)
    ):
        resultat[ligne] += montant
    for ligne, montant in session.execute(
        select(Imp.ligne_id, func.sum(AL.montant))
        .join(Imp, Imp.id == AL.imputation_id)
        .where(Imp.ligne_id.in_(ligne_ids))
        .group_by(Imp.ligne_id)
    ):
        resultat[ligne] -= montant
    return resultat


def en_cours_par_ligne(session: Session, ligne_ids: list[UUID]) -> dict[UUID, Decimal]:
    return dict(
        session.execute(
            select(Imp.ligne_id, func.sum(Imp.montant))
            .join(E, E.id == Imp.engagement_id)
            .where(Imp.ligne_id.in_(ligne_ids), E.statut.in_([s.value for s in EN_COURS]))
            .group_by(Imp.ligne_id)
        ).all()
    )


def engage_par_contrat(
    session: Session, contrat_ids: list[UUID], sauf: UUID | None = None
) -> dict[UUID, Decimal]:
    filtre: list[ColumnElement[bool]] = [
        E.contrat_id.in_(contrat_ids),
        E.date_validation.is_not(None),
    ]
    if sauf is not None:
        filtre.append(E.id != sauf)
    resultat: defaultdict[UUID, Decimal] = defaultdict(lambda: ZERO)
    for contrat, montant in session.execute(
        select(E.contrat_id, func.sum(E.montant)).where(*filtre).group_by(E.contrat_id)
    ):
        if contrat is not None:
            resultat[contrat] += montant
    for contrat, montant in session.execute(
        select(E.contrat_id, func.sum(AL.montant))
        .join(Imp, Imp.id == AL.imputation_id)
        .join(E, E.id == Imp.engagement_id)
        .where(*filtre)
        .group_by(E.contrat_id)
    ):
        if contrat is not None:
            resultat[contrat] -= montant
    return resultat


def vers_engagement(session: Session, m: EngagementModele) -> Engagement:
    imputations = tuple(
        ImputationEngagement(i.id, i.ligne_id, i.montant)
        for i in session.scalars(
            select(Imp).where(Imp.engagement_id == m.id).order_by(Imp.ligne_id)
        )
    )
    commun = {
        "id": m.id,
        "etablissement_id": m.etablissement_id,
        "numero": m.numero,
        "date_engagement": m.date_engagement,
        "objet": m.objet,
        "origine": Origine(m.origine),
        "montant": m.montant,
        "imputations": imputations,
        "statut": StatutEngagement(m.statut),
        "createur_id": m.cree_par_id,
        "centre_id": m.centre_id,
        "contrat_id": m.contrat_id,
        "fournisseur_id": m.fournisseur_id,
        "type_depense_id": m.type_depense_id,
    }
    if m.origine == Origine.HORS_MARCHE:
        nature = NatureHorsMarche(m.nature_hors_marche) if m.nature_hors_marche else None
        return DepenseHorsMarche(**commun, nature=nature, justification=m.justification)  # type: ignore[arg-type]
    return Engagement(**commun)  # type: ignore[arg-type]


class ContexteEngagementSql:
    """Données des contrôles. En validation finale (`verrouiller`), les lignes et le contrat
    sont verrouillés jusqu'à la fin de la transaction : deux engagements simultanés ne
    consomment pas le même crédit (RG-20)."""

    def __init__(self, session: Session, verrouiller: bool) -> None:
        self.session = session
        self.verrouiller = verrouiller

    def disponible(self, ligne_id: UUID) -> tuple[str, Decimal]:
        from hopitalia_budget.adaptateurs.sortie.budget_sql import indicateurs_lignes

        requete = select(LigneBudgetaireModele.code).where(LigneBudgetaireModele.id == ligne_id)
        code = self.session.scalar(requete.with_for_update() if self.verrouiller else requete)
        return code or "", indicateurs_lignes(self.session, [ligne_id])[
            ligne_id
        ].disponible_apres_engagements

    def contrat(self, contrat_id: UUID, engagement_id: UUID) -> InfosContrat | None:
        from hopitalia_budget.adaptateurs.sortie.contrats_sql import mouvements_contrats
        from hopitalia_budget.domaine.indicateurs import calculer_indicateurs_contrat

        requete = select(ContratModele).where(ContratModele.id == contrat_id)
        c = self.session.scalar(requete.with_for_update() if self.verrouiller else requete)
        if c is None:
            return None
        actualise = calculer_indicateurs_contrat(
            mouvements_contrats(self.session, [c])[c.id]
        ).montant_actualise
        autres = engage_par_contrat(self.session, [c.id], sauf=engagement_id)[c.id]
        return InfosContrat(c.statut, c.etablissement_id, c.fournisseur_id, actualise, autres)

    def seuil_hors_marche(self, type_depense_id: UUID) -> Decimal | None:
        type_depense = self.session.get(ReferentielModele, type_depense_id)
        return type_depense.seuil_hors_marche if type_depense else None

    def doublons(self, engagement: Engagement) -> list[str]:
        m = self.session.get_one(E, engagement.id)
        ecart = timedelta(days=30)
        return list(
            self.session.scalars(
                select(E.numero).where(
                    E.id != engagement.id,
                    E.etablissement_id == engagement.etablissement_id,
                    E.fournisseur_id.is_not_distinct_from(engagement.fournisseur_id),
                    E.montant == engagement.montant,
                    func.lower(E.objet) == engagement.objet.lower(),
                    E.date_engagement.between(m.date_engagement - ecart, m.date_engagement + ecart),
                    E.statut.not_in(["BROUILLON", "REJETE", "ANNULE"]),
                )
            )
        )


class DepotEngagementsSql:
    def __init__(self, session: Session) -> None:
        self.session = session

    def engagement(self, engagement_id: UUID) -> Engagement | None:
        m = self.session.get(E, engagement_id)
        return vers_engagement(self.session, m) if m else None

    def contexte(self, verrouiller: bool) -> ContexteEngagementSql:
        return ContexteEngagementSql(self.session, verrouiller)

    def changer_statut(
        self, engagement_id: UUID, statut: StatutEngagement, maintenant: datetime
    ) -> None:
        m = self.session.get_one(E, engagement_id)
        m.statut = statut
        if statut is StatutEngagement.VALIDE and m.date_validation is None:
            m.date_validation = maintenant
        self.session.flush()

    def derogations_accordees(self, engagement_id: UUID) -> dict[NatureDerogation, Decimal]:
        return accordees(self.session, "Engagement", engagement_id)

    def annule_par_imputation(self, engagement_id: UUID) -> dict[UUID, Decimal]:
        return dict(
            self.session.execute(
                select(AL.imputation_id, func.sum(AL.montant))
                .join(Imp, Imp.id == AL.imputation_id)
                .where(Imp.engagement_id == engagement_id)
                .group_by(AL.imputation_id)
            ).all()
        )

    def liquide_par_imputation(self, engagement_id: UUID) -> dict[UUID, Decimal]:
        from hopitalia_budget.adaptateurs.sortie.factures_sql import liquide_par_imputation

        imputations = list(
            self.session.scalars(select(Imp.id).where(Imp.engagement_id == engagement_id))
        )
        return dict(liquide_par_imputation(self.session, imputations))

    def ajouter_annulation(
        self,
        engagement: Engagement,
        type_annulation: str,
        lignes: dict[UUID, Decimal],
        motif: str,
        utilisateur_id: int,
        code_agent: str,
        maintenant: datetime,
    ) -> UUID:
        annulation = AnnulationModele(
            type_objet="Engagement",
            id_objet=engagement.id,
            etablissement_id=engagement.etablissement_id,
            type=type_annulation,
            montant=sum(lignes.values(), ZERO),
            motif=motif,
            utilisateur_id=utilisateur_id,
            code_agent=code_agent,
            horodatage=maintenant,
        )
        self.session.add(annulation)
        self.session.flush()
        for imputation_id, montant in lignes.items():
            self.session.add(
                AL(annulation_id=annulation.id, imputation_id=imputation_id, montant=montant)
            )
        self.session.flush()
        return annulation.id

    def pieces_obligatoires_presentes(self, type_objet: str, id_objet: UUID) -> bool:
        return pieces_obligatoires_presentes(self.session, type_objet, id_objet)
