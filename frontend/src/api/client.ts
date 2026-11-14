import { jetons } from '../auth/jetons'
import i18n from '../i18n'

/** Erreur renvoyée par l'API au format application/problem+json (section 11.9). */
export interface Probleme {
  title: string
  status: number
  code: string
  detail?: string
  erreurs?: { champ: string; code: string }[]
}

export class ErreurApi extends Error {
  readonly probleme: Probleme

  constructor(probleme: Probleme) {
    super(probleme.code)
    this.probleme = probleme
  }
}

export const EVENEMENT_SESSION_EXPIREE = 'hopitalia-budget:session-expiree'

async function lireProbleme(reponse: Response): Promise<Probleme> {
  try {
    const corps = (await reponse.json()) as Partial<Probleme>
    if (typeof corps.code === 'string') return corps as Probleme
  } catch {
    // Corps absent ou non JSON : erreur générique ci-dessous.
  }
  return { title: reponse.statusText, status: reponse.status, code: 'ERREUR_INTERNE' }
}

let rafraichissementEnCours: Promise<boolean> | null = null

async function rafraichir(): Promise<boolean> {
  const jetonRafraichissement = jetons.rafraichissement()
  if (!jetonRafraichissement) return false
  const reponse = await fetch('/api/v1/auth/rafraichissement', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ jetonRafraichissement }),
  })
  if (!reponse.ok) return false
  const nouveaux = (await reponse.json()) as { jetonAcces: string; jetonRafraichissement: string }
  jetons.enregistrer(nouveaux.jetonAcces, nouveaux.jetonRafraichissement)
  return true
}

/** Client utilisé par le code généré (orval) : langue, jeton, rafraîchissement, erreurs. */
export async function appelerApi<T>(url: string, options: RequestInit = {}): Promise<T> {
  const executer = (): Promise<Response> => {
    const entetes = new Headers(options.headers)
    entetes.set('Accept-Language', i18n.language)
    const acces = jetons.acces()
    if (acces) entetes.set('Authorization', `Bearer ${acces}`)
    return fetch(url, { ...options, headers: entetes })
  }
  let reponse = await executer()
  if (reponse.status === 401 && jetons.rafraichissement()) {
    // Un seul rafraîchissement à la fois, même si plusieurs requêtes échouent ensemble.
    rafraichissementEnCours ??= rafraichir().finally(() => {
      rafraichissementEnCours = null
    })
    if (await rafraichissementEnCours) reponse = await executer()
  }
  if (reponse.status === 401 && !url.startsWith('/api/v1/auth/')) {
    jetons.effacer()
    window.dispatchEvent(new Event(EVENEMENT_SESSION_EXPIREE))
  }
  if (!reponse.ok) throw new ErreurApi(await lireProbleme(reponse))
  if (reponse.status === 204) return undefined as T
  return (await reponse.json()) as T
}

export default appelerApi
