import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  App,
  Button,
  Descriptions,
  Drawer,
  Flex,
  Form,
  Input,
  Modal,
  Result,
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
  annulerEngagement,
  cloturerEngagement,
  demanderDerogation,
  getObtenirEngagementQueryKey,
  lireControles,
  listerAnnulations,
  listerDerogations,
  obtenirEngagement,
  resoumettre,
} from '../../api/genere/budget'
import type {
  DerogationSortie,
  EngagementSortie,
  NatureDerogation,
  ResultatControleSortie as ResultatSortie,
} from '../../api/genere/budget.schemas'
import { useAProfil } from '../../auth/session'
import { BadgeStatut, type Ton } from '../../composants/BadgeStatut'
import { Montant } from '../../composants/Montant'
import { Pieces } from '../../composants/workflow/Pieces'
import { Validations } from '../../composants/workflow/Validations'
import { formaterDate, formaterDateHeure } from '../../format/format'
import { FormulaireCommande, ListeCommandes } from '../commandes/Commandes'
import { useOptions } from '../parametrage/PageReferentiel'
import { SAISIE_ENGAGEMENT, TONS_ENGAGEMENT } from './Engagements'
import { FormulaireEngagement } from './FormulaireEngagement'

const MODIFIABLES = ['BROUILLON', 'A_CORRIGER']
const AVANT_VALIDATION = ['BROUILLON', 'SOUMIS', 'EN_CONTROLE', 'A_CORRIGER']
const ANNULABLES = ['VALIDE', 'PARTIELLEMENT_EXECUTE', 'EXECUTE']
// Profils qui annulent une opération validée (ANNULER_OPERATION_VALIDEE).
const ANNULATION = ['AF', 'VAL', 'ORD']

/** Écarts des contrôles automatiques, dérogations demandées et leur circuit (T-142 à T-147). */
function Controles({
  engagement,
  peutSaisir,
}: {
  engagement: EngagementSortie
  peutSaisir: boolean
}) {
  const { t } = useTranslation('engagements')
  const { t: tCommun } = useTranslation()
  const { message } = App.useApp()
  const afficherErreur = useAfficherErreur()
  const client = useQueryClient()
  const [formulaire] = Form.useForm()
  const [demande, setDemande] = useState<ResultatSortie>()
  const [detail, setDetail] = useState<DerogationSortie>()
  const peutDeposer = useAProfil([...SAISIE_ENGAGEMENT, 'VAL', 'ORD'])
  const { data: resultats = [], isLoading } = useQuery({
    queryKey: ['controles', engagement.id],
    queryFn: () => lireControles(engagement.id),
  })
  const { data: derogations = [] } = useQuery({
    queryKey: ['derogations', engagement.id],
    queryFn: () => listerDerogations(engagement.id),
  })
  const rafraichir = () => {
    void client.invalidateQueries({ queryKey: ['controles', engagement.id] })
    void client.invalidateQueries({ queryKey: ['derogations', engagement.id] })
  }
  const creation = useMutation({
    mutationFn: (v: { montantDepassement: string; motif: string }) =>
      demanderDerogation(engagement.id, { ...v, nature: demande!.nature as NatureDerogation }),
    onSuccess: () => {
      void message.success(t('derogations.creee'))
      setDemande(undefined)
      formulaire.resetFields()
      rafraichir()
    },
    onError: (erreur) => afficherErreur(erreur, formulaire),
  })
  const enCours = AVANT_VALIDATION.includes(engagement.statut)
  const etat = (r: ResultatSortie) => {
    const [ton, cle]: [Ton, string] = r.leve
      ? ['succes', 'leve']
      : r.nature
        ? ['attention', 'ouvert']
        : ['erreur', 'nonDerogeable']
    return <BadgeStatut ton={ton} libelle={t(`controles.${cle}`)} />
  }
  const details = (r: ResultatSortie) =>
    Object.entries(r.details)
      .filter(([, v]) => v)
      .map(([k, v]) => `${t(`controles.${k}`, { defaultValue: k })} : ${v}`)
      .join(' ; ')
  const colonnes: ColumnsType<ResultatSortie> = [
    { title: t('controles.code'), dataIndex: 'code', render: (v: string) => t(`controles.${v}`) },
    { title: t('controles.details'), key: 'details', render: (_, r) => details(r) },
    {
      title: t('controles.depassement'),
      dataIndex: 'depassement',
      align: 'end',
      render: (v: string) => <Montant valeur={v} />,
    },
    { title: t('controles.etat'), key: 'etat', render: (_, r) => etat(r) },
    {
      key: 'actions',
      render: (_, r) =>
        peutSaisir &&
        enCours &&
        !r.leve &&
        r.nature && (
          <Button size="small" onClick={() => setDemande(r)}>
            {t('controles.demander')}
          </Button>
        ),
    },
  ]
  const colonnesDerogations: ColumnsType<DerogationSortie> = [
    {
      title: t('derogations.nature'),
      dataIndex: 'nature',
      render: (v: string) => t(`derogations.${v}`),
    },
    {
      title: t('derogations.montantDepassement'),
      dataIndex: 'montantDepassement',
      align: 'end',
      render: (v: string) => <Montant valeur={v} />,
    },
    { title: t('derogations.motif'), dataIndex: 'motif' },
    {
      title: t('derogations.statut'),
      dataIndex: 'statut',
      render: (v: string) => (
        <BadgeStatut ton={TONS_ENGAGEMENT[v] ?? 'neutre'} libelle={t(`valeurs.${v}`)} />
      ),
    },
    {
      key: 'actions',
      render: (_, d) => (
        <Button size="small" onClick={() => setDetail(d)}>
          {t('derogations.detail')}
        </Button>
      ),
    },
  ]
  const requis = [{ required: true, message: tCommun('connexion.obligatoire') }]

  if (isLoading) return <Spin />
  return (
    <Flex vertical gap="middle">
      <Typography.Paragraph>{t('controles.intro')}</Typography.Paragraph>
      {resultats.length === 0 ? (
        <BadgeStatut ton="succes" libelle={t('controles.aucun')} />
      ) : (
        <Table<ResultatSortie>
          rowKey={(r) => `${r.code}-${details(r)}`}
          columns={colonnes}
          dataSource={resultats}
          pagination={false}
          scroll={{ x: 'max-content' }}
        />
      )}
      <Typography.Title level={4}>{t('derogations.titre')}</Typography.Title>
      <Table<DerogationSortie>
        rowKey="id"
        columns={colonnesDerogations}
        dataSource={derogations}
        pagination={false}
        scroll={{ x: 'max-content' }}
        locale={{ emptyText: tCommun('tableau.aucun') }}
      />
      <Modal
        open={Boolean(demande)}
        title={`${t('controles.demander')} — ${demande?.nature ? t(`derogations.${demande.nature}`) : ''}`}
        okText={tCommun('actions.enregistrer')}
        cancelText={tCommun('actions.annuler')}
        confirmLoading={creation.isPending}
        onOk={() => formulaire.submit()}
        onCancel={() => setDemande(undefined)}
        destroyOnHidden
      >
        <Form
          form={formulaire}
          layout="vertical"
          initialValues={{ montantDepassement: demande?.depassement }}
          onFinish={(v) => creation.mutate(v)}
        >
          <Form.Item
            name="montantDepassement"
            label={t('derogations.montantDepassement')}
            rules={requis}
          >
            <Input inputMode="decimal" />
          </Form.Item>
          <Form.Item name="motif" label={t('derogations.motif')} rules={requis}>
            <Input.TextArea maxLength={500} />
          </Form.Item>
        </Form>
      </Modal>
      {detail && (
        <Drawer
          open
          size="large"
          title={t(`derogations.${detail.nature}`)}
          onClose={() => setDetail(undefined)}
        >
          <Flex vertical gap="large">
            <Validations ressource="derogations" id={detail.id} surDecision={rafraichir} />
            <Pieces ressource="derogations" id={detail.id} peutDeposer={peutDeposer} />
          </Flex>
        </Drawer>
      )}
    </Flex>
  )
}

/** Annulations (contre-opérations) et clôture d'un engagement validé (T-117, T-148). */
function Annulations({
  engagement,
  rafraichir,
}: {
  engagement: EngagementSortie
  rafraichir: () => void
}) {
  const { t, i18n } = useTranslation('engagements')
  const { t: tCommun } = useTranslation()
  const { message } = App.useApp()
  const afficherErreur = useAfficherErreur()
  const client = useQueryClient()
  const [formulaire] = Form.useForm()
  const peutAnnuler = useAProfil(ANNULATION) && ANNULABLES.includes(engagement.statut)
  const lignes = useOptions('lignes-budgetaires')
  const { data: annulations = [] } = useQuery({
    queryKey: ['annulations', engagement.id],
    queryFn: () => listerAnnulations(engagement.id),
  })
  const apres = (texte: string) => {
    void message.success(texte)
    formulaire.resetFields()
    void client.invalidateQueries({ queryKey: ['annulations', engagement.id] })
    rafraichir()
  }
  const annulation = useMutation({
    mutationFn: ({ motif, montants }: { motif: string; montants?: Record<string, string> }) => {
      const detail = Object.entries(montants ?? {})
        .filter(([, m]) => m)
        .map(([imputationId, montant]) => ({ imputationId, montant }))
      return annulerEngagement(engagement.id, { motif, lignes: detail.length ? detail : null })
    },
    onSuccess: () => apres(t('annulations.enregistree')),
    onError: (erreur) => afficherErreur(erreur, formulaire),
  })
  const cloture = useMutation({
    mutationFn: (motif: string) => cloturerEngagement(engagement.id, { motif }),
    onSuccess: () => apres(t('annulations.cloturee')),
    onError: (erreur) => afficherErreur(erreur, formulaire),
  })
  const ligne = (imputationId: string) => {
    const imputation = engagement.imputations.find((i) => i.id === imputationId)
    return lignes.find((l) => l.value === imputation?.ligneId)?.label ?? ''
  }
  const requis = [{ required: true, message: tCommun('connexion.obligatoire') }]

  return (
    <Flex vertical gap="middle">
      <Typography.Paragraph>{t('annulations.intro')}</Typography.Paragraph>
      <Table
        rowKey="id"
        dataSource={annulations}
        pagination={false}
        scroll={{ x: 'max-content' }}
        locale={{ emptyText: t('annulations.aucune') }}
        columns={[
          {
            title: t('annulations.type'),
            dataIndex: 'type',
            render: (v: string) => t(`valeurs.${v === 'CLOTURE' ? 'CLOTURE_TYPE' : v}`),
          },
          {
            title: t('annulations.montant'),
            dataIndex: 'montant',
            align: 'end',
            render: (v: string) => <Montant valeur={v} />,
          },
          { title: t('annulations.motif'), dataIndex: 'motif' },
          { title: t('annulations.par'), dataIndex: 'codeAgent' },
          {
            title: t('annulations.date'),
            dataIndex: 'horodatage',
            render: (v: string) => formaterDateHeure(v, i18n.language),
          },
        ]}
      />
      {peutAnnuler && (
        <Form
          form={formulaire}
          layout="vertical"
          onFinish={(v: { motif: string; montants?: Record<string, string> }) =>
            annulation.mutate(v)
          }
        >
          <Typography.Title level={4}>{t('annulations.partielle')}</Typography.Title>
          {engagement.imputations.map((i) => (
            <Form.Item key={i.id} name={['montants', i.id]} label={ligne(i.id)}>
              <Input inputMode="decimal" />
            </Form.Item>
          ))}
          <Form.Item name="motif" label={t('annulations.motif')} rules={requis}>
            <Input.TextArea maxLength={500} />
          </Form.Item>
          <Space wrap>
            <Button htmlType="submit" danger loading={annulation.isPending}>
              {t('annulations.annuler')}
            </Button>
            {engagement.statut !== 'VALIDE' && (
              <Button
                loading={cloture.isPending}
                onClick={() =>
                  void formulaire
                    .validateFields(['motif'])
                    .then((v: { motif: string }) => cloture.mutate(v.motif))
                }
              >
                {t('annulations.cloturer')}
              </Button>
            )}
          </Space>
          <Typography.Paragraph type="secondary">
            {t('annulations.aideCloture')}
          </Typography.Paragraph>
        </Form>
      )}
    </Flex>
  )
}

/** Commandes émises sur l'engagement ; émission par le gestionnaire de marchés (EF-CMD-01). */
function CommandesEngagement({ engagement }: { engagement: EngagementSortie }) {
  const { t } = useTranslation('commandes')
  const peutEmettre =
    useAProfil(['GMC']) && ['VALIDE', 'PARTIELLEMENT_EXECUTE'].includes(engagement.statut)
  const [emission, setEmission] = useState(false)
  return (
    <Flex vertical gap="middle">
      {peutEmettre && (
        <Button
          type="primary"
          style={{ alignSelf: 'flex-start' }}
          onClick={() => setEmission(true)}
        >
          {t('emettre')}
        </Button>
      )}
      <ListeCommandes engagementId={engagement.id} />
      {emission && (
        <FormulaireCommande engagementId={engagement.id} fermer={() => setEmission(false)} />
      )}
    </Flex>
  )
}

/** Fiche engagement : /engagements/:id (T-150). */
export function FicheEngagement() {
  const { id = '' } = useParams()
  const { t, i18n } = useTranslation('engagements')
  const { t: tCommun } = useTranslation()
  const { message } = App.useApp()
  const afficherErreur = useAfficherErreur()
  const client = useQueryClient()
  const peutSaisir = useAProfil(SAISIE_ENGAGEMENT)
  const peutDeposer = useAProfil([...SAISIE_ENGAGEMENT, 'AF', 'VAL', 'ORD'])
  const [edition, setEdition] = useState(false)
  const lignes = useOptions('lignes-budgetaires')
  const fournisseurs = useOptions('fournisseurs')
  const contrats = useOptions('contrats')
  const {
    data: engagement,
    isLoading,
    error,
  } = useQuery({
    queryKey: getObtenirEngagementQueryKey(id),
    queryFn: () => obtenirEngagement(id),
  })
  const rafraichir = () => {
    void client.invalidateQueries({ queryKey: getObtenirEngagementQueryKey(id) })
    void client.invalidateQueries({ queryKey: ['controles', id] })
  }
  const soumission = useMutation({
    mutationFn: () => resoumettre('engagements', id),
    onSuccess: () => {
      void message.success(t('soumis'))
      rafraichir()
    },
    onError: (erreur) => afficherErreur(erreur),
  })

  if (isLoading) return <Spin aria-label={tCommun('tableau.chargement')} />
  if (error || !engagement) {
    return (
      <Result
        status="404"
        title={tCommun('introuvable.titre')}
        subTitle={tCommun('introuvable.detail')}
        extra={<Link to="/engagements">{tCommun('menu.engagements')}</Link>}
      />
    )
  }
  const modifiable = MODIFIABLES.includes(engagement.statut)
  const libelle = (o: { value: string; label: string }[], v?: string | null) =>
    o.find((x) => x.value === v)?.label ?? ''
  const informations: [string, ReactNode][] = [
    ['origine', t(`valeurs.${engagement.origine}`)],
    ['dateEngagement', formaterDate(engagement.dateEngagement, i18n.language)],
    ['contratId', libelle(contrats, engagement.contratId)],
    ['fournisseurId', libelle(fournisseurs, engagement.fournisseurId)],
    ['montant', <Montant key="m" valeur={engagement.montant} />],
    ['montantAnnule', <Montant key="a" valeur={engagement.montantAnnule} />],
    [
      'natureHorsMarche',
      engagement.natureHorsMarche ? t(`valeurs.${engagement.natureHorsMarche}`) : '',
    ],
    ['justification', engagement.justification],
    ['referenceDecision', engagement.referenceDecision],
    ['creeParCode', engagement.creeParCode],
  ]
  const onglets = [
    {
      key: 'informations',
      label: t('onglets.informations'),
      children: (
        <Flex vertical gap="middle">
          <Descriptions
            bordered
            size="small"
            column={{ xs: 1, md: 2 }}
            items={informations.map(([k, v]) => ({ key: k, label: t(`champs.${k}`), children: v }))}
          />
          <Table
            rowKey="id"
            pagination={false}
            dataSource={engagement.imputations}
            columns={[
              {
                title: t('champs.ligneId'),
                dataIndex: 'ligneId',
                render: (v: string) => libelle(lignes, v),
              },
              {
                title: t('champs.montant'),
                dataIndex: 'montant',
                align: 'end',
                render: (v: string) => <Montant valeur={v} />,
              },
              {
                title: t('champs.annule'),
                dataIndex: 'annule',
                align: 'end',
                render: (v: string) => <Montant valeur={v} />,
              },
            ]}
          />
        </Flex>
      ),
    },
    {
      key: 'controles',
      label: t('onglets.controles'),
      children: <Controles engagement={engagement} peutSaisir={peutSaisir} />,
    },
    {
      key: 'validation',
      label: t('onglets.validation'),
      children: (
        <Flex vertical gap="large">
          <Validations ressource="engagements" id={id} surDecision={rafraichir} />
          <Pieces ressource="engagements" id={id} peutDeposer={peutDeposer} />
        </Flex>
      ),
    },
    {
      key: 'commandes',
      label: t('onglets.commandes'),
      children: <CommandesEngagement engagement={engagement} />,
    },
    {
      key: 'annulations',
      label: t('onglets.annulations'),
      children: <Annulations engagement={engagement} rafraichir={rafraichir} />,
    },
  ]

  return (
    <Flex vertical gap="middle">
      <Flex justify="space-between" align="center" wrap gap="small">
        <Typography.Title level={1} style={{ margin: 0 }}>
          {engagement.numero} — {engagement.objet}
        </Typography.Title>
        <Space wrap>
          <BadgeStatut
            ton={TONS_ENGAGEMENT[engagement.statut] ?? 'neutre'}
            libelle={t(`valeurs.${engagement.statut}`)}
          />
          {peutSaisir && modifiable && (
            <>
              <Button onClick={() => setEdition(true)}>{t('modifier')}</Button>
              <Button
                type="primary"
                loading={soumission.isPending}
                onClick={() => soumission.mutate()}
              >
                {t('soumettre')}
              </Button>
            </>
          )}
        </Space>
      </Flex>
      <Tabs items={onglets} destroyOnHidden />
      {edition && (
        <FormulaireEngagement
          engagement={engagement}
          fermer={() => setEdition(false)}
          enregistre={(e) => {
            client.setQueryData(getObtenirEngagementQueryKey(id), e)
            void client.invalidateQueries({ queryKey: ['controles', id] })
            setEdition(false)
          }}
        />
      )}
    </Flex>
  )
}
