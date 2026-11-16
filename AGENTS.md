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

**État actuel :** priorité P0, lot 1 (P1.A), workflow transverse (P1.B, sauf annulations et dérogations qui attendent les engagements) contrats (P1.C), engagements (P1.D), commandes, réceptions et service fait (P1.E), factures, liquidations et rapprochement (P1.F), ordonnancement et paiements (P1.G) terminés ; recette de la chaîne de dépense (P1.H) faite, sauf la recette utilisateur avec la DAF (T-198, support dans `docs/recette/`). Tableaux de bord (P2.A) et alertes (P2.B, sauf courriels : T-225 bloqué) terminés. États, audit, recherche et clôture d'exercice (P2.C) terminés. Qualité, sécurité et exploitation (P2.D) terminées, sauf l'environnement de recette (T-254, bloqué : serveur de l'hôpital ; déploiement prêt, documenté dans le site, partie « Installer et exploiter »). Intégrations (P3.A) faites : journal et reprises, export comptable, import et export structurés ; imports Hopitalia (T-201, T-202) à vérifier sur des données réelles, export comptable (T-205) à faire valider par le service comptable. Livrables documentaires (P3.D) rédigés ; validations attendues (DAF, exploitation, utilisateurs) et procès-verbal final après la recette. Options d'interface (P3.C) faites : thème sombre, préférences d'affichage, traduction anglaise contrôlée, droite à gauche. Volet recettes (P3.B) fait, avec saisie dans le module ; l'import de la facturation Hopitalia (T-203) reste bloqué. Courriels d'alerte (T-225) faits. Recette blanche disponible (`docs/recette/recette-blanche.md`) : à relancer avant chaque séance de recette, et après tout changement de la chaîne de dépense. Application en phase de proposition : chaque point à valider se montre dans l'environnement de démonstration (`simulation/demonstration.py`) en suivant `docs/presentation/parcours-de-validation.md` ; les décisions se notent sur `docs/presentation/fiche-de-decision.md`, puis se reportent dans le cahier des charges et le cahier des tâches. Documentation (`site/`, servie sous `/docs/`) : guides utilisateur, d'administration, d'exploitation et d'intégration, écran par écran avec captures ; à tenir à jour avec l'interface. Une ressource avec règles métier reprend le schéma des révisions (domaine, cas d'utilisation, dépôt, routes, écrans, tests) ; un référentiel simple passe par les routes communes (voir Architecture).

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
  - aucune couleur en dur : tout passe par le thème Ant Design (IHM-03), en clair comme en sombre ;
  - propriétés logiques (`insetInlineStart`, `marginInlineEnd`, `align: 'end'`), jamais gauche et droite : une règle de lint le vérifie (I18N-10) ;
  - tout tableau paginé passe par `TableauServeur` avec un `nom` stable (clé des colonnes masquées dans les préférences) ;
  - un statut n'est jamais signalé par la seule couleur (IHM-06) : composant `BadgeStatut` ;
  - composants déclarés avec `function` : la règle de lint des textes en dur ne voit pas ceux écrits en fonction fléchée à retour implicite, ni les attributs comme `aria-label` (à vérifier en revue) ;
  - montants affichés avec le composant `Montant` (chaîne décimale formatée sans passer par un nombre flottant).
- **Images Docker :** les `.dockerignore` (racine pour l'interface, `backend/` pour l'API) sont des listes blanches. Un fichier nécessaire à la construction ou à l'exécution s'y ajoute explicitement ; tests, outils de développement, documents et secrets n'entrent jamais dans une image.
- **Fichiers générés, jamais modifiés à la main :** `frontend/openapi.json` (`python -m hopitalia_budget.outils.exporter_openapi`) et `frontend/src/api/genere/` (`npm run api`). La CI vérifie qu'ils sont à jour.
- **Écriture d'une opération :** `POST` avec en-tête `Idempotency-Key` (une clé par ouverture de formulaire), modification avec `If-Match` (version lue), trace dans le journal d'audit dans la même transaction, `session.commit()` explicite dans la route.

## Tests

- Chaque règle de gestion RG-01 à RG-20 a au moins un test qui la nomme.
- Chaque formule de la section 6 a ses tests unitaires.
- Un bug corrigé arrive avec le test qui le reproduit.
- Un test nomme dans son nom ou sa docstring (ou son titre côté frontend) les exigences qu'il couvre (`RG-xx`, `REC-xx`, `API-xx`) ; après tout ajout ou renommage, régénérer `docs/recette/tracabilite-tests.md` par `python -m tests.test_tracabilite` (depuis `backend/`).

## Documentation

- Documents produits depuis le code, à régénérer depuis `backend/` après tout changement du modèle ou des workflows (un test échoue sinon) : `python -m tests.test_dictionnaire` (une nouvelle colonne demande sa description dans ce module) et `python -m tests.test_doc_workflows`.
- Documents du projet en français ; messages de commit et descriptions de demandes de fusion en anglais.
- **Pas d'emojis ni de symboles de coche** dans les fichiers : statuts écrits en texte (« Fait », « Bloqué », « Oui »). Les symboles mathématiques (≤, ≥, −) restent permis.
- Une décision qui modifie le cahier des charges y est inscrite, pas seulement dans le code.
- **Documentation des utilisateurs** : site `site/` (Astro, Starlight), servi par l'interface sous `/docs/` ; pages dans `site/src/content/docs/`, en français. Un écran ajouté ou modifié met à jour sa page dans le même changement : libellés exacts de l'interface, profils qui peuvent agir, gestes, capture. Une capture s'ajoute dans `frontend/e2e-captures/captures.spec.ts`, puis se prend dans l'environnement de démonstration ; texte alternatif obligatoire. Les tests du site vérifient les liens, les captures et l'accessibilité.

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
| `site/` | `npm run build` · `npm test` |
| Docker | `docker compose build` · `docker compose up -d --wait` (après un changement d'un `Dockerfile`, d'un `.dockerignore` ou d'un fichier nécessaire à la construction) |
| Racine | `pre-commit run --files <fichiers modifiés>` · `docker compose up -d --build` pour l'ensemble |

La CI (`.github/workflows/ci.yml`) relance ces vérifications ; seul le job `ci-ok` est exigé pour fusionner.
