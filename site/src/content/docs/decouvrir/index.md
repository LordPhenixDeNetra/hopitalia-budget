---
title: Présentation
description: Ce que fait Hopitalia Budget, ce qu'il ne fait pas, pour qui, et comment il s'insère dans Hopitalia.
sidebar:
  order: 1
---

Hopitalia Budget est le module de gestion et de suivi budgétaire de la solution hospitalière Hopitalia. Il suit chaque dépense de l'établissement, du crédit voté jusqu'au paiement, et en tire des tableaux de bord, des alertes et des états.

## Ce que fait le module

- **Crédits** : budget de l'exercice, dotations par ligne, notifications de crédits, révisions (virements, augmentations, diminutions), disponible toujours recalculé.
- **Marchés et contrats** : enregistrement des marchés déjà attribués et des contrats déjà signés, avenants, échéancier, consommation du plafond.
- **Chaîne de dépense** : engagement, bon de commande, réception et service fait, facture, liquidation, ordonnancement, paiement.
- **Contrôles** : crédit disponible, plafond du marché, doublons, seuil hors marché, service fait, solde dû. Un dépassement est bloqué, sauf dérogation accordée.
- **Validation** : chaque pièce passe un circuit de visas paramétrable, avec séparation des tâches et délégations.
- **Pilotage** : tableau de bord, alertes (aussi par courriel), états à imprimer ou exporter, recherche, journal d'audit, clôture d'exercice.
- **Recettes** (volet activable) : recettes prévues, facturé, encaissé, reste à recouvrer.

## Ce qu'il ne fait pas

Le module suit les marchés **déjà attribués** et les contrats **déjà signés**. Il ne lance, n'évalue et n'attribue aucun marché (règle RG-12) : la passation reste en dehors.

Il ne tient pas la comptabilité générale : il produit un fichier d'écritures à importer dans le logiciel comptable (voir [Fichiers d'import et d'export](/docs/integrer/fichiers/)).

## Pour qui

| Qui | Ce qu'il y fait |
|---|---|
| Direction administrative et financière (DAF) | Vise les pièces, suit l'exécution du budget, accorde les dérogations. |
| Responsable budgétaire | Prépare le budget, demande les révisions, clôture l'exercice. |
| Gestionnaire des marchés | Enregistre les contrats et les avenants, demande les engagements, émet les commandes. |
| Agent financier | Contrôle les engagements, enregistre et liquide les factures. |
| Services | Demandent des engagements, réceptionnent les livraisons. |
| Ordonnateur et comptable | Ordonnancent et paient. |
| Auditeur, lecteurs | Consultent, sans rien modifier. |

Le détail par profil est dans [Profils et droits](/docs/decouvrir/profils/).

## Place dans Hopitalia

Hopitalia Budget est une application séparée, ouverte depuis Hopitalia et installée sur les serveurs de l'hôpital.

- **Connexion** : les agents se connectent avec leur compte Hopitalia. Le module n'a pas de mot de passe propre.
- **Droits** : les profils budgétaires sont propres au module. Un administrateur du module les attribue.
- **Données partagées** : les fournisseurs, les services et les commandes de la pharmacie sont importés d'Hopitalia, jamais ressaisis.
- **Comptabilité** : les comptes suivent le plan SYSCOHADA révisé.

Le fonctionnement technique est décrit dans [Architecture](/docs/decouvrir/architecture/).
