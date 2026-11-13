# Intégration avec le backend Hopitalia

**Projet :** Hopitalia Budget · **Date :** 13/11/2026 · **Tâche :** T-011 · **Source :** code du dépôt `hopitalia-backend` (dernier commit lu : `e15ab46`)

Cette note décrit ce que le module budgétaire utilise du backend Hopitalia : la connexion des utilisateurs, les référentiels et les achats de la pharmacie. Elle a été établie en lisant le code. À vérifier sur un environnement Hopitalia en fonctionnement avant le développement des échanges.

## 1. Le backend Hopitalia en bref

| Élément | Valeur |
|---|---|
| Technologie | Java 17, Spring Boot 3.5, Spring Data JPA |
| Base de données | PostgreSQL |
| Déploiement | Image Docker (`Dockerfile`, `docker-compose.yml`) |
| Documentation des API | OpenAPI générée à l'exécution : `/v3/api-docs` (groupe facturation : `/v3/api-docs/facturation`), interface Swagger : `/swagger-ui/index.html` |
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

## 3. Compte technique pour les échanges de données

Hopitalia ne propose pas de connexion entre applications (pas de « client credentials »). Les échanges planifiés (référentiels, pharmacie) utilisent donc un **compte technique** : un agent Hopitalia dédié, aux permissions limitées à la lecture des routes ci-dessous. Ses identifiants sont stockés comme secrets du module.

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

**À confirmer avec l'équipe Hopitalia :**

- `montant` d'une ligne est-il le total de la ligne ou un prix unitaire ?
- Les montants sont des entiers (francs CFA, sans décimales) ; le module les convertit en `Decimal`.
- Un approvisionnement peut-il être modifié après coup (`PUT /api/pharmacie/approvisionnements/{id}`) ? Si oui, il faut un horodatage de modification pour le détecter.

## 6. Recettes (volet activé plus tard)

Pour le volet recettes (P3), les routes `GET /api/encaissements/recettes/modes-paiement`, `GET /api/encaissements/recettes/agents` et `GET /api/encaissements/dashboard/global` exposent les encaissements, et `GET /api/factures/page` les factures. Leur exploitation sera détaillée au moment du lot recettes.

## 7. Environnement de test

Le dépôt Hopitalia contient un `docker-compose.yml`. Un environnement de test se monte en lançant Hopitalia localement avec une base de données de test. Cela reste à faire, et à vérifier, avant le développement des échanges (tâche T-011).
