# Points reportés

| Date | Point | Raison | Quand le traiter |
|---|---|---|---|
| 2026-11-14 | Limitation de débit en mémoire, un compteur par processus API. | Suffisant avec un seul processus (déploiement actuel). | Si l'API tourne avec plusieurs processus : compteurs partagés (Redis). |
| 2026-11-14 | La règle de lint des textes en dur ne voit ni les composants en fonction fléchée à retour implicite, ni les attributs comme `aria-label`. | Limite du plugin `eslint-plugin-i18next` ; contournée par la convention « composants en `function` » (AGENTS.md) et la revue. | Si un texte en dur passe en revue : écrire une règle maison. |
| 2026-11-14 | Composant `List` d'Ant Design déprécié depuis la version 6.6 (remplacé par `Listy`), utilisé par l'accueil et les listes sur petit écran. | Fonctionne ; avertissement seulement en développement. | Avant la version majeure suivante d'Ant Design. |
| 2026-11-14 | Paquet JavaScript principal au-delà de 500 ko (avertissement de Vite). | Ant Design dans un seul paquet ; sans effet mesuré pour l'instant. | Quand les écrans métier arrivent (lot 1) : chargement des pages à la demande. |
| 2026-11-14 | Les clés d'idempotence expirées restent en base (elles sont seulement remplacées si la même clé revient). | Volume négligeable au démarrage. | Avec les tâches planifiées (T-222) : purge périodique. |
| 2026-11-14 | Le notificateur écrit dans le journal, sans envoyer de courriel. | Aucune alerte n'existe encore. | T-225 (notifications par courriel). |
| 2026-11-14 | Avertissement de dépréciation de Starlette sur `httpx` dans le client de test. | Vient de la bibliothèque, pas du code du projet. | Quand Starlette publiera sa recommandation stable. |
