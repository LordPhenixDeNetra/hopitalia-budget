"""Tables du socle. Toute évolution passe par une migration Alembic (backend/migrations)."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from hopitalia_budget.adaptateurs.sortie.base import MONTANT, Base


class EtablissementModele(Base):
    __tablename__ = "etablissement"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    nom: Mapped[str] = mapped_column(String(200))
    actif: Mapped[bool] = mapped_column(default=True)
    version: Mapped[int] = mapped_column(default=1)

    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012  (convention SQLAlchemy)


class HabilitationModele(Base):
    """Profil budgétaire d'un agent Hopitalia ; établissement absent : tous les établissements."""

    __tablename__ = "habilitation"
    __table_args__ = (
        UniqueConstraint(
            "utilisateur_id", "profil", "etablissement_id", postgresql_nulls_not_distinct=True
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    utilisateur_id: Mapped[int] = mapped_column(BigInteger, index=True)
    code_agent: Mapped[str] = mapped_column(String(20))
    nom_agent: Mapped[str] = mapped_column(String(200), default="", server_default="")
    profil: Mapped[str] = mapped_column(String(3))
    etablissement_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("etablissement.id"))


class PreferenceUtilisateurModele(Base):
    __tablename__ = "preference_utilisateur"

    utilisateur_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    langue: Mapped[str] = mapped_column(String(5))


class CleIdempotenceModele(Base):
    __tablename__ = "cle_idempotence"

    utilisateur_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    cle: Mapped[str] = mapped_column(String(100), primary_key=True)
    empreinte_requete: Mapped[str] = mapped_column(String(64))
    # Absents tant que la première requête est en cours de traitement.
    code_reponse: Mapped[int | None]
    reponse: Mapped[Any | None] = mapped_column(JSONB)
    expire_le: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class JournalAuditModele(Base):
    """Journal en ajout seul : des déclencheurs refusent toute modification et suppression."""

    __tablename__ = "journal_audit"
    __table_args__ = (Index("ix_journal_audit_horodatage_id", "horodatage", "id"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    horodatage: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    utilisateur_id: Mapped[int | None] = mapped_column(BigInteger)
    code_agent: Mapped[str | None] = mapped_column(String(20))
    etablissement_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    action: Mapped[str] = mapped_column(String(40))
    type_objet: Mapped[str] = mapped_column(String(60))
    id_objet: Mapped[str] = mapped_column(String(64))
    ancienne_valeur: Mapped[Any | None] = mapped_column(JSONB)
    nouvelle_valeur: Mapped[Any | None] = mapped_column(JSONB)
    adresse_ip: Mapped[str | None] = mapped_column(String(45))


# --- Lot 1 : référentiels, exercices, budgets et crédits ------------------------------------


class SiteModele(Base):
    __tablename__ = "site"
    __table_args__ = (UniqueConstraint("etablissement_id", "code"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    etablissement_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("etablissement.id"), index=True)
    code: Mapped[str] = mapped_column(String(20))
    libelle: Mapped[str] = mapped_column(String(200))
    adresse: Mapped[str | None] = mapped_column(String(300))
    actif: Mapped[bool] = mapped_column(default=True)
    version: Mapped[int] = mapped_column(default=1)

    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012


class CentreResponsabiliteModele(Base):
    """Service hospitalier ou centre de responsabilité, hiérarchique, propre à un établissement."""

    __tablename__ = "centre_responsabilite"
    __table_args__ = (UniqueConstraint("etablissement_id", "code"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    etablissement_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("etablissement.id"), index=True)
    code: Mapped[str] = mapped_column(String(20))
    libelle: Mapped[str] = mapped_column(String(200))
    type: Mapped[str] = mapped_column(String(30))
    parent_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("centre_responsabilite.id"))
    site_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("site.id"))
    code_responsable: Mapped[str | None] = mapped_column(String(20))
    code_hopitalia: Mapped[str | None] = mapped_column(String(20))
    actif: Mapped[bool] = mapped_column(default=True)
    version: Mapped[int] = mapped_column(default=1)

    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012


class ReferentielModele(Base):
    """Référentiels simples, partagés par tous les établissements (une colonne par attribut
    propre à un type : seuil, numéro, durée de conservation, bailleur, dates)."""

    __tablename__ = "referentiel"
    __table_args__ = (UniqueConstraint("type", "code"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    type: Mapped[str] = mapped_column(String(30), index=True)
    code: Mapped[str] = mapped_column(String(20))
    libelle: Mapped[str] = mapped_column(String(200))
    actif: Mapped[bool] = mapped_column(default=True)
    version: Mapped[int] = mapped_column(default=1)
    seuil_hors_marche: Mapped[Decimal | None] = mapped_column(MONTANT)
    type_compte: Mapped[str | None] = mapped_column(String(20))
    numero: Mapped[str | None] = mapped_column(String(50))
    duree_conservation_ans: Mapped[int | None]
    type_financement: Mapped[str | None] = mapped_column(String(30))
    bailleur: Mapped[str | None] = mapped_column(String(200))
    date_debut: Mapped[date | None]
    date_fin: Mapped[date | None]
    # Types de pièces : objets pour lesquels la pièce est obligatoire avant validation.
    types_objets: Mapped[list[str] | None] = mapped_column(JSONB)

    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012


class FournisseurModele(Base):
    __tablename__ = "fournisseur"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    raison_sociale: Mapped[str] = mapped_column(String(200))
    identifiants_administratifs: Mapped[str | None] = mapped_column(String(200))
    adresse: Mapped[str | None] = mapped_column(String(300))
    contact: Mapped[str | None] = mapped_column(String(200))
    code_hopitalia: Mapped[str | None] = mapped_column(String(20), unique=True)
    actif: Mapped[bool] = mapped_column(default=True)
    version: Mapped[int] = mapped_column(default=1)

    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012


class CoordonneePaiementModele(Base):
    """Coordonnées bancaires d'un fournisseur pour un établissement ; numéro chiffré (ENF-03)."""

    __tablename__ = "coordonnee_paiement"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    fournisseur_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("fournisseur.id"), index=True)
    etablissement_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("etablissement.id"))
    banque: Mapped[str] = mapped_column(String(200))
    numero_compte_chiffre: Mapped[str] = mapped_column(Text)
    fin_numero: Mapped[str] = mapped_column(String(4))
    par_defaut: Mapped[bool] = mapped_column(default=False)


class CompteComptableModele(Base):
    __tablename__ = "compte_comptable"

    code: Mapped[str] = mapped_column(String(10), primary_key=True)
    libelle: Mapped[str] = mapped_column(String(200))


class NoeudNomenclatureModele(Base):
    """Nomenclature budgétaire : section, chapitre, article, paragraphe (= compte budgétaire)."""

    __tablename__ = "noeud_nomenclature"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    niveau: Mapped[str] = mapped_column(String(10))
    code: Mapped[str] = mapped_column(String(20), unique=True)
    libelle: Mapped[str] = mapped_column(String(200))
    parent_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("noeud_nomenclature.id"))
    compte_comptable_code: Mapped[str | None] = mapped_column(
        ForeignKey("compte_comptable.code"), index=True
    )


class ExerciceModele(Base):
    __tablename__ = "exercice"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(10), unique=True)
    date_ouverture: Mapped[date]
    date_cloture: Mapped[date]
    statut: Mapped[str] = mapped_column(String(10), default="OUVERT")
    version: Mapped[int] = mapped_column(default=1)

    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012


class PeriodeModele(Base):
    __tablename__ = "periode"
    __table_args__ = (UniqueConstraint("exercice_id", "code"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    exercice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("exercice.id"), index=True)
    type: Mapped[str] = mapped_column(String(15))
    code: Mapped[str] = mapped_column(String(10))
    date_debut: Mapped[date]
    date_fin: Mapped[date]


class BudgetModele(Base):
    __tablename__ = "budget"
    __table_args__ = (
        # Un seul budget primitif par exercice et par établissement (T-088).
        Index(
            "ux_budget_primitif",
            "exercice_id",
            "etablissement_id",
            unique=True,
            postgresql_where=text("type = 'PRIMITIF'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    exercice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("exercice.id"), index=True)
    etablissement_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("etablissement.id"), index=True)
    reference: Mapped[str] = mapped_column(String(50))
    type: Mapped[str] = mapped_column(String(12))
    version: Mapped[int] = mapped_column(default=1)

    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012


class LigneBudgetaireModele(Base):
    """Ligne budgétaire : seule la dotation initiale est saisie ; tout le reste est calculé."""

    __tablename__ = "ligne_budgetaire"
    __table_args__ = (UniqueConstraint("budget_id", "code"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    budget_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("budget.id"), index=True)
    etablissement_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("etablissement.id"), index=True)
    code: Mapped[str] = mapped_column(String(30))
    libelle: Mapped[str] = mapped_column(String(200))
    compte_budgetaire_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("noeud_nomenclature.id"))
    centre_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("centre_responsabilite.id"))
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("referentiel.id"))
    programme_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("referentiel.id"))
    periode_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("periode.id"))
    nature_economique: Mapped[str | None] = mapped_column(String(100))
    dotation_initiale: Mapped[Decimal] = mapped_column(MONTANT)
    version: Mapped[int] = mapped_column(default=1)

    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012


class ImportDotationsModele(Base):
    __tablename__ = "import_dotations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    budget_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("budget.id"), index=True)
    etablissement_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("etablissement.id"))
    statut: Mapped[str] = mapped_column(String(10))
    lignes_importees: Mapped[int] = mapped_column(default=0)
    anomalies: Mapped[Any] = mapped_column(JSONB, default=list)
    contenu: Mapped[str] = mapped_column(Text)
    cree_par_id: Mapped[int] = mapped_column(BigInteger)
    cree_par_code: Mapped[str] = mapped_column(String(20))
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    termine_le: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class NotificationCreditModele(Base):
    __tablename__ = "notification_credit"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    budget_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("budget.id"), index=True)
    etablissement_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("etablissement.id"))
    reference: Mapped[str] = mapped_column(String(50))
    date_notification: Mapped[date]
    montant: Mapped[Decimal] = mapped_column(MONTANT)
    objet: Mapped[str] = mapped_column(String(300))
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("referentiel.id"))


class NotificationLigneModele(Base):
    __tablename__ = "notification_ligne"

    notification_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("notification_credit.id"), primary_key=True
    )
    ligne_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ligne_budgetaire.id"), primary_key=True)
    montant: Mapped[Decimal] = mapped_column(MONTANT)


class RevisionBudgetaireModele(Base):
    """Révision budgétaire : sans effet tant qu'elle n'est pas validée (EF-BUD-04)."""

    __tablename__ = "revision_budgetaire"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    budget_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("budget.id"), index=True)
    etablissement_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("etablissement.id"))
    type: Mapped[str] = mapped_column(String(20))
    sens: Mapped[str | None] = mapped_column(String(12))
    ligne_source_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ligne_budgetaire.id"), index=True
    )
    ligne_cible_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ligne_budgetaire.id"), index=True)
    montant: Mapped[Decimal] = mapped_column(MONTANT)
    motif: Mapped[str] = mapped_column(String(500))
    statut: Mapped[str] = mapped_column(String(20), index=True)
    cree_par_id: Mapped[int] = mapped_column(BigInteger)
    cree_par_code: Mapped[str] = mapped_column(String(20))
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(default=1)

    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012


class ValidationModele(Base):
    """Visa ou rejet d'une étape de validation, conservé à vie (historique des validations)."""

    __tablename__ = "validation"
    __table_args__ = (Index("ix_validation_objet", "type_objet", "id_objet"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    type_objet: Mapped[str] = mapped_column(String(60))
    id_objet: Mapped[uuid.UUID]
    etape: Mapped[str] = mapped_column(String(10))
    decision: Mapped[str] = mapped_column(String(10))
    motif: Mapped[str | None] = mapped_column(String(500))
    utilisateur_id: Mapped[int] = mapped_column(BigInteger)
    code_agent: Mapped[str] = mapped_column(String(20))
    horodatage: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # Ordre d'enregistrement : départage deux visas de même horodatage.
    rang: Mapped[int] = mapped_column(BigInteger, Identity())
    ordre: Mapped[int | None]
    visa: Mapped[str | None] = mapped_column(String(200))
    # Visa donné par délégation : code agent du délégant.
    delegant_code: Mapped[str | None] = mapped_column(String(20))


class WorkflowObjetModele(Base):
    """État de workflow d'un objet validable : circuit figé à la soumission, statut personnalisé."""

    __tablename__ = "workflow_objet"

    type_objet: Mapped[str] = mapped_column(String(60), primary_key=True)
    id_objet: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    statut: Mapped[str] = mapped_column(String(30))
    circuit: Mapped[dict[str, Any]] = mapped_column(JSONB)


class CircuitValidationModele(Base):
    """Circuit de validation d'un type d'objet, par établissement, service et tranche de montant."""

    __tablename__ = "circuit_validation"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    etablissement_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("etablissement.id"), index=True)
    type_objet: Mapped[str] = mapped_column(String(60))
    libelle: Mapped[str] = mapped_column(String(200))
    centre_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("centre_responsabilite.id"))
    seuil_min: Mapped[Decimal] = mapped_column(MONTANT, default=Decimal("0"))
    seuil_max: Mapped[Decimal | None] = mapped_column(MONTANT)
    separation_taches: Mapped[bool] = mapped_column(default=True)
    actif: Mapped[bool] = mapped_column(default=True)
    # Étapes [{ordre, libelle, profil, obligatoire}] : lues et remplacées ensemble.
    etapes: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    version: Mapped[int] = mapped_column(default=1)

    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012


class StatutPersonnaliseModele(Base):
    __tablename__ = "statut_personnalise"
    __table_args__ = (UniqueConstraint("etablissement_id", "type_objet", "code"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    etablissement_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("etablissement.id"))
    type_objet: Mapped[str] = mapped_column(String(60))
    code: Mapped[str] = mapped_column(String(30))
    libelle: Mapped[str] = mapped_column(String(200))
    statut_reference: Mapped[str] = mapped_column(String(30))
    version: Mapped[int] = mapped_column(default=1)

    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012


class TransitionStatutModele(Base):
    __tablename__ = "transition_statut"
    __table_args__ = (UniqueConstraint("etablissement_id", "type_objet", "depuis", "action"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    etablissement_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("etablissement.id"))
    type_objet: Mapped[str] = mapped_column(String(60))
    depuis: Mapped[str] = mapped_column(String(30))
    action: Mapped[str] = mapped_column(String(20))
    vers: Mapped[str] = mapped_column(String(30))
    profil: Mapped[str | None] = mapped_column(String(10))
    version: Mapped[int] = mapped_column(default=1)

    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012


class DelegationModele(Base):
    """Délégation temporaire : le délégataire vise avec les profils du délégant, dans ses dates."""

    __tablename__ = "delegation"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    delegant_id: Mapped[int] = mapped_column(BigInteger, index=True)
    delegant_code: Mapped[str] = mapped_column(String(20))
    delegataire_id: Mapped[int] = mapped_column(BigInteger, index=True)
    delegataire_code: Mapped[str] = mapped_column(String(20))
    date_debut: Mapped[date]
    date_fin: Mapped[date]
    motif: Mapped[str] = mapped_column(String(500))
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(default=1)

    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012


class PieceJustificativeModele(Base):
    """Pièce jointe à une opération (EF-DOC-01) ; contenu rangé par empreinte SHA-256."""

    __tablename__ = "piece_justificative"
    __table_args__ = (Index("ix_piece_objet", "type_objet", "id_objet"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    type_objet: Mapped[str] = mapped_column(String(60))
    id_objet: Mapped[uuid.UUID]
    etablissement_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("etablissement.id"))
    type_piece_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("referentiel.id"))
    nom_fichier: Mapped[str] = mapped_column(String(255))
    type_mime: Mapped[str] = mapped_column(String(100))
    taille: Mapped[int] = mapped_column(BigInteger)
    empreinte_sha256: Mapped[str] = mapped_column(String(64))
    depose_par_id: Mapped[int] = mapped_column(BigInteger)
    depose_par_code: Mapped[str] = mapped_column(String(20))
    depose_le: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ParametreCalculModele(Base):
    """Option de calcul de la section 6 choisie par un établissement (sinon valeur par défaut)."""

    __tablename__ = "parametre_calcul"

    etablissement_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("etablissement.id"), primary_key=True
    )
    code: Mapped[str] = mapped_column(String(50), primary_key=True)
    valeur: Mapped[str] = mapped_column(String(50))


class ContratModele(Base):
    """Contrat signé ou marché attribué (type MARCHE : nature et lot en plus), section 7.3."""

    __tablename__ = "contrat"
    __table_args__ = (UniqueConstraint("etablissement_id", "numero"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    etablissement_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("etablissement.id"), index=True)
    numero: Mapped[str] = mapped_column(String(50))
    intitule: Mapped[str] = mapped_column(String(300))
    type: Mapped[str] = mapped_column(String(20), index=True)
    nature: Mapped[str | None] = mapped_column(String(30))
    numero_lot: Mapped[str | None] = mapped_column(String(30))
    fournisseur_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("fournisseur.id"), index=True)
    objet: Mapped[str | None] = mapped_column(Text)
    perimetre: Mapped[str | None] = mapped_column(Text)
    reference_dossier: Mapped[str | None] = mapped_column(String(100))
    date_notification: Mapped[date | None]
    date_signature: Mapped[date | None]
    date_demarrage: Mapped[date | None]
    duree_mois: Mapped[int | None]
    date_echeance: Mapped[date | None]
    devise: Mapped[str] = mapped_column(String(3), default="XOF")
    montant_initial_ht: Mapped[Decimal] = mapped_column(MONTANT)
    taux_taxe: Mapped[Decimal] = mapped_column(MONTANT)
    montant_initial_ttc: Mapped[Decimal] = mapped_column(MONTANT)
    periodicite: Mapped[str | None] = mapped_column(String(20))
    modalite_facturation: Mapped[str | None] = mapped_column(String(500))
    site_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("site.id"))
    centre_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("centre_responsabilite.id"), index=True)
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("referentiel.id"))
    famille_achat_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("referentiel.id"))
    responsable_code: Mapped[str | None] = mapped_column(String(20))
    # Avance et retenue de garantie : conditions ; les montants se calculent (RG-14).
    taux_avance: Mapped[Decimal | None] = mapped_column(MONTANT)
    mode_recuperation_avance: Mapped[str | None] = mapped_column(String(300))
    taux_retenue_garantie: Mapped[Decimal | None] = mapped_column(MONTANT)
    condition_liberation_retenue: Mapped[str | None] = mapped_column(String(300))
    date_liberation_retenue: Mapped[date | None]
    statut: Mapped[str] = mapped_column(String(20), index=True)
    cree_par_id: Mapped[int] = mapped_column(BigInteger)
    cree_par_code: Mapped[str] = mapped_column(String(20))
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(default=1)

    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012


class ImputationContratModele(Base):
    """Ventilation du contrat sur une ligne budgétaire (RG-15)."""

    __tablename__ = "imputation_contrat"
    __table_args__ = (UniqueConstraint("contrat_id", "ligne_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    contrat_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contrat.id"), index=True)
    ligne_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ligne_budgetaire.id"), index=True)
    montant: Mapped[Decimal] = mapped_column(MONTANT)


class AvenantModele(Base):
    """Avenant : n'a d'effet sur le plafond qu'une fois validé (RG-11). Montant avant et nouveau
    plafond sont relevés au moment de la validation, pour l'historique."""

    __tablename__ = "avenant"
    __table_args__ = (UniqueConstraint("contrat_id", "numero"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    contrat_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contrat.id"), index=True)
    etablissement_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("etablissement.id"))
    numero: Mapped[int]
    objet: Mapped[str] = mapped_column(String(500))
    variation: Mapped[Decimal] = mapped_column(MONTANT)
    date_effet: Mapped[date]
    montant_avant: Mapped[Decimal | None] = mapped_column(MONTANT)
    nouveau_plafond: Mapped[Decimal | None] = mapped_column(MONTANT)
    statut: Mapped[str] = mapped_column(String(20), index=True)
    cree_par_id: Mapped[int] = mapped_column(BigInteger)
    cree_par_code: Mapped[str] = mapped_column(String(20))
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(default=1)

    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012


class EcheanceContratModele(Base):
    __tablename__ = "echeance_contrat"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    contrat_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contrat.id"), index=True)
    libelle: Mapped[str] = mapped_column(String(200))
    date_echeance: Mapped[date]
    montant_prevu: Mapped[Decimal] = mapped_column(MONTANT)


class LotTrancheModele(Base):
    __tablename__ = "lot_tranche"
    __table_args__ = (UniqueConstraint("contrat_id", "code"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    contrat_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contrat.id"), index=True)
    code: Mapped[str] = mapped_column(String(30))
    libelle: Mapped[str] = mapped_column(String(200))
    montant: Mapped[Decimal] = mapped_column(MONTANT)


class OrdreServiceModele(Base):
    __tablename__ = "ordre_service"
    __table_args__ = (UniqueConstraint("contrat_id", "reference"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    contrat_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contrat.id"), index=True)
    reference: Mapped[str] = mapped_column(String(50))
    type: Mapped[str] = mapped_column(String(20))
    date: Mapped[date]
    objet: Mapped[str | None] = mapped_column(String(500))


class RevisionPrixModele(Base):
    """Révision de prix : formule, indice, incidence (hors montant actualisé, section 6.2)."""

    __tablename__ = "revision_prix"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    contrat_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contrat.id"), index=True)
    formule: Mapped[str] = mapped_column(String(300))
    indice: Mapped[str | None] = mapped_column(String(100))
    date: Mapped[date]
    incidence: Mapped[Decimal] = mapped_column(MONTANT)


class EngagementModele(Base):
    """Engagement (section 7.4) ; une dépense hors marché en est un, d'origine HORS_MARCHE."""

    __tablename__ = "engagement"
    __table_args__ = (UniqueConstraint("etablissement_id", "numero"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    etablissement_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("etablissement.id"), index=True)
    exercice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("exercice.id"), index=True)
    numero: Mapped[str] = mapped_column(String(30))
    date_engagement: Mapped[date]
    objet: Mapped[str] = mapped_column(String(500))
    origine: Mapped[str] = mapped_column(String(20))
    montant: Mapped[Decimal] = mapped_column(MONTANT)
    contrat_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("contrat.id"), index=True)
    fournisseur_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("fournisseur.id"), index=True
    )
    centre_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("centre_responsabilite.id"))
    type_depense_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("referentiel.id"))
    # Engagement de report (EF-BUD-09) : engagement de l'exercice clos dont il reprend le reliquat.
    engagement_origine_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("engagement.id"))
    nature_hors_marche: Mapped[str | None] = mapped_column(String(30))
    justification: Mapped[str | None] = mapped_column(String(1000))
    reference_decision: Mapped[str | None] = mapped_column(String(100))
    statut: Mapped[str] = mapped_column(String(30), index=True)
    # Renseignée à la validation finale : l'engagement compte alors dans l'engagé (6.1).
    date_validation: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cree_par_id: Mapped[int] = mapped_column(BigInteger)
    cree_par_code: Mapped[str] = mapped_column(String(20))
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(default=1)

    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012


class ImputationEngagementModele(Base):
    __tablename__ = "imputation_engagement"
    __table_args__ = (UniqueConstraint("engagement_id", "ligne_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    engagement_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("engagement.id"), index=True)
    ligne_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ligne_budgetaire.id"), index=True)
    montant: Mapped[Decimal] = mapped_column(MONTANT)


class DerogationModele(Base):
    """Dérogation (RG-19) : couvre un dépassement d'une nature, sur un objet, jusqu'à un montant."""

    __tablename__ = "derogation"
    __table_args__ = (Index("ix_derogation_objet", "type_objet", "id_objet"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    type_objet: Mapped[str] = mapped_column(String(60))
    id_objet: Mapped[uuid.UUID]
    etablissement_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("etablissement.id"))
    nature: Mapped[str] = mapped_column(String(30))
    montant_depassement: Mapped[Decimal] = mapped_column(MONTANT)
    motif: Mapped[str] = mapped_column(String(500))
    statut: Mapped[str] = mapped_column(String(20))
    cree_par_id: Mapped[int] = mapped_column(BigInteger)
    cree_par_code: Mapped[str] = mapped_column(String(20))
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(default=1)

    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012


class AnnulationModele(Base):
    """Annulation (totale ou partielle) ou clôture d'une opération validée (RG-09, RG-18) :
    l'opération initiale reste intacte ; l'annulation est une contre-opération tracée."""

    __tablename__ = "annulation"
    __table_args__ = (Index("ix_annulation_objet", "type_objet", "id_objet"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    type_objet: Mapped[str] = mapped_column(String(60))
    id_objet: Mapped[uuid.UUID]
    etablissement_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("etablissement.id"))
    type: Mapped[str] = mapped_column(String(20))  # ANNULATION ou CLOTURE
    montant: Mapped[Decimal] = mapped_column(MONTANT)
    motif: Mapped[str] = mapped_column(String(500))
    utilisateur_id: Mapped[int] = mapped_column(BigInteger)
    code_agent: Mapped[str] = mapped_column(String(20))
    horodatage: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AnnulationLigneModele(Base):
    __tablename__ = "annulation_ligne"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    annulation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("annulation.id"), index=True)
    imputation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("imputation_engagement.id"), index=True
    )
    montant: Mapped[Decimal] = mapped_column(MONTANT)


QUANTITE = Numeric(18, 3)


class BonCommandeModele(Base):
    """Bon de commande, tranche ou ordre de service : toujours rattaché à un engagement validé."""

    __tablename__ = "bon_commande"
    __table_args__ = (UniqueConstraint("etablissement_id", "numero"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    etablissement_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("etablissement.id"), index=True)
    engagement_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("engagement.id"), index=True)
    fournisseur_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("fournisseur.id"))
    numero: Mapped[str] = mapped_column(String(30))
    type: Mapped[str] = mapped_column(String(20))
    date_emission: Mapped[date]
    lieu_livraison: Mapped[str | None] = mapped_column(String(300))
    date_livraison_prevue: Mapped[date | None]
    cree_par_id: Mapped[int] = mapped_column(BigInteger)
    cree_par_code: Mapped[str] = mapped_column(String(20))
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class LigneCommandeModele(Base):
    __tablename__ = "ligne_commande"
    __table_args__ = (UniqueConstraint("bon_commande_id", "rang"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    bon_commande_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bon_commande.id"), index=True)
    rang: Mapped[int]
    designation: Mapped[str] = mapped_column(String(300))
    quantite: Mapped[Decimal] = mapped_column(QUANTITE)
    prix_unitaire: Mapped[Decimal] = mapped_column(MONTANT)
    taux_taxe: Mapped[Decimal] = mapped_column(MONTANT)


class ReceptionModele(Base):
    """Réception d'une commande ; preuve du service fait une fois validée (EF-REC-05)."""

    __tablename__ = "reception"
    __table_args__ = (UniqueConstraint("etablissement_id", "numero"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    etablissement_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("etablissement.id"), index=True)
    bon_commande_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bon_commande.id"), index=True)
    numero: Mapped[str] = mapped_column(String(30))
    date_reception: Mapped[date]
    type: Mapped[str] = mapped_column(String(20))
    centre_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("centre_responsabilite.id"))
    agent_responsable_code: Mapped[str] = mapped_column(String(20))
    observations: Mapped[str | None] = mapped_column(String(1000))
    statut: Mapped[str] = mapped_column(String(20), index=True)
    cree_par_id: Mapped[int] = mapped_column(BigInteger)
    cree_par_code: Mapped[str] = mapped_column(String(20))
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(default=1)

    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012


class LigneReceptionModele(Base):
    __tablename__ = "ligne_reception"
    __table_args__ = (UniqueConstraint("reception_id", "ligne_commande_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    reception_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("reception.id"), index=True)
    ligne_commande_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ligne_commande.id"), index=True
    )
    quantite_recue: Mapped[Decimal] = mapped_column(QUANTITE)
    quantite_acceptee: Mapped[Decimal] = mapped_column(QUANTITE)
    quantite_rejetee: Mapped[Decimal] = mapped_column(QUANTITE)


class ReserveReceptionModele(Base):
    __tablename__ = "reserve_reception"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    reception_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("reception.id"), index=True)
    etablissement_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("etablissement.id"))
    description: Mapped[str] = mapped_column(String(1000))
    date_constat: Mapped[date]
    date_levee: Mapped[date | None]
    levee_par_code: Mapped[str | None] = mapped_column(String(20))


class AttestationServiceFaitModele(Base):
    __tablename__ = "attestation_service_fait"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    reception_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("reception.id"), unique=True)
    date: Mapped[date]
    livrable: Mapped[str] = mapped_column(String(500))
    conforme: Mapped[bool]
    cree_par_code: Mapped[str] = mapped_column(String(20))


class FactureModele(Base):
    """Facture du fournisseur, rattachée à un engagement (RG-05) ; un avoir est négatif."""

    __tablename__ = "facture"
    __table_args__ = (Index("ix_facture_fournisseur_numero", "fournisseur_id", "numero"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    etablissement_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("etablissement.id"), index=True)
    engagement_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("engagement.id"), index=True)
    fournisseur_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("fournisseur.id"))
    bon_commande_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("bon_commande.id"))
    facture_origine_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("facture.id"))
    numero: Mapped[str] = mapped_column(String(50))
    type: Mapped[str] = mapped_column(String(20))
    objet: Mapped[str] = mapped_column(String(500))
    date_emission: Mapped[date]
    date_reception: Mapped[date]
    date_echeance: Mapped[date | None]
    date_limite_traitement: Mapped[date | None]
    periode_rattachement: Mapped[str | None] = mapped_column(String(50))
    montant_ht: Mapped[Decimal] = mapped_column(MONTANT)
    montant_taxes: Mapped[Decimal] = mapped_column(MONTANT)
    montant_ttc: Mapped[Decimal] = mapped_column(MONTANT)
    numero_decompte: Mapped[int | None]
    statut: Mapped[str] = mapped_column(String(30), index=True)
    motif_statut: Mapped[str | None] = mapped_column(String(500))  # retour ou rejet
    motif_levee_doublon: Mapped[str | None] = mapped_column(String(500))
    cree_par_id: Mapped[int] = mapped_column(BigInteger)
    cree_par_code: Mapped[str] = mapped_column(String(20))
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(default=1)

    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012


class LiquidationModele(Base):
    """Liquidation d'une facture sur une seule imputation d'engagement (RG-17)."""

    __tablename__ = "liquidation"
    __table_args__ = (UniqueConstraint("etablissement_id", "numero"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    etablissement_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("etablissement.id"), index=True)
    facture_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("facture.id"), index=True)
    imputation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("imputation_engagement.id"), index=True
    )
    numero: Mapped[str] = mapped_column(String(30))
    date_liquidation: Mapped[date]
    montant_base: Mapped[Decimal] = mapped_column(MONTANT)
    observations: Mapped[str | None] = mapped_column(String(1000))
    statut: Mapped[str] = mapped_column(String(20), index=True)
    cree_par_id: Mapped[int] = mapped_column(BigInteger)
    cree_par_code: Mapped[str] = mapped_column(String(20))
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(default=1)

    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012


class DeductionModele(Base):
    __tablename__ = "deduction"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    liquidation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("liquidation.id"), index=True)
    type: Mapped[str] = mapped_column(String(30))
    montant: Mapped[Decimal] = mapped_column(MONTANT)
    taux: Mapped[Decimal | None] = mapped_column(MONTANT)
    motif: Mapped[str | None] = mapped_column(String(500))
    base_calcul: Mapped[str | None] = mapped_column(String(300))


class LiquidationReceptionModele(Base):
    """Réceptions qui prouvent le service fait d'une liquidation (RG-06)."""

    __tablename__ = "liquidation_reception"

    liquidation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("liquidation.id"), primary_key=True
    )
    reception_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("reception.id"), primary_key=True)


class RapprochementModele(Base):
    """Rapprochement commande / réception / facture / paiement d'une facture (section 9.1)."""

    __tablename__ = "rapprochement"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    facture_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("facture.id"), index=True)
    etablissement_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("etablissement.id"))
    date_rapprochement: Mapped[date]
    ecart_commande_reception: Mapped[Decimal] = mapped_column(MONTANT)
    ecart_reception_facture: Mapped[Decimal] = mapped_column(MONTANT)
    ecart_facture_paiement: Mapped[Decimal] = mapped_column(MONTANT)
    explication: Mapped[str | None] = mapped_column(String(1000))
    cree_par_code: Mapped[str] = mapped_column(String(20))
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class OrdonnancementModele(Base):
    """Dossier de liquidations transmis au comptable (EF-ORD-01, EF-ORD-02)."""

    __tablename__ = "ordonnancement"
    __table_args__ = (UniqueConstraint("etablissement_id", "reference_piece"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    etablissement_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("etablissement.id"), index=True)
    reference_piece: Mapped[str] = mapped_column(String(50))
    type_piece: Mapped[str] = mapped_column(String(20))
    service_destinataire: Mapped[str] = mapped_column(String(200))
    date_transmission: Mapped[date | None]
    statut: Mapped[str] = mapped_column(String(20), index=True)
    motif_statut: Mapped[str | None] = mapped_column(String(500))
    transmis_par_id: Mapped[int | None] = mapped_column(BigInteger)
    cree_par_id: Mapped[int] = mapped_column(BigInteger)
    cree_par_code: Mapped[str] = mapped_column(String(20))
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(default=1)

    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012


class LigneOrdonnancementModele(Base):
    """Une liquidation dans un ordonnancement ; l'historique des rejets est conservé (EF-ORD-03)."""

    __tablename__ = "ligne_ordonnancement"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    ordonnancement_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ordonnancement.id"), index=True
    )
    liquidation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("liquidation.id"), index=True)
    montant: Mapped[Decimal] = mapped_column(MONTANT)


class PaiementModele(Base):
    """Paiement d'un fournisseur, ventilé par liquidation (EF-PAI-01, EF-PAI-02)."""

    __tablename__ = "paiement"
    __table_args__ = (UniqueConstraint("etablissement_id", "numero"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    etablissement_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("etablissement.id"), index=True)
    fournisseur_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("fournisseur.id"), index=True)
    numero: Mapped[str] = mapped_column(String(30))
    date_paiement: Mapped[date]
    montant: Mapped[Decimal] = mapped_column(MONTANT)
    mode_reglement_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("referentiel.id"))
    compte_tresorerie_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("referentiel.id"))
    reference_transaction: Mapped[str | None] = mapped_column(String(100))
    piece_caisse: Mapped[str | None] = mapped_column(String(100))
    retenue_source: Mapped[Decimal] = mapped_column(MONTANT, default=0)
    statut: Mapped[str] = mapped_column(String(20), index=True)
    motif_annulation: Mapped[str | None] = mapped_column(String(500))
    cree_par_id: Mapped[int] = mapped_column(BigInteger)
    cree_par_code: Mapped[str] = mapped_column(String(20))
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(default=1)

    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012


class AllocationPaiementModele(Base):
    """Part d'un paiement affectée à une liquidation (section 17, point 12)."""

    __tablename__ = "allocation_paiement"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    paiement_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("paiement.id"), index=True)
    liquidation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("liquidation.id"), index=True)
    montant: Mapped[Decimal] = mapped_column(MONTANT)


# --- Lot 6 : alertes ---------------------------------------------------------------------------


class RegleAlerteModele(Base):
    """Règle d'alerte d'un établissement ; absente, la valeur par défaut s'applique (T-220)."""

    __tablename__ = "regle_alerte"

    etablissement_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("etablissement.id"), primary_key=True
    )
    type: Mapped[str] = mapped_column(String(40), primary_key=True)
    actif: Mapped[bool] = mapped_column(default=True)
    seuil_pourcent: Mapped[Decimal | None] = mapped_column(MONTANT)
    delai_jours: Mapped[int | None]
    notifier_par_email: Mapped[bool] = mapped_column(default=False)


class AlerteModele(Base):
    """Alerte créée par un contrôle, une tentative refusée ou la tâche planifiée (14.3)."""

    __tablename__ = "alerte"
    __table_args__ = (UniqueConstraint("type", "type_objet", "id_objet", "cle"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    etablissement_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("etablissement.id"), index=True)
    type: Mapped[str] = mapped_column(String(40), index=True)
    gravite: Mapped[str] = mapped_column(String(10))
    type_objet: Mapped[str] = mapped_column(String(40))
    id_objet: Mapped[uuid.UUID]
    cle: Mapped[str | None] = mapped_column(String(60))
    details: Mapped[Any] = mapped_column(JSONB)
    profils: Mapped[list[str]] = mapped_column(JSONB)
    code_agent: Mapped[str | None] = mapped_column(String(20))
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class LectureAlerteModele(Base):
    """Alerte lue par un agent : chaque destinataire a son propre état de lecture."""

    __tablename__ = "lecture_alerte"

    alerte_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("alerte.id"), primary_key=True)
    utilisateur_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    lue_le: Mapped[datetime] = mapped_column(DateTime(timezone=True))


# --- Lot 6 : clôture d'exercice ----------------------------------------------------------------


class ClotureExerciceModele(Base):
    """Clôture d'un exercice pour un établissement (EF-BUD-09) ; une réouverture motivée la
    lève sans l'effacer (T-240). L'exercice est ouvert pour l'établissement tant qu'aucune
    clôture n'est en vigueur."""

    __tablename__ = "cloture_exercice"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    exercice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("exercice.id"), index=True)
    etablissement_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("etablissement.id"), index=True)
    exercice_suivant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("exercice.id"))
    motif: Mapped[str] = mapped_column(String(500))
    engagements_reportes: Mapped[int]
    montant_reporte: Mapped[Decimal] = mapped_column(MONTANT)
    cree_par_code: Mapped[str] = mapped_column(String(20))
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reouvert_le: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reouvert_par_code: Mapped[str | None] = mapped_column(String(20))
    motif_reouverture: Mapped[str | None] = mapped_column(String(500))
