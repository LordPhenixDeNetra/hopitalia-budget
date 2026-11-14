import { MinusCircleOutlined, PlusOutlined, UploadOutlined } from '@ant-design/icons'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Alert,
  App,
  Button,
  Descriptions,
  Flex,
  Form,
  Input,
  Modal,
  Result,
  Select,
  Space,
  Spin,
  Table,
  Tabs,
  Typography,
  Upload,
} from 'antd'
import type { ColumnsType } from 'antd/es/table/interface'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router'
import { appelerApi } from '../../api/client'
import { useAfficherErreur } from '../../api/erreurs'
import {
  creerNotificationCredit,
  getImporterDotationsUrl,
  getListerNotificationsCreditsQueryKey,
  getObtenirSituationQueryKey,
  useListerNotificationsCredits,
  useObtenirBudget,
  useObtenirImportDotations,
  useObtenirSituation,
} from '../../api/genere/budget'
import type {
  DisponibiliteSortie,
  ImportSortie,
  IndicateursSortie,
  NotificationCreation,
} from '../../api/genere/budget.schemas'
import { useAProfil } from '../../auth/session'
import { Montant } from '../../composants/Montant'
import { formaterDate } from '../../format/format'
import { PageReferentiel, useOptions } from '../parametrage/PageReferentiel'
import { RESSOURCES } from '../parametrage/ressources'
import { Revisions } from './Revisions'

type CleMontant = Exclude<keyof IndicateursSortie, `taux${string}`>
type CleTaux = Extract<keyof IndicateursSortie, `taux${string}`>
const MONTANTS: CleMontant[] = [
  'budgetInitial',
  'modificationsPositives',
  'modificationsNegatives',
  'budgetRevise',
  'engage',
  'enCoursValidation',
  'disponibleApresEngagements',
  'disponiblePrevisionnel',
  'liquide',
  'paye',
  'engageRestantALiquider',
  'resteAPayer',
]
const TAUX: CleTaux[] = ['tauxEngagement', 'tauxLiquidation', 'tauxPaiement']
const taux = (v?: string | null) => (v == null ? '' : `${v} %`)

/** Tous les indicateurs d'une ligne ou d'un budget (formules de la section 6.1). */
export function Indicateurs({ valeurs }: { valeurs: IndicateursSortie }) {
  const { t } = useTranslation('budget')
  return (
    <Descriptions
      bordered
      size="small"
      column={{ xs: 1, md: 2, xl: 3 }}
      items={[
        ...MONTANTS.map((c) => ({
          key: c,
          label: t(`indicateurs.${c}`),
          children: <Montant valeur={valeurs[c]} />,
        })),
        ...TAUX.map((c) => ({ key: c, label: t(`indicateurs.${c}`), children: taux(valeurs[c]) })),
      ]}
    />
  )
}

function Situation({ budgetId }: { budgetId: string }) {
  const { t } = useTranslation('budget')
  const { data, isLoading } = useObtenirSituation(budgetId)
  const COLONNES: CleMontant[] = [
    'budgetRevise',
    'engage',
    'disponibleApresEngagements',
    'liquide',
    'paye',
  ]
  const colonnes: ColumnsType<DisponibiliteSortie> = [
    {
      title: t('situation.ligne'),
      key: 'ligne',
      render: (_, l) => (
        <Link to={`/lignes-budgetaires/${l.ligneId}`}>{`${l.code} — ${l.libelle}`}</Link>
      ),
    },
    ...COLONNES.map((c) => ({
      title: t(`indicateurs.${c}`),
      key: c,
      align: 'right' as const,
      render: (_: unknown, l: DisponibiliteSortie) => <Montant valeur={l.indicateurs[c]} />,
    })),
    {
      title: t('indicateurs.tauxEngagement'),
      key: 'taux',
      align: 'right',
      render: (_, l) => taux(l.indicateurs.tauxEngagement),
    },
  ]
  if (isLoading || !data) return <Spin />
  return (
    <Flex vertical gap="middle">
      <Typography.Title level={3}>{t('situation.total')}</Typography.Title>
      <Indicateurs valeurs={data.totaux} />
      <Table<DisponibiliteSortie>
        columns={colonnes}
        dataSource={data.lignes}
        rowKey="ligneId"
        pagination={false}
        scroll={{ x: 'max-content' }}
      />
    </Flex>
  )
}

/** Import CSV des dotations : traitement en arrière-plan, suivi jusqu'à la fin (T-089). */
function ImportDotations({ budgetId }: { budgetId: string }) {
  const { t, i18n } = useTranslation('budget')
  const afficherErreur = useAfficherErreur()
  const client = useQueryClient()
  const [importId, setImportId] = useState('')
  const envoi = useMutation({
    mutationFn: async (fichier: File) =>
      appelerApi<ImportSortie>(getImporterDotationsUrl(budgetId), {
        method: 'POST',
        headers: { 'Content-Type': 'text/csv' },
        body: await fichier.text(),
      }),
    onSuccess: (travail) => setImportId(travail.id),
    onError: (erreur) => afficherErreur(erreur),
  })
  const { data: travail } = useObtenirImportDotations(importId, {
    query: {
      enabled: Boolean(importId),
      refetchInterval: (requete) => (requete.state.data?.statut === 'TERMINE' ? false : 1000),
    },
  })
  const termine = travail?.statut === 'TERMINE'
  useEffect(() => {
    if (termine) void client.invalidateQueries({ queryKey: getObtenirSituationQueryKey(budgetId) })
  }, [termine, budgetId, client])

  return (
    <Flex vertical gap="middle">
      <Typography.Paragraph>{t('import.intro')}</Typography.Paragraph>
      <Upload
        accept=".csv,text/csv"
        showUploadList={false}
        beforeUpload={(fichier) => {
          envoi.mutate(fichier)
          return false
        }}
      >
        <Button icon={<UploadOutlined aria-hidden />} loading={envoi.isPending}>
          {t('import.choisir')}
        </Button>
      </Upload>
      {travail && (
        <>
          <Alert
            showIcon
            type={
              travail.statut !== 'TERMINE'
                ? 'info'
                : travail.anomalies.length
                  ? 'warning'
                  : 'success'
            }
            title={`${t('import.statut')} : ${t(`import.${travail.statut}`)} — ${formaterDate(travail.creeLe, i18n.language)}`}
            description={t('import.lignesImportees', { nombre: travail.lignesImportees })}
          />
          {travail.anomalies.length > 0 && (
            <Table
              rowKey={(a) => `${a.ligne}-${a.code}-${a.valeur}`}
              dataSource={travail.anomalies}
              pagination={false}
              columns={[
                { title: t('import.ligne'), dataIndex: 'ligne' },
                {
                  title: t('import.code'),
                  dataIndex: 'code',
                  render: (c: string) =>
                    t(`anomalies.${c}`, { defaultValue: t('anomalies.autre') }),
                },
                { title: t('import.valeur'), dataIndex: 'valeur' },
              ]}
            />
          )}
        </>
      )}
    </Flex>
  )
}

/** Notifications de crédits et leur répartition par ligne (T-093). */
function Notifications({ budgetId }: { budgetId: string }) {
  const { t, i18n } = useTranslation('budget')
  const { t: tCommun } = useTranslation()
  const { message } = App.useApp()
  const afficherErreur = useAfficherErreur()
  const client = useQueryClient()
  const peutEcrire = useAProfil(['RB'])
  const [ouvert, setOuvert] = useState(false)
  const [cle, setCle] = useState(() => crypto.randomUUID())
  const [formulaire] = Form.useForm()
  const lignes = useOptions(`lignes-budgetaires?budgetId=${budgetId}`)
  const sources = useOptions('sources-financement')
  const { data } = useListerNotificationsCredits({ budgetId })
  const envoi = useMutation({
    mutationFn: (v: NotificationCreation) =>
      creerNotificationCredit(v, { headers: { 'Idempotency-Key': cle } }),
    onSuccess: () => {
      void client.invalidateQueries({
        queryKey: getListerNotificationsCreditsQueryKey({ budgetId }),
      })
      void message.success(t('notifications.creee'))
      formulaire.resetFields()
      setCle(crypto.randomUUID())
      setOuvert(false)
    },
    onError: (erreur) => afficherErreur(erreur, formulaire),
  })
  const requis = [{ required: true, message: tCommun('connexion.obligatoire') }]

  return (
    <Flex vertical gap="middle">
      {peutEcrire && (
        <Button type="primary" style={{ alignSelf: 'flex-start' }} onClick={() => setOuvert(true)}>
          {t('notifications.creer')}
        </Button>
      )}
      <Table
        rowKey="id"
        dataSource={data?.donnees ?? []}
        pagination={false}
        scroll={{ x: 'max-content' }}
        columns={[
          { title: t('notifications.reference'), dataIndex: 'reference' },
          {
            title: t('notifications.dateNotification'),
            dataIndex: 'dateNotification',
            render: (v: string) => formaterDate(v, i18n.language),
          },
          { title: t('notifications.objet'), dataIndex: 'objet' },
          {
            title: t('notifications.montant'),
            dataIndex: 'montant',
            align: 'right',
            render: (v: string) => <Montant valeur={v} />,
          },
        ]}
      />
      <Modal
        open={ouvert}
        title={t('notifications.creer')}
        okText={tCommun('actions.enregistrer')}
        cancelText={tCommun('actions.annuler')}
        confirmLoading={envoi.isPending}
        onOk={() => formulaire.submit()}
        onCancel={() => setOuvert(false)}
      >
        <Form
          form={formulaire}
          layout="vertical"
          initialValues={{ lignes: [{}] }}
          onFinish={(v: NotificationCreation) => envoi.mutate({ ...v, budgetId })}
        >
          <Form.Item name="reference" label={t('notifications.reference')} rules={requis}>
            <Input maxLength={50} />
          </Form.Item>
          <Form.Item
            name="dateNotification"
            label={t('notifications.dateNotification')}
            rules={requis}
          >
            <Input type="date" />
          </Form.Item>
          <Form.Item name="objet" label={t('notifications.objet')} rules={requis}>
            <Input maxLength={300} />
          </Form.Item>
          <Form.Item name="sourceId" label={t('notifications.sourceId')} rules={requis}>
            <Select options={sources} />
          </Form.Item>
          <Form.Item name="montant" label={t('notifications.montant')} rules={requis}>
            <Input inputMode="decimal" />
          </Form.Item>
          <Typography.Text>{t('notifications.lignes')}</Typography.Text>
          <Form.List name="lignes">
            {(champs, { add, remove }) => (
              <>
                {champs.map((champ) => (
                  <Space key={champ.key} align="baseline" wrap>
                    <Form.Item name={[champ.name, 'ligneId']} rules={requis}>
                      <Select
                        aria-label={t('notifications.ligneId')}
                        style={{ minWidth: 220 }}
                        options={lignes}
                      />
                    </Form.Item>
                    <Form.Item name={[champ.name, 'montant']} rules={requis}>
                      <Input aria-label={t('notifications.montant')} inputMode="decimal" />
                    </Form.Item>
                    <Button
                      type="text"
                      aria-label={t('notifications.retirer')}
                      icon={<MinusCircleOutlined aria-hidden />}
                      onClick={() => remove(champ.name)}
                    />
                  </Space>
                ))}
                <Button type="dashed" icon={<PlusOutlined aria-hidden />} onClick={() => add()}>
                  {t('notifications.ajouterLigne')}
                </Button>
              </>
            )}
          </Form.List>
        </Form>
      </Modal>
    </Flex>
  )
}

/** Fiche budget (/budgets/:id) : situation, lignes, import, notifications, révisions. */
export function FicheBudget() {
  const { id = '' } = useParams()
  const { t } = useTranslation('budget')
  const { t: tCommun } = useTranslation()
  const { t: tParam } = useTranslation('parametrage')
  const peutSaisir = useAProfil(['RB'])
  const { data: budget, isLoading, error } = useObtenirBudget(id)

  if (isLoading) return <Spin aria-label={tCommun('tableau.chargement')} />
  if (error || !budget) {
    return (
      <Result
        status="404"
        title={tCommun('introuvable.titre')}
        subTitle={tCommun('introuvable.detail')}
        extra={<Link to="/budgets">{tCommun('menu.budgets')}</Link>}
      />
    )
  }
  const onglets = [
    { key: 'situation', label: t('onglets.situation'), children: <Situation budgetId={id} /> },
    {
      key: 'lignes',
      label: t('onglets.lignes'),
      children: (
        <PageReferentiel
          definition={RESSOURCES['lignes-budgetaires']!}
          fixes={{ budgetId: id }}
          titre={false}
        />
      ),
    },
    ...(peutSaisir
      ? [{ key: 'import', label: t('onglets.import'), children: <ImportDotations budgetId={id} /> }]
      : []),
    {
      key: 'notifications',
      label: t('onglets.notifications'),
      children: <Notifications budgetId={id} />,
    },
    { key: 'revisions', label: t('onglets.revisions'), children: <Revisions budgetId={id} /> },
  ]

  return (
    <Flex vertical gap="middle">
      <Typography.Title level={1}>
        {budget.reference} — {tParam(`valeurs.${budget.type}`)}
      </Typography.Title>
      <Tabs items={onglets} destroyOnHidden />
    </Flex>
  )
}

/** Liste des budgets (/budgets) : écran générique de la ressource. */
export function Budgets() {
  return <PageReferentiel definition={RESSOURCES.budgets!} />
}
