---
title: Cas d'usage
description: Les ressources de l'API à utiliser pour chaque besoin courant, et un exemple complet de création d'engagement sans doublon.
sidebar:
  order: 5
---

| Besoin | Ressources |
|---|---|
| Lire les crédits | `GET /budgets`, `GET /budgets/{id}/situation`, `GET /lignes-budgetaires/{id}/disponibilite`. |
| Échanger un budget | `GET /budgets/{id}/export?format=csv\|json` (format de l'import), puis `POST /budgets/{id}/imports` (CSV ; `202`, suivi sur `/imports-dotations/{id}`). |
| Créer des engagements | `POST /engagements` (brouillon), puis `POST /engagements/{id}/soumissions` : les contrôles et le circuit de validation s'appliquent. |
| Suivre la chaîne de dépense | `GET /engagements`, `/bons-commande`, `/factures`, `/liquidations`, `/paiements`, filtrés par établissement et exercice. |
| Exporter vers la comptabilité | `GET /etats/ecritures?exerciceId=…&format=csv\|xlsx` : écritures équilibrées (voir [Fichiers](/docs/integrer/fichiers/#écritures-pour-la-comptabilité)). |
| Exporter un état | `GET /etats/{code}?format=json\|csv\|xlsx\|pdf`, mêmes filtres que le tableau de bord. |
| Lire les alertes | `GET /alertes` (curseur), `GET /alertes/compteur`. |

Aucun import ne crée une pièce déjà validée : une pièce créée par l'API passe ses contrôles et son circuit, comme une pièce saisie.

## Exemple : créer un engagement sans doublon

```bash
API=https://budget.hopital.local
JETON=$(curl -s -X POST "$API/api/v1/auth/connexion" -H 'Content-Type: application/json' \
  -d '{"identifiant":"svc-integration","motDePasse":"…"}' | jq -r .jetonAcces)

CLE=$(uuidgen)   # une clé par engagement, conservée pour les nouveaux essais
curl -s -X POST "$API/api/v1/engagements" \
  -H "Authorization: Bearer $JETON" -H "Idempotency-Key: $CLE" \
  -H 'Content-Type: application/json' -d @engagement.json
```

`engagement.json` :

```json
{
  "etablissementId": "…",
  "origine": "DECISION_AUTORISEE",
  "referenceDecision": "DEC-2026-014",
  "dateEngagement": "2026-11-10",
  "objet": "Maintenance des équipements de stérilisation",
  "montant": "3500000.00",
  "centreId": "…",
  "fournisseurId": "…",
  "imputations": [{"ligneId": "…", "montant": "3500000.00"}]
}
```

En cas de coupure réseau, renvoyer la même requête avec la même clé : l'engagement n'est créé qu'une fois. Puis le soumettre :

```bash
curl -s -X POST "$API/api/v1/engagements/<id>/soumissions" -H "Authorization: Bearer $JETON"
```
