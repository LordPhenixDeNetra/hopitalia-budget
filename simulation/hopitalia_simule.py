"""Hopitalia simulé, pour la recette blanche (environnement de test seulement, jamais en production).

Suit la note d'intégration (docs/cadrage/integration-hopitalia.md) : connexion des agents avec des
jetons HS512 signés comme ceux d'Hopitalia, annuaire des agents, fournisseurs, services, commandes et
approvisionnements de la pharmacie. Les données sont générées (graine fixe) avec un volume réaliste ;
`POST /simulation/jour` fait avancer le temps : un fournisseur retiré, un approvisionnement modifié,
un autre supprimé, de nouvelles commandes, comme dans Hopitalia d'un jour à l'autre.

Comptes : `agentNNN` / `recette` (identifiant NNN, code agent AGNNN) et `svc-budget` / `recette`.
"""

import os
import random
import secrets
from datetime import UTC, date, datetime, timedelta
from typing import Any

import jwt
from fastapi import FastAPI, Header, HTTPException

CLE = os.environ["HOPITALIA_JWT_CLE"]
# Mot de passe de tous les comptes : `recette` sur un poste, secret sur un serveur.
MOT_DE_PASSE = os.environ.get("SIMULATION_MOT_DE_PASSE", "recette")
# Données datées des quatre dernières semaines : le module relit une fenêtre de 30 jours.
DEBUT = date.today() - timedelta(days=28)

app = FastAPI(title="Hopitalia simulé (recette blanche)")
etat: dict[str, Any] = {"jour": 0, "rafraichissement": {}, "panne": False}


# --- Connexion et annuaire ------------------------------------------------------------------


def _agent(identifiant: str) -> dict[str, Any]:
    if identifiant == "svc-budget":
        return {"id": 999, "code": "SVC-BUDGET", "nom": "Compte technique"}
    if identifiant.startswith("agent") and identifiant[5:].isdigit():
        n = int(identifiant[5:])
        return {"id": n, "code": f"AG{n:03d}", "nom": f"Agent {n:03d}"}
    raise HTTPException(401)


def _jetons(agent: dict[str, Any]) -> dict[str, Any]:
    maintenant = datetime.now(UTC)
    acces = jwt.encode(
        {
            "sub": agent["code"].lower(),
            "scope": ["ROLE_AGENT"],
            "permissions": [],
            "userId": agent["id"],
            "code": agent["code"],
            "prenomNom": agent["nom"],
            "service": "DAF",
            "iat": maintenant,
            "exp": maintenant + timedelta(minutes=15),
        },
        CLE,
        algorithm="HS512",
    )
    rafraichissement = secrets.token_urlsafe(24)
    etat["rafraichissement"][rafraichissement] = agent
    return {
        "access_token": acces,
        "refresh_token": rafraichissement,
        "token_type": "Bearer",
        "expires_in": 900,
        "refresh_expires_at": (maintenant + timedelta(days=1)).isoformat(),
    }


@app.post("/api/auth/login")
def connexion(corps: dict[str, str]) -> dict[str, Any]:
    if corps.get("password") != MOT_DE_PASSE:
        raise HTTPException(401)
    return _jetons(_agent(corps.get("username", "")))


@app.post("/api/auth/refresh")
def rafraichissement(corps: dict[str, str]) -> dict[str, Any]:
    agent = etat["rafraichissement"].pop(corps.get("refresh_token", ""), None)
    if agent is None:
        raise HTTPException(401)
    return _jetons(agent)


@app.post("/api/auth/logout")
def deconnexion(corps: dict[str, str]) -> dict[str, str]:
    etat["rafraichissement"].pop(corps.get("refresh_token", ""), None)
    return {}


@app.post("/simulation/panne")
def panne(active: bool = True) -> dict[str, bool]:
    """Panne des données (pas de la connexion) : un échange échoue, puis se reprend."""
    etat["panne"] = active
    return {"panne": active}


def _verifier(authorization: str | None) -> None:
    if etat["panne"]:
        raise HTTPException(503)
    try:
        jwt.decode((authorization or "")[7:], CLE, algorithms=["HS512"])
    except jwt.PyJWTError as exc:
        raise HTTPException(401) from exc


@app.get("/api/agents/code/{code}")
def agent(
    code: str, authorization: str | None = Header(default=None)
) -> dict[str, Any]:
    _verifier(authorization)
    if not (code.startswith("AG") and code[2:].isdigit()):
        raise HTTPException(404)
    n = int(code[2:])
    return {"id": n, "codeAgent": code, "prenom": "Agent", "nom": f"{n:03d}"}


# --- Données générées ------------------------------------------------------------------------

alea = random.Random(2026)
PRODUITS = [
    (
        f"P{n:04d}",
        f"Produit pharmaceutique {n:04d}",
        alea.choice([500, 1250, 2500, 8000]),
    )
    for n in range(1, 301)
]
FOURNISSEURS = [
    {
        "id": n,
        "codeFourn": f"FRN-{n:03d}",
        "nomFourn": f"Fournisseur {n:03d}",
        "telephone": f"33 800 {n:04d}",
        "adresse": "Dakar",
    }
    for n in range(1, 121)
]
# Le fournisseur du jeu d'essai (docs/cadrage/jeu-essai-marche-fournitures.md), déjà saisi dans le
# module : l'import doit le rattacher, pas le dupliquer.
FOURNISSEURS.append(
    {
        "id": 500,
        "codeFourn": "PHARMA-TEST",
        "nomFourn": "Pharma Test SA",
        "telephone": None,
        "adresse": "Dakar",
    }
)
SERVICES = [
    {"codeService": "PHARMA", "nomService": "Pharmacie", "laboratoire": False},
    {"codeService": "LABO", "nomService": "Laboratoire", "laboratoire": True},
    {
        "codeService": "DAF",
        "nomService": "Direction administrative et financière",
        "administration": True,
    },
    *(
        {"codeService": f"SRV-{n:02d}", "nomService": f"Service clinique {n:02d}"}
        for n in range(1, 18)
    ),
]


def _lignes(n: int) -> list[dict[str, Any]]:
    return [
        {"codeProduit": code, "nomProduit": nom, "quantite": q, "montant": q * prix}
        for code, nom, prix in alea.sample(PRODUITS, n)
        for q in [alea.choice([10, 20, 50, 100])]
    ]


COMMANDES: dict[int, dict[str, Any]] = {}
APPROS: dict[int, dict[str, Any]] = {}
SUPPRESSIONS: list[dict[str, Any]] = []


def _ajouter_commande(numero: int, jour: date) -> None:
    lignes = _lignes(alea.randint(1, 5))
    fournisseur = alea.choice(FOURNISSEURS[:40])
    COMMANDES[numero] = {
        "entete": {
            "id": numero,
            "numBc": f"BCP-{numero:05d}",
            "dateBc": jour.isoformat(),
            "codeFourn": fournisseur["codeFourn"],
            "nomService": "Pharmacie",
            "urgent": alea.random() < 0.1,
            "livraisonTotal": False,
        },
        "lignes": lignes,
    }
    # Sept commandes sur dix sont livrées, en une ou deux fois.
    if alea.random() < 0.7:
        livraisons = 1 if alea.random() < 0.6 else 2
        for rang in range(livraisons):
            id_appro = 10 * numero + rang
            APPROS[id_appro] = {
                "id": id_appro,
                "numBl": f"BL-{id_appro:06d}",
                "numBonCmde": f"BCP-{numero:05d}",
                "date": min(
                    jour + timedelta(days=2 + 3 * rang), date.today()
                ).isoformat(),
                "codeFourn": fournisseur["codeFourn"],
                "lignes": [
                    {
                        "codeProduit": lg["codeProduit"],
                        "quantite": lg["quantite"] // livraisons,
                        "montant": lg["montant"] // livraisons,
                        "numeroLot": f"L{id_appro}",
                    }
                    for lg in lignes
                ],
            }


for n in range(1, 81):
    _ajouter_commande(n, DEBUT + timedelta(days=n % 25))


@app.post("/simulation/jour")
def jour_suivant() -> dict[str, Any]:
    """Un jour passe dans Hopitalia : retrait, modification, suppression, nouvelles commandes."""
    etat["jour"] += 1
    j = etat["jour"]
    if FOURNISSEURS and j == 1:
        FOURNISSEURS.pop(10)  # fournisseur retiré : désactivé dans le module
    livres = sorted(APPROS)
    if livres:
        modifie = APPROS[livres[j % len(livres)]]
        modifie["lignes"][0]["quantite"] += 1  # approvisionnement corrigé après coup
        supprime = livres[(j * 7) % len(livres)]
        if supprime != livres[j % len(livres)]:
            APPROS.pop(supprime)
            SUPPRESSIONS.append(
                {"id": supprime, "dateSuppression": date.today().isoformat()}
            )
    base = max(COMMANDES) + 1
    for n in range(base, base + 5):
        _ajouter_commande(n, date.today())
    return {"jour": j, "commandes": len(COMMANDES), "approvisionnements": len(APPROS)}


@app.delete("/simulation/approvisionnements/{identifiant}")
def supprimer_approvisionnement(identifiant: int) -> dict[str, Any]:
    """Suppression d'un approvisionnement dans Hopitalia, choisie par la répétition."""
    if APPROS.pop(identifiant, None) is None:
        raise HTTPException(404)
    SUPPRESSIONS.append(
        {"id": identifiant, "dateSuppression": date.today().isoformat()}
    )
    return {"supprime": identifiant}


def _dans(jour: str, start: str | None, end: str | None) -> bool:
    return (start is None or jour >= start) and (end is None or jour <= end)


@app.get("/api/pharmacie/fournisseurs")
def fournisseurs(
    authorization: str | None = Header(default=None),
) -> list[dict[str, Any]]:
    _verifier(authorization)
    return FOURNISSEURS


@app.get("/api/services")
def services(authorization: str | None = Header(default=None)) -> list[dict[str, Any]]:
    _verifier(authorization)
    return SERVICES


@app.get("/api/pharmacie/bons-commandes")
def bons_commandes(
    start: str | None = None,
    end: str | None = None,
    authorization: str | None = Header(default=None),
) -> list[dict[str, Any]]:
    _verifier(authorization)
    return [
        c["entete"]
        for c in COMMANDES.values()
        if _dans(c["entete"]["dateBc"], start, end)
    ]


@app.get("/api/pharmacie/bons-commandes/{numero}/details")
def details(
    numero: int, authorization: str | None = Header(default=None)
) -> list[dict[str, Any]]:
    _verifier(authorization)
    if numero not in COMMANDES:
        raise HTTPException(404)
    return COMMANDES[numero]["lignes"]


@app.get("/api/pharmacie/approvisionnements/historique")
def historique(
    start: str | None = None,
    end: str | None = None,
    authorization: str | None = Header(default=None),
) -> list[dict[str, Any]]:
    _verifier(authorization)
    return [
        {"id": a["id"], "date": a["date"]}
        for a in APPROS.values()
        if _dans(a["date"], start, end)
    ]


@app.get("/api/pharmacie/approvisionnements/historique-suppressions")
def suppressions(
    authorization: str | None = Header(default=None),
) -> list[dict[str, Any]]:
    _verifier(authorization)
    return SUPPRESSIONS


@app.get("/api/pharmacie/approvisionnements/{identifiant}")
def approvisionnement(
    identifiant: int, authorization: str | None = Header(default=None)
) -> dict[str, Any]:
    _verifier(authorization)
    if identifiant not in APPROS:
        raise HTTPException(404)
    return APPROS[identifiant]
