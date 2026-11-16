import { useMutation, useQueryClient } from '@tanstack/react-query'
import { App, Button, Drawer, Flex, Form, Input, Modal, Select, Space, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table/interface'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useAfficherErreur } from '../../api/erreurs'
import {
  corrigerRevision,
  getLireValidationsQueryKey,
  getListerRevisionsQueryKey,
  getObtenirDisponibiliteQueryKey,
  getObtenirSituationQueryKey,
  resoumettre,
  soumettreRevision,
  useListerRevisions,
} from '../../api/genere/budget'
import type {
  RevisionCorrection,
  RevisionCreation,
  RevisionSortie,
} from '../../api/genere/budget.schemas'
import { useAProfil } from '../../auth/session'
import { BadgeStatut, type Ton } from '../../composants/BadgeStatut'
import { Montant } from '../../composants/Montant'
import { TableauServeur, type EtatTableau } from '../../composants/TableauServeur'
import { Pieces } from '../../composants/workflow/Pieces'
import { Validations } from '../../composants/workflow/Validations'
import { formaterDateHeure } from '../../format/format'
import { useOptions } from '../parametrage/PageReferentiel'

const TONS: Record<string, Ton> = {
  SOUMISE: 'info',
  EN_VALIDATION: 'attention',
  A_CORRIGER: 'attention',
  VALIDEE: 'succes',
  REJETEE: 'erreur',
}

function Demande({ budgetId, fermer }: { budgetId: string; fermer: () => void }) {
  const { t } = useTranslation('budget')
  const { t: tCommun } = useTranslation()
  const { message } = App.useApp()
  const afficherErreur = useAfficherErreur()
  const client = useQueryClient()
  const [formulaire] = Form.useForm<RevisionCreation>()
  const [cle] = useState(() => crypto.randomUUID())
  const lignes = useOptions(`lignes-budgetaires?budgetId=${budgetId}`)
  const type = Form.useWatch('type', formulaire)
  const envoi = useMutation({
    mutationFn: (v: RevisionCreation) =>
      soumettreRevision({ ...v, budgetId }, { headers: { 'Idempotency-Key': cle } }),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: getListerRevisionsQueryKey() })
      void message.success(t('revisions.creee'))
      fermer()
    },
    onError: (erreur) => afficherErreur(erreur, formulaire),
  })
  const requis = [{ required: true, message: tCommun('connexion.obligatoire') }]
  const choix = (valeurs: string[]) =>
    valeurs.map((v) => ({ value: v, label: t(`revisions.${v}`) }))

  return (
    <Modal
      open
      title={t('revisions.creer')}
      okText={tCommun('actions.enregistrer')}
      cancelText={tCommun('actions.annuler')}
      confirmLoading={envoi.isPending}
      onOk={() => formulaire.submit()}
      onCancel={fermer}
    >
      <Typography.Paragraph>{t('revisions.aide')}</Typography.Paragraph>
      <Form form={formulaire} layout="vertical" onFinish={(v) => envoi.mutate(v)}>
        <Form.Item name="type" label={t('revisions.type')} rules={requis}>
          <Select options={choix(['VIREMENT', 'REALLOCATION', 'BUDGET_MODIFICATIF'])} />
        </Form.Item>
        {type === 'BUDGET_MODIFICATIF' ? (
          <Form.Item name="sens" label={t('revisions.sens')} rules={requis}>
            <Select options={choix(['AUGMENTATION', 'DIMINUTION'])} />
          </Form.Item>
        ) : (
          <Form.Item name="ligneSourceId" label={t('revisions.ligneSourceId')} rules={requis}>
            <Select showSearch optionFilterProp="label" options={lignes} />
          </Form.Item>
        )}
        <Form.Item name="ligneCibleId" label={t('revisions.ligneCibleId')} rules={requis}>
          <Select showSearch optionFilterProp="label" options={lignes} />
        </Form.Item>
        <Form.Item name="montant" label={t('revisions.montant')} rules={requis}>
          <Input inputMode="decimal" />
        </Form.Item>
        <Form.Item name="motif" label={t('revisions.motif')} rules={requis}>
          <Input.TextArea maxLength={500} />
        </Form.Item>
      </Form>
    </Modal>
  )
}

/** Fiche d'une révision : correction après retour, circuit et visas, pièces (T-120). */
function Detail({
  revision,
  fermer,
  rafraichir,
}: {
  revision: RevisionSortie
  fermer: () => void
  rafraichir: () => void
}) {
  const { t } = useTranslation('budget')
  const { t: tWorkflow } = useTranslation('workflow')
  const { t: tCommun } = useTranslation()
  const { message } = App.useApp()
  const afficherErreur = useAfficherErreur()
  const client = useQueryClient()
  const [formulaire] = Form.useForm<RevisionCorrection>()
  const estResponsable = useAProfil(['RB'])
  const peutDeposer = useAProfil(['RB', 'VAL', 'ORD'])
  // Le serveur vérifie en plus que l'agent est l'auteur de la révision.
  const aCorriger = revision.statut === 'A_CORRIGER' && estResponsable
  const requis = [{ required: true, message: tCommun('connexion.obligatoire') }]
  const apres = (texte: string) => {
    void message.success(texte)
    void client.invalidateQueries({
      queryKey: getLireValidationsQueryKey('revisions-budgetaires', revision.id),
    })
    rafraichir()
  }
  const correction = useMutation({
    mutationFn: (v: RevisionCorrection) =>
      corrigerRevision(revision.id, v, { headers: { 'If-Match': `"${revision.version}"` } }),
    onSuccess: () => apres(tCommun('actions.enregistrer')),
    onError: (erreur) => afficherErreur(erreur, formulaire),
  })
  const soumission = useMutation({
    mutationFn: () => resoumettre('revisions-budgetaires', revision.id),
    onSuccess: () => apres(tWorkflow('correction.resoumise')),
    onError: (erreur) => afficherErreur(erreur),
  })

  return (
    <Drawer
      open
      size="large"
      title={`${t(`revisions.${revision.type}`)} — ${revision.motif}`}
      onClose={fermer}
    >
      <Flex vertical gap="large">
        <Typography.Text>
          {t('revisions.montant')} : <Montant valeur={revision.montant} />
        </Typography.Text>
        {aCorriger && (
          <Form
            form={formulaire}
            layout="vertical"
            initialValues={{ montant: revision.montant, motif: revision.motif }}
            onFinish={(v) => correction.mutate(v)}
          >
            <Typography.Title level={4}>{tWorkflow('correction.titre')}</Typography.Title>
            <Typography.Paragraph>{tWorkflow('correction.aide')}</Typography.Paragraph>
            <Form.Item name="montant" label={t('revisions.montant')} rules={requis}>
              <Input inputMode="decimal" />
            </Form.Item>
            <Form.Item name="motif" label={t('revisions.motif')} rules={requis}>
              <Input.TextArea maxLength={500} />
            </Form.Item>
            <Space wrap>
              <Button htmlType="submit" loading={correction.isPending}>
                {tCommun('actions.enregistrer')}
              </Button>
              <Button
                type="primary"
                loading={soumission.isPending}
                onClick={() => soumission.mutate()}
              >
                {tWorkflow('correction.resoumettre')}
              </Button>
            </Space>
          </Form>
        )}
        <Validations ressource="revisions-budgetaires" id={revision.id} surDecision={rafraichir} />
        <Pieces ressource="revisions-budgetaires" id={revision.id} peutDeposer={peutDeposer} />
      </Flex>
    </Drawer>
  )
}

/** Révisions budgétaires d'un budget ou d'une ligne : demande et suivi (T-095). */
export function Revisions({ budgetId, ligneId }: { budgetId: string; ligneId?: string }) {
  const { t, i18n } = useTranslation('budget')
  const { t: tWorkflow } = useTranslation('workflow')
  const client = useQueryClient()
  const peutDemander = useAProfil(['RB'])
  const [etat, setEtat] = useState<EtatTableau>({ page: 1, taille: 25 })
  const [demande, setDemande] = useState(false)
  const [ouverte, setOuverte] = useState<string>()
  const lignes = useOptions(`lignes-budgetaires?budgetId=${budgetId}`)
  const { data, isFetching } = useListerRevisions({
    ...(ligneId ? { ligneId } : { budgetId }),
    page: etat.page,
    taille: etat.taille,
  })
  const rafraichir = () => {
    void client.invalidateQueries({ queryKey: getListerRevisionsQueryKey() })
    void client.invalidateQueries({ queryKey: getObtenirSituationQueryKey(budgetId) })
    if (ligneId)
      void client.invalidateQueries({ queryKey: getObtenirDisponibiliteQueryKey(ligneId) })
  }
  const revision = data?.donnees.find((r) => r.id === ouverte)

  const ligne = (id?: string | null) => lignes.find((l) => l.value === id)?.label ?? ''
  const detail = (r: RevisionSortie) => (
    <Button size="small" onClick={() => setOuverte(r.id)}>
      {tWorkflow('correction.detail')}
    </Button>
  )
  const statut = (r: RevisionSortie) => (
    <BadgeStatut ton={TONS[r.statut] ?? 'neutre'} libelle={t(`revisions.${r.statut}`)} />
  )
  const colonnes: ColumnsType<RevisionSortie> = [
    {
      title: t('revisions.type'),
      dataIndex: 'type',
      render: (v: string, r) =>
        `${t(`revisions.${v}`)}${r.sens ? ` (${t(`revisions.${r.sens}`)})` : ''}`,
    },
    { title: t('revisions.ligneSourceId'), dataIndex: 'ligneSourceId', render: ligne },
    { title: t('revisions.ligneCibleId'), dataIndex: 'ligneCibleId', render: ligne },
    {
      title: t('revisions.montant'),
      dataIndex: 'montant',
      align: 'end',
      render: (v: string) => <Montant valeur={v} />,
    },
    { title: t('revisions.motif'), dataIndex: 'motif' },
    { title: t('revisions.statut'), key: 'statut', render: (_, r) => statut(r) },
    {
      title: t('revisions.creeLe'),
      dataIndex: 'creeLe',
      render: (v: string) => formaterDateHeure(v, i18n.language),
    },
    { key: 'actions', render: (_, r) => detail(r) },
  ]

  return (
    <Flex vertical gap="middle">
      {peutDemander && (
        <Button type="primary" style={{ alignSelf: 'flex-start' }} onClick={() => setDemande(true)}>
          {t('revisions.creer')}
        </Button>
      )}
      <TableauServeur<RevisionSortie>
        nom="revisions"
        colonnes={colonnes}
        donnees={data?.donnees ?? []}
        total={data?.pagination.total ?? 0}
        chargement={isFetching}
        etat={etat}
        surChangement={setEtat}
        cleLigne={(r) => r.id}
        carte={(r) => (
          <Space direction="vertical">
            <Typography.Text strong>
              {t(`revisions.${r.type}`)} — <Montant valeur={r.montant} />
            </Typography.Text>
            {statut(r)}
            <Typography.Text>
              {ligne(r.ligneSourceId)} {ligne(r.ligneCibleId)}
            </Typography.Text>
            <Typography.Text>{r.motif}</Typography.Text>
            {detail(r)}
          </Space>
        )}
      />
      {demande && <Demande budgetId={budgetId} fermer={() => setDemande(false)} />}
      {revision && (
        <Detail revision={revision} fermer={() => setOuverte(undefined)} rafraichir={rafraichir} />
      )}
    </Flex>
  )
}
