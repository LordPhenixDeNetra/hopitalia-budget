---
title: Installer et exploiter
description: Ce qu'il faut pour installer le module sur un serveur de l'hôpital, et qui fait quoi pour le garder en état.
sidebar:
  order: 1
---

Cette partie s'adresse à la DSI de l'hôpital et à l'équipe projet. Elle couvre l'installation, la configuration, les sauvegardes, les mises à jour, la surveillance et la reprise après incident.

## Prérequis

| Besoin | Qui le fournit |
|---|---|
| Un serveur Linux avec Docker et Docker Compose : 2 processeurs, 4 Go de mémoire, 50 Go de disque (base, pièces et 30 jours de sauvegardes). | DSI de l'hôpital |
| Un nom d'hôte sur le réseau interne et un certificat TLS ; le proxy HTTPS de l'hôpital redirige vers le port 8080 du serveur. | DSI de l'hôpital |
| Un accès réseau du serveur vers l'API Hopitalia, la clé de vérification des jetons et un compte technique. | Équipe Hopitalia |
| Un serveur de messagerie pour les courriels d'alerte (facultatif). | DSI de l'hôpital |
| Une copie quotidienne des sauvegardes hors du serveur. | DSI de l'hôpital |

## Les étapes

1. [Installer](/docs/installer/installation/) le module et attribuer le premier administrateur.
2. [Configurer](/docs/installer/configuration/) les secrets et les variables du fichier `.env`.
3. Mettre en place les [sauvegardes](/docs/installer/sauvegarde/) et leur copie hors du serveur.
4. Confier l'établissement à l'administrateur du module, qui suit [Administrer](/docs/administrer/).

Ensuite : [mettre à jour](/docs/installer/mise-a-jour/), [surveiller et entretenir](/docs/installer/exploitation/), [reprendre après un incident](/docs/installer/incidents/).

Pour essayer le module sur un poste, sans serveur ni Hopitalia, voir l'[environnement de démonstration](/docs/installer/demonstration/) ; pour le présenter en ligne, la [démonstration sur Dokploy](/docs/installer/dokploy/).

## Responsabilités

| Qui | Rôle |
|---|---|
| DSI de l'hôpital | Serveur, proxy HTTPS et certificat, coffre des secrets, copie hors serveur, supervision, essais de restauration. |
| Équipe projet | Versions, migrations, correctifs, audit des dépendances, documentation. |
| Équipe Hopitalia | Compte technique, clé des jetons, disponibilité de l'API Hopitalia. |
| DAF | Décisions métier : recette, bascule après restauration, paramétrage validé. |
| Administrateur du module | Profils, référentiels, circuits, alertes, reprises d'échanges. |
