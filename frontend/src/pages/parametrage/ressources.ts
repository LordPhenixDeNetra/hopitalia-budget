/** Définitions des ressources servies par l'écran générique de paramétrage (lot 1). */

export type TypeChamp =
  'texte' | 'montant' | 'entier' | 'date' | 'choix' | 'choixMultiple' | 'reference'

export interface Champ {
  nom: string
  type: TypeChamp
  requis?: boolean
  /** Saisi à la création seulement (identifiants, rattachements). */
  creationSeulement?: boolean
  /** Valeurs possibles d'un champ « choix » (libellés : parametrage:valeurs.*). */
  valeurs?: string[]
  /** Ressource référencée d'un champ « reference » (chemin d'API, avec paramètres). */
  reference?: string
}

export interface DefinitionRessource {
  chemin: string
  colonnes: string[]
  tris: string[]
  champs: Champ[]
  /** Profils qui peuvent écrire (matrice des habilitations). */
  ecriture: string[]
  /** Lien de la première colonne vers une fiche. */
  fiche?: (id: string) => string
  /** La ressource a un champ « actif » : désactivation au lieu de suppression. */
  desactivable?: boolean
}

const CODE: Champ = { nom: 'code', type: 'texte', requis: true, creationSeulement: true }
const LIBELLE: Champ = { nom: 'libelle', type: 'texte', requis: true }
const ETABLISSEMENT: Champ = {
  nom: 'etablissementId',
  type: 'reference',
  reference: 'etablissements',
  requis: true,
  creationSeulement: true,
}
const ADM = ['ADM']

function simple(chemin: string, ...champs: Champ[]): DefinitionRessource {
  return {
    chemin,
    colonnes: ['code', 'libelle', ...champs.map((c) => c.nom), 'actif'],
    tris: ['code', 'libelle'],
    champs: [CODE, LIBELLE, ...champs],
    ecriture: ADM,
    desactivable: true,
  }
}

export const RESSOURCES: Record<string, DefinitionRessource> = {
  sites: {
    chemin: 'sites',
    colonnes: ['code', 'libelle', 'adresse', 'etablissementId', 'actif'],
    tris: ['code', 'libelle'],
    champs: [ETABLISSEMENT, CODE, LIBELLE, { nom: 'adresse', type: 'texte' }],
    ecriture: ADM,
    desactivable: true,
  },
  'centres-responsabilite': {
    chemin: 'centres-responsabilite',
    colonnes: ['code', 'libelle', 'type', 'parentId', 'etablissementId', 'actif'],
    tris: ['code', 'libelle'],
    champs: [
      ETABLISSEMENT,
      CODE,
      LIBELLE,
      {
        nom: 'type',
        type: 'choix',
        requis: true,
        valeurs: ['CLINIQUE', 'MEDICO_TECHNIQUE', 'ADMINISTRATIF', 'LOGISTIQUE', 'AUTRE'],
      },
      { nom: 'parentId', type: 'reference', reference: 'centres-responsabilite' },
      { nom: 'siteId', type: 'reference', reference: 'sites' },
      { nom: 'codeResponsable', type: 'texte' },
      { nom: 'codeHopitalia', type: 'texte', creationSeulement: true },
    ],
    ecriture: ADM,
    desactivable: true,
  },
  'sources-financement': simple(
    'sources-financement',
    {
      nom: 'typeFinancement',
      type: 'choix',
      requis: true,
      creationSeulement: true,
      valeurs: ['BUDGET_ETAT', 'RESSOURCES_PROPRES', 'BAILLEUR', 'AUTRE'],
    },
    { nom: 'bailleur', type: 'texte' },
  ),
  programmes: simple(
    'programmes',
    { nom: 'dateDebut', type: 'date' },
    { nom: 'dateFin', type: 'date' },
  ),
  'familles-achats': simple('familles-achats'),
  'types-depenses': simple('types-depenses', { nom: 'seuilHorsMarche', type: 'montant' }),
  'modes-reglement': simple('modes-reglement'),
  'comptes-tresorerie': simple(
    'comptes-tresorerie',
    {
      nom: 'typeCompte',
      type: 'choix',
      requis: true,
      creationSeulement: true,
      valeurs: ['BANQUE', 'CAISSE', 'TRESOR'],
    },
    { nom: 'numero', type: 'texte' },
  ),
  'types-pieces': simple(
    'types-pieces',
    { nom: 'dureeConservationAns', type: 'entier' },
    // Objets qui ne peuvent pas être validés sans une pièce de ce type (T-119).
    {
      nom: 'typesObjets',
      type: 'choixMultiple',
      valeurs: ['RevisionBudgetaire', 'Contrat', 'Avenant'],
    },
  ),
  fournisseurs: {
    chemin: 'fournisseurs',
    colonnes: ['code', 'raisonSociale', 'contact', 'codeHopitalia', 'actif'],
    tris: ['code', 'raisonSociale'],
    champs: [
      CODE,
      { nom: 'raisonSociale', type: 'texte', requis: true },
      { nom: 'identifiantsAdministratifs', type: 'texte' },
      { nom: 'adresse', type: 'texte' },
      { nom: 'contact', type: 'texte' },
      { nom: 'codeHopitalia', type: 'texte', creationSeulement: true },
    ],
    ecriture: ADM,
    desactivable: true,
  },
  exercices: {
    chemin: 'exercices',
    colonnes: ['code', 'dateOuverture', 'dateCloture', 'statut'],
    tris: ['code'],
    champs: [
      { nom: 'code', type: 'texte', requis: true, creationSeulement: true },
      { nom: 'dateOuverture', type: 'date', requis: true, creationSeulement: true },
      { nom: 'dateCloture', type: 'date', requis: true },
    ],
    ecriture: ADM,
  },
  budgets: {
    chemin: 'budgets',
    colonnes: ['reference', 'exerciceId', 'etablissementId', 'type'],
    tris: ['reference'],
    champs: [
      {
        nom: 'exerciceId',
        type: 'reference',
        reference: 'exercices',
        requis: true,
        creationSeulement: true,
      },
      ETABLISSEMENT,
      { nom: 'reference', type: 'texte', requis: true },
      {
        nom: 'type',
        type: 'choix',
        requis: true,
        creationSeulement: true,
        valeurs: ['PRIMITIF', 'MODIFICATIF'],
      },
    ],
    ecriture: ['RB'],
    fiche: (id) => `/budgets/${id}`,
  },
  'lignes-budgetaires': {
    chemin: 'lignes-budgetaires',
    colonnes: ['code', 'libelle', 'compteBudgetaireId', 'centreId', 'sourceId', 'dotationInitiale'],
    tris: ['code', 'libelle'],
    champs: [
      { nom: 'code', type: 'texte', requis: true, creationSeulement: true },
      LIBELLE,
      {
        nom: 'compteBudgetaireId',
        type: 'reference',
        reference: 'nomenclature?niveau=PARAGRAPHE',
        requis: true,
        creationSeulement: true,
      },
      {
        nom: 'centreId',
        type: 'reference',
        reference: 'centres-responsabilite',
        requis: true,
        creationSeulement: true,
      },
      {
        nom: 'sourceId',
        type: 'reference',
        reference: 'sources-financement',
        requis: true,
        creationSeulement: true,
      },
      { nom: 'programmeId', type: 'reference', reference: 'programmes', creationSeulement: true },
      { nom: 'natureEconomique', type: 'texte' },
      { nom: 'dotationInitiale', type: 'montant', requis: true, creationSeulement: true },
    ],
    ecriture: ['RB'],
    fiche: (id) => `/lignes-budgetaires/${id}`,
  },
}

/** Ressources affichées dans l'écran « Paramétrage », dans cet ordre. */
export const PARAMETRAGE = [
  'sites',
  'centres-responsabilite',
  'sources-financement',
  'programmes',
  'familles-achats',
  'types-depenses',
  'modes-reglement',
  'comptes-tresorerie',
  'types-pieces',
  'fournisseurs',
  'exercices',
  'circuits-validation',
]
