import { DownloadOutlined } from '@ant-design/icons'
import { useInfiniteQuery } from '@tanstack/react-query'
import { App, Button, Flex, Input, Space, Table, Typography } from 'antd'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { telechargerFichier } from '../api/client'
import { listerJournalAudit } from '../api/genere/budget'
import type { EntreeJournal } from '../api/genere/budget.schemas'
import { formaterDateHeure } from '../format/format'

const FILTRES = ['action', 'typeObjet', 'idObjet'] as const
const BORNES = ['du', 'au'] as const
const FORMATS = ['pdf', 'xlsx', 'csv'] as const

/** Journal d'audit en lecture seule et rapport d'audit (T-236, EF-AUD-01). */
export function Audit() {
  const { t, i18n } = useTranslation('audit')
  const { t: tCommun } = useTranslation()
  const { message } = App.useApp()
  const [saisie, setSaisie] = useState<Record<string, string>>({})
  const [filtres, setFiltres] = useState<Record<string, string>>({})
  const actifs = Object.fromEntries(Object.entries(filtres).filter(([, v]) => v))
  const { data, fetchNextPage, hasNextPage, isFetching } = useInfiniteQuery({
    queryKey: ['journal-audit', actifs],
    initialPageParam: undefined as string | undefined,
    queryFn: ({ pageParam }) => listerJournalAudit({ ...actifs, apres: pageParam, taille: 50 }),
    getNextPageParam: (page) => page.pagination.suivant ?? undefined,
  })
  const lignes = data?.pages.flatMap((p) => p.donnees) ?? []
  const telecharger = (format: string) =>
    telechargerFichier(
      `/api/v1/journal-audit/rapport?${new URLSearchParams({ ...actifs, format })}`,
      `audit.${format}`,
    ).catch(() => message.error(t('echec')))
  const champ = (nom: string, estDate = false) => (
    <Input
      key={nom}
      type={estDate ? 'date' : undefined}
      aria-label={t(`filtres.${nom}`)}
      placeholder={t(`filtres.${nom}`)}
      style={{ width: estDate ? 160 : 180 }}
      value={saisie[nom] ?? ''}
      onChange={(e) => setSaisie((s) => ({ ...s, [nom]: e.target.value }))}
    />
  )

  return (
    <Flex vertical gap="middle">
      <Typography.Title level={1} style={{ margin: 0 }}>
        {t('titre')}
      </Typography.Title>
      <Typography.Paragraph>{t('intro')}</Typography.Paragraph>
      <Flex gap="small" wrap>
        {FILTRES.map((nom) => champ(nom))}
        {BORNES.map((nom) => champ(nom, true))}
        <Button type="primary" onClick={() => setFiltres(saisie)}>
          {t('filtrer')}
        </Button>
      </Flex>
      <Space wrap>
        <Typography.Text>{t('rapport')}</Typography.Text>
        {FORMATS.map((format) => (
          <Button
            key={format}
            size="small"
            icon={<DownloadOutlined aria-hidden />}
            onClick={() => void telecharger(format)}
          >
            {t(`formats.${format}`)}
          </Button>
        ))}
      </Space>
      <Table<EntreeJournal>
        rowKey="id"
        size="small"
        loading={isFetching}
        dataSource={lignes}
        pagination={false}
        scroll={{ x: 'max-content' }}
        locale={{ emptyText: tCommun('tableau.aucun') }}
        columns={[
          {
            title: t('colonnes.horodatage'),
            dataIndex: 'horodatage',
            render: (v: string) => formaterDateHeure(v, i18n.language),
          },
          { title: t('colonnes.agent'), dataIndex: 'codeAgent' },
          { title: t('colonnes.action'), dataIndex: 'action' },
          { title: t('colonnes.objet'), dataIndex: 'typeObjet' },
          { title: t('colonnes.identifiant'), dataIndex: 'idObjet' },
          { title: t('colonnes.ip'), dataIndex: 'adresseIp' },
          {
            title: t('colonnes.valeur'),
            key: 'valeur',
            render: (_, e) => (
              <Typography.Text code style={{ whiteSpace: 'pre-wrap' }}>
                {e.nouvelleValeur ? JSON.stringify(e.nouvelleValeur).slice(0, 160) : ''}
              </Typography.Text>
            ),
          },
        ]}
      />
      {hasNextPage && (
        <Button style={{ alignSelf: 'center' }} onClick={() => void fetchNextPage()}>
          {t('plus')}
        </Button>
      )}
    </Flex>
  )
}
