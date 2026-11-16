# Guide d'intégration de l'API

**Projet :** Hopitalia Budget · **Tâche :** T-282 · **Référence :** cahier des charges V3, sections 11 et 13

Ce guide s'adresse aux équipes qui relient un autre système au module de suivi budgétaire : lecture des données, création de pièces, échanges de fichiers. Le contrat exact (ressources, champs, codes d'erreur) est le document OpenAPI de la version déployée.

## Documentation de référence

| Où | Contenu |
|---|---|
| `/api/v1/openapi.json` sur le serveur | Document OpenAPI 3.1 de la version en service. |
| `/api/v1/docs` sur le serveur | Interface Swagger pour essayer l'API avec un jeton. |
| Versions GitHub du dépôt | Pour chaque version `vX.Y.Z` : `openapi-vX.Y.Z.json` et ce guide, joints automatiquement par le workflow `publication.yml`. |
| `frontend/openapi.json` | Document de la branche principale ; la CI vérifie qu'il est identique à celui que produit l'application. |

Le champ `info.version` du document OpenAPI est la version du module. La version d'API (`/api/v1`) ne change qu'en cas de rupture ; une version reste servie 12 mois après la suivante. Une version inconnue (`/api/v2/…`) répond `404`.

## Authentification

Le module n'a pas de comptes propres : un client s'authentifie avec un compte Hopitalia.

```http
POST /api/v1/auth/connexion
Content-Type: application/json

{"identifiant": "svc-integration", "motDePasse": "…"}
```

La réponse donne `jetonAcces` (valable `expireDans` secondes) et `jetonRafraichissement`. Chaque appel porte `Authorization: Bearer <jetonAcces>`. Avant expiration, `POST /api/v1/auth/rafraichissement` avec `{"jetonRafraichissement": "…"}` donne une nouvelle paire ; `POST /api/v1/auth/deconnexion` révoque le jeton de rafraichissement.

Les droits viennent du module, pas d'Hopitalia : un administrateur du module attribue au compte du client ses profils budgétaires et ses établissements (écran « Habilitations »). Un compte sans profil reçoit `403 AUCUN_PROFIL`. Donner au compte d'un système le profil le plus étroit qui suffit : `LEC` ou `AUD` pour lire, le profil de saisie de la matrice pour créer des pièces.

## Conventions

| Sujet | Règle |
|---|---|
| Format | JSON en `camelCase`. Montants en chaîne décimale (`"1500000.00"`), jamais en nombre flottant. Dates `AAAA-MM-JJ`, horodatages ISO 8601 avec fuseau. |
| Langue | `Accept-Language: fr` ou `en` : messages d'erreur et états dans la langue demandée ; les données métier ne changent pas. |
| Pagination | Listes : `?page=1&taille=25` (100 au plus) ; la réponse donne `pagination.total` et `pagination.suivant` (adresse de la page suivante). Journaux et alertes : curseur, `?apres=<curseur>` avec `pagination.suivant`. |
| Filtres | Seuls les paramètres documentés sont acceptés ; un paramètre inconnu répond `400`. |
| Création | Tout `POST` qui crée une pièce financière exige `Idempotency-Key: <uuid>` : une clé par opération métier, réutilisée telle quelle en cas de nouvel essai. La même clé avec le même corps renvoie la réponse d'origine (conservée 24 heures) ; avec un autre corps, `422 IDEMPOTENCE_CONFLIT`. |
| Modification | Lire la fiche (en-tête `ETag`), puis envoyer `If-Match: <ETag>` avec le `PATCH`. Sans en-tête : `428 PRECONDITION_REQUISE` ; si la fiche a changé entre-temps : `412 PRECONDITION_ECHOUEE`, la relire. |
| Opération validée | Elle n'est plus modifiable (RG-18) : une correction passe par une annulation ou une contre-opération. |
| Débit | 300 requêtes par minute et par compte. En-têtes `RateLimit-Limit`, `RateLimit-Remaining`, `RateLimit-Reset` ; au-delà, `429 LIMITE_DEBIT` avec `Retry-After` (secondes). |
| Suivi | Envoyer `X-Request-ID` pour retrouver un appel dans les journaux du serveur ; il est renvoyé dans la réponse. |

## Erreurs

Toute erreur est au format `application/problem+json`, avec un `code` stable à utiliser dans le programme client (le titre et le détail sont traduits et peuvent changer) :

```json
{
  "type": "https://hopitalia-budget/erreurs/credit-insuffisant",
  "title": "Crédit insuffisant",
  "status": 422,
  "code": "CREDIT_INSUFFISANT",
  "detail": "…",
  "erreurs": [{"champ": "montant", "code": "…"}]
}
```

`erreurs` liste les champs en faute d'une requête invalide (`422 VALIDATION`). Une erreur interne répond `500 ERREUR_INTERNE` sans détail technique ; le donner à l'exploitation avec le `X-Request-ID`.

## Cas d'usage

| Besoin | Ressources |
|---|---|
| Lire les crédits | `GET /budgets`, `GET /budgets/{id}/situation`, `GET /lignes-budgetaires/{id}/disponibilite`. |
| Échanger un budget | `GET /budgets/{id}/export?format=csv|json` (format de l'import), puis `POST /budgets/{id}/imports` (CSV, `202` et suivi sur `/imports-dotations/{id}`). |
| Créer des engagements | `POST /engagements` (brouillon), puis `POST /engagements/{id}/soumissions` : les contrôles et le circuit de validation s'appliquent ; aucun import ne crée une pièce déjà validée. |
| Suivre la chaîne de dépense | `GET /engagements`, `/bons-commande`, `/factures`, `/liquidations`, `/paiements`, filtrés par établissement et exercice. |
| Exporter vers la comptabilité | `GET /etats/ecritures?exerciceId=…&format=csv|xlsx` : écritures équilibrées (section 13 du cahier des charges). |
| Exporter un état | `GET /etats/{code}?format=json|csv|xlsx|pdf`, mêmes filtres que le tableau de bord. |
| Lire les alertes | `GET /alertes` (curseur), `GET /alertes/compteur`. |

Les échanges avec Hopitalia (fournisseurs, services, pharmacie) sont faits par le module lui-même ; ils ne passent pas par un client externe (note d'intégration, section 8).

## Exemple : créer un engagement sans doublon

```bash
JETON=$(curl -s -X POST "$API/api/v1/auth/connexion" -H 'Content-Type: application/json' \
  -d '{"identifiant":"svc-integration","motDePasse":"…"}' | jq -r .jetonAcces)
CLE=$(uuidgen)   # une clé par engagement, conservée pour les nouveaux essais
curl -s -X POST "$API/api/v1/engagements" \
  -H "Authorization: Bearer $JETON" -H "Idempotency-Key: $CLE" \
  -H 'Content-Type: application/json' -d @engagement.json
```

En cas de coupure réseau, renvoyer la même requête avec la même clé : l'engagement n'est créé qu'une fois.
