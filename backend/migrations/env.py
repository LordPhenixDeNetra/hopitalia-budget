from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine

from hopitalia_budget.adaptateurs.sortie import modeles  # noqa: F401  (enregistre les tables)
from hopitalia_budget.adaptateurs.sortie.base import Base
from hopitalia_budget.config import parametres

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Les tests passent leur base de test par l'option sqlalchemy.url ; sinon DATABASE_URL.
url = config.get_main_option("sqlalchemy.url") or parametres().database_url

if context.is_offline_mode():
    context.configure(url=url, target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    with create_engine(url).connect() as connexion:
        context.configure(connection=connexion, target_metadata=Base.metadata)
        with context.begin_transaction():
            context.run_migrations()
