---
title: Mettre un établissement en service
description: L'ordre dans lequel l'administrateur fonctionnel paramètre un établissement, et la vérification de fin de paramétrage.
sidebar:
  order: 1
---

Cette partie s'adresse à l'administrateur fonctionnel du module (profil ADM). L'installation technique relève de [Installer et exploiter](/docs/installer/).

## Dans l'ordre

1. **Premier administrateur** : attribué sur le serveur, à l'installation (voir [Installation](/docs/installer/installation/#premier-administrateur)).
2. [Établissements](/docs/administrer/etablissements/) : créer l'établissement et ses sites, vérifier ses paramètres de calcul.
3. [Habilitations](/docs/administrer/habilitations/) : donner à chaque agent ses profils.
4. [Nomenclature et référentiels](/docs/administrer/referentiels/) : importer la nomenclature, créer les référentiels et l'exercice.
5. [Circuits de validation](/docs/administrer/circuits/) : garder les circuits par défaut ou les adapter.
6. [Règles d'alerte](/docs/administrer/alertes/) : seuils, délais, envois par courriel.
7. [Intégrations](/docs/administrer/integrations/) : vérifier les échanges avec Hopitalia.
8. Le responsable budgétaire crée ensuite le budget et importe ses dotations (voir [Budgets](/docs/utiliser/budgets/)) ; chaque agent crée ses [délégations](/docs/utiliser/delegations/) pour ses absences.

## Vérification de fin de paramétrage

Un établissement est prêt quand chaque point est « Oui » :

| Point | Oui / Non |
|---|---|
| L'exercice est ouvert. | |
| Les centres, sources et types de dépenses sont en place. | |
| Le budget est importé sans anomalie. | |
| Chaque profil de la matrice a au moins un agent. | |
| Un engagement d'essai passe son circuit jusqu'à l'ordonnateur. | |
| Le tableau de bord affiche les crédits attendus. | |

## Contrôle périodique

Chaque mois :

- les profils encore justifiés (agents partis, changements de poste) ;
- les délégations en cours ;
- les échanges avec Hopitalia en échec ;
- les alertes non lues anciennes.

Le [journal d'audit](/docs/utiliser/journal-audit/) retrace toute modification de donnée financière, les connexions et les exports ; chaque attribution ou retrait de profil y figure.
