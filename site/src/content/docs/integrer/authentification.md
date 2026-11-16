---
title: Authentification
description: Obtenir et rafraîchir un jeton avec un compte Hopitalia, et donner au compte d'un système ses profils budgétaires.
sidebar:
  order: 2
---

Le module n'a pas de comptes propres : un client s'authentifie avec un compte **Hopitalia**.

```http
POST /api/v1/auth/connexion
Content-Type: application/json

{"identifiant": "svc-integration", "motDePasse": "…"}
```

La réponse donne :

| Champ | Contenu |
|---|---|
| `jetonAcces` | À envoyer à chaque appel : `Authorization: Bearer <jetonAcces>`. |
| `expireDans` | Durée de validité du jeton d'accès, en secondes. |
| `jetonRafraichissement` | Pour obtenir une nouvelle paire avant expiration. |

- **Rafraîchir** : `POST /api/v1/auth/rafraichissement` avec `{"jetonRafraichissement": "…"}`.
- **Se déconnecter** : `POST /api/v1/auth/deconnexion` révoque le jeton de rafraîchissement.

## Droits

Les droits viennent du module, pas d'Hopitalia. Un administrateur du module attribue au compte du client ses profils et ses établissements, dans l'écran [Habilitations](/docs/administrer/habilitations/). Un compte sans profil reçoit `403 AUCUN_PROFIL`.

Donner au compte d'un système le **profil le plus étroit qui suffit** :

| Besoin | Profil |
|---|---|
| Lire les tableaux de bord et les états | `LEC` |
| Tout lire, journal d'audit compris | `AUD` |
| Créer des engagements | `GMC` ou `SD` |
| Autre saisie | Le profil de saisie de la [matrice](/docs/decouvrir/profils/#matrice-des-habilitations). |

Le compte reste soumis au cloisonnement par établissement et à la séparation des tâches.
