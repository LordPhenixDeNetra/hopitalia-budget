// Jeton d'accès en mémoire seulement ; jeton de rafraîchissement limité à l'onglet (sessionStorage).
const CLE_RAFRAICHISSEMENT = 'hopitalia-budget.rafraichissement'

let jetonAcces: string | null = null

function lire(): string | null {
  try {
    return sessionStorage.getItem(CLE_RAFRAICHISSEMENT)
  } catch {
    return null
  }
}

export const jetons = {
  acces: (): string | null => jetonAcces,
  rafraichissement: lire,
  enregistrer(acces: string, rafraichissement: string): void {
    jetonAcces = acces
    try {
      sessionStorage.setItem(CLE_RAFRAICHISSEMENT, rafraichissement)
    } catch {
      // Stockage indisponible : la session durera le temps du jeton d'accès.
    }
  },
  effacer(): void {
    jetonAcces = null
    try {
      sessionStorage.removeItem(CLE_RAFRAICHISSEMENT)
    } catch {
      // Rien à effacer.
    }
  },
}
