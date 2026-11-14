"""Codes d'erreur stables, statut HTTP et messages en français et en anglais (I18N-07, T-059)."""

from collections import defaultdict

LANGUES = ("fr", "en")
LANGUE_PAR_DEFAUT = "fr"

# code : (statut, (titre fr, détail fr), (titre en, détail en)) ; {x} : valeur du contexte.
_CATALOGUE: dict[str, tuple[int, tuple[str, str], tuple[str, str]]] = {
    "RESSOURCE_INTROUVABLE": (
        404,
        ("Ressource introuvable", "La ressource demandée n'existe pas ou n'est pas accessible."),
        ("Resource not found", "The requested resource does not exist or is not accessible."),
    ),
    "METHODE_NON_AUTORISEE": (
        405,
        ("Méthode non autorisée", "Cette méthode HTTP n'est pas acceptée sur cette ressource."),
        ("Method not allowed", "This HTTP method is not accepted on this resource."),
    ),
    "AUTHENTIFICATION_REQUISE": (
        401,
        ("Connexion requise", "Un jeton d'accès Hopitalia est requis."),
        ("Authentication required", "A Hopitalia access token is required."),
    ),
    "JETON_INVALIDE": (
        401,
        ("Jeton invalide", "Le jeton d'accès est invalide ou expiré."),
        ("Invalid token", "The access token is invalid or has expired."),
    ),
    "IDENTIFIANTS_INVALIDES": (
        401,
        ("Identifiants invalides", "Identifiant ou mot de passe incorrect."),
        ("Invalid credentials", "Incorrect username or password."),
    ),
    "AUCUN_PROFIL": (
        403,
        ("Aucun profil budgétaire", "Aucun profil budgétaire n'est attribué à cet agent."),
        ("No budget profile", "No budget profile is assigned to this agent."),
    ),
    "ACCES_REFUSE": (
        403,
        ("Accès refusé", "Vous n'avez pas le droit d'effectuer cette opération."),
        ("Access denied", "You are not allowed to perform this operation."),
    ),
    "VALIDATION": (
        422,
        ("Données invalides", "Certains champs sont invalides."),
        ("Invalid data", "Some fields are invalid."),
    ),
    "MONTANT_INVALIDE": (
        422,
        (
            "Montant invalide",
            "« {valeur} » n'est pas un montant valide (chaîne décimale, deux décimales au plus).",
        ),
        (
            "Invalid amount",
            '"{valeur}" is not a valid amount (decimal string, at most two decimals).',
        ),
    ),
    "PARAMETRE_INCONNU": (
        400,
        ("Paramètre inconnu", "Paramètre non autorisé : {parametre}."),
        ("Unknown parameter", "Parameter not allowed: {parametre}."),
    ),
    "TRI_INVALIDE": (
        400,
        ("Tri invalide", "Champ de tri non autorisé : {champ}."),
        ("Invalid sort", "Sort field not allowed: {champ}."),
    ),
    "CURSEUR_INVALIDE": (
        400,
        ("Curseur invalide", "Le curseur de pagination est invalide."),
        ("Invalid cursor", "The pagination cursor is invalid."),
    ),
    "IDEMPOTENCE_CLE_MANQUANTE": (
        400,
        (
            "Clé d'idempotence manquante",
            "L'en-tête Idempotency-Key est obligatoire pour cette opération.",
        ),
        ("Missing idempotency key", "The Idempotency-Key header is required for this operation."),
    ),
    "IDEMPOTENCE_CONFLIT": (
        422,
        ("Clé d'idempotence déjà utilisée", "Cette clé a déjà servi pour une requête différente."),
        ("Idempotency key already used", "This key was already used for a different request."),
    ),
    "IDEMPOTENCE_EN_COURS": (
        409,
        ("Requête en cours", "Une requête avec cette clé est encore en cours de traitement."),
        ("Request in progress", "A request with this key is still being processed."),
    ),
    "PRECONDITION_REQUISE": (
        428,
        (
            "Précondition requise",
            "L'en-tête If-Match est obligatoire pour modifier cette ressource.",
        ),
        ("Precondition required", "The If-Match header is required to modify this resource."),
    ),
    "PRECONDITION_ECHOUEE": (
        412,
        (
            "Ressource modifiée entre-temps",
            "La ressource a été modifiée depuis votre lecture ; rechargez-la.",
        ),
        ("Resource changed", "The resource was modified since you read it; reload it."),
    ),
    "CODE_DEJA_UTILISE": (
        409,
        ("Code déjà utilisé", "Le code « {code} » est déjà utilisé."),
        ("Code already used", 'The code "{code}" is already used.'),
    ),
    "LIMITE_DEBIT": (
        429,
        ("Trop de requêtes", "Limite de requêtes atteinte ; réessayez dans {secondes} secondes."),
        ("Too many requests", "Request limit reached; retry in {secondes} seconds."),
    ),
    "AGENT_INTROUVABLE": (
        422,
        ("Agent introuvable", "Aucun agent Hopitalia ne porte le code « {code} »."),
        ("Agent not found", 'No Hopitalia agent has the code "{code}".'),
    ),
    "HABILITATION_EXISTANTE": (
        409,
        ("Profil déjà attribué", "Cet agent a déjà ce profil pour cet établissement."),
        ("Profile already assigned", "This agent already has this profile for this facility."),
    ),
    "AUTO_HABILITATION": (
        403,
        (
            "Modification de ses propres droits",
            "Un administrateur ne peut pas modifier ses propres habilitations.",
        ),
        ("Changing your own rights", "Administrators cannot change their own profiles."),
    ),
    "REFERENCE_INVALIDE": (
        422,
        ("Référence invalide", "Le champ {champ} désigne un élément inexistant ou incompatible."),
        ("Invalid reference", "The field {champ} refers to a missing or incompatible item."),
    ),
    "HIERARCHIE_INVALIDE": (
        422,
        ("Hiérarchie invalide", "Un élément ne peut pas être rattaché à l'un de ses descendants."),
        ("Invalid hierarchy", "An item cannot be attached to one of its descendants."),
    ),
    "DATES_INCOHERENTES": (
        422,
        ("Dates incohérentes", "La date de fin doit suivre la date de début."),
        ("Inconsistent dates", "The end date must come after the start date."),
    ),
    "EXERCICE_NON_OUVERT": (
        409,
        ("Exercice non ouvert", "Cette opération exige un exercice ouvert."),
        ("Fiscal year not open", "This operation requires an open fiscal year."),
    ),
    "BUDGET_PRIMITIF_EXISTANT": (
        409,
        (
            "Budget primitif existant",
            "Cet établissement a déjà un budget primitif pour cet exercice.",
        ),
        ("Initial budget exists", "This facility already has an initial budget for this year."),
    ),
    "CREDIT_INSUFFISANT": (
        422,
        (
            "Crédit insuffisant",
            "Disponible {disponible}, demandé {montant} sur la ligne {ligne}.",
        ),
        ("Insufficient credit", "Available {disponible}, requested {montant} on line {ligne}."),
    ),
    "OPERATION_DEJA_TRAITEE": (
        409,
        ("Opération déjà traitée", "Cette opération n'attend aucune validation."),
        ("Already processed", "This operation is not awaiting any approval."),
    ),
    "OPERATION_NON_MODIFIABLE": (
        409,
        (
            "Opération non modifiable",
            "Seule une opération retournée pour correction se modifie (statut actuel : {statut}).",
        ),
        (
            "Operation cannot be changed",
            "Only an operation returned for correction can be changed (current status: {statut}).",
        ),
    ),
    "TRANSITION_NON_AUTORISEE": (
        409,
        (
            "Transition non autorisée",
            "L'action {action} n'est pas paramétrée depuis le statut {statut}.",
        ),
        ("Transition not allowed", "Action {action} is not configured from status {statut}."),
    ),
    "TRANSITION_INCOHERENTE": (
        422,
        (
            "Transition incohérente",
            "Cette transition ne correspond à aucune transition des statuts de référence.",
        ),
        ("Inconsistent transition", "This transition matches no reference status transition."),
    ),
    "CIRCUIT_INVALIDE": (
        422,
        (
            "Circuit invalide",
            "Étapes numérotées à partir de 1, profils autorisés à valider, dernière étape "
            "obligatoire confiée à l'ordonnateur.",
        ),
        (
            "Invalid approval flow",
            "Steps numbered from 1, profiles allowed to approve, last step mandatory and "
            "given to the authorising officer.",
        ),
    ),
    "PIECES_MANQUANTES": (
        422,
        ("Pièces manquantes", "Une pièce obligatoire manque : la validation est impossible."),
        ("Missing documents", "A mandatory document is missing: approval is not possible."),
    ),
    "PIECE_ALTEREE": (
        409,
        (
            "Pièce altérée",
            "Le fichier ne correspond plus à son empreinte : il a été modifié ou perdu.",
        ),
        ("Altered document", "The file no longer matches its fingerprint: changed or lost."),
    ),
    "PIECE_TROP_VOLUMINEUSE": (
        413,
        ("Fichier trop volumineux", "Un fichier ne doit pas dépasser {max} Mo."),
        ("File too large", "A file must not exceed {max} MB."),
    ),
    "TYPE_FICHIER_REFUSE": (
        415,
        ("Type de fichier refusé", "Formats acceptés : PDF, PNG, JPEG, Word et Excel."),
        ("File type refused", "Accepted formats: PDF, PNG, JPEG, Word and Excel."),
    ),
    "DELEGATION_INVALIDE": (
        422,
        ("Délégation invalide", "On ne se délègue pas ses propres droits."),
        ("Invalid delegation", "You cannot delegate to yourself."),
    ),
    "ETAPE_NON_AUTORISEE": (
        403,
        (
            "Étape non autorisée",
            "Cette étape de validation revient au profil {profil}.",
        ),
        ("Step not allowed", "This approval step belongs to the {profil} profile."),
    ),
    "SEPARATION_DES_TACHES": (
        403,
        (
            "Séparation des tâches",
            "Vous avez déjà saisi ou visé cette opération : une autre personne doit la valider.",
        ),
        (
            "Segregation of duties",
            "You already entered or approved this operation: someone else must approve it.",
        ),
    ),
    "MOTIF_OBLIGATOIRE": (
        422,
        ("Motif obligatoire", "Un rejet doit être motivé."),
        ("Reason required", "A rejection must state a reason."),
    ),
    "NOTIFICATION_INCOHERENTE": (
        422,
        (
            "Notification incohérente",
            "La somme des montants par ligne doit égaler le montant notifié.",
        ),
        ("Inconsistent notification", "The amounts per line must add up to the notified amount."),
    ),
    "CONFIGURATION_INCOMPLETE": (
        503,
        (
            "Configuration incomplète",
            "Le module n'est pas configuré pour cette opération ({parametre}).",
        ),
        ("Incomplete configuration", "The module is not configured for this ({parametre})."),
    ),
    "HOPITALIA_INDISPONIBLE": (
        502,
        ("Hopitalia indisponible", "Le service de connexion Hopitalia ne répond pas."),
        ("Hopitalia unavailable", "The Hopitalia login service is not responding."),
    ),
    "ERREUR_INTERNE": (
        500,
        ("Erreur interne", "Une erreur inattendue s'est produite."),
        ("Internal error", "An unexpected error occurred."),
    ),
}

CODES = frozenset(_CATALOGUE)


def langue_demandee(accept_language: str | None) -> str:
    """Première langue prise en charge dans l'en-tête Accept-Language, sinon le français."""
    for partie in (accept_language or "").split(","):
        langue = partie.split(";")[0].strip().lower()[:2]
        if langue in LANGUES:
            return langue
    return LANGUE_PAR_DEFAUT


def statut(code: str) -> int:
    return _CATALOGUE.get(code, _CATALOGUE["ERREUR_INTERNE"])[0]


def message(code: str, langue: str, contexte: dict[str, object]) -> tuple[str, str]:
    entree = _CATALOGUE.get(code, _CATALOGUE["ERREUR_INTERNE"])
    titre, detail = entree[1] if langue == "fr" else entree[2]
    valeurs: defaultdict[str, str] = defaultdict(str, {k: str(v) for k, v in contexte.items()})
    return titre, detail.format_map(valeurs)
