# Matrice des habilitations

**Projet :** Hopitalia Budget · **Statut :** validée le 13/11/2026 (tâche T-016) · **Références :** cahier des charges V3, sections 3, 7.6 et règle RG-13

Cette matrice indique, pour chaque profil, ce qu'il peut faire sur chaque opération. Une fois validée, elle sert au paramétrage des profils, des permissions et des circuits de validation. Chaque établissement peut l'adapter.

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

## Légende

| Code | Droit |
|---|---|
| S | Saisir, créer, modifier tant que l'opération n'est pas validée |
| V | Viser ou valider (dans la limite des seuils ci-dessous) |
| L | Consulter |
| — | Aucun accès |

Le droit de consulter est limité au périmètre de l'utilisateur : son ou ses établissements, et son service pour le profil SD.

## Matrice

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

Pour l'annulation d'une opération validée, AF saisit la demande et VAL ou ORD la valide.

## Ordre des validations

Il n'y a pas de seuil de montant : **l'ordonnateur valide toujours**, après le valideur (DAF), quel que soit le montant.

| Opération | 1re validation | 2e validation |
|---|---|---|
| Révision budgétaire | VAL | ORD |
| Contrat, avenant | VAL | ORD |
| Engagement | VAL | ORD |
| Liquidation | VAL | ORD |
| Dérogation | VAL | ORD |
| Annulation d'une opération validée | VAL | ORD |

Dans la matrice ci-dessus, la mention « V » pour VAL et pour ORD sur une même opération signifie donc deux validations successives, et non l'une ou l'autre.

## Séparation des tâches (RG-13)

Pour une **même opération**, une même personne ne peut pas cumuler :

| Rôle 1 | Rôle 2 | Raison |
|---|---|---|
| Demander l'engagement | Valider l'engagement | On ne valide pas sa propre demande. |
| Contrôler l'engagement | Valider l'engagement | Contrôle et décision distincts. |
| Enregistrer la réception | Valider le service fait | La preuve est confirmée par une autre personne. |
| Liquider | Valider la liquidation | On ne valide pas son propre calcul. |
| Valider la liquidation | Enregistrer le paiement | Celui qui reconnaît la dette ne la paie pas. |
| Ordonnancer | Enregistrer le paiement | Séparation ordonnateur et comptable. |
| Demander une dérogation | Accorder la dérogation | On ne s'autorise pas soi-même. |

Ces règles s'appliquent aussi en cas de délégation : le délégataire ne peut pas valider une opération qu'il a lui-même saisie.

## Validation

Matrice validée telle quelle le 13/11/2026, avec la règle « l'ordonnateur valide toujours ». Chaque établissement peut l'adapter par paramétrage.
