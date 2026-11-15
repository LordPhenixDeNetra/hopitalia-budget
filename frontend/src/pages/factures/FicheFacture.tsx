import { MinusCircleOutlined, PlusOutlined } from '@ant-design/icons'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  App,
  Button,
  Card,
  Descriptions,
  Drawer,
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
} from 'antd'
import type { ColumnsType } from 'antd/es/table/interface'
import { useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router'
import { useAfficherErreur } from '../../api/erreurs'
import {
  demanderDerogationLiquidation,
  lireControlesLiquidation,
  lireRapprochement,
  liquider,
  listerLiquidations,
  listerRapprochements,
  obtenirEngagement,
  obtenirFacture,
  rejeterFacture,
  resoumettre,
  retournerFacture,
  validerRapprochement,
} from '../../api/genere/budget'
import type {
  FactureSortie,
  LiquidationCreation,
  LiquidationSortie,
  NatureDerogation,
  ResultatControleSortie,
} from '../../api/genere/budget.schemas'
import { useAProfil } from '../../auth/session'
import { BadgeStatut, type Ton } from '../../composants/BadgeStatut'
import { Montant } from '../../composants/Montant'
import { Pieces } from '../../composants/workflow/Pieces'
import { Validations } from '../../composants/workflow/Validations'
import { formaterDate, formaterDateHeure } from '../../format/format'
import { useOptions } from '../parametrage/PageReferentiel'
import { AGENT_FINANCIER, FormulaireFacture, TONS_FACTURE } from './Factures'

const TONS_LIQUIDATION: Record<string, Ton> = {
  BROUILLON: 'neutre',
  SOUMIS: 'info',
  EN_VALIDATION: 'attention',
  A_CORRIGER: 'attention',
  VALIDE: 'succes',
  REJETE: 'erreur',
}
const TYPES_DEDUCTION = [
  'RETENUE_GARANTIE',
  'AVANCE_RECUPEREE',
  'RETENUE_SOURCE',
  'PENALITE',
  'REFACTION',
  'AUTRE',
]
const MODIFIABLES = ['BROUILLON', 'A_CORRIGER']
// États où la facture peut encore être corrigée, retournée ou rejetée (côté serveur : FACTURE_NON_TRAITABLE).
const CORRIGEABLES = ['RECUE', 'RETOURNEE']
const TRAITABLES = ['RECUE', 'EN_CONTROLE']

type Options = { value: string; label: string }[]

/** Libellé d'une imputation : la ligne budgétaire qu'elle consomme. */
function useImputations(facture: FactureSortie): Options {
  const lignes = useOptions('lignes-budgetaires')
  const { data: engagement } = useQuery({
    queryKey: ['engagement', facture.engagementId],
    queryFn: () => obtenirEngagement(facture.engagementId),
  })
  return (engagement?.imputations ?? []).map((i) => ({
    value: i.id,
    label: lignes.find((l) => l.value === i.ligneId)?.label ?? i.ligneId,
  }))
}

/** Saisie d'une liquidation en brouillon : une imputation, ses réceptions et ses déductions (T-174 à T-176). */
function FormulaireLiquidation({
  facture,
  imputations,
  fermer,
  creee,
}: {
  facture: FactureSortie
  imputations: Options
  fermer: () => void
  creee: (l: LiquidationSortie) => void
}) {
  const { t } = useTranslation('factures')
  const { t: tCommun } = useTranslation()
  const { message } = App.useApp()
  const afficherErreur = useAfficherErreur()
  const [formulaire] = Form.useForm<LiquidationCreation>()
  const [cle] = useState(() => crypto.randomUUID())
  const receptions = useOptions(
    facture.bonCommandeId ? `bons-commande/${facture.bonCommandeId}/receptions` : undefined,
  )
  const envoi = useMutation({
    mutationFn: (v: LiquidationCreation) =>
      liquider(
        facture.id,
        {
          ...v,
          observations: v.observations || null,
          deductions: (v.deductions ?? []).map((d) => ({
            ...d,
            montant: d.montant || null,
            taux: d.taux || null,
          })),
        },
        { headers: { 'Idempotency-Key': cle } },
      ),
    onSuccess: (l) => {
      void message.success(t('liquidations.creee'))
      creee(l)
    },
    onError: (erreur) => afficherErreur(erreur, formulaire),
  })
  const requis = [{ required: true, message: tCommun('connexion.obligatoire') }]

  return (
    <Drawer
      open
      size="large"
      title={t('liquidations.liquider')}
      onClose={fermer}
      extra={
        <Button type="primary" loading={envoi.isPending} onClick={() => formulaire.submit()}>
          {tCommun('actions.enregistrer')}
        </Button>
      }
    >
      <Form
        form={formulaire}
        layout="vertical"
        initialValues={{
          imputationId: imputations.length === 1 ? imputations[0].value : undefined,
          montantBase: facture.resteAPayer,
          receptionIds: [],
          deductions: [],
        }}
        onFinish={(v) => envoi.mutate(v)}
      >
        <Typography.Paragraph type="secondary">{t('liquidations.aide')}</Typography.Paragraph>
        <Form.Item name="imputationId" label={t('liquidations.imputationId')} rules={requis}>
          <Select options={imputations} />
        </Form.Item>
        <Flex gap="middle" wrap>
          <Form.Item
            name="dateLiquidation"
            label={t('liquidations.dateLiquidation')}
            rules={requis}
          >
            <Input type="date" />
          </Form.Item>
          <Form.Item name="montantBase" label={t('liquidations.montantBase')} rules={requis}>
            <Input inputMode="decimal" />
          </Form.Item>
        </Flex>
        <Form.Item name="receptionIds" label={t('liquidations.receptionIds')}>
          <Select mode="multiple" options={receptions} optionFilterProp="label" />
        </Form.Item>
        <Form.Item name="observations" label={t('liquidations.observations')}>
          <Input.TextArea maxLength={1000} />
        </Form.Item>
        <Typography.Text strong>{t('liquidations.deductions')}</Typography.Text>
        <Form.List name="deductions">
          {(lignes, { add, remove }) => (
            <>
              {lignes.map((c) => (
                <Space key={c.key} align="baseline" wrap>
                  <Form.Item name={[c.name, 'type']} rules={requis}>
                    <Select
                      aria-label={t('liquidations.typeDeduction')}
                      placeholder={t('liquidations.typeDeduction')}
                      style={{ minWidth: 180 }}
                      options={TYPES_DEDUCTION.map((v) => ({ value: v, label: t(`valeurs.${v}`) }))}
                    />
                  </Form.Item>
                  <Form.Item name={[c.name, 'montant']}>
                    <Input
                      aria-label={t('liquidations.montant')}
                      placeholder={t('liquidations.montant')}
                      inputMode="decimal"
                      style={{ width: 170 }}
                    />
                  </Form.Item>
                  <Form.Item name={[c.name, 'taux']}>
                    <Input
                      aria-label={t('liquidations.taux')}
                      placeholder={t('liquidations.taux')}
                      inputMode="decimal"
                      style={{ width: 90 }}
                    />
                  </Form.Item>
                  <Form.Item name={[c.name, 'motif']}>
                    <Input
                      aria-label={t('liquidations.motifDeduction')}
                      placeholder={t('liquidations.motifDeduction')}
                      maxLength={500}
                    />
                  </Form.Item>
                  <Button
                    type="text"
                    aria-label={t('liquidations.retirer')}
                    icon={<MinusCircleOutlined aria-hidden />}
                    onClick={() => remove(c.name)}
                  />
                </Space>
              ))}
              <Button
                type="dashed"
                icon={<PlusOutlined aria-hidden />}
                onClick={() => add({ type: 'RETENUE_GARANTIE' })}
              >
                {t('liquidations.ajouterDeduction')}
              </Button>
            </>
          )}
        </Form.List>
      </Form>
    </Drawer>
  )
}

/** Détail d'une liquidation : montants 6.3, contrôles, dérogation, circuit et pièces (T-177, T-178). */
function DetailLiquidation({
  liquidation,
  imputations,
  fermer,
  rafraichir,
}: {
  liquidation: LiquidationSortie
  imputations: Options
  fermer: () => void
  rafraichir: () => void
}) {
  const { t, i18n } = useTranslation('factures')
  const { t: tCommun } = useTranslation()
  const { t: tEngagements } = useTranslation('engagements')
  const { message } = App.useApp()
  const afficherErreur = useAfficherErreur()
  const client = useQueryClient()
  const [formulaire] = Form.useForm()
  const [demande, setDemande] = useState<ResultatControleSortie>()
  const estAgent = useAProfil(AGENT_FINANCIER)
  const peutDeposer = useAProfil([...AGENT_FINANCIER, 'VAL', 'ORD'])
  const modifiable = MODIFIABLES.includes(liquidation.statut)
  const { data: resultats = [] } = useQuery({
    queryKey: ['controles-liquidation', liquidation.id],
    queryFn: () => lireControlesLiquidation(liquidation.id),
  })
  const actualiser = () => {
    void client.invalidateQueries({ queryKey: ['controles-liquidation', liquidation.id] })
    rafraichir()
  }
  const soumission = useMutation({
    mutationFn: () => resoumettre('liquidations', liquidation.id),
    onSuccess: () => {
      void message.success(t('liquidations.soumise'))
      actualiser()
    },
    onError: (erreur) => afficherErreur(erreur),
  })
  const derogation = useMutation({
    mutationFn: (v: { montantDepassement: string; motif: string }) =>
      demanderDerogationLiquidation(liquidation.id, {
        ...v,
        nature: demande!.nature as NatureDerogation,
      }),
    onSuccess: () => {
      void message.success(t('controles.derogationDemandee'))
      setDemande(undefined)
      actualiser()
    },
    onError: (erreur) => afficherErreur(erreur, formulaire),
  })
  const etat = (r: ResultatControleSortie) => {
    const [ton, cle]: [Ton, string] = r.leve
      ? ['succes', 'leve']
      : r.bloquant
        ? ['erreur', 'bloquant']
        : ['attention', 'alerte']
    return <BadgeStatut ton={ton} libelle={t(`controles.${cle}`)} />
  }
  const details = (r: ResultatControleSortie) =>
    Object.entries(r.details)
      .filter(([, v]) => v)
      .map(([k, v]) => `${t(`controles.${k}`, { defaultValue: k })} : ${v}`)
      .join(' ; ')
  const montants: [string, string][] = [
    ['montantBase', liquidation.montantBase],
    ['montantLiquide', liquidation.montantLiquide],
    ['deductionsTotal', liquidation.deductionsTotal],
    ['netAPayer', liquidation.netAPayer],
    ['consommationBudgetaire', liquidation.consommationBudgetaire],
  ]
  const requis = [{ required: true, message: tCommun('connexion.obligatoire') }]

  return (
    <Drawer open size="large" title={liquidation.numero} onClose={fermer}>
      <Flex vertical gap="large">
        <Space wrap>
          <BadgeStatut
            ton={TONS_LIQUIDATION[liquidation.statut] ?? 'neutre'}
            libelle={t(`valeurs.${liquidation.statut}`)}
          />
          {estAgent && modifiable && (
            <Button
              type="primary"
              loading={soumission.isPending}
              onClick={() => soumission.mutate()}
            >
              {t('liquidations.soumettre')}
            </Button>
          )}
        </Space>
        <Descriptions
          bordered
          size="small"
          column={1}
          items={[
            {
              key: 'imputation',
              label: t('liquidations.imputationId'),
              children: imputations.find((i) => i.value === liquidation.imputationId)?.label,
            },
            {
              key: 'date',
              label: t('liquidations.dateLiquidation'),
              children: formaterDate(liquidation.dateLiquidation, i18n.language),
            },
            ...montants.map(([k, v]) => ({
              key: k,
              label: t(`liquidations.${k}`),
              children: <Montant valeur={v} />,
            })),
          ]}
        />
        <Table
          rowKey={(d) => `${d.type}-${d.montant}`}
          size="small"
          pagination={false}
          dataSource={liquidation.deductions}
          locale={{ emptyText: tCommun('tableau.aucun') }}
          scroll={{ x: 'max-content' }}
          columns={[
            {
              title: t('liquidations.typeDeduction'),
              dataIndex: 'type',
              render: (v: string) => t(`valeurs.${v}`),
            },
            {
              title: t('liquidations.deductionsTotal'),
              dataIndex: 'montant',
              align: 'right',
              render: (v: string) => <Montant valeur={v} />,
            },
            { title: t('liquidations.motifDeduction'), dataIndex: 'motif' },
          ]}
        />
        <Card size="small" title={t('controles.titre')}>
          {resultats.length === 0 ? (
            <BadgeStatut ton="succes" libelle={t('controles.aucun')} />
          ) : (
            <Table<ResultatControleSortie>
              rowKey={(r) => `${r.code}-${details(r)}`}
              size="small"
              pagination={false}
              dataSource={resultats}
              scroll={{ x: 'max-content' }}
              columns={[
                {
                  title: tEngagements('controles.code'),
                  dataIndex: 'code',
                  render: (v: string) => t(`controles.${v}`),
                },
                {
                  title: tEngagements('controles.details'),
                  key: 'details',
                  render: (_, r) => details(r),
                },
                {
                  title: tEngagements('controles.depassement'),
                  dataIndex: 'depassement',
                  align: 'right',
                  render: (v: string) => <Montant valeur={v} />,
                },
                { title: tEngagements('controles.etat'), key: 'etat', render: (_, r) => etat(r) },
                {
                  key: 'actions',
                  render: (_, r) =>
                    estAgent &&
                    modifiable &&
                    !r.leve &&
                    r.nature && (
                      <Button size="small" onClick={() => setDemande(r)}>
                        {t('controles.demander')}
                      </Button>
                    ),
                },
              ]}
            />
          )}
        </Card>
        <Validations ressource="liquidations" id={liquidation.id} surDecision={actualiser} />
        <Pieces ressource="liquidations" id={liquidation.id} peutDeposer={peutDeposer} />
      </Flex>
      <Modal
        open={Boolean(demande)}
        title={`${t('controles.demander')} — ${demande?.nature ? tEngagements(`derogations.${demande.nature}`) : ''}`}
        okText={tCommun('actions.enregistrer')}
        cancelText={tCommun('actions.annuler')}
        confirmLoading={derogation.isPending}
        onOk={() => formulaire.submit()}
        onCancel={() => setDemande(undefined)}
        destroyOnHidden
      >
        <Form
          form={formulaire}
          layout="vertical"
          initialValues={{ montantDepassement: demande?.depassement }}
          onFinish={(v) => derogation.mutate(v)}
        >
          <Form.Item
            name="montantDepassement"
            label={tEngagements('derogations.montantDepassement')}
            rules={requis}
          >
            <Input inputMode="decimal" />
          </Form.Item>
          <Form.Item name="motif" label={tEngagements('derogations.motif')} rules={requis}>
            <Input.TextArea maxLength={500} />
          </Form.Item>
        </Form>
      </Modal>
    </Drawer>
  )
}

/** Liquidations de la facture, une par imputation (RG-17). */
function Liquidations({ facture, rafraichir }: { facture: FactureSortie; rafraichir: () => void }) {
  const { t, i18n } = useTranslation('factures')
  const { t: tCommun } = useTranslation()
  const client = useQueryClient()
  const estAgent = useAProfil(AGENT_FINANCIER)
  const imputations = useImputations(facture)
  const [saisie, setSaisie] = useState(false)
  const [ouverte, setOuverte] = useState<string>()
  const { data: liquidations = [] } = useQuery({
    queryKey: ['liquidations', facture.id],
    queryFn: () => listerLiquidations(facture.id),
  })
  const actualiser = () => {
    void client.invalidateQueries({ queryKey: ['liquidations', facture.id] })
    rafraichir()
  }
  const liquidation = liquidations.find((l) => l.id === ouverte)
  const colonnes: ColumnsType<LiquidationSortie> = [
    { title: t('liquidations.numero'), dataIndex: 'numero' },
    {
      title: t('liquidations.dateLiquidation'),
      dataIndex: 'dateLiquidation',
      render: (v: string) => formaterDate(v, i18n.language),
    },
    {
      title: t('liquidations.montantLiquide'),
      dataIndex: 'montantLiquide',
      align: 'right',
      render: (v: string) => <Montant valeur={v} />,
    },
    {
      title: t('liquidations.netAPayer'),
      dataIndex: 'netAPayer',
      align: 'right',
      render: (v: string) => <Montant valeur={v} />,
    },
    {
      title: t('liquidations.statut'),
      dataIndex: 'statut',
      render: (v: string) => (
        <BadgeStatut ton={TONS_LIQUIDATION[v] ?? 'neutre'} libelle={t(`valeurs.${v}`)} />
      ),
    },
    {
      key: 'actions',
      render: (_, l) => (
        <Button size="small" onClick={() => setOuverte(l.id)}>
          {t('liquidations.detail')}
        </Button>
      ),
    },
  ]

  return (
    <Flex vertical gap="middle">
      {estAgent && TRAITABLES.includes(facture.statut) && facture.type !== 'AVOIR' && (
        <Button type="primary" style={{ alignSelf: 'flex-start' }} onClick={() => setSaisie(true)}>
          {t('liquidations.liquider')}
        </Button>
      )}
      <Table<LiquidationSortie>
        rowKey="id"
        columns={colonnes}
        dataSource={liquidations}
        pagination={false}
        scroll={{ x: 'max-content' }}
        locale={{ emptyText: tCommun('tableau.aucun') }}
      />
      {saisie && (
        <FormulaireLiquidation
          facture={facture}
          imputations={imputations}
          fermer={() => setSaisie(false)}
          creee={(l) => {
            setSaisie(false)
            actualiser()
            setOuverte(l.id)
          }}
        />
      )}
      {liquidation && (
        <DetailLiquidation
          liquidation={liquidation}
          imputations={imputations}
          fermer={() => setOuverte(undefined)}
          rafraichir={actualiser}
        />
      )}
    </Flex>
  )
}

/** Rapprochement commande, réception, facture et paiement (T-180). */
function Rapprochement({ facture }: { facture: FactureSortie }) {
  const { t, i18n } = useTranslation('factures')
  const { t: tCommun } = useTranslation()
  const { message } = App.useApp()
  const afficherErreur = useAfficherErreur()
  const client = useQueryClient()
  const [formulaire] = Form.useForm()
  const estAgent = useAProfil(AGENT_FINANCIER)
  const { data: ecarts } = useQuery({
    queryKey: ['rapprochement', facture.id],
    queryFn: () => lireRapprochement(facture.id),
  })
  const { data: historique = [] } = useQuery({
    queryKey: ['rapprochements', facture.id],
    queryFn: () => listerRapprochements(facture.id),
  })
  const validation = useMutation({
    mutationFn: (v: { explication?: string }) =>
      validerRapprochement(facture.id, { explication: v.explication || null }),
    onSuccess: () => {
      void message.success(t('rapprochement.valide'))
      formulaire.resetFields()
      void client.invalidateQueries({ queryKey: ['rapprochements', facture.id] })
    },
    onError: (erreur) => afficherErreur(erreur, formulaire),
  })
  if (!ecarts) return <Spin />
  const cles = [
    'commande',
    'receptionne',
    'facture',
    'paye',
    'ecartCommandeReception',
    'ecartReceptionFacture',
    'ecartFacturePaiement',
  ] as const

  return (
    <Flex vertical gap="middle">
      {ecarts.sansEcart ? (
        <BadgeStatut ton="succes" libelle={t('rapprochement.sansEcart')} />
      ) : (
        <BadgeStatut ton="attention" libelle={t('rapprochement.avecEcart')} />
      )}
      <Descriptions
        bordered
        size="small"
        column={{ xs: 1, md: 2 }}
        items={cles.map((k) => ({
          key: k,
          label: t(`rapprochement.${k}`),
          children: <Montant valeur={ecarts[k]} />,
        }))}
      />
      {estAgent && (
        <Form form={formulaire} layout="vertical" onFinish={(v) => validation.mutate(v)}>
          <Form.Item name="explication" label={t('rapprochement.explication')}>
            <Input.TextArea maxLength={1000} />
          </Form.Item>
          <Button htmlType="submit" loading={validation.isPending}>
            {t('rapprochement.valider')}
          </Button>
        </Form>
      )}
      <Typography.Title level={4}>{t('rapprochement.historique')}</Typography.Title>
      <Table
        rowKey="id"
        size="small"
        pagination={false}
        dataSource={historique}
        scroll={{ x: 'max-content' }}
        locale={{ emptyText: tCommun('tableau.aucun') }}
        columns={[
          {
            title: t('rapprochement.date'),
            dataIndex: 'dateRapprochement',
            render: (v: string) => formaterDateHeure(v, i18n.language),
          },
          { title: t('rapprochement.explication'), dataIndex: 'explication' },
          { title: t('rapprochement.par'), dataIndex: 'creeParCode' },
        ]}
      />
    </Flex>
  )
}

/** Fiche d'une facture : informations, liquidations, rapprochement et facture numérisée (T-181). */
export function FicheFacture() {
  const { id = '' } = useParams()
  const { t, i18n } = useTranslation('factures')
  const { t: tCommun } = useTranslation()
  const { message } = App.useApp()
  const afficherErreur = useAfficherErreur()
  const client = useQueryClient()
  const [motif] = Form.useForm<{ motif: string }>()
  const estAgent = useAProfil(AGENT_FINANCIER)
  const peutDeposer = useAProfil([...AGENT_FINANCIER, 'VAL', 'ORD'])
  const [edition, setEdition] = useState(false)
  const [action, setAction] = useState<'retourner' | 'rejeter'>()
  const {
    data: facture,
    isLoading,
    error,
  } = useQuery({ queryKey: ['facture', id], queryFn: () => obtenirFacture(id) })
  const rafraichir = () => {
    void client.invalidateQueries({ queryKey: ['facture', id] })
    void client.invalidateQueries({ queryKey: ['rapprochement', id] })
  }
  const decision = useMutation({
    mutationFn: (v: { motif: string }) =>
      action === 'rejeter' ? rejeterFacture(id, v) : retournerFacture(id, v),
    onSuccess: (f) => {
      void message.success(t(action === 'rejeter' ? 'rejetee' : 'retournee'))
      client.setQueryData(['facture', id], f)
      setAction(undefined)
      motif.resetFields()
    },
    onError: (erreur) => afficherErreur(erreur, motif),
  })

  if (isLoading) return <Spin aria-label={tCommun('tableau.chargement')} />
  if (error || !facture) {
    return (
      <Result
        status="404"
        title={tCommun('introuvable.titre')}
        subTitle={tCommun('introuvable.detail')}
        extra={<Link to="/factures">{tCommun('menu.factures')}</Link>}
      />
    )
  }
  const date = (v?: string | null) => (v ? formaterDate(v, i18n.language) : '')
  const informations: [string, ReactNode][] = [
    ['type', t(`valeurs.${facture.type}`)],
    ['objet', facture.objet],
    ['dateEmission', date(facture.dateEmission)],
    ['dateReception', date(facture.dateReception)],
    ['dateEcheance', date(facture.dateEcheance)],
    ['dateLimiteTraitement', date(facture.dateLimiteTraitement)],
    ['periodeRattachement', facture.periodeRattachement],
    ['montantHt', <Montant key="ht" valeur={facture.montantHt} />],
    ['montantTaxes', <Montant key="tx" valeur={facture.montantTaxes} />],
    ['montantTtc', <Montant key="ttc" valeur={facture.montantTtc} />],
    ['liquideValide', <Montant key="liq" valeur={facture.liquideValide} />],
    ['resteAPayer', <Montant key="rap" valeur={facture.resteAPayer} />],
    ...(facture.numeroDecompte
      ? ([
          ['numeroDecompte', facture.numeroDecompte],
          [
            'montantCumuleDecomptes',
            <Montant key="cum" valeur={facture.montantCumuleDecomptes ?? '0'} />,
          ],
        ] as [string, ReactNode][])
      : []),
    ['motifStatut', facture.motifStatut],
    ['motifLeveeDoublon', facture.motifLeveeDoublon],
  ]
  const onglets = [
    {
      key: 'informations',
      label: t('onglets.informations'),
      children: (
        <Descriptions
          bordered
          size="small"
          column={{ xs: 1, md: 2 }}
          items={informations
            .filter(([, v]) => v !== null && v !== '')
            .map(([k, v]) => ({ key: k, label: t(`champs.${k}`), children: v }))}
        />
      ),
    },
    {
      key: 'liquidations',
      label: t('onglets.liquidations'),
      children: <Liquidations facture={facture} rafraichir={rafraichir} />,
    },
    {
      key: 'rapprochement',
      label: t('onglets.rapprochement'),
      children: <Rapprochement facture={facture} />,
    },
    {
      key: 'pieces',
      label: t('onglets.pieces'),
      children: <Pieces ressource="factures" id={facture.id} peutDeposer={peutDeposer} />,
    },
  ]

  return (
    <Flex vertical gap="middle">
      <Flex justify="space-between" align="center" wrap gap="small">
        <Typography.Title level={1} style={{ margin: 0 }}>
          {facture.numero} — {facture.objet}
        </Typography.Title>
        <Space wrap>
          <BadgeStatut
            ton={TONS_FACTURE[facture.statut] ?? 'neutre'}
            libelle={t(`valeurs.${facture.statut}`)}
          />
          {estAgent && CORRIGEABLES.includes(facture.statut) && (
            <Button onClick={() => setEdition(true)}>{t('corriger')}</Button>
          )}
          {estAgent && TRAITABLES.includes(facture.statut) && (
            <>
              <Button onClick={() => setAction('retourner')}>{t('retourner')}</Button>
              <Button danger onClick={() => setAction('rejeter')}>
                {t('rejeter')}
              </Button>
            </>
          )}
        </Space>
      </Flex>
      <Link to={`/engagements/${facture.engagementId}`}>{tCommun('menu.engagements')}</Link>
      <Tabs items={onglets} destroyOnHidden />
      {edition && (
        <FormulaireFacture
          facture={facture}
          fermer={() => setEdition(false)}
          enregistree={(f) => {
            client.setQueryData(['facture', id], f)
            setEdition(false)
          }}
        />
      )}
      <Modal
        open={Boolean(action)}
        title={action ? t(action) : ''}
        okText={tCommun('actions.enregistrer')}
        cancelText={tCommun('actions.annuler')}
        confirmLoading={decision.isPending}
        onOk={() => motif.submit()}
        onCancel={() => setAction(undefined)}
        destroyOnHidden
      >
        <Form form={motif} layout="vertical" onFinish={(v) => decision.mutate(v)}>
          <Form.Item
            name="motif"
            label={t('motif')}
            rules={[{ required: true, message: tCommun('connexion.obligatoire') }]}
          >
            <Input.TextArea maxLength={500} />
          </Form.Item>
        </Form>
      </Modal>
    </Flex>
  )
}
