# Hopitalia Budget

Module de gestion et de suivi budgétaire hospitalier de la solution Hopitalia : crédits, marchés et contrats déjà attribués, engagements, réceptions, factures, liquidations, paiements et tableaux de bord.

Le module suit uniquement des marchés **déjà attribués** et des contrats **déjà signés** : il ne gère pas la passation des marchés.

## Documents

| Document | Contenu |
|---|---|
| [Cahier des charges](docs/Cahier_des_charges_Module_Budgetaire_Hopitalia_V3.md) | Source de vérité : exigences, règles de gestion, formules, modèle de données, conventions d'API. |
| [Cahier des tâches](CAHIER_DES_TACHES.md) | Tâches par priorité, statuts et avancement. |
| [AGENTS.md](AGENTS.md) | Règles du projet pour les développeurs et les agents de code. |
| [docs/cadrage/](docs/cadrage/) | Décisions de cadrage, intégration avec Hopitalia, nomenclature, jeu d'essai. |

## Structure

```
backend/    API FastAPI (Python)
frontend/   Interface React + TypeScript + Vite
docs/       Cahier des charges, cadrage, références
```

## Prérequis

- Docker et Docker Compose
- Python 3.12 ou plus récent
- Node.js 22 et npm
- `pre-commit` (`pip install pre-commit`)

## Démarrage rapide (tout dans Docker)

```bash
cp .env.example .env        # puis renseigner POSTGRES_PASSWORD (et l'accès Hopitalia)
docker compose up -d --build
```

Les migrations de la base s'appliquent au démarrage de l'API.

**Premier administrateur.** La connexion passe par Hopitalia, mais les droits budgétaires sont propres au module : un agent sans profil est refusé. Attribuer le premier profil d'administrateur avec l'identifiant Hopitalia de l'agent (`userId`) :

```bash
docker compose exec api python -m hopitalia_budget.outils.habiliter   --utilisateur-id 42 --code-agent AG042 --profil ADM
```

| Service | Adresse |
|---|---|
| Interface | http://127.0.0.1:8080 |
| API | http://127.0.0.1:8000 (santé : `/health`) |
| PostgreSQL | interne au réseau Docker |

Arrêt : `docker compose down` (ajouter `-v` pour effacer aussi la base).

## Développement

### Backend

```bash
cd backend
python -m venv .venv
source .venv/Scripts/activate      # Windows (Git Bash) ; sous Linux ou macOS : source .venv/bin/activate
pip install -e ".[dev]"
export DATABASE_URL=postgresql+psycopg://hopitalia:<mot-de-passe>@localhost:5432/hopitalia_budget
alembic upgrade head
uvicorn hopitalia_budget.main:app --reload
```

Documentation interactive de l'API : http://127.0.0.1:8000/api/v1/docs

**Base de test.** Les tests créent une base temporaire sur un serveur PostgreSQL de test, puis la suppriment :

```bash
docker run -d --name hb-budget-test-db -e POSTGRES_USER=test -e POSTGRES_PASSWORD=test   -p 127.0.0.1:55433:5432 postgres:16-alpine
export TEST_DATABASE_URL=postgresql+psycopg://test:test@127.0.0.1:55433/postgres
pytest
```

Sans `TEST_DATABASE_URL`, les tests qui ont besoin d'une base sont ignorés en local (et refusés en CI).

**Nouvelle migration** après une modification des modèles : `alembic revision -m "objet"`, puis écrire la migration dans `migrations/versions/`.

| Vérification | Commande |
|---|---|
| Lint | `ruff check .` |
| Format | `ruff format --check .` (corriger : `ruff format .`) |
| Typage | `mypy` |
| Tests | `pytest` |
| OpenAPI pour le frontend | `python -m hopitalia_budget.outils.exporter_openapi > ../frontend/openapi.json` |

### Frontend

```bash
cd frontend
npm ci
npm run dev
```

L'interface de développement (http://127.0.0.1:5173) envoie les appels `/api` à l'API locale (port 8000).

| Vérification | Commande |
|---|---|
| Format | `npm run format:check` (corriger : `npm run format`) |
| Lint (dont accessibilité) | `npm run lint` |
| Typage | `npm run typecheck` |
| Tests | `npm test` |
| Parcours de bout en bout (ordinateur et téléphone, API simulée) | `npm run e2e` (première fois : `npx playwright install chromium`) |
| Build | `npm run build` |
| Client d'API généré | `npm run api` (après mise à jour de `openapi.json`) |

### Hooks avant commit

```bash
pre-commit install
```

À chaque commit : espaces et fins de fichiers, YAML, gros fichiers, **clés privées**, conflits de fusion, ruff (backend), Prettier et ESLint (frontend).

## Intégration continue

Le workflow [`.github/workflows/ci.yml`](.github/workflows/ci.yml) s'exécute sur chaque demande de fusion et chaque push sur `main` :

- `backend` et `frontend` : les vérifications ci-dessus, lancées seulement si leur dossier ou le workflow a changé ;
- `dco` : chaque commit de la demande de fusion porte une signature `Signed-off-by` (`git commit -s`) ;
- `ci-ok` : synthèse, seule vérification exigée par la protection de `main`.

## Contribuer

- Toute modification arrive sur `main` par une demande de fusion, avec le modèle [`.github/pull_request_template.md`](.github/pull_request_template.md).
- Commits au format Conventional Commits, en anglais, signés : `git commit -s -m "feat(budget): ..."`.
- Règles métier, architecture et conventions : [AGENTS.md](AGENTS.md).
- Aucun secret dans le dépôt : les valeurs vont dans `.env` (non versionné) ; [`.env.example`](.env.example) liste les variables.
