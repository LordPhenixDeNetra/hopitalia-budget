---
title: Architecture
description: Les services qui composent le module, leurs échanges avec Hopitalia, et où vivent les données.
sidebar:
  order: 4
---

Le module tourne sur une seule machine, avec Docker Compose. Chaque service est un conteneur :

| Service | Rôle |
|---|---|
| `web` | Interface (React), servie par nginx, avec cette documentation sous `/docs/`. Relaie `/api/` vers l'API. |
| `api` | API REST (FastAPI, Python) sous `/api/v1` : règles de gestion, contrôles, calculs, audit. Applique les migrations de la base à son démarrage. |
| `db` | Base PostgreSQL 16 `hopitalia_budget`. |
| `alertes` | Détection quotidienne des alertes planifiées (seuils des marchés, factures échues, engagements anciens, échéances). |
| `integrations` | Échanges quotidiens avec Hopitalia : fournisseurs, services, commandes de la pharmacie ; reprise des échecs. |
| `courriels` | Envoi des courriels d'alerte, chaque minute, avec reprise des échecs. |
| `sauvegarde` | Sauvegarde quotidienne de la base et des pièces justificatives. |

```
                Proxy HTTPS de l'hôpital
                          │
                    web (nginx) ──── /docs/ (cette documentation)
                          │ /api/
                         api ──────── db (PostgreSQL)
                          │
   alertes · integrations · courriels · sauvegarde
                          │
                      Hopitalia (connexion, référentiels, pharmacie)
```

## Échanges avec Hopitalia

| Sens | Quoi | Quand |
|---|---|---|
| Hopitalia vers le module | Connexion des agents : le module vérifie localement le jeton signé par Hopitalia. | À chaque connexion. |
| Hopitalia vers le module | Annuaire des agents (nom, code), pour attribuer les profils. | À l'attribution d'un profil. |
| Hopitalia vers le module | Fournisseurs et services (centres de responsabilité). | Chaque jour, ou à la demande. |
| Hopitalia vers le module | Commandes et approvisionnements de la pharmacie. | Chaque jour, ou à la demande. |

Un échange est journalisé ; un échec est repris de lui-même, puis depuis l'écran [Intégrations](/docs/administrer/integrations/). Sans Hopitalia, personne ne peut se connecter, mais aucune donnée n'est perdue.

## Où vivent les données

| Donnée | Emplacement |
|---|---|
| Budgets, pièces, journal d'audit | Base PostgreSQL (volume `db-data`). |
| Pièces justificatives déposées | Volume `pieces`, avec leur empreinte SHA-256 en base. |
| Sauvegardes | Volume `sauvegardes`, copié chaque jour hors du serveur par la DSI. |
| Secrets (mot de passe de la base, clés) | Fichier `.env` du serveur et coffre de la DSI, jamais dans le dépôt. |

Les numéros de compte bancaire des fournisseurs sont chiffrés en base et ne sont jamais réaffichés en entier.

## Sécurité

- Les ports de l'API et de l'interface n'écoutent que sur la machine elle-même ; seul le proxy HTTPS de l'hôpital est joignable.
- L'interface envoie des en-têtes de sécurité stricts (politique de contenu, interdiction d'intégration dans un cadre).
- Chaque requête est vérifiée : jeton valide, profil, établissement.
- Le débit est limité par agent (300 requêtes par minute par défaut).
