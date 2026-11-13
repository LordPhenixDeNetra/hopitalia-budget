# Jeu d'essai — marché annuel de fournitures médicales

**Projet :** Hopitalia Budget · **Statut :** validé le 13/11/2026 ; codes du projet de nomenclature (tâche T-009) · **Référence :** cahier des charges V3, annexe 18.2

Ce jeu d'essai détaille, pièce par pièce, l'exemple chiffré de l'annexe 18.2. Il sert de référence aux tests automatisés et à la recette : chaque résultat attendu doit être retrouvé exactement par l'application.

Les codes budgétaires sont ceux du [projet de nomenclature](nomenclature-budgetaire.md) construit sur le plan SYSCOHADA révisé : `604-MED` (médicaments consommés dans les soins) et `604-CMD` (consommables médicaux). Pour simplifier, les montants sont toutes taxes comprises et sans retenue (net à payer = montant liquidé). Montants en francs CFA (XOF).

## 1. Situation de départ

**Exercice :** 2026 · **Établissement :** CHU de test (fictif)

| Ligne budgétaire | Code (fictif) | Dotation |
|---|---|---:|
| Médicaments | 604-MED | 90 000 000 |
| Consommables médicaux | 604-CMD | 40 000 000 |

**Marché** M-2026-001, fournitures médicales, fournisseur « Pharma Test SA » (fictif), signé le 05/01/2026, montant 100 000 000, sans avenant.

| Ventilation du marché | Montant |
|---|---:|
| 604-MED | 70 000 000 |
| 604-CMD | 30 000 000 |

## 2. Pièces

### Engagements

| Engagement | Date | 604-MED | 604-CMD | Total | Statut |
|---|---|---:|---:|---:|---|
| ENG-001 | 15/01/2026 | 50 000 000 | — | 50 000 000 | Validé |
| ENG-002 | 10/02/2026 | 15 000 000 | 15 000 000 | 30 000 000 | Validé |

### Commandes et réceptions

| Pièce | Rattachement | Montant |
|---|---|---:|
| BC-001 | ENG-001 | 40 000 000 |
| BC-002 | ENG-002 | 25 000 000 |
| REC-001 (validée) | BC-001 | 30 000 000 acceptés |
| REC-002 (validée) | BC-002 | 20 000 000 acceptés |
| REC-003 (validée) | BC-001 | 5 000 000 acceptés |

### Factures et liquidations

| Facture | Montant | Rattachement | Liquidation | Imputation | Montant liquidé | Statut liquidation |
|---|---:|---|---|---|---:|---|
| FAC-001 | 30 000 000 | ENG-001, REC-001 | LIQ-001 | ENG-001 / 604-MED | 30 000 000 | Validée |
| FAC-002 | 15 000 000 | ENG-002, REC-002 | LIQ-002 | ENG-002 / 604-MED | 10 000 000 | Validée |
| | | | LIQ-003 | ENG-002 / 604-CMD | 5 000 000 | Validée |
| FAC-003 | 5 000 000 | ENG-001, REC-003 | — | — | — | Facture en contrôle |

FAC-002 porte sur les deux lignes de l'engagement ENG-002 : elle donne deux liquidations, une par imputation (règle RG-17).

### Ordonnancements

| Ordonnancement | Liquidations | Montant | Statut |
|---|---|---:|---|
| ORD-001 | LIQ-001 | 30 000 000 | Pris en charge |
| ORD-002 | LIQ-003 | 5 000 000 | Pris en charge |

LIQ-002 n'est pas encore ordonnancée.

### Paiements

| Paiement | Montant | Ventilation |
|---|---:|---|
| PAI-001 | 20 000 000 | LIQ-001 : 20 000 000 |
| PAI-002 (groupé) | 10 000 000 | LIQ-001 : 5 000 000 ; LIQ-003 : 5 000 000 |

## 3. Résultats attendus

### Fiche de synthèse du marché (annexe 18.2)

| Indicateur | Calcul | Attendu |
|---|---|---:|
| Montant contractuel actualisé | 100 000 000 + 0 | 100 000 000 |
| Engagements validés | 50 000 000 + 30 000 000 | 80 000 000 |
| Commandes émises | 40 000 000 + 25 000 000 | 65 000 000 |
| Livraisons réceptionnées | 30 000 000 + 20 000 000 + 5 000 000 | 55 000 000 |
| Factures reçues | 30 000 000 + 15 000 000 + 5 000 000 | 50 000 000 |
| Factures liquidées | 30 000 000 + 10 000 000 + 5 000 000 | 45 000 000 |
| Transmis en paiement | 30 000 000 + 5 000 000 | 35 000 000 |
| Paiements effectués | 20 000 000 + 10 000 000 | 30 000 000 |
| Reste à payer sur liquidé | 45 000 000 − 30 000 000 | 15 000 000 |
| Engagé non encore facturé | 80 000 000 − 50 000 000 | 30 000 000 |
| Solde contractuel non engagé | 100 000 000 − 80 000 000 | 20 000 000 |
| Reste contractuel à payer | 100 000 000 − 30 000 000 | 70 000 000 |
| Taux de consommation | 80 000 000 / 100 000 000 | 80 % |

### Lignes budgétaires

| Indicateur | 604-MED | 604-CMD | Total |
|---|---:|---:|---:|
| Budget révisé | 90 000 000 | 40 000 000 | 130 000 000 |
| Engagé | 65 000 000 | 15 000 000 | 80 000 000 |
| Disponible après engagements | 25 000 000 | 25 000 000 | 50 000 000 |
| Liquidé | 40 000 000 | 5 000 000 | 45 000 000 |
| Engagé restant à liquider | 25 000 000 | 10 000 000 | 35 000 000 |
| Payé | 25 000 000 | 5 000 000 | 30 000 000 |
| Reste à payer | 15 000 000 | 0 | 15 000 000 |
| Taux d'engagement | 72,2 % | 37,5 % | 61,5 % |

### Reste à payer par liquidation

| Liquidation | Liquidé | Payé | Reste |
|---|---:|---:|---:|
| LIQ-001 | 30 000 000 | 25 000 000 | 5 000 000 |
| LIQ-002 | 10 000 000 | 0 | 10 000 000 |
| LIQ-003 | 5 000 000 | 5 000 000 | 0 |

### Statuts attendus

| Pièce | Statut | Raison |
|---|---|---|
| ENG-001 | Partiellement exécuté | Liquidé 30 000 000 sur 50 000 000. |
| ENG-002 | Partiellement exécuté | Liquidé 15 000 000 sur 30 000 000. |
| FAC-001 | Partiellement payée | Payé 25 000 000 sur 30 000 000. |
| FAC-002 | Partiellement payée | LIQ-003 payée, LIQ-002 pas encore. |
| FAC-003 | En contrôle | Pas encore liquidée. |

### Alertes attendues

| Alerte | Raison |
|---|---|
| Seuil de consommation du marché à 80 % | Engagé = 80 % du montant actualisé. |
| Écart engagé / réceptionné | Engagé (80 000 000) supérieur au réceptionné (55 000 000) : signalement, pas un blocage. |

## 4. Contrôles à tester sur ce jeu

| Action | Résultat attendu | Règle |
|---|---|---|
| Créer ENG-003 de 25 000 000 sur le marché | Refusé : dépasse le reste à engager (20 000 000), sauf avenant ou dérogation. | RG-04 |
| Créer un engagement de 30 000 000 sur 604-CMD, sur décision autorisée (sans marché) | Refusé : dépasse le disponible (25 000 000), sauf dérogation. | RG-02 |
| Enregistrer à nouveau FAC-001 (même fournisseur, numéro, date, montant) | Refusé : doublon. | RG-16 |
| Payer 6 000 000 sur LIQ-001 | Refusé : dépasse le reste dû (5 000 000). | RG-07 |
| Liquider FAC-003 pour 6 000 000 | Refusé : dépasse la facture et la réception acceptée (5 000 000). | EF-LIQ-05 |
| Modifier le montant de ENG-001 après validation | Refusé : opération validée ; passer par une annulation tracée. | RG-18 |
| Payer le reste de LIQ-001 (5 000 000) | Accepté ; LIQ-001 soldée, FAC-001 passe à « Payée ». FAC-002 reste « Partiellement payée » tant que LIQ-002 n'est pas payée. | RG-08 |
