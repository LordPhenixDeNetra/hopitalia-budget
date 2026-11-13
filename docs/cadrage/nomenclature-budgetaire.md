# Nomenclature budgétaire — projet à relire par la DAF

**Projet :** Hopitalia Budget · **Tâche :** T-009 · **Statut :** projet, à relire par la DAF · **Fichier d'import :** [nomenclature-budgetaire.csv](nomenclature-budgetaire.csv)

Cette nomenclature est construite sur le **plan comptable SYSCOHADA révisé** (section 17, point 3 du cahier des charges). Elle sert à la première mise en service. Chaque établissement peut ensuite l'adapter par paramétrage.

> **À vérifier :** les numéros et libellés des comptes SYSCOHADA ont été repris de mémoire, au niveau à 2 et 3 chiffres. Ils doivent être contrôlés par la DAF avec le texte officiel du plan comptable (Acte uniforme OHADA relatif au droit comptable, version révisée) avant l'import.

## Structure

| Niveau | Code | Exemple | Rôle |
|---|---|---|---|
| Section | `F` ou `I` | `F` Fonctionnement | Sépare fonctionnement et investissement. |
| Chapitre | Compte SYSCOHADA à 2 chiffres | `60` Achats et variations de stocks | Regroupement pour les états. |
| Article | Compte SYSCOHADA à 3 chiffres | `604` Achats stockés de matières et fournitures consommables | Compte comptable de correspondance. |
| Paragraphe | Article + suffixe | `604-MED` Médicaments consommés dans les soins | **Compte budgétaire** sur lequel on ouvre des lignes et on engage. |

Chaque paragraphe correspond à un compte comptable (colonne `compte_syscohada`) : c'est la correspondance compte budgétaire → compte comptable demandée par EF-REF-03.

## Contenu

85 éléments : 2 sections, 10 chapitres, 28 articles, 45 paragraphes.

| Section | Chapitres |
|---|---|
| Fonctionnement | 60 Achats ; 61 Transports ; 62 Services extérieurs ; 63 Autres services extérieurs ; 64 Impôts et taxes ; 65 Autres charges ; 66 Charges de personnel |
| Investissement | 21 Immobilisations incorporelles ; 23 Bâtiments et installations ; 24 Matériel, mobilier et actifs biologiques |

Le volet recettes, activé plus tard, recevra ses propres comptes (classe 7).

## Choix faits avec le responsable du projet

| Sujet | Choix |
|---|---|
| Médicaments | **Deux paragraphes** : `601-PHA` pour les médicaments revendus aux patients par la pharmacie, `604-MED` pour les médicaments consommés dans les soins. |
| Équipements biomédicaux | `241-BIO`, dans le compte 241 Matériel et outillage, distinct du mobilier et du matériel informatique (244). |

## Choix proposés, à confirmer par la DAF

| Sujet | Proposition | Alternative |
|---|---|---|
| Carburants | `605-CAR` (autres achats) | Compte de matières combustibles (604) si les carburants sont stockés. |
| Nettoyage, gardiennage, restauration, déchets | `621` Sous-traitance générale | Comptes plus détaillés si l'établissement les suit séparément. |
| Missions | `638-MIS` Autres charges externes | — |
| Évacuations de patients | `618-EVA` Autres frais de transport | — |

## Format du fichier

Fichier CSV, séparateur point-virgule, encodage UTF-8 (ouvrable dans un tableur). Colonnes :

| Colonne | Contenu |
|---|---|
| `niveau` | `SECTION`, `CHAPITRE`, `ARTICLE` ou `PARAGRAPHE` |
| `code` | Code unique |
| `libelle` | Libellé affiché |
| `code_parent` | Code du niveau supérieur (vide pour une section) |
| `compte_syscohada` | Compte comptable de correspondance (vide pour une section) |

Ajouter une ligne budgétaire revient à ajouter un paragraphe, avec un suffixe libre de trois lettres sous l'article voulu.
