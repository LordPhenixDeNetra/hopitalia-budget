import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { afterEach, beforeAll, describe, expect, test, vi } from 'vitest'
import { jetons } from './auth/jetons'
import { BadgeStatut } from './composants/BadgeStatut'
import { Jauge } from './composants/Jauge'
import { versCsv } from './format/csv'
import { creerTheme } from './theme/theme'
import { Fournisseurs } from './Fournisseurs'
import i18n from './i18n'
import { routes } from './routes'

const MOI = {
  idHopitalia: 1,
  codeAgent: 'AG001',
  nom: 'Awa Diop',
  service: 'DAF',
  habilitations: [{ profil: 'ADM', etablissementId: null }],
  langue: null,
}

const ETABLISSEMENT = { id: 'a1', code: 'CHU-FANN', nom: 'CHU de Fann', actif: true, version: 1 }

const json = (corps: unknown, status = 200) =>
  new Response(JSON.stringify(corps), {
    status,
    headers: { 'Content-Type': status < 400 ? 'application/json' : 'application/problem+json' },
  })

function afficher(adresse: string) {
  const routeur = createMemoryRouter(routes, { initialEntries: [adresse] })
  return render(
    <Fournisseurs>
      <RouterProvider router={routeur} />
    </Fournisseurs>,
  )
}

beforeAll(async () => {
  await i18n.changeLanguage('fr')
  await i18n.loadNamespaces([
    'commun',
    'erreurs',
    'etablissements',
    'habilitations',
    'parametrage',
    'budget',
    'workflow',
    'contrats',
    'engagements',
    'commandes',
    'factures',
    'paiements',
    'tableaux',
    'alertes',
    'recherche',
    'cloture',
    'audit',
    'integrations',
  ])
})

afterEach(async () => {
  // Démonte d'abord, puis remet la langue : un test ne doit pas hériter de celle du précédent.
  cleanup()
  jetons.effacer()
  localStorage.clear()
  vi.unstubAllGlobals()
  await i18n.changeLanguage('fr')
})

describe('badge de statut (IHM-06)', () => {
  test('libellé et icône, pas seulement une couleur', () => {
    render(<BadgeStatut ton="succes" libelle="Actif" />)
    const badge = screen.getByText('Actif').closest('.ant-tag')
    expect(badge?.querySelector('svg')).not.toBeNull()
  })
})

describe('connexion et routage (T-065, T-069)', () => {
  test('lien profond sans session : renvoi vers la connexion', async () => {
    afficher('/etablissements/42')
    expect(await screen.findByRole('button', { name: 'Se connecter' })).toBeTruthy()
  })

  test('identifiants refusés : message traduit du code d’erreur', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(json({ code: 'IDENTIFIANTS_INVALIDES', status: 401 }, 401)),
    )
    afficher('/connexion')
    await userEvent.type(await screen.findByLabelText('Identifiant'), 'agent')
    await userEvent.type(screen.getByLabelText('Mot de passe'), 'faux')
    await userEvent.click(screen.getByRole('button', { name: 'Se connecter' }))
    expect(await screen.findByText('Identifiant ou mot de passe incorrect.')).toBeTruthy()
  })

  test('connexion réussie : retour à la page demandée', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        if (url.endsWith('/auth/connexion')) {
          return json({ jetonAcces: 'a', jetonRafraichissement: 'r', expireDans: 900 })
        }
        if (url.endsWith('/moi')) {
          return json({
            idHopitalia: 1,
            codeAgent: 'AG001',
            nom: 'Awa Diop',
            service: 'DAF',
            habilitations: [{ profil: 'ADM', etablissementId: null }],
            langue: null,
          })
        }
        return json({ donnees: [], pagination: { page: 1, taille: 25, total: 0, suivant: null } })
      }),
    )
    afficher('/connexion?retour=/')
    await userEvent.type(await screen.findByLabelText('Identifiant'), 'agent')
    await userEvent.type(screen.getByLabelText('Mot de passe'), 'secret')
    await userEvent.click(screen.getByRole('button', { name: 'Se connecter' }))
    expect(await screen.findByText('Bienvenue, Awa Diop')).toBeTruthy()
  })
})

/** Simule l'API : chaque route renvoie la réponse suivante de sa file, ou la dernière. */
function simulerApi(reponses: Record<string, Response[]>) {
  const appel = vi.fn(async (url: string, options?: RequestInit) => {
    const cle = `${options?.method ?? 'GET'} ${url.split('?')[0]}`
    const file = reponses[cle] ?? reponses[`* ${url.split('?')[0]}`]
    if (!file)
      return json({ donnees: [], pagination: { page: 1, taille: 25, total: 0, suivant: null } })
    return (file.length > 1 ? file.shift() : file[0])!.clone()
  })
  vi.stubGlobal('fetch', appel)
  return appel
}

describe('préférences et session (T-069, T-074, T-077)', () => {
  test('mouvement réduit : animations coupées dans le thème', () => {
    expect(creerTheme(true).token?.motion).toBe(false)
    expect(creerTheme(false).token?.motion).toBe(true)
  })

  test('la langue du profil est appliquée à la connexion', async () => {
    simulerApi({
      'POST /api/v1/auth/connexion': [
        json({ jetonAcces: 'a', jetonRafraichissement: 'r', expireDans: 900 }),
      ],
      'GET /api/v1/moi': [json({ ...MOI, langue: 'en' })],
    })
    afficher('/connexion?retour=/')
    await userEvent.type(await screen.findByLabelText('Identifiant'), 'agent')
    await userEvent.type(screen.getByLabelText('Mot de passe'), 'secret')
    await userEvent.click(screen.getByRole('button', { name: 'Se connecter' }))
    expect(await screen.findByText('Welcome, Awa Diop')).toBeTruthy()
  })

  test('session expirée : retour à la connexion avec un message', async () => {
    jetons.enregistrer('acces-expire', 'rafraichissement-refuse')
    simulerApi({
      'GET /api/v1/moi': [json({ code: 'JETON_INVALIDE', status: 401 }, 401)],
      'POST /api/v1/auth/rafraichissement': [json({ code: 'JETON_INVALIDE', status: 401 }, 401)],
    })
    afficher('/')
    expect(await screen.findByText('Votre session a expiré. Reconnectez-vous.')).toBeTruthy()
  })
})

describe('erreurs affichées dans la fiche (T-067, T-068)', () => {
  test('erreur de champ sous le champ, puis conflit 412 expliqué', async () => {
    jetons.enregistrer('acces', 'rafraichissement')
    simulerApi({
      'GET /api/v1/moi': [json(MOI)],
      'GET /api/v1/etablissements/a1': [json(ETABLISSEMENT)],
      'PATCH /api/v1/etablissements/a1': [
        json(
          {
            code: 'VALIDATION',
            status: 422,
            erreurs: [{ champ: 'nom', code: 'string_too_short' }],
          },
          422,
        ),
        json({ code: 'PRECONDITION_ECHOUEE', status: 412 }, 412),
      ],
    })
    afficher('/etablissements/a1')
    // Le premier « Enregistrer » est celui de la fiche ; le second, celui des paramètres de calcul.
    const [enregistrer] = await screen.findAllByRole('button', { name: 'Enregistrer' })
    await userEvent.click(enregistrer!)
    expect(await screen.findByText('Ce champ est trop court.')).toBeTruthy()
    await userEvent.click(enregistrer!)
    expect(await screen.findByText(/modifiée par quelqu'un d'autre/)).toBeTruthy()
  })
})

describe('gestion des habilitations (T-121)', () => {
  const HABILITATIONS = {
    donnees: [
      {
        id: 'h1',
        utilisateurId: 1,
        codeAgent: 'AG001',
        nomAgent: 'Awa Diop',
        profil: 'ADM',
        etablissementId: null,
      },
      {
        id: 'h2',
        utilisateurId: 10,
        codeAgent: 'AG010',
        nomAgent: 'Ibrahima Fall',
        profil: 'AF',
        etablissementId: null,
      },
    ],
    pagination: { page: 1, taille: 25, total: 2, suivant: null },
  }

  test('liste, ses propres droits protégés, attribution avec clé d’idempotence', async () => {
    jetons.enregistrer('acces', 'rafraichissement')
    const appel = simulerApi({
      'GET /api/v1/moi': [json(MOI)],
      'GET /api/v1/habilitations': [json(HABILITATIONS)],
      'POST /api/v1/habilitations': [
        json(
          {
            id: 'h3',
            utilisateurId: 3,
            codeAgent: 'AG003',
            nomAgent: 'Fatou Sarr',
            profil: 'REC',
            etablissementId: null,
          },
          201,
        ),
      ],
    })
    afficher('/habilitations')
    expect(await screen.findByText(/Ibrahima Fall/)).toBeTruthy()
    // Sa propre ligne n'a pas de bouton « Retirer » ; celle d'un autre agent en a un.
    expect(
      screen.getByText('Vos propres droits ne sont modifiables que par un autre administrateur.'),
    ).toBeTruthy()
    expect(screen.getAllByRole('button', { name: 'Retirer' })).toHaveLength(1)

    await userEvent.click(screen.getByRole('button', { name: /Attribuer un profil/ }))
    await userEvent.type(await screen.findByLabelText('Code agent Hopitalia'), 'AG003')
    await userEvent.click(within(screen.getByRole('dialog')).getByLabelText('Profil'))
    await userEvent.click(await screen.findByTitle('REC — Réceptionnaire'))
    await userEvent.click(screen.getByRole('button', { name: 'Enregistrer' }))
    expect(await screen.findByText('Profil Réceptionnaire attribué à Fatou Sarr.')).toBeTruthy()

    const envoi = appel.mock.calls.find(([, options]) => options?.method === 'POST')!
    expect(JSON.parse(String(envoi[1]!.body))).toEqual({
      codeAgent: 'AG003',
      profil: 'REC',
      etablissementId: null,
    })
    expect(new Headers(envoi[1]!.headers).get('Idempotency-Key')).toMatch(/[0-9a-f-]{36}/)
  })
})

describe('paramétrage et budget (lot 1)', () => {
  const page = (donnees: unknown[]) =>
    json({ donnees, pagination: { page: 1, taille: 25, total: donnees.length, suivant: null } })
  const BUDGET = {
    id: 'b1',
    reference: 'BP-2026',
    type: 'PRIMITIF',
    exerciceId: 'x1',
    etablissementId: 'a1',
    version: 1,
  }
  const ZERO = Object.fromEntries(
    [
      'budgetInitial',
      'modificationsPositives',
      'modificationsNegatives',
      'budgetRevise',
      'engage',
      'enCoursValidation',
      'disponibleApresEngagements',
      'disponiblePrevisionnel',
      'liquide',
      'paye',
      'engageRestantALiquider',
      'resteAPayer',
    ].map((c) => [c, '0.00']),
  )
  const SITUATION = json({ budgetId: 'b1', lignes: [], totaux: ZERO })
  const REVISION = {
    id: 'r1',
    budgetId: 'b1',
    etablissementId: 'a1',
    type: 'VIREMENT',
    sens: null,
    ligneSourceId: 'l1',
    ligneCibleId: 'l2',
    montant: '5000000.00',
    motif: 'Besoin urgent',
    statut: 'SOUMISE',
    creeParCode: 'AG002',
    creeLe: '2026-03-01T10:00:00Z',
    version: 1,
  }

  test('création d’un exercice : formulaire générique, clé d’idempotence (T-087)', async () => {
    jetons.enregistrer('acces', 'rafraichissement')
    const appel = simulerApi({
      'GET /api/v1/moi': [json(MOI)],
      'POST /api/v1/exercices': [json({ id: 'x1', code: '2026' }, 201)],
    })
    afficher('/parametrage/exercices')
    await userEvent.click(await screen.findByRole('button', { name: /Ajouter/ }))
    const dialogue = await screen.findByRole('dialog')
    await userEvent.type(within(dialogue).getByLabelText('Code'), '2026')
    await userEvent.type(within(dialogue).getByLabelText('Ouverture'), '2026-01-01')
    await userEvent.type(within(dialogue).getByLabelText('Clôture'), '2026-12-31')
    await userEvent.click(within(dialogue).getByRole('button', { name: 'Enregistrer' }))
    expect(await screen.findByText('Élément ajouté.')).toBeTruthy()

    const envoi = appel.mock.calls.find(([, options]) => options?.method === 'POST')!
    expect(JSON.parse(String(envoi[1]!.body))).toEqual({
      code: '2026',
      dateOuverture: '2026-01-01',
      dateCloture: '2026-12-31',
    })
    expect(new Headers(envoi[1]!.headers).get('Idempotency-Key')).toMatch(/[0-9a-f-]{36}/)
  })

  test('import des dotations : envoi CSV brut, suivi, anomalies traduites (T-089)', async () => {
    jetons.enregistrer('acces', 'rafraichissement')
    const travail = {
      id: 'i1',
      budgetId: 'b1',
      lignesImportees: 2,
      anomalies: [],
      creeLe: '2026-01-05T10:00:00Z',
      termineLe: null,
    }
    const appel = simulerApi({
      'GET /api/v1/moi': [
        json({ ...MOI, habilitations: [{ profil: 'RB', etablissementId: 'a1' }] }),
      ],
      'GET /api/v1/budgets/b1': [json(BUDGET)],
      'GET /api/v1/budgets/b1/situation': [SITUATION],
      'POST /api/v1/budgets/b1/imports': [json({ ...travail, statut: 'EN_COURS' }, 202)],
      'GET /api/v1/imports-dotations/i1': [
        json({
          ...travail,
          statut: 'TERMINE',
          anomalies: [{ ligne: 4, code: 'COMPTE_INCONNU', valeur: '999' }],
        }),
      ],
    })
    afficher('/budgets/b1')
    await userEvent.click(await screen.findByRole('tab', { name: 'Import des dotations' }))
    const csv = new File(
      ['code;libelle;compte;centre;source;programme;dotation\n'],
      'dotations.csv',
      {
        type: 'text/csv',
      },
    )
    const champ = document.querySelector('input[type=file]') as HTMLInputElement
    await userEvent.upload(champ, csv)
    expect(await screen.findByText('Compte budgétaire inconnu')).toBeTruthy()
    expect(screen.getByText('Lignes importées : 2')).toBeTruthy()

    const envoi = appel.mock.calls.find(([, options]) => options?.method === 'POST')!
    expect(new Headers(envoi[1]!.headers).get('Content-Type')).toBe('text/csv')
    expect(String(envoi[1]!.body)).toMatch(/^code;libelle/)
  })

  const ETAT = {
    statut: 'SOUMISE',
    separationTaches: true,
    etapes: [
      { ordre: 1, libelle: 'Visa DAF', profil: 'VAL', obligatoire: true },
      { ordre: 2, libelle: 'Ordonnateur', profil: 'ORD', obligatoire: true },
    ],
    visas: [],
    etapesOuvertes: [1],
    peutDecider: true,
  }
  const VISA = {
    ordre: 1,
    etape: 'VAL',
    decision: 'A_CORRIGER',
    motif: 'Montant à revoir',
    visa: null,
    codeAgent: 'AG003',
    delegantCode: null,
    horodatage: '2026-03-02T10:00:00Z',
  }

  async function ouvrirRevision(profil: string, etat: object) {
    jetons.enregistrer('acces', 'rafraichissement')
    const appel = simulerApi({
      'GET /api/v1/moi': [json({ ...MOI, habilitations: [{ profil, etablissementId: 'a1' }] })],
      'GET /api/v1/budgets/b1': [json(BUDGET)],
      'GET /api/v1/budgets/b1/situation': [SITUATION],
      'GET /api/v1/revisions-budgetaires': [page([REVISION])],
      'GET /api/v1/revisions-budgetaires/r1/validations': [json(etat)],
      'GET /api/v1/revisions-budgetaires/r1/pieces': [json([])],
      'POST /api/v1/revisions-budgetaires/r1/validations': [
        json({ ...etat, statut: 'A_CORRIGER', visas: [VISA], peutDecider: false }, 201),
      ],
    })
    afficher('/budgets/b1')
    await userEvent.click(await screen.findByRole('tab', { name: 'Révisions' }))
    await userEvent.click(await screen.findByRole('button', { name: 'Détail' }))
    return appel
  }

  test('révision : circuit, visa et retour motivé dans la fiche (T-113, T-120)', async () => {
    const appel = await ouvrirRevision('VAL', ETAT)
    expect(await screen.findByText('Visa DAF')).toBeTruthy()
    // Le profil VAL ne peut pas demander de révision (réservé au RB).
    expect(screen.queryByRole('button', { name: 'Demander une révision' })).toBeNull()
    await userEvent.click(screen.getByRole('button', { name: 'Retourner pour correction' }))
    await userEvent.type(await screen.findByLabelText('Motif'), 'Montant à revoir')
    const dialogue = screen.getAllByRole('dialog').at(-1)!
    await userEvent.click(
      within(dialogue).getByRole('button', { name: 'Retourner pour correction' }),
    )
    expect(await screen.findByText('Décision enregistrée.')).toBeTruthy()
    expect(await screen.findByText(/Retour pour correction — AG003/)).toBeTruthy()

    const envoi = appel.mock.calls.find(([, options]) => options?.method === 'POST')!
    expect(JSON.parse(String(envoi[1]!.body))).toEqual({
      decision: 'A_CORRIGER',
      motif: 'Montant à revoir',
    })
  })

  test('révision : aucun bouton de décision si le serveur le refuse (RG-13)', async () => {
    await ouvrirRevision('ORD', { ...ETAT, peutDecider: false })
    expect(await screen.findByText('Visa DAF')).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Viser' })).toBeNull()
  })

  test('délégation : création avec clé d’idempotence (T-115)', async () => {
    jetons.enregistrer('acces', 'rafraichissement')
    const appel = simulerApi({
      'GET /api/v1/moi': [
        json({ ...MOI, habilitations: [{ profil: 'ORD', etablissementId: 'a1' }] }),
      ],
      'POST /api/v1/delegations': [
        json(
          {
            id: 'd1',
            delegantCode: 'AG001',
            delegataireCode: 'AG009',
            dateDebut: '2026-11-14',
            dateFin: '2026-11-20',
            motif: 'Congés',
            version: 1,
          },
          201,
        ),
      ],
    })
    afficher('/delegations')
    await userEvent.type(await screen.findByLabelText('Code agent du délégataire'), 'AG009')
    await userEvent.type(screen.getByLabelText('Au'), '2026-11-20')
    await userEvent.type(screen.getByLabelText('Motif'), 'Congés')
    await userEvent.click(screen.getByRole('button', { name: 'Déléguer' }))
    expect(await screen.findByText('Délégation enregistrée.')).toBeTruthy()

    const envoi = appel.mock.calls.find(([, options]) => options?.method === 'POST')!
    expect(JSON.parse(String(envoi[1]!.body))).toMatchObject({
      delegataireCode: 'AG009',
      dateFin: '2026-11-20',
      motif: 'Congés',
    })
    expect(new Headers(envoi[1]!.headers).get('Idempotency-Key')).toMatch(/[0-9a-f-]{36}/)
  })
})

describe('contrats et marchés (lot 2)', () => {
  const GMC = { ...MOI, habilitations: [{ profil: 'GMC', etablissementId: 'a1' }] }
  const RESUME = {
    id: 'c1',
    etablissementId: 'a1',
    type: 'MARCHE',
    numero: 'M-2026-001',
    intitule: 'Fournitures médicales',
    fournisseurId: 'f1',
    fournisseur: 'Pharma Test SA',
    centreId: 'ce1',
    statut: 'VALIDE',
    dateSignature: '2026-01-05',
    dateEcheance: '2026-12-31',
    montantActualise: '100000000.00',
    engage: '80000000.00',
    tauxConsommation: '80.00',
  }
  const CONTRAT = {
    ...RESUME,
    nature: 'FOURNITURES',
    numeroLot: '1',
    objet: null,
    perimetre: null,
    referenceDossier: null,
    dateNotification: null,
    dateDemarrage: null,
    dureeMois: null,
    devise: 'XOF',
    montantInitialHt: '100000000.00',
    tauxTaxe: '0.00',
    montantInitialTtc: '100000000.00',
    periodicite: null,
    modaliteFacturation: null,
    siteId: null,
    sourceId: 's1',
    familleAchatId: null,
    responsableCode: null,
    tauxAvance: null,
    modeRecuperationAvance: null,
    tauxRetenueGarantie: null,
    conditionLiberationRetenue: null,
    dateLiberationRetenue: null,
    statut: 'BROUILLON',
    creeParCode: 'AG011',
    creeLe: '2026-01-05T10:00:00Z',
    version: 1,
    imputations: [{ id: 'i1', ligneId: 'l1', montant: '100000000.00' }],
  }

  test('liste : consommation lisible et filtre transmis à l’API (T-138)', async () => {
    jetons.enregistrer('acces', 'rafraichissement')
    const appel = simulerApi({
      'GET /api/v1/moi': [json(GMC)],
      'GET /api/v1/contrats': [
        json({ donnees: [RESUME], pagination: { page: 1, taille: 25, total: 1, suivant: null } }),
      ],
    })
    afficher('/contrats?type=MARCHE')
    expect(await screen.findByText('Pharma Test SA')).toBeTruthy()
    // Taux écrit en clair, pas seulement par la longueur ou la couleur de la barre (IHM-06).
    expect(screen.getByText('80.00 %')).toBeTruthy()
    const liste = appel.mock.calls.find(([url]) => String(url).startsWith('/api/v1/contrats'))!
    expect(String(liste[0])).toContain('type=MARCHE')
  })

  test('fiche : brouillon soumis au circuit, avenants réservés au contrat validé', async () => {
    jetons.enregistrer('acces', 'rafraichissement')
    const appel = simulerApi({
      'GET /api/v1/moi': [json(GMC)],
      'GET /api/v1/contrats/c1': [json(CONTRAT)],
      'GET /api/v1/contrats/c1/synthese': [
        json({
          contratId: 'c1',
          montantInitial: '100000000.00',
          montantActualise: '100000000.00',
          tauxConsommation: '0.00',
        }),
      ],
      'GET /api/v1/contrats/c1/avenants': [json([])],
      'POST /api/v1/contrats/c1/soumissions': [json({ statut: 'SOUMIS' }, 201)],
    })
    afficher('/contrats/c1')
    expect(await screen.findByText('Montant contractuel actualisé')).toBeTruthy()
    await userEvent.click(screen.getByRole('tab', { name: 'Avenants' }))
    expect(await screen.findByText('Les avenants portent sur un contrat validé.')).toBeTruthy()
    await userEvent.click(screen.getByRole('button', { name: 'Soumettre au circuit' }))
    expect(await screen.findByText('Contrat soumis au circuit.')).toBeTruthy()
    expect(
      appel.mock.calls.some(
        ([url, o]) => url === '/api/v1/contrats/c1/soumissions' && o?.method === 'POST',
      ),
    ).toBe(true)
  })
})

describe('engagements (lot 2)', () => {
  const GMC = { ...MOI, habilitations: [{ profil: 'GMC', etablissementId: 'a1' }] }
  const ENGAGEMENT = {
    id: 'e1',
    etablissementId: 'a1',
    exerciceId: 'x1',
    numero: 'ENG-2026-00001',
    dateEngagement: '2026-03-01',
    objet: 'Médicaments',
    origine: 'CONTRAT',
    montant: '30000000.00',
    montantAnnule: '0.00',
    contratId: 'c1',
    fournisseurId: 'f1',
    centreId: 'ce1',
    typeDepenseId: null,
    natureHorsMarche: null,
    justification: null,
    referenceDecision: null,
    statut: 'BROUILLON',
    dateValidation: null,
    creeParCode: 'AG011',
    creeLe: '2026-03-01T10:00:00Z',
    version: 1,
    imputations: [{ id: 'i1', ligneId: 'l1', montant: '30000000.00', annule: '0.00' }],
  }

  test('contrôles : écart lisible, dérogation demandée pour son montant (T-118, T-150)', async () => {
    jetons.enregistrer('acces', 'rafraichissement')
    const appel = simulerApi({
      'GET /api/v1/moi': [json(GMC)],
      'GET /api/v1/engagements/e1': [json(ENGAGEMENT)],
      'GET /api/v1/engagements/e1/controles': [
        json([
          {
            code: 'PLAFOND_DEPASSE',
            nature: 'PLAFOND_CONTRAT',
            depassement: '10000000.00',
            details: { resteAEngager: '20000000.00' },
            leve: false,
          },
          {
            code: 'FOURNISSEUR_INCOHERENT',
            nature: null,
            depassement: '0.00',
            details: {},
            leve: false,
          },
        ]),
      ],
      'GET /api/v1/engagements/e1/derogations': [json([])],
      'POST /api/v1/engagements/e1/derogations': [json({ id: 'd1' }, 201)],
    })
    afficher('/engagements/e1')
    await userEvent.click(await screen.findByRole('tab', { name: 'Contrôles' }))
    expect(await screen.findByText('Plafond du marché dépassé')).toBeTruthy()
    // L'état est écrit en clair, pas signalé par la seule couleur (IHM-06).
    expect(screen.getByText('Non dérogeable : à corriger')).toBeTruthy()
    expect(screen.getByText('Reste à engager : 20000000.00')).toBeTruthy()
    await userEvent.click(screen.getByRole('button', { name: 'Demander une dérogation' }))
    const dialogue = await screen.findByRole('dialog')
    await userEvent.type(within(dialogue).getByLabelText('Motif'), 'Avenant en cours')
    await userEvent.click(within(dialogue).getByRole('button', { name: 'Enregistrer' }))
    expect(await screen.findByText('Dérogation demandée et soumise au circuit.')).toBeTruthy()

    const envoi = appel.mock.calls.find(([, o]) => o?.method === 'POST')!
    expect(JSON.parse(String(envoi[1]!.body))).toEqual({
      montantDepassement: '10000000.00',
      motif: 'Avenant en cours',
      nature: 'PLAFOND_CONTRAT',
    })
  })
})

describe('commandes et réceptions (lot 3)', () => {
  test('suivi : commandes en retard et réserves à lever (T-166, T-163)', async () => {
    jetons.enregistrer('acces', 'rafraichissement')
    const appel = simulerApi({
      'GET /api/v1/moi': [json(MOI)],
      'GET /api/v1/bons-commande': [
        json({
          donnees: [
            {
              id: 'b1',
              numero: 'BC-2026-00001',
              type: 'BON_COMMANDE',
              dateEmission: '2026-03-05',
              dateLivraisonPrevue: '2026-04-30',
              montantTtc: '10000000.00',
              enRetard: true,
              lignes: [],
            },
          ],
          pagination: { page: 1, taille: 100, total: 1, suivant: null },
        }),
      ],
      'GET /api/v1/reserves': [
        json([
          {
            id: 'rs1',
            receptionId: 'r1',
            description: 'Cartons abîmés',
            dateConstat: '2026-04-10',
            dateLevee: null,
            leveeParCode: null,
          },
        ]),
      ],
    })
    afficher('/commandes')
    // Retard écrit en clair, pas seulement par la couleur (IHM-06).
    expect(await screen.findByText('En retard')).toBeTruthy()
    expect(await screen.findByText('Cartons abîmés')).toBeTruthy()
    await userEvent.click(screen.getByRole('switch', { name: 'En retard seulement' }))
    const urls = appel.mock.calls.map(([url]) => String(url))
    expect(
      urls.some((u) => u.startsWith('/api/v1/bons-commande') && u.includes('enRetard=true')),
    ).toBe(true)
    expect(urls.some((u) => u.includes('/api/v1/reserves?nonLevees=true'))).toBe(true)
  })
})

describe('factures et liquidations (lot 4)', () => {
  const AF = { ...MOI, habilitations: [{ profil: 'AF', etablissementId: 'a1' }] }
  const FACTURE = {
    id: 'f1',
    etablissementId: 'a1',
    engagementId: 'e1',
    fournisseurId: 'fo1',
    bonCommandeId: null,
    factureOrigineId: null,
    numero: 'FA-778',
    type: 'PARTIELLE',
    objet: 'Livraison de mars',
    dateEmission: '2026-04-01',
    dateReception: '2026-04-03',
    dateEcheance: null,
    dateLimiteTraitement: null,
    periodeRattachement: null,
    montantHt: '6000000.00',
    montantTaxes: '0.00',
    montantTtc: '6000000.00',
    numeroDecompte: null,
    montantCumuleDecomptes: null,
    liquideValide: '0.00',
    resteAPayer: '6000000.00',
    statut: 'EN_CONTROLE',
    motifStatut: null,
    motifLeveeDoublon: null,
    creeParCode: 'AG020',
    creeLe: '2026-04-03T10:00:00Z',
    version: 1,
  }
  const LIQUIDATION = {
    id: 'l1',
    factureId: 'f1',
    imputationId: 'i1',
    numero: 'LIQ-2026-00001',
    dateLiquidation: '2026-04-05',
    montantBase: '6000000.00',
    montantLiquide: '6000000.00',
    deductionsTotal: '300000.00',
    netAPayer: '5700000.00',
    consommationBudgetaire: '6000000.00',
    observations: null,
    statut: 'BROUILLON',
    receptionIds: [],
    deductions: [
      { type: 'RETENUE_GARANTIE', montant: '300000.00', taux: '5', motif: null, baseCalcul: null },
    ],
    creeParCode: 'AG020',
    creeLe: '2026-04-05T10:00:00Z',
    version: 1,
  }

  test('liquidation : alerte et écart bloquant distingués, dérogation demandée (T-177, T-178)', async () => {
    jetons.enregistrer('acces', 'rafraichissement')
    const appel = simulerApi({
      'GET /api/v1/moi': [json(AF)],
      'GET /api/v1/factures/f1': [json(FACTURE)],
      'GET /api/v1/factures/f1/liquidations': [json([LIQUIDATION])],
      'GET /api/v1/engagements/e1': [
        json({ imputations: [{ id: 'i1', ligneId: 'l1', montant: '9000000.00', annule: '0.00' }] }),
      ],
      'GET /api/v1/liquidations/l1/controles': [
        json([
          {
            code: 'LIQUIDATION_SUP_DU',
            nature: 'LIQUIDATION_SUP_DU',
            depassement: '1000000.00',
            details: { resteDu: '5000000.00' },
            leve: false,
            bloquant: true,
          },
          {
            code: 'FACTURE_SUP_RECEPTION',
            nature: null,
            depassement: '500000.00',
            details: {},
            leve: false,
            bloquant: false,
          },
        ]),
      ],
      'GET /api/v1/liquidations/l1/validations': [
        json({
          statut: 'BROUILLON',
          separationTaches: true,
          etapes: [],
          visas: [],
          etapesOuvertes: [],
          peutDecider: false,
        }),
      ],
      'GET /api/v1/liquidations/l1/pieces': [json([])],
      'POST /api/v1/liquidations/l1/derogations': [json({ id: 'd1' }, 201)],
    })
    afficher('/factures/f1')
    await userEvent.click(await screen.findByRole('tab', { name: 'Liquidations' }))
    await userEvent.click(await screen.findByRole('button', { name: 'Détail' }))
    // Montants de la formule 6.3 et états écrits en clair (IHM-06).
    expect(await screen.findByText('Au-delà du reste dû')).toBeTruthy()
    expect(screen.getByText('Bloquant')).toBeTruthy()
    expect(screen.getByText('Alerte')).toBeTruthy()
    expect(screen.getByText('Reste dû : 5000000.00')).toBeTruthy()
    await userEvent.click(screen.getByRole('button', { name: 'Demander une dérogation' }))
    // La demande s'ouvre par-dessus le tiroir de la liquidation : dernier dialogue.
    const dialogue = (await screen.findAllByRole('dialog')).at(-1)!
    expect(within(dialogue).getByText(/Liquidation supérieure au dû/)).toBeTruthy()
    await userEvent.type(within(dialogue).getByLabelText('Motif'), 'Révision de prix')
    await userEvent.click(within(dialogue).getByRole('button', { name: 'Enregistrer' }))
    expect(await screen.findByText('Dérogation demandée et soumise au circuit.')).toBeTruthy()

    const envoi = appel.mock.calls.find(([, o]) => o?.method === 'POST')!
    expect(JSON.parse(String(envoi[1]!.body))).toEqual({
      montantDepassement: '1000000.00',
      motif: 'Révision de prix',
      nature: 'LIQUIDATION_SUP_DU',
    })
  })

  test('rejet motivé d’une facture (REC-12)', async () => {
    jetons.enregistrer('acces', 'rafraichissement')
    const appel = simulerApi({
      'GET /api/v1/moi': [json(AF)],
      'GET /api/v1/factures/f1': [json(FACTURE)],
      'POST /api/v1/factures/f1/rejets': [
        json({ ...FACTURE, statut: 'REJETEE', motifStatut: 'Prix non conformes' }, 201),
      ],
    })
    afficher('/factures/f1')
    await userEvent.click(await screen.findByRole('button', { name: 'Rejeter' }))
    const dialogue = await screen.findByRole('dialog')
    await userEvent.type(within(dialogue).getByLabelText('Motif'), 'Prix non conformes')
    await userEvent.click(within(dialogue).getByRole('button', { name: 'Enregistrer' }))
    expect(await screen.findByText('Facture rejetée.')).toBeTruthy()
    expect(await screen.findByText('Rejetée')).toBeTruthy()
    const envoi = appel.mock.calls.find(([, o]) => o?.method === 'POST')!
    expect(JSON.parse(String(envoi[1]!.body))).toEqual({ motif: 'Prix non conformes' })
  })
})

describe('ordonnancement et paiements (lot 5)', () => {
  const CPT = { ...MOI, habilitations: [{ profil: 'CPT', etablissementId: 'a1' }] }
  const page = (donnees: unknown[]) => ({
    donnees,
    pagination: { page: 1, taille: 100, total: donnees.length, suivant: null },
  })
  const ORDONNANCEMENT = {
    id: 'o1',
    etablissementId: 'a1',
    referencePiece: 'MD-2026-014',
    typePiece: 'MANDAT',
    serviceDestinataire: 'Agence comptable',
    dateTransmission: '2026-05-02',
    statut: 'TRANSMIS',
    motifStatut: null,
    montant: '6000000.00',
    lignes: [
      {
        liquidationId: 'l1',
        liquidationNumero: 'LIQ-2026-00001',
        factureId: 'f1',
        factureNumero: 'FA-778',
        montant: '6000000.00',
      },
    ],
    creeParCode: 'AG030',
    creeLe: '2026-05-01T10:00:00Z',
    version: 2,
  }

  test('le comptable répond à un ordonnancement transmis, motif exigé pour un rejet (T-186)', async () => {
    jetons.enregistrer('acces', 'rafraichissement')
    const appel = simulerApi({
      'GET /api/v1/moi': [json(CPT)],
      'GET /api/v1/ordonnancements': [json(page([ORDONNANCEMENT]))],
      'POST /api/v1/ordonnancements/o1/decisions': [
        json({ ...ORDONNANCEMENT, statut: 'REJETE', motifStatut: 'Mandat non signé' }, 201),
      ],
    })
    afficher('/paiements')
    await userEvent.click(await screen.findByRole('button', { name: 'Détail' }, { timeout: 5000 }))
    // Réponses du comptable seulement : la transmission revient à l'ordonnateur.
    expect(await screen.findByRole('button', { name: 'Prendre en charge' })).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Transmettre au comptable' })).toBeNull()
    await userEvent.click(screen.getByRole('button', { name: 'Rejeter' }))
    const dialogue = (await screen.findAllByRole('dialog')).at(-1)!
    await userEvent.type(within(dialogue).getByLabelText('Motif'), 'Mandat non signé')
    await userEvent.click(within(dialogue).getByRole('button', { name: 'Enregistrer' }))
    expect(await screen.findByText('Décision enregistrée.')).toBeTruthy()
    const envoi = appel.mock.calls.find(([, o]) => o?.method === 'POST')!
    expect(JSON.parse(String(envoi[1]!.body))).toEqual({
      action: 'REJETER',
      motif: 'Mandat non signé',
    })
  })

  test('paiement groupé : ventilation par liquidation, montant égal à la somme exacte (T-188)', async () => {
    jetons.enregistrer('acces', 'rafraichissement')
    const appel = simulerApi({
      'GET /api/v1/moi': [json(CPT)],
      'GET /api/v1/fournisseurs': [
        json(page([{ id: 'fo1', code: 'F01', raisonSociale: 'Medipharm' }])),
      ],
      'GET /api/v1/modes-reglement': [
        json(page([{ id: 'vir', code: 'VIR', libelle: 'Virement' }])),
      ],
      'GET /api/v1/comptes-tresorerie': [
        json(page([{ id: 'bq', code: 'BQ1', libelle: 'Banque' }])),
      ],
      'GET /api/v1/liquidations': [
        json(
          ['1', '2'].map((n) => ({
            id: `l${n}`,
            numero: `LIQ-2026-0000${n}`,
            factureId: `f${n}`,
            factureNumero: `FA-77${n}`,
            fournisseurId: 'fo1',
            netAPayer: '6000000.00',
            paye: '0.00',
            resteAPayer: '6000000.00',
            ordonnancementId: 'o1',
          })),
        ),
      ],
      'POST /api/v1/paiements': [json({ id: 'p1' }, 201)],
    })
    afficher('/paiements')
    await userEvent.click(await screen.findByRole('tab', { name: 'Paiements' }, { timeout: 5000 }))
    await userEvent.click(await screen.findByRole('button', { name: 'Enregistrer un paiement' }))
    const tiroir = await screen.findByRole('dialog')
    await userEvent.click(within(tiroir).getByLabelText('Bénéficiaire'))
    await userEvent.click(await screen.findByTitle('F01 — Medipharm'))
    await userEvent.type(await within(tiroir).findByLabelText('Part payée — LIQ-2026-00001'), '0.1')
    await userEvent.type(within(tiroir).getByLabelText('Part payée — LIQ-2026-00002'), '0.2')
    // Somme exacte, sans flottant : 0,3 et non 0,30000000000000004.
    expect(within(tiroir).getByText(/0,3(?!\d)/)).toBeTruthy()
    fireEvent.change(within(tiroir).getByLabelText('Date du paiement'), {
      target: { value: '2026-05-10' },
    })
    await userEvent.click(within(tiroir).getByLabelText('Mode de règlement'))
    await userEvent.click(await screen.findByTitle('VIR — Virement'))
    await userEvent.click(within(tiroir).getByLabelText('Compte de trésorerie'))
    await userEvent.click(await screen.findByTitle('BQ1 — Banque'))
    await userEvent.click(within(tiroir).getByRole('button', { name: 'Enregistrer' }))
    expect(await screen.findByText('Paiement enregistré.')).toBeTruthy()
    const envoi = appel.mock.calls.find(([, o]) => o?.method === 'POST')!
    expect(JSON.parse(String(envoi[1]!.body))).toMatchObject({
      montant: '0.30',
      allocations: [
        { liquidationId: 'l1', montant: '0.1' },
        { liquidationId: 'l2', montant: '0.2' },
      ],
    })
    expect(new Headers(envoi[1]!.headers).get('Idempotency-Key')).toBeTruthy()
  })
})

describe('périmètre du module (REC-15, RG-12)', () => {
  test('aucun écran ni menu de lancement, passation ou attribution de marché', async () => {
    const chemins: string[] = []
    const parcourir = (liste: typeof routes) =>
      liste.forEach((r) => {
        if (r.path) chemins.push(r.path)
        if (r.children) parcourir(r.children)
      })
    parcourir(routes)
    expect(chemins).toContain('contrats')
    const commun = (await import('./i18n/locales/fr/commun.json')).default
    const textes = [...chemins, ...Object.values(commun.menu)].map((t) => String(t).toLowerCase())
    const passation = /passation|appel.d.offres?|attribution|adjudication|soumissionnaire|lancement/
    expect(textes.filter((t) => passation.test(t))).toEqual([])
  })
})

describe('tableaux de bord (lot 6)', () => {
  test('jauge : taux et seuil écrits en clair, repères 80/90/100 % (T-213, IHM-06, IHM-10)', () => {
    const { rerender } = render(<Jauge libelle="604-MED" taux="85.5" />)
    expect(screen.getByText('85,5 %')).toBeTruthy()
    expect(screen.getByText('Seuil de 80 % atteint')).toBeTruthy()
    expect(screen.getByRole('meter', { name: '604-MED' }).getAttribute('aria-valuetext')).toBe(
      '85,5 % — Seuil de 80 % atteint',
    )
    rerender(<Jauge libelle="604-MED" taux="112" />)
    expect(screen.getByText('100 % atteints ou dépassés')).toBeTruthy()
    rerender(<Jauge libelle="604-MED" taux={null} />)
    expect(screen.getAllByText('Sans base de calcul')).toHaveLength(2)
  })

  test('tableau de la direction : étapes distinctes, filtre transmis à l’API (T-210, T-212)', async () => {
    jetons.enregistrer('acces', 'rafraichissement')
    const montant = (m: string) => `${m}000000.00`
    const indicateurs = {
      budgetInitial: montant('130'),
      budgetRevise: montant('130'),
      engage: montant('80'),
      enCoursValidation: '0.00',
      disponibleApresEngagements: montant('50'),
      liquide: montant('45'),
      transmis: montant('35'),
      paye: montant('30'),
      resteAPayer: montant('15'),
      tauxEngagement: '61.54',
      tauxLiquidation: '34.62',
      tauxPaiement: '23.08',
    }
    const appel = simulerApi({
      'GET /api/v1/moi': [json(MOI)],
      'GET /api/v1/exercices': [
        json({
          donnees: [{ id: 'x1', code: '2026' }],
          pagination: { page: 1, taille: 100, total: 1, suivant: null },
        }),
      ],
      'GET /api/v1/tableaux-de-bord/direction': [
        json({
          indicateurs,
          chaine: {
            engage: montant('80'),
            commande: montant('65'),
            receptionne: montant('55'),
            facture: montant('50'),
            liquide: montant('45'),
            transmis: montant('35'),
            paye: montant('30'),
          },
          lignes: [
            {
              ligneId: 'l1',
              code: '604-MED',
              libelle: 'Médicaments',
              indicateurs: { ...indicateurs, tauxEngagement: '72.22' },
            },
          ],
          repartitions: { compte: [], service: [], nature: [], fournisseur: [] },
          marches: [],
          operationnel: {
            resteAEngagerMarches: montant('20'),
            resteContractuelAPayer: montant('70'),
            resteAPayerFactures: montant('15'),
            facturesEnAttente: 3,
            montantFacturesEnAttente: montant('50'),
            ageMoyenFacturesJours: '212.0',
            delaiMoyenTraitementJours: '4.0',
          },
        }),
      ],
    })
    afficher('/tableau-de-bord')
    expect(await screen.findByText('Réceptionné', {}, { timeout: 5000 })).toBeTruthy()
    expect(screen.getByText('Transmis en paiement')).toBeTruthy()
    expect(screen.getByRole('meter', { name: '604-MED — Médicaments' })).toBeTruthy()
    expect(screen.getByText('212 jours')).toBeTruthy()
    const urls = appel.mock.calls.map(([url]) => String(url))
    expect(urls.some((u) => u.includes('/tableaux-de-bord/direction?exerciceId=x1'))).toBe(true)
    fireEvent.change(screen.getByLabelText('Engagé à partir du'), {
      target: { value: '2026-03-02' },
    })
    await vi.waitFor(() =>
      expect(appel.mock.calls.some(([url]) => String(url).includes('du=2026-03-02'))).toBe(true),
    )
  })

  test('export des restes à payer : CSV pour tableur, montants exacts (T-214)', () => {
    expect(
      versCsv(
        ['Facture', 'Reste'],
        [
          ['FA;1', '5000000.00'],
          ['FA "2"', null],
        ],
      ),
    ).toBe('﻿Facture;Reste\r\n"FA;1";5000000.00\r\n"FA ""2""";\r\n')
  })
})

describe('centre d’alertes (lot 6)', () => {
  test('badge du menu, message lisible, alerte marquée comme lue (T-224)', async () => {
    jetons.enregistrer('acces', 'rafraichissement')
    const alerte = {
      id: 'al1',
      etablissementId: 'a1',
      type: 'SEUIL_MARCHE',
      gravite: 'ALERTE',
      typeObjet: 'Contrat',
      idObjet: 'c1',
      details: { numero: 'M-2026-001', taux: '80.00', seuil: '80.00' },
      codeAgent: null,
      creeLe: '2026-11-14T09:00:00Z',
      lue: false,
    }
    const appel = simulerApi({
      'GET /api/v1/moi': [json(MOI)],
      'GET /api/v1/alertes/compteur': [json({ nonLues: 1 })],
      'GET /api/v1/alertes': [json({ donnees: [alerte], suivant: null })],
      'PATCH /api/v1/alertes/al1': [json({ ...alerte, lue: true })],
    })
    afficher('/alertes')
    expect(await screen.findByLabelText('1 alerte non lue', {}, { timeout: 5000 })).toBeTruthy()
    expect(
      await screen.findByText('Marché M-2026-001 consommé à 80.00 % (repère de 80.00 %).'),
    ).toBeTruthy()
    // Gravité et état écrits en clair (IHM-06).
    expect(screen.getByText('Alerte')).toBeTruthy()
    expect(screen.getByText('Non lue')).toBeTruthy()
    expect(screen.getByRole('link', { name: 'Voir' }).getAttribute('href')).toBe('/contrats/c1')
    await userEvent.click(screen.getByRole('button', { name: 'Marquer comme lue' }))
    await vi.waitFor(() => {
      const envoi = appel.mock.calls.find(([, o]) => o?.method === 'PATCH')
      expect(JSON.parse(String(envoi![1]!.body))).toEqual({ lue: true })
    })
    const urls = appel.mock.calls.map(([url]) => String(url))
    expect(urls.some((u) => u.includes('/api/v1/alertes?nonLues=true'))).toBe(true)
  })
})

describe('recherche, audit et clôture (lot 6)', () => {
  const page = (donnees: unknown[]) => ({
    donnees,
    pagination: { page: 1, taille: 100, total: donnees.length, suivant: null },
  })

  test('recherche transverse : pièces trouvées et liens vers leur écran (T-238)', async () => {
    jetons.enregistrer('acces', 'rafraichissement')
    const appel = simulerApi({
      'GET /api/v1/moi': [json(MOI)],
      'GET /api/v1/recherche': [
        json([
          {
            type: 'Facture',
            id: 'f1',
            numero: 'FAC-001',
            libelle: 'Livraison de mars',
            montant: '30000000.00',
            date: '2026-04-16',
            lien: '/factures/f1',
          },
        ]),
      ],
    })
    afficher('/recherche')
    await userEvent.type(
      await screen.findByLabelText('Rechercher', {}, { timeout: 5000 }),
      'FAC-001{Enter}',
    )
    const lien = await screen.findByRole('link', { name: 'FAC-001' })
    expect(lien.getAttribute('href')).toBe('/factures/f1')
    expect(screen.getByText('Livraison de mars')).toBeTruthy()
    expect(
      appel.mock.calls.some(([url]) => String(url).includes('/api/v1/recherche?q=FAC-001')),
    ).toBe(true)
  })

  test('clôture d’exercice : confirmation, report annoncé, réouverture proposée (T-239)', async () => {
    jetons.enregistrer('acces', 'rafraichissement')
    const cloture = {
      id: 'cl1',
      exerciceId: 'x1',
      etablissementId: 'a1',
      exerciceSuivantId: 'x2',
      motif: 'Fin de gestion',
      engagementsReportes: 3,
      montantReporte: '36000000.00',
      creeParCode: 'AG004',
      creeLe: '2026-12-31T18:00:00Z',
      reouvertLe: null,
      reouvertParCode: null,
      motifReouverture: null,
    }
    const appel = simulerApi({
      'GET /api/v1/moi': [
        json({ ...MOI, habilitations: [{ profil: 'ORD', etablissementId: 'a1' }] }),
      ],
      'GET /api/v1/exercices': [
        json(
          page([
            { id: 'x1', code: '2026' },
            { id: 'x2', code: '2027' },
          ]),
        ),
      ],
      'GET /api/v1/etablissements': [
        json(page([{ id: 'a1', code: 'CHU-FANN', nom: 'CHU de Fann' }])),
      ],
      'GET /api/v1/exercices/x1/clotures': [json([]), json([cloture])],
      'POST /api/v1/exercices/x1/clotures': [json(cloture, 201)],
    })
    afficher('/cloture-exercice')
    await userEvent.click(await screen.findByLabelText('Exercice', {}, { timeout: 5000 }))
    await userEvent.click(await screen.findByTitle('2026'))
    // Le gabarit a aussi un sélecteur d'établissement : on vise le champ du formulaire.
    fireEvent.mouseDown(document.querySelector<HTMLInputElement>('#etablissementId')!)
    await userEvent.click(await screen.findByTitle('CHU-FANN — CHU de Fann'))
    await userEvent.click(screen.getByLabelText('Exercice suivant'))
    await userEvent.click((await screen.findAllByTitle('2027')).at(-1)!)
    await userEvent.type(screen.getByLabelText('Motif'), 'Fin de gestion')
    await userEvent.click(screen.getByRole('button', { name: "Clôturer l'exercice" }))
    const confirmation = (await screen.findAllByRole('dialog')).at(-1)!
    await userEvent.click(within(confirmation).getByRole('button', { name: "Clôturer l'exercice" }))
    expect(
      await screen.findByText('Exercice clos : 3 engagement(s) reporté(s), 36000000.00 XOF.'),
    ).toBeTruthy()
    const envoi = appel.mock.calls.find(([, o]) => o?.method === 'POST')!
    expect(JSON.parse(String(envoi[1]!.body))).toEqual({
      etablissementId: 'a1',
      exerciceSuivantId: 'x2',
      motif: 'Fin de gestion',
    })
    expect(await screen.findByRole('button', { name: 'Rouvrir' })).toBeTruthy()
  }, 15_000)
})

describe('intégrations (lot 7)', () => {
  test('alerte d’une réception importée : message propre au cas (EF-REC-07)', () => {
    const message = i18n.t('messages.ECART_RAPPROCHEMENT', {
      ns: 'alertes',
      numero: 'REC-2026-00002',
      context: 'HOPITALIA_SUPPRIME',
    })
    expect(message).toMatch(/^Réception REC-2026-00002 annulée/)
  })

  const echange = {
    id: 7,
    systemeExterne: 'HOPITALIA',
    direction: 'ENTRANT',
    typeDonnees: 'PHARMACIE',
    identifiantUnique: 'HOPITALIA:PHARMACIE:2026-10-15:2026-11-14',
    etablissementId: 'a1',
    parametres: { debut: '2026-10-15', fin: '2026-11-14' },
    statut: 'ECHEC',
    erreur: 'HOPITALIA_INDISPONIBLE',
    resultat: null,
    tentatives: 1,
    declencheParCode: null,
    creeLe: '2026-11-14T09:00:00Z',
    date: '2026-11-14T09:00:00Z',
  }

  test('journal : échec traduit, reprise par l’administrateur (T-200)', async () => {
    jetons.enregistrer('acces', 'rafraichissement')
    const appel = simulerApi({
      'GET /api/v1/moi': [json(MOI)],
      'GET /api/v1/journal-integration': [
        json({ donnees: [echange], pagination: { taille: 50, suivant: null } }),
      ],
      'POST /api/v1/journal-integration/7/reprises': [
        json({ ...echange, statut: 'SUCCES', erreur: null, resultat: { commandes: 1 } }),
      ],
    })
    afficher('/integrations')
    expect(
      await screen.findByText(
        'Le service de connexion Hopitalia ne répond pas. Réessayez plus tard.',
        {},
        { timeout: 5000 },
      ),
    ).toBeTruthy()
    expect(screen.getByText('En échec')).toBeTruthy()
    await userEvent.click(screen.getByRole('button', { name: /Reprendre/ }))
    expect(await screen.findByText('Échange réussi.')).toBeTruthy()
    expect(
      appel.mock.calls.some(
        ([url, options]) =>
          String(url).endsWith('/journal-integration/7/reprises') && options?.method === 'POST',
      ),
    ).toBe(true)
  }, 15_000)

  test('commandes de la pharmacie : rattachement par l’agent financier (EF-REC-07)', async () => {
    jetons.enregistrer('acces', 'rafraichissement')
    const commande = {
      id: 'cp1',
      etablissementId: 'a1',
      numero: 'BCP-0501',
      dateCommande: '2026-03-02',
      codeFournisseur: 'PHARMA-TEST',
      fournisseurId: 'f1',
      service: 'Pharmacie centrale',
      lignes: [
        { codeProduit: 'P1', nomProduit: 'Paracétamol', quantite: '10.000', montant: '50000.00' },
      ],
      montant: '50000.00',
      bonCommandeId: null,
      approvisionnementsEnAttente: 1,
      propositions: [
        {
          engagementId: 'e1',
          numero: 'ENG-2026-00001',
          objet: 'Médicaments',
          resteACommander: '9000000.00',
        },
      ],
    }
    const appel = simulerApi({
      'GET /api/v1/moi': [
        json({ ...MOI, habilitations: [{ profil: 'AF', etablissementId: 'a1' }] }),
      ],
      'GET /api/v1/commandes-pharmacie': [
        json({ donnees: [commande], pagination: { page: 1, taille: 25, total: 1, suivant: null } }),
      ],
      'POST /api/v1/commandes-pharmacie/cp1/rattachement': [
        json({ ...commande, bonCommandeId: 'bc1', approvisionnementsEnAttente: 0 }, 201),
      ],
    })
    afficher('/commandes-pharmacie')
    await userEvent.click(
      await screen.findByLabelText('Engagement — BCP-0501', {}, { timeout: 5000 }),
    )
    await userEvent.click(await screen.findByTitle('ENG-2026-00001 — Médicaments'))
    await userEvent.click(screen.getByRole('button', { name: /Rattacher/ }))
    expect(await screen.findByText("Commande rattachée à l'engagement.")).toBeTruthy()
    const envoi = appel.mock.calls.find(([url]) => String(url).endsWith('/rattachement'))!
    expect(JSON.parse(String(envoi[1]!.body))).toEqual({ engagementId: 'e1' })
    expect(new Headers(envoi[1]!.headers).get('Idempotency-Key')).toMatch(/[0-9a-f-]{36}/)
  }, 15_000)
})
