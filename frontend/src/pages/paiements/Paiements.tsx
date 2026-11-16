import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  App,
  Button,
  Checkbox,
  Descriptions,
  Drawer,
  Flex,
  Form,
  Input,
  Modal,
  Select,
  Space,
  Table,
  Tabs,
  Typography,
} from 'antd'
import type { ColumnsType } from 'antd/es/table/interface'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'
import { useAfficherErreur } from '../../api/erreurs'
import {
  annulerPaiement,
  deciderOrdonnancement,
  enregistrerPaiement,
  listerLiquidationsATraiter,
  listerOrdonnancements,
  listerPaiements,
  ordonnancer,
} from '../../api/genere/budget'
import type {
  ActionOrdonnancement,
  OrdonnancementCreation,
  OrdonnancementSortie,
  PaiementSortie,
} from '../../api/genere/budget.schemas'
import { useAProfil } from '../../auth/session'
import { BadgeStatut, type Ton } from '../../composants/BadgeStatut'
import { Montant } from '../../composants/Montant'
import { additionnerMontants, formaterDate } from '../../format/format'
import { useOptions } from '../parametrage/PageReferentiel'

const TONS: Record<string, Ton> = {
  PREPARE: 'neutre',
  TRANSMIS: 'info',
  COMPLEMENT_DEMANDE: 'attention',
  SUSPENDU: 'attention',
  REJETE: 'erreur',
  PRIS_EN_CHARGE: 'succes',
  EXECUTE: 'succes',
  ANNULE: 'erreur',
}
// Section 8.3, comme côté serveur : statuts de départ, profil qui décide, motif obligatoire.
const ACTIONS: Record<ActionOrdonnancement, [string[], string, boolean]> = {
  TRANSMETTRE: [['PREPARE'], 'ORD', false],
  FOURNIR_COMPLEMENT: [['COMPLEMENT_DEMANDE'], 'ORD', false],
  PRENDRE_EN_CHARGE: [['TRANSMIS'], 'CPT', false],
  DEMANDER_COMPLEMENT: [['TRANSMIS'], 'CPT', true],
  SUSPENDRE: [['TRANSMIS'], 'CPT', true],
  REPRENDRE: [['SUSPENDU'], 'CPT', false],
  REJETER: [['TRANSMIS'], 'CPT', true],
}
const ANNULATION = ['AF', 'VAL', 'ORD']

function Statut({ valeur }: { valeur: string }) {
  const { t } = useTranslation('paiements')
  return <BadgeStatut ton={TONS[valeur] ?? 'neutre'} libelle={t(`valeurs.${valeur}`)} />
}

/** Motif demandé avant une action négative (complément, suspension, rejet, annulation). */
function DemandeMotif({
  titre,
  enCours,
  valider,
  fermer,
}: {
  titre: string
  enCours: boolean
  valider: (motif: string) => void
  fermer: () => void
}) {
  const { t } = useTranslation('paiements')
  const { t: tCommun } = useTranslation()
  const [formulaire] = Form.useForm<{ motif: string }>()
  return (
    <Modal
      open
      title={titre}
      okText={tCommun('actions.enregistrer')}
      cancelText={tCommun('actions.annuler')}
      confirmLoading={enCours}
      onOk={() => formulaire.submit()}
      onCancel={fermer}
    >
      <Form form={formulaire} layout="vertical" onFinish={(v) => valider(v.motif)}>
        <Form.Item
          name="motif"
          label={t('ordonnancements.motif')}
          rules={[{ required: true, message: tCommun('connexion.obligatoire') }]}
        >
          <Input.TextArea maxLength={500} />
        </Form.Item>
      </Form>
    </Modal>
  )
}

/** Préparation d'un ordonnancement : liquidations validées de factures liquidées (EF-ORD-01). */
function FormulaireOrdonnancement({ fermer }: { fermer: () => void }) {
  const { t } = useTranslation('paiements')
  const { t: tCommun } = useTranslation()
  const { message } = App.useApp()
  const afficherErreur = useAfficherErreur()
  const client = useQueryClient()
  const [formulaire] = Form.useForm<OrdonnancementCreation>()
  const [cle] = useState(() => crypto.randomUUID())
  const { data: liquidations = [] } = useQuery({
    queryKey: ['liquidations', 'A_ORDONNANCER'],
    queryFn: () => listerLiquidationsATraiter({ etape: 'A_ORDONNANCER' }),
  })
  const envoi = useMutation({
    mutationFn: (v: OrdonnancementCreation) =>
      ordonnancer(v, { headers: { 'Idempotency-Key': cle } }),
    onSuccess: () => {
      void message.success(t('ordonnancements.prepare'))
      void client.invalidateQueries({ queryKey: ['ordonnancements'] })
      void client.invalidateQueries({ queryKey: ['liquidations'] })
      fermer()
    },
    onError: (erreur) => afficherErreur(erreur, formulaire),
  })
  const requis = [{ required: true, message: tCommun('connexion.obligatoire') }]

  return (
    <Drawer
      open
      size="large"
      title={t('ordonnancements.preparer')}
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
        initialValues={{ typePiece: 'MANDAT', liquidationIds: [] }}
        onFinish={(v) => envoi.mutate(v)}
      >
        <Form.Item name="referencePiece" label={t('ordonnancements.referencePiece')} rules={requis}>
          <Input maxLength={50} />
        </Form.Item>
        <Form.Item name="typePiece" label={t('ordonnancements.typePiece')} rules={requis}>
          <Select
            options={['MANDAT', 'ORDRE_PAIEMENT'].map((v) => ({
              value: v,
              label: t(`valeurs.${v}`),
            }))}
          />
        </Form.Item>
        <Form.Item
          name="serviceDestinataire"
          label={t('ordonnancements.serviceDestinataire')}
          rules={requis}
        >
          <Input maxLength={200} />
        </Form.Item>
        <Form.Item
          name="liquidationIds"
          label={t('ordonnancements.liquidations')}
          rules={[
            { required: true, type: 'array', min: 1, message: tCommun('connexion.obligatoire') },
          ]}
        >
          {liquidations.length === 0 ? (
            <Typography.Text type="secondary">
              {t('ordonnancements.aucuneLiquidation')}
            </Typography.Text>
          ) : (
            <Checkbox.Group>
              <Flex vertical gap="small">
                {liquidations.map((lq) => (
                  <Checkbox key={lq.id} value={lq.id}>
                    <Space wrap>
                      {`${lq.numero} — ${lq.factureNumero}`}
                      <Montant valeur={lq.resteAPayer} />
                    </Space>
                  </Checkbox>
                ))}
              </Flex>
            </Checkbox.Group>
          )}
        </Form.Item>
      </Form>
    </Drawer>
  )
}

/** Détail d'un ordonnancement : liquidations, puis décision de l'ordonnateur ou du comptable. */
function DetailOrdonnancement({
  ordonnancement,
  fermer,
}: {
  ordonnancement: OrdonnancementSortie
  fermer: () => void
}) {
  const { t, i18n } = useTranslation('paiements')
  const { t: tCommun } = useTranslation()
  const { message } = App.useApp()
  const afficherErreur = useAfficherErreur()
  const client = useQueryClient()
  const estOrdonnateur = useAProfil(['ORD'])
  const estComptable = useAProfil(['CPT'])
  const [motive, setMotive] = useState<ActionOrdonnancement>()
  const decision = useMutation({
    mutationFn: (v: { action: ActionOrdonnancement; motif?: string }) =>
      deciderOrdonnancement(ordonnancement.id, v),
    onSuccess: () => {
      void message.success(t('ordonnancements.decision'))
      setMotive(undefined)
      void client.invalidateQueries({ queryKey: ['ordonnancements'] })
      void client.invalidateQueries({ queryKey: ['liquidations'] })
    },
    onError: (erreur) => afficherErreur(erreur),
  })
  const possibles = (Object.keys(ACTIONS) as ActionOrdonnancement[]).filter((a) => {
    const [depuis, profil] = ACTIONS[a]
    const habilite = profil === 'ORD' ? estOrdonnateur : estComptable
    return habilite && depuis.includes(ordonnancement.statut)
  })

  return (
    <Drawer open size="large" title={ordonnancement.referencePiece} onClose={fermer}>
      <Flex vertical gap="large">
        <Space wrap>
          <Statut valeur={ordonnancement.statut} />
          {possibles.map((a) => (
            <Button
              key={a}
              danger={a === 'REJETER'}
              type={ACTIONS[a][2] ? 'default' : 'primary'}
              loading={decision.isPending && decision.variables?.action === a}
              onClick={() => (ACTIONS[a][2] ? setMotive(a) : decision.mutate({ action: a }))}
            >
              {t(`actions.${a}`)}
            </Button>
          ))}
        </Space>
        <Descriptions
          bordered
          size="small"
          column={1}
          items={[
            {
              key: 'type',
              label: t('ordonnancements.typePiece'),
              children: t(`valeurs.${ordonnancement.typePiece}`),
            },
            {
              key: 'service',
              label: t('ordonnancements.serviceDestinataire'),
              children: ordonnancement.serviceDestinataire,
            },
            {
              key: 'date',
              label: t('ordonnancements.dateTransmission'),
              children: ordonnancement.dateTransmission
                ? formaterDate(ordonnancement.dateTransmission, i18n.language)
                : '',
            },
            {
              key: 'montant',
              label: t('ordonnancements.montant'),
              children: <Montant valeur={ordonnancement.montant} />,
            },
            ...(ordonnancement.motifStatut
              ? [
                  {
                    key: 'motif',
                    label: t('ordonnancements.motif'),
                    children: ordonnancement.motifStatut,
                  },
                ]
              : []),
          ]}
        />
        <Table
          rowKey="liquidationId"
          size="small"
          pagination={false}
          dataSource={ordonnancement.lignes}
          scroll={{ x: 'max-content' }}
          columns={[
            { title: t('ordonnancements.liquidation'), dataIndex: 'liquidationNumero' },
            {
              title: t('ordonnancements.facture'),
              key: 'facture',
              render: (_, l) => <Link to={`/factures/${l.factureId}`}>{l.factureNumero}</Link>,
            },
            {
              title: t('ordonnancements.montant'),
              dataIndex: 'montant',
              align: 'end',
              render: (v: string) => <Montant valeur={v} />,
            },
          ]}
          locale={{ emptyText: tCommun('tableau.aucun') }}
        />
      </Flex>
      {motive && (
        <DemandeMotif
          titre={t(`actions.${motive}`)}
          enCours={decision.isPending}
          valider={(motif) => decision.mutate({ action: motive, motif })}
          fermer={() => setMotive(undefined)}
        />
      )}
    </Drawer>
  )
}

function Ordonnancements() {
  const { t, i18n } = useTranslation('paiements')
  const { t: tCommun } = useTranslation()
  const estOrdonnateur = useAProfil(['ORD'])
  const [saisie, setSaisie] = useState(false)
  const [ouvert, setOuvert] = useState<string>()
  const { data, isFetching } = useQuery({
    queryKey: ['ordonnancements'],
    queryFn: () => listerOrdonnancements({ taille: 100 }),
  })
  const ordonnancements = data?.donnees ?? []
  const ordonnancement = ordonnancements.find((o) => o.id === ouvert)
  const colonnes: ColumnsType<OrdonnancementSortie> = [
    { title: t('ordonnancements.referencePiece'), dataIndex: 'referencePiece' },
    {
      title: t('ordonnancements.dateTransmission'),
      dataIndex: 'dateTransmission',
      render: (v?: string | null) => (v ? formaterDate(v, i18n.language) : ''),
    },
    {
      title: t('ordonnancements.montant'),
      dataIndex: 'montant',
      align: 'end',
      render: (v: string) => <Montant valeur={v} />,
    },
    {
      title: t('ordonnancements.statut'),
      dataIndex: 'statut',
      render: (v: string) => <Statut valeur={v} />,
    },
    {
      key: 'actions',
      render: (_, o) => (
        <Button size="small" onClick={() => setOuvert(o.id)}>
          {t('ordonnancements.detail')}
        </Button>
      ),
    },
  ]

  return (
    <Flex vertical gap="middle">
      {estOrdonnateur && (
        <Button type="primary" style={{ alignSelf: 'flex-start' }} onClick={() => setSaisie(true)}>
          {t('ordonnancements.preparer')}
        </Button>
      )}
      <Table<OrdonnancementSortie>
        rowKey="id"
        loading={isFetching}
        columns={colonnes}
        dataSource={ordonnancements}
        pagination={false}
        scroll={{ x: 'max-content' }}
        locale={{ emptyText: tCommun('tableau.aucun') }}
      />
      {saisie && <FormulaireOrdonnancement fermer={() => setSaisie(false)} />}
      {ordonnancement && (
        <DetailOrdonnancement ordonnancement={ordonnancement} fermer={() => setOuvert(undefined)} />
      )}
    </Flex>
  )
}

interface SaisiePaiement {
  fournisseurId: string
  datePaiement: string
  modeReglementId: string
  compteTresorerieId: string
  referenceTransaction?: string
  pieceCaisse?: string
  retenueSource?: string
  parts?: Record<string, string | undefined>
}

/** Paiement d'un bénéficiaire, partiel ou groupé, ventilé par liquidation (EF-PAI-01, 02). */
function FormulairePaiement({ fermer }: { fermer: () => void }) {
  const { t } = useTranslation('paiements')
  const { t: tCommun } = useTranslation()
  const { message } = App.useApp()
  const afficherErreur = useAfficherErreur()
  const client = useQueryClient()
  const [formulaire] = Form.useForm<SaisiePaiement>()
  const [cle] = useState(() => crypto.randomUUID())
  const fournisseurs = useOptions('fournisseurs')
  const modes = useOptions('modes-reglement')
  const comptes = useOptions('comptes-tresorerie')
  const fournisseurId = Form.useWatch('fournisseurId', formulaire)
  const parts = Form.useWatch('parts', formulaire) ?? {}
  const total = additionnerMontants(Object.values(parts))
  const { data: liquidations = [] } = useQuery({
    queryKey: ['liquidations', 'A_PAYER', fournisseurId],
    queryFn: () => listerLiquidationsATraiter({ etape: 'A_PAYER', fournisseurId }),
    enabled: Boolean(fournisseurId),
  })
  const envoi = useMutation({
    mutationFn: (v: SaisiePaiement) =>
      enregistrerPaiement(
        {
          datePaiement: v.datePaiement,
          montant: total,
          modeReglementId: v.modeReglementId,
          compteTresorerieId: v.compteTresorerieId,
          referenceTransaction: v.referenceTransaction || null,
          pieceCaisse: v.pieceCaisse || null,
          retenueSource: v.retenueSource || '0',
          allocations: Object.entries(v.parts ?? {})
            .filter(([, m]) => m)
            .map(([liquidationId, m]) => ({ liquidationId, montant: m! })),
        },
        { headers: { 'Idempotency-Key': cle } },
      ),
    onSuccess: () => {
      void message.success(t('paiements.enregistre'))
      void client.invalidateQueries({ queryKey: ['paiements'] })
      void client.invalidateQueries({ queryKey: ['liquidations'] })
      fermer()
    },
    onError: (erreur) => afficherErreur(erreur, formulaire),
  })
  const requis = [{ required: true, message: tCommun('connexion.obligatoire') }]

  return (
    <Drawer
      open
      size="large"
      title={t('paiements.enregistrer')}
      onClose={fermer}
      extra={
        <Button type="primary" loading={envoi.isPending} onClick={() => formulaire.submit()}>
          {tCommun('actions.enregistrer')}
        </Button>
      }
    >
      <Form form={formulaire} layout="vertical" onFinish={(v) => envoi.mutate(v)}>
        <Form.Item name="fournisseurId" label={t('paiements.fournisseur')} rules={requis}>
          <Select
            options={fournisseurs}
            showSearch
            optionFilterProp="label"
            onChange={() => formulaire.setFieldValue('parts', {})}
          />
        </Form.Item>
        <Flex gap="middle" wrap>
          <Form.Item name="datePaiement" label={t('paiements.datePaiement')} rules={requis}>
            <Input type="date" />
          </Form.Item>
          <Form.Item name="modeReglementId" label={t('paiements.modeReglementId')} rules={requis}>
            <Select style={{ minWidth: 180 }} options={modes} />
          </Form.Item>
          <Form.Item
            name="compteTresorerieId"
            label={t('paiements.compteTresorerieId')}
            rules={requis}
          >
            <Select style={{ minWidth: 180 }} options={comptes} />
          </Form.Item>
        </Flex>
        <Flex gap="middle" wrap>
          <Form.Item name="referenceTransaction" label={t('paiements.referenceTransaction')}>
            <Input maxLength={100} />
          </Form.Item>
          <Form.Item name="pieceCaisse" label={t('paiements.pieceCaisse')}>
            <Input maxLength={100} />
          </Form.Item>
          <Form.Item name="retenueSource" label={t('paiements.retenueSource')}>
            <Input inputMode="decimal" />
          </Form.Item>
        </Flex>
        {fournisseurId && (
          <>
            <Typography.Text strong>{t('paiements.ventilation')}</Typography.Text>
            <Typography.Paragraph type="secondary">{t('paiements.aide')}</Typography.Paragraph>
            <Table
              rowKey="id"
              size="small"
              pagination={false}
              dataSource={liquidations}
              scroll={{ x: 'max-content' }}
              locale={{ emptyText: t('paiements.aucuneLiquidation') }}
              columns={[
                {
                  title: t('ordonnancements.liquidation'),
                  key: 'liquidation',
                  render: (_, lq) => `${lq.numero} — ${lq.factureNumero}`,
                },
                {
                  title: t('paiements.resteAPayer'),
                  dataIndex: 'resteAPayer',
                  align: 'end',
                  render: (v: string) => <Montant valeur={v} />,
                },
                {
                  title: t('paiements.part'),
                  key: 'part',
                  render: (_, lq) => (
                    <Form.Item name={['parts', lq.id]} noStyle>
                      <Input
                        aria-label={`${t('paiements.part')} — ${lq.numero}`}
                        inputMode="decimal"
                        style={{ width: 150 }}
                      />
                    </Form.Item>
                  ),
                },
              ]}
            />
            <Space style={{ marginTop: 12 }}>
              <Typography.Text strong>{t('paiements.total')}</Typography.Text>
              <Montant valeur={total} />
            </Space>
          </>
        )}
      </Form>
    </Drawer>
  )
}

function ListePaiements() {
  const { t, i18n } = useTranslation('paiements')
  const { t: tCommun } = useTranslation()
  const { message } = App.useApp()
  const afficherErreur = useAfficherErreur()
  const client = useQueryClient()
  const estComptable = useAProfil(['CPT'])
  const peutAnnuler = useAProfil(ANNULATION)
  const [saisie, setSaisie] = useState(false)
  const [aAnnuler, setAAnnuler] = useState<string>()
  const { data, isFetching } = useQuery({
    queryKey: ['paiements'],
    queryFn: () => listerPaiements({ taille: 100 }),
  })
  const annulation = useMutation({
    mutationFn: (motif: string) => annulerPaiement(aAnnuler!, { motif }),
    onSuccess: () => {
      void message.success(t('paiements.annule'))
      setAAnnuler(undefined)
      void client.invalidateQueries({ queryKey: ['paiements'] })
      void client.invalidateQueries({ queryKey: ['liquidations'] })
    },
    onError: (erreur) => afficherErreur(erreur),
  })
  const colonnes: ColumnsType<PaiementSortie> = [
    { title: t('paiements.numero'), dataIndex: 'numero' },
    {
      title: t('paiements.date'),
      dataIndex: 'datePaiement',
      render: (v: string) => formaterDate(v, i18n.language),
    },
    {
      title: t('paiements.allocations'),
      key: 'allocations',
      render: (_, p) => (
        <Flex vertical>
          {p.allocations.map((a) => (
            <Space key={a.liquidationId} wrap>
              <Link to={`/factures/${a.factureId}`}>{a.factureNumero}</Link>
              <Montant valeur={a.montant} />
            </Space>
          ))}
        </Flex>
      ),
    },
    {
      title: t('paiements.montant'),
      dataIndex: 'montant',
      align: 'end',
      render: (v: string) => <Montant valeur={v} />,
    },
    {
      title: t('paiements.statut'),
      dataIndex: 'statut',
      render: (v: string) => <Statut valeur={v} />,
    },
    {
      key: 'actions',
      render: (_, p) =>
        peutAnnuler &&
        p.statut !== 'ANNULE' && (
          <Button size="small" danger onClick={() => setAAnnuler(p.id)}>
            {t('paiements.annuler')}
          </Button>
        ),
    },
  ]

  return (
    <Flex vertical gap="middle">
      {estComptable && (
        <Button type="primary" style={{ alignSelf: 'flex-start' }} onClick={() => setSaisie(true)}>
          {t('paiements.enregistrer')}
        </Button>
      )}
      <Table<PaiementSortie>
        rowKey="id"
        loading={isFetching}
        columns={colonnes}
        dataSource={data?.donnees ?? []}
        pagination={false}
        scroll={{ x: 'max-content' }}
        locale={{ emptyText: tCommun('tableau.aucun') }}
      />
      {saisie && <FormulairePaiement fermer={() => setSaisie(false)} />}
      {aAnnuler && (
        <DemandeMotif
          titre={t('paiements.motifAnnulation')}
          enCours={annulation.isPending}
          valider={(motif) => annulation.mutate(motif)}
          fermer={() => setAAnnuler(undefined)}
        />
      )}
    </Flex>
  )
}

/** Ordonnancement et paiements (T-193). */
export function Paiements() {
  const { t } = useTranslation('paiements')
  return (
    <Flex vertical gap="middle">
      <Typography.Title level={1} style={{ margin: 0 }}>
        {t('titre')}
      </Typography.Title>
      <Typography.Paragraph>{t('intro')}</Typography.Paragraph>
      <Tabs
        destroyOnHidden
        items={[
          {
            key: 'ordonnancements',
            label: t('onglets.ordonnancements'),
            children: <Ordonnancements />,
          },
          { key: 'paiements', label: t('onglets.paiements'), children: <ListePaiements /> },
        ]}
      />
    </Flex>
  )
}
