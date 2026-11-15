"""Dépôt SQL des contrats et avenants ; montants agrégés pour les indicateurs du contrat (6.2)."""

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from hopitalia_budget.adaptateurs.sortie.commandes_sql import commande_et_receptionne_par_contrat
from hopitalia_budget.adaptateurs.sortie.engagements_sql import engage_par_contrat
from hopitalia_budget.adaptateurs.sortie.factures_sql import factures_par_contrat
from hopitalia_budget.adaptateurs.sortie.modeles import (
    AvenantModele,
    ContratModele,
    ImputationContratModele,
)
from hopitalia_budget.adaptateurs.sortie.paiements_sql import transmis_et_paye_par_contrat
from hopitalia_budget.adaptateurs.sortie.workflow_sql import pieces_obligatoires_presentes
from hopitalia_budget.domaine.contrats import (
    Avenant,
    Contrat,
    Marche,
    NatureMarche,
    Statut,
    TypeContrat,
)
from hopitalia_budget.domaine.indicateurs import (
    ZERO,
    MouvementsContrat,
    calculer_indicateurs_contrat,
)


def vers_contrat(m: ContratModele) -> Contrat:
    commun: dict[str, Any] = {
        "id": m.id,
        "etablissement_id": m.etablissement_id,
        "numero": m.numero,
        "type": TypeContrat(m.type),
        "montant_initial_ttc": m.montant_initial_ttc,
        "statut": Statut(m.statut),
        "createur_id": m.cree_par_id,
        "centre_id": m.centre_id,
    }
    if m.type == TypeContrat.MARCHE:
        nature = NatureMarche(m.nature) if m.nature else None
        return Marche(**commun, nature=nature, numero_lot=m.numero_lot)
    return Contrat(**commun)


def mouvements_contrats(
    session: Session, contrats: list[ContratModele]
) -> dict[UUID, MouvementsContrat]:
    """Avenants validés, engagements, commandes, réceptions validées, factures, liquidations,
    ordonnancements et paiements."""
    a = AvenantModele
    variations = {
        contrat_id: (positifs, negatifs)
        for contrat_id, positifs, negatifs in session.execute(
            select(
                a.contrat_id,
                func.sum(case((a.variation > 0, a.variation), else_=0)),
                func.sum(case((a.variation < 0, -a.variation), else_=0)),
            )
            .where(a.contrat_id.in_([c.id for c in contrats]), a.statut == Statut.VALIDE)
            .group_by(a.contrat_id)
        ).all()
    }
    engage = engage_par_contrat(session, [c.id for c in contrats])
    commande, receptionne = commande_et_receptionne_par_contrat(session, [c.id for c in contrats])
    facture, liquide, net = factures_par_contrat(session, [c.id for c in contrats])
    transmis, paye = transmis_et_paye_par_contrat(session, [c.id for c in contrats])
    resultat = {}
    for c in contrats:
        positifs, negatifs = variations.get(c.id, (ZERO, ZERO))
        resultat[c.id] = MouvementsContrat(
            montant_initial=c.montant_initial_ttc,
            avenants_positifs=Decimal(positifs),
            avenants_negatifs=Decimal(negatifs),
            engage=engage.get(c.id, ZERO),
            commande=commande.get(c.id, ZERO),
            receptionne=receptionne.get(c.id, ZERO),
            facture=facture.get(c.id, ZERO),
            liquide=liquide.get(c.id, ZERO),
            net_a_payer=net.get(c.id, ZERO),
            transmis=transmis.get(c.id, ZERO),
            paye=paye.get(c.id, ZERO),
        )
    return resultat


class DepotContratsSql:
    def __init__(self, session: Session) -> None:
        self.session = session

    def contrat(self, contrat_id: UUID) -> Contrat | None:
        m = self.session.get(ContratModele, contrat_id)
        return vers_contrat(m) if m else None

    def montants_imputations(self, contrat_id: UUID) -> list[Decimal]:
        return list(
            self.session.scalars(
                select(ImputationContratModele.montant).where(
                    ImputationContratModele.contrat_id == contrat_id
                )
            )
        )

    def changer_statut_contrat(self, contrat_id: UUID, statut: Statut) -> None:
        self.session.get_one(ContratModele, contrat_id).statut = statut
        self.session.flush()

    def avenant(self, avenant_id: UUID) -> Avenant | None:
        m = self.session.get(AvenantModele, avenant_id)
        if m is None:
            return None
        return Avenant(m.id, m.contrat_id, m.numero, m.variation, Statut(m.statut), m.cree_par_id)

    def ajouter_avenant(self, avenant: Avenant, maintenant: datetime, **champs: Any) -> None:
        contrat = self.session.get_one(ContratModele, avenant.contrat_id)
        self.session.add(
            AvenantModele(
                id=avenant.id,
                contrat_id=avenant.contrat_id,
                etablissement_id=contrat.etablissement_id,
                numero=avenant.numero,
                variation=avenant.variation,
                statut=avenant.statut,
                cree_par_id=avenant.createur_id,
                cree_par_code=champs.pop("cree_par_code"),
                cree_le=maintenant,
                **champs,
            )
        )
        self.session.flush()

    def montant_actualise(self, contrat_id: UUID) -> Decimal:
        contrat = self.session.get_one(ContratModele, contrat_id)
        mouvements = mouvements_contrats(self.session, [contrat])[contrat_id]
        return calculer_indicateurs_contrat(mouvements).montant_actualise

    def engage(self, contrat_id: UUID) -> Decimal:
        return engage_par_contrat(self.session, [contrat_id])[contrat_id]

    def changer_statut_avenant(
        self,
        avenant_id: UUID,
        statut: Statut,
        montant_avant: Decimal | None,
        plafond: Decimal | None,
    ) -> None:
        m = self.session.get_one(AvenantModele, avenant_id)
        m.statut = statut
        if montant_avant is not None:
            m.montant_avant, m.nouveau_plafond = montant_avant, plafond
        self.session.flush()

    def pieces_obligatoires_presentes(self, type_objet: str, id_objet: UUID) -> bool:
        return pieces_obligatoires_presentes(self.session, type_objet, id_objet)
