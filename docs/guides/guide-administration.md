# Guide d'administration

**Projet :** Hopitalia Budget · **Tâche :** T-284 · **Référence :** cahier des charges V3, section 16 · **Statut :** à éprouver par un administrateur qui paramètre seul un établissement

Ce guide s'adresse à l'administrateur fonctionnel du module (profil ADM). Il suit l'ordre dans lequel un établissement se met en service. L'installation technique (serveur, sauvegardes) relève du [plan d'exploitation](../exploitation/plan-exploitation.md).

## 1. Premier administrateur

La connexion passe par Hopitalia, mais les droits sont propres au module. Le tout premier profil d'administrateur s'attribue sur le serveur, avec l'identifiant Hopitalia (`userId`) et le code de l'agent :

```bash
docker compose exec api python -m hopitalia_budget.outils.habiliter \
  --utilisateur-id 42 --code-agent AG042 --profil ADM
```

Les profils suivants s'attribuent dans l'interface. Un administrateur ne peut pas modifier ses propres profils.

## 2. Établissements et habilitations

1. **Établissements** :
   - créer l'établissement (code, nom), puis ses sites ;
   - sur sa fiche, vérifier les **paramètres de calcul** des indicateurs : déduction des engagements en cours du disponible prévisionnel, base du taux d'exécution, base du taux de consommation des marchés, traitement des avances récupérées.
2. **Habilitations** :
   - attribuer à chaque agent ses profils (code agent Hopitalia) et l'établissement où ils s'appliquent ; sans établissement, le profil vaut pour tous ;
   - s'appuyer sur la [matrice des habilitations](../conception/workflows-et-habilitations.md) ;
   - un agent qui cumule des profils reste soumis à la séparation des tâches (RG-13) ;
   - chaque attribution et chaque retrait sont tracés dans le journal d'audit.

## 3. Nomenclature et référentiels

1. **Nomenclature** : importer la nomenclature budgétaire, fichier [`docs/cadrage/nomenclature-budgetaire.csv`](../cadrage/nomenclature-budgetaire.csv) (colonnes `niveau;code;libelle;code_parent;compte_syscohada`). Les comptes sont ceux du plan SYSCOHADA révisé.
2. **Paramétrage**, un référentiel à la fois :

| Référentiel | À savoir |
|---|---|
| Centres de responsabilité | Services de l'établissement. Avec l'intégration Hopitalia, ils sont importés ; un centre déjà saisi avec le même code est rattaché, pas dupliqué. |
| Sources de financement, programmes et projets | Utilisés par les lignes budgétaires et les filtres. |
| Familles d'achats, types de dépenses | Le type de dépense porte le seuil au-delà duquel un achat hors marché est refusé. |
| Modes de règlement, comptes de trésorerie | Le type de compte (banque, caisse, trésor) sert aussi à l'export comptable. |
| Types de pièces | Pour chaque type, les objets qui exigent la pièce avant validation, et la durée de conservation. |
| Fournisseurs | Importés d'Hopitalia avec l'intégration ; compléter ici les identifiants administratifs et les coordonnées bancaires (numéro chiffré, jamais affiché en clair). |
| Exercices budgétaires | L'exercice crée ses périodes (année, trimestres, mois). |

Les référentiels sont communs à tous les établissements, sauf les centres de responsabilité. Un élément ne se supprime pas : il se désactive et reste visible dans l'historique.

## 4. Circuits de validation

**Paramétrage**, « Circuits de validation ». Sans circuit paramétré, chaque objet suit son circuit par défaut :

| Objet | Circuit par défaut |
|---|---|
| Engagement | Contrôle financier (AF), visa DAF (VAL), ordonnateur (ORD). |
| Réception (service fait) | Valideur du service (VAL). |
| Révision, contrat, avenant, dérogation, liquidation | Visa DAF (VAL), ordonnateur (ORD). |

Un circuit paramétré vaut pour un établissement, éventuellement pour un service, et pour une tranche de montant (seuil minimal et maximal). Le circuit du service l'emporte sur celui de l'établissement ; à montant égal, le seuil le plus élevé l'emporte. Les règles imposées :

- chaque étape est un profil qui a le droit de valider l'objet dans la matrice ;
- la dernière étape est obligatoire ;
- pour les révisions, contrats, avenants, engagements, dérogations et liquidations, la dernière étape revient à l'ordonnateur ;
- « séparation des tâches » empêche l'auteur de viser sa propre pièce. La laisser active.

Le circuit est figé à la soumission : le modifier ne change pas les pièces déjà en validation.

## 5. Alertes

**Alertes**, onglet « Règles » :

- activer ou désactiver chaque type d'alerte par établissement ;
- régler les seuils, par exemple 80, 90 et 100 % de consommation d'un marché, et les délais : factures échues, engagements anciens, échéances de contrat ;
- les alertes planifiées sont détectées une fois par jour. « Lancer la détection maintenant » les recalcule sans attendre ;
- l'envoi par courriel attend les adresses des agents et le serveur de messagerie de l'hôpital (T-225).

## 6. Budget et délégations

- Le responsable budgétaire crée ensuite le budget et importe les dotations (guide utilisateur, profil RB).
- **Délégations** : chaque agent crée les siennes pour ses absences (guide utilisateur).

## 7. Intégration Hopitalia

**Intégrations** (ADM pour lancer et reprendre ; RB et AUD en lecture) :

- le journal liste chaque échange (fournisseurs, services, pharmacie) avec son résultat ;
- la tâche quotidienne lance les échanges et reprend d'elle-même un échec jusqu'à cinq tentatives ;
- au-delà, corriger la cause (indiquée par le code d'erreur), puis cliquer sur « Reprendre » ;
- « Importer… » lance un échange sans attendre la tâche quotidienne. Le relancer ne crée pas de doublon.

Pré-requis côté serveur : compte technique Hopitalia et établissement cible (`HOPITALIA_ETABLISSEMENT`), voir le [plan d'exploitation](../exploitation/plan-exploitation.md).

## 8. Contrôle et audit

- Le **journal d'audit** (VAL, ORD, AUD) retrace toute modification de donnée financière, les connexions et les exports.
- Contrôle périodique conseillé : profils encore justifiés, délégations en cours, échanges en échec, alertes non lues anciennes.

## Vérification de fin de paramétrage

Un établissement est prêt quand chaque point est « Oui » :

| Point | Oui / Non |
|---|---|
| L'exercice est ouvert. | |
| Les centres, sources et types de dépenses sont en place. | |
| Le budget est importé sans anomalie. | |
| Chaque profil de la matrice a au moins un agent. | |
| Un engagement d'essai passe son circuit jusqu'à l'ordonnateur. | |
| Le tableau de bord affiche les crédits attendus. | |
