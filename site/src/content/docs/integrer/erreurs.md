---
title: Erreurs
description: Le format problem+json des erreurs, le code stable à utiliser dans un programme, et les codes les plus courants.
sidebar:
  order: 4
---

Toute erreur est au format `application/problem+json`, avec un `code` **stable**, à utiliser dans le programme client. Le titre et le détail sont traduits selon `Accept-Language` et peuvent changer d'une version à l'autre.

```json
{
  "type": "https://hopitalia-budget/erreurs/credit-insuffisant",
  "title": "Crédit insuffisant",
  "status": 422,
  "code": "CREDIT_INSUFFISANT",
  "detail": "…",
  "erreurs": [{"champ": "montant", "code": "…"}]
}
```

`erreurs` liste les champs en faute d'une requête invalide (`422 VALIDATION`).

## Codes courants

| Statut | Code | Signification |
|---|---|---|
| 400 | `PARAMETRE_INCONNU`, `TRI_INVALIDE` | Paramètre non documenté, ou tri non permis. |
| 400 | `IDEMPOTENCE_CLE_MANQUANTE` | `Idempotency-Key` manquant sur une création. |
| 401 | `AUTHENTIFICATION_REQUISE`, `JETON_INVALIDE` | Jeton absent, expiré ou invalide : se reconnecter ou rafraîchir. |
| 403 | `AUCUN_PROFIL`, `ACCES_REFUSE` | Le compte n'a pas le profil ou l'établissement requis. |
| 403 | `SEPARATION_DES_TACHES`, `SEPARATION_PAIEMENT` | L'agent ne peut pas viser ou payer cette pièce (RG-13). |
| 404 | `RESSOURCE_INTROUVABLE` | Inexistante, ou hors du périmètre du compte. |
| 409 | `FACTURE_DOUBLON` | La facture double une facture déjà enregistrée (RG-16). |
| 409 | `OPERATION_NON_MODIFIABLE` | La pièce est validée (RG-18). |
| 412 | `PRECONDITION_ECHOUEE` | La fiche a changé depuis sa lecture. |
| 422 | `VALIDATION` | Champs invalides, détaillés dans `erreurs`. |
| 422 | `CREDIT_INSUFFISANT`, `PLAFOND_INSUFFISANT`, `CONTROLE_BLOQUANT`, `PAIEMENT_SUP_SOLDE`… | Une règle de gestion refuse l'opération. |
| 422 | `PIECES_MANQUANTES` | Une pièce justificative obligatoire manque. |
| 422 | `IDEMPOTENCE_CONFLIT` | Clé d'idempotence déjà utilisée avec un autre corps. |
| 428 | `PRECONDITION_REQUISE` | `If-Match` manquant. |
| 429 | `LIMITE_DEBIT` | Trop de requêtes ; attendre `Retry-After`. |
| 500 | `ERREUR_INTERNE` | Sans détail technique ; donner le `X-Request-ID` à l'exploitation. |

La liste complète des codes est dans le document OpenAPI de la version en service.
