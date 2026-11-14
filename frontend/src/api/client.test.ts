import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'
import { jetons } from '../auth/jetons'
import { appelerApi, ErreurApi, EVENEMENT_SESSION_EXPIREE } from './client'

const json = (corps: unknown, status = 200, type = 'application/json') =>
  new Response(JSON.stringify(corps), { status, headers: { 'Content-Type': type } })

const probleme = (code: string, status: number) =>
  json({ code, status, title: code }, status, 'application/problem+json')

describe('client HTTP (T-067, T-069)', () => {
  beforeEach(() => jetons.enregistrer('acces-1', 'rafraichissement-1'))
  afterEach(() => {
    jetons.effacer()
    vi.unstubAllGlobals()
  })

  test('envoie le jeton et la langue', async () => {
    const appel = vi.fn().mockResolvedValue(json({ ok: true }))
    vi.stubGlobal('fetch', appel)
    await appelerApi('/api/v1/moi')
    const entetes = appel.mock.calls[0][1].headers as Headers
    expect(entetes.get('Authorization')).toBe('Bearer acces-1')
    expect(entetes.get('Accept-Language')).toMatch(/fr|en/)
  })

  test('jeton expiré : un seul rafraîchissement, puis la requête est rejouée', async () => {
    const appel = vi
      .fn()
      .mockResolvedValueOnce(probleme('JETON_INVALIDE', 401))
      .mockResolvedValueOnce(json({ jetonAcces: 'acces-2', jetonRafraichissement: 'r-2' }))
      .mockResolvedValueOnce(json({ nom: 'Awa' }))
    vi.stubGlobal('fetch', appel)
    expect(await appelerApi('/api/v1/moi')).toEqual({ nom: 'Awa' })
    expect(appel.mock.calls[1][0]).toBe('/api/v1/auth/rafraichissement')
    expect((appel.mock.calls[2][1].headers as Headers).get('Authorization')).toBe('Bearer acces-2')
  })

  test('rafraîchissement refusé : session expirée signalée', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValueOnce(probleme('JETON_INVALIDE', 401))
        .mockResolvedValueOnce(probleme('IDENTIFIANTS_INVALIDES', 401)),
    )
    const expiration = vi.fn()
    window.addEventListener(EVENEMENT_SESSION_EXPIREE, expiration)
    await expect(appelerApi('/api/v1/moi')).rejects.toBeInstanceOf(ErreurApi)
    expect(expiration).toHaveBeenCalledOnce()
    expect(jetons.acces()).toBeNull()
    window.removeEventListener(EVENEMENT_SESSION_EXPIREE, expiration)
  })

  test('erreur problem+json : code métier conservé', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(probleme('PRECONDITION_ECHOUEE', 412)))
    const erreur = await appelerApi('/api/v1/etablissements/1', { method: 'PATCH' }).catch(
      (e: unknown) => e,
    )
    expect(erreur).toBeInstanceOf(ErreurApi)
    expect((erreur as ErreurApi).probleme).toMatchObject({
      code: 'PRECONDITION_ECHOUEE',
      status: 412,
    })
  })
})
