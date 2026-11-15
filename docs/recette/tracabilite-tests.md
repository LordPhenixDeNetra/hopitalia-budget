# Traçabilité des exigences vers les tests

**Projet :** Hopitalia Budget · **Tâches :** T-245 à T-247 · **Référence :** cahier des charges V3, sections 5, 15.1 et 15.2

Tableau produit à partir des tests (nom et docstring des tests backend, titre des tests Vitest et Playwright). Ne pas le modifier à la main : le régénérer depuis `backend/` par `python -m tests.test_tracabilite`. Le test `test_tracabilite.py` échoue si une exigence n'a aucun test ou si ce tableau n'est plus à jour.

| Exigence | Tests |
|---|---|
| RG-01 | `backend/tests/test_engagements.py::test_rg01_engagement_rattache_a_un_exercice_et_a_ses_lignes`<br>`backend/tests/test_tracabilite.py::test_chaque_exigence_a_son_test` |
| RG-02 | `backend/tests/test_engagements.py::test_rg02_controle_credits_identique_pour_les_sous_classes`<br>`backend/tests/test_engagements.py::test_rg02_credit_insuffisant_et_derogation_limitee` |
| RG-03 | `backend/tests/test_contrats.py::test_rg03_contrat_sans_signature_ni_notification_refuse` |
| RG-04 | `backend/tests/test_engagements.py::test_rec03_plafond_du_marche` |
| RG-05 | `backend/tests/test_factures.py::test_facture_rattachee_a_un_engagement_valide` |
| RG-06 | `backend/tests/test_factures.py::test_rg06_service_fait_avant_liquidation` |
| RG-07 | `backend/tests/test_paiements.py::test_rec08_rec09_paiements_partiels_et_solde`<br>`backend/tests/test_paiements.py::test_ventilation_solde_et_statut_de_la_facture` |
| RG-08 | `backend/tests/test_paiements.py::test_ventilation_solde_et_statut_de_la_facture` |
| RG-09 | `backend/tests/test_engagements.py::test_annulation_partielle_puis_totale` |
| RG-10 | `backend/tests/test_audit_cloture.py::test_t239_t240_cloture_report_et_reouverture` |
| RG-11 | `backend/tests/test_contrats.py::test_rec04_avenant_effectif_apres_validation` |
| RG-12 | `backend/tests/test_architecture.py::test_rec15_aucune_fonction_de_passation_dans_l_api` |
| RG-13 | `backend/tests/test_paiements.py::test_rg13_qui_valide_la_liquidation_ne_la_paie_pas`<br>`backend/tests/test_paiements.py::test_ventilation_solde_et_statut_de_la_facture`<br>`backend/tests/test_workflow.py::test_rg13_separation_des_taches_selon_le_circuit`<br>`frontend/src/App.test.tsx : révision : aucun bouton de décision si le serveur le refuse (RG-13)` |
| RG-14 | `backend/tests/test_architecture.py::test_rg14_aucun_indicateur_stocke` |
| RG-15 | `backend/tests/test_contrats.py::test_rg15_ventilation_incoherente_refusee`<br>`backend/tests/test_contrats.py::test_rg15_ventilation_vaut_pour_contrat_et_marche`<br>`backend/tests/test_engagements.py::test_rg15_engagement_incoherent_refuse` |
| RG-16 | `backend/tests/test_factures.py::test_rec11_doublon_de_facture` |
| RG-17 | `backend/tests/test_factures.py::test_une_liquidation_par_imputation` |
| RG-18 | `backend/tests/test_engagements.py::test_annulation_partielle_puis_totale`<br>`backend/tests/test_paiements.py::test_rg18_annulation_du_paiement` |
| RG-19 | `backend/tests/test_engagements.py::test_rg02_credit_insuffisant_et_derogation_limitee` |
| RG-20 | `backend/tests/test_engagements.py::test_rec16_deux_engagements_simultanes_un_seul_passe`<br>`backend/tests/test_tracabilite.py::test_chaque_exigence_a_son_test` |
| REC-01 | `backend/tests/test_tracabilite.py::test_chaque_exigence_a_son_test`<br>`frontend/e2e/parcours.spec.ts : REC-01 : créer un exercice puis importer les crédits du budget` |
| REC-02 | `frontend/e2e/parcours.spec.ts : REC-02 : enregistrer un marché avec ventilation, échéance et pièce` |
| REC-03 | `backend/tests/test_engagements.py::test_rec03_plafond_du_marche`<br>`frontend/e2e/parcours.spec.ts : REC-03 : engagement lié au marché, crédits et plafond contrôlés` |
| REC-04 | `backend/tests/test_contrats.py::test_rec04_avenant_effectif_apres_validation` |
| REC-05 | `frontend/e2e/parcours.spec.ts : REC-05 : livraison partielle enregistrée avec son procès-verbal` |
| REC-06 | `frontend/e2e/parcours.spec.ts : REC-06 : facture partielle enregistrée, contrôlée et liquidée` |
| REC-07 | `backend/tests/test_factures.py::test_rec07_reste_du_et_facture_superieure_a_la_reception` |
| REC-08 | `backend/tests/test_paiements.py::test_rec08_rec09_paiements_partiels_et_solde`<br>`frontend/e2e/parcours.spec.ts : REC-08 et REC-09 : ordonnancer, payer en partie, puis solder` |
| REC-09 | `backend/tests/test_paiements.py::test_rec08_rec09_paiements_partiels_et_solde`<br>`frontend/e2e/parcours.spec.ts : REC-08 et REC-09 : ordonnancer, payer en partie, puis solder` |
| REC-10 | `backend/tests/test_paiements.py::test_rec10_paiement_groupe_ventile`<br>`frontend/e2e/parcours.spec.ts : REC-10 : paiement groupé ventilé facture par facture` |
| REC-11 | `backend/tests/test_factures.py::test_rec11_doublon_de_facture` |
| REC-12 | `backend/tests/test_factures.py::test_rec12_rejet_correction_et_piste_d_audit`<br>`frontend/e2e/parcours.spec.ts : REC-12 : facture retournée, corrigée puis rejetée avec motif`<br>`frontend/src/App.test.tsx : rejet motivé d’une facture (REC-12)` |
| REC-13 | `backend/tests/test_api_avec_base.py::test_operation_non_autorisee_refusee`<br>`backend/tests/test_workflow.py::test_rg13_separation_des_taches_selon_le_circuit` |
| REC-14 | `backend/tests/test_recette_chaine_depense.py::test_rec14_jeu_d_essai_de_l_annexe_18_2`<br>`backend/tests/test_tableaux_de_bord.py::test_t210_t211_tableau_de_la_direction` |
| REC-15 | `backend/tests/test_architecture.py::test_rec15_aucune_fonction_de_passation_dans_l_api` |
| REC-16 | `backend/tests/test_engagements.py::test_rec16_deux_engagements_simultanes_un_seul_passe` |
| REC-17 | `backend/tests/test_api_avec_base.py::test_lecteur_ne_voit_que_son_etablissement` |
| REC-18 | `backend/tests/test_tracabilite.py::test_chaque_exigence_a_son_test`<br>`frontend/e2e/parcours.spec.ts : REC-18 : état PDF produit dans la langue de l’agent (T-230)` |
| API-01 | `backend/tests/test_api_avec_base.py::test_rejeu_avec_la_meme_cle_ne_cree_rien`<br>`backend/tests/test_paiements.py::test_api01_idempotence_du_paiement`<br>`backend/tests/test_tracabilite.py::test_chaque_exigence_a_son_test` |
| API-02 | `backend/tests/test_api_avec_base.py::test_meme_cle_corps_different`<br>`backend/tests/test_paiements.py::test_api01_idempotence_du_paiement` |
| API-03 | `backend/tests/test_api_avec_base.py::test_post_financier_sans_cle_refuse`<br>`backend/tests/test_paiements.py::test_api01_idempotence_du_paiement` |
| API-04 | `backend/tests/test_engagements.py::test_circuit_engage_et_immuabilite` |
| API-05 | `backend/tests/test_api_avec_base.py::test_modification_exige_if_match_a_jour` |
| API-06 | `backend/tests/test_api_avec_base.py::test_curseur_stable_malgre_nouvelles_lignes` |
| API-07 | `backend/tests/test_api_avec_base.py::test_champ_non_documente_refuse` |
| API-08 | `backend/tests/test_api_avec_base.py::test_limite_de_debit` |
| API-09 | `backend/tests/test_api_avec_base.py::test_api09_version_inconnue` |
| API-10 | `backend/tests/test_api_avec_base.py::test_lecteur_ne_voit_que_son_etablissement` |
| API-11 | `backend/tests/test_contrat_openapi.py::test_api11_reponses_conformes_au_document_publie`<br>`backend/tests/test_contrat_openapi.py::test_document_publie_identique_a_l_application`<br>`backend/tests/test_tracabilite.py::test_chaque_exigence_a_son_test` |
