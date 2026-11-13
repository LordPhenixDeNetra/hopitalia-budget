# Questionnaire pour l'équipe technique Hopitalia

**Projet :** Hopitalia Budget (`hopitalia-budget`), module de suivi budgétaire · **Date :** 13/11/2026

Ces réponses conditionnent le démarrage du développement : authentification, intégration de l'interface et échanges de données avec les autres modules d'Hopitalia. **Réponses reçues le 13/11/2026** pour les questions marquées ; les autres restent à compléter. Merci de compléter les zones « Réponse » et de joindre les documents demandés.

## 1. Authentification et utilisateurs

**Q-H01 — Fournisseur d'identité.** Hopitalia dispose-t-il d'un service de connexion commun à ses modules ? Si oui : quel protocole (OpenID Connect, SAML, LDAP, autre), quel produit (Keycloak, Active Directory…), et comment un nouveau module s'y déclare-t-il ?

> Réponse (13/11/2026) : pas de service de connexion commun ; le module gère ses propres comptes.

**Q-H02 — Profils et droits.** Les profils et droits des utilisateurs sont-ils gérés de façon centrale dans Hopitalia, ou chaque module gère-t-il les siens ?

> Réponse (13/11/2026, déduite de Q-H01) : sans objet : les comptes, profils et droits sont gérés dans le module.

## 2. Interface

**Q-H03 — Interface existante.** Hopitalia a-t-il une interface web ? Si oui : quelle technologie (React, Angular, Vue…), dans quel dépôt de code, et le module doit-il s'y intégrer (menu commun, même application) ou être une application séparée accessible par un lien ?

> Réponse (13/11/2026) : application séparée, accessible par un lien depuis Hopitalia.

**Q-H04 — Charte graphique.** Existe-t-il une charte Hopitalia (logo, couleurs, polices) à respecter ?

> Réponse :

## 3. Données et échanges

**Q-H05 — Référentiels.** Les fournisseurs, services hospitaliers, établissements et sites existent-ils déjà dans Hopitalia ? Si oui : par quelle API les lire, avec quel identifiant unique, et à quelle fréquence changent-ils ?

> Réponse (13/11/2026) : ces référentiels n'existent pas dans Hopitalia ; ils sont créés et gérés dans le module.

**Q-H06 — Stocks et pharmacie.** Le module stocks expose-t-il une API pour recevoir les réceptions validées (entrées en stock) et rapprocher commandes et livraisons ?

> Réponse (13/11/2026) : oui, le module stocks et pharmacie dispose d'une API.

**Q-H07 — Facturation et recouvrement.** Pour le volet recettes, quelle API permet de lire les montants facturés et encaissés (par nature, service, période) ?

> Réponse (13/11/2026) : oui, la facturation patient dispose d'une API.

**Q-H08 — Documentation.** Merci de joindre la documentation des API concernées (OpenAPI, Postman ou autre) et d'indiquer un environnement de test accessible.

> Réponse :

## 4. Hébergement

**Q-H09 — Base de données.** Quelle base de données Hopitalia utilise-t-il ? Le module prévoit PostgreSQL : est-ce compatible avec votre exploitation ?

> Réponse :

**Q-H10 — Infrastructure.** Où le module sera-t-il hébergé (serveurs de l'hôpital, centre de données, nuage) ? Les conteneurs Docker sont-ils autorisés ? L'accès à Internet depuis les serveurs est-il filtré ?

> Réponse (13/11/2026) : serveurs de l'hôpital, sur le réseau hospitalier. Docker et filtrage d'Internet : à préciser.

**Q-H11 — Établissements.** Quels établissements et sites seront concernés au premier déploiement ?

> Réponse :

## 5. Contact

**Q-H12 — Interlocuteur technique.** Qui contacter pour les questions d'intégration (nom, fonction, courriel) ?

> Réponse :
