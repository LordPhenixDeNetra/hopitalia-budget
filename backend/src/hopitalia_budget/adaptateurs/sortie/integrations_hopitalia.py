"""Échanges avec Hopitalia (lot 7) : fournisseurs et services (INT-01), commandes et
approvisionnements de la pharmacie (INT-03), journal d'intégration et reprises (INT-07).

Hopitalia est lu, jamais écrit. Chaque échange est rejouable : les éléments sont rapprochés par
leur identifiant Hopitalia (INT-06), si bien qu'une reprise ou un second import ne crée pas de
doublon. Un échange se déroule dans un point de sauvegarde : un échec n'écrit rien, sauf la
ligne du journal qui le décrit.
"""

import hashlib
import json
import logging
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from hopitalia_budget.adaptateurs.sortie.alertes_sql import CLE_SESSION, mettre_en_attente
from hopitalia_budget.adaptateurs.sortie.audit_sql import JournaliseurAuditSql
from hopitalia_budget.adaptateurs.sortie.commandes_sql import (
    accepte_valide,
    lignes_commande,
    numero_suivant,
)
from hopitalia_budget.adaptateurs.sortie.hopitalia import ClientHopitalia
from hopitalia_budget.adaptateurs.sortie.modeles import (
    ApprovisionnementPharmacieModele,
    BonCommandeModele,
    CentreResponsabiliteModele,
    CommandePharmacieModele,
    EngagementModele,
    EtablissementModele,
    FournisseurModele,
    JournalIntegrationModele,
    LigneReceptionModele,
    ReceptionModele,
)
from hopitalia_budget.config import Parametres
from hopitalia_budget.domaine.alertes import Signal, TypeAlerte
from hopitalia_budget.domaine.commandes import (
    LigneReception,
    StatutReception,
    type_reception,
    verifier_lignes_reception,
)
from hopitalia_budget.domaine.erreurs import ErreurMetier
from hopitalia_budget.domaine.ports import EvenementAudit, Horloge

journal_technique = logging.getLogger(__name__)
F, C = FournisseurModele, CentreResponsabiliteModele
CP, AP = CommandePharmacieModele, ApprovisionnementPharmacieModele

SYSTEME = "HOPITALIA"
# Auteur des écritures faites par un import : l'échange, pas un agent.
AUTEUR_ID, AUTEUR_CODE = 0, "HOPITALIA"
TENTATIVES_AUTOMATIQUES = 5


class TypeEchange(StrEnum):
    FOURNISSEURS = "FOURNISSEURS"
    SERVICES = "SERVICES"
    PHARMACIE = "PHARMACIE"


class StatutEchange(StrEnum):
    EN_COURS = "EN_COURS"
    SUCCES = "SUCCES"
    ECHEC = "ECHEC"


class ReponseIncoherente(Exception):
    """Réponse d'Hopitalia inexploitable : l'échange échoue sans rien écrire."""


@dataclass
class Contexte:
    session: Session
    client: ClientHopitalia
    jeton: str
    horloge: Horloge
    journal: JournaliseurAuditSql
    etablissement_id: UUID | None

    def lire(self, chemin: str, **parametres: str) -> Any:
        return self.client.lire(chemin, self.jeton, **parametres)

    def tracer(
        self,
        action: str,
        type_objet: str,
        id_objet: object,
        avant: dict[str, Any] | None,
        apres: dict[str, Any] | None,
        etablissement_id: UUID | None,
    ) -> None:
        self.journal.tracer(
            EvenementAudit(
                action=action,
                type_objet=type_objet,
                id_objet=str(id_objet),
                ancienne_valeur=avant,
                nouvelle_valeur=apres,
                utilisateur_id=AUTEUR_ID,
                code_agent=AUTEUR_CODE,
                etablissement_id=etablissement_id,
            )
        )


# --- Lecture des réponses -------------------------------------------------------------------


def _liste(donnees: Any) -> list[dict[str, Any]]:
    """Liste simple ou page Spring (`content`)."""
    if isinstance(donnees, dict):
        donnees = donnees.get("content")
    if not isinstance(donnees, list) or not all(isinstance(d, dict) for d in donnees):
        raise ReponseIncoherente("LISTE_ATTENDUE")
    return donnees


def _texte(valeur: Any, longueur: int) -> str | None:
    texte = str(valeur).strip() if valeur is not None else ""
    return texte[:longueur] or None


def _nombre(valeur: Any) -> Decimal:
    try:
        return Decimal(str(valeur))
    except (InvalidOperation, ValueError) as exc:
        raise ReponseIncoherente("NOMBRE_ATTENDU") from exc


def _date(valeur: Any) -> date:
    try:
        return date.fromisoformat(str(valeur)[:10])
    except ValueError as exc:
        raise ReponseIncoherente("DATE_ATTENDUE") from exc


def _lignes(donnees: Any) -> list[dict[str, Any]]:
    """Lignes d'une commande ou d'un approvisionnement : liste, ou objet qui les porte."""
    if isinstance(donnees, dict):
        donnees = donnees.get("lignes") or donnees.get("details") or []
    return [
        {
            "codeProduit": _texte(d.get("codeProduit"), 50) or "",
            "nomProduit": _texte(d.get("nomProduit"), 200) or "",
            "quantite": str(_nombre(d.get("quantite"))),
            "montant": str(_nombre(d.get("montant"))),
        }
        for d in _liste(donnees)
    ]


# --- Journal et reprises (INT-07) -----------------------------------------------------------


def etablissement_cible(session: Session, parametres: Parametres) -> UUID:
    """Établissement du module qui reçoit les services et la pharmacie d'Hopitalia."""
    if not parametres.hopitalia_etablissement:
        raise ErreurMetier("CONFIGURATION_INCOMPLETE", parametre="HOPITALIA_ETABLISSEMENT")
    identifiant = session.scalar(
        select(EtablissementModele.id).where(
            EtablissementModele.code == parametres.hopitalia_etablissement
        )
    )
    if identifiant is None:
        raise ErreurMetier("CONFIGURATION_INCOMPLETE", parametre="HOPITALIA_ETABLISSEMENT")
    return identifiant


def parametres_du_jour(type_echange: TypeEchange, jour: date, fenetre: int) -> dict[str, str]:
    if type_echange == TypeEchange.PHARMACIE:
        return {"debut": (jour - timedelta(days=fenetre)).isoformat(), "fin": jour.isoformat()}
    return {"jour": jour.isoformat()}


def identifiant_unique(type_echange: TypeEchange, parametres: dict[str, str]) -> str:
    """Un échange par type et par période : le relancer ou le reprendre réutilise sa ligne."""
    # Ordre des clés fixé : JSONB ne garde pas l'ordre des paramètres relus pour une reprise.
    return ":".join([SYSTEME, type_echange.value, *(parametres[k] for k in sorted(parametres))])


def executer(
    session: Session,
    client: ClientHopitalia,
    config: Parametres,
    horloge: Horloge,
    type_echange: TypeEchange,
    parametres: dict[str, str],
    declencheur: str | None,
) -> JournalIntegrationModele:
    """Lance l'échange, ou le rejoue s'il existe déjà ; le journal dit le résultat."""
    if not config.hopitalia_compte_technique:
        raise ErreurMetier("CONFIGURATION_INCOMPLETE", parametre="HOPITALIA_COMPTE_TECHNIQUE")
    etablissement_id = (
        None if type_echange == TypeEchange.FOURNISSEURS else etablissement_cible(session, config)
    )
    identifiant = identifiant_unique(type_echange, parametres)
    ligne = session.scalar(
        select(JournalIntegrationModele).where(
            JournalIntegrationModele.identifiant_unique == identifiant
        )
    )
    maintenant = horloge.maintenant()
    if ligne is None:
        ligne = JournalIntegrationModele(
            systeme_externe=SYSTEME,
            direction="ENTRANT",
            type_donnees=type_echange.value,
            identifiant_unique=identifiant,
            etablissement_id=etablissement_id,
            parametres=parametres,
            tentatives=0,
            cree_le=maintenant,
        )
        session.add(ligne)
    ligne.tentatives += 1
    ligne.date = maintenant
    ligne.statut = StatutEchange.EN_COURS
    ligne.declenche_par_code = declencheur
    session.flush()
    signaux = len(session.info.get(CLE_SESSION, []))
    point = session.begin_nested()
    try:
        jeton = client.connecter(
            config.hopitalia_compte_technique,
            config.hopitalia_compte_technique_mot_de_passe.get_secret_value(),
        )["jeton_acces"]
        contexte = Contexte(
            session,
            client,
            jeton,
            horloge,
            JournaliseurAuditSql(session, horloge, None),
            etablissement_id,
        )
        resultat = ECHANGES[type_echange](contexte, parametres)
        point.commit()
    except (ErreurMetier, ReponseIncoherente) as exc:
        point.rollback()
        erreur = exc.code if isinstance(exc, ErreurMetier) else f"REPONSE_INCOHERENTE:{exc}"
        _echec(session, ligne, signaux, erreur)
    except Exception:
        # Détail dans le journal du serveur seulement (revue de sécurité, T-252).
        journal_technique.exception("Échange %s en échec", identifiant)
        point.rollback()
        _echec(session, ligne, signaux, "ERREUR_INTERNE")
    else:
        ligne.statut = StatutEchange.SUCCES
        ligne.erreur = None
        ligne.resultat = dict(resultat)
    session.flush()
    return ligne


def _echec(session: Session, ligne: JournalIntegrationModele, signaux: int, erreur: str) -> None:
    # Les alertes préparées par l'échange annulé ne doivent pas partir.
    del session.info.setdefault(CLE_SESSION, [])[signaux:]
    ligne.statut = StatutEchange.ECHEC
    ligne.erreur = erreur[:1000]
    ligne.resultat = None


def reprendre(
    session: Session,
    client: ClientHopitalia,
    config: Parametres,
    horloge: Horloge,
    ligne: JournalIntegrationModele,
    declencheur: str | None,
) -> JournalIntegrationModele:
    """Reprise d'un échange en échec, avec ses paramètres d'origine (idempotente)."""
    if ligne.statut != StatutEchange.ECHEC:
        raise ErreurMetier("ECHANGE_NON_REPRENABLE")
    return executer(
        session,
        client,
        config,
        horloge,
        TypeEchange(ligne.type_donnees),
        dict(ligne.parametres),
        declencheur,
    )


def a_reprendre(session: Session) -> list[JournalIntegrationModele]:
    """Échanges en échec que la tâche planifiée reprend d'elle-même."""
    return list(
        session.scalars(
            select(JournalIntegrationModele)
            .where(
                JournalIntegrationModele.statut == StatutEchange.ECHEC,
                JournalIntegrationModele.tentatives < TENTATIVES_AUTOMATIQUES,
            )
            .order_by(JournalIntegrationModele.id)
        )
    )


# --- Fournisseurs et services (INT-01, EF-REF-05) -------------------------------------------


def _code_libre(session: Session, modele: Any, code: str, *conditions: Any) -> str:
    """Code du module : celui d'Hopitalia, sauf s'il est déjà pris par un autre élément."""
    pris = session.scalar(select(modele.id).where(modele.code == code, *conditions))
    return code if pris is None else f"H-{code}"[:20]


def _synchroniser(
    contexte: Contexte,
    elements: list[dict[str, Any]],
    existants: dict[str | None, Any],
    sans_lien: Callable[[str], Any],
    creer: Callable[[str, dict[str, Any]], Any],
    type_objet: str,
) -> Counter[str]:
    """Création ou mise à jour par code Hopitalia ; un élément disparu est désactivé, jamais
    supprimé ; un élément revenu est réactivé (INT-01)."""
    if not elements and existants:
        # Une liste vide désactiverait tout : réponse refusée plutôt que perte du référentiel.
        raise ReponseIncoherente("LISTE_VIDE")
    compte: Counter[str] = Counter()
    vus: set[str] = set()
    for code, valeurs in ((e.pop("code"), e) for e in elements):
        if code in vus:
            continue
        vus.add(code)
        objet: Any = existants.get(code)
        lie = sans_lien(code) if objet is None else None
        if lie is not None:
            # Élément saisi dans le module avant l'import : rattaché, pas dupliqué (INT-06).
            objet = lie
            objet.code_hopitalia = code
            contexte.tracer(
                "MODIFICATION",
                type_objet,
                objet.id,
                {"codeHopitalia": None},
                {"codeHopitalia": code},
                getattr(objet, "etablissement_id", None),
            )
        if objet is None:
            objet = creer(code, valeurs)
            contexte.session.add(objet)
            contexte.session.flush()
            contexte.tracer(
                "CREATION",
                type_objet,
                objet.id,
                None,
                {"codeHopitalia": code, **valeurs},
                getattr(objet, "etablissement_id", None),
            )
            compte["crees"] += 1
            continue
        # Une valeur absente d'Hopitalia n'efface pas celle complétée dans le module.
        apres = {cle: v for cle, v in valeurs.items() if v is not None} | {"actif": True}
        avant = {cle: getattr(objet, cle) for cle in apres}
        if avant != apres:
            for cle, valeur in apres.items():
                setattr(objet, cle, valeur)
            contexte.tracer(
                "MODIFICATION",
                type_objet,
                objet.id,
                avant,
                apres,
                getattr(objet, "etablissement_id", None),
            )
            compte["modifies"] += 1
    for code, objet in existants.items():
        if code not in vus and objet.actif:
            objet.actif = False
            contexte.tracer(
                "DESACTIVATION",
                type_objet,
                objet.id,
                {"actif": True},
                {"actif": False},
                getattr(objet, "etablissement_id", None),
            )
            compte["desactives"] += 1
    compte["lus"] = len(vus)
    return compte


def importer_fournisseurs(contexte: Contexte, _: dict[str, str]) -> Counter[str]:
    session = contexte.session
    elements = [
        {
            "code": code,
            "raison_sociale": _texte(d.get("nomFourn"), 200) or code,
            "adresse": _texte(d.get("adresse"), 300),
            "contact": _texte(d.get("telephone"), 200),
        }
        for d in _liste(contexte.lire("/api/pharmacie/fournisseurs"))
        if (code := _texte(d.get("codeFourn"), 20))
    ]
    existants = {
        f.code_hopitalia: f for f in session.scalars(select(F).where(F.code_hopitalia.is_not(None)))
    }
    return _synchroniser(
        contexte,
        elements,
        existants,
        lambda code: session.scalar(select(F).where(F.code == code, F.code_hopitalia.is_(None))),
        lambda code, valeurs: F(
            code=_code_libre(session, F, code), code_hopitalia=code, actif=True, **valeurs
        ),
        "Fournisseur",
    )


def _type_centre(service: dict[str, Any]) -> str:
    if service.get("administration"):
        return "ADMINISTRATIF"
    return "MEDICO_TECHNIQUE" if service.get("laboratoire") else "CLINIQUE"


def importer_services(contexte: Contexte, _: dict[str, str]) -> Counter[str]:
    session, etablissement = contexte.session, contexte.etablissement_id
    services = {
        code: d
        for d in _liste(contexte.lire("/api/services"))
        if (code := _texte(d.get("codeService"), 20))
    }
    elements = [
        {"code": code, "libelle": _texte(d.get("nomService"), 200) or code}
        for code, d in services.items()
    ]
    existants = {
        c.code_hopitalia: c
        for c in session.scalars(
            select(C).where(C.etablissement_id == etablissement, C.code_hopitalia.is_not(None))
        )
    }
    return _synchroniser(
        contexte,
        elements,
        existants,
        lambda code: session.scalar(
            select(C).where(
                C.etablissement_id == etablissement, C.code == code, C.code_hopitalia.is_(None)
            )
        ),
        lambda code, valeurs: C(
            etablissement_id=etablissement,
            code=_code_libre(session, C, code, C.etablissement_id == etablissement),
            type=_type_centre(services[code]),
            code_hopitalia=code,
            actif=True,
            **valeurs,
        ),
        "CentreResponsabilite",
    )


# --- Pharmacie (INT-03, EF-REC-07) ----------------------------------------------------------


def _empreinte(contenu: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(contenu, sort_keys=True).encode()).hexdigest()


def importer_pharmacie(contexte: Contexte, parametres: dict[str, str]) -> Counter[str]:
    session, etablissement = contexte.session, contexte.etablissement_id
    if etablissement is None:
        raise ErreurMetier("CONFIGURATION_INCOMPLETE", parametre="HOPITALIA_ETABLISSEMENT")
    periode = {"start": parametres["debut"], "end": parametres["fin"]}
    maintenant = contexte.horloge.maintenant()
    compte: Counter[str] = Counter()

    for bc in _liste(contexte.lire("/api/pharmacie/bons-commandes", **periode)):
        id_hopitalia = int(_nombre(bc.get("id")))
        commande = session.scalar(
            select(CP).where(CP.etablissement_id == etablissement, CP.id_hopitalia == id_hopitalia)
        )
        if commande is not None and commande.bon_commande_id is not None:
            continue  # rattachée : le bon de commande du module fait foi (RG-18)
        lignes = _lignes(contexte.lire(f"/api/pharmacie/bons-commandes/{id_hopitalia}/details"))
        code_fournisseur = _texte(bc.get("codeFourn"), 20)
        valeurs = {
            "numero": _texte(bc.get("numBc"), 30) or str(id_hopitalia),
            "date_commande": _date(bc.get("dateBc")),
            "code_fournisseur": code_fournisseur,
            "fournisseur_id": session.scalar(
                select(FournisseurModele.id).where(
                    FournisseurModele.code_hopitalia == code_fournisseur
                )
            ),
            "service": _texte(bc.get("nomService"), 200),
            "lignes": lignes,
            "montant": sum((Decimal(lg["montant"]) for lg in lignes), Decimal("0")),
        }
        if commande is None:
            session.add(
                CP(
                    etablissement_id=etablissement,
                    id_hopitalia=id_hopitalia,
                    importe_le=maintenant,
                    **valeurs,
                )
            )
            compte["commandes"] += 1
        else:
            for cle, valeur in valeurs.items():
                setattr(commande, cle, valeur)
    session.flush()

    for item in _liste(contexte.lire("/api/pharmacie/approvisionnements/historique", **periode)):
        id_hopitalia = int(_nombre(item.get("id")))
        detail = contexte.lire(f"/api/pharmacie/approvisionnements/{id_hopitalia}")
        source = detail if isinstance(detail, dict) else item
        contenu: dict[str, Any] = {
            "numero_bl": _texte(source.get("numBl"), 50),
            "numero_commande": _texte(source.get("numBonCmde"), 30),
            "date_approvisionnement": _date(source.get("date")).isoformat(),
            "code_fournisseur": _texte(source.get("codeFourn"), 20),
            "lignes": _lignes(detail),
        }
        empreinte = _empreinte(contenu)
        appro = session.scalar(
            select(AP).where(AP.etablissement_id == etablissement, AP.id_hopitalia == id_hopitalia)
        )
        if appro is not None and appro.empreinte == empreinte:
            continue  # déjà importé, inchangé : importé une seule fois
        contenu["date_approvisionnement"] = date.fromisoformat(contenu["date_approvisionnement"])
        if appro is None:
            appro = AP(
                etablissement_id=etablissement,
                id_hopitalia=id_hopitalia,
                importe_le=maintenant,
                empreinte=empreinte,
                **contenu,
            )
            session.add(appro)
            session.flush()
            compte["approvisionnements"] += 1
        elif appro.reception_id is not None:
            # Modifié dans Hopitalia après sa réception : la réception validée ne change pas
            # (RG-18), un écart est signalé à l'agent financier.
            reception = session.get_one(ReceptionModele, appro.reception_id)
            mettre_en_attente(
                session,
                Signal(
                    TypeAlerte.ECART_RAPPROCHEMENT,
                    "Reception",
                    reception.id,
                    etablissement,
                    cle=empreinte[:16],
                    # `context` choisit le message de l'alerte à l'écran (i18next).
                    details={"numero": reception.numero, "context": "HOPITALIA_MODIFIE"},
                ),
            )
            appro.empreinte = empreinte
            compte["ecarts"] += 1
            continue
        else:
            for cle, valeur in contenu.items():
                setattr(appro, cle, valeur)
            appro.empreinte = empreinte
        if creer_reception(contexte.session, contexte.journal, maintenant, appro):
            compte["receptions"] += 1

    for item in _liste(
        contexte.lire("/api/pharmacie/approvisionnements/historique-suppressions", **periode)
    ):
        id_hopitalia = int(_nombre(item.get("approvisionnementId", item.get("id"))))
        appro = session.scalar(
            select(AP).where(AP.etablissement_id == etablissement, AP.id_hopitalia == id_hopitalia)
        )
        if appro is None or appro.supprime:
            continue
        appro.supprime = True
        if appro.reception_id is not None:
            reception = session.get_one(ReceptionModele, appro.reception_id)
            if reception.statut == StatutReception.VALIDE:
                reception.statut = StatutReception.ANNULE
                contexte.tracer(
                    "ANNULATION",
                    "Reception",
                    reception.id,
                    {"statut": StatutReception.VALIDE.value},
                    {
                        "statut": StatutReception.ANNULE.value,
                        "motif": "APPROVISIONNEMENT_SUPPRIME_HOPITALIA",
                        "approvisionnementHopitalia": str(id_hopitalia),
                    },
                    etablissement,
                )
                # Une facture a pu être liquidée sur cette réception : l'agent financier vérifie.
                mettre_en_attente(
                    session,
                    Signal(
                        TypeAlerte.ECART_RAPPROCHEMENT,
                        "Reception",
                        reception.id,
                        etablissement,
                        cle="SUPPRIME",
                        details={"numero": reception.numero, "context": "HOPITALIA_SUPPRIME"},
                    ),
                )
                compte["annulations"] += 1
    return compte


def creer_reception(
    session: Session,
    journal: JournaliseurAuditSql,
    maintenant: Any,
    appro: ApprovisionnementPharmacieModele,
) -> bool:
    """Réception validée d'un approvisionnement, si sa commande est rattachée (EF-REC-07) ; la
    preuve du service fait est le bon de livraison. Faux s'il reste en attente."""
    if appro.supprime or appro.reception_id is not None or not appro.numero_commande:
        return False
    commande = session.scalar(
        select(CommandePharmacieModele).where(
            CommandePharmacieModele.etablissement_id == appro.etablissement_id,
            CommandePharmacieModele.numero == appro.numero_commande,
            CommandePharmacieModele.bon_commande_id.is_not(None),
        )
    )
    if commande is None or commande.bon_commande_id is None:
        return False
    bon = session.get_one(BonCommandeModele, commande.bon_commande_id)
    lignes_bc = lignes_commande(session, bon.id)
    # Les lignes du bon de commande suivent l'ordre des lignes importées (rang = position + 1).
    par_produit = {lg["codeProduit"]: lignes_bc[i].id for i, lg in enumerate(commande.lignes)}
    recues: dict[UUID, Decimal] = {}
    for importee in appro.lignes:
        ligne_id = par_produit.get(importee["codeProduit"])
        if ligne_id is None:
            return False  # produit absent de la commande : reste en attente, à examiner
        recues[ligne_id] = recues.get(ligne_id, Decimal("0")) + Decimal(importee["quantite"])
    lignes = [LigneReception(i, q, q, Decimal("0")) for i, q in recues.items()]
    deja = accepte_valide(session, bon.id)
    try:
        verifier_lignes_reception(lignes_bc, lignes, deja)
    except ErreurMetier:
        return False  # quantités au-delà de la commande : reste en attente, à examiner
    engagement = session.get_one(EngagementModele, bon.engagement_id)
    reception = ReceptionModele(
        etablissement_id=appro.etablissement_id,
        bon_commande_id=bon.id,
        numero=numero_suivant(
            session,
            ReceptionModele,
            appro.etablissement_id,
            "REC",
            str(appro.date_approvisionnement.year),
        ),
        date_reception=appro.date_approvisionnement,
        type=type_reception(lignes_bc, lignes, deja),
        centre_id=engagement.centre_id,
        agent_responsable_code=AUTEUR_CODE,
        observations=f"Bon de livraison {appro.numero_bl or ''} (pharmacie Hopitalia)",
        statut=StatutReception.VALIDE,
        cree_par_id=AUTEUR_ID,
        cree_par_code=AUTEUR_CODE,
        cree_le=maintenant,
    )
    session.add(reception)
    session.flush()
    for lg in lignes:
        session.add(
            LigneReceptionModele(
                reception_id=reception.id,
                ligne_commande_id=lg.ligne_commande_id,
                quantite_recue=lg.quantite_recue,
                quantite_acceptee=lg.quantite_acceptee,
                quantite_rejetee=lg.quantite_rejetee,
            )
        )
    appro.reception_id = reception.id
    session.flush()
    journal.tracer(
        EvenementAudit(
            action="CREATION",
            type_objet="Reception",
            id_objet=str(reception.id),
            ancienne_valeur=None,
            nouvelle_valeur={
                "numero": reception.numero,
                "statut": reception.statut,
                "bonLivraison": appro.numero_bl,
                "approvisionnementHopitalia": str(appro.id_hopitalia),
            },
            utilisateur_id=AUTEUR_ID,
            code_agent=AUTEUR_CODE,
            etablissement_id=appro.etablissement_id,
        )
    )
    return True


ECHANGES: dict[TypeEchange, Callable[[Contexte, dict[str, str]], Counter[str]]] = {
    TypeEchange.FOURNISSEURS: importer_fournisseurs,
    TypeEchange.SERVICES: importer_services,
    TypeEchange.PHARMACIE: importer_pharmacie,
}
