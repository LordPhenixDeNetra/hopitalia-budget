---
title: Profils et droits
description: Les onze profils budgétaires, ce que chacun peut faire, et la matrice des habilitations.
sidebar:
  order: 3
---

Un agent reçoit un ou plusieurs **profils budgétaires**, chacun pour un établissement ou pour tous. Le menu ne montre que ce que ses profils permettent, et le serveur refuse le reste.

| Code | Profil | En bref |
|---|---|---|
| ADM | Administrateur fonctionnel | Paramètre le module : établissements, habilitations, référentiels, circuits, alertes, échanges avec Hopitalia. |
| RB | Responsable budgétaire | Prépare le budget, importe les dotations, demande les révisions, clôture l'exercice, gère les recettes. |
| GMC | Gestionnaire de marchés et contrats | Enregistre les contrats et les avenants, demande les engagements, émet les commandes. |
| SD | Service demandeur | Demande les engagements de son service et suit leurs commandes. |
| AF | Agent financier | Contrôle les engagements, rattache les commandes de la pharmacie, enregistre et liquide les factures, annule les engagements. |
| REC | Réceptionnaire | Enregistre les réceptions et joint le bon de livraison. |
| VAL | Valideur (responsable de service, DAF) | Vise les pièces, valide le service fait, accorde les dérogations. |
| ORD | Ordonnateur | Valide en dernier, ordonnance les paiements, clôture l'exercice. |
| CPT | Comptable, agent de paiement | Prend en charge les ordonnancements et enregistre les paiements. |
| AUD | Auditeur | Consulte tout, journal d'audit compris, sans rien modifier. |
| LEC | Lecteur de tableaux de bord | Consulte le tableau de bord et les états de son établissement. |

## Matrice des habilitations

S : saisir ; V : valider ; L : consulter ; — : aucun accès.

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
| Gérer les recettes (prévisions, facturé, encaissé) | — | S | S | — | — | — | L | L | S | L | — |

La matrice de référence est produite depuis le code : `docs/conception/workflows-et-habilitations.md` dans le dépôt, avec le détail de chaque circuit et de chaque cycle de vie.

## Cumul de profils

Un agent peut cumuler des profils, par exemple valideur et ordonnateur. La **séparation des tâches** s'applique quand même : il ne vise pas une pièce qu'il a saisie, et il ne paie pas une liquidation qu'il a validée.

Pour une même opération, une même personne ne peut pas cumuler :

| Rôle 1 | Rôle 2 |
|---|---|
| Demander l'engagement | Valider l'engagement |
| Contrôler l'engagement | Valider l'engagement |
| Enregistrer la réception | Valider le service fait |
| Liquider | Valider la liquidation |
| Valider la liquidation | Enregistrer le paiement |
| Ordonnancer | Enregistrer le paiement |
| Demander une dérogation | Accorder la dérogation |
