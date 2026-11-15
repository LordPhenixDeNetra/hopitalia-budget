import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  App,
  Button,
  Card,
  Checkbox,
  Descriptions,
  Drawer,
  Flex,
  Form,
  Input,
  Result,
  Select,
  Space,
  Spin,
  Table,
  Typography,
} from 'antd'
import type { ColumnsType } from 'antd/es/table/interface'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router'
import { useAfficherErreur } from '../../api/erreurs'
import {
  attesterServiceFait,
  emettreReserve,
  enregistrerReception,
  leverReserve,
  listerReceptions,
  obtenirBonCommande,
  resoumettre,
} from '../../api/genere/budget'
import type {
  BonCommandeSortie,
  LigneCommandeSortie,
  ReceptionSortie,
} from '../../api/genere/budget.schemas'
import { useAProfil } from '../../auth/session'
import { BadgeStatut, type Ton } from '../../composants/BadgeStatut'
import { Montant } from '../../composants/Montant'
import { Pieces } from '../../composants/workflow/Pieces'
import { Validations } from '../../composants/workflow/Validations'
import { formaterDate } from '../../format/format'
import { useOptions } from '../parametrage/PageReferentiel'
import { Delai } from './Commandes'

const TONS: Record<string, Ton> = {
  BROUILLON: 'neutre',
  SOUMIS: 'info',
  EN_VALIDATION: 'attention',
  A_CORRIGER: 'attention',
  VALIDE: 'succes',
  REJETE: 'erreur',
}
const MODIFIABLES = ['BROUILLON', 'A_CORRIGER']
// Réceptionnaire (ENREGISTRER_RECEPTION) ; valideurs et réceptionnaire déposent les pièces.
const RECEPTION = ['REC']

/** Saisie d'une réception, totale ou partielle, ligne par ligne (EF-REC-01, EF-REC-02). */
function FormulaireReception({
  commande,
  fermer,
}: {
  commande: BonCommandeSortie
  fermer: () => void
}) {
  const { t } = useTranslation('commandes')
  const { t: tCommun } = useTranslation()
  const { message } = App.useApp()
  const afficherErreur = useAfficherErreur()
  const client = useQueryClient()
  const [formulaire] = Form.useForm()
  const [cle] = useState(() => crypto.randomUUID())
  const centres = useOptions('centres-responsabilite')
  const envoi = useMutation({
    mutationFn: (v: {
      dateReception: string
      centreId: string
      agentResponsableCode: string
      observations?: string
      quantites: Record<string, { recue?: string; acceptee?: string; rejetee?: string }>
    }) =>
      enregistrerReception(
        commande.id,
        {
          dateReception: v.dateReception,
          centreId: v.centreId,
          agentResponsableCode: v.agentResponsableCode,
          observations: v.observations || null,
          lignes: Object.entries(v.quantites)
            .filter(([, q]) => q.recue)
            .map(([ligneCommandeId, q]) => ({
              ligneCommandeId,
              quantiteRecue: q.recue!,
              quantiteAcceptee: q.acceptee || '0',
              quantiteRejetee: q.rejetee || '0',
            })),
        },
        { headers: { 'Idempotency-Key': cle } },
      ),
    onSuccess: () => {
      void message.success(t('receptions.enregistree'))
      void client.invalidateQueries({ queryKey: ['receptions', commande.id] })
      fermer()
    },
    onError: (erreur) => afficherErreur(erreur, formulaire),
  })
  const requis = [{ required: true, message: tCommun('connexion.obligatoire') }]
  const quantite = (ligne: LigneCommandeSortie, champ: string) => (
    <Form.Item name={['quantites', ligne.id, champ]} noStyle>
      <Input
        aria-label={`${t(`receptions.${champ}`)} — ${ligne.designation}`}
        inputMode="decimal"
        style={{ width: 110 }}
      />
    </Form.Item>
  )

  return (
    <Drawer
      open
      size="large"
      title={t('receptions.enregistrer')}
      onClose={fermer}
      extra={
        <Button type="primary" loading={envoi.isPending} onClick={() => formulaire.submit()}>
          {tCommun('actions.enregistrer')}
        </Button>
      }
    >
      <Form form={formulaire} layout="vertical" onFinish={(v) => envoi.mutate(v)}>
        <Flex gap="middle" wrap>
          <Form.Item name="dateReception" label={t('receptions.date')} rules={requis}>
            <Input type="date" />
          </Form.Item>
          <Form.Item name="centreId" label={t('receptions.centreId')} rules={requis}>
            <Select
              style={{ minWidth: 220 }}
              options={centres}
              showSearch
              optionFilterProp="label"
            />
          </Form.Item>
          <Form.Item
            name="agentResponsableCode"
            label={t('receptions.agentResponsableCode')}
            rules={requis}
          >
            <Input maxLength={20} />
          </Form.Item>
        </Flex>
        <Form.Item name="observations" label={t('receptions.observations')}>
          <Input.TextArea maxLength={1000} />
        </Form.Item>
        <Typography.Paragraph type="secondary">{t('receptions.aide')}</Typography.Paragraph>
        <Table<LigneCommandeSortie>
          rowKey="id"
          size="small"
          pagination={false}
          dataSource={commande.lignes}
          scroll={{ x: 'max-content' }}
          columns={[
            { title: t('champs.designation'), dataIndex: 'designation' },
            { title: t('champs.resteARecevoir'), dataIndex: 'resteARecevoir', align: 'right' },
            {
              title: t('receptions.recue'),
              key: 'recue',
              render: (_, lg) => quantite(lg, 'recue'),
            },
            {
              title: t('receptions.acceptee'),
              key: 'acceptee',
              render: (_, lg) => quantite(lg, 'acceptee'),
            },
            {
              title: t('receptions.rejetee'),
              key: 'rejetee',
              render: (_, lg) => quantite(lg, 'rejetee'),
            },
          ]}
        />
      </Form>
    </Drawer>
  )
}

/** Détail d'une réception : quantités, réserves, attestation, service fait et pièces. */
function DetailReception({
  reception,
  commande,
  fermer,
  rafraichir,
}: {
  reception: ReceptionSortie
  commande: BonCommandeSortie
  fermer: () => void
  rafraichir: () => void
}) {
  const { t, i18n } = useTranslation('commandes')
  const { t: tCommun } = useTranslation()
  const { message } = App.useApp()
  const afficherErreur = useAfficherErreur()
  const [reserve] = Form.useForm()
  const [attestation] = Form.useForm()
  const estReceptionnaire = useAProfil(RECEPTION)
  const peutDeposer = useAProfil([...RECEPTION, 'VAL'])
  const modifiable = MODIFIABLES.includes(reception.statut)
  const apres = (texte: string) => {
    void message.success(texte)
    reserve.resetFields()
    rafraichir()
  }
  const ajoutReserve = useMutation({
    mutationFn: (v: { description: string; dateConstat: string }) =>
      emettreReserve(reception.id, v),
    onSuccess: () => apres(t('reserves.ajoutee')),
    onError: (erreur) => afficherErreur(erreur, reserve),
  })
  const levee = useMutation({
    mutationFn: (id: string) =>
      leverReserve(id, { dateLevee: new Date().toISOString().slice(0, 10) }),
    onSuccess: () => apres(t('reserves.levee')),
    onError: (erreur) => afficherErreur(erreur),
  })
  const attester = useMutation({
    mutationFn: (v: { date: string; livrable: string; conforme?: boolean }) =>
      attesterServiceFait(reception.id, { ...v, conforme: Boolean(v.conforme) }),
    onSuccess: () => apres(t('attestation.enregistree')),
    onError: (erreur) => afficherErreur(erreur, attestation),
  })
  const soumission = useMutation({
    mutationFn: () => resoumettre('receptions', reception.id),
    onSuccess: () => apres(t('receptions.soumise')),
    onError: (erreur) => afficherErreur(erreur),
  })
  const designation = (id: string) => commande.lignes.find((l) => l.id === id)?.designation ?? ''
  const date = (v?: string | null) => (v ? formaterDate(v, i18n.language) : '')
  const requis = [{ required: true, message: tCommun('connexion.obligatoire') }]

  return (
    <Drawer open size="large" title={reception.numero} onClose={fermer}>
      <Flex vertical gap="large">
        <Space wrap>
          <BadgeStatut
            ton={TONS[reception.statut] ?? 'neutre'}
            libelle={t(`valeurs.${reception.statut}`)}
          />
          {reception.statut === 'VALIDE' && (
            <Typography.Text>{t(`valeurs.${reception.type}`)}</Typography.Text>
          )}
          {estReceptionnaire && modifiable && (
            <Button
              type="primary"
              loading={soumission.isPending}
              onClick={() => soumission.mutate()}
            >
              {t('receptions.soumettre')}
            </Button>
          )}
        </Space>
        <Table
          rowKey="ligneCommandeId"
          size="small"
          pagination={false}
          dataSource={reception.lignes}
          scroll={{ x: 'max-content' }}
          columns={[
            { title: t('champs.designation'), dataIndex: 'ligneCommandeId', render: designation },
            { title: t('receptions.recue'), dataIndex: 'quantiteRecue', align: 'right' },
            { title: t('receptions.acceptee'), dataIndex: 'quantiteAcceptee', align: 'right' },
            { title: t('receptions.rejetee'), dataIndex: 'quantiteRejetee', align: 'right' },
          ]}
        />
        <Card size="small" title={t('reserves.titre')}>
          <Table
            rowKey="id"
            size="small"
            pagination={false}
            dataSource={reception.reserves}
            locale={{ emptyText: tCommun('tableau.aucun') }}
            scroll={{ x: 'max-content' }}
            columns={[
              { title: t('reserves.description'), dataIndex: 'description' },
              { title: t('reserves.dateConstat'), dataIndex: 'dateConstat', render: date },
              {
                title: t('reserves.dateLevee'),
                key: 'levee',
                render: (_, r) =>
                  r.dateLevee ? (
                    <BadgeStatut
                      ton="succes"
                      libelle={`${t('reserves.leveeLe')} ${date(r.dateLevee)}`}
                    />
                  ) : (
                    <Space>
                      <BadgeStatut ton="attention" libelle={t('reserves.nonLevee')} />
                      {estReceptionnaire && (
                        <Button size="small" onClick={() => levee.mutate(r.id)}>
                          {t('reserves.lever')}
                        </Button>
                      )}
                    </Space>
                  ),
              },
            ]}
          />
          {estReceptionnaire && (
            <Form
              form={reserve}
              layout="inline"
              style={{ marginTop: 12, rowGap: 8 }}
              onFinish={(v) => ajoutReserve.mutate(v)}
            >
              <Form.Item name="description" rules={requis}>
                <Input
                  aria-label={t('reserves.description')}
                  placeholder={t('reserves.description')}
                />
              </Form.Item>
              <Form.Item name="dateConstat" rules={requis}>
                <Input aria-label={t('reserves.dateConstat')} type="date" />
              </Form.Item>
              <Button htmlType="submit" loading={ajoutReserve.isPending}>
                {t('reserves.ajouter')}
              </Button>
            </Form>
          )}
        </Card>
        <Card size="small" title={t('attestation.titre')}>
          {reception.attestation ? (
            <Descriptions
              size="small"
              column={1}
              items={[
                {
                  key: 'date',
                  label: t('attestation.date'),
                  children: date(reception.attestation.date),
                },
                {
                  key: 'livrable',
                  label: t('attestation.livrable'),
                  children: reception.attestation.livrable,
                },
                {
                  key: 'conforme',
                  label: t('attestation.conforme'),
                  children: reception.attestation.conforme ? (
                    <BadgeStatut ton="succes" libelle={t('attestation.conforme')} />
                  ) : (
                    <BadgeStatut ton="erreur" libelle={t('attestation.nonConforme')} />
                  ),
                },
              ]}
            />
          ) : estReceptionnaire && modifiable ? (
            <Form form={attestation} layout="vertical" onFinish={(v) => attester.mutate(v)}>
              <Form.Item name="date" label={t('attestation.date')} rules={requis}>
                <Input type="date" />
              </Form.Item>
              <Form.Item name="livrable" label={t('attestation.livrable')} rules={requis}>
                <Input maxLength={500} />
              </Form.Item>
              <Form.Item name="conforme" valuePropName="checked">
                <Checkbox>{t('attestation.conforme')}</Checkbox>
              </Form.Item>
              <Button htmlType="submit" loading={attester.isPending}>
                {t('attestation.enregistrer')}
              </Button>
            </Form>
          ) : (
            <Typography.Text type="secondary">{t('attestation.aucune')}</Typography.Text>
          )}
        </Card>
        <Validations ressource="receptions" id={reception.id} surDecision={rafraichir} />
        <Pieces ressource="receptions" id={reception.id} peutDeposer={peutDeposer} />
      </Flex>
    </Drawer>
  )
}

/** Fiche d'un bon de commande : lignes, reste à recevoir et réceptions (T-167). */
export function FicheCommande() {
  const { id = '' } = useParams()
  const { t, i18n } = useTranslation('commandes')
  const { t: tCommun } = useTranslation()
  const client = useQueryClient()
  const estReceptionnaire = useAProfil(RECEPTION)
  const [saisie, setSaisie] = useState(false)
  const [ouverte, setOuverte] = useState<string>()
  const {
    data: commande,
    isLoading,
    error,
  } = useQuery({
    queryKey: ['bon-commande', id],
    queryFn: () => obtenirBonCommande(id),
  })
  const { data: receptions = [] } = useQuery({
    queryKey: ['receptions', id],
    queryFn: () => listerReceptions(id),
    enabled: Boolean(commande),
  })
  const rafraichir = () => {
    void client.invalidateQueries({ queryKey: ['bon-commande', id] })
    void client.invalidateQueries({ queryKey: ['receptions', id] })
  }

  if (isLoading) return <Spin aria-label={tCommun('tableau.chargement')} />
  if (error || !commande) {
    return (
      <Result
        status="404"
        title={tCommun('introuvable.titre')}
        subTitle={tCommun('introuvable.detail')}
        extra={<Link to="/commandes">{tCommun('menu.commandes')}</Link>}
      />
    )
  }
  const reception = receptions.find((r) => r.id === ouverte)
  const colonnesReceptions: ColumnsType<ReceptionSortie> = [
    { title: t('receptions.numero'), dataIndex: 'numero' },
    {
      title: t('receptions.date'),
      dataIndex: 'dateReception',
      render: (v: string) => formaterDate(v, i18n.language),
    },
    {
      title: t('receptions.statut'),
      dataIndex: 'statut',
      render: (v: string) => <BadgeStatut ton={TONS[v] ?? 'neutre'} libelle={t(`valeurs.${v}`)} />,
    },
    {
      key: 'actions',
      render: (_, r) => (
        <Button size="small" onClick={() => setOuverte(r.id)}>
          {t('receptions.detail')}
        </Button>
      ),
    },
  ]

  return (
    <Flex vertical gap="middle">
      <Flex justify="space-between" align="center" wrap gap="small">
        <Typography.Title level={1} style={{ margin: 0 }}>
          {commande.numero} — {t(`valeurs.${commande.type}`)}
        </Typography.Title>
        <Delai commande={commande} />
      </Flex>
      <Link to={`/engagements/${commande.engagementId}`}>{tCommun('menu.engagements')}</Link>
      <Descriptions
        bordered
        size="small"
        column={{ xs: 1, md: 2 }}
        items={[
          {
            key: 'emission',
            label: t('champs.dateEmission'),
            children: formaterDate(commande.dateEmission, i18n.language),
          },
          {
            key: 'livraison',
            label: t('champs.dateLivraisonPrevue'),
            children: commande.dateLivraisonPrevue
              ? formaterDate(commande.dateLivraisonPrevue, i18n.language)
              : '',
          },
          { key: 'lieu', label: t('champs.lieuLivraison'), children: commande.lieuLivraison },
          {
            key: 'montant',
            label: t('champs.montantTtc'),
            children: <Montant valeur={commande.montantTtc} />,
          },
        ]}
      />
      <Table<LigneCommandeSortie>
        rowKey="id"
        pagination={false}
        dataSource={commande.lignes}
        scroll={{ x: 'max-content' }}
        columns={[
          { title: t('champs.designation'), dataIndex: 'designation' },
          { title: t('champs.quantite'), dataIndex: 'quantite', align: 'right' },
          {
            title: t('champs.prixUnitaire'),
            dataIndex: 'prixUnitaire',
            align: 'right',
            render: (v: string) => <Montant valeur={v} />,
          },
          { title: t('champs.quantiteAcceptee'), dataIndex: 'quantiteAcceptee', align: 'right' },
          { title: t('champs.resteARecevoir'), dataIndex: 'resteARecevoir', align: 'right' },
        ]}
      />
      <Flex justify="space-between" align="center" wrap gap="small">
        <Typography.Title level={3} style={{ margin: 0 }}>
          {t('receptions.titre')}
        </Typography.Title>
        {estReceptionnaire && (
          <Button type="primary" onClick={() => setSaisie(true)}>
            {t('receptions.enregistrer')}
          </Button>
        )}
      </Flex>
      <Table<ReceptionSortie>
        rowKey="id"
        columns={colonnesReceptions}
        dataSource={receptions}
        pagination={false}
        scroll={{ x: 'max-content' }}
        locale={{ emptyText: tCommun('tableau.aucun') }}
      />
      {saisie && <FormulaireReception commande={commande} fermer={() => setSaisie(false)} />}
      {reception && (
        <DetailReception
          reception={reception}
          commande={commande}
          fermer={() => setOuverte(undefined)}
          rafraichir={rafraichir}
        />
      )}
    </Flex>
  )
}
