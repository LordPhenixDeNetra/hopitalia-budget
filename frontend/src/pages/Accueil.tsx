import { Card, List, Typography } from 'antd'
import { useTranslation } from 'react-i18next'
import { useSession } from '../auth/session'

export function Accueil() {
  const { t } = useTranslation()
  const { moi } = useSession()
  return (
    <>
      <Typography.Title level={1}>{t('accueil.titre')}</Typography.Title>
      <Typography.Paragraph>{t('accueil.bienvenue', { nom: moi?.nom ?? '' })}</Typography.Paragraph>
      <Card title={t('accueil.profils')}>
        <List
          dataSource={moi?.habilitations ?? []}
          renderItem={(h) => (
            <List.Item>
              {h.profil} — {h.etablissementId ?? t('accueil.tousEtablissements')}
            </List.Item>
          )}
        />
      </Card>
    </>
  )
}
