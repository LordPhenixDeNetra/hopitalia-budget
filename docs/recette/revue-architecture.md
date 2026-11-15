# Revue d'architecture — lots 1 à 5

**Projet :** Hopitalia Budget · **Tâche :** T-197 · **Date :** 15/11/2026 · **Référence :** cahier des charges V3, section 15.3

Grille des critères d'architecture, vérifiée sur le code à la fin de la chaîne de dépense (lots 1 à 5). Pour chaque critère : comment il a été vérifié, le résultat, et les écarts corrigés pendant la revue.

## Grille

| Réf. | Critère | Vérification | Résultat |
|---|---|---|---|
| ARC-S | Chaque formule de la section 6 est implémentée une seule fois. | Relecture des calculs hors de `domaine/indicateurs.py` (recherche des soustractions sur engagé, liquidé, net à payer, payé, montant actualisé). | Conforme après correction de trois écarts (ci-dessous). |
| ARC-O | Un nouveau contrôle s'ajoute sans modifier le moteur ni les cas d'utilisation existants. | `test_moteur_extensible_et_derogation_limitee` ajoute un contrôle de test sans toucher au moteur. Lots 2 et 4 : cinq contrôles d'engagement et trois de liquidation, chacun une classe `RegleControle`. | Conforme, avec une remarque (ci-dessous). |
| ARC-L | Les tests de `Contrat` et `Engagement` passent avec `Marche` et `DepenseHorsMarche`. | Tests paramétrés sur `[Contrat, Marche]` et `[Engagement, DepenseHorsMarche]` (règles du domaine), et sur les types `CONVENTION`, `MARCHE` et les origines `DECISION_AUTORISEE`, `HORS_MARCHE` (API). | Conforme. |
| ARC-I | Aucune méthode d'interface n'est implémentée par une exception « non supporté ». | Nouveau test `test_arc_i_aucune_methode_non_supportee` : aucun `raise NotImplementedError` dans le code. Capacités découpées (`Validable`, `Justifiable`) : la facture est justifiable sans être validable, l'ordonnancement et le paiement n'implémentent ni l'une ni l'autre. | Conforme. |
| ARC-D | Le domaine se teste sans base de données, sans réseau et sans module Hopitalia. | `test_couche_sans_cadriciel` : `domaine` et `application` n'importent ni FastAPI, ni SQLAlchemy, ni client HTTP. Les tests du domaine passent sans `TEST_DATABASE_URL` (28 tests ; ceux qui demandent une base sont ignorés). | Conforme. |

## Écarts corrigés pendant la revue (ARC-S)

| Formule (section 6) | Où elle était recalculée | Correction |
|---|---|---|
| Reste à engager d'un contrat (6.2) | Contrôle du plafond `ControlePlafondContrat` (`domaine/engagements.py`). | Fonction `reste_a_engager` dans `domaine/indicateurs.py`, utilisée par la synthèse du contrat et par le contrôle. |
| Engagé restant à liquider (6.1) | Reste dû d'une imputation, lu par les contrôles de la liquidation (`adaptateurs/sortie/factures_sql.py`). | Fonction `engage_restant_a_liquider`, utilisée par les indicateurs de ligne et par l'état de la liquidation. |
| Reste à payer (6.3) | Solde dû d'une liquidation, deux fois dans `routes/paiements.py`. | `reste_a_payer_facture`, déjà utilisée pour la facture, sert aussi au solde d'une liquidation. |

## Remarque sur ARC-O

Le moteur de contrôles (`domaine/controles.py`) a été modifié une fois depuis sa création, au lot 4 : le champ `bloquant` du résultat permet un contrôle d'alerte (facturé au-delà du réceptionné) qui ne bloque pas la validation. C'est une capacité nouvelle du moteur, pas l'ajout d'un contrôle : aucun contrôle n'a demandé de modifier le moteur ni les cas d'utilisation.

## Suite

Les critères généraux d'acceptation (section 15.4) se vérifient avec la DAF lors de la recette utilisateur (T-198) : voir [recette-lots-1-a-5.md](recette-lots-1-a-5.md).
