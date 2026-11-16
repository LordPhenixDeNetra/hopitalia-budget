# Guide utilisateur

**Projet :** Hopitalia Budget · **Tâche :** T-283 · **Référence :** cahier des charges V3, section 16 · **Statut :** à relire par un utilisateur de chaque profil

Ce guide explique, profil par profil, ce que chaque agent fait dans le module de suivi budgétaire. Les droits exacts de chaque profil sont dans la [matrice des habilitations](../conception/workflows-et-habilitations.md).

## Pour tous

**Se connecter.** Avec son identifiant et son mot de passe Hopitalia. Le module n'a pas de mot de passe propre. Un agent sans profil budgétaire est refusé : demander un profil à l'administrateur du module.

**L'écran.**

- Le **menu** à gauche ne montre que ce que vos profils permettent.
- En haut, le sélecteur d'**établissement** limite l'affichage à un établissement ; « tous les établissements » montre tout votre périmètre.
- Le sélecteur de **langue** passe l'interface en anglais ou en français. Les données ne changent pas.
- L'**accueil** rappelle vos profils et les établissements où ils s'appliquent.
- **Affichage**, dans l'en-tête : thème clair, sombre ou celui de votre ordinateur, et densité compacte ou confortable. Dans les listes, le bouton « Colonnes » masque les colonnes inutiles. Ces choix sont conservés sur votre profil, d'un poste à l'autre.

**Retrouver une pièce.** « Recherche » trouve un engagement, une commande, une facture, un paiement ou un contrat par son numéro ou son objet, et ouvre sa fiche.

**Les alertes.** En haut de l'écran Alertes, donnez votre adresse pour recevoir aussi par courriel, dans votre langue, les alertes que l'administrateur a choisi d'envoyer. Le menu « Alertes » affiche le nombre d'alertes non lues. Une alerte signale un dépassement, un doublon, un écart ou une échéance, et renvoie à la pièce concernée. Elle est marquée lue une fois consultée.

**Valider une pièce.** Ouvrir la pièce depuis sa liste ou depuis l'alerte, puis l'onglet « Validation et pièces » :

- « Viser » valide votre étape ; un motif est demandé pour « Rejeter » ou « Retourner pour correction » ;
- le circuit indique l'étape en attente et qui l'a visée, y compris par délégation ;
- on ne vise jamais une pièce que l'on a saisie soi-même (séparation des tâches).

**Joindre des pièces.** Dans le même onglet : PDF, PNG, JPEG, Word ou Excel, 20 Mo au plus. Une pièce déposée ne se modifie plus ; elle est contrôlée par son empreinte à chaque téléchargement.

**S'absenter.** « Délégations » permet de désigner, pour une période, un agent qui vise à votre place dans les circuits. Il n'obtient aucun autre droit. Une délégation peut être raccourcie ou révoquée.

**Une erreur s'affiche.** Le message explique la règle en cause : crédit insuffisant, plafond du marché, doublon… Corriger la saisie ou demander une dérogation à qui de droit. Une pièce validée ne se modifie plus : une correction passe par une annulation tracée.

## Responsable budgétaire (RB)

- **Budgets** :
  - créer le budget de l'exercice ;
  - charger les dotations (onglet « Import des dotations », fichier CSV ; le rapport d'anomalies liste les lignes refusées) ;
  - enregistrer les notifications de crédits reçues de la tutelle ;
  - exporter les lignes au même format (CSV ou JSON).
- **Révisions** (fiche budget, onglet « Révisions ») : demander un virement, une augmentation ou une diminution de crédits. Une révision n'a d'effet qu'une fois validée par le valideur puis l'ordonnateur.
- **Situation** (onglet « Situation ») : budget initial, révisé, engagé, disponible, liquidé et payé, ligne par ligne. Ces chiffres sont toujours recalculés depuis les pièces.
- **Clôture d'exercice** : clôturer l'exercice d'un établissement, avec un motif. Les engagements non soldés sont reportés sur l'exercice suivant ; une réouverture motivée reste possible.

## Gestionnaire de marchés et contrats (GMC)

- **Contrats** :
  - enregistrer un marché déjà attribué ou un contrat déjà signé (montant, fournisseur, échéances, ventilation sur les lignes budgétaires, pièces), puis le soumettre ;
  - le module ne gère pas la passation des marchés.
- **Avenants** (fiche contrat) : un avenant ne change le plafond qu'une fois validé ; l'historique est conservé.
- **Engagements** : créer l'engagement (lié au marché ou hors marché), l'imputer sur les lignes, puis le soumettre. Les crédits disponibles et le plafond du marché sont contrôlés à la soumission.
- **Commandes** : émettre un bon de commande sur un engagement validé, dans la limite de son montant.
- **Commandes de la pharmacie** : consulter les commandes importées d'Hopitalia.

## Service demandeur (SD)

- **Engagements** : demander un engagement pour son service, le soumettre et suivre son circuit.
- **Commandes** : consulter les commandes et leurs réceptions.

## Agent financier (AF)

- **Engagements** : contrôler l'engagement (imputation, crédits disponibles). C'est la première étape de son circuit.
- **Commandes de la pharmacie** : rattacher chaque commande importée d'Hopitalia à un engagement validé du même fournisseur. Le module propose les engagements dont le reste à commander couvre la commande. Une fois la commande rattachée, ses approvisionnements deviennent des réceptions validées.
- **Factures** :
  - enregistrer la facture du fournisseur ; un doublon est bloqué, sauf levée motivée ;
  - la liquider (onglet « Liquidations » : base, déductions, réceptions concernées), puis soumettre la liquidation ;
  - rapprocher commande, réception, facture et paiement (onglet « Rapprochement ») ; un écart doit être expliqué.
- **Annulations** (fiche engagement, onglet « Annulations ») : annuler tout ou partie d'un engagement validé, avec un motif.

## Réceptionnaire (REC)

- **Commandes** (fiche du bon de commande) :
  - enregistrer la réception : quantités reçues, acceptées et rejetées, réserves éventuelles ;
  - joindre le bon de livraison ou le procès-verbal, puis soumettre ;
  - le service fait n'est acquis qu'après validation.

## Valideur (VAL)

- **Viser** les révisions, contrats, avenants, engagements, dérogations et liquidations au rang prévu par le circuit.
- **Valider le service fait** des réceptions.
- **Accorder une dérogation** quand un dépassement est justifié : elle ne couvre que la nature, l'objet et le montant accordés.
- Consulter le **journal d'audit**.

## Ordonnateur (ORD)

- **Valider en dernier** les révisions, contrats, avenants, engagements, dérogations et liquidations : l'ordonnateur valide toujours après le valideur.
- **Ordonnancement et paiements**, onglet « Ordonnancements » : regrouper les liquidations validées, indiquer le mandat ou l'ordre de paiement, et transmettre au comptable.
- **Clôturer** ou rouvrir un exercice, comme le responsable budgétaire.

## Comptable (CPT)

- **Ordonnancement et paiements** :
  - prendre en charge les ordonnancements transmis, ou demander un complément, suspendre, rejeter ;
  - enregistrer le paiement exécuté, ventilé par liquidation. Un paiement peut solder plusieurs factures ou une partie d'une facture. Il ne dépasse jamais le solde dû.

## Auditeur (AUD)

- Consulter toutes les pièces en lecture seule.
- **Journal d'audit** : chaque opération, connexion et export, avec l'avant et l'après ; rapport d'audit en PDF, tableur ou CSV.

## Lecteur (LEC)

- **Tableau de bord** et **États** de son établissement, en lecture seule.

## Recettes (RB, AF, CPT ; VAL, ORD, AUD en lecture)

Le menu « Recettes » n'apparaît que si le volet est activé dans votre établissement.

- **Recettes** : enregistrer une recette prévue (nature, libellé, montant prévu, échéance, source, service, débiteur).
- **Fiche d'une recette** : enregistrer le facturé et l'encaissé. Une erreur se corrige par un mouvement négatif, avec un motif ; un mouvement enregistré ne se modifie pas.
- **Tableau de bord** : prévu, facturé, encaissé, reste à recouvrer et taux, par nature, par service et par mois.

## Tableau de bord et états (tous les profils qui y ont accès)

- **Tableau de bord** : les étapes de la dépense (engagé, commandé, réceptionné, facturé, liquidé, transmis, payé), les jauges de consommation, les principaux marchés et les factures en attente. Filtres : exercice, période, service, compte, fournisseur, marché, source de financement.
- **États** : les mêmes filtres, à télécharger en PDF, tableur, CSV ou JSON. Chaque total d'état est celui du tableau de bord.
- Engagé, facturé, liquidé, transmis et payé sont des étapes d'une même dépense : ils ne s'additionnent pas entre eux.
