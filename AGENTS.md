# AGENTS.md — Module de suivi budgétaire Hopitalia

Règles du projet pour tout agent de code et tout développeur. [CLAUDE.md](CLAUDE.md) importe ce fichier : les règles communes s'écrivent ici, jamais en double. Les préférences personnelles vont dans `CLAUDE.local.md`, non versionné.

## Le projet

**Nom :** `hopitalia-budget` · **Dépôt :** https://github.com/LordPhenixDeNetra/hopitalia-budget · **Nom affiché :** Hopitalia Budget

Module de gestion et de suivi budgétaire hospitalier de la solution Hopitalia : crédits, marchés et contrats, engagements, réceptions, factures, liquidations, paiements, tableaux de bord.

**Périmètre non négociable :** le module suit les marchés **déjà attribués** et les contrats **déjà signés**. Ne jamais ajouter de fonction de lancement, de passation, d'évaluation ou d'attribution de marché (RG-12).

## Documents de référence

| Document | Rôle |
|---|---|
| [Cahier des charges V3](docs/Cahier_des_charges_Module_Budgetaire_Hopitalia_V3.md) | **Source de vérité** : exigences, règles de gestion, formules, modèle de données, conventions d'API. En cas de doute, il prime sur ce fichier. |
| [CAHIER_DES_TACHES.md](CAHIER_DES_TACHES.md) | Tâches par priorité, statuts, dépendances, critères de fin. |
| [POINTS_REPORTES.md](POINTS_REPORTES.md) | Ce qui a été volontairement remis à plus tard. |
| [docs/cadrage/](docs/cadrage/) | Questionnaires (DAF, équipe Hopitalia), matrice des habilitations, jeu d'essai de référence. |

**État actuel :** priorité P0, lot 1 (P1.A), workflow transverse (P1.B, sauf annulations et dérogations qui attendent les engagements) contrats (P1.C), engagements (P1.D), commandes, réceptions et service fait (P1.E), factures, liquidations et rapprochement (P1.F) terminés ; payeur (RG-13) et écart facture et paiement attendent le lot 5. Suite : ordonnancement et paiements (P1.G). Une ressource avec règles métier reprend le schéma des révisions (domaine, cas d'utilisation, dépôt, routes, écrans, tests) ; un référentiel simple passe par les routes communes (voir Architecture).

## Pile technique

- **Backend :** Python, FastAPI, SQLAlchemy 2, Alembic, Pydantic. Base de données : PostgreSQL.
- **Frontend :** React, TypeScript, Vite, Ant Design 6, TanStack Query, `react-i18next`, client d'API généré par `orval` depuis l'OpenAPI de FastAPI.
- **Tests :** `pytest` ; Vitest et Playwright.
- **Déploiement et Hopitalia :** application séparée (lien depuis Hopitalia), hébergée sur les serveurs de l'hôpital. La connexion des agents passe par Hopitalia (jetons vérifiés localement) ; les droits budgétaires sont propres au module. Fournisseurs, services et achats pharmaceutiques sont importés d'Hopitalia, jamais ressaisis. Comptes comptables du plan SYSCOHADA révisé. Détails : section 17 du cahier des charges et [note d'intégration](docs/cadrage/integration-hopitalia.md).
- **Secrets :** la clé de vérification des jetons Hopitalia et le compte technique Hopitalia sont des secrets de production, en variables d'environnement, jamais dans le dépôt.
- **Organisation :** dépôt unique avec `backend/`, `frontend/` et `docs/`.
- **Noms techniques :** paquet Python `hopitalia_budget`, paquet npm `@hopitalia/budget-web`, base `hopitalia_budget`, images `hopitalia-budget-api` et `hopitalia-budget-web`.

## Règles métier à ne jamais enfreindre

- **Montants :** `Decimal` en Python, `Numeric(18,2)` en base, chaîne décimale en JSON. Jamais de `float`.
- **Indicateurs calculés, jamais stockés** (RG-14) : engagé, liquidé, payé, restes et disponibles se calculent à partir des pièces, avec la formule unique de la section 6 du cahier des charges.
- **Engagé, facturé, liquidé, transmis et payé** sont des étapes d'une même dépense : ne jamais les additionner entre eux.
- **Opération validée = immuable** (RG-18) : toute correction passe par une annulation ou une contre-opération tracée.
- **Contrôle de crédit atomique** (RG-20) : deux engagements simultanés ne peuvent pas consommer le même crédit.
- **Cloisonnement par établissement** vérifié côté serveur à chaque requête.
- **Toute modification de donnée financière** est écrite dans le journal d'audit.

## Architecture

- Couches : `domaine` (entités, règles, ports), `application` (cas d'utilisation), `adaptateurs` (API, base, systèmes externes). Le domaine n'importe ni FastAPI ni SQLAlchemy.
- SOLID appliqué comme décrit en section 10 du cahier des charges, **sans excès** : une abstraction n'est créée que si elle a au moins deux implémentations (réelle et de test comptent) ou un point d'extension prévu par le cahier des charges.
- Nouveau contrôle automatique = nouvelle classe `RegleControle`, sans modifier le moteur.
- Nouvel objet validable : il implémente `Validable` (et `Justifiable` s'il porte des pièces), puis se déclare dans `TRANSITIONS_REFERENCE` et `OPERATIONS` (`domaine/workflow.py`), `VALIDABLES` (`routes/workflow.py`) et `TypeObjet` (`schemas.py`). Circuits, visas, délégations, pièces et écrans `Validations` et `Pieces` viennent avec, sans code propre.
- Référentiel sans règle métier : routes communes de `adaptateurs/entree/api/crud.py` (liste, fiche, création, modification, audit). Dès qu'une règle métier apparaît, elle va dans `application/`.
- Côté interface, un référentiel simple se déclare dans `frontend/src/pages/parametrage/ressources.ts` ; pas de nouvel écran.

## Conventions de code

- **Nommage métier en français sans accents**, identique au modèle de données : `Engagement`, `LigneBudgetaire`, `montantActualise`.
- Python : `snake_case` pour les attributs et fonctions ; JSON de l'API en `camelCase` (alias Pydantic).
- **API :** suivre la section 11 du cahier des charges (ressources au pluriel, `/api/v1`, idempotence des `POST` financiers, pagination, filtres sur liste blanche, erreurs `problem+json` avec code stable).
- **Frontend :**
  - aucun texte en dur : tout passe par une clé de traduction (I18N-02) ;
  - aucune couleur en dur : tout passe par le thème Ant Design (IHM-03) ;
  - un statut n'est jamais signalé par la seule couleur (IHM-06) : composant `BadgeStatut` ;
  - composants déclarés avec `function` : la règle de lint des textes en dur ne voit pas ceux écrits en fonction fléchée à retour implicite, ni les attributs comme `aria-label` (à vérifier en revue) ;
  - montants affichés avec le composant `Montant` (chaîne décimale formatée sans passer par un nombre flottant).
- **Fichiers générés, jamais modifiés à la main :** `frontend/openapi.json` (`python -m hopitalia_budget.outils.exporter_openapi`) et `frontend/src/api/genere/` (`npm run api`). La CI vérifie qu'ils sont à jour.
- **Écriture d'une opération :** `POST` avec en-tête `Idempotency-Key` (une clé par ouverture de formulaire), modification avec `If-Match` (version lue), trace dans le journal d'audit dans la même transaction, `session.commit()` explicite dans la route.

## Tests

- Chaque règle de gestion RG-01 à RG-20 a au moins un test qui la nomme.
- Chaque formule de la section 6 a ses tests unitaires.
- Un bug corrigé arrive avec le test qui le reproduit.

## Documentation

- Documents du projet en français ; messages de commit et descriptions de demandes de fusion en anglais.
- **Pas d'emojis ni de symboles de coche** dans les fichiers : statuts écrits en texte (« Fait », « Bloqué », « Oui »). Les symboles mathématiques (≤, ≥, −) restent permis.
- Une décision qui modifie le cahier des charges y est inscrite, pas seulement dans le code.

## Suivi des tâches

- Mettre à jour [CAHIER_DES_TACHES.md](CAHIER_DES_TACHES.md) à chaque changement : statut de la tâche, compteurs du tableau de bord, ligne dans le journal.
- Une tâche passe à « Fait » **seulement** quand son critère de fin est vérifié. Sinon, elle reste « En cours ».
- Une tâche « Bloqué » indique toujours ce qui la bloque et qui peut la débloquer.
- Ce qui est remis à plus tard est inscrit dans [POINTS_REPORTES.md](POINTS_REPORTES.md).

## Git

- Messages au format Conventional Commits, en anglais, avec portée : `feat(budget): ...`, `docs(spec): ...`.
- Signature DCO obligatoire : `git commit -s`.
- Un commit par sujet ; `git add` avec des chemins explicites.
- Toute modification arrive sur `main` par une demande de fusion.

## Commandes

Détail et installation : [README.md](README.md).

| Où | Vérifications avant de proposer une modification |
|---|---|
| `backend/` | `ruff check .` · `ruff format --check .` · `mypy` · `pytest` (base de test : `TEST_DATABASE_URL`) |
| `frontend/` | `npm run format:check` · `npm run lint` · `npm run typecheck` · `npm test` · `npm run e2e` |
| Racine | `pre-commit run --files <fichiers modifiés>` · `docker compose up -d --build` pour l'ensemble |

La CI (`.github/workflows/ci.yml`) relance ces vérifications ; seul le job `ci-ok` est exigé pour fusionner.
