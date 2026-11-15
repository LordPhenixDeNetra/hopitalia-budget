# Cahier des tâches — Module de suivi budgétaire Hopitalia

**Projet :** `hopitalia-budget` · **Dépôt :** https://github.com/LordPhenixDeNetra/hopitalia-budget · **Référence :** [cahier des charges V3](docs/Cahier_des_charges_Module_Budgetaire_Hopitalia_V3.md) · **Pile :** FastAPI, PostgreSQL (à confirmer), React, TypeScript, Ant Design · **Mise à jour :** 15/11/2026

## Légende

| Statut | Signification |
|---|---|
| Fait | Terminé et vérifié selon le critère de fin. |
| En cours | Commencé, pas encore terminé. |
| À faire | Prêt à démarrer ou en attente de ses dépendances internes. |
| Bloqué | Ne peut pas avancer : il manque une information ou une décision **externe** (la raison est indiquée). |
| En attente | Décision interne à prendre avant de commencer. |
| Abandonné | Retiré du périmètre (garder la ligne et la raison). |

| Priorité | Signification |
|---|---|
| **P0 — Critique** | Préalable à tout le reste, ou protège l'intégrité financière et la sécurité. |
| **P1 — Haute** | Cœur du module : la chaîne de dépense complète (lots 1 à 5). |
| **P2 — Moyenne** | Pilotage, alertes, états, qualité avant la mise en production (lot 6). |
| **P3 — Basse** | Intégrations avancées, volets optionnels, documentation finale (lot 7). |

**Règles de suivi**

- Un identifiant (`T-xxx`) ne change jamais, même si la tâche change de section ou est abandonnée.
- Une tâche passe à « Fait » seulement quand son **critère de fin** est vérifié (tests verts, revue faite).
- Une tâche « Bloqué » indique toujours ce qui la bloque et qui peut la débloquer.
- Les colonnes « Réf. » renvoient aux exigences du cahier des charges (EF, RG, ENF, IHM, API, REC, ARC).

## Tableau de bord

| Priorité | Fait | En cours | À faire | Bloqué | En attente | Abandonné | Total |
|---|---:|---:|---:|---:|---:|---:|---:|
| P0 | 69 | 2 | 0 | 0 | 0 | 1 | 72 |
| P1 | 68 | 1 | 13 | 0 | 0 | 0 | 82 |
| P2 | 0 | 0 | 32 | 0 | 0 | 0 | 32 |
| P3 | 0 | 0 | 22 | 0 | 0 | 1 | 23 |
| **Total** | **137** | **3** | **67** | **0** | **0** | **2** | **209** |

Avancement : 137 / 207 tâches actives terminées (66 %), hors 2 abandonnées.

**Bloquants actuels**

Aucune tâche bloquée.

## Ordre de réalisation

```mermaid
flowchart LR
  P0A["P0 Cadrage<br/>et décisions"] --> P0B["P0 Dépôt<br/>et outillage"]
  P0B --> P0C["P0 Socle backend"]
  P0B --> P0D["P0 Socle frontend"]
  P0C --> L1["P1 Lot 1<br/>Budgets, crédits"]
  P0D --> L1
  L1 --> WF["P1 Workflow<br/>transverse"]
  WF --> L2["P1 Lot 2<br/>Contrats, engagements"]
  L2 --> L3["P1 Lot 3<br/>Commandes, réceptions"]
  L3 --> L4["P1 Lot 4<br/>Factures, liquidations"]
  L4 --> L5["P1 Lot 5<br/>Paiements"]
  L5 --> L6["P2 Lot 6<br/>Pilotage, alertes, états"]
  L6 --> L7["P3 Lot 7<br/>Intégrations"]
```

---

## P0 — Critique

### P0.A — Cadrage et décisions

| ID | Tâche | Réf. | Dépend de | Statut | Critère de fin |
|---|---|---|---|---|---|
| T-001 | Rédiger le cahier des charges V3 (modèle corrigé, SOLID, conventions d'API, diagrammes). | — | — | Fait | Fichier V3 livré. |
| T-002 | Choisir le framework backend. | §17.1 | — | Fait | FastAPI retenu. |
| T-003 | Choisir le framework frontend. | §17.1 | — | Fait | React + TypeScript + Vite + Ant Design retenus. |
| T-004 | Définir la charte d'interface. | IHM-01 à 12 | T-003 | Fait | Section 12.1 du cahier des charges. |
| T-005 | Recommander l'organisation des dépôts. | — | — | Fait | Dépôt unique recommandé. |
| T-006 | Valider le cahier des charges V3 avec la DAF et l'équipe Hopitalia. | — | T-001 | Fait | Version validée, remarques intégrées (version 3.1). |
| T-007 | Confirmer le dépôt unique (monorepo). | — | T-005 | Fait | Décision écrite. |
| T-008 | Choisir l'authentification : fournisseur d'identité d'Hopitalia ou authentification propre. | §11.9, §17.2 | — | Fait | Décision écrite : connexion Hopitalia réutilisée, droits budgétaires propres au module (§17, point 2). |
| T-009 | Construire la nomenclature budgétaire sur le plan SYSCOHADA révisé (sections, chapitres, articles, comptes) et la faire relire par la DAF. | EF-REF-01, §17.3 | — | En cours | Fichier d'import de la nomenclature relu par la DAF. *Projet prêt : `docs/cadrage/nomenclature-budgetaire.csv`.* |
| T-010 | Vérifier si Hopitalia a un frontend et un dépôt central où le module doit s'intégrer. | §17.1 | — | Fait | Réponse écrite : application séparée (§17, point 10). |
| T-011 | Documenter les API Hopitalia utilisées (connexion, référentiels, pharmacie, facturation) et monter un environnement de test Hopitalia. | §13 | — | Fait | Note d'intégration écrite et vérifiée (`docs/cadrage/integration-hopitalia.md`) ; environnement de test Hopitalia en fonctionnement (11 vérifications sur 12 conformes du premier coup, la dernière après correction des paramètres de date). |
| T-012 | Confirmer PostgreSQL comme base de données. | ENF-08, §17.1 | — | Fait | Décision écrite. |
| T-013 | Trancher les points ouverts 4 à 9 de la section 17 (fournisseurs partagés, base du taux de consommation, traitement de l'avance, limites de débit, conservation, seuils hors marché). | §17 | T-006 | Fait | Chaque point a une décision inscrite dans le cahier des charges. |
| T-014 | Vérifier le rendu des 17 diagrammes Mermaid du cahier des charges. | — | T-001 | Fait | Tous les diagrammes s'affichent sur GitHub (vérifié par le responsable du projet). |
| T-015 | Constituer un jeu de données d'essai réaliste (budget, contrats, factures) avec la DAF, dont l'exemple de l'annexe 18.2. | §18.2 | T-009 | Fait | Jeu d'essai validé le 13/11/2026 (codes fictifs à remplacer, T-009). |
| T-016 | Établir la matrice des habilitations (profil × opération × seuil). | §3, RG-13 | T-006 | Fait | Matrice validée le 13/11/2026 (l'ordonnateur valide toujours). |
| T-017 | Obtenir de l'équipe Hopitalia un compte technique en lecture et la clé de vérification des jetons ; lui transmettre, hors du dépôt, les points de sécurité relevés. | §17.2, INT-01 | T-011 | En cours | Compte et clé fournis hors dépôt ; points de sécurité transmis par écrit. *Note de sécurité et besoins du module rédigés hors dépôt ; reste à transmettre et à recevoir le compte et la clé.* |

### P0.B — Dépôt et outillage

| ID | Tâche | Réf. | Dépend de | Statut | Critère de fin |
|---|---|---|---|---|---|
| T-020 | Initialiser le dépôt git et la branche `main`. | — | T-007 | Fait | `git log` montre le premier commit. |
| T-021 | Créer le dépôt distant et y pousser `main`. | — | T-020 | Fait | `gh repo view` fonctionne. |
| T-022 | Créer la structure `backend/`, `frontend/`, `docs/` ; déplacer le cahier des charges et les images dans `docs/`. | — | T-020 | Fait | Arborescence en place, liens internes à jour. |
| T-023 | Écrire `.gitignore` (Python, Node, environnements, `CLAUDE.local.md`). | — | T-020 | Fait | `git status` propre après installation (vérifié : aucun `.venv`, `node_modules`, `dist`, cache ni `.env` visible). |
| T-033 | Écrire `AGENTS.md` (règles du projet) et `CLAUDE.md` qui l'importe. | — | — | Fait | `CLAUDE.md` importe `AGENTS.md` ; liens vérifiés. |
| T-024 | Écrire le modèle de demande de fusion `.github/pull_request_template.md`. | — | T-020 | Fait | Modèle proposé à l'ouverture d'une demande de fusion (présent sur `main` depuis la demande n° 6). |
| T-025 | Protéger `main` : demande de fusion obligatoire, CI verte, signature DCO. | — | T-021, T-028 | Fait | Un push direct sur `main` est refusé : demande de fusion obligatoire et `ci-ok` exigé, administrateurs inclus (règle relue via l'API ; `ci-ok` affiché comme exigé sur la demande n° 6). |
| T-026 | Écrire le `README.md` : installation, lancement, tests, conventions. | — | T-022 | Fait | Un nouveau développeur lance le projet en suivant le README (commandes du README exécutées : Docker, backend, frontend, hooks). |
| T-027 | Écrire `docker-compose.yml` : PostgreSQL, backend, frontend. | ENF-01 | T-012, T-022 | Fait | `docker compose up` démarre les trois services (vérifié : base saine, `/health` et interface répondent). |
| T-028 | CI backend dans `.github/workflows/ci.yml` (job `backend`, lancé si `backend/**` ou le workflow change) : lint, format, typage, tests ; job de synthèse `ci-ok` et job `dco`. | ENF-11 | T-030 | Fait | CI verte sur une demande de fusion (demande n° 6 : `changements`, `backend`, `dco`, `ci-ok` verts ; push sur `main` vert). |
| T-029 | CI frontend dans `.github/workflows/ci.yml` (job `frontend`, lancé si `frontend/**` ou le workflow change) : format, lint, typage, tests, build. | ENF-11 | T-060 | Fait | CI verte sur une demande de fusion (demande n° 6 : job `frontend` vert). |
| T-030 | Outils qualité backend : `ruff`, `mypy`, `pytest`, configurés dans `pyproject.toml`. | — | T-022 | Fait | Commandes lancées en local et en CI (ruff, ruff format, mypy strict, pytest). |
| T-031 | Outils qualité frontend : ESLint (dont `jsx-a11y`), Prettier, `tsc --noEmit`. | IHM-07 | T-060 | Fait | Commandes lancées en local et en CI (Prettier, ESLint avec `jsx-a11y`, `tsc`). |
| T-032 | Hooks `pre-commit` pour les deux sous-projets. | — | T-030, T-031 | Fait | Un commit mal formaté est refusé (vérifié dans une copie jetable du dépôt : fichier Python indexé rejeté par ruff, clé privée et fichier frontend rejetés). |

### P0.C — Socle backend (lot 0)

| ID | Tâche | Réf. | Dépend de | Statut | Critère de fin |
|---|---|---|---|---|---|
| T-040 | Squelette FastAPI en couches : `domaine/`, `application/`, `adaptateurs/entree/`, `adaptateurs/sortie/`. | §10.1, ARC-D | T-022 | Fait | Le domaine et la couche application n'importent ni FastAPI ni SQLAlchemy (test `test_architecture.py`). |
| T-041 | Configuration par variables d'environnement (`pydantic-settings`). | — | T-040 | Fait | Aucun secret dans le code ; clé Hopitalia en `SecretStr`, absente de l'affichage (test). |
| T-042 | Accès base : SQLAlchemy 2, sessions, transactions. | — | T-012, T-040 | Fait | Tests sur PostgreSQL verts ; `Numeric(18, 2)` relu en `Decimal` exact. |
| T-043 | Migrations Alembic et première migration. | — | T-042 | Fait | `alembic upgrade head` sur une base vide, puis retour arrière complet (vérifié) ; migrations appliquées au démarrage du conteneur. |
| T-044 | Convention monétaire : `Numeric(18,2)` en base, `Decimal` en Python, chaîne décimale en JSON. | §11.1 | T-040 | Fait | Aller-retour JSON sans perte jusqu'à 9 999 999 999 999 999,99 ; nombres JSON et trois décimales refusés (tests). |
| T-045 | Préfixe de version `/api/v1` et publication OpenAPI. | §11.8, API-11 | T-040 | Fait | `/api/v1/openapi.json` publié ; toutes les routes métier sous `/api/v1` (test). |
| T-046 | Format d'erreur `application/problem+json` avec code métier. | §11.9 | T-040 | Fait | Erreurs métier et techniques en `problem+json` avec code stable (tests). |
| T-047 | Pagination par décalage (`page`, `taille`, max 100) et par curseur (`apres`). | §11.4, API-06 | T-040 | Fait | Pagination par décalage et par curseur testées ; curseur stable pendant des insertions (API-06). |
| T-048 | Tri et filtres sur liste blanche de champs. | §11.5, API-07 | T-047 | Fait | Paramètre ou champ de tri inconnu : `400` (tests). |
| T-049 | Idempotence : en-tête `Idempotency-Key`, table `CleIdempotence`, rejeu de la réponse. | §11.3, API-01 à 03 | T-042 | Fait | Tests API-01, API-02, API-03 verts, plus clé en cours (`409`), clé expirée et clé libérée après échec. |
| T-050 | Concurrence optimiste : `ETag`, `If-Match`, réponses `412` et `428`. | §11.3, API-05 | T-042 | Fait | Test API-05 vert (`428` sans `If-Match`, `412` si périmé). |
| T-051 | Limitation de débit par utilisateur et par client, en-têtes `RateLimit-*`, `429`. | §11.7, API-08 | T-040 | Fait | Test API-08 vert (`429`, `Retry-After`, en-têtes `RateLimit-*`, compteur par utilisateur). |
| T-052 | Connexion relayée vers Hopitalia (connexion, rafraîchissement, déconnexion) et vérification locale des jetons Hopitalia (HS512, clé en variable d'environnement). | ENF-02 | T-008, T-017 | Fait | Jeton valide accepté ; jeton absent, expiré ou mal signé refusé (`401`) ; agent sans profil refusé (`403`). Vérifié aussi contre une instance Hopitalia réelle. |
| T-039 | Gestion des comptes utilisateurs : création par l'administrateur, mot de passe haché (Argon2), réinitialisation, verrouillage après échecs répétés, désactivation, expiration des accès. | ENF-02, §17.2 | T-052 | Abandonné | *Abandonné : la connexion Hopitalia est réutilisée ; seuls les droits budgétaires sont gérés dans le module (T-053).* |
| T-053 | Habilitations : profils, permissions, seuils de montant. | §3, ENF-02 | T-052, T-016 | Fait | Appel non autorisé : `403` (test) ; matrice du code identique au document validé (test). Pas de seuil de montant : l'ordonnateur valide toujours (§17, point 16). |
| T-054 | Cloisonnement par établissement, appliqué côté serveur à chaque requête. | ENF-04, REC-17 | T-053 | Fait | Tests REC-17 et API-10 verts : un lecteur ne voit que son établissement, un autre établissement répond `404`. |
| T-055 | Journal d'audit en ajout seul (ancienne et nouvelle valeur, IP), protégé en base contre la modification. | EF-AUD-01, ENF-05 | T-042 | Fait | `UPDATE`, `DELETE` et `TRUNCATE` sur le journal échouent (déclencheurs PostgreSQL, tests). |
| T-056 | Ports transverses : `Horloge`, `JournaliseurAudit`, `StockagePieces`, `Notificateur`, avec implémentations de test. | §10.2 D | T-040 | Fait | Domaine et cas d'utilisation testés avec les doubles des ports, sans base ni réseau. |
| T-057 | Journalisation technique structurée et point de santé `/health`. | — | T-040 | Fait | `/health` répond ; journaux JSON avec identifiant de requête (tests et conteneur). |
| T-058 | Base de test isolée et fabriques de données pour les tests. | ENF-11 | T-043 | Fait | Base de test créée puis supprimée à chaque exécution ; transaction annulée après chaque test ; fabriques de données. |
| T-059 | Langue côté backend : lecture de `Accept-Language`, catalogues de messages `fr` et `en` pour `title` et `detail` des erreurs. | I18N-07 | T-046 | Fait | Même erreur en `fr` et en `en`, code identique (tests) ; chaque code traduit dans les deux langues. |

### P0.D — Socle frontend (lot 0)

| ID | Tâche | Réf. | Dépend de | Statut | Critère de fin |
|---|---|---|---|---|---|
| T-060 | Projet Vite + React + TypeScript. | §12.1 | T-022, T-010 | Fait | `npm run build` sans erreur (vérifié). |
| T-061 | Thème Ant Design centralisé dans `ConfigProvider` (palette, mode compact). | IHM-01 à 03 | T-060 | Fait | Aucune couleur en dur hors de `src/theme/theme.ts` (recherche dans le code) ; thème compact. |
| T-062 | Polices Lexend et Source Sans 3 hébergées avec l'application. | IHM-04 | T-060 | Fait | Aucune requête hors du serveur au chargement (parcours Playwright). |
| T-063 | Mettre en place `react-i18next` : langues `fr` (défaut) et `en`, fichiers JSON par domaine chargés à la demande, langue de repli. | I18N-01, 03 | T-060 | Fait | Changement de langue sans rechargement (parcours Playwright) ; mêmes clés en `fr` et en `en` (test) ; clé manquante signalée en développement. |
| T-076 | Règle de lint interdisant les textes en dur dans les composants. | I18N-02 | T-031, T-063 | Fait | Un texte en dur entre balises fait échouer le lint, donc la CI (vérifié). Limites notées dans POINTS_REPORTES.md. |
| T-077 | Choix de la langue : profil utilisateur, puis navigateur, puis français ; sélecteur dans l'en-tête. | I18N-04 | T-063, T-064 | Fait | Langue du profil appliquée à la connexion et conservée côté serveur (tests) ; sélecteur dans l'en-tête. |
| T-078 | Formats selon la langue (`Intl`) : montants, nombres, dates, pluriels ; Ant Design dans la langue choisie. | I18N-05, 06 | T-063, T-071 | Fait | Tests de formatage en `fr` et en `en` (montants, nombres, dates) ; Ant Design dans la langue choisie. |
| T-079 | Traduction des codes d'erreur de l'API côté frontend. | I18N-07 | T-063, T-068 | Fait | Chaque code d'erreur de l'API a sa traduction `fr` et `en` (test côté backend qui lit les fichiers du frontend). |
| T-064 | Gabarit de l'application : menu, fil d'Ariane, en-tête utilisateur et établissement. | IHM-08 | T-061 | Fait | Navigation utilisable sur ordinateur et à 375 px sans défilement horizontal (parcours Playwright). |
| T-065 | Routage avec liens profonds vers chaque fiche. | — | T-064 | Fait | Une adresse de fiche s'ouvre directement après connexion (test) ; nginx renvoie l'application pour toute adresse. |
| T-066 | Génération du client d'API avec `orval` depuis l'OpenAPI FastAPI. | §12.1 | T-045, T-060 | Fait | Client régénéré en une commande (`npm run api`), typé ; la CI vérifie qu'il est à jour. |
| T-067 | TanStack Query : cache, invalidation après validation, gestion de `409` et `412`. | §11.3 | T-066 | Fait | Conflit `412` : fiche rechargée et message clair (test) ; pas de nouvel essai automatique sur les erreurs 4xx. |
| T-068 | Affichage des erreurs `problem+json` : près du champ, ou en notification. | IHM-07 | T-067 | Fait | Erreur de champ affichée sous le champ (test). |
| T-069 | Connexion, déconnexion, expiration de session. | ENF-02 | T-052 | Fait | Session expirée : retour à la connexion avec un message (test) ; rafraîchissement automatique du jeton (test). |
| T-070 | Composant de tableau serveur : pagination, tri, filtres, sélection multiple, actions groupées. | IHM-09 | T-067 | Fait | Utilisé par la liste des établissements (pagination, tri, filtre de statut, désactivation groupée). |
| T-071 | Formatage des montants (`tabular-nums`, alignement à droite, `XOF`). | IHM-05 | T-060 | Fait | Tests de formatage ; montants formatés depuis la chaîne exacte, sans nombre flottant. |
| T-072 | Badges de statut avec libellé et icône (jamais la couleur seule). | IHM-06 | T-061 | Fait | Composant `BadgeStatut` unique, libellé et icône (test). |
| T-073 | Affichage adaptatif des listes sur petit écran (cartes ou défilement horizontal). | IHM-08 | T-070 | Fait | Cartes sous 768 px ; aucun débordement à 375 px (parcours Playwright). |
| T-074 | Respect de la préférence « mouvement réduit ». | IHM-11 | T-061 | Fait | Animations coupées dans le thème quand la préférence est active (test) et par CSS. |
| T-075 | Tests : Vitest pour les composants, Playwright pour les parcours. | ENF-11 | T-060 | Fait | Un test de chaque type passe en CI (demande n° 8 : 20 tests Vitest et 3 parcours Playwright verts ; 67 tests backend sur PostgreSQL). |

---

## P1 — Haute

### P1.A — Lot 1 : référentiels, exercices, budgets et crédits

| ID | Tâche | Réf. | Dépend de | Statut | Critère de fin |
|---|---|---|---|---|---|
| T-080 | Établissements et sites. | EF-REF-02 | T-054 | Fait | CRUD API + écran + tests. Sites par établissement : API, écran Paramétrage, tests (test_lot1). |
| T-081 | Centres de responsabilité (hiérarchie, responsable habilité). | EF-REF-02 | T-080 | Fait | CRUD API + écran + tests. Hiérarchie sans cycle, parent et site du même établissement ; responsable saisi par code agent. |
| T-082 | Sources de financement et programmes ou projets. | EF-REF-02 | T-080 | Fait | CRUD API + écran + tests. Sources (type, bailleur) et programmes (dates contrôlées) : API, écran, tests. |
| T-083 | Nomenclature hiérarchique (section, chapitre, article, paragraphe). | EF-REF-01 | T-009 | Fait | Import de la nomenclature reçue + arbre affiché. Nomenclature du cadrage importée (85 éléments, 45 paragraphes) ; arbre dans l'écran Nomenclature. |
| T-084 | Comptes budgétaires, comptes comptables et leur correspondance. | EF-REF-03 | T-083 | Fait | Correspondance consultable dans les deux sens. Compte budgétaire vers SYSCOHADA et `/comptes-comptables/{code}` en sens inverse ; testé. |
| T-085 | Fournisseurs et coordonnées de paiement (coordonnées chiffrées). | EF-REF-04, ENF-03 | T-080 | Fait | Numéro de compte chiffré en base, masqué à l'écran. Numéro chiffré (Fernet, `COORDONNEES_CLE`), affiché masqué, jamais en clair dans l'audit ; testé. |
| T-086 | Familles d'achats, types de dépenses (seuil hors marché), modes de règlement, comptes de trésorerie, types de pièces. | EF-REF-04 | T-080 | Fait | CRUD API + écrans + tests. Cinq référentiels sur les routes communes ; écran Paramétrage ; tests. |
| T-087 | Exercices budgétaires et périodes. | EF-BUD-01 | T-080 | Fait | Exercice ouvert avec ses périodes. Exercice ouvert avec 17 périodes (année, 4 trimestres, 12 mois) ; testé, parcours REC-01. |
| T-088 | Budgets (primitif, modificatif) par exercice et établissement. | EF-BUD-01 | T-087 | Fait | Un seul budget primitif par exercice et établissement. Second budget primitif refusé (`BUDGET_PRIMITIF_EXISTANT`) ; testé. |
| T-089 | Lignes budgétaires et leurs axes (compte, centre, source, programme, période). | EF-BUD-01 | T-084, T-088 | Fait | Saisie et liste filtrable. Axes contrôlés (paragraphe, centre, source, programme, période) ; liste filtrable ; testé. |
| T-090 | Import asynchrone des dotations (`202`, suivi, rapport d'anomalies). | EF-BUD-02, REC-01 | T-089 | Fait | Import du jeu d'essai T-015, anomalies listées ligne par ligne. Lignes du jeu d'essai T-015 importées sans anomalie ; anomalies listées par ligne ; testé et parcours REC-01. |
| T-091 | Notifications de crédits. | EF-BUD-03 | T-089 | Fait | Notification rattachée à ses lignes. Somme des lignes égale au montant (`NOTIFICATION_INCOHERENTE`) ; onglet de la fiche budget ; testé. |
| T-092 | Paramètres de calcul par établissement (`ParametreCalcul`). | §6 | T-080 | Fait | Chaque option paramétrable de la section 6 est lisible depuis ce paramétrage. Les 4 options de la section 6 lues et modifiées par établissement (fiche établissement) ; testé. |
| T-093 | Service unique de calcul des indicateurs de ligne (6.1). | §6.1, RG-14, ARC-S | T-089, T-092 | Fait | Tests unitaires de chaque formule ; aucune autre implémentation. `domaine/indicateurs.py`, seule implémentation ; tests unitaires de chaque formule. |
| T-094 | Endpoint `/lignes-budgetaires/{id}/disponibilite`. | EF-BUD-06, 07 | T-093 | Fait | Valeurs conformes aux tests de T-093. Endpoint conforme aux tests de T-093 ; situation du budget avec totaux. |
| T-095 | Révisions budgétaires (modificatif, virement, réallocation), effectives après validation. | EF-BUD-04, 05 | T-089, T-110 | Fait | Un virement non validé ne change pas les disponibles. Virement sans effet avant la décision de l'ordonnateur (testé). Circuit fixe du point 16 de la section 17 (visa DAF puis ordonnateur) ; T-110 à T-112 le rendront paramétrable. |
| T-096 | Écrans du lot 1 : budgets, lignes, disponibilités, révisions. | EF-BUD-06 | T-094, T-070 | Fait | Parcours Playwright REC-01 vert. Écrans Paramétrage, Nomenclature, Budgets, fiche budget et fiche ligne ; parcours Playwright REC-01 vert (ordinateur et téléphone). |

### P1.B — Workflow transverse (validations, pièces, corrections)

| ID | Tâche | Réf. | Dépend de | Statut | Critère de fin |
|---|---|---|---|---|---|
| T-110 | Interfaces `Validable`, `Justifiable`, `Annulable`, `Derogeable`. | §7.6, ARC-I | T-040 | Fait | Aucune implémentation par exception « non supporté ». `domaine/workflow.py` ; la révision implémente `Validable` et `Justifiable`, rien d'autre (aucune méthode « non supportée »). |
| T-111 | Statuts de référence, statuts personnalisés et transitions configurables. | §7.6 | T-110 | Fait | Une transition non paramétrée est refusée. Statuts personnalisés rattachés à un statut de référence ; transition incohérente refusée ; transition non paramétrée refusée (`test_transition_non_parametree_refusee`). |
| T-112 | Circuits de validation (étapes, profils, seuils, service). | EF-ENG-04 | T-111, T-053 | Fait | Un circuit à 2 étapes s'exécute dans l'ordre. Circuits par établissement, service et tranche de montant, figés à la soumission ; ordonnateur en dernière étape ; testé (`test_circuit_a_deux_etapes_s_execute_dans_l_ordre`) ; écran dans Paramétrage. |
| T-113 | Ressource `POST /{ressource}/{id}/validations` (visa, motif, décision). | §11.1 | T-112 | Fait | Validation, rejet et retour pour correction testés. Route générique ; visa, rejet, retour pour correction, correction et renvoi au circuit testés (`test_retour_pour_correction_puis_validation`). |
| T-114 | Séparation des tâches : créateur ≠ valideur ≠ payeur selon le circuit. | RG-13, REC-13 | T-113 | En cours | Test REC-13 vert. Créateur ≠ valideur et un visa par agent et par cycle, selon le circuit : fait et testé (`test_rg13_...`). Reste le payeur, avec les paiements (lot 5) : REC-13 complet à ce moment. |
| T-115 | Délégations temporaires. | §7.6 | T-112 | Fait | Une délégation expirée n'autorise plus rien. Délégation datée, visa au nom du délégant, révocation ; une délégation expirée n'autorise plus rien (`test_delegation_active_puis_expiree`) ; écran Délégations. |
| T-116 | Immuabilité des objets validés (`409` sur `PUT`, `PATCH`, `DELETE`). | RG-18, API-04 | T-113 | Fait | Test API-04 vert. Mécanisme commun (`exiger_modifiable`) : `PATCH` d'une révision en circuit, validée ou rejetée → `409` (testé). API-04 porte sur l'engagement : vérifié avec T-140. API-04 vérifié : `PATCH` d'un engagement validé répond 409 (`test_circuit_engage_et_immuabilite`). |
| T-117 | Annulations et contre-opérations tracées. | RG-09, RG-18 | T-116, T-140 | Fait | L'opération initiale reste visible avec son annulation. Annulation : contre-opération par imputation ; l'engagement initial reste visible avec ses annulations (`test_annulation_partielle_puis_totale`). |
| T-118 | Dérogations par nature et montant. | RG-19 | T-113, T-140 | Fait | Une dérogation ne couvre que son objet et son montant. Dérogation validée par le circuit ; elle ne couvre que sa nature, son objet et son montant (tests moteur et API). |
| T-119 | Pièces justificatives : dépôt, empreinte SHA-256, type, contrôle des pièces obligatoires. | EF-DOC-01, 02 | T-056 | Fait | Fichier altéré détecté par l'empreinte. Dépôt multipart, empreinte SHA-256, types de fichiers limités, pièces obligatoires par type d'objet ; fichier altéré détecté (`test_pieces_empreinte_et_pieces_obligatoires`). |
| T-120 | Composants frontend : historique de validation (`Timeline`), boutons valider / rejeter, dépôt de pièces. | IHM-07 | T-113, T-119 | Fait | Réutilisés par toutes les fiches. `Validations` (circuit, `Timeline`, valider, rejeter, retourner) et `Pieces` (dépôt, téléchargement) prennent la ressource en paramètre ; utilisés par la fiche révision, à réutiliser par les fiches suivantes. |
| T-121 | Gestion des habilitations dans le module : attribuer et retirer les profils budgétaires des agents Hopitalia, par établissement (API et écran). | §3, RG-13 | T-053 | Fait | Un administrateur attribue un profil sans ligne de commande ; chaque changement est tracé dans le journal d'audit (10 tests ; vérifié avec une instance Hopitalia réelle). Pas d'auto-attribution ; dépendance à T-110 levée : aucun circuit de validation ici. |

### P1.C — Lot 2 : contrats, marchés, avenants

| ID | Tâche | Réf. | Dépend de | Statut | Critère de fin |
|---|---|---|---|---|---|
| T-130 | Contrats et marchés (fiche complète, date de signature ou de notification obligatoire). | EF-CTR-01, 02, RG-03 | T-085, T-110 | Fait | Contrat sans date de signature ni de notification refusé. Fiche complète, brouillon puis soumission ; contrat sans date de signature ni de notification refusé (`test_rg03_...`, contrat et marché). |
| T-131 | Ventilation du contrat sur les lignes (`ImputationContrat`, somme = montant). | EF-CTR-03, RG-15 | T-130 | Fait | Ventilation incohérente refusée à la validation. Ventilation dans le contrat, remplacée en bloc ; contrôlée à la soumission et à la validation (`test_rg15_ventilation_incoherente_refusee`). |
| T-132 | Avenants : montant antérieur, variation, nouveau plafond, effet après validation. | EF-CTR-04, RG-11, REC-04 | T-130, T-113 | Fait | Test REC-04 vert. Avenant soumis, sans effet avant validation ; montant avant et nouveau plafond relevés ; plafond sous l'engagé refusé (`test_rec04_avenant_effectif_apres_validation`). |
| T-133 | Échéancier, lots et tranches, ordres de service. | EF-CTR-05 | T-130 | Fait | CRUD + affichage dans la fiche. Échéancier, lots et tranches (total contrôlé, figés après validation), ordres de service, révisions de prix ; onglet Exécution de la fiche. |
| T-134 | Avance, retenue de garantie, révisions de prix (montants calculés, pas stockés). | EF-CTR-05, RG-14 | T-130 | Fait | Montants recalculés depuis les déductions. Taux et conditions sur le contrat ; avance, récupéré, retenu et libéré calculés depuis les déductions (`test_avance_et_retenue_recalculees_depuis_les_deductions`). Les déductions réelles viendront des liquidations (lot 4). |
| T-135 | Calculs contrat (6.2) dans le service unique d'indicateurs. | §6.2, ARC-S | T-093, T-130 | Fait | Tests unitaires de chaque formule. `calculer_indicateurs_contrat` dans `domaine/indicateurs.py` ; chaque formule testée sur le jeu d'essai de l'annexe 18.2. |
| T-136 | Endpoint `/contrats/{id}/synthese`. | EF-CTR-06, §18.1 | T-135 | Fait | Fiche de synthèse complète en JSON. Synthèse complète en JSON (annexe 18.1, plus avance, retenue et révisions de prix) ; testée. |
| T-137 | Tests de substitution : les tests de `Contrat` passent avec `Marche`. | ARC-L | T-130 | Fait | Suite paramétrée verte. Tests d'API paramétrés contrat et marché, et règle de domaine testée avec `Contrat` et `Marche` : verts. |
| T-138 | Écrans : liste des contrats (filtres, niveau de consommation) et fiche à onglets. | §18.1 | T-136, T-120 | Fait | Parcours Playwright REC-02 vert. Liste filtrable (dont consommation) et fiche à onglets ; parcours Playwright REC-02 vert sur ordinateur et téléphone. |

### P1.D — Lot 2 : engagements et contrôles

| ID | Tâche | Réf. | Dépend de | Statut | Critère de fin |
|---|---|---|---|---|---|
| T-140 | Engagements et imputations (somme des imputations = montant). | EF-ENG-01, 02, RG-01, RG-15 | T-089, T-110 | Fait | Engagement incohérent refusé. Engagement en brouillon, imputations, exercice tiré des lignes ; engagement incohérent refusé (`test_rg15_engagement_incoherent_refuse`). |
| T-141 | Moteur de contrôles extensible (`RegleControle`, `MoteurControles`). | §10.2 O, ARC-O | T-040 | Fait | Ajouter un contrôle ne modifie pas le moteur (démontré par un contrôle de test). `domaine/controles.py` : un contrôle de test ajouté sans toucher au moteur (`test_moteur_extensible_et_derogation_limitee`). |
| T-142 | Contrôle de disponibilité des crédits. | RG-02, EF-ENG-03 | T-141, T-093 | Fait | Dépassement bloqué sans dérogation. `ControleCredits` ; dépassement bloqué sans dérogation (`test_rg02_credit_insuffisant_et_derogation_limitee`). |
| T-143 | Contrôle atomique du crédit (verrou de ligne ou transaction sérialisée). | RG-20, ENF-08, REC-16 | T-142 | Fait | Test de concurrence REC-16 : un seul engagement passe. Lignes et contrat verrouillés à la validation finale ; test de concurrence REC-16 sur deux connexions réelles : un seul passe ; le test échoue si le verrou est retiré. |
| T-144 | Contrôle du plafond contractuel. | RG-04 | T-141, T-135 | Fait | Dépassement bloqué sans avenant ni dérogation. `ControlePlafondContrat` ; dépassement bloqué sans avenant ni dérogation (`test_rec03_plafond_du_marche`). |
| T-145 | Contrôle de cohérence engagement / contrat / fournisseur. | EF-ENG-03 | T-141 | Fait | Fournisseur différent du titulaire refusé. `ControleCoherenceContrat` ; bénéficiaire différent du titulaire refusé, non dérogeable. |
| T-146 | Détection des doublons d'engagement. | EF-ENG-03 | T-141 | Fait | Doublon signalé. `DetectionDoublonEngagement` ; doublon signalé (`test_doublon_signale`). |
| T-147 | Dépenses hors marché et contrôle de seuil. | EF-DHM-01 | T-140, T-141 | Fait | Seuil dépassé bloqué ; tests `Engagement` verts avec `DepenseHorsMarche` (ARC-L). `DepenseHorsMarche` et `ControleSeuilHorsMarche` ; seuil dépassé ou absent bloqué ; tests d'API paramétrés décision et hors marché (ARC-L). |
| T-148 | Annulation partielle et clôture avec désengagement automatique du reliquat. | EF-ENG-05 | T-117, T-140 | Fait | Disponible recrédité du reliquat, trace d'annulation créée. Annulation partielle et totale faites (disponible recrédité, trace créée). Clôture d'un engagement partiellement exécuté : reliquat non liquidé désengagé, disponible recrédité, trace créée (`test_t148_cloture_desengage_le_reliquat`). |
| T-149 | Idempotence de la création d'engagement. | §11.3 | T-049, T-140 | Fait | Rejeu sans doublon. Rejeu avec la même clé : même engagement, aucun doublon (`test_idempotence_de_la_creation`). |
| T-150 | Écrans : demande d'engagement, contrôle, validation, liste. | — | T-140, T-120 | Fait | Parcours Playwright REC-03 vert. Liste, demande, fiche (contrôles, dérogations, validation, pièces, annulations) ; parcours Playwright REC-03 vert sur ordinateur et téléphone. |

### P1.E — Lot 3 : commandes, réceptions et service fait

| ID | Tâche | Réf. | Dépend de | Statut | Critère de fin |
|---|---|---|---|---|---|
| T-160 | Bons de commande, tranches et ordres de service, avec lignes. | EF-CMD-01 | T-140 | Fait | Commande impossible sur un engagement non validé. Bons de commande, tranches et ordres de service avec lignes ; commande refusée sur un engagement non validé, total limité au montant net (`test_commande_seulement_sur_engagement_valide`). |
| T-161 | Réceptions totales et partielles, en plusieurs étapes. | EF-REC-01 | T-160 | Fait | Plusieurs réceptions pour une commande. Deux réceptions sur une commande, partielle puis totale (`test_receptions_partielles_puis_totale`). |
| T-162 | Lignes de réception : quantités reçues, acceptées, rejetées. | EF-REC-02 | T-161 | Fait | Acceptée + rejetée ≤ reçue. Acceptée + rejetée ≤ reçue ; cumul accepté ≤ commandé, contrôlé à la saisie et sous verrou à la validation. |
| T-163 | Réserves et levée des réserves. | EF-REC-03 | T-161 | Fait | Réserves non levées listées. Réserves émises et levées ; réserves non levées listées (`test_reserves_et_levee`). |
| T-164 | Attestation de service fait et pièces (BL, PV). | EF-REC-04 | T-161, T-119 | Fait | Pièces obligatoires contrôlées. Attestation de service fait (une par réception) ; procès-verbal obligatoire contrôlé avant validation (`test_pieces_obligatoires_et_attestation`). |
| T-165 | Validation de la réception par le service réceptionnaire. | EF-REC-05 | T-161, T-113 | Fait | Réception non validée inutilisable comme preuve. Circuit « Service fait » (VAL) ; une réception non validée ne réduit pas le reste à recevoir ni le réceptionné du marché. |
| T-166 | Suivi des retards et des prestations non réalisées. | EF-REC-06 | T-161 | Fait | Liste des commandes en retard. Commandes en retard listées (`GET /bons-commande?enRetard=true`) ; reste à recevoir par ligne (`test_commandes_en_retard`). |
| T-167 | Écrans : commandes, réceptions, service fait. | — | T-165, T-120 | Fait | Parcours Playwright REC-05 vert. Page Commandes (retards, réserves), fiche commande (réceptions, réserves, attestation, service fait, pièces), onglet Commandes de l'engagement ; parcours Playwright REC-05 vert. |

### P1.F — Lot 4 : factures, liquidations, rapprochement

| ID | Tâche | Réf. | Dépend de | Statut | Critère de fin |
|---|---|---|---|---|---|
| T-170 | Factures (tous types) rattachées à un engagement. | EF-FAC-01, 02, RG-05 | T-140 | Fait | Facture sans engagement refusée. Factures de tous types rattachées à un engagement validé, fournisseur repris de l'engagement ; facture sans engagement valide refusée (`test_facture_rattachee_a_un_engagement_valide`). |
| T-171 | Détection des doublons de facture (`409` avec référence). | EF-FAC-03, RG-16, REC-11 | T-170 | Fait | Test REC-11 vert. `409 FACTURE_DOUBLON` avec la référence du doublon, levée motivée tracée au journal d'audit (`test_rec11_doublon_de_facture`). |
| T-172 | Avoirs liés à la facture d'origine. | EF-FAC-02 | T-170 | Fait | Facture d'origine intacte, cumuls nets corrects. Avoir négatif lié à sa facture d'origine, plafonné ; facture d'origine intacte, cumuls nets corrects (`test_avoir_et_decomptes`). |
| T-173 | Décomptes successifs (marchés de travaux). | EF-FAC-02 | T-170 | Fait | Cumul des décomptes correct. Numéro de décompte et cumul des décomptes (`test_avoir_et_decomptes`). |
| T-174 | Liquidations par imputation d'engagement. | EF-LIQ-03, RG-17 | T-170 | Fait | Facture sur 2 lignes donne 2 liquidations. Une liquidation par imputation ; une facture sur 2 lignes donne 2 liquidations, imputation étrangère refusée (`test_une_liquidation_par_imputation`). |
| T-175 | Calculs de déduction extensibles (`CalculDeduction` : retenue de garantie, pénalité, avance récupérée, retenue à la source). | §6.3, §10.2 O | T-174 | Fait | Net à payer = liquidé − déductions, testé par type. `CalculDeduction` (retenue de garantie, avance récupérée au prorata et plafonnée, retenue à la source, montant saisi) ; net à payer testé par type (`test_calculs_de_deduction_par_type`). |
| T-176 | Contrôle du service fait avant liquidation. | RG-06 | T-141, T-165 | Fait | Liquidation sans réception requise bloquée. `ControleServiceFait` : liquidation sans réception validée bloquée, non dérogeable, factures d'avance dispensées (`test_rg06_service_fait_avant_liquidation`). |
| T-177 | Contrôle du reste dû et de la facture supérieure à la réception. | EF-LIQ-05, REC-07 | T-141, T-174 | Fait | Test REC-07 vert. `ControleResteDu` (dérogeable) et `ControleFactureSuperieureReception` (alerte non bloquante) ; test REC-07 vert (`test_rec07_reste_du_et_facture_superieure_a_la_reception`). |
| T-178 | Rejet motivé, retour pour correction, validation de la liquidation. | EF-LIQ-04 | T-113, T-174 | Fait | Historique complet consultable. Liquidation validable par le circuit (DAF puis ordonnateur) ; retour, rejet, validation et historique des visas (`test_circuit_de_liquidation_et_indicateurs`, `test_rec12_rejet_correction_et_piste_d_audit`). |
| T-179 | Calculs par liquidation et facture (6.3) dans le service unique. | §6.3, ARC-S | T-093, T-174 | Fait | Tests unitaires de chaque formule, dont la règle de l'avance. `calculer_liquidation` et `reste_a_payer_facture` dans `domaine/indicateurs.py`, branchés sur les indicateurs des lignes et des contrats (`test_formules_6_3_et_regle_de_l_avance`). |
| T-180 | Rapprochement commande / réception / facture / paiement, avec explication des écarts. | §9.1 | T-174 | Fait | Écart sans explication non validable. Écarts commande, réception, facture et paiement ; écart sans explication refusé (`ECART_NON_EXPLIQUE`, `test_rapprochement_ecart_explique`). |
| T-181 | Écrans : traitement des factures, liquidation, rapprochement. | §18.1 | T-178, T-120 | Fait | Parcours Playwright REC-06 et REC-12 verts. Page Factures, fiche facture (liquidations, contrôles, dérogation, circuit, rapprochement, facture numérisée) ; parcours Playwright REC-06 et REC-12 verts sur ordinateur et téléphone, et à 300 px. |

### P1.G — Lot 5 : ordonnancement et paiements

| ID | Tâche | Réf. | Dépend de | Statut | Critère de fin |
|---|---|---|---|---|---|
| T-185 | Ordonnancements et lignes d'ordonnancement. | EF-ORD-01, 02 | T-174 | À faire | Une liquidation dans un seul ordonnancement actif. |
| T-186 | Statuts : transmis, complément demandé, suspendu, rejeté (liquidations libérées), pris en charge. | EF-ORD-03 | T-185, T-111 | À faire | Liquidation rejetée retransmissible, historique conservé. |
| T-187 | Paiements et allocations par liquidation. | EF-PAI-01, 02 | T-185 | À faire | Somme des allocations = montant du paiement. |
| T-188 | Paiement groupé ventilé. | EF-PAI-02, REC-10 | T-187 | À faire | Test REC-10 vert. |
| T-189 | Interdiction de payer au-delà du solde dû. | RG-07 | T-187, T-141 | À faire | Dépassement bloqué sans dérogation. |
| T-190 | Statut de la facture recalculé (partiellement payée, payée). | RG-08, EF-PAI-03 | T-187 | À faire | Tests REC-08 et REC-09 verts. |
| T-191 | Idempotence obligatoire de `POST /paiements`. | §9.2, API-01 | T-049, T-187 | À faire | Test API-01 vert sur les paiements. |
| T-192 | Annulation de paiement par contre-opération. | RG-18 | T-117, T-187 | À faire | Paiement annulé visible, soldes recalculés. |
| T-193 | Écrans : ordonnancement, saisie de paiement, ventilation. | — | T-190, T-120 | À faire | Parcours Playwright REC-08 à REC-10 verts. |

### P1.H — Recette de la chaîne de dépense

| ID | Tâche | Réf. | Dépend de | Statut | Critère de fin |
|---|---|---|---|---|---|
| T-195 | Scénario de bout en bout de l'annexe 18.2 (marché de 100 M XOF). | REC-14, §18.2 | T-193, T-015 | À faire | Tous les montants de l'annexe retrouvés. |
| T-196 | Test d'absence de fonction de passation dans l'API et les écrans. | RG-12, REC-15 | T-193 | À faire | Aucun point d'API ni écran de passation. |
| T-197 | Revue d'architecture ARC-S, ARC-O, ARC-L, ARC-I, ARC-D. | §15.3 | T-193 | À faire | Grille de revue complétée, écarts corrigés. |
| T-198 | Recette utilisateur des lots 1 à 5 avec la DAF. | §15.4 | T-195 | À faire | Procès-verbal de recette partiel signé. |

---

## P2 — Moyenne

### P2.A — Lot 6 : tableaux de bord et indicateurs

| ID | Tâche | Réf. | Dépend de | Statut | Critère de fin |
|---|---|---|---|---|---|
| T-210 | Tableau de bord de la direction. | §14.1 | T-195 | À faire | Engagé, réceptionné, facturé, liquidé, transmis et payé distincts (REC-14). |
| T-211 | Indicateurs opérationnels (taux, restes, âge des factures, délai moyen). | §14.2 | T-210 | À faire | Valeurs conformes à la section 6. |
| T-212 | Filtres : exercice, période, service, compte, fournisseur, marché, source. | §14.1 | T-210 | À faire | Chaque filtre testé. |
| T-213 | Jauges de consommation avec repères 80 / 90 / 100 % et tableau équivalent. | IHM-10 | T-210 | À faire | Valeur lisible en texte, sans dépendre de la couleur. |
| T-214 | Tableau de bord des restes à payer et des factures en attente. | §18.1 | T-210 | À faire | Liste exportable. |

### P2.B — Lot 6 : alertes

| ID | Tâche | Réf. | Dépend de | Statut | Critère de fin |
|---|---|---|---|---|---|
| T-220 | Règles d'alerte paramétrables (`RegleAlerte`). | §14.3 | T-092 | À faire | Seuils et délais modifiables par établissement. |
| T-221 | Alertes immédiates déclenchées par les contrôles (crédit, plafond, doublon, service fait, paiement). | §14.3 | T-220, T-141 | À faire | Chaque contrôle bloquant crée son alerte. |
| T-222 | Alertes planifiées (seuils 80/90/100 %, factures échues, engagements anciens, échéances de contrat). | §14.3 | T-220 | À faire | Tâche planifiée testée avec une horloge simulée. |
| T-223 | Alerte de modification après validation. | §14.3, RG-18 | T-116, T-220 | À faire | Tentative tracée et signalée. |
| T-224 | Centre d'alertes (liste, marquer comme lue) et pagination par curseur. | §11.2 | T-221 | À faire | Écran et API testés. |
| T-225 | Notifications par courriel (option par règle), dans la langue du destinataire. | §7.6, I18N-08 | T-222, T-056, T-059 | À faire | Courriel reçu en environnement de test, dans la langue du destinataire. |

### P2.C — Lot 6 : états, audit, clôture

| ID | Tâche | Réf. | Dépend de | Statut | Critère de fin |
|---|---|---|---|---|---|
| T-230 | Moteur d'états : PDF, tableur, JSON (`/etats/{code}`), dans la langue de l'utilisateur. | ENF-09, I18N-08 | T-195, T-059 | À faire | Un état produit dans les trois formats, en `fr` et en `en`. |
| T-231 | États budgétaires : budget primitif et révisé, crédits disponibles. | §14.4 | T-230 | À faire | Totaux identiques au tableau de bord. |
| T-232 | États d'engagement et d'exécution des contrats. | §14.4 | T-230 | À faire | Idem. |
| T-233 | États des commandes, réceptions, factures, liquidations. | §14.4 | T-230 | À faire | Idem. |
| T-234 | États des paiements, rapprochements et restes (à engager, liquider, payer). | §14.4 | T-230 | À faire | Idem. |
| T-235 | État des dépenses par service, compte, nature, période ; contrats arrivant à échéance. | §14.4 | T-230 | À faire | Idem. |
| T-236 | Consultation du journal d'audit et rapport d'audit (profil auditeur, lecture seule). | EF-AUD-01, §14.4 | T-055 | À faire | Test API-06 vert ; aucune action de modification pour l'auditeur. |
| T-237 | Journalisation des connexions et opérations sensibles. | EF-AUD-02 | T-052, T-055 | À faire | Connexions réussies et échouées tracées. |
| T-238 | Recherche transverse (numéro, date, fournisseur, montant, compte, service). | EF-DOC-03 | T-195 | À faire | Résultats en moins de 3 s sur un exercice. |
| T-239 | Clôture d'exercice avec report des engagements restant à payer. | EF-BUD-09, RG-10 | T-195 | À faire | Historique intact, restes rattachés au nouvel exercice. |
| T-240 | Réouverture d'exercice motivée. | §7.2 | T-239 | À faire | Réouverture tracée. |

### P2.D — Qualité, sécurité et exploitation

| ID | Tâche | Réf. | Dépend de | Statut | Critère de fin |
|---|---|---|---|---|---|
| T-245 | Couverture de tests des règles RG-01 à RG-20 (une règle, au moins un test nommé). | ENF-11 | T-195 | À faire | Tableau règle → test complet. |
| T-246 | Automatisation des scénarios REC-01 à REC-18. | §15.1 | T-195 | À faire | Tous verts en CI. |
| T-247 | Automatisation des scénarios API-01 à API-11. | §15.2 | T-193 | À faire | Tous verts en CI. |
| T-248 | Vérification de conformité OpenAPI publiée / API réelle. | API-11 | T-045 | À faire | Test de contrat en CI. |
| T-249 | Audit d'accessibilité (contraste, clavier, focus, libellés). | IHM-07 | T-193 | À faire | Aucun défaut bloquant. |
| T-250 | Tests responsive à 375, 768, 1024 et 1440 px. | IHM-08 | T-193 | À faire | Captures Playwright sans débordement. |
| T-251 | Tests de performance à volumétrie d'un exercice. | ENF-07 | T-195 | À faire | Lectures < 1 s (95 %), tableaux de bord < 3 s. |
| T-252 | Revue de sécurité (OWASP, dépendances, secrets, chiffrement des coordonnées bancaires). | ENF-03 | T-195 | À faire | Aucune faille critique ouverte. |
| T-253 | Sauvegardes automatiques et test de restauration. | ENF-06 | T-027 | À faire | Restauration réussie et chronométrée. |
| T-254 | Environnement de recette déployé. | — | T-027 | À faire | Accessible aux testeurs de la DAF. |

---

## P3 — Basse

### P3.A — Lot 7 : intégrations

| ID | Tâche | Réf. | Dépend de | Statut | Critère de fin |
|---|---|---|---|---|---|
| T-200 | Journal d'intégration, reprises automatiques et manuelles, idempotentes. | INT-07 | T-049 | À faire | Échange en échec repris sans doublon. |
| T-201 | Import des fournisseurs et services depuis Hopitalia (identifiant externe, désactivation sans suppression). | INT-01, EF-REF-05 | T-011, T-017, T-200 | À faire | Deux synchronisations successives sans doublon ; un fournisseur retiré d'Hopitalia est désactivé. |
| T-202 | Import des bons de commande et approvisionnements de la pharmacie Hopitalia, rattachement aux engagements, annulation des réceptions supprimées. | INT-03 | T-011, T-017, T-160, T-161, T-200 | À faire | Approvisionnement importé une seule fois ; suppression dans Hopitalia annule la réception avec trace (EF-REC-07). |
| T-203 | Échange avec la facturation patient et le recouvrement (volet recettes). | INT-02 | T-011, T-017, T-262 | À faire | Facturé et encaissé alimentés par interface. *Bloqué : T-011.* |
| T-204 | Échange avec la banque (confirmation des virements). | INT-04 | T-187 | Abandonné | *Abandonné : confirmations de virement saisies à la main dans le module (§17, point 17).* |
| T-205 | Export vers la comptabilité par fichier (tableur, CSV). | INT-04 | T-187, T-206 | À faire | Fichier accepté par le service comptable. |
| T-206 | Import et export structurés (budgets, engagements, liquidations, paiements). | INT-05 | T-200 | À faire | Aller-retour export → import sans perte. |
| T-207 | Identifiants uniques partagés entre modules. | INT-06 | T-200 | À faire | Aucun doublon après deux synchronisations. |

### P3.B — Volet recettes (activable)

| ID | Tâche | Réf. | Dépend de | Statut | Critère de fin |
|---|---|---|---|---|---|
| T-260 | Activation du volet par établissement. | §7.2 | T-080 | À faire | Volet invisible quand il est désactivé. |
| T-261 | Recettes et débiteurs (nature, service, source, période). | EF-RCT-01 | T-260 | À faire | CRUD API + écran + tests. |
| T-262 | Calculs : facturé, encaissé, reste à recouvrer, taux. | EF-RCT-02, RG-14 | T-261 | À faire | Tests unitaires. |
| T-263 | Tableau de bord des recettes. | EF-RCT-02 | T-262 | À faire | Filtres par nature, service, période. |

### P3.C — Options d'interface

| ID | Tâche | Réf. | Dépend de | Statut | Critère de fin |
|---|---|---|---|---|---|
| T-270 | Thème sombre (algorithme sombre d'Ant Design). | IHM-01 | T-061 | À faire | Contrastes conformes en mode sombre. |
| T-271 | Préférences utilisateur (densité, colonnes visibles des tableaux). | IHM-02 | T-070 | À faire | Préférences conservées entre les sessions. |
| T-272 | Traduction anglaise complète et relue de tous les écrans. | I18N-01 | T-193 | À faire | Aucune clé `en` manquante (contrôle automatique). |
| T-273 | Compatibilité écriture de droite à gauche (propriétés CSS logiques, `direction` d'Ant Design). | I18N-10 | T-061 | À faire | Gabarit affiché correctement en mode droite à gauche de test. |

### P3.D — Livrables documentaires

| ID | Tâche | Réf. | Dépend de | Statut | Critère de fin |
|---|---|---|---|---|---|
| T-280 | Dictionnaire des données (généré depuis le modèle). | §16 | T-195 | À faire | Chaque table et champ documenté. |
| T-281 | Description des workflows et matrice des habilitations finale. | §16 | T-112, T-016 | À faire | Validée par la DAF. |
| T-282 | Documentation OpenAPI publiée et guide d'intégration. | §16 | T-248 | À faire | Publiée avec la version. |
| T-283 | Guide utilisateur (par profil). | §16 | T-198 | À faire | Relu par un utilisateur de chaque profil. |
| T-284 | Guide d'administration (paramétrage, circuits, alertes). | §16 | T-198 | À faire | Un administrateur paramètre un établissement seul. |
| T-285 | Plan de déploiement, de sauvegarde, de reprise et de maintenance. | §16 | T-253 | À faire | Validé par l'exploitation. |
| T-286 | Procès-verbal de recette final. | §15.4 | T-246, T-198 | À faire | Signé par les représentants de l'établissement. |

---

## Journal des changements de statut

| Date | Tâche | Ancien statut | Nouveau statut | Commentaire |
|---|---|---|---|---|
| 13/11/2026 | T-001 à T-005 | — | Fait | Cahier des charges V3, choix techniques, charte d'interface, recommandation de dépôt unique. |
| 13/11/2026 | T-008 à T-011, T-201 à T-205 | — | Bloqué | Informations externes attendues. |
| 13/11/2026 | T-059, T-063, T-076 à T-079, T-272, T-273 | — | À faire | Ajout de l'internationalisation (I18N-01 à 10). |
| 13/11/2026 | T-023 | À faire | En cours | `.gitignore` créé à la racine ; à vérifier par `git status` après T-020 et l'installation des dépendances. |
| 13/11/2026 | T-033 | — | Fait | `AGENTS.md` et `CLAUDE.md` créés. |
| 13/11/2026 | T-007, T-020, T-021 | En attente, À faire | Fait | Dépôt unique `hopitalia-budget` créé sur GitHub, `main` poussée (« Init Commit »). |
| 13/11/2026 | T-012, T-013 | En attente | Fait | PostgreSQL retenu ; points 4 à 9 décidés à titre provisoire (section 17 du cahier des charges), à confirmer par la DAF. |
| 13/11/2026 | T-006, T-014, T-015, T-016 | À faire | En cours | Dossier de cadrage prêt dans `docs/cadrage/` (questionnaires, matrice, jeu d'essai) ; en attente des réponses DAF et Hopitalia. Diagrammes à vérifier sur GitHub. |
| 13/11/2026 | T-006, T-008, T-010, T-015, T-016 | En cours, Bloqué | Fait | Réponses de cadrage : cahier des charges validé (v3.1), authentification propre, application séparée, jeu d'essai et matrice validés. |
| 13/11/2026 | T-009, T-205 | Bloqué | À faire | Nomenclature construite sur le plan SYSCOHADA révisé ; export comptable par fichier. |
| 13/11/2026 | T-201, T-204 | À faire, Bloqué | Abandonné | Pas de référentiels communs Hopitalia ; pas d'échange bancaire automatique. |
| 13/11/2026 | T-039 | — | À faire | Ajout : gestion des comptes utilisateurs propres au module. |
| 13/11/2026 | T-014 | En cours | Fait | Diagrammes vérifiés sur GitHub. |
| 13/11/2026 | T-009, T-011 | À faire, Bloqué | En cours | Projet de nomenclature SYSCOHADA prêt ; note d'intégration Hopitalia écrite à partir du code. |
| 13/11/2026 | T-039 | À faire | Abandonné | Connexion Hopitalia réutilisée. |
| 13/11/2026 | T-201, T-202, T-203 | Abandonné, Bloqué | À faire | Référentiels et achats pharmaceutiques importés d'Hopitalia ; API documentées. |
| 13/11/2026 | T-017 | — | À faire | Ajout : compte technique et clé Hopitalia, points de sécurité. |
| 13/11/2026 | T-017 | À faire | En cours | Note de sécurité Hopitalia et besoins du module (compte technique, clé, variables) rédigés ; transmission à faire. |
| 13/11/2026 | T-011 | En cours | Fait | Instance Hopitalia de test montée en local (Docker) ; routes de la note vérifiées ; chemin OpenAPI et formats de date corrigés dans la note. |
| 14/11/2026 | T-022, T-023, T-026, T-027, T-032, T-060 | À faire, En cours | Fait | Structure `backend/`, `frontend/`, `docs/` ; squelettes backend (FastAPI, `/health`) et frontend (Vite) ; `docker-compose.yml` vérifié ; README ; hooks `pre-commit` vérifiés. |
| 14/11/2026 | T-024, T-025, T-028, T-029, T-030, T-031 | À faire | En cours | Modèle de demande de fusion, protection de `main` appliquée, CI unique `ci.yml` (backend, frontend, dco, ci-ok) ; vérifications locales vertes, à constater sur GitHub. |
| 14/11/2026 | T-024, T-025, T-028, T-029, T-030, T-031 | En cours | Fait | Demande n° 6 fusionnée : CI verte (5 jobs), `ci-ok` exigé par la protection de `main`, modèle présent sur `main`. P0.B terminé. |
| 14/11/2026 | T-040 à T-059 | À faire | Fait | Socle backend : couches, configuration, PostgreSQL et Alembic, montants, erreurs, pagination, idempotence, ETag, limitation de débit, connexion Hopitalia, habilitations, cloisonnement, journal d'audit, ports, journalisation, base de test, langue. 67 tests verts ; connexion vérifiée contre Hopitalia réel. |
| 14/11/2026 | T-061 à T-079 (P0.D) | À faire | Fait | Socle frontend : thème, polices, i18n, client généré, session, gabarit, routage, tableau serveur, formats, badges, mouvement réduit. 20 tests Vitest, 3 parcours Playwright. |
| 14/11/2026 | T-075 | À faire | En cours | Vert en local ; à constater en CI. |
| 14/11/2026 | T-121 | — | À faire | Ajout : gestion des habilitations dans le module (la connexion passe par Hopitalia). |
| 14/11/2026 | T-075 | En cours | Fait | CI verte sur la demande n° 8 (Vitest, Playwright, backend sur PostgreSQL). P0.C et P0.D terminés. |
| 14/11/2026 | T-121 | À faire | Fait | Écran et API « Habilitations » : attribution par code agent Hopitalia, retrait, liste cloisonnée, journal d'audit, pas d'auto-attribution ; migration 0002. |
| 14/11/2026 | T-080 à T-096 (P1.A) | À faire | Fait | Lot 1 : référentiels, nomenclature, exercices, budgets, lignes, import des dotations, notifications, paramètres et service de calcul, révisions avec visas ; migration 0003 ; 106 tests backend, 27 tests Vitest, parcours REC-01. T-095 suit le circuit fixe en attendant T-110 à T-112. |
| 14/11/2026 | T-110 à T-113, T-115, T-119, T-120 | À faire | Fait | Workflow transverse : circuits paramétrés, visas, retour pour correction, délégations, statuts personnalisés, pièces avec empreinte ; migration 0004 ; 121 tests backend, 30 tests Vitest. Révisions passées sur ce workflow. |
| 14/11/2026 | T-114, T-116 | À faire | En cours | Fait et testé sur les révisions ; le payeur (REC-13) et l'engagement validé (API-04) arrivent avec les lots 2 et 5. |
| 14/11/2026 | T-117, T-118 | À faire | À faire | Dépendance à T-140 ajoutée : aucun objet annulable ni dérogeable n'existe avant les engagements. |
| 15/11/2026 | T-130 à T-138 (P1.C) | À faire | Fait | Contrats et marchés : fiche, ventilation, avenants, échéancier, lots, ordres de service, révisions de prix, synthèse 18.1, écrans ; migration 0005 ; 138 tests backend, 33 tests Vitest, parcours REC-02. |
| 15/11/2026 | T-140 à T-147, T-149, T-150 | À faire | Fait | Engagements, moteur de contrôles et cinq contrôles, verrou de crédit (REC-16), écrans et parcours REC-03 ; migration 0006 ; 157 tests backend, 35 tests Vitest. |
| 15/11/2026 | T-117, T-118 | À faire | Fait | Annulations (contre-opérations par imputation) et dérogations validées par le circuit. |
| 15/11/2026 | T-116 | En cours | Fait | API-04 vérifié sur l'engagement validé. |
| 15/11/2026 | T-148 | À faire | En cours | Annulation partielle et totale faites ; clôture à vérifier avec les liquidations (lot 4). |
| 15/11/2026 | T-160 à T-167 (P1.E) | À faire | Fait | Commandes, réceptions, réserves, attestation et service fait ; migration 0007 ; 165 tests backend, 37 tests Vitest, parcours REC-05. |
| 15/11/2026 | T-170 à T-181 (P1.F) | À faire | Fait | Factures, avoirs, décomptes, liquidations par imputation, déductions, contrôles (RG-05, RG-06, REC-07), rapprochement, écrans ; dérogations communes à l'engagement et à la liquidation ; migration 0008 ; 178 tests backend, 40 tests Vitest, parcours REC-06 et REC-12. |
| 15/11/2026 | T-148 | En cours | Fait | Clôture d'un engagement partiellement exécuté vérifiée avec les liquidations. |
