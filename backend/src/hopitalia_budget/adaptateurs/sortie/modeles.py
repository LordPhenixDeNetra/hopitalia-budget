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
