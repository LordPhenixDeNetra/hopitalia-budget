import { DownloadOutlined } from '@ant-design/icons'
import { App, Button, Flex, List, Space, Typography } from 'antd'
import { useTranslation } from 'react-i18next'
import { telechargerFichier } from '../../api/client'
import { BarreFiltres, useFiltresTableau } from './TableauDeBord'

const CODES = [
  'budget',
  'restes',
  'engagements',
  'contrats',
  'commandes',
  'factures',
  'liquidations',
  'paiements',
  'rapprochements',
  'depenses',
  'echeances',
  'ecritures',
] as const
const FORMATS = ['pdf', 'xlsx', 'csv', 'json'] as const

/** États de la section 14.4 : mêmes filtres que le tableau de bord, quatre formats (T-230). */
export function Etats() {
  const { t } = useTranslation('etats')
  const { message } = App.useApp()
  const filtres = useFiltresTableau()
  const telecharger = (code: string, format: string) => {
    const parametres = new URLSearchParams({
      ...(filtres as unknown as Record<string, string>),
      format,
    })
    telechargerFichier(`/api/v1/etats/${code}?${parametres}`, `${code}.${format}`).catch(() =>
      message.error(t('echec')),
    )
  }

  return (
    <Flex vertical gap="middle">
      <Typography.Title level={1} style={{ margin: 0 }}>
        {t('titre')}
      </Typography.Title>
      <Typography.Paragraph>{t('intro')}</Typography.Paragraph>
      <BarreFiltres />
      <List
        dataSource={[...CODES]}
        renderItem={(code) => (
          <List.Item>
            <Flex justify="space-between" align="center" wrap gap="small" style={{ width: '100%' }}>
              <Flex vertical>
                <Typography.Text strong>{t(`codes.${code}.titre`)}</Typography.Text>
                <Typography.Text type="secondary">{t(`codes.${code}.description`)}</Typography.Text>
              </Flex>
              <Space wrap>
                {FORMATS.map((format) => (
                  <Button
                    key={format}
                    size="small"
                    icon={<DownloadOutlined aria-hidden />}
                    disabled={!filtres}
                    aria-label={`${t(`formats.${format}`)} — ${t(`codes.${code}.titre`)}`}
                    onClick={() => telecharger(code, format)}
                  >
                    {t(`formats.${format}`)}
                  </Button>
                ))}
              </Space>
            </Flex>
          </List.Item>
        )}
      />
    </Flex>
  )
}
