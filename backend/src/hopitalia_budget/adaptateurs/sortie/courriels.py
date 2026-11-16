"""Courriels d'alerte (T-225) : file d'envoi, dans la langue du destinataire (I18N-08).

Une alerte est écrite dans la transaction de l'opération ; l'envoi se fait ensuite, par le service
`courriels` : une panne de messagerie ne bloque aucune opération et un courriel en échec est repris
jusqu'à cinq tentatives. Seules les règles qui le demandent (`notifier_par_email`) envoient, aux
agents des profils destinataires qui ont donné leur adresse (l'API Hopitalia n'en fournit pas).
"""

import contextlib
import logging
import smtplib
from collections import Counter, defaultdict
from collections.abc import Callable
from datetime import datetime
from email.message import EmailMessage
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from hopitalia_budget.adaptateurs.sortie.modeles import (
    AlerteModele,
    CourrielModele,
    EtablissementModele,
    HabilitationModele,
    PreferenceUtilisateurModele,
    RegleAlerteModele,
)
from hopitalia_budget.config import Parametres

journal = logging.getLogger(__name__)
TENTATIVES = 5
A_ENVOYER, ENVOYE, ECHEC = "A_ENVOYER", "ENVOYE", "ECHEC"

# Textes des alertes, identiques à ceux de l'interface (frontend/src/i18n/locales/*/alertes.json) :
# un test vérifie qu'ils ne divergent pas.
TEXTES = {
    "fr": {
        "types": {
            "CREDIT_INSUFFISANT": "Crédit insuffisant",
            "DEPASSEMENT_MARCHE": "Dépassement du marché",
            "SEUIL_MARCHE": "Seuil de consommation du marché",
            "AVENANT_NECESSAIRE": "Avenant nécessaire",
            "FACTURE_DOUBLON": "Facture en doublon",
            "FACTURE_SUP_RECEPTION": "Facturé au-delà du réceptionné ou du dû",
            "SERVICE_FAIT_MANQUANT": "Service fait manquant",
            "PAIEMENT_SUP_LIQUIDE": "Paiement au-delà du liquidé",
            "FACTURE_ECHUE": "Facture échue",
            "ECART_RAPPROCHEMENT": "Écart de rapprochement",
            "ENGAGEMENT_ANCIEN": "Engagement ancien",
            "ECHEANCE_CONTRAT": "Échéance de contrat",
            "MODIFICATION_APRES_VALIDATION": "Modification après validation",
            "CONTROLE_BLOQUANT": "Contrôle bloquant",
        },
        "messages": {
            "CREDIT_INSUFFISANT": "Engagement refusé : dépassement de {depassement} "
            "XOF sur le crédit disponible.",
            "DEPASSEMENT_MARCHE": "Engagement refusé : dépassement de {depassement} "
            "XOF sur le reste à engager du marché.",
            "AVENANT_NECESSAIRE": "Le besoin dépasse le plafond du marché de "
            "{depassement} XOF : un avenant ou une dérogation "
            "est nécessaire.",
            "SEUIL_MARCHE": "Marché {numero} consommé à {taux} % (repère de {seuil} %).",
            "FACTURE_DOUBLON": "Facture {numero} refusée : doublon de la facture {reference}.",
            "FACTURE_SUP_RECEPTION": "Liquidation au-delà du réceptionné, de la "
            "facture ou du reste dû ({depassement} XOF).",
            "SERVICE_FAIT_MANQUANT": "Liquidation refusée : aucune réception validée "
            "ne prouve le service fait.",
            "PAIEMENT_SUP_LIQUIDE": "Paiement refusé sur la liquidation {numero} : "
            "part de {part} XOF pour un reste dû de "
            "{resteDu} XOF.",
            "FACTURE_ECHUE": "Facture {numero}, reçue le {recueLe}, non soldée dans le délai.",
            "ECART_RAPPROCHEMENT": "Rapprochement de la facture {numero} enregistré "
            "avec un écart : {explication}",
            "ENGAGEMENT_ANCIEN": "Engagement {numero}, validé le {valideLe}, toujours non soldé.",
            "ECHEANCE_CONTRAT": "Contrat {numero} : échéance au {echeance}.",
            "MODIFICATION_APRES_VALIDATION": "Tentative de modification refusée sur "
            "une opération au statut {statut}.",
            "CONTROLE_BLOQUANT": "Opération refusée par le contrôle {code}.",
            "ECART_RAPPROCHEMENT_HOPITALIA_MODIFIE": "Réception {numero} : "
            "l'approvisionnement a été "
            "modifié dans Hopitalia après "
            "sa réception. Vérifier la "
            "réception et la facture.",
            "ECART_RAPPROCHEMENT_HOPITALIA_SUPPRIME": "Réception {numero} annulée : "
            "l'approvisionnement a été "
            "supprimé dans Hopitalia. "
            "Vérifier les liquidations de "
            "la commande.",
        },
    },
    "en": {
        "types": {
            "CREDIT_INSUFFISANT": "Insufficient credit",
            "DEPASSEMENT_MARCHE": "Contract cap exceeded",
            "SEUIL_MARCHE": "Contract consumption threshold",
            "AVENANT_NECESSAIRE": "Amendment needed",
            "FACTURE_DOUBLON": "Duplicate invoice",
            "FACTURE_SUP_RECEPTION": "Invoiced above received or due",
            "SERVICE_FAIT_MANQUANT": "Service delivery missing",
            "PAIEMENT_SUP_LIQUIDE": "Payment above settled",
            "FACTURE_ECHUE": "Overdue invoice",
            "ECART_RAPPROCHEMENT": "Reconciliation gap",
            "ENGAGEMENT_ANCIEN": "Old commitment",
            "ECHEANCE_CONTRAT": "Contract end date",
            "MODIFICATION_APRES_VALIDATION": "Change after approval",
            "CONTROLE_BLOQUANT": "Blocking check",
        },
        "messages": {
            "CREDIT_INSUFFISANT": "Commitment refused: {depassement} XOF above the "
            "available credit.",
            "DEPASSEMENT_MARCHE": "Commitment refused: {depassement} XOF above the "
            "contract amount left to commit.",
            "AVENANT_NECESSAIRE": "The need exceeds the contract cap by "
            "{depassement} XOF: an amendment or a derogation "
            "is needed.",
            "SEUIL_MARCHE": "Contract {numero} consumed at {taux}% ({seuil}% marker).",
            "FACTURE_DOUBLON": "Invoice {numero} refused: duplicate of invoice {reference}.",
            "FACTURE_SUP_RECEPTION": "Settlement above received, invoice or amount "
            "due ({depassement} XOF).",
            "SERVICE_FAIT_MANQUANT": "Settlement refused: no approved receipt proves "
            "the service delivery.",
            "PAIEMENT_SUP_LIQUIDE": "Payment refused on settlement {numero}: share "
            "of {part} XOF for {resteDu} XOF due.",
            "FACTURE_ECHUE": "Invoice {numero}, received on {recueLe}, not paid in time.",
            "ECART_RAPPROCHEMENT": "Reconciliation of invoice {numero} recorded with "
            "a gap: {explication}",
            "ENGAGEMENT_ANCIEN": "Commitment {numero}, approved on {valideLe}, still "
            "not completed.",
            "ECHEANCE_CONTRAT": "Contract {numero}: ends on {echeance}.",
            "MODIFICATION_APRES_VALIDATION": "Change refused on an operation with status {statut}.",
            "CONTROLE_BLOQUANT": "Operation refused by check {code}.",
            "ECART_RAPPROCHEMENT_HOPITALIA_MODIFIE": "Receipt {numero}: the delivery "
            "was changed in Hopitalia after "
            "receipt. Check the receipt and "
            "the invoice.",
            "ECART_RAPPROCHEMENT_HOPITALIA_SUPPRIME": "Receipt {numero} cancelled: "
            "the delivery was deleted in "
            "Hopitalia. Check the order's "
            "settlements.",
        },
    },
}

CADRE = {
    "fr": {
        "sujet": "[Hopitalia Budget] {type}",
        "corps": (
            "{message}\n\nÉtablissement : {etablissement}\nDate : {date}\n\n"
            "Consultez l'écran Alertes du module de suivi budgétaire{lien}.\n\n"
            "Courriel envoyé automatiquement ; votre adresse se modifie dans l'écran Alertes."
        ),
    },
    "en": {
        "sujet": "[Hopitalia Budget] {type}",
        "corps": (
            "{message}\n\nEstablishment: {etablissement}\nDate: {date}\n\n"
            "See the Alerts screen of the budget tracking module{lien}.\n\n"
            "Automatic email; your address can be changed on the Alerts screen."
        ),
    },
}


def contenu(
    type_alerte: str, details: dict[str, Any], langue: str, etablissement: str, date: str, url: str
) -> tuple[str, str]:
    """Sujet et corps d'un courriel d'alerte, dans la langue du destinataire (français sinon)."""
    langue = langue if langue in TEXTES else "fr"
    textes, cadre = TEXTES[langue], CADRE[langue]
    messages = textes["messages"]
    modele = messages.get(f"{type_alerte}_{details.get('context')}") or messages.get(
        type_alerte, ""
    )
    valeurs: defaultdict[str, str] = defaultdict(str, {k: str(v) for k, v in details.items()})
    lien = (" : " if langue == "fr" else ": ") + f"{url.rstrip('/')}/alertes" if url else ""
    sujet = cadre["sujet"].format(type=textes["types"].get(type_alerte, type_alerte))
    corps = cadre["corps"].format(
        message=modele.format_map(valeurs), etablissement=etablissement, date=date, lien=lien
    )
    return sujet, corps


def preparer(session: Session, maintenant: datetime) -> int:
    """Met en file les courriels des alertes nouvelles ; renvoie leur nombre."""
    crees = 0
    nouvelles = list(
        session.scalars(
            select(AlerteModele)
            .where(AlerteModele.courriels_prepares.is_(False))
            .order_by(AlerteModele.cree_le)
            .limit(500)
        )
    )
    for alerte in nouvelles:
        alerte.courriels_prepares = True
        regle = session.get(RegleAlerteModele, (alerte.etablissement_id, alerte.type))
        if regle is None or not regle.actif or not regle.notifier_par_email:
            continue
        destinataires = session.execute(
            select(
                PreferenceUtilisateurModele.utilisateur_id,
                PreferenceUtilisateurModele.courriel,
                PreferenceUtilisateurModele.langue,
            )
            .join(
                HabilitationModele,
                HabilitationModele.utilisateur_id == PreferenceUtilisateurModele.utilisateur_id,
            )
            .where(
                PreferenceUtilisateurModele.courriel.is_not(None),
                HabilitationModele.profil.in_(alerte.profils),
                or_(
                    HabilitationModele.etablissement_id.is_(None),
                    HabilitationModele.etablissement_id == alerte.etablissement_id,
                ),
            )
            .distinct()
        ).all()
        for utilisateur_id, adresse, langue in destinataires:
            session.add(
                CourrielModele(
                    alerte_id=alerte.id,
                    utilisateur_id=utilisateur_id,
                    adresse=adresse,
                    langue=langue or "fr",
                    statut=A_ENVOYER,
                    cree_le=maintenant,
                )
            )
            crees += 1
    session.flush()
    return crees


def envoyer(
    session: Session,
    config: Parametres,
    maintenant: datetime,
    connexion: Callable[..., Any] = smtplib.SMTP,
) -> Counter[str]:
    """Envoie la file ; sans serveur configuré, les courriels attendent."""
    compte: Counter[str] = Counter()
    if not config.smtp_hote:
        return compte
    en_file = list(
        session.scalars(
            select(CourrielModele)
            .where(
                CourrielModele.statut.in_([A_ENVOYER, ECHEC]),
                CourrielModele.tentatives < TENTATIVES,
            )
            .order_by(CourrielModele.cree_le)
            .limit(200)
        )
    )
    if not en_file:
        return compte
    try:
        serveur = connexion(config.smtp_hote, config.smtp_port, timeout=10)
        if config.smtp_starttls:
            serveur.starttls()
        if config.smtp_utilisateur:
            serveur.login(config.smtp_utilisateur, config.smtp_mot_de_passe.get_secret_value())
    except (OSError, smtplib.SMTPException) as exc:
        journal.warning("Serveur de messagerie injoignable : %s", type(exc).__name__)
        for courriel in en_file:
            _echec(courriel, type(exc).__name__)
        compte["echecs"] = len(en_file)
        session.flush()
        return compte
    try:
        for courriel in en_file:
            alerte = session.get_one(AlerteModele, courriel.alerte_id)
            etablissement = session.get_one(EtablissementModele, alerte.etablissement_id)
            sujet, corps = contenu(
                alerte.type,
                alerte.details or {},
                courriel.langue,
                f"{etablissement.code} — {etablissement.nom}",
                alerte.cree_le.date().isoformat(),
                config.url_application,
            )
            message = EmailMessage()
            message["From"] = config.smtp_expediteur
            message["To"] = courriel.adresse
            message["Subject"] = sujet
            message.set_content(corps)
            # Après le corps : set_content() efface les en-têtes Content-* déjà posés.
            message["Content-Language"] = courriel.langue
            try:
                serveur.send_message(message)
            except smtplib.SMTPException as exc:
                _echec(courriel, type(exc).__name__)
                compte["echecs"] += 1
            else:
                courriel.statut = ENVOYE
                courriel.tentatives += 1
                courriel.envoye_le = maintenant
                courriel.erreur = None
                compte["envoyes"] += 1
    finally:
        with contextlib.suppress(OSError, smtplib.SMTPException):
            serveur.quit()
    session.flush()
    return compte


def _echec(courriel: CourrielModele, erreur: str) -> None:
    courriel.statut = ECHEC
    courriel.tentatives += 1
    courriel.erreur = erreur[:300]
