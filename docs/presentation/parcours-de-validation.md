# Parcours de présentation et de validation

**Projet :** Hopitalia Budget · **Date :** 16/11/2026 · **Phase :** proposition · **À utiliser avec :** [fiche-de-decision.md](fiche-de-decision.md)

L'application est en phase de proposition. Chaque point qui attend une décision est visible et démontrable dans l'environnement de démonstration : rien n'est masqué ni désactivé. Une fiche par point donne :
- la décision attendue et qui la prend ;
- le compte et l'écran à ouvrir ;
- les gestes à faire devant l'assistance.

Les décisions se notent pendant la séance sur la [fiche de décision](fiche-de-decision.md).

## Préparer l'environnement (la veille)

Sur le poste de démonstration, depuis la racine du dépôt :

```bash
docker compose stop   # libère les ports de l'environnement de développement, s'il tourne
docker compose -p hopitalia-budget-simulation -f docker-compose.yml -f docker-compose.simulation.yml down -v
docker compose -p hopitalia-budget-simulation -f docker-compose.yml -f docker-compose.simulation.yml up -d --build
cd backend && .venv/Scripts/python ../simulation/demonstration.py
```

Le script rejoue d'abord la [recette blanche](../recette/recette-blanche.md) (jeu d'essai de l'annexe 18.2), et s'arrête si elle n'est pas conforme. Il prépare ensuite ce que la séance montre :
- une révision et un engagement en attente de visa ;
- des alertes et leurs courriels ;
- des commandes de la pharmacie avec un engagement proposé ;
- un échange Hopitalia en échec, à reprendre ;
- trois recettes.

La tâche quotidienne des échanges est mise en pause, pour que l'échec reste visible jusqu'à la séance.

| Accès | Adresse |
|---|---|
| Application | http://127.0.0.1:8080 |
| Courriels reçus (boîte de test) | http://127.0.0.1:8025 |

**Comptes.** Le mot de passe est `recette` pour tous. Ouvrir une fenêtre de navigation privée par compte pour passer d'un profil à l'autre.

| Compte | Profil | Établissement |
|---|---|---|
| `agent001` | Administrateur fonctionnel (ADM) | Tous |
| `agent002` | Responsable budgétaire (RB) | CHU-A |
| `agent003` | Valideur, DAF (VAL) | CHU-A |
| `agent004` | Ordonnateur (ORD) | CHU-A |
| `agent006` | Lecteur (LEC) | CHU-B (ne voit rien de CHU-A) |
| `agent007` | Auditeur (AUD) | Tous |
| `agent011` | Gestionnaire de marchés et contrats (GMC) | CHU-A |
| `agent012` | Agent financier (AF) | CHU-A |
| `agent013` | Réceptionnaire (REC) | CHU-A |
| `agent014` | Comptable (CPT) | CHU-A |

Deux précisions à donner en séance :
- les libellés des pièces du jeu d'essai (« Achat 368f08 ») sont produits par les tests automatisés ; les montants, eux, sont ceux de l'annexe 18.2 ;
- les fournisseurs, services et commandes de la pharmacie viennent d'un Hopitalia simulé ; la vérification sur une vraie instance reste à faire (V-09).

## Ordre de la séance

| Partie | Points | Avec | Durée indicative |
|---|---|---|---|
| 1. Chaîne de dépense et contrôles | V-01 à V-05 | DAF | 45 min |
| 2. Recettes, alertes et courriels | V-06, V-07 | DAF | 20 min |
| 3. Comptabilité | V-08 | Service comptable | 15 min |
| 4. Hopitalia | V-09 | Équipe Hopitalia | 15 min |
| 5. Exploitation et documentation | V-10 à V-12 | DSI, DAF | 20 min |

---

## V-01. Chaîne de dépense, du marché au paiement

- **Décision attendue :** la chaîne correspond-elle au fonctionnement de l'établissement ? Elle est l'objet de la recette des lots 1 à 5 (T-198).
- **Qui décide :** DAF.
- **Où :** `agent002`, écrans Tableau de bord, Contrats, Engagements, Factures, Paiements.
- **Démonstration :**
  1. Tableau de bord : budget, engagé, liquidé, payé et disponible par ligne. Rappeler que ces étapes d'une même dépense ne s'additionnent pas.
  2. Contrats : le marché M-2026-001 (100 M). Sa fiche donne engagé 80 M, liquidé 45 M, payé 30 M et 20 M restant à engager, comme l'annexe 18.2.
  3. Factures : FAC-001, partiellement payée (25 M sur 30 M), et ses rattachements à l'engagement et à la réception.
  4. Paiements : les paiements de l'annexe, et le reste à payer sur liquidé (15 M).
- **Référence :**
  - [recette-lots-1-a-5.md](../recette/recette-lots-1-a-5.md) ;
  - [repetition-recette.md](../recette/repetition-recette.md), répétition conforme.

## V-02. Circuits de validation et matrice des habilitations

- **Décision attendue :**
  - **matrice et circuits par défaut (T-281) :** l'engagement passe par le contrôle financier (AF), puis la DAF (VAL), puis l'ordonnateur (ORD), qui valide toujours en dernier ;
  - **annulation d'une opération validée :** faut-il un circuit propre ? Aujourd'hui, un agent habilité l'enregistre directement, avec un motif ;
  - **clôture d'exercice :** même question.
- **Qui décide :** DAF.
- **Où :** `agent003` (VAL), puis `agent004` (ORD), écran Engagements ; `agent001`, écran Habilitations.
- **Démonstration :**
  1. `agent003` : l'engagement ENG-2026-00006, « Maintenance des équipements de stérilisation » (3,5 M), est en contrôle. Son onglet de validation montre le visa de l'agent financier ; donner le visa de la DAF.
  2. `agent004` : valider en dernier. L'engagement passe à « Validé » et consomme le crédit.
  3. `agent003` puis `agent004` : la révision budgétaire de 5 M (virement de 604-MED vers 604-CMD) attend son visa. La viser, puis la valider.
  4. Montrer qu'un agent ne vise pas sa propre pièce (séparation des tâches).
- **Référence :** [workflows-et-habilitations.md](../conception/workflows-et-habilitations.md), produit depuis le code.

## V-03. Nouvelle ligne de matrice : rattacher une commande de la pharmacie

- **Décision attendue :** l'agent financier rattache les commandes de la pharmacie aux engagements ; le gestionnaire des marchés consulte. Cette ligne a été ajoutée au lot 3 : elle est à confirmer.
- **Qui décide :** DAF.
- **Où :** `agent012`, écran Commandes de la pharmacie.
- **Démonstration :**
  1. Les commandes à rattacher : elles sont importées d'Hopitalia, sans ressaisie.
  2. Une commande avec un engagement proposé (même fournisseur, reste suffisant) : la rattacher.
  3. Les commandes rattachées : le bon de commande est créé, et ses livraisons sont devenues des réceptions validées.

## V-04. Nouvelle ligne de matrice : gérer les recettes

- **Décision attendue :**
  - RB, AF et CPT saisissent les recettes ; VAL, ORD et AUD consultent ;
  - le volet est-il souhaité dès maintenant ? Le cahier des charges (section 17, point 14) le prévoyait après la mise en service.
- **Qui décide :** DAF.
- **Où :** `agent002`, écran Recettes ; `agent001`, fiche de l'établissement CHU-A.
- **Démonstration :**
  1. Recettes : trois recettes (subvention, prestations, assurances), chacune avec prévu, facturé, encaissé, reste à recouvrer et taux.
  2. La recette des assurances : ses mouvements, dont un contre-mouvement négatif motivé (« Encaissement saisi deux fois »). Un mouvement ne se modifie jamais.
  3. Le tableau de bord des recettes, par nature, service et mois.
  4. `agent001`, fiche de l'établissement : désactiver le volet recettes, puis le réactiver. Le menu disparaît et réapparaît.

## V-05. Contrôles proposés à confirmer

- **Décision attendue :**
  - **doublon de facture :** même fournisseur, montant et objet, à moins de 30 jours. Faut-il ajuster ce critère ?
  - **paiement au-delà du solde dû :** il est refusé sans exception. Faut-il une dérogation ?
  - **bon de commande émis :** il ne se modifie ni ne s'annule. Faut-il un circuit ?
- **Qui décide :** DAF.
- **Où :** `agent002`, écran Alertes ; `agent012`, écran Factures.
- **Démonstration :** les alertes du jeu d'essai (doublon probable, seuil du marché, crédit insuffisant) et les pièces qu'elles désignent.
- **Référence :** [POINTS_REPORTES.md](../../POINTS_REPORTES.md).

## V-06. Volet recettes : natures, débiteurs, états

- **Décision attendue :**
  - les cinq natures de recette conviennent-elles ? Ce sont : subvention ou dotation, recette propre, remboursement d'assurance, prestation hospitalière, autre ;
  - les types de débiteurs conviennent-ils ?
  - un état imprimable des recettes est-il nécessaire ? Il n'existe pas aujourd'hui.
- **Qui décide :** DAF.
- **Où :** `agent001`, écran Paramétrage, débiteurs (« Assurances du Sénégal ») ; `agent002`, écran Recettes.

## V-07. Alertes et courriels

- **Décision attendue :**
  - **alertes par courriel :** lesquelles partent aussi par courriel ? Avec quels seuils (marchés à 80, 90 et 100 %) et quels délais (facture échue, engagement ancien, échéance de contrat) ?
  - **adresse des agents :** chaque agent saisit la sienne, car l'API Hopitalia n'en fournit pas. Cela convient-il ?
- **Qui décide :** DAF ; la DSI, pour le serveur de messagerie.
- **Où :**
  - `agent002`, écran Alertes, champ de l'adresse de courriel ;
  - `agent001`, règles des alertes ;
  - la boîte de test, http://127.0.0.1:8025.
- **Démonstration :**
  1. Alertes : seuil du marché atteint, crédit insuffisant, doublon probable.
  2. Boîte de test : la même alerte en français pour un agent, et en anglais pour l'agent qui a choisi l'anglais.
  3. Règles : activer l'envoi par courriel d'une alerte.

## V-08. Export vers la comptabilité

- **Décision attendue :** le fichier d'écritures est-il accepté (T-205) ? Comptes proposés :
  - 401 pour les fournisseurs ;
  - 471, compte d'attente, pour les déductions ;
  - 521, 531 ou 571 pour la trésorerie, selon le type de compte.
- **Qui décide :** service comptable.
- **Où :** `agent002`, écran États, état des écritures comptables.
- **Démonstration :** le télécharger en tableur. Montrer que le débit égale le crédit, que les comptes de charge viennent de la nomenclature, et que le fournisseur figure comme tiers.

## V-09. Échanges avec Hopitalia

- **Décision attendue :**
  - l'équipe Hopitalia ouvre-t-elle un compte technique et une instance avec des données (T-201, T-202) ?
  - la facturation des patients sera-t-elle ouverte au volet recettes (T-203) ?
- **Qui décide :** équipe Hopitalia.
- **Où :** `agent001`, écran Intégrations ; `agent012`, écran Commandes de la pharmacie.
- **Démonstration :**
  1. Intégrations : l'échange « Services » est en échec. Le reprendre : il réussit, sans doublon.
  2. Expliquer que la tâche quotidienne reprend seule les échecs ; elle a été mise en pause pour la séance.
  3. Expliquer que la démonstration utilise un Hopitalia simulé (121 fournisseurs, 85 commandes de la pharmacie). La vérification doit se refaire sur leur instance.
- **Référence :** [integration-hopitalia.md](../cadrage/integration-hopitalia.md), [guide-integration.md](../integration/guide-integration.md).

## V-10. Environnement de recette et exploitation

- **Décision attendue :**
  - serveur de recette, nom d'hôte et certificat (T-254) ;
  - validation du plan d'exploitation (T-285) ;
  - fréquence de l'essai de restauration : trimestrielle (ENF-06), à valider ;
  - serveur de messagerie de l'hôpital.
- **Qui décide :** DSI.
- **Où :** [deploiement-recette.md](../exploitation/deploiement-recette.md), [plan-exploitation.md](../exploitation/plan-exploitation.md), [sauvegarde.md](../exploitation/sauvegarde.md).

## V-11. Paramètres techniques provisoires

- **Décision attendue :** les valeurs proposées, toutes paramétrables, conviennent-elles ?
  - 300 requêtes par minute et par agent ;
  - 10 imports ou exports par heure ;
  - ancienne version de l'API maintenue 12 mois après la suivante ;
  - clés d'idempotence conservées 24 heures.
- **Qui décide :** DSI et DAF.
- **Référence :** cahier des charges, section 17, point 7.

## V-12. Guides et procès-verbal final

- **Décision attendue :**
  - désigner un agent par profil pour relire le guide utilisateur (T-283) ;
  - désigner un administrateur qui paramètre un établissement avec le guide d'administration (T-284) ;
  - fixer la date de la recette finale et de son procès-verbal (T-286).
- **Qui décide :** DAF.
- **Référence :** [guide-utilisateur.md](../guides/guide-utilisateur.md), [guide-administration.md](../guides/guide-administration.md), [proces-verbal-final.md](../recette/proces-verbal-final.md).

## Après la séance

Les décisions de la fiche sont reportées le jour même :
- dans le [cahier des tâches](../../CAHIER_DES_TACHES.md) : statut et journal ;
- dans le [cahier des charges](../Cahier_des_charges_Module_Budgetaire_Hopitalia_V3.md), quand une décision le modifie ;
- dans les [points reportés](../../POINTS_REPORTES.md).

Chaque point « À modifier » devient une tâche.
