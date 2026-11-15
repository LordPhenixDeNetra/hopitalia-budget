# Recette utilisateur — lots 1 à 5 (chaîne de dépense)

**Projet :** Hopitalia Budget · **Tâche :** T-198 · **Référence :** cahier des charges V3, sections 15.1 et 15.4 · **Statut :** à dérouler avec la DAF

Ce document sert de support à la recette des lots 1 à 5 avec la direction administrative et financière (DAF). Chaque scénario est déjà couvert par un test automatisé ; la recette vérifie, avec les agents de l'établissement, qu'il répond au besoin. Les colonnes « Constat » et « Résultat » sont remplies pendant la séance.

## Préparation

- Instance de recette : application déployée avec `docker compose up -d --build`, base vide, migrations à jour.
- Données : celles du [jeu d'essai](../cadrage/jeu-essai-marche-fournitures.md) (marché M-2026-001 de 100 000 000 XOF, lignes 604-MED et 604-CMD).
- Comptes : un agent par profil de la [matrice des habilitations](../cadrage/matrice-habilitations.md) (RB, GMC, AF, REC, VAL, ORD, CPT, AUD), habilités sur l'établissement de recette, et un agent d'un autre établissement pour REC-17.
- Résultat attendu de référence : la section 3 du jeu d'essai (montants et statuts).

## Scénarios

Résultat : « Conforme », « Conforme avec réserve » ou « Non conforme ».

| Réf. | Scénario | Profils | Test automatisé | Constat | Résultat |
|---|---|---|---|---|---|
| REC-01 | Créer un exercice et importer les crédits par compte. | ADM, RB | Playwright REC-01 | | |
| REC-02 | Enregistrer un marché attribué avec montant, fournisseur, échéances, ventilation et pièces. | GMC, VAL, ORD | Playwright REC-02 | | |
| REC-03 | Créer un engagement lié au marché ; contrôle des crédits et du plafond. | GMC, AF, VAL, ORD | `test_rec03_plafond_du_marche`, Playwright REC-03 | | |
| REC-04 | Avenant : le plafond change seulement après validation, l'historique est conservé. | GMC, VAL, ORD | `test_rec04_avenant_effectif_apres_validation` | | |
| REC-05 | Livraison partielle avec son procès-verbal. | REC, VAL | Playwright REC-05 | | |
| REC-06 | Facture partielle contrôlée et liquidée sans clôturer le marché. | AF, VAL, ORD | Playwright REC-06 | | |
| REC-07 | Facture supérieure à la réception acceptée : alerte. | AF | `test_rec07_reste_du_et_facture_superieure_a_la_reception` | | |
| REC-08 | Ordonnancer, puis paiement partiel : la facture reste ouverte. | ORD, CPT | `test_rec08_rec09_paiements_partiels_et_solde`, Playwright REC-08 | | |
| REC-09 | Second paiement ; solde restant dû. | CPT | idem | | |
| REC-10 | Paiement groupé ventilé facture par facture. | CPT | `test_rec10_paiement_groupe_ventile`, Playwright REC-10 | | |
| REC-11 | Doublon de facture détecté et bloqué. | AF | `test_rec11_doublon_de_facture` | | |
| REC-12 | Rejet de facture, correction, annulation contrôlée ; piste d'audit. | AF, AUD | `test_rec12_rejet_correction_et_piste_d_audit`, Playwright REC-12 | | |
| REC-13 | Un non-habilité ne valide ni ne paie ; un même agent ne crée, ne valide et ne paie pas la même opération. | Tous | `test_rg13_separation_des_taches_selon_le_circuit`, `test_rg13_qui_valide_la_liquidation_ne_la_paie_pas` | | |
| REC-14 | Engagé, réceptionné, facturé, liquidé, transmis et payé distincts ; chiffres de l'annexe 18.2 retrouvés. | Tous | `test_rec14_jeu_d_essai_de_l_annexe_18_2` | | |
| REC-15 | Aucune fonction de lancement ou d'attribution de marché. | Tous | `test_rec15_aucune_fonction_de_passation_dans_l_api`, test d'interface REC-15 | | |
| REC-16 | Deux engagements simultanés sur le même crédit : un seul passe. | GMC | `test_rec16_deux_engagements_simultanes_un_seul_passe` | | |
| REC-17 | Un agent d'un établissement ne voit rien d'un autre établissement. | LEC (autre établissement) | `test_lecteur_ne_voit_que_son_etablissement`, `test_liste_filtres_et_cloisonnement` | | |
| REC-18 | Interface en anglais puis en français. | Tous | Playwright « changement de langue » | | |

Hors de ces lots, à recetter plus tard : le tableau de bord de la direction (T-210), les alertes de seuil 80/90/100 % (T-222) et les états imprimables et exportables, dont l'état PDF de REC-18 (T-230 et suivantes).

## Critères généraux d'acceptation (section 15.4)

| Critère | Constat | Résultat |
|---|---|---|
| Données budgétaires exactes et rapprochées des référentiels validés. | | |
| Marchés enregistrés sans reproduire leur passation. | | |
| Engagements, liquidations et paiements liés, historique consultable. | | |
| Calculs vérifiables. | | |
| Dépassements non autorisés et doublons courants bloqués. | | |
| Habilitations et séparation des tâches conformes à la matrice. | | |
| Scénarios exécutés et validés par les représentants de l'établissement. | | |

Les états filtrables, imprimables et exportables relèvent des lots suivants (P2).

## Procès-verbal de recette partiel

| | |
|---|---|
| Établissement | |
| Date de la séance | |
| Version recettée (commit ou image) | |
| Participants (nom, fonction) | |
| Réserves | |
| Décision | Recette prononcée / prononcée avec réserves / ajournée |

| Signataire | Fonction | Date | Signature |
|---|---|---|---|
| | Directeur administratif et financier | | |
| | Représentant de l'équipe projet | | |
