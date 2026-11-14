export const LANGUES = ['fr', 'en'] as const
export type Langue = (typeof LANGUES)[number]

const CLE_LANGUE = 'hopitalia-budget.langue'

export function estLangue(valeur: unknown): valeur is Langue {
  return LANGUES.includes(valeur as Langue)
}

/** Avant connexion (I18N-04) : dernier choix mémorisé, sinon langue du navigateur, sinon français. */
export function langueInitiale(navigateur: readonly string[] = navigator.languages): Langue {
  try {
    const memorisee = localStorage.getItem(CLE_LANGUE)
    if (estLangue(memorisee)) return memorisee
  } catch {
    // Stockage indisponible : on passe à la langue du navigateur.
  }
  for (const langue of navigateur) {
    const code = langue.slice(0, 2).toLowerCase()
    if (estLangue(code)) return code
  }
  return 'fr'
}

export function memoriserLangue(langue: Langue): void {
  try {
    localStorage.setItem(CLE_LANGUE, langue)
  } catch {
    // Préférence non mémorisée sur ce poste ; le profil la conserve.
  }
}
