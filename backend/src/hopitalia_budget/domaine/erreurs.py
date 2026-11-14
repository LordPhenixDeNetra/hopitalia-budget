class ErreurMetier(Exception):
    """Erreur prévue par les règles de gestion, identifiée par un code stable.

    L'API associe le code à un statut HTTP et le traduit ; le contexte complète le message.
    """

    def __init__(self, code: str, /, **contexte: object) -> None:
        super().__init__(code)
        self.code = code
        self.contexte = contexte
