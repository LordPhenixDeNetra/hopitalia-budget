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
import { appelerApi } from '../../api/client'
import { useAfficherErreur } from '../../api/erreurs'
import {
  creerAvenant,
  getObtenirContratQueryKey,
  listerAvenants,
  obtenirContrat,
  obtenirSyntheseContrat,
  resoumettre,
} from '../../api/genere/budget'
import type { AvenantSortie, ContratSortie, SyntheseContrat } from '../../api/genere/budget.schemas'
import { useAProfil } from '../../auth/session'
import { BadgeStatut } from '../../composants/BadgeStatut'
import { Montant } from '../../composants/Montant'
import { Pieces } from '../../composants/workflow/Pieces'
import { Validations } from '../../composants/workflow/Validations'
import { formaterDate } from '../../format/format'
import { useOptions } from '../parametrage/PageReferentiel'
import { Consommation, TONS_STATUT } from './Contrats'
import { FormulaireContrat } from './FormulaireContrat'

type Element = Record<string, unknown> & { id: string }
interface ChampSousListe {
  nom: string
  type: 'texte' | 'date' | 'montant' | 'choix'
  valeurs?: string[]
}

/** Éléments rattachés au contrat (échéancier, lots, ordres de service, révisions de prix). */
function SousListe({
  contratId,
  chemin,
  titre,
  champs,
  suppression,
  peutAjouter,
}: {
  contratId: string
  chemin: string
  titre: string
  champs: ChampSousListe[]
  suppression: boolean
  peutAjouter: boolean
}) {
  const { t, i18n } = useTranslation('contrats')
  const { t: tCommun } = useTranslation()
  const { message } = App.useApp()
  const afficherErreur = useAfficherErreur()
  const client = useQueryClient()
  const [formulaire] = Form.useForm()
  const url = `/api/v1/contrats/${contratId}/${chemin}`
  const { data: elements = [] } = useQuery({
    queryKey: [url],
    queryFn: () => appelerApi<Element[]>(url),
  })
  const rafraichir = () => {
    void client.invalidateQueries({ queryKey: [url] })
    void client.invalidateQueries({ queryKey: ['synthese', contratId] })
  }
  const ajout = useMutation({
    mutationFn: (v: Record<string, unknown>) =>
      appelerApi(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(v),
      }),
    onSuccess: () => {
      formulaire.resetFields()
      rafraichir()
      void message.success(t('execution.ajoute'))
    },
    onError: (erreur) => afficherErreur(erreur, formulaire),
  })
  const retrait = useMutation({
    mutationFn: (id: string) => appelerApi(`${url}/${id}`, { method: 'DELETE' }),
    onSuccess: rafraichir,
    onError: (erreur) => afficherErreur(erreur),
  })
  const rendu = (c: ChampSousListe, v: unknown): ReactNode => {
    if (v == null) return ''
    if (c.type === 'montant') return <Montant valeur={String(v)} />
    if (c.type === 'date') return formaterDate(String(v), i18n.language)
    if (c.type === 'choix') return t(`valeurs.${String(v)}`)
    return String(v)
  }
  const colonnes: ColumnsType<Element> = champs.map((c) => ({
    title: t(`execution.${c.nom}`),
    dataIndex: c.nom,
    align: c.type === 'montant' ? 'right' : undefined,
    render: (v: unknown) => rendu(c, v),
  }))
  if (suppression && peutAjouter) {
    colonnes.push({
      key: 'actions',
      render: (_, e) => (
        <Button size="small" danger onClick={() => retrait.mutate(e.id)}>
          {t('execution.supprimer')}
        </Button>
      ),
    })
  }
  const requis = [{ required: true, message: tCommun('connexion.obligatoire') }]

  return (
    <Card title={titre} size="small">
      <Table<Element>
        rowKey="id"
        size="small"
        columns={colonnes}
        dataSource={elements}
        pagination={false}
        scroll={{ x: 'max-content' }}
        locale={{ emptyText: tCommun('tableau.aucun') }}
      />
      {peutAjouter && (
        <Form
          form={formulaire}
          layout="inline"
          style={{ marginTop: 12, rowGap: 8 }}
          onFinish={(v) => ajout.mutate(v)}
        >
          {champs.map((c) => (
            <Form.Item
              key={c.nom}
              name={c.nom}
              rules={c.nom === 'objet' || c.nom === 'indice' ? [] : requis}
            >
              {c.type === 'choix' ? (
                <Select
                  aria-label={t(`execution.${c.nom}`)}
                  placeholder={t(`execution.${c.nom}`)}
                  style={{ minWidth: 140 }}
                  options={(c.valeurs ?? []).map((v) => ({ value: v, label: t(`valeurs.${v}`) }))}
                />
              ) : (
                <Input
                  aria-label={t(`execution.${c.nom}`)}
                  placeholder={t(`execution.${c.nom}`)}
                  type={c.type === 'date' ? 'date' : 'text'}
                  inputMode={c.type === 'montant' ? 'decimal' : undefined}
                />
              )}
            </Form.Item>
          ))}
          <Button htmlType="submit" loading={ajout.isPending}>
            {t('execution.ajouter')}
          </Button>
        </Form>
      )}
    </Card>
  )
}

// Lignes de l'annexe 18.1, dans l'ordre de la fiche, puis avance, retenue et révisions de prix.
const MONTANTS_SYNTHESE = [
  'montantInitial',
  'avenantsValides',
  'montantActualise',
  'engage',
  'resteAEngager',
  'commande',
  'receptionne',
  'facture',
  'liquide',
  'transmis',
  'paye',
  'engageNonFacture',
  'resteAPayerSurLiquide',
  'resteContractuelAPayer',
  'montantAvance',
  'avanceRecuperee',
  'avanceRestantARecuperer',
  'retenueOperee',
  'retenueLiberee',
  'retenueALiberer',
  'incidenceRevisionsPrix',
] as const satisfies readonly (keyof SyntheseContrat)[]

function Synthese({ contrat }: { contrat: ContratSortie }) {
  const { t } = useTranslation('contrats')
  const { data } = useQuery({
    queryKey: ['synthese', contrat.id],
    queryFn: () => obtenirSyntheseContrat(contrat.id),
  })
  if (!data) return <Spin />
  return (
    <Flex vertical gap="middle">
      <Consommation taux={data.tauxConsommation} />
      <Descriptions
        bordered
        size="small"
        column={{ xs: 1, md: 2, xl: 3 }}
        items={MONTANTS_SYNTHESE.map((k) => ({
          key: k,
          label: t(`synthese.${k}`),
          children: <Montant valeur={data[k]} />,
        }))}
      />
    </Flex>
  )
}

function Avenants({ contrat, peutSaisir }: { contrat: ContratSortie; peutSaisir: boolean }) {
  const { t, i18n } = useTranslation('contrats')
  const { t: tCommun } = useTranslation()
  const { message } = App.useApp()
  const afficherErreur = useAfficherErreur()
  const client = useQueryClient()
  const [formulaire] = Form.useForm()
  const [ouvert, setOuvert] = useState(false)
  const [cle, setCle] = useState(() => crypto.randomUUID())
  const [detail, setDetail] = useState<AvenantSortie>()
  const peutDeposer = useAProfil(['GMC', 'VAL', 'ORD'])
  const cleRequete = ['avenants', contrat.id]
  const { data: avenants = [] } = useQuery({
    queryKey: cleRequete,
    queryFn: () => listerAvenants(contrat.id),
  })
  const rafraichir = () => {
    void client.invalidateQueries({ queryKey: cleRequete })
    void client.invalidateQueries({ queryKey: ['synthese', contrat.id] })
  }
  const creation = useMutation({
    mutationFn: (v: { objet: string; variation: string; dateEffet: string }) =>
      creerAvenant(contrat.id, v, { headers: { 'Idempotency-Key': cle } }),
    onSuccess: () => {
      void message.success(t('avenants.cree'))
      formulaire.resetFields()
      setCle(crypto.randomUUID())
      setOuvert(false)
      rafraichir()
    },
    onError: (erreur) => afficherErreur(erreur, formulaire),
  })
  const montant = (v?: string | null) => (v ? <Montant valeur={v} /> : '')
  const colonnes: ColumnsType<AvenantSortie> = [
    { title: t('avenants.numero'), dataIndex: 'numero' },
    { title: t('avenants.objet'), dataIndex: 'objet' },
    { title: t('avenants.variation'), dataIndex: 'variation', align: 'right', render: montant },
    {
      title: t('avenants.dateEffet'),
      dataIndex: 'dateEffet',
      render: (v: string) => formaterDate(v, i18n.language),
    },
    {
      title: t('champs.statut'),
      dataIndex: 'statut',
      render: (v: string) => (
        <BadgeStatut ton={TONS_STATUT[v] ?? 'neutre'} libelle={t(`valeurs.${v}`)} />
      ),
    },
    {
      title: t('avenants.montantAvant'),
      dataIndex: 'montantAvant',
      align: 'right',
      render: montant,
    },
    {
      title: t('avenants.nouveauPlafond'),
      dataIndex: 'nouveauPlafond',
      align: 'right',
      render: montant,
    },
    {
      key: 'actions',
      render: (_, a) => (
        <Button size="small" onClick={() => setDetail(a)}>
          {t('avenants.detail')}
        </Button>
      ),
    },
  ]
  const requis = [{ required: true, message: tCommun('connexion.obligatoire') }]

  return (
    <Flex vertical gap="middle">
      {contrat.statut !== 'VALIDE' ? (
        <Typography.Text type="secondary">{t('avenants.contratNonValide')}</Typography.Text>
      ) : (
        peutSaisir && (
          <Button
            type="primary"
            style={{ alignSelf: 'flex-start' }}
            onClick={() => setOuvert(true)}
          >
            {t('avenants.creer')}
          </Button>
        )
      )}
      <Table<AvenantSortie>
        rowKey="id"
        columns={colonnes}
        dataSource={avenants}
        pagination={false}
        scroll={{ x: 'max-content' }}
        locale={{ emptyText: tCommun('tableau.aucun') }}
      />
      <Modal
        open={ouvert}
        title={t('avenants.creer')}
        okText={tCommun('actions.enregistrer')}
        cancelText={tCommun('actions.annuler')}
        confirmLoading={creation.isPending}
        onOk={() => formulaire.submit()}
        onCancel={() => setOuvert(false)}
      >
        <Form form={formulaire} layout="vertical" onFinish={(v) => creation.mutate(v)}>
          <Form.Item name="objet" label={t('avenants.objet')} rules={requis}>
            <Input maxLength={500} />
          </Form.Item>
          <Form.Item
            name="variation"
            label={t('avenants.variation')}
            rules={requis}
            extra={t('avenants.aide')}
          >
            <Input inputMode="decimal" />
          </Form.Item>
          <Form.Item name="dateEffet" label={t('avenants.dateEffet')} rules={requis}>
            <Input type="date" />
          </Form.Item>
        </Form>
      </Modal>
      {detail && (
        <Drawer
          open
          size="large"
          title={t('avenants.titre', { numero: detail.numero })}
          onClose={() => setDetail(undefined)}
        >
          <Flex vertical gap="large">
            <Validations ressource="avenants" id={detail.id} surDecision={rafraichir} />
            <Pieces ressource="avenants" id={detail.id} peutDeposer={peutDeposer} />
          </Flex>
        </Drawer>
      )}
    </Flex>
  )
}

/** Fiche contrat à onglets (annexe 18.1) : /contrats/:id. */
export function FicheContrat() {
  const { id = '' } = useParams()
  const { t, i18n } = useTranslation('contrats')
  const { t: tCommun } = useTranslation()
  const { message } = App.useApp()
  const afficherErreur = useAfficherErreur()
  const client = useQueryClient()
  const peutSaisir = useAProfil(['GMC'])
  const peutDeposer = useAProfil(['GMC', 'VAL', 'ORD'])
  const [edition, setEdition] = useState(false)
  const lignes = useOptions('lignes-budgetaires')
  const fournisseurs = useOptions('fournisseurs')
  const {
    data: contrat,
    isLoading,
    error,
  } = useQuery({
    queryKey: getObtenirContratQueryKey(id),
    queryFn: () => obtenirContrat(id),
  })
  const rafraichir = () => {
    void client.invalidateQueries({ queryKey: getObtenirContratQueryKey(id) })
    void client.invalidateQueries({ queryKey: ['synthese', id] })
  }
  const soumission = useMutation({
    mutationFn: () => resoumettre('contrats', id),
    onSuccess: () => {
      void message.success(t('soumis'))
      rafraichir()
    },
    onError: (erreur) => afficherErreur(erreur),
  })

  if (isLoading) return <Spin aria-label={tCommun('tableau.chargement')} />
  if (error || !contrat) {
    return (
      <Result
        status="404"
        title={tCommun('introuvable.titre')}
        subTitle={tCommun('introuvable.detail')}
        extra={<Link to="/contrats">{tCommun('menu.contrats')}</Link>}
      />
    )
  }
  const modifiable = ['BROUILLON', 'A_CORRIGER'].includes(contrat.statut)
  const date = (v?: string | null) => (v ? formaterDate(v, i18n.language) : '')
  const montant = (v?: string | null) => (v ? <Montant valeur={v} /> : '')
  const informations: [string, ReactNode][] = [
    ['type', t(`valeurs.${contrat.type}`)],
    ['nature', contrat.nature ? t(`valeurs.${contrat.nature}`) : ''],
    ['numeroLot', contrat.numeroLot],
    ['fournisseurId', fournisseurs.find((f) => f.value === contrat.fournisseurId)?.label],
    ['objet', contrat.objet],
    ['referenceDossier', contrat.referenceDossier],
    ['dateSignature', date(contrat.dateSignature)],
    ['dateNotification', date(contrat.dateNotification)],
    ['dateDemarrage', date(contrat.dateDemarrage)],
    ['dateEcheance', date(contrat.dateEcheance)],
    ['montantInitialHt', montant(contrat.montantInitialHt)],
    ['tauxTaxe', `${contrat.tauxTaxe} %`],
    ['montantInitialTtc', montant(contrat.montantInitialTtc)],
    ['periodicite', contrat.periodicite ? t(`valeurs.${contrat.periodicite}`) : ''],
    ['tauxAvance', contrat.tauxAvance ? `${contrat.tauxAvance} %` : ''],
    ['tauxRetenueGarantie', contrat.tauxRetenueGarantie ? `${contrat.tauxRetenueGarantie} %` : ''],
    ['creeParCode', contrat.creeParCode],
  ]
  const exec = (cle: string) => t(`execution.${cle}`)
  const onglets = [
    { key: 'synthese', label: t('onglets.synthese'), children: <Synthese contrat={contrat} /> },
    {
      key: 'informations',
      label: t('onglets.informations'),
      children: (
        <Descriptions
          bordered
          size="small"
          column={{ xs: 1, md: 2 }}
          items={informations.map(([k, v]) => ({ key: k, label: t(`champs.${k}`), children: v }))}
        />
      ),
    },
    {
      key: 'ventilation',
      label: t('onglets.ventilation'),
      children: (
        <Table
          rowKey="id"
          pagination={false}
          dataSource={contrat.imputations}
          columns={[
            {
              title: t('champs.ligneId'),
              dataIndex: 'ligneId',
              render: (v: string) => lignes.find((l) => l.value === v)?.label ?? '',
            },
            {
              title: t('champs.montant'),
              dataIndex: 'montant',
              align: 'right',
              render: (v: string) => <Montant valeur={v} />,
            },
          ]}
        />
      ),
    },
    {
      key: 'avenants',
      label: t('onglets.avenants'),
      children: <Avenants contrat={contrat} peutSaisir={peutSaisir} />,
    },
    {
      key: 'execution',
      label: t('onglets.execution'),
      children: (
        <Flex vertical gap="middle">
          <SousListe
            contratId={id}
            chemin="echeances"
            titre={exec('echeances')}
            champs={[
              { nom: 'libelle', type: 'texte' },
              { nom: 'dateEcheance', type: 'date' },
              { nom: 'montantPrevu', type: 'montant' },
            ]}
            suppression
            peutAjouter={peutSaisir}
          />
          <SousListe
            contratId={id}
            chemin="lots"
            titre={exec('lots')}
            champs={[
              { nom: 'code', type: 'texte' },
              { nom: 'libelle', type: 'texte' },
              { nom: 'montant', type: 'montant' },
            ]}
            suppression
            peutAjouter={peutSaisir && modifiable}
          />
          <SousListe
            contratId={id}
            chemin="ordres-service"
            titre={exec('ordresService')}
            champs={[
              { nom: 'reference', type: 'texte' },
              {
                nom: 'type',
                type: 'choix',
                valeurs: ['DEMARRAGE', 'ARRET', 'REPRISE', 'MODIFICATION', 'AUTRE'],
              },
              { nom: 'date', type: 'date' },
              { nom: 'objet', type: 'texte' },
            ]}
            suppression={false}
            peutAjouter={peutSaisir}
          />
          <SousListe
            contratId={id}
            chemin="revisions-prix"
            titre={exec('revisionsPrix')}
            champs={[
              { nom: 'formule', type: 'texte' },
              { nom: 'indice', type: 'texte' },
              { nom: 'date', type: 'date' },
              { nom: 'incidence', type: 'montant' },
            ]}
            suppression={false}
            peutAjouter={peutSaisir}
          />
        </Flex>
      ),
    },
    {
      key: 'validation',
      label: t('onglets.validation'),
      children: (
        <Flex vertical gap="large">
          <Validations ressource="contrats" id={id} surDecision={rafraichir} />
          <Pieces ressource="contrats" id={id} peutDeposer={peutDeposer} />
        </Flex>
      ),
    },
  ]

  return (
    <Flex vertical gap="middle">
      <Flex justify="space-between" align="center" wrap gap="small">
        <Typography.Title level={1} style={{ margin: 0 }}>
          {contrat.numero} — {contrat.intitule}
        </Typography.Title>
        <Space wrap>
          <BadgeStatut
            ton={TONS_STATUT[contrat.statut] ?? 'neutre'}
            libelle={t(`valeurs.${contrat.statut}`)}
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
        <FormulaireContrat
          contrat={contrat}
          fermer={() => setEdition(false)}
          enregistre={(c) => {
            client.setQueryData(getObtenirContratQueryKey(id), c)
            void client.invalidateQueries({ queryKey: ['synthese', id] })
            setEdition(false)
          }}
        />
      )}
    </Flex>
  )
}
