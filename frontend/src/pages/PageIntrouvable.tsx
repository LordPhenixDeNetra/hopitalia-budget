import { Result } from 'antd'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'

export function PageIntrouvable() {
  const { t } = useTranslation()
  return (
    <Result
      status="404"
      title={t('introuvable.titre')}
      subTitle={t('introuvable.detail')}
      extra={<Link to="/">{t('introuvable.retour')}</Link>}
    />
  )
}
