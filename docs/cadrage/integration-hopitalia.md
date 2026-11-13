# Intégration avec le backend Hopitalia

**Projet :** Hopitalia Budget · **Date :** 13/11/2026 · **Tâche :** T-011 · **Source :** code du dépôt `hopitalia-backend` (dernier commit lu : `e15ab46`)

Cette note décrit ce que le module budgétaire utilise du backend Hopitalia : la connexion des utilisateurs, les référentiels et les achats de la pharmacie. Elle a été établie en lisant le code, puis **vérifiée le 13/11/2026 sur une instance Hopitalia de test** (section 7).

## 1. Le backend Hopitalia en bref

| Élément | Valeur |
|---|---|
| Technologie | Java 17, Spring Boot 3.5, Spring Data JPA |
| Base de données | PostgreSQL |
| Déploiement | Image Docker (`Dockerfile`, `docker-compose.yml`) |
| Documentation des API | OpenAPI générée à l'exécution : `/openapi.json` (832 routes), interface Swagger : `/swagger-ui/index.html` |
| Sécurité | Jetons JWT signés en HS512 ; toutes les routes exigent un jeton, sauf la connexion et quelques routes publiques |

## 2. Connexion des utilisateurs (décision : réutiliser la connexion Hopitalia)

### Ce que fournit Hopitalia

| Route | Rôle |
|---|---|
| `POST /api/auth/login` | Corps `{"username", "password"}` ; renvoie `access_token`, `refresh_token`, `token_type`, `expires_in`, `refresh_expires_at`. |
| `POST /api/auth/refresh` | Corps `{"refresh_token"}` ; renvoie une nouvelle paire de jetons (rotation du jeton de rafraîchissement). |
| `POST /api/auth/logout` | Corps `{"refresh_token"}` ; révoque le jeton de rafraîchissement. |
| `GET /api/auth/me` | Profil de l'utilisateur connecté. |

Contenu du jeton d'accès : `sub` (identifiant de connexion), `scope` (rôles Hopitalia), `permissions` (codes de permission Hopitalia), `userId`, `code` (code de l'agent), `prenomNom`, `service`, `specialiteId`, `iat`, `exp`. Pas d'émetteur (`iss`) ni d'audience (`aud`).

### Ce que fait le module

1. **Connexion relayée :** l'interface du module envoie l'identifiant et le mot de passe à son propre backend (`POST /api/v1/auth/connexion`), qui les relaie à `POST /api/auth/login` d'Hopitalia. Même principe pour le rafraîchissement et la déconnexion. L'interface ne parle qu'au backend du module : pas de règle CORS à ajouter côté Hopitalia.
2. **Vérification locale du jeton :** le backend du module vérifie la signature HS512 et l'expiration de chaque jeton, avec la clé de signature d'Hopitalia fournie par variable d'environnement. Il ne rappelle pas Hopitalia à chaque requête.
3. **Identité :** l'utilisateur est identifié par `userId` et `code` (code agent). Ses nom et service viennent du jeton.
4. **Droits budgétaires propres au module :** les rôles et permissions Hopitalia ne donnent **aucun** droit dans le module. Un administrateur du module attribue à chaque agent ses profils budgétaires (matrice des habilitations) et son ou ses établissements. Un agent sans profil budgétaire est refusé (`403`).

### Points de sécurité à traiter avec l'équipe Hopitalia

- **Clé partagée :** avec HS512, la clé qui vérifie les jetons permet aussi d'en fabriquer. Le module la garde donc comme un secret de production : variable d'environnement, jamais dans le code ni dans le dépôt. À terme, demander à Hopitalia une signature asymétrique (RS256, avec publication de la clé publique) : le module pourrait alors vérifier les jetons sans pouvoir en fabriquer.
- **Configuration de la clé côté Hopitalia :** des points de configuration ont été transmis directement à l'équipe Hopitalia (tâche T-017), hors de ce dépôt public.
- **Pas d'audience :** un jeton Hopitalia est accepté par toute application qui partage la clé. Demander l'ajout d'une audience (`aud`) à terme.

## 3. Compte technique et configuration du module

Hopitalia ne propose pas de connexion entre applications (pas de « client credentials »). Les échanges planifiés (référentiels, pharmacie) utilisent donc un **compte technique** : un agent Hopitalia dédié (par exemple `svc-budget`), réservé à ces échanges, avec un mot de passe long et aléatoire.

Le module n'appelle que des routes en lecture (`GET`) ; son client HTTP vers Hopitalia refuse toute autre méthode.

**Variables d'environnement du module** (valeurs jamais dans le dépôt ; un fichier `.env.example` listera les noms sans valeurs, tâche T-041) :

| Variable | Contenu | Secret |
|---|---|---|
| `HOPITALIA_API_URL` | URL de base de l'API Hopitalia (test, puis production). | Non |
| `HOPITALIA_JWT_CLE` | Clé de vérification des jetons Hopitalia (même valeur que `hopitalia.jwt.secret` côté Hopitalia). | Oui |
| `HOPITALIA_COMPTE_TECHNIQUE` | Identifiant du compte technique. | Non |
| `HOPITALIA_COMPTE_TECHNIQUE_MOT_DE_PASSE` | Mot de passe du compte technique. | Oui |

Le compte technique et la clé sont remis par l'équipe Hopitalia hors de ce dépôt (tâche T-017).

## 4. Référentiels (décision : importer depuis Hopitalia)

| Donnée module | Route Hopitalia | Champs | Correspondance |
|---|---|---|---|
| Fournisseur | `GET /api/pharmacie/fournisseurs` | `id`, `codeFourn`, `nomFourn`, `telephone`, `adresse` | `codeFourn` devient l'identifiant externe ; `nomFourn` la raison sociale. Coordonnées bancaires, identifiants administratifs et fournisseurs hors pharmacie sont gérés dans le module. |
| Centre de responsabilité | `GET /api/services`, `GET /api/services/code/{codeService}` | `codeService`, `nomService`, `administration`, `laboratoire`, `specialites` | `codeService` devient l'identifiant externe. Les spécialités peuvent devenir des centres enfants. |

Synchronisation : lecture complète périodique (les listes sont courtes), création ou mise à jour par identifiant externe, jamais de suppression automatique (un fournisseur disparu d'Hopitalia est désactivé, pas supprimé, pour garder l'historique).

## 5. Achats pharmaceutiques (décision : les reprendre d'Hopitalia)

La pharmacie d'Hopitalia saisit ses commandes et ses approvisionnements. Le module les **lit** et les rattache aux engagements ; il ne les ressaisit pas.

| Donnée module | Route Hopitalia | Champs utiles |
|---|---|---|
| Bon de commande | `GET /api/pharmacie/bons-commandes?start=AAAA-MM-JJ&end=AAAA-MM-JJ[&fournisseurId=]` puis `GET /api/pharmacie/bons-commandes/{id}/details` | `numBc`, `dateBc`, `codeFourn`, `nomService`, `urgent`, `livraisonTotal` ; lignes : `codeProduit`, `nomProduit`, `quantite`, `montant` |
| Réception | `GET /api/pharmacie/approvisionnements/historique?start=…&end=…` et `GET /api/pharmacie/approvisionnements/{id}` | `date`, `numBl`, `numBonCmde` (lien vers la commande), `codeFourn` ; lignes : `codeProduit`, `quantite`, `montant`, `numeroLot`, `datePeremption` |
| Réception supprimée | `GET /api/pharmacie/approvisionnements/historique-suppressions?start=…&end=…` | Approvisionnements supprimés dans Hopitalia : la réception correspondante est annulée dans le module, avec trace. |

Règles côté module :

- Une commande importée est rattachée à un engagement validé par l'agent financier (proposition automatique par fournisseur et montant restant). Tant qu'elle n'est pas rattachée, elle apparaît dans une liste « commandes à rattacher ».
- Un approvisionnement importé devient une réception **validée** : dans Hopitalia, l'entrée en stock vaut constat de livraison. La preuve de service fait (RG-06) est le bon de livraison (`numBl`).
- Le lien réception → commande passe par `numBonCmde`.
- Dans ce sens, c'est Hopitalia qui alimente le module ; le module n'écrit jamais dans le stock.

**Constaté dans le code et sur l'instance de test :**

- `montant` d'une ligne de commande ou d'approvisionnement est le **total de la ligne**, calculé par Hopitalia : prix de cession du produit × quantité, arrondi à l'entier. Ce n'est donc pas le prix facturé par le fournisseur : les écarts avec la facture apparaîtront au rapprochement (annexe B), c'est attendu.
- Les montants sont des entiers (francs CFA, sans décimales) ; le module les convertit en `Decimal`.
- Un approvisionnement peut être modifié après coup (`PUT /api/pharmacie/approvisionnements/{id}`), mais Hopitalia n'enregistre pas de date de modification. Le module détecte donc les changements en comparant, à chaque import, une empreinte du contenu de l'approvisionnement avec celle de l'import précédent ; un changement sur une réception déjà rattachée crée une alerte d'écart.

## 6. Recettes (volet activé plus tard)

Pour le volet recettes (P3), les routes `GET /api/encaissements/recettes/modes-paiement`, `GET /api/encaissements/recettes/agents` et `GET /api/encaissements/dashboard/global` exposent les encaissements. Elles exigent `dateDebut` et `dateFin` au format `AAAA-MM-JJ` (un format avec heure renvoie une erreur 500). `GET /api/factures/page` liste les factures, paginées (`page`, `size`, `sort`). Leur exploitation sera détaillée au moment du lot recettes.

## 7. Environnement de test

Une instance Hopitalia de test a été montée et vérifiée le 13/11/2026, sur le poste de développement :

- image construite avec le `Dockerfile` d'Hopitalia (configuration par défaut), base PostgreSQL 16 vide dédiée au test, schéma créé au démarrage ;
- clé de signature des jetons et mots de passe de test générés aléatoirement, propres à cette instance, conservés hors des dépôts ;
- accès limité au poste (`127.0.0.1`) ;
- un agent de test `svc-budget` créé pour jouer le compte technique.

**Démarrage** (valeurs entre chevrons à fournir, jamais versionnées) :

```bash
docker network create hb-test-net
docker run -d --name hb-test-postgres --network hb-test-net -e POSTGRES_USER=hbtest   -e POSTGRES_PASSWORD=<mot-de-passe-base> -e POSTGRES_DB=hopitalia_test -p 127.0.0.1:55432:5432 postgres:16-alpine
docker build -t hopitalia-backend-test:local <dossier hopitalia-backend>
docker run -d --name hb-test-backend --network hb-test-net -p 127.0.0.1:58080:8080   -e SPRING_DATASOURCE_URL=jdbc:postgresql://hb-test-postgres:5432/hopitalia_test   -e SPRING_DATASOURCE_USERNAME=hbtest -e SPRING_DATASOURCE_PASSWORD=<mot-de-passe-base>   -e HOPITALIA_JWT_SECRET=<cle-de-test> hopitalia-backend-test:local
```

**Résultats de la vérification :**

| Vérification | Résultat |
|---|---|
| `POST /api/auth/login` renvoie `access_token`, `refresh_token`, `token_type`, `expires_in`, `refresh_expires_at` | Conforme |
| Contenu du jeton : `sub`, `scope`, `permissions`, `userId`, `code`, `prenomNom`, `service`, `specialiteId`, `iat`, `exp` | Conforme |
| Signature HS512 vérifiable localement avec la clé, comme le fera le module | Conforme |
| `POST /api/auth/refresh`, `GET /api/auth/me` | Conformes |
| Routes de la pharmacie sans jeton | Refusées (`401`) |
| `GET /api/pharmacie/fournisseurs`, `GET /api/services`, `GET /api/services/code/{code}` | Conformes |
| `GET /api/pharmacie/bons-commandes`, `.../approvisionnements/historique`, `.../historique-suppressions` | Conformes |
| `GET /api/encaissements/recettes/modes-paiement` | Conforme avec dates `AAAA-MM-JJ` |
| Documentation OpenAPI | À `/openapi.json`, et non `/v3/api-docs` comme indiqué dans le README d'Hopitalia |

La base de test est vide : le contenu des réponses (pharmacie, encaissements) sera vérifié avec des données lors des tâches d'intégration (T-201 à T-203).
