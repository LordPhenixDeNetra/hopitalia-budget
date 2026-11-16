---
title: Mise à jour
description: Passer à une nouvelle version publiée, et revenir en arrière si elle pose problème.
sidebar:
  order: 5
---

Chaque version publiée porte une étiquette `vX.Y.Z` et son document OpenAPI. Fenêtre conseillée : hors des heures de saisie, jamais pendant la clôture d'un exercice.

1. Lire les [notes de version](/docs/versions/) et ce qu'elles demandent de faire avant.
2. Sauvegarder :

   ```bash
   docker compose exec sauvegarde sh /exploitation/sauvegarder.sh
   ```

3. Passer à la nouvelle version :

   ```bash
   git fetch --tags && git checkout vX.Y.Z
   docker compose up -d --build --wait
   ```

4. L'API applique les migrations à son démarrage ; `--wait` attend qu'elle et l'interface soient saines. Vérifier ensuite une connexion et l'ouverture du tableau de bord.

## Revenir en arrière

Une migration ne se défait pas sur une base en service. En cas de problème :

1. Revenir à l'étiquette précédente.
2. Restaurer la sauvegarde de l'étape 2 dans une base neuve (voir [Sauvegarde et restauration](/docs/installer/sauvegarde/#restaurer)).
3. Basculer l'API sur la base restaurée.

Les saisies faites entre la mise à jour et le retour en arrière sont à refaire.

## Avant chaque mise en production

L'équipe projet lance `npm audit` et `pip-audit` sur la version, et relit ses notes de version.
