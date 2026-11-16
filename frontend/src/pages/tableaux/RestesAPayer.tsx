import { DownloadOutlined } from '@ant-design/icons'
import { useQuery } from '@tanstack/react-query'
import { Button, Flex, Table, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table/interface'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'
import { restesAPayer } from '../../api/genere/budget'
import type { FactureEnAttente } from '../../api/genere/budget.schemas'
import { BadgeStatut } from '../../composants/BadgeStatut'
import { Montant } from '../../composants/Montant'
import { telechargerCsv, versCsv } from '../../format/csv'
import { formaterDate } from '../../format/format'
import { TONS_FACTURE } from '../factures/Factures'
import { BarreFiltres, useFiltresTableau } from './TableauDeBord'

/** Restes à payer et factures en attente du périmètre, exportables (T-214, annexe 18.1). */
export function RestesAPayer() {
  const { t, i18n } = useTranslation('tableaux')
  const { t: tFactures } = useTranslation('factures')
  const { t: tCommun } = useTranslation()
  const filtres = useFiltresTableau()
  const { data = [], isFetching } = useQuery({
    queryKey: ['restes-a-payer', filtres],
    queryFn: () => restesAPayer(filtres!),
    enabled: Boolean(filtres),
  })
  const exporter = () =>
    telechargerCsv(
      'restes-a-payer.csv',
      versCsv(
        ['numero', 'statut', 'dateReception', 'montantTtc', 'resteAPayer', 'ageJours'].map((c) =>
          t(`restes.${c}`),
        ),
        data.map((f) => [
          f.numero,
          tFactures(`valeurs.${f.statut}`),
          f.dateReception,
          f.montantTtc,
          f.resteAPayer,
          f.ageJours,
        ]),
      ),
    )
  const colonnes: ColumnsType<FactureEnAttente> = [
    {
      title: t('restes.numero'),
      dataIndex: 'numero',
      render: (v: string, f) => <Link to={`/factures/${f.factureId}`}>{v}</Link>,
    },
    {
      title: t('restes.statut'),
      dataIndex: 'statut',
      render: (v: string) => (
        <BadgeStatut ton={TONS_FACTURE[v] ?? 'neutre'} libelle={tFactures(`valeurs.${v}`)} />
      ),
    },
    {
      title: t('restes.dateReception'),
      dataIndex: 'dateReception',
      render: (v: string) => formaterDate(v, i18n.language),
    },
    {
      title: t('restes.montantTtc'),
      dataIndex: 'montantTtc',
      align: 'end',
      render: (v: string) => <Montant valeur={v} />,
    },
    {
      title: t('restes.resteAPayer'),
      dataIndex: 'resteAPayer',
      align: 'end',
      render: (v: string) => <Montant valeur={v} />,
    },
    { title: t('restes.ageJours'), dataIndex: 'ageJours', align: 'end' },
  ]

  return (
    <Flex vertical gap="middle">
      <Flex justify="space-between" align="center" wrap gap="small">
        <Typography.Title level={1} style={{ margin: 0 }}>
          {t('restes.titre')}
        </Typography.Title>
        <Button
          icon={<DownloadOutlined aria-hidden />}
          disabled={data.length === 0}
          onClick={exporter}
        >
          {t('restes.exporter')}
        </Button>
      </Flex>
      <Typography.Paragraph>{t('restes.intro')}</Typography.Paragraph>
      <BarreFiltres />
      <Table<FactureEnAttente>
        rowKey="factureId"
        loading={isFetching}
        columns={colonnes}
        dataSource={data}
        pagination={false}
        scroll={{ x: 'max-content' }}
        locale={{ emptyText: tCommun('tableau.aucun') }}
      />
    </Flex>
  )
}
