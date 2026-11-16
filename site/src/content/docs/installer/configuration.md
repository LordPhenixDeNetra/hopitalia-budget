---
title: Configuration
description: Les variables du fichier .env, les secrets à conserver dans le coffre de la DSI, et ce qui se passe quand l'un d'eux est perdu.
sidebar:
  order: 3
---

La configuration tient dans le fichier `.env` du serveur, créé depuis `.env.example`. Il n'est jamais versionné. Les secrets sont aussi conservés dans le coffre de la DSI, hors du serveur.

## Variables

| Variable | Secret | Rôle et perte |
|---|---|---|
| `POSTGRES_PASSWORD` | Oui | Mot de passe de la base. Se change sur la base, puis dans `.env`. |
| `COORDONNEES_CLE` | Oui | Chiffre les numéros de compte des fournisseurs. **Irremplaçable** : sans elle, les numéros sauvegardés sont illisibles et doivent être ressaisis. |
| `HOPITALIA_JWT_CLE` | Oui | Vérifie les jetons de connexion. Fournie par l'équipe Hopitalia, même valeur que la sienne. |
| `HOPITALIA_COMPTE_TECHNIQUE_MOT_DE_PASSE` | Oui | Mot de passe du compte technique. Se change dans Hopitalia, puis dans `.env`. |
| `HOPITALIA_API_URL`, `HOPITALIA_COMPTE_TECHNIQUE`, `HOPITALIA_ETABLISSEMENT` | Non | Adresse de l'API Hopitalia, compte technique, établissement cible des échanges. |
| `SMTP_MOT_DE_PASSE` | Oui | Compte d'envoi du serveur de messagerie. Se change chez la DSI, puis dans `.env`. |
| `SMTP_HOTE`, `SMTP_PORT`, `SMTP_STARTTLS`, `SMTP_UTILISATEUR`, `SMTP_EXPEDITEUR` | Non | Serveur de messagerie. Sans `SMTP_HOTE`, les courriels attendent en file. |
| `URL_APPLICATION` | Non | Adresse de l'interface, citée dans les courriels. |
| `RETENTION_JOURS` | Non | Durée de conservation des sauvegardes sur le serveur. Défaut : 30. |
| `INTEGRATION_FENETRE_JOURS` | Non | Période relue à chaque échange avec la pharmacie. Défaut : 30. |
| `LIMITE_REQUETES_PAR_MINUTE` | Non | Débit maximal par agent. Défaut : 300. |

Après une modification de `.env` : `docker compose up -d` recrée les services concernés.

:::danger[Ne jamais versionner .env]
Le dépôt est public. Le fichier `.env`, les clés et les mots de passe ne doivent jamais y entrer.
:::
