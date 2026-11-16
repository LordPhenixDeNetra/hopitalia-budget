---
title: Concepts
description: La chaîne de dépense, les indicateurs calculés, les circuits de validation, les contrôles et les dérogations, l'immuabilité des pièces validées.
sidebar:
  order: 2
---

## La chaîne de dépense

Une dépense franchit des étapes successives, chacune portée par une pièce :

| Étape | Pièce | Ce qu'elle prouve |
|---|---|---|
| Crédit | Ligne budgétaire | L'argent est prévu au budget de l'exercice. |
| Engagement | Engagement | L'établissement réserve le crédit pour une dépense précise. |
| Commande | Bon de commande | Le fournisseur est sollicité, dans la limite de l'engagement. |
| Réception | Réception validée | Le service fait est constaté. |
| Facture | Facture | Le fournisseur réclame son dû. |
| Liquidation | Liquidation | Le montant dû est arrêté, appuyé sur le service fait. |
| Ordonnancement | Mandat ou ordre de paiement | L'ordonnateur transmet la dépense au comptable. |
| Paiement | Paiement | Le comptable règle le fournisseur. |

:::caution[Les étapes ne s'additionnent pas]
Engagé, commandé, réceptionné, facturé, liquidé, transmis et payé sont des **étapes d'une même dépense**. Une facture de 10 M liquidée puis payée compte 10 M engagés, 10 M liquidés et 10 M payés, jamais 30 M.
:::

## Des indicateurs calculés, jamais saisis

Engagé, liquidé, payé, restes et disponibles sont **calculés à partir des pièces** à chaque affichage (règle RG-14). Personne ne les saisit, et ils ne peuvent pas diverger des pièces. Chaque indicateur a une seule définition, la même dans le tableau de bord, les fiches et les états.

Par ligne budgétaire :

| Indicateur | Définition |
|---|---|
| Budget révisé | Budget initial + révisions validées qui créditent la ligne − révisions validées qui la débitent. |
| Engagé | Engagements validés imputés sur la ligne, moins leurs annulations. |
| En cours de validation | Engagements soumis ou en contrôle, pas encore validés. |
| Disponible | Budget révisé − engagé. |
| Disponible prévisionnel | Disponible − en cours de validation (réglable par établissement). |
| Liquidé | Consommation budgétaire des liquidations validées. |
| Payé | Paiements exécutés affectés aux liquidations de la ligne. |
| Reste à payer | Nets à payer des liquidations validées − payé. |

Par contrat : montant actualisé (initial + avenants validés), engagé, reste à engager, commandé, réceptionné, facturé, liquidé, payé, et **taux de consommation** (engagé / montant actualisé), qui déclenche les alertes à 80, 90 et 100 %.

Par liquidation : montant liquidé, déductions (retenue de garantie, retenue à la source, avance récupérée, autres retenues), **net à payer** = liquidé − déductions.

## Circuits de validation

Une pièce se saisit en brouillon, se **soumet**, puis passe les étapes de son **circuit** : à chaque étape, un agent du profil prévu la vise, la rejette ou la retourne pour correction. À la dernière étape, l'opération prend effet.

| Pièce | Circuit par défaut |
|---|---|
| Engagement | Contrôle financier (agent financier), visa DAF (valideur), ordonnateur. |
| Révision, contrat, avenant, dérogation, liquidation | Visa DAF (valideur), ordonnateur. |
| Réception (service fait) | Valideur du service. |

Un établissement peut paramétrer ses circuits par service et par tranche de montant (voir [Circuits de validation](/docs/administrer/circuits/)). L'ordonnateur valide toujours en dernier.

**Séparation des tâches** (RG-13) : on ne vise jamais sa propre pièce ; celui qui valide une liquidation ne la paie pas ; l'ordonnateur et le comptable sont distincts. La règle vaut aussi par délégation.

## Contrôles et dérogations

À la soumission puis à la validation, le module contrôle automatiquement la pièce :

- crédit disponible sur chaque ligne (RG-02) ;
- plafond du marché (RG-04) ;
- contrat validé, bénéficiaire égal au titulaire ;
- engagement en doublon probable : même bénéficiaire, même montant, même objet, à moins de 30 jours ;
- facture en doublon : même fournisseur, et même numéro ou même date d'émission et même montant (RG-16) ;
- seuil des achats hors marché ;
- service fait avant liquidation (RG-06) ;
- paiement dans la limite du solde dû (RG-07).

Un écart bloque la pièce. Il se corrige, ou se couvre par une **dérogation** validée par son propre circuit. Une dérogation ne couvre que la nature, l'objet et le montant accordés (RG-19).

Le contrôle du crédit et l'enregistrement de l'engagement sont **atomiques** (RG-20) : deux engagements simultanés ne consomment jamais le même crédit.

## Une pièce validée ne se modifie plus

Une opération validée est **immuable** (RG-18). Une erreur se corrige par une opération tracée : annulation partielle ou totale d'un engagement, annulation motivée d'un paiement, contre-mouvement négatif sur une recette. L'historique reste lisible, et chaque modification de donnée financière est écrite dans le **journal d'audit**.

## Établissements et cloisonnement

Chaque agent travaille dans son périmètre : le ou les établissements où ses profils s'appliquent. Le serveur vérifie ce périmètre à chaque requête. Un agent d'un autre établissement ne voit rien, même en connaissant l'adresse d'une fiche.

## Exercice et clôture

Toute dépense est rattachée à un exercice et à une imputation budgétaire (RG-01). À la clôture, le reliquat non liquidé de chaque engagement est reporté sur l'exercice suivant ; rien n'est supprimé (RG-10). Voir [Clôture d'exercice](/docs/utiliser/cloture-exercice/).
