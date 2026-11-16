---
title: Reprise après incident
description: Que faire quand un service s'arrête, qu'Hopitalia est indisponible, qu'une donnée est erronée, ou que le serveur est perdu.
sidebar:
  order: 7
---

| Incident | Effet | Reprise |
|---|---|---|
| Un service s'arrête | Selon le service. | Redémarrage automatique ; sinon `docker compose up -d`. Lire `docker compose logs <service>`. |
| Hopitalia indisponible | Connexion impossible ; échanges en échec. | Rien à faire côté module : les échanges sont repris d'eux-mêmes (cinq tentatives), puis depuis l'écran [Intégrations](/docs/administrer/integrations/). |
| Erreur de saisie ou donnée altérée | Selon le cas. | D'abord la correction métier : annulation ou contre-opération tracée. Sinon, restaurer dans une base neuve, comparer, et ne basculer qu'avec l'accord de la DAF. |
| Base corrompue | Module arrêté. | Restaurer la dernière sauvegarde dans une base neuve et basculer l'API ([Sauvegarde et restauration](/docs/installer/sauvegarde/#restaurer)). Les saisies faites depuis la sauvegarde sont à refaire. |
| Perte du serveur | Module arrêté. | Nouveau serveur ([Installation](/docs/installer/installation/)), `.env` reconstitué depuis le coffre de la DSI, restauration de la dernière copie hors serveur (base et pièces). |
| Clé `COORDONNEES_CLE` perdue | Numéros de compte illisibles. | Nouvelle clé, puis ressaisie des coordonnées bancaires des fournisseurs. Le reste des données n'est pas touché. |
| Courriels qui n'arrivent pas | Les alertes restent visibles dans l'application. | Vérifier `SMTP_*` et `docker compose logs courriels` ; les courriels en échec sont repris jusqu'à cinq tentatives. |

## Une erreur signalée par un utilisateur

1. Lui demander l'heure, l'écran, le message affiché et, s'il est visible, le code d'erreur.
2. Retrouver la requête dans `docker compose logs api` par son heure ou son `X-Request-ID`.
3. Une erreur interne (`500 ERREUR_INTERNE`) ne montre aucun détail à l'utilisateur : le détail est dans les journaux.
