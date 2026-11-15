"""Workflow transverse (P1.B, T-110 à T-120) : circuits, visas, délégations, statuts, pièces."""

import hashlib
import uuid
from decimal import Decimal
from typing import Any, get_args

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from hopitalia_budget.adaptateurs.entree.api.routes.workflow import VALIDABLES, Ressource
from hopitalia_budget.adaptateurs.entree.api.schemas import TypeObjet
from hopitalia_budget.config import Parametres
from hopitalia_budget.domaine.erreurs import ErreurMetier
from hopitalia_budget.domaine.habilitations import Profil
from hopitalia_budget.domaine.workflow import (
    CIRCUIT_PAR_DEFAUT,
    JUSTIFIABLES_SANS_CIRCUIT,
    TRANSITIONS_REFERENCE,
    Circuit,
    CircuitParametre,
    Etape,
    choisir_circuit,
    etapes_ouvertes,
    verifier_etapes,
)
from tests import test_lot1
from tests.conftest import entetes, habiliter
from tests.doubles import HorlogeFixe
from tests.test_lot1 import ADMIN, AUDITEUR, LEC_B, ORD_A, RB_A, VAL_A, VAL_ORD_A, creer, poster

socle = test_lot1.socle  # fixture partagée avec le lot 1

DELEGATAIRE_A, RB_VAL_A = 9, 10
REVISIONS = "/api/v1/revisions-budgetaires"


def _revision(
    client: TestClient, s: dict[str, Any], montant: str = "1.00", auteur: int = RB_A
) -> dict[str, Any]:
    return creer(
        client,
        auteur,
        REVISIONS,
        {
            "budgetId": s["budget"]["id"],
            "type": "VIREMENT",
            "ligneSourceId": s["med"]["id"],
            "ligneCibleId": s["cmd"]["id"],
            "montant": montant,
            "motif": "Besoins en consommables",
        },
    )


def _decider(
    client: TestClient,
    utilisateur: int,
    revision: dict[str, Any],
    decision: str = "VALIDE",
    motif: str | None = None,
) -> Any:
    return client.post(
        f"{REVISIONS}/{revision['id']}/validations",
        json={"decision": decision, "motif": motif},
        headers=entetes(utilisateur),
    )


def _circuit(
    client: TestClient, s: dict[str, Any], etapes: list[tuple[str, str, bool]], **autres: Any
) -> Any:
    return poster(
        client,
        ADMIN,
        "/api/v1/circuits-validation",
        {
            "etablissementId": s["a"],
            "typeObjet": "RevisionBudgetaire",
            "libelle": "Circuit de test",
            "etapes": [
                {"ordre": i, "libelle": libelle, "profil": profil, "obligatoire": obligatoire}
                for i, (libelle, profil, obligatoire) in enumerate(etapes, start=1)
            ],
        }
        | autres,
    )


def _etat(client: TestClient, utilisateur: int, revision: dict[str, Any]) -> dict[str, Any]:
    etat: dict[str, Any] = client.get(
        f"{REVISIONS}/{revision['id']}/validations", headers=entetes(utilisateur)
    ).json()
    return etat


# --- Sans base : interfaces, circuits ------------------------------------------------------------


def test_types_validables_alignes_sur_le_domaine() -> None:
    assert set(get_args(TypeObjet)) == set(TRANSITIONS_REFERENCE) | JUSTIFIABLES_SANS_CIRCUIT
    assert set(get_args(Ressource)) == set(VALIDABLES)


def test_choix_du_circuit_par_service_et_seuil() -> None:
    centre = uuid.uuid4()

    def parametre(
        libelle: str, centre_id: uuid.UUID | None, minimum: str, maximum: str | None
    ) -> CircuitParametre:
        etapes = (Etape(1, libelle, Profil.ORD),)
        return CircuitParametre(
            Circuit(etapes), centre_id, Decimal(minimum), Decimal(maximum) if maximum else None
        )

    parametres = [
        parametre("Petit", None, "0", "1000000"),
        parametre("Gros", None, "1000000", None),
        parametre("Pharmacie", centre, "0", None),
    ]

    def libelle(montant: str, centre_id: uuid.UUID | None) -> str:
        return choisir_circuit(parametres, Decimal(montant), centre_id).etapes[0].libelle

    assert libelle("500", None) == "Petit"
    assert libelle("1000000", None) == "Gros"
    assert libelle("500", centre) == "Pharmacie"
    assert choisir_circuit([], Decimal("1"), None) is CIRCUIT_PAR_DEFAUT


def test_etapes_ouvertes_et_etapes_facultatives() -> None:
    circuit = Circuit(
        (
            Etape(1, "Avis", Profil.ORD, obligatoire=False),
            Etape(2, "Contrôle", Profil.VAL),
            Etape(3, "Ordonnateur", Profil.ORD),
        )
    )
    assert [e.ordre for e in etapes_ouvertes(circuit, set())] == [1, 2]
    assert [e.ordre for e in etapes_ouvertes(circuit, {2})] == [3]
    assert etapes_ouvertes(circuit, {3}) == []


def test_point_16_l_ordonnateur_clot_tout_circuit() -> None:
    for etapes in (
        [Etape(1, "DAF", Profil.VAL)],
        [Etape(1, "Ordonnateur", Profil.ORD), Etape(2, "DAF", Profil.VAL)],
        [Etape(1, "Responsable", Profil.RB), Etape(2, "Ordonnateur", Profil.ORD)],
        [Etape(2, "Ordonnateur", Profil.ORD)],
    ):
        try:
            verifier_etapes("RevisionBudgetaire", etapes)
        except ErreurMetier as exc:
            assert exc.code == "CIRCUIT_INVALIDE"
        else:
            raise AssertionError(etapes)


# --- T-112 : circuits paramétrés ----------------------------------------------------------------


def test_circuit_a_deux_etapes_s_execute_dans_l_ordre(
    client: TestClient, socle: dict[str, Any]
) -> None:
    """Critère de T-112."""
    cree = _circuit(
        client,
        socle,
        [("Contrôle DAF", "VAL", True), ("Visa ordonnateur", "ORD", True)],
        seuilMin="1000000.00",
    )
    assert cree.status_code == 201, cree.json()
    gros = _revision(client, socle, "2000000.00")
    petit = _revision(client, socle, "1.00")
    assert [e["libelle"] for e in _etat(client, VAL_A, gros)["etapes"]] == [
        "Contrôle DAF",
        "Visa ordonnateur",
    ]
    assert _etat(client, VAL_A, petit)["etapes"][0]["libelle"] == "Visa DAF"  # circuit par défaut

    hors_ordre = _decider(client, ORD_A, gros)
    assert (hors_ordre.status_code, hors_ordre.json()["code"]) == (403, "ETAPE_NON_AUTORISEE")
    premier = _decider(client, VAL_A, gros).json()
    assert (premier["statut"], premier["etapesOuvertes"]) == ("EN_VALIDATION", [2])
    second = _decider(client, ORD_A, gros).json()
    assert second["statut"] == "VALIDEE"
    assert [(v["ordre"], v["etape"]) for v in second["visas"]] == [(1, "VAL"), (2, "ORD")]


def test_etape_facultative_sautee(client: TestClient, socle: dict[str, Any]) -> None:
    _circuit(
        client,
        socle,
        [("Avis", "ORD", False), ("Contrôle", "VAL", True), ("Ordonnateur", "ORD", True)],
    )
    revision = _revision(client, socle)
    assert _etat(client, VAL_A, revision)["etapesOuvertes"] == [1, 2]
    assert _decider(client, VAL_A, revision).json()["etapesOuvertes"] == [3]
    assert _decider(client, ORD_A, revision).json()["statut"] == "VALIDEE"


def test_circuit_invalide_refuse(client: TestClient, socle: dict[str, Any]) -> None:
    sans_ordonnateur = _circuit(client, socle, [("DAF", "VAL", True)])
    assert (sans_ordonnateur.status_code, sans_ordonnateur.json()["code"]) == (
        422,
        "CIRCUIT_INVALIDE",
    )
    seuils = _circuit(
        client, socle, [("Ordonnateur", "ORD", True)], seuilMin="10.00", seuilMax="5.00"
    )
    assert (seuils.status_code, seuils.json()["code"]) == (422, "REFERENCE_INVALIDE")
    refuse = poster(
        client,
        RB_A,
        "/api/v1/circuits-validation",
        {
            "etablissementId": socle["a"],
            "typeObjet": "RevisionBudgetaire",
            "libelle": "x",
            "etapes": [{"ordre": 1, "libelle": "O", "profil": "ORD"}],
        },
    )
    assert refuse.status_code == 403


def test_circuit_fige_a_la_soumission(client: TestClient, socle: dict[str, Any]) -> None:
    revision = _revision(client, socle)
    _circuit(client, socle, [("Seul ordonnateur", "ORD", True)])
    assert [e["libelle"] for e in _etat(client, VAL_A, revision)["etapes"]] == [
        "Visa DAF",
        "Ordonnateur",
    ]


# --- T-113, T-116 : décisions, retour pour correction, immuabilité ------------------------------


def test_retour_pour_correction_puis_validation(client: TestClient, socle: dict[str, Any]) -> None:
    """Critères de T-113 (validation, rejet, retour) et de T-116 (409 hors correction)."""
    revision = _revision(client, socle, "1000.00")
    url = f"{REVISIONS}/{revision['id']}"

    def corriger(montant: str, version: int) -> Any:
        return client.patch(
            url,
            json={"montant": montant, "motif": "Montant corrigé"},
            headers=entetes(RB_A, **{"If-Match": f'"{version}"'}),
        )

    en_circuit = corriger("900.00", revision["version"])
    assert (en_circuit.status_code, en_circuit.json()["code"]) == (409, "OPERATION_NON_MODIFIABLE")
    sans_motif = _decider(client, VAL_A, revision, "A_CORRIGER")
    assert (sans_motif.status_code, sans_motif.json()["code"]) == (422, "MOTIF_OBLIGATOIRE")
    assert (
        _decider(client, VAL_A, revision, "A_CORRIGER", "Montant à revoir").json()["statut"]
        == "A_CORRIGER"
    )

    version = client.get(url, headers=entetes(RB_A)).json()["version"]
    perimee = corriger("900.00", version - 1)
    assert perimee.status_code == 412
    corrigee = corriger("900.00", version)
    assert corrigee.json()["montant"] == "900.00"
    autre = client.post(f"{url}/soumissions", headers=entetes(VAL_A))
    assert autre.status_code == 403
    resoumise = client.post(f"{url}/soumissions", headers=entetes(RB_A))
    assert (resoumise.status_code, resoumise.json()["statut"]) == (201, "SOUMISE")

    # Nouveau cycle : le même valideur peut viser de nouveau.
    assert _decider(client, VAL_A, revision).json()["statut"] == "EN_VALIDATION"
    assert _decider(client, ORD_A, revision).json()["statut"] == "VALIDEE"
    validee = corriger("1.00", corrigee.json()["version"])
    assert (validee.status_code, validee.json()["code"]) == (409, "OPERATION_NON_MODIFIABLE")
    decisions = [v["decision"] for v in _etat(client, VAL_A, revision)["visas"]]
    assert decisions == ["A_CORRIGER", "VALIDE", "VALIDE"]
    journal = client.get(
        f"/api/v1/journal-audit?idObjet={revision['id']}", headers=entetes(AUDITEUR)
    ).json()
    assert [e["action"] for e in journal["donnees"]] == [
        "CREATION",
        "RETOUR",
        "MODIFICATION",
        "SOUMISSION",
        "VALIDATION",
        "VALIDATION",
    ]


def test_rejet_definitif(client: TestClient, socle: dict[str, Any]) -> None:
    revision = _revision(client, socle)
    assert _decider(client, VAL_A, revision, "REJETE", "Hors budget").json()["statut"] == "REJETEE"
    apres = _decider(client, ORD_A, revision)
    assert (apres.status_code, apres.json()["code"]) == (409, "OPERATION_DEJA_TRAITEE")


# --- T-114 : séparation des tâches (RG-13) ------------------------------------------------------


def test_rg13_separation_des_taches_selon_le_circuit(
    client: TestClient, session: Session, socle: dict[str, Any]
) -> None:
    from hopitalia_budget.adaptateurs.sortie.modeles import EtablissementModele

    a = session.get_one(EtablissementModele, uuid.UUID(socle["a"]))
    habiliter(session, RB_VAL_A, Profil.RB, a)
    habiliter(session, RB_VAL_A, Profil.VAL, a)
    session.commit()
    propre = _revision(client, socle, auteur=RB_VAL_A)
    createur = _decider(client, RB_VAL_A, propre)
    assert (createur.status_code, createur.json()["code"]) == (403, "SEPARATION_DES_TACHES")
    assert _etat(client, RB_VAL_A, propre)["peutDecider"] is False

    revision = _revision(client, socle)
    _decider(client, VAL_ORD_A, revision)
    meme = _decider(client, VAL_ORD_A, revision)
    assert (meme.status_code, meme.json()["code"]) == (403, "SEPARATION_DES_TACHES")

    _circuit(
        client, socle, [("DAF", "VAL", True), ("Ordonnateur", "ORD", True)], separationTaches=False
    )
    souple = _revision(client, socle)
    _decider(client, VAL_ORD_A, souple)
    assert _decider(client, VAL_ORD_A, souple).json()["statut"] == "VALIDEE"


# --- T-115 : délégations ------------------------------------------------------------------------


def test_delegation_active_puis_expiree(
    client: TestClient, session: Session, horloge: HorlogeFixe, socle: dict[str, Any]
) -> None:
    """Critère de T-115 : une délégation expirée n'autorise plus rien."""
    from hopitalia_budget.adaptateurs.sortie.modeles import EtablissementModele

    habiliter(
        session,
        DELEGATAIRE_A,
        Profil.LEC,
        session.get_one(EtablissementModele, uuid.UUID(socle["a"])),
    )
    session.commit()
    corps = {
        "delegataireCode": "AG009",
        "dateDebut": "2026-11-14",
        "dateFin": "2026-11-20",
        "motif": "Congés",
    }
    soi = poster(client, ORD_A, "/api/v1/delegations", corps | {"delegataireCode": "AG004"})
    assert (soi.status_code, soi.json()["code"]) == (422, "DELEGATION_INVALIDE")
    inconnu = poster(client, ORD_A, "/api/v1/delegations", corps | {"delegataireCode": "AG999"})
    assert inconnu.json()["code"] == "AGENT_INTROUVABLE"
    delegation = creer(client, ORD_A, "/api/v1/delegations", corps)
    recues = client.get("/api/v1/delegations", headers=entetes(DELEGATAIRE_A)).json()
    assert [d["id"] for d in recues["donnees"]] == [delegation["id"]]

    revision = _revision(client, socle)
    _decider(client, VAL_A, revision)
    assert _etat(client, DELEGATAIRE_A, revision)["peutDecider"] is True
    validee = _decider(client, DELEGATAIRE_A, revision).json()
    assert validee["statut"] == "VALIDEE"
    assert validee["visas"][-1]["delegantCode"] == "AG001"  # code du jeton du délégant

    horloge.avancer(days=7)
    expiree = _revision(client, socle)
    _decider(client, VAL_A, expiree)
    refus = _decider(client, DELEGATAIRE_A, expiree)
    assert (refus.status_code, refus.json()["code"]) == (403, "ETAPE_NON_AUTORISEE")


def test_revocation_d_une_delegation(
    client: TestClient, session: Session, socle: dict[str, Any]
) -> None:
    from hopitalia_budget.adaptateurs.sortie.modeles import EtablissementModele

    habiliter(
        session,
        DELEGATAIRE_A,
        Profil.LEC,
        session.get_one(EtablissementModele, uuid.UUID(socle["a"])),
    )
    session.commit()
    delegation = creer(
        client,
        ORD_A,
        "/api/v1/delegations",
        {
            "delegataireCode": "AG009",
            "dateDebut": "2026-11-14",
            "dateFin": "2026-11-20",
            "motif": "Mission",
        },
    )
    url = f"/api/v1/delegations/{delegation['id']}"
    prolongee = client.patch(
        url, json={"dateFin": "2026-12-31"}, headers=entetes(ORD_A, **{"If-Match": '"1"'})
    )
    assert prolongee.json()["code"] == "DATES_INCOHERENTES"
    autre = client.patch(
        url, json={"dateFin": "2026-11-13"}, headers=entetes(DELEGATAIRE_A, **{"If-Match": '"1"'})
    )
    assert autre.status_code == 404
    revoquee = client.patch(
        url, json={"dateFin": "2026-11-13"}, headers=entetes(ORD_A, **{"If-Match": '"1"'})
    )
    assert revoquee.json()["dateFin"] == "2026-11-13"
    revision = _revision(client, socle)
    _decider(client, VAL_A, revision)
    assert _decider(client, DELEGATAIRE_A, revision).status_code == 403


# --- T-111 : statuts personnalisés et transitions -----------------------------------------------


def test_transition_non_parametree_refusee(client: TestClient, socle: dict[str, Any]) -> None:
    """Critère de T-111."""
    base = {"etablissementId": socle["a"], "typeObjet": "RevisionBudgetaire"}
    statut = creer(
        client,
        ADMIN,
        "/api/v1/statuts-personnalises",
        base
        | {"code": "VISEE_DAF", "libelle": "Visée par la DAF", "statutReference": "EN_VALIDATION"},
    )
    assert statut["statutReference"] == "EN_VALIDATION"
    incoherente = poster(
        client,
        ADMIN,
        "/api/v1/transitions-statuts",
        base | {"depuis": "SOUMISE", "action": "VISER", "vers": "VALIDEE"},
    )
    assert (incoherente.status_code, incoherente.json()["code"]) == (422, "TRANSITION_INCOHERENTE")
    for depuis, action, vers in (
        ("SOUMISE", "VISER", "VISEE_DAF"),
        ("VISEE_DAF", "VALIDER", "VALIDEE"),
        ("SOUMISE", "REJETER", "REJETEE"),
    ):
        creer(
            client,
            ADMIN,
            "/api/v1/transitions-statuts",
            base | {"depuis": depuis, "action": action, "vers": vers},
        )

    revision = _revision(client, socle)
    visee = _decider(client, VAL_A, revision).json()
    assert visee["statut"] == "VISEE_DAF"
    lue = client.get(f"{REVISIONS}/{revision['id']}", headers=entetes(RB_A)).json()
    assert lue["statut"] == "EN_VALIDATION"  # statut de référence, lu par les calculs
    assert _decider(client, ORD_A, revision).json()["statut"] == "VALIDEE"

    autre = _revision(client, socle)
    retour = _decider(client, VAL_A, autre, "A_CORRIGER", "À revoir")
    assert (retour.status_code, retour.json()["code"]) == (409, "TRANSITION_NON_AUTORISEE")


# --- T-119 : pièces justificatives --------------------------------------------------------------


def test_pieces_empreinte_et_pieces_obligatoires(
    client: TestClient, parametres: Parametres, socle: dict[str, Any]
) -> None:
    """Critère de T-119 : un fichier altéré est détecté par son empreinte."""
    type_piece = creer(
        client,
        ADMIN,
        "/api/v1/types-pieces",
        {"code": "JUSTIF", "libelle": "Justificatif", "typesObjets": ["RevisionBudgetaire"]},
    )
    revision = _revision(client, socle)
    manquante = _decider(client, VAL_A, revision)
    assert (manquante.status_code, manquante.json()["code"]) == (422, "PIECES_MANQUANTES")

    url = f"{REVISIONS}/{revision['id']}/pieces"
    contenu = b"%PDF-1.4 note de service"

    def deposer(utilisateur: int, nom: str = "note.pdf", mime: str = "application/pdf") -> Any:
        return client.post(
            url,
            files={"fichier": (nom, contenu, mime)},
            data={"typePieceId": type_piece["id"]},
            headers=entetes(utilisateur),
        )

    assert deposer(AUDITEUR).status_code == 403
    refuse = deposer(RB_A, "script.html", "text/html")
    assert (refuse.status_code, refuse.json()["code"]) == (415, "TYPE_FICHIER_REFUSE")
    piece = deposer(RB_A).json()
    assert piece["empreinteSha256"] == hashlib.sha256(contenu).hexdigest()
    assert [p["id"] for p in client.get(url, headers=entetes(VAL_A)).json()] == [piece["id"]]
    assert client.get(url, headers=entetes(LEC_B)).status_code == 404

    telechargement = client.get(f"/api/v1/pieces/{piece['id']}/contenu", headers=entetes(VAL_A))
    assert telechargement.content == contenu
    assert telechargement.headers["x-content-type-options"] == "nosniff"
    assert _decider(client, VAL_A, revision).json()["statut"] == "EN_VALIDATION"

    empreinte = piece["empreinteSha256"]
    (parametres.dossier_pieces / empreinte[:2] / empreinte).write_bytes(b"contenu remplace")
    alteree = client.get(f"/api/v1/pieces/{piece['id']}/contenu", headers=entetes(VAL_A))
    assert (alteree.status_code, alteree.json()["code"]) == (409, "PIECE_ALTEREE")
