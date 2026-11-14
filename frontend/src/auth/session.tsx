import { useQueryClient } from '@tanstack/react-query'
import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { EVENEMENT_SESSION_EXPIREE } from '../api/client'
import { connexion, deconnexion, useLireMoi } from '../api/genere/budget'
import type { Moi } from '../api/genere/budget.schemas'
import { estLangue, memoriserLangue } from '../i18n/langue'
import { jetons } from './jetons'

interface Session {
  connecte: boolean
  expiree: boolean
  moi?: Moi
  connecter: (identifiant: string, motDePasse: string) => Promise<void>
  deconnecter: () => Promise<void>
}

const ContexteSession = createContext<Session | null>(null)

export function FournisseurSession({ children }: { children: ReactNode }) {
  const client = useQueryClient()
  const { i18n } = useTranslation()
  // Après un rechargement, le jeton d'accès est perdu mais le rafraîchissement le renouvelle.
  const [connecte, setConnecte] = useState(() => jetons.rafraichissement() !== null)
  const [expiree, setExpiree] = useState(false)
  const { data: moi } = useLireMoi({ query: { enabled: connecte } })

  useEffect(() => {
    const expirer = () => {
      setConnecte(false)
      setExpiree(true)
      client.clear()
    }
    window.addEventListener(EVENEMENT_SESSION_EXPIREE, expirer)
    return () => window.removeEventListener(EVENEMENT_SESSION_EXPIREE, expirer)
  }, [client])

  // La langue du profil prime sur celle du navigateur (I18N-04).
  useEffect(() => {
    if (estLangue(moi?.langue) && moi.langue !== i18n.language) {
      memoriserLangue(moi.langue)
      void i18n.changeLanguage(moi.langue)
    }
  }, [moi?.langue, i18n])

  const valeur: Session = {
    connecte,
    expiree,
    moi,
    async connecter(identifiant, motDePasse) {
      const nouveaux = await connexion({ identifiant, motDePasse })
      jetons.enregistrer(nouveaux.jetonAcces, nouveaux.jetonRafraichissement)
      setExpiree(false)
      setConnecte(true)
    },
    async deconnecter() {
      const jetonRafraichissement = jetons.rafraichissement()
      jetons.effacer()
      setConnecte(false)
      client.clear()
      if (jetonRafraichissement) await deconnexion({ jetonRafraichissement }).catch(() => {})
    },
  }
  return <ContexteSession.Provider value={valeur}>{children}</ContexteSession.Provider>
}

export function useSession(): Session {
  const session = useContext(ContexteSession)
  if (!session) throw new Error('useSession hors de FournisseurSession')
  return session
}

/** Vrai si l'utilisateur a au moins un des profils (dans un établissement quelconque). */
export function useAProfil(profils: string[]): boolean {
  const { moi } = useSession()
  return (moi?.habilitations ?? []).some((h) => profils.includes(h.profil))
}
