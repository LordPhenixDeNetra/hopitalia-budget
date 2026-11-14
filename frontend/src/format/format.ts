// Formats selon la langue (I18N-05), avec les API Intl du navigateur.
const REGIONS: Record<string, string> = { fr: 'fr-FR', en: 'en-US' }

const region = (langue: string): string => REGIONS[langue] ?? REGIONS.fr

/**
 * Montant reçu de l'API sous forme de chaîne décimale exacte.
 * La chaîne est formatée telle quelle (Intl.NumberFormat accepte les chaînes depuis ES2023) :
 * aucune conversion en nombre flottant, donc aucune perte au-delà de 2^53.
 */
export function formaterMontant(valeur: string, langue: string, devise = 'XOF'): string {
  return new Intl.NumberFormat(region(langue), {
    style: 'currency',
    currency: devise,
    currencyDisplay: 'code',
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(valeur as unknown as number)
}

export function formaterNombre(valeur: number, langue: string): string {
  return new Intl.NumberFormat(region(langue)).format(valeur)
}

export function formaterDate(iso: string, langue: string): string {
  return new Intl.DateTimeFormat(region(langue), { dateStyle: 'medium' }).format(new Date(iso))
}

export function formaterDateHeure(iso: string, langue: string): string {
  return new Intl.DateTimeFormat(region(langue), {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(iso))
}
