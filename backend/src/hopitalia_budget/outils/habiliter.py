"""Attribue un profil budgétaire à un agent Hopitalia.

Sert à créer le premier administrateur ; ensuite, les habilitations se gèrent dans le module.

    python -m hopitalia_budget.outils.habiliter --utilisateur-id 42 --code-agent AG042 --profil ADM
    python -m hopitalia_budget.outils.habiliter ... --profil AF --etablissement CHU-TEST
"""

import argparse

from sqlalchemy import select

from hopitalia_budget.adaptateurs.sortie.base import creer_fabrique_sessions
from hopitalia_budget.adaptateurs.sortie.modeles import EtablissementModele, HabilitationModele
from hopitalia_budget.config import parametres
from hopitalia_budget.domaine.habilitations import Profil


def main() -> None:
    lecteur = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    lecteur.add_argument("--utilisateur-id", type=int, required=True, help="userId Hopitalia")
    lecteur.add_argument("--code-agent", required=True)
    lecteur.add_argument("--profil", choices=[p.value for p in Profil], required=True)
    lecteur.add_argument("--etablissement", help="code ; absent : tous les établissements")
    arguments = lecteur.parse_args()

    with creer_fabrique_sessions(parametres().database_url)() as session:
        etablissement_id = None
        if arguments.etablissement:
            etablissement_id = session.scalar(
                select(EtablissementModele.id).where(
                    EtablissementModele.code == arguments.etablissement
                )
            )
            if etablissement_id is None:
                lecteur.error(f"établissement inconnu : {arguments.etablissement}")
        session.add(
            HabilitationModele(
                utilisateur_id=arguments.utilisateur_id,
                code_agent=arguments.code_agent,
                profil=arguments.profil,
                etablissement_id=etablissement_id,
            )
        )
        session.commit()
    print(f"Profil {arguments.profil} attribué à l'agent {arguments.code_agent}.")


if __name__ == "__main__":
    main()
