# Dictionnaire des données

**Projet :** Hopitalia Budget · **Tâche :** T-280 · **Référence :** cahier des charges V3, sections 9 et 16

Produit depuis le modèle (`backend/src/hopitalia_budget/adaptateurs/sortie/modeles.py`). Ne pas le modifier à la main : le régénérer depuis `backend/` par `python -m tests.test_dictionnaire`. Le test `test_dictionnaire.py` échoue si une table ou une colonne n'est pas décrite, ou si ce fichier n'est plus à jour.

Conventions : montants en `Numeric(18,2)` (francs CFA) ; indicateurs (engagé, liquidé, payé, restes, disponibles) jamais stockés, toujours calculés (RG-14) ; toute modification de donnée financière est tracée dans `journal_audit`.

62 tables, 568 colonnes.

## Tables

- [`etablissement`](#etablissement)
- [`habilitation`](#habilitation)
- [`preference_utilisateur`](#preference-utilisateur)
- [`cle_idempotence`](#cle-idempotence)
- [`journal_audit`](#journal-audit)
- [`site`](#site)
- [`centre_responsabilite`](#centre-responsabilite)
- [`referentiel`](#referentiel)
- [`fournisseur`](#fournisseur)
- [`coordonnee_paiement`](#coordonnee-paiement)
- [`compte_comptable`](#compte-comptable)
- [`noeud_nomenclature`](#noeud-nomenclature)
- [`exercice`](#exercice)
- [`periode`](#periode)
- [`budget`](#budget)
- [`ligne_budgetaire`](#ligne-budgetaire)
- [`import_dotations`](#import-dotations)
- [`notification_credit`](#notification-credit)
- [`notification_ligne`](#notification-ligne)
- [`revision_budgetaire`](#revision-budgetaire)
- [`validation`](#validation)
- [`workflow_objet`](#workflow-objet)
- [`circuit_validation`](#circuit-validation)
- [`statut_personnalise`](#statut-personnalise)
- [`transition_statut`](#transition-statut)
- [`delegation`](#delegation)
- [`piece_justificative`](#piece-justificative)
- [`parametre_calcul`](#parametre-calcul)
- [`contrat`](#contrat)
- [`imputation_contrat`](#imputation-contrat)
- [`avenant`](#avenant)
- [`echeance_contrat`](#echeance-contrat)
- [`lot_tranche`](#lot-tranche)
- [`ordre_service`](#ordre-service)
- [`revision_prix`](#revision-prix)
- [`engagement`](#engagement)
- [`imputation_engagement`](#imputation-engagement)
- [`derogation`](#derogation)
- [`annulation`](#annulation)
- [`annulation_ligne`](#annulation-ligne)
- [`bon_commande`](#bon-commande)
- [`ligne_commande`](#ligne-commande)
- [`reception`](#reception)
- [`ligne_reception`](#ligne-reception)
- [`reserve_reception`](#reserve-reception)
- [`attestation_service_fait`](#attestation-service-fait)
- [`facture`](#facture)
- [`liquidation`](#liquidation)
- [`deduction`](#deduction)
- [`liquidation_reception`](#liquidation-reception)
- [`rapprochement`](#rapprochement)
- [`ordonnancement`](#ordonnancement)
- [`ligne_ordonnancement`](#ligne-ordonnancement)
- [`paiement`](#paiement)
- [`allocation_paiement`](#allocation-paiement)
- [`regle_alerte`](#regle-alerte)
- [`alerte`](#alerte)
- [`lecture_alerte`](#lecture-alerte)
- [`cloture_exercice`](#cloture-exercice)
- [`journal_integration`](#journal-integration)
- [`commande_pharmacie`](#commande-pharmacie)
- [`approvisionnement_pharmacie`](#approvisionnement-pharmacie)

## etablissement

Table `etablissement`. Établissement hospitalier : unité de cloisonnement des données (chaque requête est filtrée par établissement).

Unicité : `code`.

| Colonne | Type | Obligatoire | Clé | Description |
|---|---|---|---|---|
| `id` | UUID | Oui | primaire | Identifiant unique (UUID), exposé par l'API et partagé entre modules (INT-06). |
| `code` | VARCHAR(20) | Oui | unique | Code de l'élément, unique dans son périmètre. |
| `nom` | VARCHAR(200) | Oui |  | Nom de l'établissement. |
| `actif` | BOOLEAN | Oui |  | Faux : élément désactivé, conservé pour l'historique, plus proposé à la saisie. |
| `version` | INTEGER | Oui |  | Version de la ligne : verrou optimiste, comparée à l'en-tête `If-Match`. |

## habilitation

Table `habilitation`. Profil budgétaire d'un agent Hopitalia ; établissement absent : tous les établissements.

Unicité : `utilisateur_id`, `profil`, `etablissement_id`.

| Colonne | Type | Obligatoire | Clé | Description |
|---|---|---|---|---|
| `id` | UUID | Oui | primaire | Identifiant unique (UUID), exposé par l'API et partagé entre modules (INT-06). |
| `utilisateur_id` | BIGINT | Oui |  | Identifiant Hopitalia (`userId`) de l'agent. |
| `code_agent` | VARCHAR(20) | Oui |  | Code de l'agent habilité. |
| `nom_agent` | VARCHAR(200) | Oui |  | Nom de l'agent, lu dans Hopitalia à l'attribution du profil. |
| `profil` | VARCHAR(3) | Oui |  | Profil budgétaire (matrice des habilitations : ADM, RB, AF, GMC, SD, REC, VAL, ORD, CPT, AUD, LEC). |
| `etablissement_id` | UUID | Non | → `etablissement` | Établissement du profil (vide : tous les établissements). |

## preference-utilisateur

Table `preference_utilisateur`. Préférences d'un agent dans le module (langue de l'interface).

| Colonne | Type | Obligatoire | Clé | Description |
|---|---|---|---|---|
| `utilisateur_id` | BIGINT | Oui | primaire | Identifiant Hopitalia (`userId`) de l'agent. |
| `langue` | VARCHAR(5) | Oui |  | Langue de l'interface choisie par l'agent (`fr`, `en`). |

## cle-idempotence

Table `cle_idempotence`. Clé d'idempotence d'un `POST` financier et réponse rendue, conservée 24 heures (section 11.3).

| Colonne | Type | Obligatoire | Clé | Description |
|---|---|---|---|---|
| `utilisateur_id` | BIGINT | Oui | primaire | Identifiant Hopitalia (`userId`) de l'agent. |
| `cle` | VARCHAR(100) | Oui | primaire | Clé `Idempotency-Key` envoyée par le client. |
| `empreinte_requete` | VARCHAR(64) | Oui |  | Empreinte du corps de la requête : une clé réutilisée avec un autre corps est refusée. |
| `code_reponse` | INTEGER | Non |  | Code HTTP de la réponse rendue. |
| `reponse` | JSONB | Non |  | Réponse rendue (JSON), renvoyée telle quelle si la clé revient. |
| `expire_le` | TIMESTAMP WITH TIME ZONE | Oui |  | Fin de conservation de la clé. |

## journal-audit

Table `journal_audit`. Journal en ajout seul : des déclencheurs refusent toute modification et suppression.

| Colonne | Type | Obligatoire | Clé | Description |
|---|---|---|---|---|
| `id` | BIGINT | Oui | primaire | Rang de l'entrée, croissant : le journal est en ajout seul. |
| `horodatage` | TIMESTAMP WITH TIME ZONE | Oui |  | Date et heure de l'événement. |
| `utilisateur_id` | BIGINT | Non |  | Identifiant Hopitalia (`userId`) de l'agent. |
| `code_agent` | VARCHAR(20) | Non |  | Code de l'agent Hopitalia concerné. |
| `etablissement_id` | UUID | Non |  | Établissement de l'objet tracé (vide : opération globale). |
| `action` | VARCHAR(40) | Oui |  | Action réalisée (création, modification, validation, export…). |
| `type_objet` | VARCHAR(60) | Oui |  | Type de l'objet concerné (`Engagement`, `Facture`…). |
| `id_objet` | VARCHAR(64) | Oui |  | Identifiant de l'objet concerné. |
| `ancienne_valeur` | JSONB | Non |  | Valeur avant l'opération (JSON). |
| `nouvelle_valeur` | JSONB | Non |  | Valeur après l'opération (JSON). |
| `adresse_ip` | VARCHAR(45) | Non |  | Adresse IP de l'agent. |

## site

Table `site`. Site géographique d'un établissement.

Unicité : `etablissement_id`, `code`.

| Colonne | Type | Obligatoire | Clé | Description |
|---|---|---|---|---|
| `id` | UUID | Oui | primaire | Identifiant unique (UUID), exposé par l'API et partagé entre modules (INT-06). |
| `etablissement_id` | UUID | Oui | → `etablissement` | Établissement propriétaire : cloisonnement vérifié à chaque requête. |
| `code` | VARCHAR(20) | Oui |  | Code de l'élément, unique dans son périmètre. |
| `libelle` | VARCHAR(200) | Oui |  | Libellé affiché. |
| `adresse` | VARCHAR(300) | Non |  | Adresse postale. |
| `actif` | BOOLEAN | Oui |  | Faux : élément désactivé, conservé pour l'historique, plus proposé à la saisie. |
| `version` | INTEGER | Oui |  | Version de la ligne : verrou optimiste, comparée à l'en-tête `If-Match`. |

## centre-responsabilite

Table `centre_responsabilite`. Service hospitalier ou centre de responsabilité, hiérarchique, propre à un établissement.

Unicité : `etablissement_id`, `code_hopitalia` ; `etablissement_id`, `code`.

| Colonne | Type | Obligatoire | Clé | Description |
|---|---|---|---|---|
| `id` | UUID | Oui | primaire | Identifiant unique (UUID), exposé par l'API et partagé entre modules (INT-06). |
| `etablissement_id` | UUID | Oui | → `etablissement` | Établissement propriétaire : cloisonnement vérifié à chaque requête. |
| `code` | VARCHAR(20) | Oui |  | Code de l'élément, unique dans son périmètre. |
| `libelle` | VARCHAR(200) | Oui |  | Libellé affiché. |
| `type` | VARCHAR(30) | Oui |  | Type de centre : clinique, médico-technique, administratif, logistique, autre. |
| `parent_id` | UUID | Non | → `centre_responsabilite` | Référence vers `centre_responsabilite`. |
| `site_id` | UUID | Non | → `site` | Référence vers `site`. |
| `code_responsable` | VARCHAR(20) | Non |  | Code de l'agent responsable du centre. |
| `code_hopitalia` | VARCHAR(20) | Non |  | Code de l'élément dans Hopitalia ; vide pour un élément saisi dans le module. |
| `actif` | BOOLEAN | Oui |  | Faux : élément désactivé, conservé pour l'historique, plus proposé à la saisie. |
| `version` | INTEGER | Oui |  | Version de la ligne : verrou optimiste, comparée à l'en-tête `If-Match`. |

## referentiel

Table `referentiel`. Référentiels simples, partagés par tous les établissements (une colonne par attribut propre à un type : seuil, numéro, durée de conservation, bailleur, dates).

Unicité : `type`, `code`.

| Colonne | Type | Obligatoire | Clé | Description |
|---|---|---|---|---|
| `id` | UUID | Oui | primaire | Identifiant unique (UUID), exposé par l'API et partagé entre modules (INT-06). |
| `type` | VARCHAR(30) | Oui |  | Type de référentiel (source de financement, programme, mode de règlement, type de pièce…). |
| `code` | VARCHAR(20) | Oui |  | Code de l'élément, unique dans son périmètre. |
| `libelle` | VARCHAR(200) | Oui |  | Libellé affiché. |
| `actif` | BOOLEAN | Oui |  | Faux : élément désactivé, conservé pour l'historique, plus proposé à la saisie. |
| `version` | INTEGER | Oui |  | Version de la ligne : verrou optimiste, comparée à l'en-tête `If-Match`. |
| `seuil_hors_marche` | NUMERIC(18, 2) | Non |  | Type de dépense : montant au-delà duquel un achat hors marché est refusé. |
| `type_compte` | VARCHAR(20) | Non |  | Compte de trésorerie : `BANQUE`, `CAISSE` ou `TRESOR`. |
| `numero` | VARCHAR(50) | Non |  | Compte de trésorerie : numéro du compte. |
| `duree_conservation_ans` | INTEGER | Non |  | Type de pièce : durée de conservation en années. |
| `type_financement` | VARCHAR(30) | Non |  | Source de financement : type (budget de l'État, ressources propres, bailleur…). |
| `bailleur` | VARCHAR(200) | Non |  | Source de financement : bailleur. |
| `date_debut` | DATE | Non |  | Début de validité. |
| `date_fin` | DATE | Non |  | Fin de validité. |
| `types_objets` | JSONB | Non |  | Type de pièce : objets pour lesquels la pièce est obligatoire avant validation. |

## fournisseur

Table `fournisseur`. Fournisseur, commun à tous les établissements ; importé d'Hopitalia (code Hopitalia) ou saisi dans le module (EF-REF-05).

Unicité : `code_hopitalia` ; `code`.

| Colonne | Type | Obligatoire | Clé | Description |
|---|---|---|---|---|
| `id` | UUID | Oui | primaire | Identifiant unique (UUID), exposé par l'API et partagé entre modules (INT-06). |
| `code` | VARCHAR(20) | Oui | unique | Code de l'élément, unique dans son périmètre. |
| `raison_sociale` | VARCHAR(200) | Oui |  | Raison sociale du fournisseur. |
| `identifiants_administratifs` | VARCHAR(200) | Non |  | Identifiants administratifs (NINEA, registre du commerce). |
| `adresse` | VARCHAR(300) | Non |  | Adresse postale. |
| `contact` | VARCHAR(200) | Non |  | Contact (téléphone, courriel). |
| `code_hopitalia` | VARCHAR(20) | Non | unique | Code de l'élément dans Hopitalia ; vide pour un élément saisi dans le module. |
| `actif` | BOOLEAN | Oui |  | Faux : élément désactivé, conservé pour l'historique, plus proposé à la saisie. |
| `version` | INTEGER | Oui |  | Version de la ligne : verrou optimiste, comparée à l'en-tête `If-Match`. |

## coordonnee-paiement

Table `coordonnee_paiement`. Coordonnées bancaires d'un fournisseur pour un établissement ; numéro chiffré (ENF-03).

| Colonne | Type | Obligatoire | Clé | Description |
|---|---|---|---|---|
| `id` | UUID | Oui | primaire | Identifiant unique (UUID), exposé par l'API et partagé entre modules (INT-06). |
| `fournisseur_id` | UUID | Oui | → `fournisseur` | Référence vers `fournisseur`. |
| `etablissement_id` | UUID | Oui | → `etablissement` | Établissement propriétaire : cloisonnement vérifié à chaque requête. |
| `banque` | VARCHAR(200) | Oui |  | Banque du compte. |
| `numero_compte_chiffre` | TEXT | Oui |  | Numéro de compte chiffré (Fernet, clé hors base, ENF-03). |
| `fin_numero` | VARCHAR(4) | Oui |  | Quatre derniers chiffres du numéro de compte, affichés masqués. |
| `par_defaut` | BOOLEAN | Oui |  | Vrai : coordonnées proposées par défaut au paiement. |

## compte-comptable

Table `compte_comptable`. Compte du plan SYSCOHADA révisé, rattaché aux comptes budgétaires de la nomenclature.

| Colonne | Type | Obligatoire | Clé | Description |
|---|---|---|---|---|
| `code` | VARCHAR(10) | Oui | primaire | Code de l'élément, unique dans son périmètre. |
| `libelle` | VARCHAR(200) | Oui |  | Libellé affiché. |

## noeud-nomenclature

Table `noeud_nomenclature`. Nomenclature budgétaire : section, chapitre, article, paragraphe (= compte budgétaire).

Unicité : `code`.

| Colonne | Type | Obligatoire | Clé | Description |
|---|---|---|---|---|
| `id` | UUID | Oui | primaire | Identifiant unique (UUID), exposé par l'API et partagé entre modules (INT-06). |
| `niveau` | VARCHAR(10) | Oui |  | Niveau dans la nomenclature : section, chapitre, article, paragraphe. |
| `code` | VARCHAR(20) | Oui | unique | Code de l'élément, unique dans son périmètre. |
| `libelle` | VARCHAR(200) | Oui |  | Libellé affiché. |
| `parent_id` | UUID | Non | → `noeud_nomenclature` | Référence vers `noeud_nomenclature`. |
| `compte_comptable_code` | VARCHAR(10) | Non | → `compte_comptable` | Référence vers `compte_comptable`. |

## exercice

Table `exercice`. Exercice budgétaire (année), ouvert puis clos par établissement.

Unicité : `code`.

| Colonne | Type | Obligatoire | Clé | Description |
|---|---|---|---|---|
| `id` | UUID | Oui | primaire | Identifiant unique (UUID), exposé par l'API et partagé entre modules (INT-06). |
| `code` | VARCHAR(10) | Oui | unique | Code de l'élément, unique dans son périmètre. |
| `date_ouverture` | DATE | Oui |  | Premier jour de l'exercice. |
| `date_cloture` | DATE | Oui |  | Dernier jour de l'exercice. |
| `statut` | VARCHAR(10) | Oui |  | Statut dans le cycle de l'objet (cycle de référence : cahier des charges, 7). |
| `version` | INTEGER | Oui |  | Version de la ligne : verrou optimiste, comparée à l'en-tête `If-Match`. |

## periode

Table `periode`. Période d'un exercice (année, trimestre, mois), créée avec l'exercice, pour les filtres.

Unicité : `exercice_id`, `code`.

| Colonne | Type | Obligatoire | Clé | Description |
|---|---|---|---|---|
| `id` | UUID | Oui | primaire | Identifiant unique (UUID), exposé par l'API et partagé entre modules (INT-06). |
| `exercice_id` | UUID | Oui | → `exercice` | Référence vers `exercice`. |
| `type` | VARCHAR(15) | Oui |  | Type de période : annuelle, trimestrielle ou mensuelle. |
| `code` | VARCHAR(10) | Oui |  | Code de l'élément, unique dans son périmètre. |
| `date_debut` | DATE | Oui |  | Début de validité. |
| `date_fin` | DATE | Oui |  | Fin de validité. |

## budget

Table `budget`. Budget d'un établissement pour un exercice (primitif ou modificatif).

| Colonne | Type | Obligatoire | Clé | Description |
|---|---|---|---|---|
| `id` | UUID | Oui | primaire | Identifiant unique (UUID), exposé par l'API et partagé entre modules (INT-06). |
| `exercice_id` | UUID | Oui | → `exercice` | Référence vers `exercice`. |
| `etablissement_id` | UUID | Oui | → `etablissement` | Établissement propriétaire : cloisonnement vérifié à chaque requête. |
| `reference` | VARCHAR(50) | Oui |  | Référence du budget (`BP-2026`). |
| `type` | VARCHAR(12) | Oui |  | Type de budget : primitif ou modificatif. |
| `version` | INTEGER | Oui |  | Version de la ligne : verrou optimiste, comparée à l'en-tête `If-Match`. |

## ligne-budgetaire

Table `ligne_budgetaire`. Ligne budgétaire : seule la dotation initiale est saisie ; tout le reste est calculé.

Unicité : `budget_id`, `code`.

| Colonne | Type | Obligatoire | Clé | Description |
|---|---|---|---|---|
| `id` | UUID | Oui | primaire | Identifiant unique (UUID), exposé par l'API et partagé entre modules (INT-06). |
| `budget_id` | UUID | Oui | → `budget` | Référence vers `budget`. |
| `etablissement_id` | UUID | Oui | → `etablissement` | Établissement propriétaire : cloisonnement vérifié à chaque requête. |
| `code` | VARCHAR(30) | Oui |  | Code de la ligne, unique dans le budget. |
| `libelle` | VARCHAR(200) | Oui |  | Libellé affiché. |
| `compte_budgetaire_id` | UUID | Oui | → `noeud_nomenclature` | Référence vers `noeud_nomenclature`. |
| `centre_id` | UUID | Oui | → `centre_responsabilite` | Référence vers `centre_responsabilite`. |
| `source_id` | UUID | Oui | → `referentiel` | Référence vers `referentiel`. |
| `programme_id` | UUID | Non | → `referentiel` | Référence vers `referentiel`. |
| `periode_id` | UUID | Non | → `periode` | Référence vers `periode`. |
| `nature_economique` | VARCHAR(100) | Non |  | Nature économique de la ligne (fonctionnement, investissement…). |
| `dotation_initiale` | NUMERIC(18, 2) | Oui |  | Dotation initiale de la ligne (budget primitif). |
| `version` | INTEGER | Oui |  | Version de la ligne : verrou optimiste, comparée à l'en-tête `If-Match`. |

## import-dotations

Table `import_dotations`. Import asynchrone des dotations d'un budget depuis un fichier CSV, avec son rapport d'anomalies (EF-BUD-02).

| Colonne | Type | Obligatoire | Clé | Description |
|---|---|---|---|---|
| `id` | UUID | Oui | primaire | Identifiant unique (UUID), exposé par l'API et partagé entre modules (INT-06). |
| `budget_id` | UUID | Oui | → `budget` | Référence vers `budget`. |
| `etablissement_id` | UUID | Oui | → `etablissement` | Établissement propriétaire : cloisonnement vérifié à chaque requête. |
| `statut` | VARCHAR(10) | Oui |  | Statut dans le cycle de l'objet (cycle de référence : cahier des charges, 7). |
| `lignes_importees` | INTEGER | Oui |  | Nombre de lignes créées par l'import. |
| `anomalies` | JSONB | Oui |  | Rapport d'anomalies de l'import, ligne par ligne (JSON). |
| `contenu` | TEXT | Oui |  | Contenu CSV importé. |
| `cree_par_id` | BIGINT | Oui |  | Identifiant Hopitalia (`userId`) de l'agent créateur. |
| `cree_par_code` | VARCHAR(20) | Oui |  | Code de l'agent créateur. |
| `cree_le` | TIMESTAMP WITH TIME ZONE | Oui |  | Date et heure de création. |
| `termine_le` | TIMESTAMP WITH TIME ZONE | Non |  | Date et heure de fin du traitement. |

## notification-credit

Table `notification_credit`. Notification de crédits reçue de la tutelle pour un budget (T-091).

| Colonne | Type | Obligatoire | Clé | Description |
|---|---|---|---|---|
| `id` | UUID | Oui | primaire | Identifiant unique (UUID), exposé par l'API et partagé entre modules (INT-06). |
| `budget_id` | UUID | Oui | → `budget` | Référence vers `budget`. |
| `etablissement_id` | UUID | Oui | → `etablissement` | Établissement propriétaire : cloisonnement vérifié à chaque requête. |
| `reference` | VARCHAR(50) | Oui |  | Référence de la notification de la tutelle. |
| `date_notification` | DATE | Oui |  | Date de notification. |
| `montant` | NUMERIC(18, 2) | Oui |  | Montant en francs CFA, `Numeric(18,2)`. |
| `objet` | VARCHAR(300) | Oui |  | Objet de la pièce. |
| `source_id` | UUID | Oui | → `referentiel` | Référence vers `referentiel`. |

## notification-ligne

Table `notification_ligne`. Montant notifié pour une ligne budgétaire dans une notification de crédits.

| Colonne | Type | Obligatoire | Clé | Description |
|---|---|---|---|---|
| `notification_id` | UUID | Oui | primaire, → `notification_credit` | Référence vers `notification_credit`. |
| `ligne_id` | UUID | Oui | primaire, → `ligne_budgetaire` | Référence vers `ligne_budgetaire`. |
| `montant` | NUMERIC(18, 2) | Oui |  | Montant en francs CFA, `Numeric(18,2)`. |

## revision-budgetaire

Table `revision_budgetaire`. Révision budgétaire : sans effet tant qu'elle n'est pas validée (EF-BUD-04).

| Colonne | Type | Obligatoire | Clé | Description |
|---|---|---|---|---|
| `id` | UUID | Oui | primaire | Identifiant unique (UUID), exposé par l'API et partagé entre modules (INT-06). |
| `budget_id` | UUID | Oui | → `budget` | Référence vers `budget`. |
| `etablissement_id` | UUID | Oui | → `etablissement` | Établissement propriétaire : cloisonnement vérifié à chaque requête. |
| `type` | VARCHAR(20) | Oui |  | Budget modificatif, virement, réallocation, augmentation ou diminution. |
| `sens` | VARCHAR(12) | Non |  | Sens de la révision : augmentation ou diminution. |
| `ligne_source_id` | UUID | Non | → `ligne_budgetaire` | Référence vers `ligne_budgetaire`. |
| `ligne_cible_id` | UUID | Oui | → `ligne_budgetaire` | Référence vers `ligne_budgetaire`. |
| `montant` | NUMERIC(18, 2) | Oui |  | Montant en francs CFA, `Numeric(18,2)`. |
| `motif` | VARCHAR(500) | Oui |  | Motif saisi, obligatoire pour l'opération. |
| `statut` | VARCHAR(20) | Oui |  | Statut dans le cycle de l'objet (cycle de référence : cahier des charges, 7). |
| `cree_par_id` | BIGINT | Oui |  | Identifiant Hopitalia (`userId`) de l'agent créateur. |
| `cree_par_code` | VARCHAR(20) | Oui |  | Code de l'agent créateur. |
| `cree_le` | TIMESTAMP WITH TIME ZONE | Oui |  | Date et heure de création. |
| `version` | INTEGER | Oui |  | Version de la ligne : verrou optimiste, comparée à l'en-tête `If-Match`. |

## validation

Table `validation`. Visa ou rejet d'une étape de validation, conservé à vie (historique des validations).

| Colonne | Type | Obligatoire | Clé | Description |
|---|---|---|---|---|
| `id` | UUID | Oui | primaire | Identifiant unique (UUID), exposé par l'API et partagé entre modules (INT-06). |
| `type_objet` | VARCHAR(60) | Oui |  | Type de l'objet concerné (`Engagement`, `Facture`…). |
| `id_objet` | UUID | Oui |  | Identifiant de l'objet concerné. |
| `etape` | VARCHAR(10) | Oui |  | Profil de l'étape visée (vide pour une soumission). |
| `decision` | VARCHAR(10) | Oui |  | Soumission, visa d'étape, validation finale, rejet ou retour à corriger. |
| `motif` | VARCHAR(500) | Non |  | Motif du visa défavorable ou du retour à corriger. |
| `utilisateur_id` | BIGINT | Oui |  | Identifiant Hopitalia (`userId`) de l'agent. |
| `code_agent` | VARCHAR(20) | Oui |  | Code de l'agent Hopitalia concerné. |
| `horodatage` | TIMESTAMP WITH TIME ZONE | Oui |  | Date et heure de l'événement. |
| `rang` | BIGINT | Oui |  | Rang de la ligne. |
| `ordre` | INTEGER | Non |  | Rang de l'étape dans le circuit. |
| `visa` | VARCHAR(200) | Non |  | Mention de visa saisie par le valideur. |
| `delegant_code` | VARCHAR(20) | Non |  | Code de l'agent qui délègue. |

## workflow-objet

Table `workflow_objet`. État de workflow d'un objet validable : circuit figé à la soumission, statut personnalisé.

| Colonne | Type | Obligatoire | Clé | Description |
|---|---|---|---|---|
| `type_objet` | VARCHAR(60) | Oui | primaire | Type de l'objet concerné (`Engagement`, `Facture`…). |
| `id_objet` | UUID | Oui | primaire | Identifiant de l'objet concerné. |
| `statut` | VARCHAR(30) | Oui |  | Statut dans le cycle de l'objet (cycle de référence : cahier des charges, 7). |
| `circuit` | JSONB | Oui |  | Circuit de validation figé à la soumission (JSON). |

## circuit-validation

Table `circuit_validation`. Circuit de validation d'un type d'objet, par établissement, service et tranche de montant.

| Colonne | Type | Obligatoire | Clé | Description |
|---|---|---|---|---|
| `id` | UUID | Oui | primaire | Identifiant unique (UUID), exposé par l'API et partagé entre modules (INT-06). |
| `etablissement_id` | UUID | Oui | → `etablissement` | Établissement propriétaire : cloisonnement vérifié à chaque requête. |
| `type_objet` | VARCHAR(60) | Oui |  | Type de l'objet concerné (`Engagement`, `Facture`…). |
| `libelle` | VARCHAR(200) | Oui |  | Libellé affiché. |
| `centre_id` | UUID | Non | → `centre_responsabilite` | Référence vers `centre_responsabilite`. |
| `seuil_min` | NUMERIC(18, 2) | Oui |  | Montant à partir duquel le circuit s'applique. |
| `seuil_max` | NUMERIC(18, 2) | Non |  | Montant jusqu'auquel le circuit s'applique (vide : sans limite). |
| `separation_taches` | BOOLEAN | Oui |  | Vrai : l'auteur d'une pièce ne peut pas la viser. |
| `actif` | BOOLEAN | Oui |  | Faux : élément désactivé, conservé pour l'historique, plus proposé à la saisie. |
| `etapes` | JSONB | Oui |  | Étapes du circuit : profils valideurs dans l'ordre (JSON). |
| `version` | INTEGER | Oui |  | Version de la ligne : verrou optimiste, comparée à l'en-tête `If-Match`. |

## statut-personnalise

Table `statut_personnalise`. Statut propre à un établissement, rattaché à un statut de référence du cycle de validation.

Unicité : `etablissement_id`, `type_objet`, `code`.

| Colonne | Type | Obligatoire | Clé | Description |
|---|---|---|---|---|
| `id` | UUID | Oui | primaire | Identifiant unique (UUID), exposé par l'API et partagé entre modules (INT-06). |
| `etablissement_id` | UUID | Oui | → `etablissement` | Établissement propriétaire : cloisonnement vérifié à chaque requête. |
| `type_objet` | VARCHAR(60) | Oui |  | Type de l'objet concerné (`Engagement`, `Facture`…). |
| `code` | VARCHAR(30) | Oui |  | Code de l'élément, unique dans son périmètre. |
| `libelle` | VARCHAR(200) | Oui |  | Libellé affiché. |
| `statut_reference` | VARCHAR(30) | Oui |  | Statut du cycle de référence auquel le statut personnalisé correspond. |
| `version` | INTEGER | Oui |  | Version de la ligne : verrou optimiste, comparée à l'en-tête `If-Match`. |

## transition-statut

Table `transition_statut`. Transition autorisée entre deux statuts pour un type d'objet, et profil qui peut la faire.

Unicité : `etablissement_id`, `type_objet`, `depuis`, `action`.

| Colonne | Type | Obligatoire | Clé | Description |
|---|---|---|---|---|
| `id` | UUID | Oui | primaire | Identifiant unique (UUID), exposé par l'API et partagé entre modules (INT-06). |
| `etablissement_id` | UUID | Oui | → `etablissement` | Établissement propriétaire : cloisonnement vérifié à chaque requête. |
| `type_objet` | VARCHAR(60) | Oui |  | Type de l'objet concerné (`Engagement`, `Facture`…). |
| `depuis` | VARCHAR(30) | Oui |  | Statut de départ de la transition. |
| `action` | VARCHAR(20) | Oui |  | Action qui fait passer de `depuis` à `vers`. |
| `vers` | VARCHAR(30) | Oui |  | Statut d'arrivée de la transition. |
| `profil` | VARCHAR(10) | Non |  | Profil qui peut faire la transition. |
| `version` | INTEGER | Oui |  | Version de la ligne : verrou optimiste, comparée à l'en-tête `If-Match`. |

## delegation

Table `delegation`. Délégation temporaire : le délégataire vise avec les profils du délégant, dans ses dates.

| Colonne | Type | Obligatoire | Clé | Description |
|---|---|---|---|---|
| `id` | UUID | Oui | primaire | Identifiant unique (UUID), exposé par l'API et partagé entre modules (INT-06). |
| `delegant_id` | BIGINT | Oui |  | Identifiant Hopitalia de l'agent qui délègue. |
| `delegant_code` | VARCHAR(20) | Oui |  | Code de l'agent qui délègue. |
| `delegataire_id` | BIGINT | Oui |  | Identifiant Hopitalia de l'agent qui reçoit la délégation. |
| `delegataire_code` | VARCHAR(20) | Oui |  | Code de l'agent qui reçoit la délégation. |
| `date_debut` | DATE | Oui |  | Début de validité. |
| `date_fin` | DATE | Oui |  | Fin de validité. |
| `motif` | VARCHAR(500) | Oui |  | Motif saisi, obligatoire pour l'opération. |
| `cree_le` | TIMESTAMP WITH TIME ZONE | Oui |  | Date et heure de création. |
| `version` | INTEGER | Oui |  | Version de la ligne : verrou optimiste, comparée à l'en-tête `If-Match`. |

## piece-justificative

Table `piece_justificative`. Pièce jointe à une opération (EF-DOC-01) ; contenu rangé par empreinte SHA-256.

| Colonne | Type | Obligatoire | Clé | Description |
|---|---|---|---|---|
| `id` | UUID | Oui | primaire | Identifiant unique (UUID), exposé par l'API et partagé entre modules (INT-06). |
| `type_objet` | VARCHAR(60) | Oui |  | Type de l'objet qui porte la pièce. |
| `id_objet` | UUID | Oui |  | Identifiant de l'objet concerné. |
| `etablissement_id` | UUID | Oui | → `etablissement` | Établissement propriétaire : cloisonnement vérifié à chaque requête. |
| `type_piece_id` | UUID | Oui | → `referentiel` | Référence vers `referentiel`. |
| `nom_fichier` | VARCHAR(255) | Oui |  | Nom du fichier déposé. |
| `type_mime` | VARCHAR(100) | Oui |  | Type du fichier (liste fermée). |
| `taille` | BIGINT | Oui |  | Taille du fichier en octets. |
| `empreinte_sha256` | VARCHAR(64) | Oui |  | Empreinte SHA-256 du contenu : le fichier est rangé et vérifié par elle. |
| `depose_par_id` | BIGINT | Oui |  | Identifiant Hopitalia de l'agent qui dépose. |
| `depose_par_code` | VARCHAR(20) | Oui |  | Code de l'agent qui dépose. |
| `depose_le` | TIMESTAMP WITH TIME ZONE | Oui |  | Date et heure du dépôt. |

## parametre-calcul

Table `parametre_calcul`. Option de calcul de la section 6 choisie par un établissement (sinon valeur par défaut).

| Colonne | Type | Obligatoire | Clé | Description |
|---|---|---|---|---|
| `etablissement_id` | UUID | Oui | primaire, → `etablissement` | Établissement propriétaire : cloisonnement vérifié à chaque requête. |
| `code` | VARCHAR(50) | Oui | primaire | Code de l'élément, unique dans son périmètre. |
| `valeur` | VARCHAR(50) | Oui |  | Valeur du paramètre de calcul. |

## contrat

Table `contrat`. Contrat signé ou marché attribué (type MARCHE : nature et lot en plus), section 7.3.

Unicité : `etablissement_id`, `numero`.

| Colonne | Type | Obligatoire | Clé | Description |
|---|---|---|---|---|
| `id` | UUID | Oui | primaire | Identifiant unique (UUID), exposé par l'API et partagé entre modules (INT-06). |
| `etablissement_id` | UUID | Oui | → `etablissement` | Établissement propriétaire : cloisonnement vérifié à chaque requête. |
| `numero` | VARCHAR(50) | Oui |  | Numéro du contrat attribué. |
| `intitule` | VARCHAR(300) | Oui |  | Intitulé du contrat. |
| `type` | VARCHAR(20) | Oui |  | Marché, convention, maintenance, prestation ou autre. |
| `nature` | VARCHAR(30) | Non |  | Marché : fournitures, travaux, services ou prestations intellectuelles. |
| `numero_lot` | VARCHAR(30) | Non |  | Numéro du lot du marché. |
| `fournisseur_id` | UUID | Oui | → `fournisseur` | Référence vers `fournisseur`. |
| `objet` | TEXT | Non |  | Objet du contrat. |
| `perimetre` | TEXT | Non |  | Périmètre des prestations. |
| `reference_dossier` | VARCHAR(100) | Non |  | Référence du dossier de passation (marché déjà attribué). |
| `date_notification` | DATE | Non |  | Date de notification. |
| `date_signature` | DATE | Non |  | Date de signature. |
| `date_demarrage` | DATE | Non |  | Date de démarrage des prestations. |
| `duree_mois` | INTEGER | Non |  | Durée en mois. |
| `date_echeance` | DATE | Non |  | Date d'échéance. |
| `devise` | VARCHAR(3) | Oui |  | Devise du contrat. |
| `montant_initial_ht` | NUMERIC(18, 2) | Oui |  | Montant initial hors taxes. |
| `taux_taxe` | NUMERIC(18, 2) | Oui |  | Taux de taxe en pourcentage. |
| `montant_initial_ttc` | NUMERIC(18, 2) | Oui |  | Montant initial toutes taxes comprises. |
| `periodicite` | VARCHAR(20) | Non |  | Périodicité de facturation. |
| `modalite_facturation` | VARCHAR(500) | Non |  | Modalité de facturation. |
| `site_id` | UUID | Non | → `site` | Référence vers `site`. |
| `centre_id` | UUID | Oui | → `centre_responsabilite` | Référence vers `centre_responsabilite`. |
| `source_id` | UUID | Oui | → `referentiel` | Référence vers `referentiel`. |
| `famille_achat_id` | UUID | Non | → `referentiel` | Référence vers `referentiel`. |
| `responsable_code` | VARCHAR(20) | Non |  | Code de l'agent responsable du suivi. |
| `taux_avance` | NUMERIC(18, 2) | Non |  | Taux de l'avance de démarrage en pourcentage. |
| `mode_recuperation_avance` | VARCHAR(300) | Non |  | Mode de récupération de l'avance sur les décomptes. |
| `taux_retenue_garantie` | NUMERIC(18, 2) | Non |  | Taux de la retenue de garantie en pourcentage. |
| `condition_liberation_retenue` | VARCHAR(300) | Non |  | Condition de libération de la retenue de garantie. |
| `date_liberation_retenue` | DATE | Non |  | Date de libération de la retenue de garantie. |
| `statut` | VARCHAR(20) | Oui |  | Statut dans le cycle de l'objet (cycle de référence : cahier des charges, 7). |
| `cree_par_id` | BIGINT | Oui |  | Identifiant Hopitalia (`userId`) de l'agent créateur. |
| `cree_par_code` | VARCHAR(20) | Oui |  | Code de l'agent créateur. |
| `cree_le` | TIMESTAMP WITH TIME ZONE | Oui |  | Date et heure de création. |
| `version` | INTEGER | Oui |  | Version de la ligne : verrou optimiste, comparée à l'en-tête `If-Match`. |

## imputation-contrat

Table `imputation_contrat`. Ventilation du contrat sur une ligne budgétaire (RG-15).

Unicité : `contrat_id`, `ligne_id`.

| Colonne | Type | Obligatoire | Clé | Description |
|---|---|---|---|---|
| `id` | UUID | Oui | primaire | Identifiant unique (UUID), exposé par l'API et partagé entre modules (INT-06). |
| `contrat_id` | UUID | Oui | → `contrat` | Référence vers `contrat`. |
| `ligne_id` | UUID | Oui | → `ligne_budgetaire` | Référence vers `ligne_budgetaire`. |
| `montant` | NUMERIC(18, 2) | Oui |  | Montant en francs CFA, `Numeric(18,2)`. |

## avenant

Table `avenant`. Avenant : n'a d'effet sur le plafond qu'une fois validé (RG-11). Montant avant et nouveau plafond sont relevés au moment de la validation, pour l'historique.

Unicité : `contrat_id`, `numero`.

| Colonne | Type | Obligatoire | Clé | Description |
|---|---|---|---|---|
| `id` | UUID | Oui | primaire | Identifiant unique (UUID), exposé par l'API et partagé entre modules (INT-06). |
| `contrat_id` | UUID | Oui | → `contrat` | Référence vers `contrat`. |
| `etablissement_id` | UUID | Oui | → `etablissement` | Établissement propriétaire : cloisonnement vérifié à chaque requête. |
| `numero` | INTEGER | Oui |  | Numéro de l'avenant, unique dans le contrat. |
| `objet` | VARCHAR(500) | Oui |  | Objet de la pièce. |
| `variation` | NUMERIC(18, 2) | Oui |  | Variation du montant apportée par l'avenant (positive ou négative). |
| `date_effet` | DATE | Oui |  | Date d'effet de l'avenant. |
| `montant_avant` | NUMERIC(18, 2) | Non |  | Montant actualisé du contrat avant l'avenant. |
| `nouveau_plafond` | NUMERIC(18, 2) | Non |  | Montant actualisé après l'avenant. |
| `statut` | VARCHAR(20) | Oui |  | Statut dans le cycle de l'objet (cycle de référence : cahier des charges, 7). |
| `cree_par_id` | BIGINT | Oui |  | Identifiant Hopitalia (`userId`) de l'agent créateur. |
| `cree_par_code` | VARCHAR(20) | Oui |  | Code de l'agent créateur. |
| `cree_le` | TIMESTAMP WITH TIME ZONE | Oui |  | Date et heure de création. |
| `version` | INTEGER | Oui |  | Version de la ligne : verrou optimiste, comparée à l'en-tête `If-Match`. |

## echeance-contrat

Table `echeance_contrat`. Échéance prévue d'un contrat (date et montant), pour le suivi des échéances.

| Colonne | Type | Obligatoire | Clé | Description |
|---|---|---|---|---|
| `id` | UUID | Oui | primaire | Identifiant unique (UUID), exposé par l'API et partagé entre modules (INT-06). |
| `contrat_id` | UUID | Oui | → `contrat` | Référence vers `contrat`. |
| `libelle` | VARCHAR(200) | Oui |  | Libellé affiché. |
| `date_echeance` | DATE | Oui |  | Date d'échéance. |
| `montant_prevu` | NUMERIC(18, 2) | Oui |  | Montant prévu à l'échéance. |

## lot-tranche

Table `lot_tranche`. Lot ou tranche d'un contrat, avec son montant.

Unicité : `contrat_id`, `code`.

| Colonne | Type | Obligatoire | Clé | Description |
|---|---|---|---|---|
| `id` | UUID | Oui | primaire | Identifiant unique (UUID), exposé par l'API et partagé entre modules (INT-06). |
| `contrat_id` | UUID | Oui | → `contrat` | Référence vers `contrat`. |
| `code` | VARCHAR(30) | Oui |  | Code de l'élément, unique dans son périmètre. |
| `libelle` | VARCHAR(200) | Oui |  | Libellé affiché. |
| `montant` | NUMERIC(18, 2) | Oui |  | Montant en francs CFA, `Numeric(18,2)`. |

## ordre-service

Table `ordre_service`. Ordre de service d'un contrat (démarrage, arrêt, reprise, modification des prestations).

Unicité : `contrat_id`, `reference`.

| Colonne | Type | Obligatoire | Clé | Description |
|---|---|---|---|---|
| `id` | UUID | Oui | primaire | Identifiant unique (UUID), exposé par l'API et partagé entre modules (INT-06). |
| `contrat_id` | UUID | Oui | → `contrat` | Référence vers `contrat`. |
| `reference` | VARCHAR(50) | Oui |  | Référence de l'ordre de service. |
| `type` | VARCHAR(20) | Oui |  | Type d'ordre de service : démarrage, arrêt, reprise, modification, autre. |
| `date` | DATE | Oui |  | Date de l'ordre de service. |
| `objet` | VARCHAR(500) | Non |  | Objet de la pièce. |

## revision-prix

Table `revision_prix`. Révision de prix : formule, indice, incidence (hors montant actualisé, section 6.2).

| Colonne | Type | Obligatoire | Clé | Description |
|---|---|---|---|---|
| `id` | UUID | Oui | primaire | Identifiant unique (UUID), exposé par l'API et partagé entre modules (INT-06). |
| `contrat_id` | UUID | Oui | → `contrat` | Référence vers `contrat`. |
| `formule` | VARCHAR(300) | Oui |  | Formule de révision de prix. |
| `indice` | VARCHAR(100) | Non |  | Valeur de l'indice appliqué. |
| `date` | DATE | Oui |  | Date d'application de la révision de prix. |
| `incidence` | NUMERIC(18, 2) | Oui |  | Incidence financière de la révision de prix. |

## engagement

Table `engagement`. Engagement (section 7.4) ; une dépense hors marché en est un, d'origine HORS_MARCHE.

Unicité : `etablissement_id`, `numero`.

| Colonne | Type | Obligatoire | Clé | Description |
|---|---|---|---|---|
| `id` | UUID | Oui | primaire | Identifiant unique (UUID), exposé par l'API et partagé entre modules (INT-06). |
| `etablissement_id` | UUID | Oui | → `etablissement` | Établissement propriétaire : cloisonnement vérifié à chaque requête. |
| `exercice_id` | UUID | Oui | → `exercice` | Référence vers `exercice`. |
| `numero` | VARCHAR(30) | Oui |  | Numéro de pièce, unique par établissement (`PREFIXE-ANNEE-RANG`). |
| `date_engagement` | DATE | Oui |  | Date de l'engagement. |
| `objet` | VARCHAR(500) | Oui |  | Objet de la pièce. |
| `origine` | VARCHAR(20) | Oui |  | Origine : contrat, décision autorisée, hors marché, mission ou petit achat. |
| `montant` | NUMERIC(18, 2) | Oui |  | Montant en francs CFA, `Numeric(18,2)`. |
| `contrat_id` | UUID | Non | → `contrat` | Référence vers `contrat`. |
| `fournisseur_id` | UUID | Non | → `fournisseur` | Référence vers `fournisseur`. |
| `centre_id` | UUID | Oui | → `centre_responsabilite` | Référence vers `centre_responsabilite`. |
| `type_depense_id` | UUID | Non | → `referentiel` | Référence vers `referentiel`. |
| `engagement_origine_id` | UUID | Non | → `engagement` | Référence vers `engagement`. |
| `nature_hors_marche` | VARCHAR(30) | Non |  | Nature d'un achat hors marché. |
| `justification` | VARCHAR(1000) | Non |  | Justification d'un achat hors marché. |
| `reference_decision` | VARCHAR(100) | Non |  | Référence de la décision qui autorise la dépense. |
| `statut` | VARCHAR(30) | Oui |  | Statut dans le cycle de l'objet (cycle de référence : cahier des charges, 7). |
| `date_validation` | TIMESTAMP WITH TIME ZONE | Non |  | Date et heure de la validation finale. |
| `cree_par_id` | BIGINT | Oui |  | Identifiant Hopitalia (`userId`) de l'agent créateur. |
| `cree_par_code` | VARCHAR(20) | Oui |  | Code de l'agent créateur. |
| `cree_le` | TIMESTAMP WITH TIME ZONE | Oui |  | Date et heure de création. |
| `version` | INTEGER | Oui |  | Version de la ligne : verrou optimiste, comparée à l'en-tête `If-Match`. |

## imputation-engagement

Table `imputation_engagement`. Part d'un engagement imputée sur une ligne budgétaire ; la somme des imputations égale le montant de l'engagement (RG-15).

Unicité : `engagement_id`, `ligne_id`.

| Colonne | Type | Obligatoire | Clé | Description |
|---|---|---|---|---|
| `id` | UUID | Oui | primaire | Identifiant unique (UUID), exposé par l'API et partagé entre modules (INT-06). |
| `engagement_id` | UUID | Oui | → `engagement` | Référence vers `engagement`. |
| `ligne_id` | UUID | Oui | → `ligne_budgetaire` | Référence vers `ligne_budgetaire`. |
| `montant` | NUMERIC(18, 2) | Oui |  | Montant en francs CFA, `Numeric(18,2)`. |

## derogation

Table `derogation`. Dérogation (RG-19) : couvre un dépassement d'une nature, sur un objet, jusqu'à un montant.

| Colonne | Type | Obligatoire | Clé | Description |
|---|---|---|---|---|
| `id` | UUID | Oui | primaire | Identifiant unique (UUID), exposé par l'API et partagé entre modules (INT-06). |
| `type_objet` | VARCHAR(60) | Oui |  | Type de l'objet concerné (`Engagement`, `Facture`…). |
| `id_objet` | UUID | Oui |  | Identifiant de l'objet concerné. |
| `etablissement_id` | UUID | Oui | → `etablissement` | Établissement propriétaire : cloisonnement vérifié à chaque requête. |
| `nature` | VARCHAR(30) | Oui |  | Dépassement autorisé (RG-19) : crédit, plafond du contrat, seuil hors marché, liquidation au-delà du dû, paiement au-delà du solde, doublon. |
| `montant_depassement` | NUMERIC(18, 2) | Oui |  | Dépassement autorisé par la dérogation (RG-19). |
| `motif` | VARCHAR(500) | Oui |  | Motif saisi, obligatoire pour l'opération. |
| `statut` | VARCHAR(20) | Oui |  | Statut dans le cycle de l'objet (cycle de référence : cahier des charges, 7). |
| `cree_par_id` | BIGINT | Oui |  | Identifiant Hopitalia (`userId`) de l'agent créateur. |
| `cree_par_code` | VARCHAR(20) | Oui |  | Code de l'agent créateur. |
| `cree_le` | TIMESTAMP WITH TIME ZONE | Oui |  | Date et heure de création. |
| `version` | INTEGER | Oui |  | Version de la ligne : verrou optimiste, comparée à l'en-tête `If-Match`. |

## annulation

Table `annulation`. Annulation (totale ou partielle) ou clôture d'une opération validée (RG-09, RG-18) : l'opération initiale reste intacte ; l'annulation est une contre-opération tracée.

| Colonne | Type | Obligatoire | Clé | Description |
|---|---|---|---|---|
| `id` | UUID | Oui | primaire | Identifiant unique (UUID), exposé par l'API et partagé entre modules (INT-06). |
| `type_objet` | VARCHAR(60) | Oui |  | Type de l'objet concerné (`Engagement`, `Facture`…). |
| `id_objet` | UUID | Oui |  | Identifiant de l'objet concerné. |
| `etablissement_id` | UUID | Oui | → `etablissement` | Établissement propriétaire : cloisonnement vérifié à chaque requête. |
| `type` | VARCHAR(20) | Oui |  | Annulation, clôture (reliquat libéré) ou report sur l'exercice suivant. |
| `montant` | NUMERIC(18, 2) | Oui |  | Montant en francs CFA, `Numeric(18,2)`. |
| `motif` | VARCHAR(500) | Oui |  | Motif saisi, obligatoire pour l'opération. |
| `utilisateur_id` | BIGINT | Oui |  | Identifiant Hopitalia (`userId`) de l'agent. |
| `code_agent` | VARCHAR(20) | Oui |  | Code de l'agent Hopitalia concerné. |
| `horodatage` | TIMESTAMP WITH TIME ZONE | Oui |  | Date et heure de l'événement. |

## annulation-ligne

Table `annulation_ligne`. Part d'une annulation d'engagement imputée sur une ligne budgétaire.

| Colonne | Type | Obligatoire | Clé | Description |
|---|---|---|---|---|
| `id` | UUID | Oui | primaire | Identifiant unique (UUID), exposé par l'API et partagé entre modules (INT-06). |
| `annulation_id` | UUID | Oui | → `annulation` | Référence vers `annulation`. |
| `imputation_id` | UUID | Oui | → `imputation_engagement` | Référence vers `imputation_engagement`. |
| `montant` | NUMERIC(18, 2) | Oui |  | Montant en francs CFA, `Numeric(18,2)`. |

## bon-commande

Table `bon_commande`. Bon de commande, tranche ou ordre de service : toujours rattaché à un engagement validé.

Unicité : `etablissement_id`, `numero`.

| Colonne | Type | Obligatoire | Clé | Description |
|---|---|---|---|---|
| `id` | UUID | Oui | primaire | Identifiant unique (UUID), exposé par l'API et partagé entre modules (INT-06). |
| `etablissement_id` | UUID | Oui | → `etablissement` | Établissement propriétaire : cloisonnement vérifié à chaque requête. |
| `engagement_id` | UUID | Oui | → `engagement` | Référence vers `engagement`. |
| `fournisseur_id` | UUID | Non | → `fournisseur` | Référence vers `fournisseur`. |
| `numero` | VARCHAR(30) | Oui |  | Numéro de pièce, unique par établissement (`PREFIXE-ANNEE-RANG`). |
| `type` | VARCHAR(20) | Oui |  | Bon de commande, tranche ou ordre de service. |
| `date_emission` | DATE | Oui |  | Date d'émission de la pièce. |
| `lieu_livraison` | VARCHAR(300) | Non |  | Lieu de livraison (service destinataire pour une commande de la pharmacie). |
| `date_livraison_prevue` | DATE | Non |  | Date de livraison prévue ; dépassée, la commande est en retard (EF-REC-06). |
| `cree_par_id` | BIGINT | Oui |  | Identifiant Hopitalia (`userId`) de l'agent créateur. |
| `cree_par_code` | VARCHAR(20) | Oui |  | Code de l'agent créateur. |
| `cree_le` | TIMESTAMP WITH TIME ZONE | Oui |  | Date et heure de création. |

## ligne-commande

Table `ligne_commande`. Ligne d'un bon de commande : désignation, quantité, prix unitaire et taux de taxe.

Unicité : `bon_commande_id`, `rang`.

| Colonne | Type | Obligatoire | Clé | Description |
|---|---|---|---|---|
| `id` | UUID | Oui | primaire | Identifiant unique (UUID), exposé par l'API et partagé entre modules (INT-06). |
| `bon_commande_id` | UUID | Oui | → `bon_commande` | Référence vers `bon_commande`. |
| `rang` | INTEGER | Oui |  | Rang de la ligne. |
| `designation` | VARCHAR(300) | Oui |  | Désignation de l'article ou de la prestation. |
| `quantite` | NUMERIC(18, 3) | Oui |  | Quantité commandée. |
| `prix_unitaire` | NUMERIC(18, 2) | Oui |  | Prix unitaire hors taxes. |
| `taux_taxe` | NUMERIC(18, 2) | Oui |  | Taux de taxe en pourcentage. |

## reception

Table `reception`. Réception d'une commande ; preuve du service fait une fois validée (EF-REC-05).

Unicité : `etablissement_id`, `numero`.

| Colonne | Type | Obligatoire | Clé | Description |
|---|---|---|---|---|
| `id` | UUID | Oui | primaire | Identifiant unique (UUID), exposé par l'API et partagé entre modules (INT-06). |
| `etablissement_id` | UUID | Oui | → `etablissement` | Établissement propriétaire : cloisonnement vérifié à chaque requête. |
| `bon_commande_id` | UUID | Oui | → `bon_commande` | Référence vers `bon_commande`. |
| `numero` | VARCHAR(30) | Oui |  | Numéro de pièce, unique par établissement (`PREFIXE-ANNEE-RANG`). |
| `date_reception` | DATE | Oui |  | Date de réception. |
| `type` | VARCHAR(20) | Oui |  | Réception totale, partielle ou refusée. |
| `centre_id` | UUID | Oui | → `centre_responsabilite` | Référence vers `centre_responsabilite`. |
| `agent_responsable_code` | VARCHAR(20) | Oui |  | Code de l'agent qui réceptionne (`HOPITALIA` pour un approvisionnement importé). |
| `observations` | VARCHAR(1000) | Non |  | Observations libres. |
| `statut` | VARCHAR(20) | Oui |  | Statut de la réception ; seule une réception validée prouve le service fait ; `ANNULE` : approvisionnement supprimé dans Hopitalia. |
| `cree_par_id` | BIGINT | Oui |  | Identifiant Hopitalia (`userId`) de l'agent créateur. |
| `cree_par_code` | VARCHAR(20) | Oui |  | Code de l'agent créateur. |
| `cree_le` | TIMESTAMP WITH TIME ZONE | Oui |  | Date et heure de création. |
| `version` | INTEGER | Oui |  | Version de la ligne : verrou optimiste, comparée à l'en-tête `If-Match`. |

## ligne-reception

Table `ligne_reception`. Quantités reçues, acceptées et rejetées d'une ligne de commande dans une réception.

Unicité : `reception_id`, `ligne_commande_id`.

| Colonne | Type | Obligatoire | Clé | Description |
|---|---|---|---|---|
| `id` | UUID | Oui | primaire | Identifiant unique (UUID), exposé par l'API et partagé entre modules (INT-06). |
| `reception_id` | UUID | Oui | → `reception` | Référence vers `reception`. |
| `ligne_commande_id` | UUID | Oui | → `ligne_commande` | Référence vers `ligne_commande`. |
| `quantite_recue` | NUMERIC(18, 3) | Oui |  | Quantité reçue. |
| `quantite_acceptee` | NUMERIC(18, 3) | Oui |  | Quantité acceptée ; compte dans le réceptionné une fois la réception validée. |
| `quantite_rejetee` | NUMERIC(18, 3) | Oui |  | Quantité rejetée. |

## reserve-reception

Table `reserve_reception`. Réserve émise sur une réception, puis levée.

| Colonne | Type | Obligatoire | Clé | Description |
|---|---|---|---|---|
| `id` | UUID | Oui | primaire | Identifiant unique (UUID), exposé par l'API et partagé entre modules (INT-06). |
| `reception_id` | UUID | Oui | → `reception` | Référence vers `reception`. |
| `etablissement_id` | UUID | Oui | → `etablissement` | Établissement propriétaire : cloisonnement vérifié à chaque requête. |
| `description` | VARCHAR(1000) | Oui |  | Description libre. |
| `date_constat` | DATE | Oui |  | Date du constat de la réserve. |
| `date_levee` | DATE | Non |  | Date de levée de la réserve. |
| `levee_par_code` | VARCHAR(20) | Non |  | Code de l'agent qui lève la réserve. |

## attestation-service-fait

Table `attestation_service_fait`. Attestation de service fait pour une prestation sans livraison physique.

Unicité : `reception_id`.

| Colonne | Type | Obligatoire | Clé | Description |
|---|---|---|---|---|
| `id` | UUID | Oui | primaire | Identifiant unique (UUID), exposé par l'API et partagé entre modules (INT-06). |
| `reception_id` | UUID | Oui | → `reception`, unique | Référence vers `reception`. |
| `date` | DATE | Oui |  | Date de l'attestation. |
| `livrable` | VARCHAR(500) | Oui |  | Livrable attesté. |
| `conforme` | BOOLEAN | Oui |  | Vrai : prestation conforme. |
| `cree_par_code` | VARCHAR(20) | Oui |  | Code de l'agent créateur. |

## facture

Table `facture`. Facture du fournisseur, rattachée à un engagement (RG-05) ; un avoir est négatif.

| Colonne | Type | Obligatoire | Clé | Description |
|---|---|---|---|---|
| `id` | UUID | Oui | primaire | Identifiant unique (UUID), exposé par l'API et partagé entre modules (INT-06). |
| `etablissement_id` | UUID | Oui | → `etablissement` | Établissement propriétaire : cloisonnement vérifié à chaque requête. |
| `engagement_id` | UUID | Oui | → `engagement` | Référence vers `engagement`. |
| `fournisseur_id` | UUID | Oui | → `fournisseur` | Référence vers `fournisseur`. |
| `bon_commande_id` | UUID | Non | → `bon_commande` | Référence vers `bon_commande`. |
| `facture_origine_id` | UUID | Non | → `facture` | Référence vers `facture`. |
| `numero` | VARCHAR(50) | Oui |  | Numéro de la facture du fournisseur (contrôle de doublon, RG-16). |
| `type` | VARCHAR(20) | Oui |  | Avance, acompte, partielle, définitive, décompte ou avoir. |
| `objet` | VARCHAR(500) | Oui |  | Objet de la pièce. |
| `date_emission` | DATE | Oui |  | Date d'émission de la pièce. |
| `date_reception` | DATE | Oui |  | Date de réception. |
| `date_echeance` | DATE | Non |  | Date d'échéance. |
| `date_limite_traitement` | DATE | Non |  | Date limite de traitement de la facture. |
| `periode_rattachement` | VARCHAR(50) | Non |  | Période à laquelle la facture se rattache. |
| `montant_ht` | NUMERIC(18, 2) | Oui |  | Montant hors taxes. |
| `montant_taxes` | NUMERIC(18, 2) | Oui |  | Montant des taxes. |
| `montant_ttc` | NUMERIC(18, 2) | Oui |  | Montant toutes taxes comprises. |
| `numero_decompte` | INTEGER | Non |  | Numéro du décompte (facture de marché). |
| `statut` | VARCHAR(30) | Oui |  | Statut dans le cycle de l'objet (cycle de référence : cahier des charges, 7). |
| `motif_statut` | VARCHAR(500) | Non |  | Motif du dernier changement de statut (rejet, retour). |
| `motif_levee_doublon` | VARCHAR(500) | Non |  | Motif de la levée du blocage de doublon (RG-16). |
| `cree_par_id` | BIGINT | Oui |  | Identifiant Hopitalia (`userId`) de l'agent créateur. |
| `cree_par_code` | VARCHAR(20) | Oui |  | Code de l'agent créateur. |
| `cree_le` | TIMESTAMP WITH TIME ZONE | Oui |  | Date et heure de création. |
| `version` | INTEGER | Oui |  | Version de la ligne : verrou optimiste, comparée à l'en-tête `If-Match`. |

## liquidation

Table `liquidation`. Liquidation d'une facture sur une seule imputation d'engagement (RG-17).

Unicité : `etablissement_id`, `numero`.

| Colonne | Type | Obligatoire | Clé | Description |
|---|---|---|---|---|
| `id` | UUID | Oui | primaire | Identifiant unique (UUID), exposé par l'API et partagé entre modules (INT-06). |
| `etablissement_id` | UUID | Oui | → `etablissement` | Établissement propriétaire : cloisonnement vérifié à chaque requête. |
| `facture_id` | UUID | Oui | → `facture` | Référence vers `facture`. |
| `imputation_id` | UUID | Oui | → `imputation_engagement` | Référence vers `imputation_engagement`. |
| `numero` | VARCHAR(30) | Oui |  | Numéro de pièce, unique par établissement (`PREFIXE-ANNEE-RANG`). |
| `date_liquidation` | DATE | Oui |  | Date de la liquidation. |
| `montant_base` | NUMERIC(18, 2) | Oui |  | Montant liquidé avant déductions. |
| `observations` | VARCHAR(1000) | Non |  | Observations libres. |
| `statut` | VARCHAR(20) | Oui |  | Statut dans le cycle de l'objet (cycle de référence : cahier des charges, 7). |
| `cree_par_id` | BIGINT | Oui |  | Identifiant Hopitalia (`userId`) de l'agent créateur. |
| `cree_par_code` | VARCHAR(20) | Oui |  | Code de l'agent créateur. |
| `cree_le` | TIMESTAMP WITH TIME ZONE | Oui |  | Date et heure de création. |
| `version` | INTEGER | Oui |  | Version de la ligne : verrou optimiste, comparée à l'en-tête `If-Match`. |

## deduction

Table `deduction`. Déduction appliquée à une liquidation : avance récupérée, retenue de garantie, pénalité, réfaction, retenue à la source ou autre.

| Colonne | Type | Obligatoire | Clé | Description |
|---|---|---|---|---|
| `id` | UUID | Oui | primaire | Identifiant unique (UUID), exposé par l'API et partagé entre modules (INT-06). |
| `liquidation_id` | UUID | Oui | → `liquidation` | Référence vers `liquidation`. |
| `type` | VARCHAR(30) | Oui |  | Avance récupérée, retenue de garantie, pénalité, réfaction, retenue à la source, autre. |
| `montant` | NUMERIC(18, 2) | Oui |  | Montant en francs CFA, `Numeric(18,2)`. |
| `taux` | NUMERIC(18, 2) | Non |  | Taux de la déduction en pourcentage. |
| `motif` | VARCHAR(500) | Non |  | Motif saisi, obligatoire pour l'opération. |
| `base_calcul` | VARCHAR(300) | Non |  | Base de calcul de la déduction. |

## liquidation-reception

Table `liquidation_reception`. Réceptions qui prouvent le service fait d'une liquidation (RG-06).

| Colonne | Type | Obligatoire | Clé | Description |
|---|---|---|---|---|
| `liquidation_id` | UUID | Oui | primaire, → `liquidation` | Référence vers `liquidation`. |
| `reception_id` | UUID | Oui | primaire, → `reception` | Référence vers `reception`. |

## rapprochement

Table `rapprochement`. Rapprochement commande / réception / facture / paiement d'une facture (section 9.1).

| Colonne | Type | Obligatoire | Clé | Description |
|---|---|---|---|---|
| `id` | UUID | Oui | primaire | Identifiant unique (UUID), exposé par l'API et partagé entre modules (INT-06). |
| `facture_id` | UUID | Oui | → `facture` | Référence vers `facture`. |
| `etablissement_id` | UUID | Oui | → `etablissement` | Établissement propriétaire : cloisonnement vérifié à chaque requête. |
| `date_rapprochement` | DATE | Oui |  | Date du rapprochement. |
| `ecart_commande_reception` | NUMERIC(18, 2) | Oui |  | Écart entre commandé et réceptionné. |
| `ecart_reception_facture` | NUMERIC(18, 2) | Oui |  | Écart entre réceptionné et facturé. |
| `ecart_facture_paiement` | NUMERIC(18, 2) | Oui |  | Écart entre facturé et payé. |
| `explication` | VARCHAR(1000) | Non |  | Explication de l'écart, obligatoire s'il n'est pas nul. |
| `cree_par_code` | VARCHAR(20) | Oui |  | Code de l'agent créateur. |
| `cree_le` | TIMESTAMP WITH TIME ZONE | Oui |  | Date et heure de création. |

## ordonnancement

Table `ordonnancement`. Dossier de liquidations transmis au comptable (EF-ORD-01, EF-ORD-02).

Unicité : `etablissement_id`, `reference_piece`.

| Colonne | Type | Obligatoire | Clé | Description |
|---|---|---|---|---|
| `id` | UUID | Oui | primaire | Identifiant unique (UUID), exposé par l'API et partagé entre modules (INT-06). |
| `etablissement_id` | UUID | Oui | → `etablissement` | Établissement propriétaire : cloisonnement vérifié à chaque requête. |
| `reference_piece` | VARCHAR(50) | Oui |  | Référence du mandat ou de l'ordre de paiement. |
| `type_piece` | VARCHAR(20) | Oui |  | Type de pièce de l'ordonnancement (mandat, ordre de paiement). |
| `service_destinataire` | VARCHAR(200) | Oui |  | Service destinataire de la transmission. |
| `date_transmission` | DATE | Non |  | Date de transmission au comptable. |
| `statut` | VARCHAR(20) | Oui |  | Statut dans le cycle de l'objet (cycle de référence : cahier des charges, 7). |
| `motif_statut` | VARCHAR(500) | Non |  | Motif du dernier changement de statut (rejet, retour). |
| `transmis_par_id` | BIGINT | Non |  | Identifiant Hopitalia de l'agent qui transmet. |
| `cree_par_id` | BIGINT | Oui |  | Identifiant Hopitalia (`userId`) de l'agent créateur. |
| `cree_par_code` | VARCHAR(20) | Oui |  | Code de l'agent créateur. |
| `cree_le` | TIMESTAMP WITH TIME ZONE | Oui |  | Date et heure de création. |
| `version` | INTEGER | Oui |  | Version de la ligne : verrou optimiste, comparée à l'en-tête `If-Match`. |

## ligne-ordonnancement

Table `ligne_ordonnancement`. Une liquidation dans un ordonnancement ; l'historique des rejets est conservé (EF-ORD-03).

| Colonne | Type | Obligatoire | Clé | Description |
|---|---|---|---|---|
| `id` | UUID | Oui | primaire | Identifiant unique (UUID), exposé par l'API et partagé entre modules (INT-06). |
| `ordonnancement_id` | UUID | Oui | → `ordonnancement` | Référence vers `ordonnancement`. |
| `liquidation_id` | UUID | Oui | → `liquidation` | Référence vers `liquidation`. |
| `montant` | NUMERIC(18, 2) | Oui |  | Montant en francs CFA, `Numeric(18,2)`. |

## paiement

Table `paiement`. Paiement d'un fournisseur, ventilé par liquidation (EF-PAI-01, EF-PAI-02).

Unicité : `etablissement_id`, `numero`.

| Colonne | Type | Obligatoire | Clé | Description |
|---|---|---|---|---|
| `id` | UUID | Oui | primaire | Identifiant unique (UUID), exposé par l'API et partagé entre modules (INT-06). |
| `etablissement_id` | UUID | Oui | → `etablissement` | Établissement propriétaire : cloisonnement vérifié à chaque requête. |
| `fournisseur_id` | UUID | Oui | → `fournisseur` | Référence vers `fournisseur`. |
| `numero` | VARCHAR(30) | Oui |  | Numéro de pièce, unique par établissement (`PREFIXE-ANNEE-RANG`). |
| `date_paiement` | DATE | Oui |  | Date d'exécution du paiement. |
| `montant` | NUMERIC(18, 2) | Oui |  | Montant en francs CFA, `Numeric(18,2)`. |
| `mode_reglement_id` | UUID | Oui | → `referentiel` | Référence vers `referentiel`. |
| `compte_tresorerie_id` | UUID | Oui | → `referentiel` | Référence vers `referentiel`. |
| `reference_transaction` | VARCHAR(100) | Non |  | Référence bancaire ou de transaction. |
| `piece_caisse` | VARCHAR(100) | Non |  | Référence de la pièce de caisse. |
| `retenue_source` | NUMERIC(18, 2) | Oui |  | Retenue à la source opérée au paiement. |
| `statut` | VARCHAR(20) | Oui |  | Statut dans le cycle de l'objet (cycle de référence : cahier des charges, 7). |
| `motif_annulation` | VARCHAR(500) | Non |  | Motif de l'annulation du paiement. |
| `cree_par_id` | BIGINT | Oui |  | Identifiant Hopitalia (`userId`) de l'agent créateur. |
| `cree_par_code` | VARCHAR(20) | Oui |  | Code de l'agent créateur. |
| `cree_le` | TIMESTAMP WITH TIME ZONE | Oui |  | Date et heure de création. |
| `version` | INTEGER | Oui |  | Version de la ligne : verrou optimiste, comparée à l'en-tête `If-Match`. |

## allocation-paiement

Table `allocation_paiement`. Part d'un paiement affectée à une liquidation (section 17, point 12).

| Colonne | Type | Obligatoire | Clé | Description |
|---|---|---|---|---|
| `id` | UUID | Oui | primaire | Identifiant unique (UUID), exposé par l'API et partagé entre modules (INT-06). |
| `paiement_id` | UUID | Oui | → `paiement` | Référence vers `paiement`. |
| `liquidation_id` | UUID | Oui | → `liquidation` | Référence vers `liquidation`. |
| `montant` | NUMERIC(18, 2) | Oui |  | Montant en francs CFA, `Numeric(18,2)`. |

## regle-alerte

Table `regle_alerte`. Règle d'alerte d'un établissement ; absente, la valeur par défaut s'applique (T-220).

| Colonne | Type | Obligatoire | Clé | Description |
|---|---|---|---|---|
| `etablissement_id` | UUID | Oui | primaire, → `etablissement` | Établissement propriétaire : cloisonnement vérifié à chaque requête. |
| `type` | VARCHAR(40) | Oui | primaire | Type d'alerte réglée (section 14.3). |
| `actif` | BOOLEAN | Oui |  | Faux : élément désactivé, conservé pour l'historique, plus proposé à la saisie. |
| `seuil_pourcent` | NUMERIC(18, 2) | Non |  | Seuil de consommation en pourcentage. |
| `delai_jours` | INTEGER | Non |  | Délai en jours. |
| `notifier_par_email` | BOOLEAN | Oui |  | Vrai : l'alerte est aussi envoyée par courriel (T-225, en attente). |

## alerte

Table `alerte`. Alerte créée par un contrôle, une tentative refusée ou la tâche planifiée (14.3).

Unicité : `type`, `type_objet`, `id_objet`, `cle`.

| Colonne | Type | Obligatoire | Clé | Description |
|---|---|---|---|---|
| `id` | UUID | Oui | primaire | Identifiant unique (UUID), exposé par l'API et partagé entre modules (INT-06). |
| `etablissement_id` | UUID | Oui | → `etablissement` | Établissement propriétaire : cloisonnement vérifié à chaque requête. |
| `type` | VARCHAR(40) | Oui |  | Type d'alerte (section 14.3). |
| `gravite` | VARCHAR(10) | Oui |  | Gravité de l'alerte : blocage ou alerte. |
| `type_objet` | VARCHAR(40) | Oui |  | Type de l'objet concerné (`Engagement`, `Facture`…). |
| `id_objet` | UUID | Oui |  | Identifiant de l'objet concerné. |
| `cle` | VARCHAR(60) | Non |  | Clé de dédoublonnage : même type, objet et clé, une seule alerte. |
| `details` | JSONB | Oui |  | Valeurs du message de l'alerte (JSON). |
| `profils` | JSONB | Oui |  | Profils destinataires de l'alerte (JSON). |
| `code_agent` | VARCHAR(20) | Non |  | Code de l'agent Hopitalia concerné. |
| `cree_le` | TIMESTAMP WITH TIME ZONE | Oui |  | Date et heure de création. |

## lecture-alerte

Table `lecture_alerte`. Alerte lue par un agent : chaque destinataire a son propre état de lecture.

| Colonne | Type | Obligatoire | Clé | Description |
|---|---|---|---|---|
| `alerte_id` | UUID | Oui | primaire, → `alerte` | Référence vers `alerte`. |
| `utilisateur_id` | BIGINT | Oui | primaire | Identifiant Hopitalia (`userId`) de l'agent. |
| `lue_le` | TIMESTAMP WITH TIME ZONE | Oui |  | Date et heure de lecture par l'agent. |

## cloture-exercice

Table `cloture_exercice`. Clôture d'un exercice pour un établissement (EF-BUD-09) ; une réouverture motivée la lève sans l'effacer (T-240). L'exercice est ouvert pour l'établissement tant qu'aucune clôture n'est en vigueur.

| Colonne | Type | Obligatoire | Clé | Description |
|---|---|---|---|---|
| `id` | UUID | Oui | primaire | Identifiant unique (UUID), exposé par l'API et partagé entre modules (INT-06). |
| `exercice_id` | UUID | Oui | → `exercice` | Référence vers `exercice`. |
| `etablissement_id` | UUID | Oui | → `etablissement` | Établissement propriétaire : cloisonnement vérifié à chaque requête. |
| `exercice_suivant_id` | UUID | Oui | → `exercice` | Référence vers `exercice`. |
| `motif` | VARCHAR(500) | Oui |  | Motif saisi, obligatoire pour l'opération. |
| `engagements_reportes` | INTEGER | Oui |  | Nombre d'engagements reportés sur l'exercice suivant. |
| `montant_reporte` | NUMERIC(18, 2) | Oui |  | Montant total reporté. |
| `cree_par_code` | VARCHAR(20) | Oui |  | Code de l'agent créateur. |
| `cree_le` | TIMESTAMP WITH TIME ZONE | Oui |  | Date et heure de création. |
| `reouvert_le` | TIMESTAMP WITH TIME ZONE | Non |  | Date et heure de réouverture (vide : clôture en vigueur). |
| `reouvert_par_code` | VARCHAR(20) | Non |  | Code de l'agent qui rouvre. |
| `motif_reouverture` | VARCHAR(500) | Non |  | Motif de la réouverture. |

## journal-integration

Table `journal_integration`. Un échange avec un système externe (INT-07). Une reprise rejoue l'échange sur la même ligne (même identifiant unique) : tentatives et statut changent, jamais de doublon.

Unicité : `identifiant_unique`.

| Colonne | Type | Obligatoire | Clé | Description |
|---|---|---|---|---|
| `id` | BIGINT | Oui | primaire | Rang de l'échange, croissant. |
| `systeme_externe` | VARCHAR(30) | Oui |  | Système externe de l'échange (`HOPITALIA`). |
| `direction` | VARCHAR(10) | Oui |  | Sens de l'échange (`ENTRANT`). |
| `type_donnees` | VARCHAR(40) | Oui |  | Données échangées : fournisseurs, services ou pharmacie. |
| `identifiant_unique` | VARCHAR(120) | Oui | unique | Système, type et période : un échange rejoué réutilise sa ligne (INT-07). |
| `etablissement_id` | UUID | Non | → `etablissement` | Établissement qui reçoit les données (vide : fournisseurs, communs). |
| `parametres` | JSONB | Oui |  | Paramètres de l'échange (jour, ou début et fin de la fenêtre), réutilisés par une reprise. |
| `statut` | VARCHAR(10) | Oui |  | `EN_COURS`, `SUCCES` ou `ECHEC`. |
| `erreur` | VARCHAR(1000) | Non |  | Code d'erreur du dernier échec. |
| `resultat` | JSONB | Non |  | Compteurs du dernier succès (lus, créés, modifiés…). |
| `tentatives` | INTEGER | Oui |  | Nombre de tentatives ; la reprise automatique s'arrête à cinq. |
| `declenche_par_code` | VARCHAR(20) | Non |  | Code de l'agent qui a lancé ou repris l'échange (vide : tâche planifiée). |
| `cree_le` | TIMESTAMP WITH TIME ZONE | Oui |  | Date et heure de création. |
| `date` | TIMESTAMP WITH TIME ZONE | Oui |  | Date et heure de la dernière tentative. |

## commande-pharmacie

Table `commande_pharmacie`. Bon de commande de la pharmacie Hopitalia, importé tel quel (INT-03), en attente de rattachement à un engagement ; le rattachement crée le bon de commande du module.

Unicité : `bon_commande_id` ; `etablissement_id`, `id_hopitalia`.

| Colonne | Type | Obligatoire | Clé | Description |
|---|---|---|---|---|
| `id` | UUID | Oui | primaire | Identifiant unique (UUID), exposé par l'API et partagé entre modules (INT-06). |
| `etablissement_id` | UUID | Oui | → `etablissement` | Établissement propriétaire : cloisonnement vérifié à chaque requête. |
| `id_hopitalia` | BIGINT | Oui |  | Identifiant de l'élément dans Hopitalia ; unique par établissement. |
| `numero` | VARCHAR(30) | Oui |  | Numéro de la commande dans Hopitalia (`numBc`). |
| `date_commande` | DATE | Oui |  | Date de la commande dans Hopitalia. |
| `code_fournisseur` | VARCHAR(20) | Non |  | Code du fournisseur dans Hopitalia (`codeFourn`). |
| `fournisseur_id` | UUID | Non | → `fournisseur` | Référence vers `fournisseur`. |
| `service` | VARCHAR(200) | Non |  | Service demandeur dans Hopitalia. |
| `lignes` | JSONB | Oui |  | Lignes importées telles quelles (JSON : produit, désignation, quantité, montant). |
| `montant` | NUMERIC(18, 2) | Oui |  | Total des lignes Hopitalia. |
| `bon_commande_id` | UUID | Non | → `bon_commande`, unique | Bon de commande créé au rattachement (vide : à rattacher). |
| `importe_le` | TIMESTAMP WITH TIME ZONE | Oui |  | Date et heure du premier import. |

## approvisionnement-pharmacie

Table `approvisionnement_pharmacie`. Approvisionnement de la pharmacie Hopitalia (INT-03) : devient une réception validée de la commande rattachée. L'empreinte du contenu détecte une modification dans Hopitalia.

Unicité : `etablissement_id`, `id_hopitalia` ; `reception_id`.

| Colonne | Type | Obligatoire | Clé | Description |
|---|---|---|---|---|
| `id` | UUID | Oui | primaire | Identifiant unique (UUID), exposé par l'API et partagé entre modules (INT-06). |
| `etablissement_id` | UUID | Oui | → `etablissement` | Établissement propriétaire : cloisonnement vérifié à chaque requête. |
| `id_hopitalia` | BIGINT | Oui |  | Identifiant de l'élément dans Hopitalia ; unique par établissement. |
| `numero_bl` | VARCHAR(50) | Non |  | Numéro du bon de livraison : preuve du service fait. |
| `numero_commande` | VARCHAR(30) | Non |  | Numéro de la commande Hopitalia livrée (`numBonCmde`). |
| `date_approvisionnement` | DATE | Oui |  | Date de l'approvisionnement. |
| `code_fournisseur` | VARCHAR(20) | Non |  | Code du fournisseur dans Hopitalia (`codeFourn`). |
| `lignes` | JSONB | Oui |  | Lignes importées telles quelles (JSON : produit, désignation, quantité, montant). |
| `empreinte` | VARCHAR(64) | Oui |  | Empreinte du contenu : un approvisionnement inchangé n'est pas réimporté. |
| `reception_id` | UUID | Non | → `reception`, unique | Réception validée créée pour l'approvisionnement (vide : en attente). |
| `supprime` | BOOLEAN | Oui |  | Vrai : approvisionnement supprimé dans Hopitalia ; sa réception est annulée. |
| `importe_le` | TIMESTAMP WITH TIME ZONE | Oui |  | Date et heure du premier import. |
