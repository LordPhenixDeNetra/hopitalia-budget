import { useTranslation } from 'react-i18next'
import { formaterMontant } from '../format/format'

export function Montant({ valeur, devise = 'XOF' }: { valeur: string; devise?: string }) {
  const { i18n } = useTranslation()
  return <span className="montant">{formaterMontant(valeur, i18n.language, devise)}</span>
}
