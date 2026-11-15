"""Alertes planifiées (T-222) : seuils de consommation des marchés, factures échues, engagements
anciens, échéances de contrat. La tâche est rejouable : une alerte déjà créée ne l'est pas deux
fois (même type, objet et clé)."""

from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from hopitalia_budget.adaptateurs.sortie.alertes_sql import mettre_en_attente, regles
from hopitalia_budget.adaptateurs.sortie.budget_sql import parametres_calcul
from hopitalia_budget.adaptateurs.sortie.contrats_sql import mouvements_contrats
from hopitalia_budget.adaptateurs.sortie.modeles import (
    ContratModele,
    EngagementModele,
    EtablissementModele,
    FactureModele,
)
from hopitalia_budget.domaine.alertes import (
    Signal,
    TypeAlerte,
    anterieur_de,
    echeance_proche,
    facture_echue,
    seuil_atteint,
    seuils_marche,
)
from hopitalia_budget.domaine.contrats import Statut
from hopitalia_budget.domaine.engagements import StatutEngagement
from hopitalia_budget.domaine.indicateurs import calculer_indicateurs_contrat
from hopitalia_budget.domaine.tableaux_de_bord import FACTURES_EN_ATTENTE


def detecter(
    session: Session, aujourdhui: date, etablissement_ids: list[UUID] | None = None
) -> int:
    """Met en attente les signaux du jour ; renvoie leur nombre (avant dédoublonnage)."""
    if etablissement_ids is None:
        etablissement_ids = list(session.scalars(select(EtablissementModele.id)))
    signaux: list[Signal] = []
    for etablissement_id in etablissement_ids:
        r = regles(session, etablissement_id)
        contrats = list(
            session.scalars(
                select(ContratModele).where(
                    ContratModele.etablissement_id == etablissement_id,
                    ContratModele.statut == Statut.VALIDE,
                )
            )
        )
        mouvements = mouvements_contrats(session, contrats)
        parametres = parametres_calcul(session, etablissement_id)
        seuil = r[TypeAlerte.SEUIL_MARCHE].seuil_pourcent
        for c in contrats:
            taux = calculer_indicateurs_contrat(mouvements[c.id], parametres).taux_consommation
            atteint = seuil_atteint(taux, seuils_marche(seuil)) if seuil is not None else None
            if atteint is not None:
                signaux.append(
                    Signal(
                        TypeAlerte.SEUIL_MARCHE,
                        "Contrat",
                        c.id,
                        etablissement_id,
                        cle=format(atteint, "f"),
                        details={
                            "numero": c.numero,
                            "taux": format(taux, "f"),
                            "seuil": format(atteint, "f"),
                        },
                    )
                )
            delai = r[TypeAlerte.ECHEANCE_CONTRAT].delai_jours
            if (
                c.date_echeance
                and delai is not None
                and echeance_proche(c.date_echeance, delai, aujourdhui)
            ):
                signaux.append(
                    Signal(
                        TypeAlerte.ECHEANCE_CONTRAT,
                        "Contrat",
                        c.id,
                        etablissement_id,
                        cle=c.date_echeance.isoformat(),
                        details={"numero": c.numero, "echeance": c.date_echeance.isoformat()},
                    )
                )
        delai = r[TypeAlerte.FACTURE_ECHUE].delai_jours
        for f in session.scalars(
            select(FactureModele).where(
                FactureModele.etablissement_id == etablissement_id,
                FactureModele.statut.in_(FACTURES_EN_ATTENTE),
            )
        ):
            if delai is not None and facture_echue(
                f.date_reception, f.date_echeance, delai, aujourdhui
            ):
                signaux.append(
                    Signal(
                        TypeAlerte.FACTURE_ECHUE,
                        "Facture",
                        f.id,
                        etablissement_id,
                        cle="ECHUE",
                        details={"numero": f.numero, "recueLe": f.date_reception.isoformat()},
                    )
                )
        delai = r[TypeAlerte.ENGAGEMENT_ANCIEN].delai_jours
        for e in session.scalars(
            select(EngagementModele).where(
                EngagementModele.etablissement_id == etablissement_id,
                EngagementModele.statut.in_(
                    {StatutEngagement.VALIDE, StatutEngagement.PARTIELLEMENT_EXECUTE}
                ),
                EngagementModele.date_validation.is_not(None),
            )
        ):
            if (
                e.date_validation is not None
                and delai is not None
                and anterieur_de(e.date_validation.date(), delai, aujourdhui)
            ):
                signaux.append(
                    Signal(
                        TypeAlerte.ENGAGEMENT_ANCIEN,
                        "Engagement",
                        e.id,
                        etablissement_id,
                        cle="ANCIEN",
                        details={
                            "numero": e.numero,
                            "valideLe": e.date_validation.date().isoformat(),
                        },
                    )
                )
    for s in signaux:
        mettre_en_attente(session, s)
    return len(signaux)
