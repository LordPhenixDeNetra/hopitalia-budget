# Recette blanche

**Projet :** Hopitalia Budget · **Date :** 16/11/2026 · **Références :** T-198, T-201, T-202, T-225, T-254

La recette blanche répète la recette avant la séance réelle avec la DAF. Elle s'exécute sur un poste, avec la pile Docker complète : base PostgreSQL, API, interface servie par nginx et tâches planifiées. Deux éléments extérieurs sont remplacés par des doublures :
- **Hopitalia simulé** : connexion des agents, annuaire, fournisseurs, services, commandes et approvisionnements de la pharmacie, avec un volume réaliste ;
- **serveur de courrier de test** : une boîte de réception consultable dans le navigateur.

Une répétition trouve les anomalies avant la séance. Elle ne remplace ni le constat ni la signature de la DAF (T-198, T-286), ni la vérification sur un vrai Hopitalia (T-201, T-202).

## Lancer

Depuis la racine du dépôt, la pile de développement arrêtée (`docker compose stop`) pour libérer les ports :

```bash
# Projet séparé (-p) : ses volumes ne touchent pas à ceux du développement. down -v : base neuve.
docker compose -p hopitalia-budget-simulation -f docker-compose.yml -f docker-compose.simulation.yml down -v
docker compose -p hopitalia-budget-simulation -f docker-compose.yml -f docker-compose.simulation.yml up -d --build

# Paramétrage et scénarios par l'API ; écrit le procès-verbal de répétition.
cd backend && .venv/Scripts/python ../simulation/recette_blanche.py

# Écrans, profil par profil, connexion par l'Hopitalia simulé ; captures dans le rapport HTML.
cd ../frontend && npx playwright test -c playwright.recette.config.ts
```

## Ce qui est répété

`simulation/recette_blanche.py` paramètre l'établissement par l'API, comme l'administrateur, puis déroule les étapes suivantes. Une anomalie n'arrête pas la répétition : elle est notée et l'étape suivante est lancée.

| Réf. | Étape |
|---|---|
| PREP-01, PREP-02 | Premier administrateur (commande `habiliter`), établissements, profils de treize agents lus dans l'annuaire. |
| REC-01 | Nomenclature, référentiels, exercice, budget et crédits. |
| COUR-01 | Adresses de courriel de deux agents (français, anglais) ; règle « crédit insuffisant » envoyée par courriel. |
| REC-14 | Jeu d'essai de l'annexe 18.2, pièce par pièce, validé profil par profil (REC-02, 03, 05, 06, 08, 09, 10, 11) ; montants, restes et statuts comparés à l'annexe ; contrôles de plafond, de crédit, de doublon et de trop-payé. |
| REC-17 | Cloisonnement : le lecteur d'un autre établissement ne voit rien. |
| REC-18 | État PDF en anglais pour un agent anglophone. |
| INT-01 | Fournisseurs et services importés deux fois sans doublon ; fournisseur du module rattaché ; fournisseur retiré d'Hopitalia désactivé. |
| INT-03 | Commandes de la pharmacie importées, rattachées, réceptions validées créées ; approvisionnement reçu puis supprimé dans Hopitalia : réception annulée. |
| RCT-01 | Volet recettes : activation, recette, facturé, encaissé, tableau de bord. |
| COUR-02 | Courriel d'alerte reçu par chaque destinataire, dans sa langue. |

Le résultat est écrit dans [repetition-recette.md](repetition-recette.md). La suite Playwright `frontend/e2e-recette/` ouvre ensuite les écrans de chaque profil, par l'interface réelle.

## Accès pendant la répétition

| Quoi | Où |
|---|---|
| Interface | http://127.0.0.1:8080 : comptes `agentNNN` / `recette` (par exemple `agent002` pour le responsable budgétaire, `agent012` pour l'agent financier). |
| Boîte de réception de test | http://127.0.0.1:8025 |
| Hopitalia simulé | http://127.0.0.1:8090 ; `POST /simulation/jour` fait passer un jour (retrait, modification, suppression, nouvelles commandes). |

Les comptes, le mot de passe `recette` et la clé de signature de `docker-compose.simulation.yml` sont ceux des tests : ils ne valent que face à l'Hopitalia simulé. Cette pile ne doit jamais servir en production.

## Préparer la séance réelle

1. Lancer la répétition sur la version à recetter, et corriger chaque étape non conforme.
2. Apporter à la séance [repetition-recette.md](repetition-recette.md) et les captures de la suite Playwright.
3. Pour présenter la proposition et faire valider chaque point, compléter la répétition par l'environnement de démonstration : [parcours de validation](../presentation/parcours-de-validation.md).
4. Pendant la séance, dérouler [recette-lots-1-a-5.md](recette-lots-1-a-5.md) sur l'environnement de recette de l'hôpital (T-254), avec les agents.
