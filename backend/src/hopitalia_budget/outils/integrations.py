"""Tâche planifiée des échanges avec Hopitalia (lot 7) : fournisseurs, services et pharmacie,
puis reprise automatique des échanges en échec (INT-07). Lancée une fois par jour par le
service `integrations` de docker-compose :
    python -m hopitalia_budget.outils.integrations
"""

from sqlalchemy import select

from hopitalia_budget.adaptateurs.sortie import integrations_hopitalia as echanges
from hopitalia_budget.adaptateurs.sortie.base import creer_fabrique_sessions
from hopitalia_budget.adaptateurs.sortie.hopitalia import ClientHopitalia
from hopitalia_budget.adaptateurs.sortie.modeles import JournalIntegrationModele as J
from hopitalia_budget.adaptateurs.sortie.systeme import HorlogeSysteme
from hopitalia_budget.config import Parametres
from hopitalia_budget.domaine.erreurs import ErreurMetier


def executer() -> list[str]:
    config = Parametres()
    client = ClientHopitalia(config.hopitalia_api_url, config.hopitalia_delai_secondes)
    horloge = HorlogeSysteme()
    compte_rendu: list[str] = []
    with creer_fabrique_sessions(config.database_url)() as session:
        jour = horloge.maintenant().date()
        faits: set[int] = set()
        for type_echange in echanges.TypeEchange:
            parametres = echanges.parametres_du_jour(
                type_echange, jour, config.integration_fenetre_jours
            )
            try:
                ligne = echanges.executer(
                    session, client, config, horloge, type_echange, parametres, None
                )
            except ErreurMetier as exc:
                compte_rendu.append(f"{type_echange} : non lancé ({exc.code})")
                continue
            faits.add(ligne.id)
            session.commit()
        for ligne in echanges.a_reprendre(session):
            if ligne.id not in faits:
                echanges.reprendre(session, client, config, horloge, ligne, None)
                session.commit()
        for ligne in session.scalars(select(J).where(J.id.in_(faits))):
            compte_rendu.append(f"{ligne.identifiant_unique} : {ligne.statut} {ligne.erreur or ''}")
    return compte_rendu


if __name__ == "__main__":
    print("\n".join(executer()))
