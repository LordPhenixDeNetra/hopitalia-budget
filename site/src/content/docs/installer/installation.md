---
title: Installation
description: Installer le module sur un serveur avec Docker Compose, vérifier l'installation et attribuer le premier administrateur.
sidebar:
  order: 2
---

L'environnement de recette et la production s'installent de la même façon, chacun avec ses propres secrets : jamais ceux de l'autre.

## Installer

1. Cloner le dépôt sur le serveur, à l'étiquette de la version à installer :

   ```bash
   git clone https://github.com/LordPhenixDeNetra/hopitalia-budget.git
   cd hopitalia-budget
   git checkout vX.Y.Z
   ```

2. Créer le fichier `.env` depuis `.env.example`, puis le renseigner (voir [Configuration](/docs/installer/configuration/)) :
   - un `POSTGRES_PASSWORD` long et aléatoire ;
   - `COORDONNEES_CLE`, avec la commande indiquée dans `.env.example`, et sa copie dans le coffre de secrets de la DSI ;
   - l'accès à Hopitalia (`HOPITALIA_*`).

3. Construire et démarrer :

   ```bash
   docker compose up -d --build --wait
   ```

   L'API applique les migrations de la base à son démarrage. `--wait` rend la main quand l'API et l'interface sont saines, ou signale celle qui ne l'est pas ; les tâches planifiées démarrent une fois l'API saine.

## Vérifier

- `docker compose ps` : tous les services sont démarrés ; `api`, `web` et `db` sont `(healthy)`.
- `curl http://127.0.0.1:8000/health` répond.
- `docker compose logs sauvegarde` montre une première sauvegarde.
- L'interface s'ouvre par le nom d'hôte, en HTTPS ; la documentation est sous `/docs/`.
- `curl -I` sur l'interface montre l'en-tête `Content-Security-Policy`.
- Le port 8000 n'est pas joignable depuis un autre poste : les ports 8000 et 8080 n'écoutent que sur `127.0.0.1`, seul le proxy HTTPS est joignable.

## Les images

| Image | Construite depuis | Contenu |
|---|---|---|
| `hopitalia-budget-api` | `backend/` | Python 3.12 : l'API, ses migrations et ses tâches planifiées (`alertes`, `courriels`, `integrations`). Utilisateur sans privilège `app`. |
| `hopitalia-budget-web` | Racine du dépôt (`frontend/Dockerfile`) | nginx : l'interface construite et cette documentation, sous `/docs/`. |

Les fichiers `.dockerignore` sont des **listes blanches** : n'entre dans une image que ce qui sert à la construire. Les tests, les outils de développement, les documents du projet et le fichier `.env` n'y entrent jamais.

Les images de PostgreSQL et de la sauvegarde sont les images officielles `postgres:16-alpine`.

## Premier administrateur

La connexion passe par Hopitalia, mais les droits sont propres au module : un agent sans profil est refusé. Le tout premier profil d'administrateur s'attribue sur le serveur, avec l'identifiant Hopitalia de l'agent (`userId`) et son code :

```bash
docker compose exec api python -m hopitalia_budget.outils.habiliter \
  --utilisateur-id 42 --code-agent AG042 --profil ADM
```

Les profils suivants s'attribuent dans l'écran [Habilitations](/docs/administrer/habilitations/). Un administrateur ne peut pas modifier ses propres profils.

L'administrateur suit ensuite [la mise en service d'un établissement](/docs/administrer/).

## Adresses

| Service | Adresse sur le serveur |
|---|---|
| Interface | `http://127.0.0.1:8080` |
| Documentation | `http://127.0.0.1:8080/docs/` |
| API | `http://127.0.0.1:8000` (santé : `/health`) |
| PostgreSQL | Interne au réseau Docker. |

## Arrêter

`docker compose down` arrête le module. Avec `-v`, la base, les pièces et les sauvegardes sont **effacées** : ne jamais l'utiliser en production.
