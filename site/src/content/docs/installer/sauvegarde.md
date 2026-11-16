---
title: Sauvegarde et restauration
description: Ce qui est sauvegardé, la copie hors du serveur, la restauration dans une base neuve et l'essai trimestriel.
sidebar:
  order: 4
---

## Ce qui est sauvegardé

| Donnée | Où elle vit | Fichier de sauvegarde |
|---|---|---|
| Base PostgreSQL : budgets, pièces comptables, journal d'audit | Volume `db-data` | `base-<horodatage>.dump` (`pg_dump`, format personnalisé) |
| Pièces justificatives déposées | Volume `pieces` | `pieces-<horodatage>.tar.gz` |
| Clés `COORDONNEES_CLE` et `HOPITALIA_JWT_CLE` | Fichier `.env` du serveur | **Hors de ce dispositif** : dans le coffre de secrets de la DSI. |

## Fonctionnement

- Le service `sauvegarde` lance `exploitation/sauvegarder.sh` à son démarrage, puis toutes les 24 heures.
- Les fichiers vont dans le volume `sauvegardes`. Un fichier ne prend son nom définitif qu'une fois complet.
- Rétention : `RETENTION_JOURS` (30 jours par défaut) ; au-delà, les fichiers sont supprimés.
- Sauvegarde à la demande :

  ```bash
  docker compose exec sauvegarde sh /exploitation/sauvegarder.sh
  ```

| Élément | Valeur |
|---|---|
| Fréquence | Quotidienne, plus avant chaque mise à jour. |
| Perte de données maximale | 24 heures (dernière sauvegarde). |
| Rétention sur le serveur | 30 jours. |
| Essai de restauration | Chaque trimestre, chronométré, noté au registre d'exploitation (ENF-06). |

:::caution[Copie hors du serveur]
Le volume `sauvegardes` est sur le même disque que la base. La DSI le copie chaque jour vers un autre support. Sans cette copie, une panne du serveur emporte la base et ses sauvegardes.
:::

## Restaurer

Toujours dans une base neuve, jamais par-dessus la base en service :

```bash
docker compose exec sauvegarde psql -d postgres -c "CREATE DATABASE hopitalia_budget_restauree"
docker compose exec sauvegarde sh /exploitation/restaurer.sh <horodatage> hopitalia_budget_restauree
```

Ensuite :

1. Vérifier la base restaurée : nombre de lignes des tables principales, dernière ligne du journal d'audit.
2. Arrêter `api` et `alertes`.
3. Pointer `POSTGRES_DB` vers la base restaurée.
4. Pour les pièces, relancer la restauration avec `RESTAURER_PIECES=oui`, API arrêtée.
5. Redémarrer `api` et `alertes`.

Les migrations s'appliquent au démarrage de l'API : une sauvegarde d'une version antérieure est mise à niveau automatiquement.

## Essai trimestriel

Une fois par trimestre, la DSI restaure la dernière sauvegarde dans une base neuve, refait les vérifications ci-dessus et note la date et la durée dans le registre d'exploitation.

Essais de référence du 15/11/2026, avec `restaurer.sh`, sur PostgreSQL 16, sur un poste de développement :

| Essai | Volume | Durée de restauration | Vérification |
|---|---|---|---|
| Base de développement | 10 Mo, schéma seul | 3 s | Nombre de lignes identique, table par table. |
| Un exercice complet | 17 Mo une fois restaurée (sauvegarde de 1,2 Mo) : 2 000 engagements, commandes, réceptions, factures et liquidations, 1 000 paiements | 4 s | Nombre de lignes de chaque table égal au jeu chargé. |

La durée sur le serveur de l'hôpital se mesure au premier essai trimestriel.
