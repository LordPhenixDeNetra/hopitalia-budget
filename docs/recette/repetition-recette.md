# Répétition de la recette (recette blanche)

**Projet :** Hopitalia Budget · **Date :** 16/11/2026 06:19 UTC · **Version :** `v0.1.0-6-g28c11c6-dirty` · **Statut :** répétition, sans valeur de procès-verbal

Produit par `simulation/recette_blanche.py` sur la pile Docker de simulation (`docker-compose.simulation.yml`) : base PostgreSQL neuve, Hopitalia simulé, serveur de courrier de test. Mode d'emploi : [recette-blanche.md](recette-blanche.md).

**Résultat :** 11 étape(s) conforme(s) sur 11.

| Réf. | Étape | Résultat | Constat |
|---|---|---|---|
| PREP-01 | Pile démarrée, premier administrateur attribué sur le serveur | Conforme | API saine ; ADM attribué par la commande `habiliter`. |
| PREP-02 | Établissements, profils de chaque agent (annuaire Hopitalia simulé) | Conforme | 13 profils attribués par l'écran Habilitations (API), noms lus dans l'annuaire. |
| REC-01 | Nomenclature, référentiels, exercice et budget avec ses crédits | Conforme | 85 nœuds de nomenclature ; budget BP-2026 : 604-MED 90 M, 604-CMD 40 M. |
| COUR-01 | Courriels : adresses des agents et règle « crédit insuffisant » par courriel | Conforme | RB (français) et AF (anglais) ont donné leur adresse ; la règle envoie par courriel. |
| REC-14 | Jeu d'essai de l'annexe 18.2 (REC-02, 03, 05, 06, 08, 09, 10, 11 compris) et ses contrôles | Conforme | Marché M-2026-001 et ses pièces saisis et validés profil par profil ; synthèse, lignes, restes et statuts identiques à l'annexe ; plafond, crédit, doublon et trop-payé bloqués. |
| REC-17 | Un agent d'un autre établissement ne voit rien de CHU-A | Conforme | Liste vide et fiche introuvable (404) pour le lecteur de CHU-B. |
| REC-18 | État PDF produit en anglais pour un agent anglophone | Conforme | PDF de 1527 octets, titre en anglais. |
| INT-01 | Fournisseurs et services importés d'Hopitalia, deux fois sans doublon | Conforme | Fournisseurs : {'crees': 120, 'modifies': 1, 'lus': 121} puis {'lus': 121} ; services : {'crees': 19, 'lus': 20} ; après un jour : {'desactives': 1, 'lus': 120} (fournisseur retiré désactivé). |
| INT-03 | Pharmacie : commandes importées, rattachement, réceptions, suppression | Conforme | Premier import : {'commandes': 85, 'approvisionnements': 85} ; 85 commandes à rattacher ; 1 engagement(s) proposé(s) ; rattachement de BCP-00082 : 2 réception(s) validée(s) créée(s) ; après un jour : {'commandes': 5, 'approvisionnements': 5} ; approvisionnement reçu supprimé dans Hopitalia : {'annulations': 1}, réceptions ['ANNULE', 'VALIDE']. |
| RCT-01 | Volet recettes : activation, recette, facturé, encaissé, tableau de bord | Conforme | Recette RCT-2026-00001 : reste à recouvrer 15 M, recouvrement 75 %. |
| COUR-02 | Courriel d'alerte reçu dans la langue de chaque destinataire | Conforme | 2 courriel(s) dans la boîte de test ; dernier envoi : 0 en file, 0 envoyés, 0 en échec. |

## Ce que cette répétition ne remplace pas

- La séance de recette avec la DAF (T-198), ses constats et sa signature (T-286).
- La vérification sur une instance Hopitalia réelle : la forme des réponses simulées suit la note d'intégration, pas des réponses observées (T-201, T-202).
- Le serveur de messagerie de l'hôpital et l'environnement de recette sur ses serveurs (T-254).
