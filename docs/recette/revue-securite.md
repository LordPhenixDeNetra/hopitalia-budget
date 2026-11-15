# Revue de sécurité

**Projet :** Hopitalia Budget · **Tâche :** T-252 · **Date :** 15/11/2026 · **Référence :** cahier des charges V3, ENF-03 et section 11

Grille de contrôle inspirée du Top 10 OWASP, vérifiée sur le code, les dépendances et la configuration de déploiement. Le dépôt est public : ce document dit ce qui a été vérifié et le résultat, sans détail exploitable. Les constats se signalent en privé à l'équipe du projet, jamais dans un ticket public.

**Résultat :** aucune faille critique ouverte. Trois points de durcissement ont été corrigés pendant la revue (voir plus bas) ; chacun a son test ou sa vérification.

## Grille

| Domaine | Vérification | Résultat |
|---|---|---|
| Contrôle d'accès | Chaque route de l'API exige un utilisateur authentifié et habilité, sauf la connexion, le rafraîchissement, la déconnexion et `/health` (inventaire automatique des routes). Cloisonnement par établissement vérifié côté serveur (tests `test_lecteur_ne_voit_que_son_etablissement`, `test_liste_filtres_et_cloisonnement`, `test_revisions_cloisonnees_et_tracees` et suivants). | Conforme. |
| Authentification | Jetons Hopitalia vérifiés localement : algorithme fixé, expiration et sujet obligatoires, clé hors dépôt (variable d'environnement). | Conforme. |
| Chiffrement | Numéros de compte des fournisseurs chiffrés en base (Fernet, clé `COORDONNEES_CLE` hors dépôt), jamais renvoyés en clair. | Conforme. |
| Injection | Requêtes construites par SQLAlchemy ; la seule expression SQL écrite à la main est une constante. Filtres et tris sur liste blanche (section 11). | Conforme. |
| Fichiers déposés | Types de fichier sur liste blanche, taille limitée, contenu rangé sous son empreinte ; téléchargement en pièce jointe, sans interprétation par le navigateur. | Conforme. |
| Erreurs | Erreurs au format `problem+json` avec code stable ; une erreur inattendue renvoie un message générique, le détail reste dans le journal du serveur. | Conforme. |
| Limitation de débit | Compteur par utilisateur authentifié, sinon par adresse du client (section 11.7). | Corrigé pendant la revue (point 1). |
| En-têtes HTTP | Politique de sécurité du contenu, interdiction de l'affichage en cadre, pas de devinette du type, politique de référent, version du serveur masquée. | Corrigé pendant la revue (point 2). |
| Proxy | Adresse réelle du client transmise par le proxy, non falsifiable par le client. | Corrigé pendant la revue (point 3). |
| Dépendances | `npm audit` (frontend, production et développement) et `pip-audit` (backend) : aucune vulnérabilité connue. Un outil de développement (analyse de code TypeScript) tirait une version vulnérable d'une bibliothèque ; version forcée par `overrides` dans `frontend/package.json`. | Conforme. |
| Secrets | Aucun secret versionné (recherche dans le dépôt) ; `.env` exclu par `.gitignore`, `.env.example` sans valeur. | Conforme. |
| Journal d'audit | Toute modification de donnée financière tracée dans la même transaction (tests de piste d'audit de chaque lot, REC-12 notamment). | Conforme. |

## Points corrigés pendant la revue

1. **Limitation de débit.** Le compteur d'un utilisateur repose désormais sur un jeton dont la signature est vérifiée. Test : `test_limite_de_debit_jeton_forge`.
2. **En-têtes HTTP.** Ajoutés dans `frontend/nginx.conf`. La politique de sécurité du contenu admet les styles en ligne, qu'Ant Design injecte à l'exécution ; aucun script en ligne ni ressource externe n'est admis. Vérifié par les tests Playwright, lancés sur l'image servie par nginx en recette (T-254).
3. **Adresse du client.** nginx remplace l'en-tête de l'adresse du client au lieu de le compléter, et l'API lit cet en-tête (`FORWARDED_ALLOW_IPS`, `docker-compose.yml`). Au passage, la taille maximale d'une requête dans nginx a été portée à celle des pièces justificatives (20 Mo).

## À refaire

- À chaque montée de version des dépendances : `npm audit` et `pip-audit` (la CI lance déjà les tests ; l'audit reste manuel, voir [POINTS_REPORTES.md](../../POINTS_REPORTES.md)).
- Avant la mise en production : test d'intrusion par la DSI de l'hôpital sur l'environnement de recette, une fois Hopitalia raccordé.
