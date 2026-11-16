import { Card, List, Typography } from 'antd'
import { useTranslation } from 'react-i18next'
import { useSession } from '../auth/session'
import { useEtablissementCourant } from '../composants/etablissementCourant'

export function Accueil() {
  const { t } = useTranslation()
  const { t: tHabilitations } = useTranslation('habilitations')
  const { moi } = useSession()
  const { etablissements } = useEtablissementCourant()
  // Établissement de l'habilitation par son code et son nom, comme dans l'en-tête.
  const etablissement = (id: string | null) => {
    if (!id) return t('accueil.tousEtablissements')
    const e = etablissements.find((x) => x.id === id)
    return e ? `${e.code} — ${e.nom}` : id
  }
  return (
    <>
      <Typography.Title level={1}>{t('accueil.titre')}</Typography.Title>
      <Typography.Paragraph>{t('accueil.bienvenue', { nom: moi?.nom ?? '' })}</Typography.Paragraph>
      <Card title={t('accueil.profils')}>
        <List
          dataSource={moi?.habilitations ?? []}
          renderItem={(h) => (
            <List.Item>
              {tHabilitations(`profils.${h.profil}`)} ({h.profil}) —{' '}
              {etablissement(h.etablissementId)}
            </List.Item>
          )}
        />
      </Card>
    </>
  )
}
