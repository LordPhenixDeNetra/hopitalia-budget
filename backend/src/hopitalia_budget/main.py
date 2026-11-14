from hopitalia_budget.adaptateurs.entree.api.application import creer_application
from hopitalia_budget.config import parametres
from hopitalia_budget.journalisation import configurer_journalisation

configurer_journalisation(parametres().niveau_journal)
app = creer_application(parametres())
