"""Chiffrement des données sensibles en base (coordonnées bancaires, ENF-03)."""

from cryptography.fernet import Fernet, InvalidToken

from hopitalia_budget.domaine.erreurs import ErreurMetier


class Chiffreur:
    """Fernet (AES-128 en mode CBC avec HMAC) ; la clé vient de COORDONNEES_CLE, hors dépôt."""

    def __init__(self, cle: str) -> None:
        if not cle:
            raise ErreurMetier("CONFIGURATION_INCOMPLETE", parametre="COORDONNEES_CLE")
        self.fernet = Fernet(cle.encode())

    def chiffrer(self, texte: str) -> str:
        return self.fernet.encrypt(texte.encode()).decode()

    def dechiffrer(self, chiffre: str) -> str:
        try:
            return self.fernet.decrypt(chiffre.encode()).decode()
        except InvalidToken as exc:
            raise ErreurMetier("CONFIGURATION_INCOMPLETE", parametre="COORDONNEES_CLE") from exc


def masquer(fin_numero: str) -> str:
    return f"•••• {fin_numero}"
