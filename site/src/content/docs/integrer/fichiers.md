---
title: Fichiers d'import et d'export
description: Le format des fichiers de nomenclature et de dotations, l'export du budget, et le fichier d'écritures pour le logiciel comptable.
sidebar:
  order: 6
---

Les fichiers CSV sont séparés par des **points-virgules**, encodés en **UTF-8**, avec une ligne d'en-tête.

## Nomenclature

Écran **Nomenclature**, « Importer un fichier CSV » (administrateur).

| Colonne | Contenu |
|---|---|
| `niveau` | `SECTION`, `CHAPITRE`, `ARTICLE` ou `PARAGRAPHE`. |
| `code` | Code de l'élément, unique. |
| `libelle` | Libellé. |
| `code_parent` | Code de l'élément parent ; vide pour une section. |
| `compte_syscohada` | Compte du plan SYSCOHADA révisé (paragraphes). |

Le dépôt fournit un projet de nomenclature : `docs/cadrage/nomenclature-budgetaire.csv`. Un import se relance : les éléments existants sont mis à jour, jamais dupliqués.

## Dotations d'un budget

Fiche budget, onglet **Import des dotations** (responsable budgétaire), ou `POST /budgets/{id}/imports`.

| Colonne | Contenu |
|---|---|
| `code` | Code de la ligne budgétaire. |
| `libelle` | Libellé de la ligne. |
| `compte` | Code du compte budgétaire (paragraphe de la nomenclature). |
| `centre` | Code du centre de responsabilité. |
| `source` | Code de la source de financement. |
| `programme` | Code du programme ; facultatif. |
| `dotation` | Montant : `8500000` ou `8 500 000,50`. |

```csv
code;libelle;compte;centre;source;programme;dotation
604-MED;Médicaments;604-MED;PHARMA;BE;;90000000
604-CMD;Consommables médicaux;604-CMD;PHARMA;BE;;40000000
```

Les lignes valides sont créées ; les autres sont listées avec leur numéro de ligne, leur anomalie et la valeur en cause.

**Export** : `GET /budgets/{id}/export?format=csv|json` produit les lignes et dotations au même format, prêtes à être modifiées puis réimportées.

## Écritures pour la comptabilité

État **Écritures pour la comptabilité**, en CSV ou en tableur (`GET /etats/ecritures?exerciceId=…&format=csv|xlsx`).

| Colonne | Contenu |
|---|---|
| `date` | Date de la liquidation ou du paiement. |
| `journal` | `ACH` pour une liquidation, `BQ` pour un paiement. |
| `piece` | Numéro de la liquidation ou du paiement. |
| `compte` | Compte SYSCOHADA. |
| `tiers` | Code du fournisseur, ou du compte de trésorerie. |
| `libelle` | Facture et objet, ou numéro du paiement. |
| `debit`, `credit` | Montants. |

Chaque pièce donne des écritures **équilibrées** :

| Pièce | Débit | Crédit |
|---|---|---|
| Liquidation validée | Compte de charge de la ligne (nomenclature), montant liquidé. | `401` fournisseur, net à payer ; `471` compte d'attente, déductions. |
| Paiement exécuté | `401` fournisseur, montant payé. | Trésorerie : `521` banque, `531` trésor ou `571` caisse, selon le type du compte. |

Les déductions (avance récupérée, retenue de garantie, pénalités) vont au compte d'attente `471`, que le service comptable ventile. Ces comptes sont une proposition à valider par le service comptable.
