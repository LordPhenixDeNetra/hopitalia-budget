"""Courriels d'alerte (T-225) : file d'envoi, langue du destinataire, reprises."""

import json
import re
import smtplib
import uuid
from datetime import UTC, datetime
from email.message import EmailMessage
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from hopitalia_budget.adaptateurs.sortie import courriels
from hopitalia_budget.adaptateurs.sortie.modeles import (
    AlerteModele,
    CourrielModele,
    RegleAlerteModele,
)
from hopitalia_budget.config import Parametres
from tests import test_lot1
from tests.conftest import entetes
from tests.test_lot1 import RB_A, VAL_A

socle = test_lot1.socle  # fixtures partagées avec les lots précédents
LOCALES = Path(__file__).parents[2] / "frontend" / "src" / "i18n" / "locales"
INSTANT = datetime(2026, 11, 16, 8, 0, tzinfo=UTC)


def test_t225_textes_identiques_a_l_interface() -> None:
    """Le courriel dit exactement ce que dit l'écran Alertes, dans chaque langue."""
    for langue in ("fr", "en"):
        ecran = json.loads((LOCALES / langue / "alertes.json").read_text(encoding="utf-8"))
        attendu = {
            partie: {cle: re.sub(r"\{\{(\w+)\}\}", r"{\1}", v) for cle, v in ecran[partie].items()}
            for partie in ("types", "messages")
        }
        assert courriels.TEXTES[langue] == attendu, langue


def test_t225_contenu_dans_la_langue_du_destinataire() -> None:
    details = {"depassement": "1500000.00"}
    sujet, corps = courriels.contenu(
        "CREDIT_INSUFFISANT", details, "en", "CHU-A — CHU A", "2026-11-16", "https://budget.chu"
    )
    assert sujet == "[Hopitalia Budget] Insufficient credit"
    assert corps.startswith("Commitment refused: 1500000.00 XOF above the available credit.")
    assert "https://budget.chu/alertes" in corps
    sujet_fr, corps_fr = courriels.contenu(
        "ECART_RAPPROCHEMENT",
        {"numero": "REC-1", "context": "HOPITALIA_SUPPRIME"},
        "xx",
        "A",
        "d",
        "",
    )
    assert sujet_fr == "[Hopitalia Budget] Écart de rapprochement"
    assert corps_fr.startswith("Réception REC-1 annulée")


class ServeurSimule:
    """Serveur SMTP de test : garde les messages ; peut échouer à l'envoi."""

    def __init__(self, echouer: bool = False) -> None:
        self.messages: list[EmailMessage] = []
        self.echouer = echouer

    def __call__(self, hote: str, port: int, timeout: int) -> "ServeurSimule":
        return self

    def send_message(self, message: EmailMessage) -> None:
        if self.echouer:
            raise smtplib.SMTPRecipientsRefused({})
        self.messages.append(message)

    def quit(self) -> None:
        pass


@pytest.fixture
def alerte(client: TestClient, session: Session, socle: dict[str, Any]) -> AlerteModele:
    """RB_A lit en anglais et a donné son adresse ; VAL_A aussi, mais n'est pas destinataire."""
    url = "/api/v1/moi/preferences"
    client.put(url, json={"langue": "en", "courriel": "rb@chu.sn"}, headers=entetes(RB_A))
    client.put(url, json={"courriel": "val@chu.sn"}, headers=entetes(VAL_A))
    etablissement = uuid.UUID(socle["a"])
    session.add(
        RegleAlerteModele(
            etablissement_id=etablissement, type="CREDIT_INSUFFISANT", notifier_par_email=True
        )
    )
    alerte = AlerteModele(
        etablissement_id=etablissement,
        type="CREDIT_INSUFFISANT",
        gravite="BLOCAGE",
        type_objet="Engagement",
        id_objet=uuid.uuid4(),
        cle=None,
        details={"depassement": "1500000.00"},
        profils=["AF", "RB"],
        cree_le=INSTANT,
    )
    session.add(alerte)
    session.commit()
    return alerte


def test_t225_courriel_envoye_dans_la_langue_du_destinataire(
    session: Session, parametres: Parametres, alerte: AlerteModele
) -> None:
    """Critère de T-225 : courriel reçu en environnement de test, dans la langue du destinataire ;
    seuls les profils destinataires qui ont une adresse le reçoivent, une seule fois."""
    assert courriels.preparer(session, INSTANT) == 1
    assert courriels.preparer(session, INSTANT) == 0  # alerte déjà examinée
    serveur = ServeurSimule()
    config = parametres.model_copy(update={"smtp_hote": "smtp.test"})
    assert courriels.envoyer(session, config, INSTANT, serveur)["envoyes"] == 1
    [message] = serveur.messages
    assert (message["To"], message["Subject"], message["Content-Language"]) == (
        "rb@chu.sn",
        "[Hopitalia Budget] Insufficient credit",
        "en",
    )
    assert "1500000.00 XOF above the available credit" in message.get_content()
    assert courriels.envoyer(session, config, INSTANT, serveur) == {}  # rien à renvoyer


def test_t225_echec_repris_et_sans_serveur_en_attente(
    session: Session, parametres: Parametres, alerte: AlerteModele
) -> None:
    courriels.preparer(session, INSTANT)
    # Sans serveur configuré : le courriel attend, rien n'est perdu.
    assert courriels.envoyer(session, parametres, INSTANT) == {}
    config = parametres.model_copy(update={"smtp_hote": "smtp.test"})
    assert courriels.envoyer(session, config, INSTANT, ServeurSimule(echouer=True))["echecs"] == 1
    courriel = session.scalar(select(CourrielModele))
    assert courriel is not None
    assert (courriel.statut, courriel.tentatives, courriel.erreur) == (
        "ECHEC",
        1,
        "SMTPRecipientsRefused",
    )
    serveur = ServeurSimule()
    assert courriels.envoyer(session, config, INSTANT, serveur)["envoyes"] == 1
    assert (courriel.statut, courriel.tentatives) == ("ENVOYE", 2)


def test_t225_regle_sans_courriel(
    session: Session, alerte: AlerteModele, socle: dict[str, Any]
) -> None:
    regle = session.get_one(RegleAlerteModele, (uuid.UUID(socle["a"]), "CREDIT_INSUFFISANT"))
    regle.notifier_par_email = False
    session.commit()
    assert courriels.preparer(session, INSTANT) == 0
    assert session.get_one(AlerteModele, alerte.id).courriels_prepares is True


def test_t225_adresse_controlee(client: TestClient, socle: dict[str, Any]) -> None:
    url = "/api/v1/moi/preferences"
    assert (
        client.put(url, json={"courriel": "pas-une-adresse"}, headers=entetes(RB_A)).status_code
        == 422
    )
    client.put(url, json={"courriel": "rb@chu.sn"}, headers=entetes(RB_A))
    client.put(url, json={"courriel": None}, headers=entetes(RB_A))
    assert client.get("/api/v1/moi", headers=entetes(RB_A)).json()["courriel"] is None
