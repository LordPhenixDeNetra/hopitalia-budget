"""Lot 5 : ordonnancements et paiements (T-185 à T-192)."""

import uuid
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from hopitalia_budget.adaptateurs.sortie.modeles import EtablissementModele
from hopitalia_budget.domaine.erreurs import ErreurMetier
from hopitalia_budget.domaine.factures import StatutFacture
from hopitalia_budget.domaine.habilitations import Profil
from hopitalia_budget.domaine.paiements import (
    ActionOrdonnancement,
    StatutOrdonnancement,
    appliquer,
    statut_facture,
    verifier_separation,
    verifier_solde,
    verifier_ventilation,
)
from tests import test_commandes, test_contrats, test_engagements, test_lot1
from tests.conftest import entetes, habiliter
from tests.test_engagements import _corps, _soumettre
from tests.test_engagements import _viser as _viser_engagement
from tests.test_factures import _facture, _liquider, _viser
from tests.test_lot1 import ADMIN, ORD_A, VAL_A, creer, disponibilite, poster

socle = test_lot1.socle  # fixtures partagées avec les lots précédents
lot2 = test_contrats.lot2
lot2d = test_engagements.lot2d
lot3 = test_commandes.lot3
CPT_A, VAL_CPT_A = 14, 15
AF_A, GMC_A = test_engagements.AF_A, test_contrats.GMC_A
M = Decimal
S = StatutOrdonnancement


# --- Sans base : cycle de l'ordonnancement, ventilation, solde, statut de la facture -----------


def test_cycle_de_l_ordonnancement() -> None:
    """Critère de T-186 : section 8.3, motif obligatoire pour les réponses négatives."""
    assert appliquer(S.PREPARE, ActionOrdonnancement.TRANSMETTRE, None) == S.TRANSMIS
    assert appliquer(S.TRANSMIS, ActionOrdonnancement.REJETER, "Pièce manquante") == S.REJETE
    assert appliquer(S.SUSPENDU, ActionOrdonnancement.REPRENDRE, None) == S.TRANSMIS
    assert (
        appliquer(S.COMPLEMENT_DEMANDE, ActionOrdonnancement.FOURNIR_COMPLEMENT, None) == S.TRANSMIS
    )
    with pytest.raises(ErreurMetier) as motif:
        appliquer(S.TRANSMIS, ActionOrdonnancement.SUSPENDRE, " ")
    assert motif.value.code == "MOTIF_OBLIGATOIRE"
    with pytest.raises(ErreurMetier) as interdite:
        appliquer(S.PRIS_EN_CHARGE, ActionOrdonnancement.REJETER, "Trop tard")
    assert interdite.value.code == "TRANSITION_NON_AUTORISEE"


def test_ventilation_solde_et_statut_de_la_facture() -> None:
    """Critères de T-187 (ventilation), T-189 (RG-07), T-190 (RG-08) et RG-13."""
    verifier_ventilation(M("100"), [M("60"), M("40")])
    for montant, parts in (
        (M("100"), [M("60"), M("30")]),
        (M("0"), []),
        (M("10"), [M("-5"), M("15")]),
    ):
        with pytest.raises(ErreurMetier) as e:
            verifier_ventilation(montant, parts)
        assert e.value.code == "VENTILATION_PAIEMENT"
    verifier_solde("LIQ-1", M("100"), M("100"))
    with pytest.raises(ErreurMetier) as solde:
        verifier_solde("LIQ-1", M("100"), M("100.01"))
    assert solde.value.code == "PAIEMENT_SUP_SOLDE"
    liquidee, en_paiement = StatutFacture.LIQUIDEE, StatutFacture.MISE_EN_PAIEMENT
    assert statut_facture(liquidee, M("100"), M("0"), True) == en_paiement
    assert statut_facture(en_paiement, M("100"), M("0"), False) == liquidee
    assert statut_facture(en_paiement, M("100"), M("40"), True) == StatutFacture.PARTIELLEMENT_PAYEE
    assert statut_facture(en_paiement, M("100"), M("100"), True) == StatutFacture.PAYEE
    assert statut_facture(StatutFacture.EN_CONTROLE, M("100"), M("0"), True) == (
        StatutFacture.EN_CONTROLE
    )
    verifier_separation(1, {2, 3})
    with pytest.raises(ErreurMetier) as separation:
        verifier_separation(2, {2, 3})
    assert separation.value.code == "SEPARATION_PAIEMENT"


# --- Avec base -----------------------------------------------------------------------------------


@pytest.fixture
def lot5(client: TestClient, session: Session, lot3: dict[str, Any]) -> dict[str, Any]:
    a = session.get_one(EtablissementModele, uuid.UUID(lot3["a"]))
    habiliter(session, CPT_A, Profil.CPT, a)
    habiliter(session, VAL_CPT_A, Profil.VAL, a)
    habiliter(session, VAL_CPT_A, Profil.CPT, a)
    session.commit()
    mode = creer(client, ADMIN, "/api/v1/modes-reglement", {"code": "VIR", "libelle": "Virement"})
    compte = creer(
        client,
        ADMIN,
        "/api/v1/comptes-tresorerie",
        {"code": "BQ1", "libelle": "Banque", "typeCompte": "BANQUE"},
    )
    return lot3 | {"mode": mode["id"], "compte": compte["id"]}


def _liquidee(
    client: TestClient, s: dict[str, Any], montant: str, valideurs: tuple[int, int] = (VAL_A, ORD_A)
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Facture entièrement liquidée sur un engagement validé du même montant."""
    e = creer(client, GMC_A, "/api/v1/engagements", _corps(s, "DECISION_AUTORISEE", montant))
    _soumettre(client, e)
    _viser_engagement(client, "engagements", e["id"], (AF_A, VAL_A, ORD_A))
    engagement = client.get(f"/api/v1/engagements/{e['id']}", headers=entetes(VAL_A)).json()
    facture = _facture(client, engagement, montant=montant).json()
    liquidation = _liquider(client, facture, engagement["imputations"][0]["id"], montant).json()
    client.post(f"/api/v1/liquidations/{liquidation['id']}/soumissions", headers=entetes(AF_A))
    _viser(client, "liquidations", liquidation["id"], *valideurs)
    return facture, liquidation


def _ordonnancer(client: TestClient, *liquidations: dict[str, Any]) -> Any:
    return poster(
        client,
        ORD_A,
        "/api/v1/ordonnancements",
        {
            "referencePiece": f"MD-{uuid.uuid4().hex[:6]}",
            "serviceDestinataire": "Agence comptable",
            "liquidationIds": [lq["id"] for lq in liquidations],
        },
    )


def _decider(
    client: TestClient,
    utilisateur: int,
    ordonnancement: dict[str, Any],
    action: str,
    motif: str = "",
) -> Any:
    return client.post(
        f"/api/v1/ordonnancements/{ordonnancement['id']}/decisions",
        json={"action": action} | ({"motif": motif} if motif else {}),
        headers=entetes(utilisateur),
    )


def _pris_en_charge(client: TestClient, *liquidations: dict[str, Any]) -> dict[str, Any]:
    o: dict[str, Any] = _ordonnancer(client, *liquidations).json()
    assert _decider(client, ORD_A, o, "TRANSMETTRE").status_code == 201
    assert _decider(client, CPT_A, o, "PRENDRE_EN_CHARGE").json()["statut"] == "PRIS_EN_CHARGE"
    return o


def _payer(
    client: TestClient, s: dict[str, Any], parts: list[tuple[dict[str, Any], str]], **autres: Any
) -> Any:
    total = sum((M(m) for _, m in parts), M("0"))
    return poster(
        client,
        autres.pop("par", CPT_A),
        "/api/v1/paiements",
        {
            "datePaiement": "2026-05-10",
            "montant": format(total, "f"),
            "modeReglementId": s["mode"],
            "compteTresorerieId": s["compte"],
            "referenceTransaction": "VIR-778",
            "allocations": [{"liquidationId": lq["id"], "montant": m} for lq, m in parts],
        }
        | autres,
    )


def _statut(client: TestClient, facture: dict[str, Any]) -> dict[str, Any]:
    lue: dict[str, Any] = client.get(
        f"/api/v1/factures/{facture['id']}", headers=entetes(VAL_A)
    ).json()
    return lue


def test_ordonnancement_une_liquidation_active(client: TestClient, lot5: dict[str, Any]) -> None:
    """Critères de T-185 et T-186 : une liquidation dans un seul ordonnancement actif ; un rejet
    la libère, l'historique reste ; chaque réponse revient au bon profil."""
    facture, liquidation = _liquidee(client, lot5, "6000000.00")
    o = _ordonnancer(client, liquidation)
    assert o.status_code == 201, o.json()
    o = o.json()
    assert (o["statut"], o["montant"], o["lignes"][0]["factureNumero"]) == (
        "PREPARE",
        "6000000.00",
        facture["numero"],
    )
    double = _ordonnancer(client, liquidation)
    assert (double.status_code, double.json()["code"]) == (409, "LIQUIDATION_NON_ORDONNANCABLE")
    assert _decider(client, CPT_A, o, "TRANSMETTRE").status_code == 403
    assert _decider(client, ORD_A, o, "TRANSMETTRE").json()["dateTransmission"] == "2026-11-14"
    assert _statut(client, facture)["statut"] == "MISE_EN_PAIEMENT"
    assert _decider(client, ORD_A, o, "PRENDRE_EN_CHARGE").status_code == 403
    assert _decider(client, CPT_A, o, "REJETER").json()["code"] == "MOTIF_OBLIGATOIRE"
    rejete = _decider(client, CPT_A, o, "REJETER", "Mandat non signé").json()
    assert (rejete["statut"], rejete["motifStatut"]) == ("REJETE", "Mandat non signé")
    assert _statut(client, facture)["statut"] == "LIQUIDEE"
    # EF-ORD-03 : retransmise dans un nouvel ordonnancement, l'ancien reste consultable.
    assert _ordonnancer(client, liquidation).status_code == 201
    ancien = client.get(f"/api/v1/ordonnancements/{o['id']}", headers=entetes(CPT_A)).json()
    assert ancien["lignes"][0]["liquidationId"] == liquidation["id"]
    # Facture pas encore entièrement liquidée : rien à ordonnancer.
    e = _corps(lot5, "DECISION_AUTORISEE", "3000000.00")
    engagement = creer(client, GMC_A, "/api/v1/engagements", e)
    _soumettre(client, engagement)
    _viser_engagement(client, "engagements", engagement["id"], (AF_A, VAL_A, ORD_A))
    engagement = client.get(
        f"/api/v1/engagements/{engagement['id']}", headers=entetes(VAL_A)
    ).json()
    partielle = _facture(client, engagement, montant="3000000.00").json()
    moitie = _liquider(client, partielle, engagement["imputations"][0]["id"], "1500000.00").json()
    client.post(f"/api/v1/liquidations/{moitie['id']}/soumissions", headers=entetes(AF_A))
    _viser(client, "liquidations", moitie["id"], VAL_A, ORD_A)
    assert _ordonnancer(client, moitie).json()["code"] == "LIQUIDATION_NON_ORDONNANCABLE"


def test_rec08_rec09_paiements_partiels_et_solde(client: TestClient, lot5: dict[str, Any]) -> None:
    """REC-08, REC-09 et critères de T-187, T-189, T-190 : paiement partiel, la facture reste
    ouverte ; second paiement, solde recalculé ; rien au-delà du solde dû (RG-07)."""
    facture, liquidation = _liquidee(client, lot5, "6000000.00")
    non_pris = _payer(client, lot5, [(liquidation, "1000000.00")])
    assert (non_pris.status_code, non_pris.json()["code"]) == (409, "LIQUIDATION_NON_PAYABLE")
    _pris_en_charge(client, liquidation)
    ventilation = _payer(client, lot5, [(liquidation, "1000000.00")], montant="1500000.00")
    assert ventilation.json()["code"] == "VENTILATION_PAIEMENT"
    premier = _payer(client, lot5, [(liquidation, "2000000.00")])
    assert premier.status_code == 201, premier.json()
    assert (premier.json()["numero"], premier.json()["statut"]) == ("PAI-2026-00001", "EXECUTE")
    lue = _statut(client, facture)
    assert (lue["statut"], lue["resteAPayer"]) == ("PARTIELLEMENT_PAYEE", "4000000.00")
    assert disponibilite(client, lot5["med"]["id"])["paye"] == "2000000.00"
    trop = _payer(client, lot5, [(liquidation, "4000000.01")])
    assert (trop.status_code, trop.json()["code"]) == (422, "PAIEMENT_SUP_SOLDE")
    assert _payer(client, lot5, [(liquidation, "4000000.00")]).status_code == 201
    lue = _statut(client, facture)
    assert (lue["statut"], lue["resteAPayer"]) == ("PAYEE", "0.00")
    a_payer = client.get("/api/v1/liquidations?etape=A_PAYER", headers=entetes(CPT_A)).json()
    assert liquidation["id"] not in [lq["id"] for lq in a_payer]
    ecarts = client.get(
        f"/api/v1/factures/{facture['id']}/rapprochement", headers=entetes(AF_A)
    ).json()
    assert (ecarts["paye"], ecarts["ecartFacturePaiement"]) == ("6000000.00", "0.00")


def test_rec10_paiement_groupe_ventile(client: TestClient, lot5: dict[str, Any]) -> None:
    """REC-10 et critère de T-188 : un paiement groupé est ventilé facture par facture."""
    facture_a, liquidation_a = _liquidee(client, lot5, "6000000.00")
    facture_b, liquidation_b = _liquidee(client, lot5, "4000000.00")
    a_ordonnancer = client.get(
        "/api/v1/liquidations?etape=A_ORDONNANCER", headers=entetes(ORD_A)
    ).json()
    assert {liquidation_a["id"], liquidation_b["id"]} <= {lq["id"] for lq in a_ordonnancer}
    _pris_en_charge(client, liquidation_a, liquidation_b)
    groupe = _payer(client, lot5, [(liquidation_a, "6000000.00"), (liquidation_b, "1000000.00")])
    assert groupe.status_code == 201, groupe.json()
    assert [(a["factureNumero"], a["montant"]) for a in groupe.json()["allocations"]] == [
        (facture_a["numero"], "6000000.00"),
        (facture_b["numero"], "1000000.00"),
    ]
    assert _statut(client, facture_a)["statut"] == "PAYEE"
    assert (_statut(client, facture_b)["statut"], _statut(client, facture_b)["resteAPayer"]) == (
        "PARTIELLEMENT_PAYEE",
        "3000000.00",
    )
    du_b = client.get(
        f"/api/v1/paiements?factureId={facture_b['id']}", headers=entetes(CPT_A)
    ).json()
    assert [p["id"] for p in du_b["donnees"]] == [groupe.json()["id"]]


def test_api01_idempotence_du_paiement(client: TestClient, lot5: dict[str, Any]) -> None:
    """API-01, API-02, API-03 et critère de T-191 sur `POST /paiements` (section 9.2)."""
    _, liquidation = _liquidee(client, lot5, "6000000.00")
    _pris_en_charge(client, liquidation)
    corps = {
        "datePaiement": "2026-05-10",
        "montant": "1000000.00",
        "modeReglementId": lot5["mode"],
        "compteTresorerieId": lot5["compte"],
        "allocations": [{"liquidationId": liquidation["id"], "montant": "1000000.00"}],
    }
    cle = entetes(CPT_A, **{"Idempotency-Key": "paiement-778"})
    premier = client.post("/api/v1/paiements", json=corps, headers=cle)
    rejeu = client.post("/api/v1/paiements", json=corps, headers=cle)
    assert (premier.status_code, rejeu.status_code) == (201, 201)
    assert rejeu.json() == premier.json()
    autre = client.post("/api/v1/paiements", json=corps | {"montant": "2"}, headers=cle)
    assert autre.status_code == 422
    sans_cle = client.post("/api/v1/paiements", json=corps, headers=entetes(CPT_A))
    assert sans_cle.status_code == 400
    tous = client.get("/api/v1/paiements", headers=entetes(CPT_A)).json()
    assert tous["pagination"]["total"] == 1


def test_rg18_annulation_du_paiement(client: TestClient, lot5: dict[str, Any]) -> None:
    """RG-18 et critère de T-192 : un paiement s'annule par contre-opération, motivée ; il reste
    visible et les soldes sont recalculés."""
    facture, liquidation = _liquidee(client, lot5, "6000000.00")
    _pris_en_charge(client, liquidation)
    paiement = _payer(client, lot5, [(liquidation, "6000000.00")]).json()
    assert _statut(client, facture)["statut"] == "PAYEE"
    url = f"/api/v1/paiements/{paiement['id']}/annulations"
    assert client.post(url, json={"motif": "Erreur"}, headers=entetes(CPT_A)).status_code == 403
    annule = client.post(url, json={"motif": "Virement rejeté"}, headers=entetes(AF_A))
    assert annule.status_code == 201, annule.json()
    assert (annule.json()["statut"], annule.json()["motifAnnulation"]) == (
        "ANNULE",
        "Virement rejeté",
    )
    lue = _statut(client, facture)
    assert (lue["statut"], lue["resteAPayer"]) == ("MISE_EN_PAIEMENT", "6000000.00")
    assert disponibilite(client, lot5["med"]["id"])["paye"] == "0.00"
    deux = client.post(url, json={"motif": "Encore"}, headers=entetes(AF_A))
    assert deux.json()["code"] == "PAIEMENT_DEJA_ANNULE"
    assert client.get(f"/api/v1/paiements/{paiement['id']}", headers=entetes(CPT_A)).json()[
        "statut"
    ] == ("ANNULE")
    # Le solde libéré se paie de nouveau.
    assert _payer(client, lot5, [(liquidation, "6000000.00")]).status_code == 201


def test_rg13_qui_valide_la_liquidation_ne_la_paie_pas(
    client: TestClient, lot5: dict[str, Any]
) -> None:
    """RG-13 : le valideur de la liquidation, aussi comptable, ne la paie pas."""
    facture, liquidation = _liquidee(client, lot5, "6000000.00", valideurs=(VAL_CPT_A, ORD_A))
    _pris_en_charge(client, liquidation)
    refus = _payer(client, lot5, [(liquidation, "1000000.00")], par=VAL_CPT_A)
    assert (refus.status_code, refus.json()["code"]) == (403, "SEPARATION_PAIEMENT")
    assert _payer(client, lot5, [(liquidation, "1000000.00")]).status_code == 201
    assert _statut(client, facture)["statut"] == "PARTIELLEMENT_PAYEE"
