import { App, type FormInstance } from 'antd'
import { useTranslation } from 'react-i18next'
import { ErreurApi } from './client'

export function codeErreur(erreur: unknown): string {
  return erreur instanceof ErreurApi ? erreur.probleme.code : 'ERREUR_INTERNE'
}

/**
 * Affiche une erreur d'API (T-068) : sous les champs concernés quand l'API les désigne,
 * sinon en notification. Le message vient du code d'erreur, traduit (I18N-07).
 */
export function useAfficherErreur() {
  const { t } = useTranslation('erreurs')
  const { notification } = App.useApp()
  return (erreur: unknown, formulaire?: FormInstance) => {
    const erreursChamps = erreur instanceof ErreurApi ? (erreur.probleme.erreurs ?? []) : []
    if (formulaire && erreursChamps.length > 0) {
      formulaire.setFields(
        erreursChamps.map((e) => ({
          name: e.champ,
          errors: [t(`champ.${e.code}`, { defaultValue: t('VALIDATION') })],
        })),
      )
      return
    }
    notification.error({ title: t(codeErreur(erreur)) })
  }
}
