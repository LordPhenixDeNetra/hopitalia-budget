import { PlusOutlined } from '@ant-design/icons'
import { useMutation, useQuery } from '@tanstack/react-query'
import { App, Button, Col, Drawer, Flex, Form, Input, Row, Select, Space, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table/interface'
import { useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useSearchParams } from 'react-router'
import { useAfficherErreur } from '../../api/erreurs'
import {
  corrigerFacture,
  enregistrerFacture,
  getListerFacturesQueryKey,
  listerFactures,
} from '../../api/genere/budget'
import type {
  FactureCreation,
  FactureSortie,
  ListerFacturesParams,
} from '../../api/genere/budget.schemas'
import { useAProfil } from '../../auth/session'
import { BadgeStatut, type Ton } from '../../composants/BadgeStatut'
import { Montant } from '../../composants/Montant'
import { TableauServeur } from '../../composants/TableauServeur'
import { formaterDate } from '../../format/format'
import { useOptions } from '../parametrage/PageReferentiel'

export const TYPES_FACTURE = ['AVANCE', 'ACOMPTE', 'PARTIELLE', 'DEFINITIVE', 'DECOMPTE', 'AVOIR']
export const TONS_FACTURE: Record<string, Ton> = {
  RECUE: 'info',
  EN_CONTROLE: 'attention',
  RETOURNEE: 'attention',
  REJETEE: 'erreur',
  LIQUIDEE: 'succes',
  MISE_EN_PAIEMENT: 'info',
  PARTIELLEMENT_PAYEE: 'info',
  PAYEE: 'succes',
}
// Enregistrement des factures et liquidation : agent financier (matrice des habilitations).
export const AGENT_FINANCIER = ['AF']

const nettoyer = (v: Record<string, unknown>) =>
  Object.fromEntries(Object.entries(v).map(([k, x]) => [k, x === '' ? null : x]))

/** Enregistrement ou correction d'une facture (T-170 à T-173). */
export function FormulaireFacture({
  facture,
  fermer,
  enregistree,
}: {
  facture?: FactureSortie
  fermer: () => void
  enregistree: (f: FactureSortie) => void
}) {
  const { t } = useTranslation('factures')
  const { t: tCommun } = useTranslation()
  const { message } = App.useApp()
  const afficherErreur = useAfficherErreur()
  const [formulaire] = Form.useForm<FactureCreation>()
  const [cle] = useState(() => crypto.randomUUID())
  const type = Form.useWatch('type', formulaire) ?? facture?.type
  const engagementId = Form.useWatch('engagementId', formulaire) ?? facture?.engagementId
  const engagements = useOptions('engagements?statut=VALIDE')
  const commandes = useOptions(
    engagementId ? `bons-commande?engagementId=${engagementId}` : undefined,
  )
  const origines = useOptions(engagementId ? `factures?engagementId=${engagementId}` : undefined)
  const requis = [{ required: true, message: tCommun('connexion.obligatoire') }]
  const envoi = useMutation({
    mutationFn: (v: FactureCreation) => {
      const corps = nettoyer(v as unknown as Record<string, unknown>) as unknown as FactureCreation
      return facture
        ? corrigerFacture(facture.id, corps, { headers: { 'If-Match': `"${facture.version}"` } })
        : enregistrerFacture(corps, { headers: { 'Idempotency-Key': cle } })
    },
    onSuccess: (f) => {
      void message.success(t(facture ? 'corrigee' : 'enregistree'))
      enregistree(f)
    },
    onError: (erreur) => afficherErreur(erreur, formulaire),
  })
  const liste = (o: { value: string; label: string }[]) => (
    <Select allowClear showSearch optionFilterProp="label" options={o} />
  )
  // [nom, contrôle, obligatoire] ; false masque un champ selon le type de facture.
  type Champ = [string, ReactNode, boolean?]
  const champs: (Champ | false)[] = [
    !facture && ['engagementId', liste(engagements), true],
    !facture && ['bonCommandeId', liste(commandes)],
    !facture && [
      'type',
      <Select
        key="type"
        options={TYPES_FACTURE.map((v) => ({ value: v, label: t(`valeurs.${v}`) }))}
      />,
      true,
    ],
    !facture && type === 'AVOIR' && ['factureOrigineId', liste(origines), true],
    !facture &&
      type === 'DECOMPTE' && ['numeroDecompte', <Input key="dec" type="number" min={1} />, true],
    ['numero', <Input key="numero" maxLength={50} />, true],
    ['objet', <Input key="objet" maxLength={500} />, true],
    ['dateEmission', <Input key="em" type="date" />, true],
    ['dateReception', <Input key="rec" type="date" />, true],
    ['dateEcheance', <Input key="ech" type="date" />],
    ['dateLimiteTraitement', <Input key="lim" type="date" />],
    ['periodeRattachement', <Input key="per" maxLength={50} />],
    ['montantHt', <Input key="ht" inputMode="decimal" />, true],
    ['montantTaxes', <Input key="tx" inputMode="decimal" />],
    ['montantTtc', <Input key="ttc" inputMode="decimal" />, true],
    ['motifLeveeDoublon', <Input.TextArea key="lev" maxLength={500} />],
  ]

  return (
    <Drawer
      open
      size="large"
      title={facture ? `${facture.numero} — ${t('corriger')}` : t('enregistrer')}
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
        initialValues={facture ?? { type: 'PARTIELLE', montantTaxes: '0' }}
        onFinish={(v) => envoi.mutate(v)}
      >
        <Row gutter={16}>
          {champs
            .filter((c): c is Champ => Boolean(c))
            .map(([nom, controle, obligatoire]) => (
              <Col xs={24} md={12} key={nom}>
                <Form.Item name={nom} label={t(`champs.${nom}`)} rules={obligatoire ? requis : []}>
                  {controle}
                </Form.Item>
              </Col>
            ))}
        </Row>
      </Form>
    </Drawer>
  )
}

/** Traitement des factures : liste filtrable et enregistrement (T-181). */
export function Factures() {
  const { t, i18n } = useTranslation('factures')
  const naviguer = useNavigate()
  const peutSaisir = useAProfil(AGENT_FINANCIER)
  const [saisie, setSaisie] = useState(false)
  const [parametres, setParametres] = useSearchParams()
  const filtres: ListerFacturesParams = {
    page: Number(parametres.get('page') ?? 1),
    taille: Number(parametres.get('taille') ?? 25),
    ...Object.fromEntries(
      ['statut', 'type'].map((k) => [k, parametres.get(k)]).filter(([, v]) => v),
    ),
  }
  const { data, isFetching } = useQuery({
    queryKey: getListerFacturesQueryKey(filtres),
    queryFn: () => listerFactures(filtres),
  })
  const filtrer = (cle: string, valeur?: string | null) => {
    const suivants = new URLSearchParams(parametres)
    if (valeur) suivants.set(cle, valeur)
    else suivants.delete(cle)
    suivants.delete('page')
    setParametres(suivants)
  }
  const choix = (valeurs: string[]) => valeurs.map((v) => ({ value: v, label: t(`valeurs.${v}`) }))
  const statut = (f: FactureSortie) => (
    <BadgeStatut ton={TONS_FACTURE[f.statut] ?? 'neutre'} libelle={t(`valeurs.${f.statut}`)} />
  )
  const colonnes: ColumnsType<FactureSortie> = [
    {
      title: t('champs.numero'),
      dataIndex: 'numero',
      render: (v: string, f) => <Link to={`/factures/${f.id}`}>{v}</Link>,
    },
    { title: t('champs.type'), dataIndex: 'type', render: (v: string) => t(`valeurs.${v}`) },
    { title: t('champs.objet'), dataIndex: 'objet' },
    {
      title: t('champs.dateReception'),
      dataIndex: 'dateReception',
      render: (v: string) => formaterDate(v, i18n.language),
    },
    {
      title: t('champs.montantTtc'),
      dataIndex: 'montantTtc',
      align: 'right',
      render: (v: string) => <Montant valeur={v} />,
    },
    {
      title: t('champs.resteAPayer'),
      dataIndex: 'resteAPayer',
      align: 'right',
      render: (v: string) => <Montant valeur={v} />,
    },
    { title: t('champs.statut'), key: 'statut', render: (_, f) => statut(f) },
  ]

  return (
    <Flex vertical gap="middle">
      <Flex justify="space-between" align="center" wrap gap="small">
        <Typography.Title level={1} style={{ margin: 0 }}>
          {t('titre')}
        </Typography.Title>
        {peutSaisir && (
          <Button
            type="primary"
            icon={<PlusOutlined aria-hidden />}
            onClick={() => setSaisie(true)}
          >
            {t('enregistrer')}
          </Button>
        )}
      </Flex>
      <Typography.Paragraph>{t('intro')}</Typography.Paragraph>
      <Flex gap="small" wrap>
        <Select
          aria-label={t('filtres.statut')}
          placeholder={t('filtres.statut')}
          allowClear
          style={{ minWidth: 180 }}
          value={parametres.get('statut') ?? undefined}
          onChange={(v) => filtrer('statut', v)}
          options={choix(Object.keys(TONS_FACTURE))}
        />
        <Select
          aria-label={t('filtres.type')}
          placeholder={t('filtres.type')}
          allowClear
          style={{ minWidth: 160 }}
          value={parametres.get('type') ?? undefined}
          onChange={(v) => filtrer('type', v)}
          options={choix(TYPES_FACTURE)}
        />
      </Flex>
      <TableauServeur<FactureSortie>
        colonnes={colonnes}
        donnees={data?.donnees ?? []}
        total={data?.pagination.total ?? 0}
        chargement={isFetching}
        etat={{ page: filtres.page ?? 1, taille: filtres.taille ?? 25 }}
        surChangement={(e) => {
          const suivants = new URLSearchParams(parametres)
          suivants.set('page', String(e.page))
          suivants.set('taille', String(e.taille))
          setParametres(suivants)
        }}
        cleLigne={(f) => f.id}
        carte={(f) => (
          <Space direction="vertical">
            <Link to={`/factures/${f.id}`}>{`${f.numero} — ${f.objet}`}</Link>
            <Montant valeur={f.montantTtc} />
            {statut(f)}
          </Space>
        )}
      />
      {saisie && (
        <FormulaireFacture
          fermer={() => setSaisie(false)}
          enregistree={(f) => naviguer(`/factures/${f.id}`)}
        />
      )}
    </Flex>
  )
}
