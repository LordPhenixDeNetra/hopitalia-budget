---
title: Conventions
description: Format JSON, montants, langue, pagination, filtres, idempotence des créations, modifications conditionnelles, débit et suivi des requêtes.
sidebar:
  order: 3
---

| Sujet | Règle |
|---|---|
| Ressources | Au pluriel, sous `/api/v1` : `/engagements`, `/factures`, `/lignes-budgetaires/{id}`. |
| Format | JSON en `camelCase`. Dates `AAAA-MM-JJ`, horodatages ISO 8601 avec fuseau. |
| Montants | En **chaîne décimale** (`"1500000.00"`), jamais en nombre flottant. Francs CFA, deux décimales au plus. |
| Langue | `Accept-Language: fr` ou `en` : messages d'erreur et états dans la langue demandée ; les données métier ne changent pas. |
| Pagination | Listes : `?page=1&taille=25` (100 au plus) ; la réponse donne `pagination.total` et `pagination.suivant` (adresse de la page suivante). Journaux et alertes : curseur, `?apres=<curseur>` avec `pagination.suivant`. |
| Filtres | Seuls les paramètres documentés sont acceptés ; un paramètre inconnu répond `400`. |
| Opération validée | Elle n'est plus modifiable (RG-18) : une correction passe par une annulation ou une contre-opération. |

## Créer : clé d'idempotence

Tout `POST` qui crée une pièce financière exige l'en-tête `Idempotency-Key: <uuid>` :

- une clé par opération métier, réutilisée telle quelle en cas de nouvel essai ;
- la même clé avec le même corps renvoie la réponse d'origine (conservée 24 heures) ;
- la même clé avec un autre corps répond `422 IDEMPOTENCE_CONFLIT`.

Après une coupure réseau, renvoyer la même requête avec la même clé : la pièce n'est créée qu'une fois.

## Modifier : version lue

1. Lire la fiche : la réponse porte l'en-tête `ETag`.
2. Envoyer le `PATCH` avec `If-Match: <ETag>`.

Sans en-tête : `428 PRECONDITION_REQUISE`. Si la fiche a changé entre-temps : `412 PRECONDITION_ECHOUEE` ; la relire, puis recommencer.

## Débit

300 requêtes par minute et par compte. Chaque réponse porte `RateLimit-Limit`, `RateLimit-Remaining` et `RateLimit-Reset`. Au-delà : `429 LIMITE_DEBIT`, avec `Retry-After` (en secondes).

## Suivi

Envoyer `X-Request-ID` pour retrouver un appel dans les journaux du serveur ; il est renvoyé dans la réponse. Le donner à l'exploitation pour toute erreur signalée.
