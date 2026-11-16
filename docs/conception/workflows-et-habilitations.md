# Workflows et matrice des habilitations

**Projet :** Hopitalia Budget · **Tâche :** T-281 · **Référence :** cahier des charges V3, sections 7.6, 8 et 17 ; matrice validée le 13/11/2026 (`docs/cadrage/matrice-habilitations.md`)

Produit depuis le domaine (`domaine/workflow.py`, `domaine/habilitations.py`). Ne pas le modifier à la main : le régénérer depuis `backend/` par `python -m tests.test_doc_workflows`. Le test `test_doc_workflows.py` échoue si ce fichier n'est plus à jour.

**Statut :** à valider par la DAF (critère de fin de T-281).

## Profils

| Code | Profil |
|---|---|
| ADM | Administrateur fonctionnel |
| RB | Responsable budgétaire |
| AF | Agent financier |
| GMC | Gestionnaire de marchés et contrats |
| SD | Service demandeur |
| REC | Réceptionnaire |
| VAL | Valideur (responsable de service, DAF) |
| ORD | Ordonnateur |
| CPT | Comptable, agent de paiement |
| AUD | Auditeur |
| LEC | Lecteur de tableaux de bord |

## Matrice des habilitations

S : saisir ; V : valider ; L : consulter ; — : aucun accès. Le droit vaut dans le périmètre de l'agent (son ou ses établissements).

| Opération | ADM | RB | AF | GMC | SD | REC | VAL | ORD | CPT | AUD | LEC |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Paramétrer référentiels, circuits, alertes, profils | S | L | — | — | — | — | — | — | — | L | — |
| Saisir ou importer un budget, une notification de crédits | — | S | L | — | — | — | L | L | — | L | — |
| Demander une révision budgétaire | — | S | — | — | — | — | — | — | — | L | — |
| Valider une révision budgétaire | — | L | — | — | — | — | V | V | — | L | — |
| Enregistrer un contrat, un avenant | — | L | L | S | — | — | L | L | — | L | — |
| Valider un contrat, un avenant | — | — | — | L | — | — | V | V | — | L | — |
| Demander un engagement | — | — | — | S | S | — | L | L | — | L | — |
| Contrôler un engagement (imputation, crédits) | — | — | V | — | — | — | — | — | — | L | — |
| Valider un engagement | — | — | L | L | L | — | V | V | — | L | — |
| Émettre un bon de commande | — | — | L | S | L | — | — | — | — | L | — |
| Rattacher une commande de la pharmacie à un engagement | — | — | S | L | — | — | — | — | — | L | — |
| Enregistrer une réception | — | — | — | L | L | S | — | — | — | L | — |
| Valider le service fait | — | — | L | L | — | — | V | — | — | L | — |
| Enregistrer une facture | — | — | S | L | — | — | — | — | — | L | — |
| Liquider une facture | — | — | S | — | — | — | — | — | — | L | — |
| Valider une liquidation | — | — | L | — | — | — | V | V | — | L | — |
| Ordonnancer (transmettre en paiement) | — | — | L | — | — | — | — | S | L | L | — |
| Enregistrer un paiement | — | — | L | — | — | — | — | L | S | L | — |
| Accorder une dérogation | — | — | — | — | — | — | V | V | — | L | — |
| Annuler une opération validée | — | — | S | — | — | — | V | V | — | L | — |
| Clôturer un exercice | — | S | — | — | — | — | — | V | — | L | — |
| Consulter les tableaux de bord et exporter les états | L | L | L | L | L | — | L | L | L | L | L |
| Consulter le journal d'audit | — | — | — | — | — | — | L | L | — | L | — |

## Objets validés par circuit

Une pièce se saisit, se soumet, puis passe les étapes de son circuit. Chaque étape est un profil qui a le droit « Valider » dans la matrice. Un établissement peut paramétrer ses circuits (par service et par seuil de montant) ; pour les objets marqués ci-dessous, la dernière étape revient toujours à l'ordonnateur (section 17, point 16).

### Révision budgétaire

- Saisie : demander une révision budgétaire — profils RB.
- Profils qui peuvent viser : ORD, VAL.
- Circuit par défaut : 1. Visa DAF (VAL) ; 2. Ordonnateur (ORD).
- Ordonnateur en dernière étape obligatoire : Oui.

| Depuis | Action | Vers |
|---|---|---|
| `SOUMISE` | Viser (d'autres étapes restent) | `EN_VALIDATION` |
| `SOUMISE` | Valider (dernière étape : l'opération prend effet) | `VALIDEE` |
| `EN_VALIDATION` | Viser (d'autres étapes restent) | `EN_VALIDATION` |
| `EN_VALIDATION` | Valider (dernière étape : l'opération prend effet) | `VALIDEE` |
| `SOUMISE` | Rejeter | `REJETEE` |
| `EN_VALIDATION` | Rejeter | `REJETEE` |
| `SOUMISE` | Retourner pour correction | `A_CORRIGER` |
| `EN_VALIDATION` | Retourner pour correction | `A_CORRIGER` |
| `A_CORRIGER` | Soumettre | `SOUMISE` |

### Contrat

- Saisie : enregistrer un contrat, un avenant — profils GMC.
- Profils qui peuvent viser : ORD, VAL.
- Circuit par défaut : 1. Visa DAF (VAL) ; 2. Ordonnateur (ORD).
- Ordonnateur en dernière étape obligatoire : Oui.

| Depuis | Action | Vers |
|---|---|---|
| `BROUILLON` | Soumettre | `SOUMIS` |
| `SOUMIS` | Viser (d'autres étapes restent) | `EN_VALIDATION` |
| `SOUMIS` | Valider (dernière étape : l'opération prend effet) | `VALIDE` |
| `EN_VALIDATION` | Viser (d'autres étapes restent) | `EN_VALIDATION` |
| `EN_VALIDATION` | Valider (dernière étape : l'opération prend effet) | `VALIDE` |
| `SOUMIS` | Rejeter | `REJETE` |
| `EN_VALIDATION` | Rejeter | `REJETE` |
| `SOUMIS` | Retourner pour correction | `A_CORRIGER` |
| `EN_VALIDATION` | Retourner pour correction | `A_CORRIGER` |
| `A_CORRIGER` | Soumettre | `SOUMIS` |

### Avenant

- Saisie : enregistrer un contrat, un avenant — profils GMC.
- Profils qui peuvent viser : ORD, VAL.
- Circuit par défaut : 1. Visa DAF (VAL) ; 2. Ordonnateur (ORD).
- Ordonnateur en dernière étape obligatoire : Oui.

| Depuis | Action | Vers |
|---|---|---|
| `SOUMIS` | Viser (d'autres étapes restent) | `EN_VALIDATION` |
| `SOUMIS` | Valider (dernière étape : l'opération prend effet) | `VALIDE` |
| `EN_VALIDATION` | Viser (d'autres étapes restent) | `EN_VALIDATION` |
| `EN_VALIDATION` | Valider (dernière étape : l'opération prend effet) | `VALIDE` |
| `SOUMIS` | Rejeter | `REJETE` |
| `EN_VALIDATION` | Rejeter | `REJETE` |
| `SOUMIS` | Retourner pour correction | `A_CORRIGER` |
| `EN_VALIDATION` | Retourner pour correction | `A_CORRIGER` |
| `A_CORRIGER` | Soumettre | `SOUMIS` |

### Engagement

- Saisie : demander un engagement — profils GMC, SD.
- Profils qui peuvent viser : AF, ORD, VAL.
- Circuit par défaut : 1. Contrôle financier (AF) ; 2. Visa DAF (VAL) ; 3. Ordonnateur (ORD).
- Ordonnateur en dernière étape obligatoire : Oui.

| Depuis | Action | Vers |
|---|---|---|
| `BROUILLON` | Soumettre | `SOUMIS` |
| `SOUMIS` | Viser (d'autres étapes restent) | `EN_CONTROLE` |
| `SOUMIS` | Valider (dernière étape : l'opération prend effet) | `VALIDE` |
| `EN_CONTROLE` | Viser (d'autres étapes restent) | `EN_CONTROLE` |
| `EN_CONTROLE` | Valider (dernière étape : l'opération prend effet) | `VALIDE` |
| `SOUMIS` | Rejeter | `REJETE` |
| `EN_CONTROLE` | Rejeter | `REJETE` |
| `SOUMIS` | Retourner pour correction | `A_CORRIGER` |
| `EN_CONTROLE` | Retourner pour correction | `A_CORRIGER` |
| `A_CORRIGER` | Soumettre | `SOUMIS` |

### Dérogation

- Saisie : demander un engagement — profils GMC, SD.
- Profils qui peuvent viser : ORD, VAL.
- Circuit par défaut : 1. Visa DAF (VAL) ; 2. Ordonnateur (ORD).
- Ordonnateur en dernière étape obligatoire : Oui.

| Depuis | Action | Vers |
|---|---|---|
| `SOUMIS` | Viser (d'autres étapes restent) | `EN_VALIDATION` |
| `SOUMIS` | Valider (dernière étape : l'opération prend effet) | `VALIDE` |
| `EN_VALIDATION` | Viser (d'autres étapes restent) | `EN_VALIDATION` |
| `EN_VALIDATION` | Valider (dernière étape : l'opération prend effet) | `VALIDE` |
| `SOUMIS` | Rejeter | `REJETE` |
| `EN_VALIDATION` | Rejeter | `REJETE` |
| `SOUMIS` | Retourner pour correction | `A_CORRIGER` |
| `EN_VALIDATION` | Retourner pour correction | `A_CORRIGER` |
| `A_CORRIGER` | Soumettre | `SOUMIS` |

### Liquidation

- Saisie : liquider une facture — profils AF.
- Profils qui peuvent viser : ORD, VAL.
- Circuit par défaut : 1. Visa DAF (VAL) ; 2. Ordonnateur (ORD).
- Ordonnateur en dernière étape obligatoire : Oui.

| Depuis | Action | Vers |
|---|---|---|
| `BROUILLON` | Soumettre | `SOUMIS` |
| `SOUMIS` | Viser (d'autres étapes restent) | `EN_VALIDATION` |
| `SOUMIS` | Valider (dernière étape : l'opération prend effet) | `VALIDE` |
| `EN_VALIDATION` | Viser (d'autres étapes restent) | `EN_VALIDATION` |
| `EN_VALIDATION` | Valider (dernière étape : l'opération prend effet) | `VALIDE` |
| `SOUMIS` | Rejeter | `REJETE` |
| `EN_VALIDATION` | Rejeter | `REJETE` |
| `SOUMIS` | Retourner pour correction | `A_CORRIGER` |
| `EN_VALIDATION` | Retourner pour correction | `A_CORRIGER` |
| `A_CORRIGER` | Soumettre | `SOUMIS` |

### Réception (service fait)

- Saisie : enregistrer une réception — profils REC.
- Profils qui peuvent viser : VAL.
- Circuit par défaut : 1. Service fait (VAL).
- Ordonnateur en dernière étape obligatoire : Non.

| Depuis | Action | Vers |
|---|---|---|
| `BROUILLON` | Soumettre | `SOUMIS` |
| `SOUMIS` | Viser (d'autres étapes restent) | `EN_VALIDATION` |
| `SOUMIS` | Valider (dernière étape : l'opération prend effet) | `VALIDE` |
| `EN_VALIDATION` | Viser (d'autres étapes restent) | `EN_VALIDATION` |
| `EN_VALIDATION` | Valider (dernière étape : l'opération prend effet) | `VALIDE` |
| `SOUMIS` | Rejeter | `REJETE` |
| `EN_VALIDATION` | Rejeter | `REJETE` |
| `SOUMIS` | Retourner pour correction | `A_CORRIGER` |
| `EN_VALIDATION` | Retourner pour correction | `A_CORRIGER` |
| `A_CORRIGER` | Soumettre | `SOUMIS` |

### Facture

Porte des pièces justificatives sans circuit propre : saisie par AF ; ses liquidations sont validées par leur circuit.

## Cycles sans circuit de validation

| Objet | Statuts | Qui le fait avancer |
|---|---|---|
| Facture | `RECUE`, `EN_CONTROLE` (une liquidation saisie), `RETOURNEE`, `REJETEE`, `LIQUIDEE`, `MISE_EN_PAIEMENT`, `PARTIELLEMENT_PAYEE`, `PAYEE` | L'agent financier l'enregistre ; ses statuts suivent ses liquidations et ses paiements. Un doublon est bloqué, sauf levée motivée (RG-16). |
| Bon de commande | Émis, sans circuit | Le gestionnaire de marchés l'émet sur un engagement validé, dans la limite de son montant net (EF-CMD-01). Une commande de la pharmacie est rattachée par l'agent financier (EF-REC-07). |
| Ordonnancement | `PREPARE`, `TRANSMIS`, `COMPLEMENT_DEMANDE`, `SUSPENDU`, `REJETE`, `PRIS_EN_CHARGE` | L'ordonnateur prépare et transmet ; le comptable prend en charge, demande un complément, suspend ou rejette. |
| Paiement | `EXECUTE`, `ANNULE` | Le comptable l'enregistre une fois exécuté ; une annulation est motivée et tracée. |
| Annulation d'une opération validée | Enregistrée, sans circuit | Un agent habilité (AF, VAL ou ORD) l'enregistre avec un motif, tracée (RG-18). La matrice prévoit une demande par AF validée par VAL ou ORD : circuit propre reporté (`POINTS_REPORTES.md`). |
| Clôture d'exercice | Close, rouverte | Le responsable budgétaire ou l'ordonnateur clôt et rouvre, avec motif ; les engagements non soldés sont reportés. |
| Réception importée de la pharmacie | `VALIDE`, `ANNULE` | Créée validée par l'import d'Hopitalia (preuve : bon de livraison) ; annulée si l'approvisionnement est supprimé dans Hopitalia. |

## Séparation des tâches (RG-13)

Pour une même opération, une même personne ne peut pas cumuler :

| Rôle 1 | Rôle 2 | Raison |
|---|---|---|
| Demander l'engagement | Valider l'engagement | On ne valide pas sa propre demande. |
| Contrôler l'engagement | Valider l'engagement | Contrôle et décision distincts. |
| Enregistrer la réception | Valider le service fait | La preuve est confirmée par une autre personne. |
| Liquider | Valider la liquidation | On ne valide pas son propre calcul. |
| Valider la liquidation | Enregistrer le paiement | Celui qui reconnaît la dette ne la paie pas. |
| Ordonnancer | Enregistrer le paiement | Séparation ordonnateur et comptable. |
| Demander une dérogation | Accorder la dérogation | On ne s'autorise pas soi-même. |

Ces règles valent aussi par délégation : le délégataire ne valide pas une opération qu'il a saisie. Un circuit marqué « séparation des tâches » refuse le visa de l'auteur de la pièce.
