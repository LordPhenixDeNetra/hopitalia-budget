"""Socle API sur une vraie base PostgreSQL (T-042 à T-055, scénarios API et REC du cahier)."""

import hashlib
from datetime import timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from hopitalia_budget.adaptateurs.entree.api.application import creer_application
from hopitalia_budget.adaptateurs.entree.api.dependances import obtenir_session
from hopitalia_budget.config import Parametres
from hopitalia_budget.domaine.habilitations import Profil
from tests.conftest import creer_etablissement, entetes, habiliter, jeton
from tests.doubles import HorlogeFixe

ADMIN, AUDITEUR, LECTEUR_A = 1, 2, 3


@pytest.fixture
def donnees(session: Session) -> dict[str, str]:
    a = creer_etablissement(session, "CHU-A")
    b = creer_etablissement(session, "CHU-B")
    creer_etablissement(session, "CHU-C")
    habiliter(session, ADMIN, Profil.ADM)
    habiliter(session, AUDITEUR, Profil.AUD)
    habiliter(session, LECTEUR_A, Profil.LEC, a)
    # Valide un point de sauvegarde : les données survivent aux annulations des requêtes
    # en échec, et la transaction englobante les efface à la fin du test.
    session.commit()
    return {"a": str(a.id), "b": str(b.id)}


# --- T-042, T-044 : base et montants -------------------------------------------------------


def test_numeric_18_2_relu_en_decimal_exact(session: Session) -> None:
    relu = session.scalar(text("SELECT CAST('9999999999999999.99' AS NUMERIC(18, 2))"))
    assert relu == Decimal("9999999999999999.99")
    assert isinstance(relu, Decimal)


# --- T-052 : connexion et jetons Hopitalia ---------------------------------------------------


def test_connexion_relayee_vers_hopitalia(client: TestClient) -> None:
    ok = client.post("/api/v1/auth/connexion", json={"identifiant": "a", "motDePasse": "secret"})
    assert ok.status_code == 200
    assert ok.json() == {
        "jetonAcces": "acces",
        "jetonRafraichissement": "rafraichissement",
        "expireDans": 900,
    }
    refus = client.post("/api/v1/auth/connexion", json={"identifiant": "a", "motDePasse": "x"})
    assert (refus.status_code, refus.json()["code"]) == (401, "IDENTIFIANTS_INVALIDES")
    panne = client.post("/api/v1/auth/connexion", json={"identifiant": "panne", "motDePasse": "x"})
    assert (panne.status_code, panne.json()["code"]) == (502, "HOPITALIA_INDISPONIBLE")
    assert (
        client.post(
            "/api/v1/auth/rafraichissement", json={"jetonRafraichissement": "r"}
        ).status_code
        == 200
    )
    assert (
        client.post("/api/v1/auth/deconnexion", json={"jetonRafraichissement": "r"}).status_code
        == 204
    )


def test_jeton_hopitalia_valide_accepte(client: TestClient, donnees: dict[str, str]) -> None:
    reponse = client.get("/api/v1/moi", headers=entetes(ADMIN))
    assert reponse.status_code == 200
    assert reponse.json()["codeAgent"] == "AG001"
    assert reponse.json()["habilitations"] == [{"profil": "ADM", "etablissementId": None}]


@pytest.mark.parametrize(
    "autorisation",
    [
        None,
        "Basic abc",
        f"Bearer {jeton(ADMIN, expire_dans=timedelta(minutes=-1))}",
        f"Bearer {jeton(ADMIN, cle='une-autre-cle-' + 'x' * 64)}",
        "Bearer pas-un-jeton",
    ],
)
def test_jeton_absent_expire_ou_mal_signe_refuse(
    client: TestClient, donnees: dict[str, str], autorisation: str | None
) -> None:
    reponse = client.get(
        "/api/v1/moi", headers={"Authorization": autorisation} if autorisation else {}
    )
    assert reponse.status_code == 401


def test_agent_sans_profil_budgetaire_refuse(client: TestClient) -> None:
    reponse = client.get("/api/v1/moi", headers=entetes(999))
    assert (reponse.status_code, reponse.json()["code"]) == (403, "AUCUN_PROFIL")


def test_preference_de_langue_conservee(client: TestClient, donnees: dict[str, str]) -> None:
    assert client.get("/api/v1/moi", headers=entetes(ADMIN)).json()["langue"] is None
    client.put("/api/v1/moi/preferences", json={"langue": "en"}, headers=entetes(ADMIN))
    assert client.get("/api/v1/moi", headers=entetes(ADMIN)).json()["langue"] == "en"


# --- T-053, T-054 : habilitations et cloisonnement (REC-13, REC-17, API-10) ------------------


def test_operation_non_autorisee_refusee(client: TestClient, donnees: dict[str, str]) -> None:
    """REC-13 : un agent non habilité ne peut pas agir (403)."""
    reponse = client.post(
        "/api/v1/etablissements",
        json={"code": "CHU-X", "nom": "X"},
        headers=entetes(LECTEUR_A, **{"Idempotency-Key": "k1"}),
    )
    assert (reponse.status_code, reponse.json()["code"]) == (403, "ACCES_REFUSE")


def test_lecteur_ne_voit_que_son_etablissement(client: TestClient, donnees: dict[str, str]) -> None:
    """REC-17 et API-10 : un agent ne voit rien d'un autre établissement ; l'objet d'un
    autre établissement répond 404."""
    liste = client.get("/api/v1/etablissements", headers=entetes(LECTEUR_A)).json()
    assert [e["code"] for e in liste["donnees"]] == ["CHU-A"]
    autre = client.get(f"/api/v1/etablissements/{donnees['b']}", headers=entetes(LECTEUR_A))
    assert (autre.status_code, autre.json()["code"]) == (404, "RESSOURCE_INTROUVABLE")


def test_api09_version_inconnue(client: TestClient, donnees: dict[str, str]) -> None:
    """API-09 : `/api/v2/…` n'existe pas (404), `/api/v1/…` répond normalement."""
    inconnue = client.get("/api/v2/etablissements", headers=entetes(ADMIN))
    assert inconnue.status_code == 404
    assert client.get("/api/v1/etablissements", headers=entetes(ADMIN)).status_code == 200


# --- T-047, T-048 : pagination, tri, filtres sur liste blanche --------------------------------


def test_pagination_par_decalage(client: TestClient, donnees: dict[str, str]) -> None:
    page = client.get("/api/v1/etablissements?taille=2&tri=-code", headers=entetes(ADMIN)).json()
    assert [e["code"] for e in page["donnees"]] == ["CHU-C", "CHU-B"]
    assert page["pagination"] == {
        "page": 1,
        "taille": 2,
        "total": 3,
        "suivant": "/api/v1/etablissements?taille=2&tri=-code&page=2",
    }
    suivante = client.get(page["pagination"]["suivant"], headers=entetes(ADMIN)).json()
    assert [e["code"] for e in suivante["donnees"]] == ["CHU-A"]
    assert suivante["pagination"]["suivant"] is None


def test_taille_maximale_et_filtres(client: TestClient, donnees: dict[str, str]) -> None:
    trop = client.get("/api/v1/etablissements?taille=101", headers=entetes(ADMIN))
    assert trop.status_code == 422
    filtre = client.get("/api/v1/etablissements?code=CHU-B", headers=entetes(ADMIN)).json()
    assert [e["code"] for e in filtre["donnees"]] == ["CHU-B"]


@pytest.mark.parametrize(
    ("requete", "code"),
    [("?ville=Dakar", "PARAMETRE_INCONNU"), ("?tri=-version", "TRI_INVALIDE")],
)
def test_champ_non_documente_refuse(
    client: TestClient, donnees: dict[str, str], requete: str, code: str
) -> None:
    """API-07 : tri ou filtre sur un champ non documenté, 400."""
    reponse = client.get(f"/api/v1/etablissements{requete}", headers=entetes(ADMIN))
    assert (reponse.status_code, reponse.json()["code"]) == (400, code)


# --- T-049 : idempotence (API-01 à API-03) -----------------------------------------------------


def test_rejeu_avec_la_meme_cle_ne_cree_rien(
    client: TestClient, donnees: dict[str, str], session: Session
) -> None:
    """API-01 : rejeu avec la même clé, même réponse, une seule création."""
    corps = {"code": "CHU-D", "nom": "CHU D"}
    en_tetes = entetes(ADMIN, **{"Idempotency-Key": "cle-1"})
    premiere = client.post("/api/v1/etablissements", json=corps, headers=en_tetes)
    rejeu = client.post("/api/v1/etablissements", json=corps, headers=en_tetes)
    assert premiere.status_code == rejeu.status_code == 201
    assert premiere.json() == rejeu.json()
    assert rejeu.headers["Idempotent-Replayed"] == "true"
    nombre = session.scalar(text("SELECT count(*) FROM etablissement WHERE code = 'CHU-D'"))
    assert nombre == 1


def test_meme_cle_corps_different(client: TestClient, donnees: dict[str, str]) -> None:
    """API-02 : même clé, corps différent, 422."""
    en_tetes = entetes(ADMIN, **{"Idempotency-Key": "cle-2"})
    client.post("/api/v1/etablissements", json={"code": "CHU-E", "nom": "E"}, headers=en_tetes)
    autre = client.post(
        "/api/v1/etablissements", json={"code": "CHU-F", "nom": "F"}, headers=en_tetes
    )
    assert (autre.status_code, autre.json()["code"]) == (422, "IDEMPOTENCE_CONFLIT")


def test_post_financier_sans_cle_refuse(client: TestClient, donnees: dict[str, str]) -> None:
    """API-03 : POST financier sans clé, 400."""
    reponse = client.post(
        "/api/v1/etablissements", json={"code": "CHU-G", "nom": "G"}, headers=entetes(ADMIN)
    )
    assert (reponse.status_code, reponse.json()["code"]) == (400, "IDEMPOTENCE_CLE_MANQUANTE")


def test_cle_encore_en_cours(client: TestClient, donnees: dict[str, str], session: Session) -> None:
    corps = b'{"code":"CHU-H","nom":"H"}'
    empreinte = hashlib.sha256(b"POST/api/v1/etablissements" + corps).hexdigest()
    session.execute(
        text(
            "INSERT INTO cle_idempotence (utilisateur_id, cle, empreinte_requete, expire_le) "
            "VALUES (:u, 'cle-3', :e, now() + interval '1 hour')"
        ),
        {"u": ADMIN, "e": empreinte},
    )
    reponse = client.post(
        "/api/v1/etablissements",
        content=corps,
        headers=entetes(ADMIN, **{"Idempotency-Key": "cle-3", "Content-Type": "application/json"}),
    )
    assert (reponse.status_code, reponse.json()["code"]) == (409, "IDEMPOTENCE_EN_COURS")


def test_cle_expiree_reutilisable(
    client: TestClient, donnees: dict[str, str], horloge: HorlogeFixe
) -> None:
    en_tetes = entetes(ADMIN, **{"Idempotency-Key": "cle-4"})
    client.post("/api/v1/etablissements", json={"code": "CHU-I", "nom": "I"}, headers=en_tetes)
    horloge.avancer(hours=25)
    reponse = client.post(
        "/api/v1/etablissements", json={"code": "CHU-J", "nom": "J"}, headers=en_tetes
    )
    assert reponse.status_code == 201


def test_creation_echouee_libere_la_cle(client: TestClient, donnees: dict[str, str]) -> None:
    en_tetes = entetes(ADMIN, **{"Idempotency-Key": "cle-5"})
    doublon = client.post(
        "/api/v1/etablissements", json={"code": "CHU-A", "nom": "A"}, headers=en_tetes
    )
    assert (doublon.status_code, doublon.json()["code"]) == (409, "CODE_DEJA_UTILISE")
    reprise = client.post(
        "/api/v1/etablissements", json={"code": "CHU-K", "nom": "K"}, headers=en_tetes
    )
    assert reprise.status_code == 201


# --- T-050 : concurrence optimiste (API-05) ---------------------------------------------------


def test_modification_exige_if_match_a_jour(client: TestClient, donnees: dict[str, str]) -> None:
    """API-05 : If-Match absent (428) ou périmé (412)."""
    url = f"/api/v1/etablissements/{donnees['a']}"
    lecture = client.get(url, headers=entetes(ADMIN))
    etag = lecture.headers["ETag"]
    sans = client.patch(url, json={"nom": "Nouveau"}, headers=entetes(ADMIN))
    assert (sans.status_code, sans.json()["code"]) == (428, "PRECONDITION_REQUISE")
    ok = client.patch(url, json={"nom": "Nouveau"}, headers=entetes(ADMIN, **{"If-Match": etag}))
    assert ok.status_code == 200
    assert ok.json()["nom"] == "Nouveau"
    assert ok.headers["ETag"] != etag
    perime = client.patch(url, json={"nom": "Autre"}, headers=entetes(ADMIN, **{"If-Match": etag}))
    assert (perime.status_code, perime.json()["code"]) == (412, "PRECONDITION_ECHOUEE")


# --- T-055 : journal d'audit en ajout seul ----------------------------------------------------


def test_creation_et_modification_tracees(
    client: TestClient, donnees: dict[str, str], session: Session
) -> None:
    cree = client.post(
        "/api/v1/etablissements",
        json={"code": "CHU-L", "nom": "L"},
        headers=entetes(ADMIN, **{"Idempotency-Key": "cle-6"}),
    ).json()
    client.patch(
        f"/api/v1/etablissements/{cree['id']}",
        json={"actif": False},
        headers=entetes(ADMIN, **{"If-Match": '"1"'}),
    )
    journal = client.get(
        f"/api/v1/journal-audit?idObjet={cree['id']}", headers=entetes(AUDITEUR)
    ).json()["donnees"]
    assert [(e["action"], e["codeAgent"]) for e in journal] == [
        ("CREATION", "AG001"),
        ("MODIFICATION", "AG001"),
    ]
    assert journal[1]["ancienneValeur"]["actif"] is True
    assert journal[1]["nouvelleValeur"]["actif"] is False
    assert journal[1]["adresseIp"] is not None


@pytest.mark.parametrize(
    "instruction",
    [
        "UPDATE journal_audit SET action = 'FALSIFIE'",
        "DELETE FROM journal_audit",
        "TRUNCATE journal_audit",
    ],
)
def test_journal_non_modifiable_en_base(
    client: TestClient, donnees: dict[str, str], session: Session, instruction: str
) -> None:
    client.post(
        "/api/v1/etablissements",
        json={"code": "CHU-M", "nom": "M"},
        headers=entetes(ADMIN, **{"Idempotency-Key": "cle-7"}),
    )
    with pytest.raises(DBAPIError, match="ajout seul"), session.begin_nested():
        session.execute(text(instruction))


def test_journal_reserve_aux_profils_d_audit(client: TestClient, donnees: dict[str, str]) -> None:
    reponse = client.get("/api/v1/journal-audit", headers=entetes(LECTEUR_A))
    assert (reponse.status_code, reponse.json()["code"]) == (403, "ACCES_REFUSE")


def test_curseur_stable_malgre_nouvelles_lignes(
    client: TestClient, donnees: dict[str, str], horloge: HorlogeFixe
) -> None:
    """API-06 : parcours par curseur pendant que des écritures arrivent, sans perte ni doublon."""
    for numero in range(5):
        horloge.avancer(seconds=1)
        client.post(
            "/api/v1/etablissements",
            json={"code": f"CHU-P{numero}", "nom": "P"},
            headers=entetes(ADMIN, **{"Idempotency-Key": f"p{numero}"}),
        )
    vus: list[int] = []
    page = client.get("/api/v1/journal-audit?taille=2", headers=entetes(AUDITEUR)).json()
    vus += [e["id"] for e in page["donnees"]]
    horloge.avancer(seconds=1)
    client.post(
        "/api/v1/etablissements",
        json={"code": "CHU-NOUVEAU", "nom": "N"},
        headers=entetes(ADMIN, **{"Idempotency-Key": "pn"}),
    )
    while page["pagination"]["suivant"]:
        page = client.get(
            f"/api/v1/journal-audit?taille=2&apres={page['pagination']['suivant']}",
            headers=entetes(AUDITEUR),
        ).json()
        vus += [e["id"] for e in page["donnees"]]
    assert len(vus) == len(set(vus)) == 6
    assert vus == sorted(vus)


def test_curseur_illisible_refuse(client: TestClient, donnees: dict[str, str]) -> None:
    reponse = client.get("/api/v1/journal-audit?apres=%%%", headers=entetes(AUDITEUR))
    assert (reponse.status_code, reponse.json()["code"]) == (400, "CURSEUR_INVALIDE")


# --- T-051 : limitation de débit (API-08) -----------------------------------------------------


def test_limite_de_debit(session: Session, parametres: Parametres, donnees: dict[str, str]) -> None:
    """API-08 : au-delà de la limite de débit, 429 avec Retry-After."""
    application = creer_application(parametres.model_copy(update={"limite_requetes_par_minute": 2}))
    application.dependency_overrides[obtenir_session] = lambda: session
    client = TestClient(application)
    premiere = client.get("/api/v1/moi", headers=entetes(ADMIN))
    assert premiere.headers["RateLimit-Limit"] == "2"
    assert premiere.headers["RateLimit-Remaining"] == "1"
    client.get("/api/v1/moi", headers=entetes(ADMIN))
    bloquee = client.get("/api/v1/moi", headers=entetes(ADMIN))
    assert (bloquee.status_code, bloquee.json()["code"]) == (429, "LIMITE_DEBIT")
    assert int(bloquee.headers["Retry-After"]) > 0
    # Un autre utilisateur a son propre compteur.
    assert client.get("/api/v1/moi", headers=entetes(AUDITEUR)).status_code != 429
