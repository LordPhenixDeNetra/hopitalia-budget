---
title: Intégrer
description: Relier un autre système au module par son API REST, et où trouver le contrat exact de chaque version.
sidebar:
  order: 1
---

Cette partie s'adresse aux équipes qui relient un autre système au module : lecture des données, création de pièces, échanges de fichiers.

## Documentation de référence

| Où | Contenu |
|---|---|
| `/api/v1/openapi.json` sur le serveur | Document OpenAPI 3.1 de la version en service : ressources, champs, codes d'erreur. |
| `/api/v1/docs` sur le serveur | Interface Swagger pour essayer l'API avec un jeton. |
| Versions GitHub du dépôt | Pour chaque version `vX.Y.Z` : `openapi-vX.Y.Z.json`, joint automatiquement. |

Le champ `info.version` du document OpenAPI est la version du module. La version d'API (`/api/v1`) ne change qu'en cas de rupture ; une version reste servie 12 mois après la suivante. Une version inconnue (`/api/v2/…`) répond `404`.

## Dans cette partie

- [Authentification](/docs/integrer/authentification/) : jetons, rafraîchissement, profils du compte d'un système.
- [Conventions](/docs/integrer/conventions/) : formats, pagination, filtres, idempotence, modifications, débit.
- [Erreurs](/docs/integrer/erreurs/) : format `problem+json` et codes stables.
- [Cas d'usage](/docs/integrer/cas-d-usage/) : les ressources à utiliser pour chaque besoin, et un exemple complet.
- [Fichiers d'import et d'export](/docs/integrer/fichiers/) : nomenclature, dotations, export du budget, écritures comptables.

Les échanges avec Hopitalia (fournisseurs, services, pharmacie) sont faits par le module lui-même ; ils ne passent pas par un client externe (voir [Intégrations](/docs/administrer/integrations/)).
