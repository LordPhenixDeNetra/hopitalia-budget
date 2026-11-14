import { cleanup, render, screen } from '@testing-library/react'
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
  await i18n.loadNamespaces(['commun', 'erreurs', 'etablissements'])
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
    const enregistrer = await screen.findByRole('button', { name: 'Enregistrer' })
    await userEvent.click(enregistrer)
    expect(await screen.findByText('Ce champ est trop court.')).toBeTruthy()
    await userEvent.click(enregistrer)
    expect(await screen.findByText(/modifiée par quelqu'un d'autre/)).toBeTruthy()
  })
})
