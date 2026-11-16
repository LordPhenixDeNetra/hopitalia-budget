---
title: Démonstration en ligne (Dokploy)
description: Déployer la démonstration sur un serveur géré par Dokploy, avec un Hopitalia simulé, sous budget.hopitalia.cloud et apibudget.hopitalia.cloud.
sidebar:
  order: 9
---

La démonstration en ligne fait tourner le module complet sur un serveur, avec un **Hopitalia simulé** et le jeu de démonstration : de quoi présenter la proposition à distance. Elle est décrite par `docker-compose.dokploy.yml` et ses variables par `.env.dokploy.example`.

:::caution[Données fictives seulement]
La démonstration ne se branche jamais sur un vrai Hopitalia et ne reçoit jamais de vraies données. Tous les comptes de démonstration partagent un mot de passe : ne le donner qu'aux personnes qui évaluent la proposition.
:::

| Adresse | Service | Contenu |
|---|---|---|
| `https://budget.hopitalia.cloud` | `web`, port 80 | L'application, et cette documentation sous `/docs/`. |
| `https://apibudget.hopitalia.cloud` | `api`, port 8000 | L'API `/api/v1`, et son interface Swagger sous `/api/v1/docs`. |

L'application n'a pas besoin du second domaine : elle appelle l'API par `/api/` sur sa propre adresse. Il sert aux intégrations.

## Ce que contient la pile

- Le module complet : base, API, interface, tâches planifiées, sauvegarde. Ses services sont recopiés de `docker-compose.yml`, car Dokploy ne suit pas `include` ; la CI vérifie que la copie reste identique.
- `hopitalia-simule` : connexion des agents, annuaire, fournisseurs, services et pharmacie, avec une clé de signature et un mot de passe **secrets**, fixés dans Dokploy.
- `courrier-test` : reçoit les courriels d'alerte ; rien ne part vers de vraies boîtes.
- `demonstration` : au **premier** démarrage, rejoue la recette blanche puis ajoute les pièces à valider, les alertes, l'échange en échec et les recettes, puis s'arrête. Aux déploiements suivants, il voit la base remplie et ne fait rien.

## Préparer

1. **DNS** : les enregistrements `A` de `budget.hopitalia.cloud` et `apibudget.hopitalia.cloud` pointent vers l'adresse IP du serveur.
2. **Secrets** : générer chacun sur un poste, et les garder dans un gestionnaire de mots de passe.

   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(48))"          # POSTGRES_PASSWORD, HOPITALIA_JWT_CLE, SIMULATION_MOT_DE_PASSE
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"   # COORDONNEES_CLE
   ```

## Créer l'application dans Dokploy

1. **Projet** : ouvrir (ou créer) le projet, puis **Create Service**, **Compose**. Nom : `hopitalia-budget`.
2. **Provider** : le dépôt GitHub `LordPhenixDeNetra/hopitalia-budget`, branche `main`. **Compose Path** : `./docker-compose.dokploy.yml`.
3. **Advanced** : activer **Isolated Deployment**. Sans lui, les services `api` et `db` partagent le réseau de Traefik avec les autres applications du serveur, et un service d'une autre application du même nom pourrait répondre à leur place.
4. **Environment** : recopier `.env.dokploy.example`, puis renseigner :
   - `POSTGRES_PASSWORD`, `COORDONNEES_CLE`, `HOPITALIA_JWT_CLE`, `SIMULATION_MOT_DE_PASSE` : les secrets générés ;
   - `HOPITALIA_COMPTE_TECHNIQUE_MOT_DE_PASSE` : la même valeur que `SIMULATION_MOT_DE_PASSE` ;
   - `ADRESSE_API`, `ADRESSE_WEB` : à changer seulement si les ports 18000 ou 18080 sont déjà pris sur le serveur.
5. **Domains** : ajouter deux domaines, HTTPS activé, certificat **Let's Encrypt**. Si `web` et `api` ne figurent pas dans la liste des services, cliquer sur le bouton d'actualisation à côté de la liste : Dokploy relit alors le fichier Compose du dépôt.

   | Host | Service | Container Port | Path |
   |---|---|---|---|
   | `budget.hopitalia.cloud` | `web` | `80` | `/` |
   | `apibudget.hopitalia.cloud` | `api` | `8000` | `/` |

6. **Deploy**. La première construction prend plusieurs minutes (trois images).

## Vérifier

- **Logs** du service `demonstration` : onze étapes « Conforme », puis « Démonstration prête ». Il s'arrête ensuite : c'est normal.
- `https://budget.hopitalia.cloud` : se connecter avec `agent002` et le mot de passe `SIMULATION_MOT_DE_PASSE`. Les comptes et leurs profils sont ceux de l'[environnement de démonstration](/docs/installer/demonstration/#comptes).
- `https://budget.hopitalia.cloud/docs/` : cette documentation.
- `https://apibudget.hopitalia.cloud/health` répond `{"statut":"ok"}`.

## Mettre à jour

Un nouveau déploiement (bouton **Deploy**, ou déploiement automatique à chaque fusion sur `main` si l'option est activée) reconstruit les images et applique les migrations ; les données de démonstration sont conservées.

## Repartir de zéro

Pour retrouver la démonstration dans son état initial, par exemple après une séance :

1. **Stop** l'application dans Dokploy.
2. Sur le serveur, supprimer le volume de la base de l'application : `docker volume ls | grep db-data`, puis `docker volume rm <nom du volume>`.
3. **Deploy** : la base est recréée et le service `demonstration` la remplit de nouveau.

## Changer le mot de passe des comptes

Modifier `SIMULATION_MOT_DE_PASSE` et `HOPITALIA_COMPTE_TECHNIQUE_MOT_DE_PASSE` (même valeur) dans **Environment**, puis **Deploy**.

## Sécurité

- La clé de signature et le mot de passe sont propres au serveur : ceux de l'environnement de démonstration sur un poste, publics, n'y donnent aucun accès.
- Seuls `web` et `api` sont publiés, par Traefik ; la base, le Hopitalia simulé et le serveur de courrier restent internes.
- nginx lit l'adresse du client transmise par Traefik : la limitation du débit et le journal d'audit voient l'adresse réelle de chaque agent.
- La boîte de courrier de test n'a pas d'adresse publique : elle n'a pas d'authentification.
