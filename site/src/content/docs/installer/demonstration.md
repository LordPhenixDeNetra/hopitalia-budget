---
title: Environnement de démonstration
description: Essayer le module sur un poste, avec un Hopitalia simulé, un serveur de courrier de test et des données d'exemple.
sidebar:
  order: 8
---

L'environnement de démonstration fait tourner le module complet sur un poste, sans serveur de l'hôpital ni Hopitalia réel. Il sert à présenter le module, à former les agents et à répéter la recette.

:::caution[Jamais en production]
Les comptes, le mot de passe `recette` et la clé de signature de cet environnement sont ceux des tests automatisés, publics. Ils ne valent que face à l'Hopitalia simulé.
:::

## Lancer

Depuis la racine du dépôt, l'environnement de développement arrêté (`docker compose stop`) pour libérer les ports :

```bash
docker compose -p hopitalia-budget-simulation -f docker-compose.yml -f docker-compose.simulation.yml down -v
docker compose -p hopitalia-budget-simulation -f docker-compose.yml -f docker-compose.simulation.yml up -d --build
cd backend && .venv/Scripts/python ../simulation/demonstration.py
```

Le script rejoue la recette blanche (le jeu d'essai de référence), puis ajoute des pièces en attente de visa, des alertes et leurs courriels, des commandes de la pharmacie à rattacher, un échange Hopitalia en échec et des recettes. Il s'arrête si la recette blanche n'est pas conforme.

| Accès | Adresse |
|---|---|
| Application | `http://127.0.0.1:8080` |
| Documentation | `http://127.0.0.1:8080/docs/` |
| Courriels envoyés (boîte de test) | `http://127.0.0.1:8025` |
| Hopitalia simulé | `http://127.0.0.1:8090` |

## Comptes

Mot de passe `recette` pour tous. Une fenêtre de navigation privée par compte permet de passer d'un profil à l'autre.

| Compte | Profil | Établissement |
|---|---|---|
| `agent001` | Administrateur fonctionnel (ADM) | Tous |
| `agent002` | Responsable budgétaire (RB) | CHU-A |
| `agent003` | Valideur, DAF (VAL) | CHU-A |
| `agent004` | Ordonnateur (ORD) | CHU-A |
| `agent006` | Lecteur (LEC) | CHU-B |
| `agent007` | Auditeur (AUD) | Tous |
| `agent011` | Gestionnaire de marchés et contrats (GMC) | CHU-A |
| `agent012` | Agent financier (AF) | CHU-A |
| `agent013` | Réceptionnaire (REC) | CHU-A |
| `agent014` | Comptable (CPT) | CHU-A |

## Ce qui est simulé

- **Hopitalia** : connexion, annuaire, 121 fournisseurs, 20 services, commandes et approvisionnements de la pharmacie. `POST /simulation/jour` fait passer un jour (fournisseur retiré, approvisionnement modifié ou supprimé, nouvelles commandes).
- **Messagerie** : les courriels arrivent dans la boîte de test, jamais dans de vraies boîtes.
- **Échanges** : la tâche quotidienne des échanges est arrêtée, pour qu'un échec reste visible jusqu'à sa reprise.

Les captures d'écran de cette documentation sont prises dans cet environnement.
