---
title: Prochaine version
description: Ce que contient la branche principale depuis la version 0.1.0, avant sa publication.
sidebar:
  order: 2
---

Changements fusionnés depuis la version 0.1.0, pas encore publiés.

## Nouveautés

- **Volet recettes**, activable par établissement : recettes prévues, facturé, encaissé, contre-mouvements motivés, reste à recouvrer, tableau de bord par nature, service et mois ; référentiel des débiteurs. Voir [Recettes](/docs/utiliser/recettes/).
- **Courriels d'alerte** : chaque agent donne son adresse dans l'écran Alertes ; l'administrateur choisit, règle par règle, les alertes envoyées par courriel (case « Par courriel » de l'onglet Règles). Le courriel est dans la langue de l'agent. Voir [Règles d'alerte](/docs/administrer/alertes/#courriels).
- **Documentation** servie par l'application sous `/docs/`, avec captures d'écran et recherche hors ligne.
- **Environnement de démonstration** sur un poste : Hopitalia simulé, serveur de courrier de test, données d'exemple. Voir [Environnement de démonstration](/docs/installer/demonstration/).

## Avant de mettre à jour

- Deux migrations de la base (0014 et 0015) s'appliquent au démarrage de l'API : sauvegarder avant.
- Pour envoyer les courriels, renseigner `SMTP_*` et `URL_APPLICATION` dans `.env` (voir [Configuration](/docs/installer/configuration/)). Sans serveur de messagerie, les courriels attendent en file ; rien n'est perdu.
- Un nouveau service `courriels` démarre avec `docker compose up -d --build`.
