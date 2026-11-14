import { useState } from 'react'
import { useListerEtablissements } from '../api/genere/budget'
import type { EtablissementSortie } from '../api/genere/budget.schemas'

const CLE = 'hopitalia-budget.etablissement'

function lire(): string | null {
  try {
    return localStorage.getItem(CLE)
  } catch {
    return null
  }
}

/** Établissement de travail choisi dans l'en-tête ; null : tous ceux de l'utilisateur. */
export function useEtablissementCourant(): {
  etablissements: EtablissementSortie[]
  courant: string | null
  choisir: (id: string | null) => void
} {
  const { data } = useListerEtablissements({ actif: true, taille: 100 })
  const [courant, setCourant] = useState<string | null>(lire)
  const etablissements = data?.donnees ?? []
  return {
    etablissements,
    courant: etablissements.some((e) => e.id === courant) ? courant : null,
    choisir(id) {
      setCourant(id)
      try {
        if (id) localStorage.setItem(CLE, id)
        else localStorage.removeItem(CLE)
      } catch {
        // Choix non mémorisé sur ce poste.
      }
    },
  }
}
