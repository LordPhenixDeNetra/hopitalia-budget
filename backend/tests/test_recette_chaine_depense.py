"""Recette de la chaîne de dépense (T-195, REC-14) : le jeu d'essai de l'annexe 18.2, pièce par
pièce (docs/cadrage/jeu-essai-marche-fournitures.md), et ses contrôles (section 4 du jeu)."""

from typing import Any

from fastapi.testclient import TestClient

from tests import test_commandes, test_contrats, test_engagements, test_lot1, test_paiements
from tests.conftest import entetes
from tests.test_commandes import _commande, _reception, _valider_reception
from tests.test_contrats import GMC_A, _contrat_valide, _synthese
from tests.test_engagements import AF_A, _corps, _soumettre, _valide
from tests.test_factures import _facture, _liquider, _valider_liquidation
from tests.test_lot1 import VAL_A, creer, disponibilite
from tests.test_paiements import CPT_A, _payer, _pris_en_charge, _statut

socle = test_lot1.socle  # fixtures partagées avec les lots précédents
lot2 = test_contrats.lot2
lot2d = test_engagements.lot2d
lot3 = test_commandes.lot3
lot5 = test_paiements.lot5


def _dataset(client: TestClient, s: dict[str, Any]) -> dict[str, Any]:
    """Toutes les pièces du jeu d'essai, saisies et validées par l'API, dans l'ordre du métier."""
    marche = _contrat_valide(client, s, "MARCHE")  # M-2026-001 : 100 M, 70 M MED, 30 M CMD

    def engagement(montant: str, imputations: list[tuple[str, str]]) -> dict[str, Any]:
        return _valide(
            client,
            s,
            "CONTRAT",
            contratId=marche["id"],
            montant=montant,
            imputations=[{"ligneId": s[ligne]["id"], "montant": m} for ligne, m in imputations],
        )

    eng1 = engagement("50000000.00", [("med", "50000000.00")])
    eng2 = engagement("30000000.00", [("med", "15000000.00"), ("cmd", "15000000.00")])
    # Commandes à 100 000 l'unité : BC-001 = 40 M, BC-002 = 25 M.
    bc1 = _commande(client, eng1, quantite="400").json()
    bc2 = _commande(client, eng2, quantite="250").json()

    def reception(commande: dict[str, Any], quantite: str) -> dict[str, Any]:
        r: dict[str, Any] = _reception(client, s, commande, quantite, quantite).json()
        assert _valider_reception(client, r).status_code == 201
        return r

    rec1, rec2, rec3 = reception(bc1, "300"), reception(bc2, "200"), reception(bc1, "50")

    def facture(
        numero: str, engagement: dict[str, Any], commande: dict[str, Any], montant: str
    ) -> dict[str, Any]:
        f = _facture(
            client, engagement, montant=montant, numero=numero, bonCommandeId=commande["id"]
        )
        assert f.status_code == 201, f.json()
        resultat: dict[str, Any] = f.json()
        return resultat

    fac1 = facture("FAC-001", eng1, bc1, "30000000.00")
    fac2 = facture("FAC-002", eng2, bc2, "15000000.00")
    fac3 = facture("FAC-003", eng1, bc1, "5000000.00")

    def liquidation(
        f: dict[str, Any], imputation: dict[str, Any], montant: str, recu: dict[str, Any]
    ) -> dict[str, Any]:
        lq: dict[str, Any] = _liquider(
            client, f, imputation["id"], montant, receptionIds=[recu["id"]]
        ).json()
        _valider_liquidation(client, lq)
        return lq

    med2, cmd2 = eng2["imputations"]
    if med2["ligneId"] != s["med"]["id"]:
        med2, cmd2 = cmd2, med2
    liq1 = liquidation(fac1, eng1["imputations"][0], "30000000.00", rec1)
    liq2 = liquidation(fac2, med2, "10000000.00", rec2)  # RG-17 : une liquidation par imputation
    liq3 = liquidation(fac2, cmd2, "5000000.00", rec2)
    _pris_en_charge(client, liq1)  # ORD-001
    _pris_en_charge(client, liq3)  # ORD-002 ; LIQ-002 n'est pas encore ordonnancée
    assert _payer(client, s, [(liq1, "20000000.00")]).status_code == 201  # PAI-001
    groupe = _payer(client, s, [(liq1, "5000000.00"), (liq3, "5000000.00")])  # PAI-002
    assert groupe.status_code == 201, groupe.json()
    return {
        "marche": marche,
        "eng1": eng1,
        "eng2": eng2,
        "fac1": fac1,
        "fac2": fac2,
        "fac3": fac3,
        "liq1": liq1,
        "liq2": liq2,
        "liq3": liq3,
        "rec3": rec3,
    }


def test_rec14_jeu_d_essai_de_l_annexe_18_2(client: TestClient, lot5: dict[str, Any]) -> None:
    """REC-14 et critère de T-195 : tous les montants et statuts du jeu d'essai sont retrouvés,
    puis les contrôles de sa section 4 se comportent comme attendu."""
    d = _dataset(client, lot5)

    # Fiche de synthèse du marché (annexe 18.2).
    synthese = _synthese(client, d["marche"])
    assert {
        k: synthese[k]
        for k in (
            "montantActualise",
            "engage",
            "commande",
            "receptionne",
            "facture",
            "liquide",
            "transmis",
            "paye",
            "resteAPayerSurLiquide",
            "engageNonFacture",
            "resteAEngager",
            "resteContractuelAPayer",
            "tauxConsommation",
        )
    } == {
        "montantActualise": "100000000.00",
        "engage": "80000000.00",
        "commande": "65000000.00",
        "receptionne": "55000000.00",
        "facture": "50000000.00",
        "liquide": "45000000.00",
        "transmis": "35000000.00",
        "paye": "30000000.00",
        "resteAPayerSurLiquide": "15000000.00",
        "engageNonFacture": "30000000.00",
        "resteAEngager": "20000000.00",
        "resteContractuelAPayer": "70000000.00",
        "tauxConsommation": "80.00",
    }

    # Lignes budgétaires.
    attendus = {
        "med": ("90000000.00", "65000000.00", "25000000.00", "40000000.00", "25000000.00"),
        "cmd": ("40000000.00", "15000000.00", "25000000.00", "5000000.00", "10000000.00"),
    }
    payes = {"med": ("25000000.00", "15000000.00"), "cmd": ("5000000.00", "0.00")}
    taux = {"med": "72.22", "cmd": "37.50"}
    for ligne, valeurs in attendus.items():
        i = disponibilite(client, lot5[ligne]["id"])
        assert (
            i["budgetRevise"],
            i["engage"],
            i["disponibleApresEngagements"],
            i["liquide"],
            i["engageRestantALiquider"],
        ) == valeurs, ligne
        assert (i["paye"], i["resteAPayer"]) == payes[ligne], ligne
        assert i["tauxEngagement"] == taux[ligne], ligne

    # Reste à payer par liquidation.
    a_payer = {
        lq["numero"]: (lq["netAPayer"], lq["paye"], lq["resteAPayer"])
        for lq in client.get("/api/v1/liquidations?etape=A_PAYER", headers=entetes(CPT_A)).json()
    }
    assert a_payer == {d["liq1"]["numero"]: ("30000000.00", "25000000.00", "5000000.00")}
    a_ordonnancer = {
        lq["numero"]: lq["resteAPayer"]
        for lq in client.get(
            "/api/v1/liquidations?etape=A_ORDONNANCER", headers=entetes(CPT_A)
        ).json()
    }
    assert a_ordonnancer == {d["liq2"]["numero"]: "10000000.00"}

    # Statuts attendus.
    for cle in ("eng1", "eng2"):
        lu = client.get(f"/api/v1/engagements/{d[cle]['id']}", headers=entetes(VAL_A)).json()
        assert lu["statut"] == "PARTIELLEMENT_EXECUTE", cle
    assert [_statut(client, d[f])["statut"] for f in ("fac1", "fac2", "fac3")] == [
        "PARTIELLEMENT_PAYEE",
        "PARTIELLEMENT_PAYEE",
        "RECUE",  # section 8.2 : en contrôle à sa première liquidation
    ]

    # Section 4 du jeu : contrôles.
    eng3 = creer(
        client,
        GMC_A,
        "/api/v1/engagements",
        _corps(
            lot5,
            "CONTRAT",
            contratId=d["marche"]["id"],
            montant="25000000.00",
            imputations=[{"ligneId": lot5["med"]["id"], "montant": "25000000.00"}],
        ),
    )
    plafond = _soumettre(client, eng3).json()["ecarts"]
    assert [(e["code"], e["depassement"]) for e in plafond] == [("PLAFOND_DEPASSE", "5000000.00")]
    hors_marche = creer(
        client,
        GMC_A,
        "/api/v1/engagements",
        _corps(
            lot5,
            "DECISION_AUTORISEE",
            montant="30000000.00",
            imputations=[{"ligneId": lot5["cmd"]["id"], "montant": "30000000.00"}],
        ),
    )
    credit = _soumettre(client, hors_marche).json()["ecarts"]
    assert [(e["code"], e["depassement"]) for e in credit] == [("CREDIT_INSUFFISANT", "5000000.00")]
    doublon = _facture(
        client,
        d["eng1"],
        montant="30000000.00",
        numero="FAC-001",
        bonCommandeId=d["fac1"]["bonCommandeId"],
    )
    assert (doublon.status_code, doublon.json()["code"]) == (409, "FACTURE_DOUBLON")
    trop_paye = _payer(client, lot5, [(d["liq1"], "6000000.00")])
    assert (trop_paye.status_code, trop_paye.json()["code"]) == (422, "PAIEMENT_SUP_SOLDE")
    trop_liquide = _liquider(
        client,
        d["fac3"],
        d["eng1"]["imputations"][0]["id"],
        "6000000.00",
        receptionIds=[d["rec3"]["id"]],
    ).json()
    soumise = client.post(
        f"/api/v1/liquidations/{trop_liquide['id']}/soumissions", headers=entetes(AF_A)
    )
    assert "LIQUIDATION_SUP_FACTURE" in [e["code"] for e in soumise.json()["ecarts"]]
    url = f"/api/v1/engagements/{d['eng1']['id']}"
    version = client.get(url, headers=entetes(GMC_A)).json()["version"]
    modifie = client.patch(
        url,
        json={"montant": "40000000.00"},
        headers=entetes(GMC_A, **{"If-Match": f'"{version}"'}),
    )
    assert modifie.status_code == 409  # RG-18 : passer par une annulation tracée
    solde = _payer(client, lot5, [(d["liq1"], "5000000.00")])
    assert solde.status_code == 201, solde.json()
    assert [_statut(client, d[f])["statut"] for f in ("fac1", "fac2")] == [
        "PAYEE",
        "PARTIELLEMENT_PAYEE",
    ]
