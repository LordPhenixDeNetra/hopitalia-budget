import { PlusOutlined } from '@ant-design/icons'
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
  Select,
  Statistic,
  Table,
  Tabs,
  Typography,
} from 'antd'
import type { ColumnsType } from 'antd/es/table/interface'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useAfficherErreur } from '../../api/erreurs'
import {
  creerRecette,
  enregistrerMouvement,
  listerMouvements,
  listerRecettes,
  tableauRecettes,
} from '../../api/genere/budget'
import type {
  IndicateursRecetteSortie,
  MouvementCreation,
  RecetteCreation,
  RecetteSortie,
  RepartitionRecettes,
} from '../../api/genere/budget.schemas'
import { useAProfil } from '../../auth/session'
import { Montant } from '../../composants/Montant'
import { TableauServeur, type EtatTableau } from '../../composants/TableauServeur'
import { useEtablissementCourant } from '../../composants/etablissementCourant'
import { formaterDate, formaterNombre } from '../../format/format'
import { useOptions } from '../parametrage/PageReferentiel'

export const NATURES = [
  'SUBVENTION_DOTATION',
  'RECETTE_PROPRE',
  'REMBOURSEMENT_ASSURANCE',
  'PRESTATION_HOSPITALIERE',
  'AUTRE',
] as const
const TYPES_MOUVEMENT = ['FACTURE', 'ENCAISSEMENT'] as const
const MONTANTS = ['prevu', 'facture', 'encaisse', 'resteARecouvrer'] as const
const BORNES = ['du', 'au'] as const
// Matrice : « Gérer les recettes » en saisie pour RB, AF et CPT.
const SAISIE = ['RB', 'AF', 'CPT']

function Taux({ valeur }: { valeur?: string | null }) {
  const { i18n } = useTranslation()
  return (
    <span className="montant">
      {valeur == null ? '—' : `${formaterNombre(Number(valeur), i18n.language)} %`}
    </span>
  )
}

/** Volet recettes (lot P3.B) : recettes et mouvements, puis tableau de bord (T-261 à T-263). */
export function Recettes() {
  const { t } = useTranslation('recettes')
  return (
    <Flex vertical gap="middle">
      <Typography.Title level={1} style={{ margin: 0 }}>
        {t('titre')}
      </Typography.Title>
      <Typography.Paragraph>{t('intro')}</Typography.Paragraph>
      <Tabs
        destroyOnHidden
        items={[
          { key: 'liste', label: t('onglets.liste'), children: <ListeRecettes /> },
          { key: 'tableau', label: t('onglets.tableau'), children: <TableauDeBordRecettes /> },
        ]}
      />
    </Flex>
  )
}

function ListeRecettes() {
  const { t } = useTranslation('recettes')
  const peutSaisir = useAProfil(SAISIE)
  const exercices = useOptions('exercices')
  const [exerciceId, setExerciceId] = useState<string>()
  const [nature, setNature] = useState<string>()
  const [etat, setEtat] = useState<EtatTableau>({ page: 1, taille: 25 })
  const [creation, setCreation] = useState(false)
  const [ouverte, setOuverte] = useState<RecetteSortie>()
  const parametres = {
    page: etat.page,
    taille: etat.taille,
    ...(exerciceId ? { exerciceId } : {}),
    ...(nature ? { nature: nature as RecetteCreation['nature'] } : {}),
  }
  const { data, isFetching } = useQuery({
    queryKey: ['recettes', parametres],
    queryFn: () => listerRecettes(parametres),
  })
  const colonnes: ColumnsType<RecetteSortie> = [
    {
      title: t('colonnes.numero'),
      dataIndex: 'numero',
      render: (numero: string, r) => (
        <Button type="link" style={{ padding: 0 }} onClick={() => setOuverte(r)}>
          {numero}
        </Button>
      ),
    },
    { title: t('colonnes.libelle'), dataIndex: 'libelle' },
    { title: t('colonnes.nature'), dataIndex: 'nature', render: (v: string) => t(`natures.${v}`) },
    { title: t('colonnes.debiteur'), dataIndex: 'debiteur' },
    { title: t('colonnes.service'), dataIndex: 'service' },
    ...MONTANTS.map((cle) => ({
      title: t(`indicateurs.${cle}`),
      key: cle,
      align: 'end' as const,
      render: (_: unknown, r: RecetteSortie) => <Montant valeur={r.indicateurs[cle]} />,
    })),
    {
      title: t('indicateurs.tauxRecouvrement'),
      key: 'tauxRecouvrement',
      align: 'end',
      render: (_, r) => <Taux valeur={r.indicateurs.tauxRecouvrement} />,
    },
  ]
  return (
    <Flex vertical gap="middle">
      <Flex gap="small" wrap justify="space-between">
        <Flex gap="small" wrap>
          <Select
            allowClear
            aria-label={t('filtres.exercice')}
            placeholder={t('filtres.exercice')}
            style={{ minWidth: 160 }}
            options={exercices}
            value={exerciceId}
            onChange={setExerciceId}
          />
          <Select
            allowClear
            aria-label={t('filtres.nature')}
            placeholder={t('filtres.nature')}
            style={{ minWidth: 220 }}
            options={NATURES.map((n) => ({ value: n, label: t(`natures.${n}`) }))}
            value={nature}
            onChange={setNature}
          />
        </Flex>
        {peutSaisir && (
          <Button
            type="primary"
            icon={<PlusOutlined aria-hidden />}
            onClick={() => setCreation(true)}
          >
            {t('nouvelle')}
          </Button>
        )}
      </Flex>
      <TableauServeur<RecetteSortie>
        nom="recettes"
        colonnes={colonnes}
        donnees={data?.donnees ?? []}
        total={data?.pagination.total ?? 0}
        chargement={isFetching}
        etat={etat}
        surChangement={setEtat}
        cleLigne={(r) => r.id}
        carte={(r) => (
          <Flex vertical gap={4}>
            <Button type="link" style={{ padding: 0 }} onClick={() => setOuverte(r)}>
              {r.numero} — {r.libelle}
            </Button>
            <Typography.Text type="secondary">{t(`natures.${r.nature}`)}</Typography.Text>
            <Typography.Text>
              {t('indicateurs.resteARecouvrer')} :{' '}
              <Montant valeur={r.indicateurs.resteARecouvrer} />
            </Typography.Text>
          </Flex>
        )}
      />
      {creation && <FormulaireRecette fermer={() => setCreation(false)} />}
      {ouverte && <FicheRecette recette={ouverte} fermer={() => setOuverte(undefined)} />}
    </Flex>
  )
}

/** Création d'une recette prévue, dans un établissement où le volet est actif (EF-RCT-01). */
function FormulaireRecette({ fermer }: { fermer: () => void }) {
  const { t } = useTranslation('recettes')
  const { t: tCommun } = useTranslation()
  const { message } = App.useApp()
  const afficherErreur = useAfficherErreur()
  const client = useQueryClient()
  const [formulaire] = Form.useForm<RecetteCreation>()
  const [cle] = useState(() => crypto.randomUUID())
  const { etablissements } = useEtablissementCourant()
  const etablissementId = Form.useWatch('etablissementId', formulaire)
  const options = {
    etablissements: etablissements
      .filter((e) => e.voletRecettesActif)
      .map((e) => ({ value: e.id, label: `${e.code} — ${e.nom}` })),
    natures: NATURES.map((n) => ({ value: n, label: t(`natures.${n}`) })),
    exercices: useOptions('exercices'),
    sources: useOptions('sources-financement'),
    debiteurs: useOptions('debiteurs?actif=true'),
    centres: useOptions(
      etablissementId ? `centres-responsabilite?etablissementId=${etablissementId}` : undefined,
    ),
  }
  const envoi = useMutation({
    mutationFn: (v: RecetteCreation) => creerRecette(v, { headers: { 'Idempotency-Key': cle } }),
    onSuccess: () => {
      void message.success(t('creee'))
      void client.invalidateQueries({ queryKey: ['recettes'] })
      fermer()
    },
    onError: (erreur) => afficherErreur(erreur, formulaire),
  })
  const requis = [{ required: true, message: tCommun('connexion.obligatoire') }]
  return (
    <Modal
      open
      width={640}
      title={t('nouvelle')}
      okText={tCommun('actions.enregistrer')}
      cancelText={tCommun('actions.annuler')}
      confirmLoading={envoi.isPending}
      onOk={() => formulaire.submit()}
      onCancel={fermer}
    >
      <Form form={formulaire} layout="vertical" onFinish={(v) => envoi.mutate(v)}>
        <ChampChoix nom="etablissementId" options={options.etablissements} obligatoire />
        <ChampChoix nom="exerciceId" options={options.exercices} obligatoire />
        <ChampChoix nom="nature" options={options.natures} obligatoire />
        <Form.Item name="libelle" label={t('champs.libelle')} rules={requis}>
          <Input maxLength={300} />
        </Form.Item>
        <Form.Item
          name="montantPrevisionnel"
          label={t('champs.montantPrevisionnel')}
          rules={requis}
        >
          <Input inputMode="decimal" />
        </Form.Item>
        <Form.Item name="dateEcheance" label={t('champs.dateEcheance')}>
          <Input type="date" />
        </Form.Item>
        <ChampChoix nom="sourceId" options={options.sources} obligatoire />
        <ChampChoix nom="centreId" options={options.centres} />
        <ChampChoix nom="debiteurId" options={options.debiteurs} />
      </Form>
    </Modal>
  )
}

/** Liste de choix du formulaire de recette, libellée par sa clé de traduction. */
function ChampChoix({
  nom,
  options,
  obligatoire = false,
}: {
  nom: keyof RecetteCreation
  options: { value: string; label: string }[]
  obligatoire?: boolean
}) {
  const { t } = useTranslation('recettes')
  const { t: tCommun } = useTranslation()
  return (
    <Form.Item
      name={nom}
      label={t(`champs.${nom}`)}
      rules={
        obligatoire ? [{ required: true, message: tCommun('connexion.obligatoire') }] : undefined
      }
    >
      <Select allowClear={!obligatoire} showSearch optionFilterProp="label" options={options} />
    </Form.Item>
  )
}

/** Fiche d'une recette : indicateurs et mouvements ; saisie du facturé et de l'encaissé. */
function FicheRecette({ recette, fermer }: { recette: RecetteSortie; fermer: () => void }) {
  const { t, i18n } = useTranslation('recettes')
  const { t: tCommun } = useTranslation()
  const peutSaisir = useAProfil(SAISIE)
  const { data: mouvements } = useQuery({
    queryKey: ['recettes', recette.id, 'mouvements'],
    queryFn: () => listerMouvements(recette.id),
  })
  return (
    <Drawer open size="large" title={`${recette.numero} — ${recette.libelle}`} onClose={fermer}>
      <Flex vertical gap="middle">
        <Indicateurs indicateurs={recette.indicateurs} />
        <Descriptions
          column={1}
          size="small"
          items={[
            {
              key: 'nature',
              label: t('colonnes.nature'),
              children: t(`natures.${recette.nature}`),
            },
            { key: 'debiteur', label: t('colonnes.debiteur'), children: recette.debiteur },
            { key: 'service', label: t('colonnes.service'), children: recette.service },
            {
              key: 'echeance',
              label: t('champs.dateEcheance'),
              children: recette.dateEcheance
                ? formaterDate(recette.dateEcheance, i18n.language)
                : '',
            },
          ]}
        />
        <Typography.Title level={2} style={{ margin: 0 }}>
          {t('mouvements.titre')}
        </Typography.Title>
        <Table
          rowKey="id"
          size="small"
          pagination={false}
          scroll={{ x: 'max-content' }}
          locale={{ emptyText: tCommun('tableau.aucun') }}
          dataSource={mouvements ?? []}
          columns={[
            {
              title: t('mouvements.date'),
              dataIndex: 'date',
              render: (v: string) => formaterDate(v, i18n.language),
            },
            {
              title: t('mouvements.type'),
              dataIndex: 'type',
              render: (v: string) => t(`types.${v}`),
            },
            {
              title: t('mouvements.montant'),
              dataIndex: 'montant',
              align: 'end',
              render: (v: string) => <Montant valeur={v} />,
            },
            { title: t('mouvements.reference'), dataIndex: 'reference' },
            { title: t('mouvements.motif'), dataIndex: 'motif' },
            {
              title: t('mouvements.origine'),
              dataIndex: 'origine',
              render: (v: string) => t(`origines.${v}`),
            },
          ]}
        />
        {peutSaisir && <FormulaireMouvement recette={recette} fermer={fermer} />}
      </Flex>
    </Drawer>
  )
}

function FormulaireMouvement({ recette, fermer }: { recette: RecetteSortie; fermer: () => void }) {
  const { t } = useTranslation('recettes')
  const { t: tCommun } = useTranslation()
  const { message } = App.useApp()
  const afficherErreur = useAfficherErreur()
  const client = useQueryClient()
  const [formulaire] = Form.useForm<MouvementCreation>()
  const [cle, setCle] = useState(() => crypto.randomUUID())
  const envoi = useMutation({
    mutationFn: (v: MouvementCreation) =>
      enregistrerMouvement(recette.id, v, { headers: { 'Idempotency-Key': cle } }),
    onSuccess: () => {
      void message.success(t('mouvements.enregistre'))
      void client.invalidateQueries({ queryKey: ['recettes'] })
      formulaire.resetFields()
      setCle(crypto.randomUUID())
      fermer()
    },
    onError: (erreur) => afficherErreur(erreur, formulaire),
  })
  const requis = [{ required: true, message: tCommun('connexion.obligatoire') }]
  return (
    <Card title={t('mouvements.ajouter')} size="small">
      <Typography.Paragraph type="secondary">{t('mouvements.aide')}</Typography.Paragraph>
      <Form
        form={formulaire}
        layout="vertical"
        initialValues={{ type: 'FACTURE' }}
        onFinish={(v) => envoi.mutate(v)}
      >
        <Flex gap="middle" wrap>
          <Form.Item name="type" label={t('mouvements.type')} rules={requis}>
            <Select
              style={{ minWidth: 160 }}
              options={TYPES_MOUVEMENT.map((v) => ({ value: v, label: t(`types.${v}`) }))}
            />
          </Form.Item>
          <Form.Item name="date" label={t('mouvements.date')} rules={requis}>
            <Input type="date" />
          </Form.Item>
          <Form.Item name="montant" label={t('mouvements.montant')} rules={requis}>
            <Input inputMode="decimal" />
          </Form.Item>
        </Flex>
        <Form.Item name="reference" label={t('mouvements.reference')}>
          <Input maxLength={100} />
        </Form.Item>
        <Form.Item name="motif" label={t('mouvements.motif')}>
          <Input maxLength={500} />
        </Form.Item>
        <Button type="primary" htmlType="submit" loading={envoi.isPending}>
          {tCommun('actions.enregistrer')}
        </Button>
      </Form>
    </Card>
  )
}

function Indicateurs({ indicateurs }: { indicateurs: IndicateursRecetteSortie }) {
  const { t } = useTranslation('recettes')
  return (
    <Flex gap="large" wrap>
      {MONTANTS.map((cle) => (
        <Statistic
          key={cle}
          title={t(`indicateurs.${cle}`)}
          valueRender={() => <Montant valeur={indicateurs[cle]} />}
        />
      ))}
      <Statistic
        title={t('indicateurs.tauxRecouvrement')}
        valueRender={() => <Taux valeur={indicateurs.tauxRecouvrement} />}
      />
      <Statistic
        title={t('indicateurs.tauxRealisation')}
        valueRender={() => <Taux valeur={indicateurs.tauxRealisation} />}
      />
    </Flex>
  )
}

/** Tableau de bord des recettes (T-263) : filtres par nature, service et période. */
function TableauDeBordRecettes() {
  const { t } = useTranslation('recettes')
  const { t: tCommun } = useTranslation()
  const exercices = useOptions('exercices')
  const centres = useOptions('centres-responsabilite')
  const [filtres, setFiltres] = useState<{
    exerciceId?: string
    nature?: string
    centreId?: string
    du?: string
    au?: string
  }>({})
  const exerciceId = filtres.exerciceId ?? exercices.at(-1)?.value
  const parametres = Object.fromEntries(
    Object.entries({ ...filtres, exerciceId }).filter(([, v]) => v),
  ) as Parameters<typeof tableauRecettes>[0]
  const { data, isFetching } = useQuery({
    queryKey: ['tableau-recettes', parametres],
    enabled: Boolean(exerciceId),
    queryFn: () => tableauRecettes(parametres),
  })
  const changer = (nom: string) => (valeur?: string) =>
    setFiltres((f) => ({ ...f, [nom]: valeur || undefined }))
  const repartition = (titre: string, lignes: RepartitionRecettes[], traduire = false) => (
    <Card title={titre} size="small">
      <Table<RepartitionRecettes>
        rowKey="cle"
        size="small"
        pagination={false}
        loading={isFetching}
        scroll={{ x: 'max-content' }}
        locale={{ emptyText: tCommun('tableau.aucun') }}
        dataSource={lignes}
        columns={[
          {
            title: titre,
            dataIndex: 'libelle',
            render: (v: string) =>
              traduire ? t(`natures.${v}`) : v === '-' ? t('sansService') : v,
          },
          ...MONTANTS.map((cle) => ({
            title: t(`indicateurs.${cle}`),
            key: cle,
            align: 'end' as const,
            render: (_: unknown, r: RepartitionRecettes) => <Montant valeur={r.indicateurs[cle]} />,
          })),
          {
            title: t('indicateurs.tauxRecouvrement'),
            key: 'taux',
            align: 'end',
            render: (_, r) => <Taux valeur={r.indicateurs.tauxRecouvrement} />,
          },
        ]}
      />
    </Card>
  )
  return (
    <Flex vertical gap="middle">
      <Flex gap="small" wrap>
        <Select
          aria-label={t('filtres.exercice')}
          style={{ minWidth: 160 }}
          options={exercices}
          value={exerciceId}
          onChange={changer('exerciceId')}
        />
        <Select
          allowClear
          aria-label={t('filtres.nature')}
          placeholder={t('filtres.nature')}
          style={{ minWidth: 220 }}
          options={NATURES.map((n) => ({ value: n, label: t(`natures.${n}`) }))}
          value={filtres.nature}
          onChange={changer('nature')}
        />
        <Select
          allowClear
          aria-label={t('filtres.service')}
          placeholder={t('filtres.service')}
          style={{ minWidth: 220 }}
          options={centres}
          value={filtres.centreId}
          onChange={changer('centreId')}
        />
        {BORNES.map((nom) => (
          <Input
            key={nom}
            type="date"
            aria-label={t(`filtres.${nom}`)}
            style={{ width: 160 }}
            value={filtres[nom] ?? ''}
            onChange={(e) => changer(nom)(e.target.value)}
          />
        ))}
      </Flex>
      {data && (
        <>
          <Card size="small">
            <Indicateurs indicateurs={data.totaux} />
          </Card>
          {repartition(t('repartitions.nature'), data.parNature, true)}
          {repartition(t('repartitions.service'), data.parService)}
          {repartition(t('repartitions.mois'), data.parMois)}
        </>
      )}
    </Flex>
  )
}
