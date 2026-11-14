"""T-121 : gestion des habilitations dans le module (attribuer, retirer, tracer)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from hopitalia_budget.application import habilitations
from hopitalia_budget.domaine.attributions import AgentHopitalia
from hopitalia_budget.domaine.erreurs import ErreurMetier
from hopitalia_budget.domaine.habilitations import Profil
from hopitalia_budget.domaine.utilisateur import Habilitation, Utilisateur
from tests.conftest import creer_etablissement, entetes, habiliter
from tests.doubles import DepotEtablissementsMemoire, JournaliseurAuditMemoire

ADMIN_GLOBAL, ADMIN_A, AUDITEUR, LECTEUR = 1, 2, 3, 4
URL = "/api/v1/habilitations"


@pytest.fixture
def donnees(session: Session) -> dict[str, str]:
    a = creer_etablissement(session, "CHU-A")
    b = creer_etablissement(session, "CHU-B")
    habiliter(session, ADMIN_GLOBAL, Profil.ADM)
    habiliter(session, ADMIN_A, Profil.ADM, a)
    habiliter(session, AUDITEUR, Profil.AUD)
    habiliter(session, LECTEUR, Profil.LEC, a)
    session.commit()
    return {"a": str(a.id), "b": str(b.id)}


def _attribuer(
    client: TestClient, par: int, cle: str, **corps: str | None
) -> tuple[int, dict[str, object]]:
    reponse = client.post(URL, json=corps, headers=entetes(par, **{"Idempotency-Key": cle}))
    return reponse.status_code, reponse.json()


def test_administrateur_attribue_un_profil_sans_ligne_de_commande(
    client: TestClient, donnees: dict[str, str]
) -> None:
    # L'agent AG010 (id 10) n'a encore aucun profil : il est refusé.
    assert client.get("/api/v1/moi", headers=entetes(10)).json()["code"] == "AUCUN_PROFIL"
    statut, cree = _attribuer(
        client, ADMIN_GLOBAL, "k1", codeAgent="AG010", profil="AF", etablissementId=donnees["a"]
    )
    assert statut == 201
    assert cree["utilisateurId"] == 10
    assert cree["nomAgent"] == "Ibrahima Fall"
    # Effet immédiat : l'agent est maintenant accepté, avec son profil.
    moi = client.get("/api/v1/moi", headers=entetes(10)).json()
    assert moi["habilitations"] == [{"profil": "AF", "etablissementId": donnees["a"]}]


def test_attribution_et_retrait_traces_dans_le_journal(
    client: TestClient, donnees: dict[str, str]
) -> None:
    _, cree = _attribuer(client, ADMIN_GLOBAL, "k2", codeAgent="AG010", profil="RB")
    retrait = client.delete(f"{URL}/{cree['id']}", headers=entetes(ADMIN_GLOBAL))
    assert retrait.status_code == 204
    journal = client.get(
        f"/api/v1/journal-audit?idObjet={cree['id']}", headers=entetes(AUDITEUR)
    ).json()["donnees"]
    assert [(e["action"], e["codeAgent"]) for e in journal] == [
        ("ATTRIBUTION", "AG001"),
        ("RETRAIT", "AG001"),
    ]
    assert journal[0]["nouvelleValeur"]["profil"] == "RB"
    assert journal[1]["ancienneValeur"]["codeAgent"] == "AG010"
    # Après le retrait, l'agent n'a plus accès.
    assert client.get("/api/v1/moi", headers=entetes(10)).json()["code"] == "AUCUN_PROFIL"


def test_administrateur_local_limite_a_son_etablissement(
    client: TestClient, donnees: dict[str, str]
) -> None:
    ok, _ = _attribuer(
        client, ADMIN_A, "k3", codeAgent="AG010", profil="SD", etablissementId=donnees["a"]
    )
    assert ok == 201
    autre, corps = _attribuer(
        client, ADMIN_A, "k4", codeAgent="AG010", profil="SD", etablissementId=donnees["b"]
    )
    assert (autre, corps["code"]) == (403, "ACCES_REFUSE")
    global_, corps = _attribuer(client, ADMIN_A, "k5", codeAgent="AG010", profil="SD")
    assert (global_, corps["code"]) == (403, "ACCES_REFUSE")


def test_pas_d_auto_attribution(client: TestClient, donnees: dict[str, str]) -> None:
    statut, corps = _attribuer(client, ADMIN_GLOBAL, "k6", codeAgent="AG001", profil="ORD")
    assert (statut, corps["code"]) == (403, "AUTO_HABILITATION")
    propre = client.get(f"{URL}?codeAgent=AG001", headers=entetes(ADMIN_GLOBAL)).json()
    retrait = client.delete(f"{URL}/{propre['donnees'][0]['id']}", headers=entetes(ADMIN_GLOBAL))
    assert (retrait.status_code, retrait.json()["code"]) == (403, "AUTO_HABILITATION")


def test_doublon_agent_inconnu_et_etablissement_inconnu(
    client: TestClient, donnees: dict[str, str]
) -> None:
    _attribuer(client, ADMIN_GLOBAL, "k7", codeAgent="AG010", profil="CPT")
    statut, corps = _attribuer(client, ADMIN_GLOBAL, "k8", codeAgent="AG010", profil="CPT")
    assert (statut, corps["code"]) == (409, "HABILITATION_EXISTANTE")
    statut, corps = _attribuer(client, ADMIN_GLOBAL, "k9", codeAgent="INCONNU", profil="CPT")
    assert (statut, corps["code"]) == (422, "AGENT_INTROUVABLE")
    statut, corps = _attribuer(
        client,
        ADMIN_GLOBAL,
        "k10",
        codeAgent="AG010",
        profil="CPT",
        etablissementId="00000000-0000-0000-0000-000000000000",
    )
    assert (statut, corps["code"]) == (404, "RESSOURCE_INTROUVABLE")


def test_code_agent_mal_forme_refuse(client: TestClient, donnees: dict[str, str]) -> None:
    statut, corps = _attribuer(client, ADMIN_GLOBAL, "k11", codeAgent="../admin", profil="AF")
    assert (statut, corps["code"]) == (422, "VALIDATION")


def test_rejeu_idempotent(client: TestClient, donnees: dict[str, str]) -> None:
    premiere = _attribuer(client, ADMIN_GLOBAL, "k12", codeAgent="AG003", profil="REC")
    rejeu = _attribuer(client, ADMIN_GLOBAL, "k12", codeAgent="AG003", profil="REC")
    assert premiere == rejeu
    assert premiere[0] == 201


def test_liste_cloisonnee(client: TestClient, donnees: dict[str, str]) -> None:
    def codes(utilisateur: int) -> list[tuple[str, str]]:
        page = client.get(URL, headers=entetes(utilisateur)).json()
        return [(h["codeAgent"], h["profil"]) for h in page["donnees"]]

    # Global : tout ; administrateur de CHU-A : seulement les profils de CHU-A.
    assert codes(ADMIN_GLOBAL) == [
        ("AG001", "ADM"),
        ("AG002", "ADM"),
        ("AG003", "AUD"),
        ("AG004", "LEC"),
    ]
    assert codes(ADMIN_A) == [("AG002", "ADM"), ("AG004", "LEC")]
    refus = client.get(URL, headers=entetes(LECTEUR))
    assert (refus.status_code, refus.json()["code"]) == (403, "ACCES_REFUSE")
    hors = client.get(URL, headers=entetes(ADMIN_A)).json()["donnees"]
    global_ = [h for h in client.get(URL, headers=entetes(ADMIN_GLOBAL)).json()["donnees"]]
    autre = next(h for h in global_ if h["etablissementId"] is None and h["codeAgent"] == "AG003")
    assert autre["id"] not in [h["id"] for h in hors]
    introuvable = client.delete(f"{URL}/{autre['id']}", headers=entetes(ADMIN_A))
    assert introuvable.status_code == 404


def test_filtres_de_la_liste(client: TestClient, donnees: dict[str, str]) -> None:
    filtre = client.get(f"{URL}?profil=AUD", headers=entetes(ADMIN_GLOBAL)).json()
    assert [h["codeAgent"] for h in filtre["donnees"]] == ["AG003"]
    par_etab = client.get(
        f"{URL}?etablissementId={donnees['a']}", headers=entetes(ADMIN_GLOBAL)
    ).json()
    assert {h["codeAgent"] for h in par_etab["donnees"]} == {"AG002", "AG004"}


class AnnuaireMemoire:
    def rechercher(self, code_agent: str) -> AgentHopitalia:
        return AgentHopitalia(id=7, code=code_agent, nom="Agent Sept")


def test_domaine_refuse_sans_droit_de_parametrage() -> None:
    """Cas d'utilisation testé sans base ni réseau (ARC-D)."""
    lecteur = Utilisateur(5, "AG005", "Lecteur", "DAF", (Habilitation(Profil.LEC, None),))
    with pytest.raises(ErreurMetier) as erreur:
        habilitations.attribuer(
            # Dépôt jamais atteint : le droit est vérifié avant tout accès.
            None,  # type: ignore[arg-type]
            DepotEtablissementsMemoire(),
            AnnuaireMemoire(),
            JournaliseurAuditMemoire(),
            lecteur,
            "AG007",
            Profil.AF,
            None,
        )
    assert erreur.value.code == "ACCES_REFUSE"
