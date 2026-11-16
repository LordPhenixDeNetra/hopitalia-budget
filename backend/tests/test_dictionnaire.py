"""Dictionnaire des données (T-280), produit depuis le modèle SQLAlchemy.

Chaque table est décrite par la docstring de sa classe, chaque colonne par la table
DESCRIPTIONS ci-dessous (par nom de colonne, ou `table.colonne` quand le sens dépend de la
table) ; une clé étrangère sans description propre est décrite par sa table cible. Le test échoue
si une table ou une colonne n'est pas décrite, ou si `docs/conception/dictionnaire-donnees.md`
n'est plus à jour. Régénérer depuis `backend/` : `python -m tests.test_dictionnaire`.
"""

# ruff: noqa: E501  (table de descriptions : une description par ligne, sans coupure)

import inspect
from pathlib import Path
from typing import Any

from sqlalchemy import Column, Table, UniqueConstraint
from sqlalchemy.dialects import postgresql

import hopitalia_budget.adaptateurs.sortie.modeles as modeles
from hopitalia_budget.adaptateurs.sortie.base import Base

RACINE = Path(__file__).parents[2]
DICTIONNAIRE = RACINE / "docs" / "conception" / "dictionnaire-donnees.md"
# Types affichés comme en base (UUID, NUMERIC, JSONB).
DIALECTE = postgresql.dialect()  # type: ignore[no-untyped-call]

DESCRIPTIONS = {
    # --- Communes --------------------------------------------------------------------------
    "id": "Identifiant unique (UUID), exposé par l'API et partagé entre modules (INT-06).",
    "version": "Version de la ligne : verrou optimiste, comparée à l'en-tête `If-Match`.",
    "etablissement_id": "Établissement propriétaire : cloisonnement vérifié à chaque requête.",
    "actif": "Faux : élément désactivé, conservé pour l'historique, plus proposé à la saisie.",
    "code": "Code de l'élément, unique dans son périmètre.",
    "libelle": "Libellé affiché.",
    "numero": "Numéro de pièce, unique par établissement (`PREFIXE-ANNEE-RANG`).",
    "statut": "Statut dans le cycle de l'objet (cycle de référence : cahier des charges, 7).",
    "type": "Type de l'élément (valeurs fixées par l'API).",
    "montant": "Montant en francs CFA, `Numeric(18,2)`.",
    "motif": "Motif saisi, obligatoire pour l'opération.",
    "objet": "Objet de la pièce.",
    "reference": "Référence externe de la pièce.",
    "date": "Date de l'événement.",
    "date_debut": "Début de validité.",
    "date_fin": "Fin de validité.",
    "cree_le": "Date et heure de création.",
    "cree_par_id": "Identifiant Hopitalia (`userId`) de l'agent créateur.",
    "cree_par_code": "Code de l'agent créateur.",
    "code_agent": "Code de l'agent Hopitalia concerné.",
    "utilisateur_id": "Identifiant Hopitalia (`userId`) de l'agent.",
    "type_objet": "Type de l'objet concerné (`Engagement`, `Facture`…).",
    "id_objet": "Identifiant de l'objet concerné.",
    "horodatage": "Date et heure de l'événement.",
    "observations": "Observations libres.",
    "description": "Description libre.",
    "adresse": "Adresse postale.",
    "nature": "Nature de l'élément (valeurs fixées par l'API).",
    "lignes": "Lignes importées telles quelles (JSON : produit, désignation, quantité, montant).",
    "code_fournisseur": "Code du fournisseur dans Hopitalia (`codeFourn`).",
    "id_hopitalia": "Identifiant de l'élément dans Hopitalia ; unique par établissement.",
    "importe_le": "Date et heure du premier import.",
    "code_hopitalia": "Code de l'élément dans Hopitalia ; vide pour un élément saisi dans le module.",
    "cle": "Clé de dédoublonnage.",
    # --- Référentiels et budget ------------------------------------------------------------
    "nom": "Nom de l'établissement.",
    "nom_agent": "Nom de l'agent, lu dans Hopitalia à l'attribution du profil.",
    "profil": "Profil budgétaire (matrice des habilitations : ADM, RB, AF, GMC, SD, REC, VAL, ORD, CPT, AUD, LEC).",
    "langue": "Langue de l'interface choisie par l'agent (`fr`, `en`).",
    "theme": "Thème choisi par l'agent : clair, sombre ou celui du système (IHM-01).",
    "densite": "Densité de l'affichage choisie par l'agent : compacte ou confortable (IHM-02).",
    "colonnes_masquees": "Colonnes masquées par l'agent, par tableau (JSON : nom du tableau -> clés des colonnes).",
    "code_responsable": "Code de l'agent responsable du centre.",
    "seuil_hors_marche": "Type de dépense : montant au-delà duquel un achat hors marché est refusé.",
    "type_compte": "Compte de trésorerie : `BANQUE`, `CAISSE` ou `TRESOR`.",
    "numero_compte_chiffre": "Numéro de compte chiffré (Fernet, clé hors base, ENF-03).",
    "fin_numero": "Quatre derniers chiffres du numéro de compte, affichés masqués.",
    "banque": "Banque du compte.",
    "par_defaut": "Vrai : coordonnées proposées par défaut au paiement.",
    "duree_conservation_ans": "Type de pièce : durée de conservation en années.",
    "type_financement": "Source de financement : type (budget de l'État, ressources propres, bailleur…).",
    "bailleur": "Source de financement : bailleur.",
    "types_objets": "Type de pièce : objets pour lesquels la pièce est obligatoire avant validation.",
    "raison_sociale": "Raison sociale du fournisseur.",
    "identifiants_administratifs": "Identifiants administratifs (NINEA, registre du commerce).",
    "contact": "Contact (téléphone, courriel).",
    "niveau": "Niveau dans la nomenclature : section, chapitre, article, paragraphe.",
    "date_ouverture": "Premier jour de l'exercice.",
    "date_cloture": "Dernier jour de l'exercice.",
    "dotation_initiale": "Dotation initiale de la ligne (budget primitif).",
    "nature_economique": "Nature économique de la ligne (fonctionnement, investissement…).",
    "sens": "Sens de la révision : augmentation ou diminution.",
    "valeur": "Valeur du paramètre de calcul.",
    "date_notification": "Date de notification.",
    "anomalies": "Rapport d'anomalies de l'import, ligne par ligne (JSON).",
    "contenu": "Contenu CSV importé.",
    "lignes_importees": "Nombre de lignes créées par l'import.",
    "termine_le": "Date et heure de fin du traitement.",
    # --- Workflow, pièces, audit, alertes --------------------------------------------------
    "etapes": "Étapes du circuit : profils valideurs dans l'ordre (JSON).",
    "seuil_min": "Montant à partir duquel le circuit s'applique.",
    "seuil_max": "Montant jusqu'auquel le circuit s'applique (vide : sans limite).",
    "separation_taches": "Vrai : l'auteur d'une pièce ne peut pas la viser.",
    "circuit": "Circuit de validation figé à la soumission (JSON).",
    "etape": "Profil de l'étape visée (vide pour une soumission).",
    "ordre": "Rang de l'étape dans le circuit.",
    "rang": "Rang de la ligne.",
    "decision": "Soumission, visa d'étape, validation finale, rejet ou retour à corriger.",
    "visa": "Mention de visa saisie par le valideur.",
    "delegant_code": "Code de l'agent qui délègue.",
    "delegant_id": "Identifiant Hopitalia de l'agent qui délègue.",
    "delegataire_code": "Code de l'agent qui reçoit la délégation.",
    "delegataire_id": "Identifiant Hopitalia de l'agent qui reçoit la délégation.",
    "statut_reference": "Statut du cycle de référence auquel le statut personnalisé correspond.",
    "depuis": "Statut de départ de la transition.",
    "vers": "Statut d'arrivée de la transition.",
    "action": "Action réalisée (création, modification, validation, export…).",
    "ancienne_valeur": "Valeur avant l'opération (JSON).",
    "nouvelle_valeur": "Valeur après l'opération (JSON).",
    "adresse_ip": "Adresse IP de l'agent.",
    "nom_fichier": "Nom du fichier déposé.",
    "type_mime": "Type du fichier (liste fermée).",
    "taille": "Taille du fichier en octets.",
    "empreinte_sha256": "Empreinte SHA-256 du contenu : le fichier est rangé et vérifié par elle.",
    "depose_le": "Date et heure du dépôt.",
    "depose_par_id": "Identifiant Hopitalia de l'agent qui dépose.",
    "depose_par_code": "Code de l'agent qui dépose.",
    "empreinte_requete": "Empreinte du corps de la requête : une clé réutilisée avec un autre corps est refusée.",
    "code_reponse": "Code HTTP de la réponse rendue.",
    "reponse": "Réponse rendue (JSON), renvoyée telle quelle si la clé revient.",
    "expire_le": "Fin de conservation de la clé.",
    "gravite": "Gravité de l'alerte : blocage ou alerte.",
    "details": "Valeurs du message de l'alerte (JSON).",
    "profils": "Profils destinataires de l'alerte (JSON).",
    "lue_le": "Date et heure de lecture par l'agent.",
    "seuil_pourcent": "Seuil de consommation en pourcentage.",
    "delai_jours": "Délai en jours.",
    "notifier_par_email": "Vrai : l'alerte est aussi envoyée par courriel (T-225, en attente).",
    # --- Contrats ---------------------------------------------------------------------------
    "intitule": "Intitulé du contrat.",
    "reference_dossier": "Référence du dossier de passation (marché déjà attribué).",
    "numero_lot": "Numéro du lot du marché.",
    "date_signature": "Date de signature.",
    "date_demarrage": "Date de démarrage des prestations.",
    "date_echeance": "Date d'échéance.",
    "duree_mois": "Durée en mois.",
    "montant_initial_ht": "Montant initial hors taxes.",
    "montant_initial_ttc": "Montant initial toutes taxes comprises.",
    "taux_taxe": "Taux de taxe en pourcentage.",
    "devise": "Devise du contrat.",
    "periodicite": "Périodicité de facturation.",
    "modalite_facturation": "Modalité de facturation.",
    "perimetre": "Périmètre des prestations.",
    "taux_avance": "Taux de l'avance de démarrage en pourcentage.",
    "mode_recuperation_avance": "Mode de récupération de l'avance sur les décomptes.",
    "taux_retenue_garantie": "Taux de la retenue de garantie en pourcentage.",
    "condition_liberation_retenue": "Condition de libération de la retenue de garantie.",
    "date_liberation_retenue": "Date de libération de la retenue de garantie.",
    "responsable_code": "Code de l'agent responsable du suivi.",
    "date_effet": "Date d'effet de l'avenant.",
    "montant_avant": "Montant actualisé du contrat avant l'avenant.",
    "variation": "Variation du montant apportée par l'avenant (positive ou négative).",
    "nouveau_plafond": "Montant actualisé après l'avenant.",
    "montant_prevu": "Montant prévu à l'échéance.",
    "formule": "Formule de révision de prix.",
    "indice": "Valeur de l'indice appliqué.",
    "incidence": "Incidence financière de la révision de prix.",
    # --- Engagements, commandes, réceptions -------------------------------------------------
    "date_engagement": "Date de l'engagement.",
    "origine": "Origine : contrat, décision autorisée, hors marché, mission ou petit achat.",
    "nature_hors_marche": "Nature d'un achat hors marché.",
    "justification": "Justification d'un achat hors marché.",
    "reference_decision": "Référence de la décision qui autorise la dépense.",
    "date_validation": "Date et heure de la validation finale.",
    "montant_depassement": "Dépassement autorisé par la dérogation (RG-19).",
    "date_emission": "Date d'émission de la pièce.",
    "lieu_livraison": "Lieu de livraison (service destinataire pour une commande de la pharmacie).",
    "date_livraison_prevue": "Date de livraison prévue ; dépassée, la commande est en retard (EF-REC-06).",
    "designation": "Désignation de l'article ou de la prestation.",
    "quantite": "Quantité commandée.",
    "prix_unitaire": "Prix unitaire hors taxes.",
    "date_reception": "Date de réception.",
    "agent_responsable_code": "Code de l'agent qui réceptionne (`HOPITALIA` pour un approvisionnement importé).",
    "quantite_recue": "Quantité reçue.",
    "quantite_acceptee": "Quantité acceptée ; compte dans le réceptionné une fois la réception validée.",
    "quantite_rejetee": "Quantité rejetée.",
    "date_constat": "Date du constat de la réserve.",
    "date_levee": "Date de levée de la réserve.",
    "levee_par_code": "Code de l'agent qui lève la réserve.",
    "conforme": "Vrai : prestation conforme.",
    "livrable": "Livrable attesté.",
    # --- Factures, liquidations, paiements --------------------------------------------------
    "numero_decompte": "Numéro du décompte (facture de marché).",
    "periode_rattachement": "Période à laquelle la facture se rattache.",
    "montant_ht": "Montant hors taxes.",
    "montant_taxes": "Montant des taxes.",
    "montant_ttc": "Montant toutes taxes comprises.",
    "date_limite_traitement": "Date limite de traitement de la facture.",
    "motif_levee_doublon": "Motif de la levée du blocage de doublon (RG-16).",
    "motif_statut": "Motif du dernier changement de statut (rejet, retour).",
    "date_liquidation": "Date de la liquidation.",
    "montant_base": "Montant liquidé avant déductions.",
    "base_calcul": "Base de calcul de la déduction.",
    "taux": "Taux de la déduction en pourcentage.",
    "date_rapprochement": "Date du rapprochement.",
    "ecart_commande_reception": "Écart entre commandé et réceptionné.",
    "ecart_reception_facture": "Écart entre réceptionné et facturé.",
    "ecart_facture_paiement": "Écart entre facturé et payé.",
    "explication": "Explication de l'écart, obligatoire s'il n'est pas nul.",
    "reference_piece": "Référence du mandat ou de l'ordre de paiement.",
    "type_piece": "Type de pièce de l'ordonnancement (mandat, ordre de paiement).",
    "date_transmission": "Date de transmission au comptable.",
    "service_destinataire": "Service destinataire de la transmission.",
    "transmis_par_id": "Identifiant Hopitalia de l'agent qui transmet.",
    "date_paiement": "Date d'exécution du paiement.",
    "reference_transaction": "Référence bancaire ou de transaction.",
    "piece_caisse": "Référence de la pièce de caisse.",
    "retenue_source": "Retenue à la source opérée au paiement.",
    "motif_annulation": "Motif de l'annulation du paiement.",
    # --- Clôture ---------------------------------------------------------------------------
    "engagements_reportes": "Nombre d'engagements reportés sur l'exercice suivant.",
    "montant_reporte": "Montant total reporté.",
    "reouvert_le": "Date et heure de réouverture (vide : clôture en vigueur).",
    "reouvert_par_code": "Code de l'agent qui rouvre.",
    "motif_reouverture": "Motif de la réouverture.",
    # --- Intégrations ----------------------------------------------------------------------
    "systeme_externe": "Système externe de l'échange (`HOPITALIA`).",
    "direction": "Sens de l'échange (`ENTRANT`).",
    "type_donnees": "Données échangées : fournisseurs, services ou pharmacie.",
    "identifiant_unique": "Système, type et période : un échange rejoué réutilise sa ligne (INT-07).",
    "parametres": "Paramètres de l'échange (jour, ou début et fin de la fenêtre), réutilisés par une reprise.",
    "erreur": "Code d'erreur du dernier échec.",
    "resultat": "Compteurs du dernier succès (lus, créés, modifiés…).",
    "tentatives": "Nombre de tentatives ; la reprise automatique s'arrête à cinq.",
    "declenche_par_code": "Code de l'agent qui a lancé ou repris l'échange (vide : tâche planifiée).",
    "date_commande": "Date de la commande dans Hopitalia.",
    "service": "Service demandeur dans Hopitalia.",
    "numero_bl": "Numéro du bon de livraison : preuve du service fait.",
    "numero_commande": "Numéro de la commande Hopitalia livrée (`numBonCmde`).",
    "date_approvisionnement": "Date de l'approvisionnement.",
    "empreinte": "Empreinte du contenu : un approvisionnement inchangé n'est pas réimporté.",
    "supprime": "Vrai : approvisionnement supprimé dans Hopitalia ; sa réception est annulée.",
    # --- Sens propre à une table -----------------------------------------------------------
    "journal_audit.id": "Rang de l'entrée, croissant : le journal est en ajout seul.",
    "journal_audit.etablissement_id": "Établissement de l'objet tracé (vide : opération globale).",
    "journal_integration.id": "Rang de l'échange, croissant.",
    "journal_integration.etablissement_id": "Établissement qui reçoit les données (vide : fournisseurs, communs).",
    "journal_integration.date": "Date et heure de la dernière tentative.",
    "journal_integration.statut": "`EN_COURS`, `SUCCES` ou `ECHEC`.",
    "referentiel.type": "Type de référentiel (source de financement, programme, mode de règlement, type de pièce…).",
    "referentiel.numero": "Compte de trésorerie : numéro du compte.",
    "centre_responsabilite.type": "Type de centre : clinique, médico-technique, administratif, logistique, autre.",
    "periode.type": "Type de période : annuelle, trimestrielle ou mensuelle.",
    "budget.type": "Type de budget : primitif ou modificatif.",
    "budget.reference": "Référence du budget (`BP-2026`).",
    "revision_budgetaire.type": "Budget modificatif, virement, réallocation, augmentation ou diminution.",
    "contrat.type": "Marché, convention, maintenance, prestation ou autre.",
    "contrat.nature": "Marché : fournitures, travaux, services ou prestations intellectuelles.",
    "contrat.numero": "Numéro du contrat attribué.",
    "contrat.objet": "Objet du contrat.",
    "derogation.nature": "Dépassement autorisé (RG-19) : crédit, plafond du contrat, seuil hors marché, liquidation au-delà du dû, paiement au-delà du solde, doublon.",
    "ordre_service.type": "Type d'ordre de service : démarrage, arrêt, reprise, modification, autre.",
    "annulation.type": "Annulation, clôture (reliquat libéré) ou report sur l'exercice suivant.",
    "bon_commande.type": "Bon de commande, tranche ou ordre de service.",
    "reception.type": "Réception totale, partielle ou refusée.",
    "reception.statut": "Statut de la réception ; seule une réception validée prouve le service fait ; `ANNULE` : approvisionnement supprimé dans Hopitalia.",
    "facture.type": "Avance, acompte, partielle, définitive, décompte ou avoir.",
    "deduction.type": "Avance récupérée, retenue de garantie, pénalité, réfaction, retenue à la source, autre.",
    "regle_alerte.type": "Type d'alerte réglée (section 14.3).",
    "alerte.type": "Type d'alerte (section 14.3).",
    "habilitation.etablissement_id": "Établissement du profil (vide : tous les établissements).",
    "habilitation.code_agent": "Code de l'agent habilité.",
    "transition_statut.action": "Action qui fait passer de `depuis` à `vers`.",
    "transition_statut.profil": "Profil qui peut faire la transition.",
    "cle_idempotence.cle": "Clé `Idempotency-Key` envoyée par le client.",
    "alerte.cle": "Clé de dédoublonnage : même type, objet et clé, une seule alerte.",
    "notification_credit.reference": "Référence de la notification de la tutelle.",
    "ordre_service.reference": "Référence de l'ordre de service.",
    "ordre_service.date": "Date de l'ordre de service.",
    "revision_prix.date": "Date d'application de la révision de prix.",
    "attestation_service_fait.date": "Date de l'attestation.",
    "facture.numero": "Numéro de la facture du fournisseur (contrôle de doublon, RG-16).",
    "avenant.numero": "Numéro de l'avenant, unique dans le contrat.",
    "commande_pharmacie.numero": "Numéro de la commande dans Hopitalia (`numBc`).",
    "commande_pharmacie.montant": "Total des lignes Hopitalia.",
    "commande_pharmacie.bon_commande_id": "Bon de commande créé au rattachement (vide : à rattacher).",
    "approvisionnement_pharmacie.reception_id": "Réception validée créée pour l'approvisionnement (vide : en attente).",
    "ligne_budgetaire.code": "Code de la ligne, unique dans le budget.",
    "piece_justificative.type_objet": "Type de l'objet qui porte la pièce.",
    "validation.motif": "Motif du visa défavorable ou du retour à corriger.",
}


def description(table: Table, colonne: Column[Any]) -> str | None:
    propre = DESCRIPTIONS.get(f"{table.name}.{colonne.name}")
    if propre:
        return propre
    if colonne.foreign_keys and colonne.name != "etablissement_id":
        cibles = sorted({cle.column.table.name for cle in colonne.foreign_keys})
        commune = DESCRIPTIONS.get(colonne.name)
        return commune or f"Référence vers `{'`, `'.join(cibles)}`."
    return DESCRIPTIONS.get(colonne.name)


def classes() -> dict[str, type]:
    return {
        c.__tablename__: c
        for c in vars(modeles).values()
        if inspect.isclass(c) and issubclass(c, Base) and hasattr(c, "__tablename__")
    }


def _premier_paragraphe(texte: str) -> str:
    return " ".join(inspect.cleandoc(texte).split("\n\n")[0].split())


def manquants() -> list[str]:
    par_table = classes()
    erreurs = [
        f"table {t}" for t in Base.metadata.tables if not (par_table[t].__doc__ or "").strip()
    ]
    for table in Base.metadata.tables.values():
        erreurs += [f"{table.name}.{c.name}" for c in table.columns if not description(table, c)]
    return erreurs


def dictionnaire() -> str:
    par_table = classes()
    tables = list(Base.metadata.tables.values())
    lignes = [
        "# Dictionnaire des données",
        "",
        "**Projet :** Hopitalia Budget · **Tâche :** T-280 · **Référence :** cahier des charges V3, "
        "sections 9 et 16",
        "",
        "Produit depuis le modèle (`backend/src/hopitalia_budget/adaptateurs/sortie/modeles.py`). "
        "Ne pas le modifier à la main : le régénérer depuis `backend/` par "
        "`python -m tests.test_dictionnaire`. Le test `test_dictionnaire.py` échoue si une table ou "
        "une colonne n'est pas décrite, ou si ce fichier n'est plus à jour.",
        "",
        "Conventions : montants en `Numeric(18,2)` (francs CFA) ; indicateurs (engagé, liquidé, "
        "payé, restes, disponibles) jamais stockés, toujours calculés (RG-14) ; toute modification "
        "de donnée financière est tracée dans `journal_audit`.",
        "",
        f"{len(tables)} tables, {sum(len(t.columns) for t in tables)} colonnes.",
        "",
        "## Tables",
        "",
    ]
    lignes += [f"- [`{t.name}`](#{t.name.replace('_', '-')})" for t in tables]
    for table in tables:
        # Tri par colonnes : l'ordre des contraintes d'une table n'est pas stable.
        uniques = sorted(
            ", ".join(f"`{c.name}`" for c in contrainte.columns)
            for contrainte in table.constraints
            if isinstance(contrainte, UniqueConstraint)
        )
        lignes += [
            "",
            f"## {table.name.replace('_', '-')}",
            "",
            f"Table `{table.name}`. {_premier_paragraphe(par_table[table.name].__doc__ or '')}",
            "",
        ]
        if uniques:
            lignes += [f"Unicité : {' ; '.join(uniques)}.", ""]
        lignes += ["| Colonne | Type | Obligatoire | Clé | Description |", "|---|---|---|---|---|"]
        for c in table.columns:
            cles = (["primaire"] if c.primary_key else []) + [
                f"→ `{cle.column.table.name}`" for cle in sorted(c.foreign_keys, key=str)
            ]
            if c.unique:
                cles.append("unique")
            obligatoire = "Non" if c.nullable and not c.primary_key else "Oui"
            texte = (description(table, c) or "").replace("|", "\\|")
            lignes.append(
                f"| `{c.name}` | {c.type.compile(dialect=DIALECTE)} | {obligatoire} | {', '.join(cles)} | {texte} |"
            )
    return "\n".join(lignes) + "\n"


def test_chaque_table_et_colonne_decrite() -> None:
    """Critère de T-280 : chaque table et chaque champ documentés."""
    assert manquants() == []


def test_dictionnaire_a_jour() -> None:
    assert DICTIONNAIRE.read_text(encoding="utf-8") == dictionnaire()


if __name__ == "__main__":
    DICTIONNAIRE.parent.mkdir(exist_ok=True)
    DICTIONNAIRE.write_text(dictionnaire(), encoding="utf-8", newline="\n")
    print(f"{DICTIONNAIRE} écrit.")
