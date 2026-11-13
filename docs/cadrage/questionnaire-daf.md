# Questionnaire pour la Direction administrative et financière

**Projet :** Hopitalia Budget, module de suivi budgétaire · **Date :** 13/11/2026

Ce questionnaire accompagne le [cahier des charges V3](../../Backend/Cahier_des_charges_Module_Budgetaire_Hopitalia_V3.md). Il sert à valider le document et à recueillir les informations propres à l'établissement. **Réponses reçues le 13/11/2026** pour les questions marquées ; les autres restent à compléter. Merci de compléter les zones « Réponse » et de joindre les documents demandés.

## 1. Validation du cahier des charges

**Q-D01 — Relecture.** Merci de relire en priorité :

- le périmètre (section 2) : le module suit les marchés déjà attribués et ne gère pas leur passation ;
- les règles de gestion RG-01 à RG-20 (section 5) ;
- les formules de calcul (section 6) : budget révisé, engagé, liquidé, payé, restes, disponibles.

Ces éléments vous paraissent-ils conformes à vos pratiques ? Indiquez toute règle manquante ou à corriger.

> Réponse (13/11/2026) : cahier des charges validé.

## 2. Nomenclature et comptes

**Q-D02 — Nomenclature budgétaire.** Merci de fournir, de préférence dans un tableur, la nomenclature utilisée : sections, chapitres, articles, paragraphes et comptes budgétaires, avec leurs codes et libellés.

> Réponse (13/11/2026) : partir du plan comptable SYSCOHADA révisé ; la nomenclature est construite sur ce plan.

**Q-D03 — Comptabilité.** Quel plan comptable utilisez-vous ? Existe-t-il une table de correspondance entre comptes budgétaires et comptes comptables ?

> Réponse (13/11/2026) : plan SYSCOHADA révisé.

## 3. Décisions provisoires à confirmer

En attendant votre réponse, ces choix sont appliqués à titre provisoire (section 17 du cahier des charges). Pour chacun, indiquez « Confirmé » ou la correction souhaitée.

| # | Sujet | Décision provisoire | Votre réponse |
|---|---|---|---|
| 4 | Fournisseurs | Un référentiel partagé entre établissements ; coordonnées bancaires propres à chaque établissement. | Confirmé |
| 5 | Taux de consommation d'un marché | Calculé sur l'engagé (engagé / montant actualisé du marché). | Confirmé |
| 6 | Avance | L'avance consomme le crédit quand elle est liquidée ; sa récupération sur les décomptes réduit d'autant leur consommation. | Confirmé |
| 7 | Versions et limites techniques | Limites d'usage de l'application et durée de maintien des versions : valeurs techniques, modifiables. | Non soumis (valeurs techniques) |
| 8 | Conservation des pièces | 10 ans par défaut, modifiable par type de pièce. | Confirmé |

**Q-D04 — Seuils hors marché.** Pour chaque type de dépense hors marché (missions, petits achats, eau, électricité, télécoms, fonctionnement, prestations ponctuelles…), quel est le montant au-delà duquel un marché est obligatoire ? Tant qu'aucun seuil n'est fixé, ces dépenses passeront par une dérogation.

> Réponse (13/11/2026) : pas encore de montants : la règle par défaut (dérogation obligatoire sans seuil) s'applique ; seuils saisis plus tard.

## 4. Circuits de validation et habilitations

**Q-D05 — Circuits actuels.** Qui vise et valide aujourd'hui un engagement, une liquidation et un paiement ? Y a-t-il des seuils de montant qui changent le valideur (par exemple : DAF jusqu'à un montant, ordonnateur au-delà) ? Existe-t-il des délégations de signature ?

> Réponse (13/11/2026) : l'ordonnateur valide toujours, après la DAF, quel que soit le montant.

**Q-D06 — Matrice des habilitations.** Merci de valider ou de corriger le projet de [matrice des habilitations](matrice-habilitations.md), en particulier les seuils et les incompatibilités de rôles.

> Réponse (13/11/2026) : matrice validée telle quelle.

## 5. Données d'essai

**Q-D07 — Jeu d'essai.** Merci de vérifier le [jeu d'essai du marché de fournitures médicales](jeu-essai-marche-fournitures.md) : les pièces et les résultats attendus correspondent-ils à ce que vous attendez de l'outil ?

> Réponse (13/11/2026) : jeu d'essai validé, codes fictifs à remplacer.

**Q-D08 — Données réelles.** Pouvez-vous fournir, anonymisés si nécessaire, le budget d'un exercice passé et quelques marchés réels avec leurs factures et paiements ? Ils serviront aux tests de recette.

> Réponse :

## 6. Échanges et états

**Q-D09 — Logiciel comptable.** Quel logiciel comptable utilisez-vous, et sous quel format peut-il recevoir des données (fichier, API) ?

> Réponse (13/11/2026) : export de fichiers (tableur, CSV) vers la comptabilité.

**Q-D10 — Banque.** Avec quelles banques travaillez-vous, et sous quel format recevez-vous les confirmations de virement (relevés, fichiers, portail) ?

> Réponse (13/11/2026) : confirmations de virement saisies à la main dans le module.

**Q-D11 — États réglementaires.** La tutelle impose-t-elle des modèles officiels pour certains états (budget, exécution, restes à payer) ? Merci de joindre ces modèles.

> Réponse (13/11/2026) : pas de modèle officiel : présentation libre.

## 7. Fonctionnement

**Q-D12 — Volet recettes.** Le suivi des recettes doit-il être actif dès la mise en service ?

> Réponse (13/11/2026) : non, volet recettes activé plus tard.

**Q-D13 — Langues.** L'interface sera en français, avec l'anglais en option. D'autres langues sont-elles nécessaires ?

> Réponse (13/11/2026) : français et anglais.

**Q-D14 — Interlocuteurs.** Qui contacter pour les questions budgétaires, comptables et de recette (nom, fonction, courriel) ?

> Réponse :
