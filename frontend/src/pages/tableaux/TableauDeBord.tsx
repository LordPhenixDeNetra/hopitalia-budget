import { useQuery } from '@tanstack/react-query'
import {
  Card,
  Col,
  Descriptions,
  Flex,
  Input,
  Row,
  Select,
  Spin,
  Table,
  Tabs,
  Typography,
} from 'antd'
import { useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useSearchParams } from 'react-router'
import { tableauDirection } from '../../api/genere/budget'
import type {
  Indicateurs,
  MarcheTableau,
  Repartition,
  TableauDirectionParams,
} from '../../api/genere/budget.schemas'
import { Jauge } from '../../composants/Jauge'
import { Montant } from '../../composants/Montant'
import { formaterDate, formaterNombre } from '../../format/format'
import { useOptions } from '../parametrage/PageReferentiel'

const FILTRES: [keyof TableauDirectionParams, string][] = [
  ['etablissementId', 'etablissements'],
  ['centreId', 'centres-responsabilite'],
  ['compteId', 'nomenclature?niveau=PARAGRAPHE'],
  ['sourceId', 'sources-financement'],
  ['fournisseurId', 'fournisseurs'],
  ['contratId', 'contrats'],
]

const BORNES = ['du', 'au'] as const

function Filtre({ nom, chemin }: { nom: string; chemin: string }) {
  const { t } = useTranslation('tableaux')
  const [parametres, setParametres] = useSearchParams()
  const options = useOptions(chemin)
  return (
    <Select
      aria-label={t(`filtres.${nom}`)}
      placeholder={t(`filtres.${nom}`)}
      allowClear
      showSearch
      optionFilterProp="label"
      style={{ minWidth: 200 }}
      value={parametres.get(nom) ?? undefined}
      options={options}
      onChange={(v?: string) => {
        const suivants = new URLSearchParams(parametres)
        if (v) suivants.set(nom, v)
        else suivants.delete(nom)
        setParametres(suivants, { replace: true })
      }}
    />
  )
}

/** Filtres de la section 14.1, gardés dans l'adresse ; l'exercice est obligatoire. */
export function useFiltresTableau(): TableauDirectionParams | undefined {
  const [parametres, setParametres] = useSearchParams()
  const exercices = useOptions('exercices')
  const exerciceId = parametres.get('exerciceId')
  useEffect(() => {
    if (!exerciceId && exercices.length > 0) {
      const suivants = new URLSearchParams(parametres)
      suivants.set('exerciceId', exercices[exercices.length - 1].value)
      setParametres(suivants, { replace: true })
    }
  }, [exerciceId, exercices, parametres, setParametres])
  if (!exerciceId) return undefined
  return Object.fromEntries(
    [...parametres.entries()].filter(([, v]) => v),
  ) as unknown as TableauDirectionParams
}

export function BarreFiltres() {
  const { t } = useTranslation('tableaux')
  const [parametres, setParametres] = useSearchParams()
  const exercices = useOptions('exercices')
  const date = (nom: (typeof BORNES)[number]) => (
    <Input
      key={nom}
      type="date"
      aria-label={t(`filtres.${nom}`)}
      style={{ width: 160 }}
      value={parametres.get(nom) ?? ''}
      onChange={(e) => {
        const suivants = new URLSearchParams(parametres)
        if (e.target.value) suivants.set(nom, e.target.value)
        else suivants.delete(nom)
        setParametres(suivants, { replace: true })
      }}
    />
  )
  return (
    <Flex gap="small" wrap align="center">
      <Select
        aria-label={t('filtres.exerciceId')}
        style={{ minWidth: 140 }}
        options={exercices}
        value={parametres.get('exerciceId') ?? undefined}
        onChange={(v: string) => {
          const suivants = new URLSearchParams(parametres)
          suivants.set('exerciceId', v)
          setParametres(suivants, { replace: true })
        }}
      />
      {FILTRES.map(([nom, chemin]) => (
        <Filtre key={nom} nom={nom} chemin={chemin} />
      ))}
      {BORNES.map(date)}
    </Flex>
  )
}

function Chiffre({ libelle, valeur }: { libelle: string; valeur: string }) {
  return (
    <Card size="small">
      <Typography.Text type="secondary">{libelle}</Typography.Text>
      <Typography.Title level={4} style={{ margin: 0 }}>
        <Montant valeur={valeur} />
      </Typography.Title>
    </Card>
  )
}

const CHIFFRES: (keyof Indicateurs)[] = [
  'budgetRevise',
  'engage',
  'disponibleApresEngagements',
  'liquide',
  'paye',
  'resteAPayer',
]
const ETAPES = [
  'engage',
  'commande',
  'receptionne',
  'facture',
  'liquide',
  'transmis',
  'paye',
] as const

function TableRepartition({ lignes }: { lignes: Repartition[] }) {
  const { t } = useTranslation('tableaux')
  const { t: tCommun } = useTranslation()
  const montant = (titre: string, cle: 'engage' | 'liquide' | 'paye' | 'budgetRevise') => ({
    title: t(titre),
    dataIndex: cle,
    align: 'right' as const,
    render: (v?: string | null) => (v ? <Montant valeur={v} /> : ''),
  })
  return (
    <Table<Repartition>
      rowKey={(r) => r.cle ?? '-'}
      size="small"
      pagination={false}
      dataSource={lignes}
      scroll={{ x: 'max-content' }}
      locale={{ emptyText: tCommun('tableau.aucun') }}
      columns={[
        {
          title: t('repartitions.cle'),
          key: 'cle',
          render: (_, r) => r.libelle ?? t('repartitions.nonRenseigne'),
        },
        montant('indicateurs.budgetRevise', 'budgetRevise'),
        montant('indicateurs.engage', 'engage'),
        montant('indicateurs.liquide', 'liquide'),
        montant('indicateurs.paye', 'paye'),
        {
          title: t('indicateurs.tauxEngagement'),
          dataIndex: 'tauxEngagement',
          align: 'right',
          render: (v?: string | null) => (v ? `${v} %` : ''),
        },
      ]}
    />
  )
}

/** Tableau de bord de la direction (T-210 à T-213). */
export function TableauDeBord() {
  const { t, i18n } = useTranslation('tableaux')
  const { t: tCommun } = useTranslation()
  const filtres = useFiltresTableau()
  const { data, isLoading } = useQuery({
    queryKey: ['tableau-direction', filtres],
    queryFn: () => tableauDirection(filtres!),
    enabled: Boolean(filtres),
  })
  const colonnesMarches = [
    {
      title: t('marches.marche'),
      key: 'marche',
      render: (_: unknown, m: MarcheTableau) => (
        <Link to={`/contrats/${m.contratId}`}>{`${m.numero} — ${m.intitule}`}</Link>
      ),
    },
    {
      title: t('marches.consommation'),
      key: 'jauge',
      render: (_: unknown, m: MarcheTableau) => (
        <Jauge libelle={m.numero} taux={m.tauxConsommation} />
      ),
    },
    ...(['montantActualise', 'engage', 'paye', 'resteAEngager'] as const).map((cle) => ({
      title: t(`marches.${cle}`),
      dataIndex: cle,
      align: 'right' as const,
      render: (v: string) => <Montant valeur={v} />,
    })),
    {
      title: t('marches.dateEcheance'),
      dataIndex: 'dateEcheance',
      render: (v?: string | null) => (v ? formaterDate(v, i18n.language) : ''),
    },
  ]

  return (
    <Flex vertical gap="middle">
      <Flex justify="space-between" align="center" wrap gap="small">
        <Typography.Title level={1} style={{ margin: 0 }}>
          {t('titre')}
        </Typography.Title>
        <Link to={{ pathname: '/restes-a-payer', search: window.location.search }}>
          {t('restes.titre')}
        </Link>
      </Flex>
      <Typography.Paragraph>{t('intro')}</Typography.Paragraph>
      <BarreFiltres />
      {isLoading || !data ? (
        <Spin aria-label={tCommun('tableau.chargement')} />
      ) : (
        <>
          <Row gutter={[12, 12]}>
            {CHIFFRES.map((cle) => (
              <Col key={cle} xs={12} md={8} xl={4}>
                <Chiffre libelle={t(`indicateurs.${cle}`)} valeur={String(data.indicateurs[cle])} />
              </Col>
            ))}
          </Row>
          <Row gutter={[16, 16]}>
            <Col xs={24} lg={10}>
              <Card size="small" title={t('chaine.titre')}>
                <Typography.Paragraph type="secondary">{t('chaine.aide')}</Typography.Paragraph>
                <Table
                  rowKey="etape"
                  size="small"
                  pagination={false}
                  dataSource={ETAPES.map((etape) => ({ etape, montant: data.chaine[etape] }))}
                  columns={[
                    {
                      title: t('chaine.etape'),
                      dataIndex: 'etape',
                      render: (e: string) => t(`chaine.${e}`),
                    },
                    {
                      title: t('chaine.montant'),
                      dataIndex: 'montant',
                      align: 'right',
                      render: (v: string) => <Montant valeur={v} />,
                    },
                  ]}
                />
              </Card>
            </Col>
            <Col xs={24} lg={14}>
              <Card size="small" title={t('credits.titre')}>
                <Flex vertical gap="middle">
                  <Jauge libelle={t('credits.ensemble')} taux={data.indicateurs.tauxEngagement} />
                  {data.lignes.map((lg) => (
                    <Jauge
                      key={lg.ligneId}
                      libelle={`${lg.code} — ${lg.libelle}`}
                      taux={lg.indicateurs.tauxEngagement}
                    />
                  ))}
                  <Table
                    rowKey="ligneId"
                    size="small"
                    pagination={false}
                    dataSource={data.lignes}
                    scroll={{ x: 'max-content' }}
                    columns={[
                      { title: t('credits.ligne'), dataIndex: 'code' },
                      ...(['budgetRevise', 'engage', 'liquide', 'paye'] as const).map((cle) => ({
                        title: t(`indicateurs.${cle}`),
                        key: cle,
                        align: 'right' as const,
                        render: (_: unknown, lg: (typeof data.lignes)[number]) => (
                          <Montant valeur={lg.indicateurs[cle]} />
                        ),
                      })),
                      {
                        title: t('indicateurs.tauxEngagement'),
                        key: 'taux',
                        align: 'right',
                        render: (_, lg) =>
                          lg.indicateurs.tauxEngagement ? `${lg.indicateurs.tauxEngagement} %` : '',
                      },
                    ]}
                  />
                </Flex>
              </Card>
            </Col>
          </Row>
          <Card size="small" title={t('operationnel.titre')}>
            <Descriptions
              size="small"
              column={{ xs: 1, md: 2, xl: 3 }}
              items={[
                ...(['tauxEngagement', 'tauxLiquidation', 'tauxPaiement'] as const).map((cle) => ({
                  key: cle,
                  label: t(`indicateurs.${cle}`),
                  children: data.indicateurs[cle] ? `${data.indicateurs[cle]} %` : '',
                })),
                {
                  key: 'enCours',
                  label: t('indicateurs.enCoursValidation'),
                  children: <Montant valeur={data.indicateurs.enCoursValidation} />,
                },
                ...(
                  [
                    'resteAEngagerMarches',
                    'resteContractuelAPayer',
                    'resteAPayerFactures',
                    'montantFacturesEnAttente',
                  ] as const
                ).map((cle) => ({
                  key: cle,
                  label: t(`operationnel.${cle}`),
                  children: <Montant valeur={data.operationnel[cle]} />,
                })),
                {
                  key: 'nombre',
                  label: t('operationnel.facturesEnAttente'),
                  children: data.operationnel.facturesEnAttente,
                },
                ...(['ageMoyenFacturesJours', 'delaiMoyenTraitementJours'] as const).map((cle) => ({
                  key: cle,
                  label: t(`operationnel.${cle}`),
                  children:
                    data.operationnel[cle] === null
                      ? ''
                      : t('operationnel.jours', {
                          nombre: formaterNombre(Number(data.operationnel[cle]), i18n.language),
                        }),
                })),
              ]}
            />
          </Card>
          <Card size="small" title={t('marches.titre')}>
            <Table<MarcheTableau>
              rowKey="contratId"
              size="small"
              pagination={false}
              dataSource={data.marches}
              scroll={{ x: 'max-content' }}
              columns={colonnesMarches}
              locale={{ emptyText: tCommun('tableau.aucun') }}
            />
          </Card>
          <Card size="small" title={t('repartitions.titre')}>
            <Tabs
              items={(['compte', 'service', 'nature', 'fournisseur'] as const).map((cle) => ({
                key: cle,
                label: t(`repartitions.${cle}`),
                children: <TableRepartition lignes={data.repartitions[cle]} />,
              }))}
            />
          </Card>
        </>
      )}
    </Flex>
  )
}
