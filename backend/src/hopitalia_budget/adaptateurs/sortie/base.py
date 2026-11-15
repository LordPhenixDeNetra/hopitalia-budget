from collections.abc import Iterator

from sqlalchemy import Engine, Numeric, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

# Convention monétaire (T-044) : montants en Numeric(18, 2), lus en Decimal, jamais en float.
MONTANT = Numeric(18, 2, asdecimal=True)


class Base(DeclarativeBase):
    pass


def creer_fabrique_sessions(database_url: str) -> sessionmaker[Session]:
    moteur: Engine = create_engine(database_url, pool_pre_ping=True)
    return sessionmaker(moteur, expire_on_commit=False)


def ouvrir_session(fabrique: sessionmaker[Session]) -> Iterator[Session]:
    """Une session par requête ; les routes valident explicitement (session.commit())."""
    # Import différé : alertes_sql dépend des modèles, qui dépendent de ce module.
    from hopitalia_budget.adaptateurs.sortie.alertes_sql import persister_apres_echec

    with fabrique() as session:
        try:
            yield session
        except Exception:
            session.rollback()
            persister_apres_echec(session)
            raise
