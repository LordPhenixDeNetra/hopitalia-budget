import { cleanup, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { afterEach, beforeAll, describe, expect, test, vi } from 'vitest'
import { jetons } from './auth/jetons'
import { BadgeStatut } from './composants/BadgeStatut'
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
    visas: [],
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

  test('révision : visa DAF proposé au seul profil de l’étape (T-095)', async () => {
    jetons.enregistrer('acces', 'rafraichissement')
    const appel = simulerApi({
      'GET /api/v1/moi': [
        json({ ...MOI, habilitations: [{ profil: 'VAL', etablissementId: 'a1' }] }),
      ],
      'GET /api/v1/budgets/b1': [json(BUDGET)],
      'GET /api/v1/budgets/b1/situation': [SITUATION],
      'GET /api/v1/revisions-budgetaires': [page([REVISION])],
      'POST /api/v1/revisions-budgetaires/r1/validations': [json({ ...REVISION, statut: 'VISEE' })],
    })
    afficher('/budgets/b1')
    await userEvent.click(await screen.findByRole('tab', { name: 'Révisions' }))
    expect(await screen.findByText('En attente du visa DAF')).toBeTruthy()
    // Le profil VAL ne peut pas demander de révision (réservé au RB).
    expect(screen.queryByRole('button', { name: 'Demander une révision' })).toBeNull()
    await userEvent.click(screen.getByRole('button', { name: 'Viser' }))
    expect(await screen.findByText('Décision enregistrée.')).toBeTruthy()

    const envoi = appel.mock.calls.find(([, options]) => options?.method === 'POST')!
    expect(JSON.parse(String(envoi[1]!.body))).toEqual({ decision: 'VALIDE' })
  })
})
