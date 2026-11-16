"""Domaine et application testés avec les doubles des ports : ni base, ni réseau (T-056, ARC-D)."""

import re
from decimal import Decimal
from pathlib import Path

import pytest

from hopitalia_budget.application import etablissements
from hopitalia_budget.domaine.erreurs import ErreurMetier
from hopitalia_budget.domaine.habilitations import MATRICE, Droit, Operation, Profil, autorise
from hopitalia_budget.domaine.monnaie import vers_montant
from hopitalia_budget.domaine.utilisateur import Habilitation, Utilisateur
from tests.doubles import (
    DepotEtablissementsMemoire,
    HorlogeFixe,
    JournaliseurAuditMemoire,
    NotificateurMemoire,
    StockagePiecesMemoire,
)

MATRICE_VALIDEE = Path(__file__).parents[2] / "docs" / "cadrage" / "matrice-habilitations.md"

# Libellés du document validé → opérations du code.
LIBELLES = {
    "Paramétrer référentiels, circuits, alertes, profils": Operation.PARAMETRER,
    "Saisir ou importer un budget, une notification de crédits": Operation.SAISIR_BUDGET,
    "Demander une révision budgétaire": Operation.DEMANDER_REVISION,
    "Valider une révision budgétaire": Operation.VALIDER_REVISION,
    "Enregistrer un contrat, un avenant": Operation.ENREGISTRER_CONTRAT,
    "Valider un contrat, un avenant": Operation.VALIDER_CONTRAT,
    "Demander un engagement": Operation.DEMANDER_ENGAGEMENT,
    "Contrôler un engagement (imputation, crédits)": Operation.CONTROLER_ENGAGEMENT,
    "Valider un engagement": Operation.VALIDER_ENGAGEMENT,
    "Émettre un bon de commande": Operation.EMETTRE_COMMANDE,
    "Rattacher une commande de la pharmacie à un engagement": (
        Operation.RATTACHER_COMMANDE_PHARMACIE
    ),
    "Enregistrer une réception": Operation.ENREGISTRER_RECEPTION,
    "Valider le service fait": Operation.VALIDER_SERVICE_FAIT,
    "Enregistrer une facture": Operation.ENREGISTRER_FACTURE,
    "Liquider une facture": Operation.LIQUIDER,
    "Valider une liquidation": Operation.VALIDER_LIQUIDATION,
    "Ordonnancer (transmettre en paiement)": Operation.ORDONNANCER,
    "Enregistrer un paiement": Operation.ENREGISTRER_PAIEMENT,
    "Accorder une dérogation": Operation.ACCORDER_DEROGATION,
    "Annuler une opération validée": Operation.ANNULER_OPERATION_VALIDEE,
    "Clôturer un exercice": Operation.CLOTURER_EXERCICE,
    "Consulter les tableaux de bord et exporter les états": Operation.CONSULTER_TABLEAUX_BORD,
    "Consulter le journal d'audit": Operation.CONSULTER_AUDIT,
    "Gérer les recettes (prévisions, facturé, encaissé)": Operation.GERER_RECETTES,
}


def test_matrice_identique_au_document_valide() -> None:
    texte = MATRICE_VALIDEE.read_text(encoding="utf-8")
    entete = re.search(r"^\| Opération \|(.+)\|$", texte, re.M)
    assert entete is not None
    profils = [Profil(p.strip()) for p in entete.group(1).split("|")]
    lues: dict[Operation, dict[Profil, Droit]] = {}
    for libelle, operation in LIBELLES.items():
        ligne = re.search(rf"^\| {re.escape(libelle)} \|(.+)\|$", texte, re.M)
        assert ligne is not None, libelle
        cases = [c.strip() for c in ligne.group(1).split("|")]
        lues[operation] = {p: Droit(c) for p, c in zip(profils, cases, strict=True) if c != "—"}
    assert lues == MATRICE


def test_saisir_ou_valider_inclut_consulter_mais_pas_l_inverse() -> None:
    assert autorise(Profil.AF, Operation.LIQUIDER, Droit.SAISIR)
    assert autorise(Profil.AF, Operation.LIQUIDER, Droit.CONSULTER)
    assert not autorise(Profil.AF, Operation.LIQUIDER, Droit.VALIDER)
    assert not autorise(Profil.LEC, Operation.LIQUIDER, Droit.CONSULTER)


def test_separation_des_taches_dans_la_matrice() -> None:
    # Celui qui liquide ne valide pas la liquidation ; celui qui la valide ne paie pas (RG-13).
    assert not autorise(Profil.AF, Operation.VALIDER_LIQUIDATION, Droit.VALIDER)
    assert not autorise(Profil.VAL, Operation.ENREGISTRER_PAIEMENT, Droit.SAISIR)


@pytest.mark.parametrize(
    ("valeur", "attendu"),
    [("45000000", "45000000.00"), ("0.1", "0.10"), ("-12.34", "-12.34")],
)
def test_montant_exact(valeur: str, attendu: str) -> None:
    assert vers_montant(valeur) == Decimal(attendu)
    assert str(vers_montant(valeur)) == attendu


@pytest.mark.parametrize("valeur", ["1.005", "abc", "NaN", "Infinity", "10000000000000000"])
def test_montant_refuse_sans_arrondi_implicite(valeur: str) -> None:
    with pytest.raises(ErreurMetier) as erreur:
        vers_montant(valeur)
    assert erreur.value.code == "MONTANT_INVALIDE"


def _utilisateur(*habilitations: Habilitation) -> Utilisateur:
    return Utilisateur(1, "AG001", "Awa Diop", "DAF", habilitations)


def test_creation_tracee_dans_le_journal() -> None:
    depot, journal = DepotEtablissementsMemoire(), JournaliseurAuditMemoire()
    admin = _utilisateur(Habilitation(Profil.ADM, None))
    cree = etablissements.creer(depot, journal, admin, "CHU-A", "CHU A")
    assert [e.action for e in journal.evenements] == ["CREATION"]
    assert journal.evenements[0].nouvelle_valeur == {
        "id": str(cree.id),
        "code": "CHU-A",
        "nom": "CHU A",
        "actif": True,
        "version": 1,
        "volet_recettes_actif": False,
    }


def test_creation_refusee_sans_habilitation_globale() -> None:
    depot = DepotEtablissementsMemoire()
    autre = depot.ajouter("CHU-B", "CHU B")
    admin_local = _utilisateur(Habilitation(Profil.ADM, autre.id))
    with pytest.raises(ErreurMetier) as erreur:
        etablissements.creer(depot, JournaliseurAuditMemoire(), admin_local, "CHU-C", "CHU C")
    assert erreur.value.code == "ACCES_REFUSE"


def test_etablissement_hors_perimetre_introuvable() -> None:
    depot = DepotEtablissementsMemoire()
    a, b = depot.ajouter("CHU-A", "A"), depot.ajouter("CHU-B", "B")
    lecteur_a = _utilisateur(Habilitation(Profil.LEC, a.id))
    assert etablissements.obtenir(depot, lecteur_a, a.id).code == "CHU-A"
    with pytest.raises(ErreurMetier) as erreur:
        etablissements.obtenir(depot, lecteur_a, b.id)
    assert erreur.value.code == "RESSOURCE_INTROUVABLE"


def test_modification_avec_version_perimee_refusee() -> None:
    depot = DepotEtablissementsMemoire()
    cree = depot.ajouter("CHU-A", "A")
    admin = _utilisateur(Habilitation(Profil.ADM, None))
    with pytest.raises(ErreurMetier) as erreur:
        etablissements.modifier(depot, JournaliseurAuditMemoire(), admin, cree.id, 99, "B", None)
    assert erreur.value.code == "PRECONDITION_ECHOUEE"


def test_doubles_des_ports() -> None:
    horloge = HorlogeFixe()
    debut = horloge.maintenant()
    horloge.avancer(minutes=5)
    assert (horloge.maintenant() - debut).total_seconds() == 300
    stockage = StockagePiecesMemoire()
    piece = stockage.deposer(b"PV de reception")
    assert stockage.lire(piece.reference) == b"PV de reception"
    notificateur = NotificateurMemoire()
    notificateur.notifier(["daf@hopital.test"], "Alerte", "Seuil atteint")
    assert notificateur.envois == [(["daf@hopital.test"], "Alerte", "Seuil atteint")]
