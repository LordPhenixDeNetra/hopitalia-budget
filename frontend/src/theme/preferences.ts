import { useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { getLireMoiQueryKey, modifierPreferences } from '../api/genere/budget'
import type { Moi, Preferences } from '../api/genere/budget.schemas'
import { useSession } from '../auth/session'

export type Theme = NonNullable<Moi['theme']>
export type Densite = NonNullable<Moi['densite']>

const CLE_AFFICHAGE = 'hopitalia-budget.affichage'
// Mode de test de l'écriture de droite à gauche (I18N-10) : aucune langue de ce type n'est prévue.
const CLE_DIRECTION = 'hopitalia-budget.direction'

interface Memorise {
  theme?: Theme
  densite?: Densite
}

function lire<T>(cle: string, defaut: T): T {
  try {
    const valeur = localStorage.getItem(cle)
    return valeur ? (JSON.parse(valeur) as T) : defaut
  } catch {
    return defaut
  }
}

function ecrire(cle: string, valeur: unknown): void {
  try {
    localStorage.setItem(cle, JSON.stringify(valeur))
  } catch {
    // Préférence non mémorisée sur ce poste ; le profil la conserve.
  }
}

/** Direction forcée pour le test droite à gauche, sinon celle de la langue. */
export function directionDeTest(): 'rtl' | undefined {
  return lire<string | null>(CLE_DIRECTION, null) === 'rtl' ? 'rtl' : undefined
}

/**
 * Préférences d'affichage (T-270, T-271) : enregistrées sur le profil de l'agent, donc conservées
 * d'une session et d'un poste à l'autre ; thème et densité sont aussi mémorisés sur le poste pour
 * l'écran de connexion. Thème clair et densité compacte par défaut (IHM-01, IHM-02).
 */
export function usePreferencesAffichage() {
  const { moi } = useSession()
  const client = useQueryClient()
  const memorise = lire<Memorise>(CLE_AFFICHAGE, {})
  const theme: Theme = moi?.theme ?? memorise.theme ?? 'CLAIR'
  const densite: Densite = moi?.densite ?? memorise.densite ?? 'COMPACTE'
  const colonnesMasquees: Record<string, string[]> = moi?.colonnesMasquees ?? {}

  const modifier = (changement: Preferences) => {
    ecrire(CLE_AFFICHAGE, {
      theme: changement.theme ?? theme,
      densite: changement.densite ?? densite,
    })
    // Affichage immédiat ; le profil est mis à jour en arrière-plan.
    client.setQueryData<Moi>(getLireMoiQueryKey(), (actuel) =>
      actuel
        ? {
            ...actuel,
            ...changement,
            colonnesMasquees: changement.colonnesMasquees ?? actuel.colonnesMasquees,
          }
        : actuel,
    )
    void modifierPreferences(changement).then(
      (enregistre) => client.setQueryData(getLireMoiQueryKey(), enregistre),
      () => void client.invalidateQueries({ queryKey: getLireMoiQueryKey() }),
    )
  }
  return { theme, densite, colonnesMasquees, modifier }
}

const REQUETE_SOMBRE = '(prefers-color-scheme: dark)'

/** Vrai si le thème sombre s'applique : choisi, ou demandé par le système (« Système »). */
export function useSombre(theme: Theme): boolean {
  const [systeme, setSysteme] = useState(() => window.matchMedia(REQUETE_SOMBRE).matches)
  useEffect(() => {
    const media = window.matchMedia(REQUETE_SOMBRE)
    const changer = (evenement: MediaQueryListEvent) => setSysteme(evenement.matches)
    media.addEventListener('change', changer)
    return () => media.removeEventListener('change', changer)
  }, [])
  return theme === 'SOMBRE' || (theme === 'SYSTEME' && systeme)
}
