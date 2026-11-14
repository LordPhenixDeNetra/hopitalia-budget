import { useEffect, useState } from 'react'

const REQUETE = '(prefers-reduced-motion: reduce)'

export function useMouvementReduit(): boolean {
  const [reduit, setReduit] = useState(() => window.matchMedia(REQUETE).matches)
  useEffect(() => {
    const media = window.matchMedia(REQUETE)
    const changer = (evenement: MediaQueryListEvent) => setReduit(evenement.matches)
    media.addEventListener('change', changer)
    return () => media.removeEventListener('change', changer)
  }, [])
  return reduit
}
