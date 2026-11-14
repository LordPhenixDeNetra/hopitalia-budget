import { useMutation, useQueryClient } from '@tanstack/react-query'
import { App, Button, Flex, Form, Input, Modal, Select, Space, Timeline, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table/interface'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useAfficherErreur } from '../../api/erreurs'
import {
  deciderRevision,
  getListerRevisionsQueryKey,
  getObtenirDisponibiliteQueryKey,
  getObtenirSituationQueryKey,
  soumettreRevision,
  useListerRevisions,
} from '../../api/genere/budget'
import type { RevisionCreation, RevisionSortie } from '../../api/genere/budget.schemas'
import { useAProfil } from '../../auth/session'
import { BadgeStatut, type Ton } from '../../composants/BadgeStatut'
import { Montant } from '../../composants/Montant'
import { TableauServeur, type EtatTableau } from '../../composants/TableauServeur'
import { formaterDateHeure } from '../../format/format'
import { useOptions } from '../parametrage/PageReferentiel'

const TONS: Record<string, Ton> = {
  SOUMISE: 'info',
  VISEE: 'attention',
  VALIDEE: 'succes',
  REJETEE: 'erreur',
}
/** Profil attendu à chaque étape (section 17, point 16 : visa DAF puis ordonnateur). */
const ETAPES: Record<string, string> = { SOUMISE: 'VAL', VISEE: 'ORD' }

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

/** Révisions budgétaires d'un budget ou d'une ligne : demande, visas et décision (T-095). */
export function Revisions({ budgetId, ligneId }: { budgetId: string; ligneId?: string }) {
  const { t, i18n } = useTranslation('budget')
  const { t: tCommun } = useTranslation()
  const { message, modal } = App.useApp()
  const afficherErreur = useAfficherErreur()
  const client = useQueryClient()
  const peutDemander = useAProfil(['RB'])
  const estVal = useAProfil(['VAL'])
  const estOrd = useAProfil(['ORD'])
  const [etat, setEtat] = useState<EtatTableau>({ page: 1, taille: 25 })
  const [demande, setDemande] = useState(false)
  const lignes = useOptions(`lignes-budgetaires?budgetId=${budgetId}`)
  const { data, isFetching } = useListerRevisions({
    ...(ligneId ? { ligneId } : { budgetId }),
    page: etat.page,
    taille: etat.taille,
  })

  const decision = useMutation({
    mutationFn: ({ id, valide, motif }: { id: string; valide: boolean; motif?: string }) =>
      deciderRevision(id, { decision: valide ? 'VALIDE' : 'REJETE', motif }),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: getListerRevisionsQueryKey() })
      void client.invalidateQueries({ queryKey: getObtenirSituationQueryKey(budgetId) })
      if (ligneId)
        void client.invalidateQueries({ queryKey: getObtenirDisponibiliteQueryKey(ligneId) })
      void message.success(t('revisions.decision'))
    },
    onError: (erreur) => afficherErreur(erreur),
  })
  const rejeter = (id: string) => {
    let motif = ''
    modal.confirm({
      title: t('revisions.motifRejet'),
      content: (
        <Input.TextArea
          aria-label={t('revisions.motifRejet')}
          onChange={(e) => (motif = e.target.value)}
        />
      ),
      okText: t('revisions.rejeter'),
      cancelText: tCommun('actions.annuler'),
      onOk: () => decision.mutateAsync({ id, valide: false, motif }),
    })
  }

  const ligne = (id?: string | null) => lignes.find((l) => l.value === id)?.label ?? ''
  const peutDecider = (r: RevisionSortie) =>
    (ETAPES[r.statut] === 'VAL' && estVal) || (ETAPES[r.statut] === 'ORD' && estOrd)
  const actions = (r: RevisionSortie) =>
    peutDecider(r) && (
      <Space wrap>
        <Button
          size="small"
          type="primary"
          onClick={() => decision.mutate({ id: r.id, valide: true })}
        >
          {t('revisions.valider')}
        </Button>
        <Button size="small" danger onClick={() => rejeter(r.id)}>
          {t('revisions.rejeter')}
        </Button>
      </Space>
    )
  const visas = (r: RevisionSortie) =>
    r.visas.length > 0 && (
      <Timeline
        items={r.visas.map((v) => ({
          key: `${v.etape}-${v.horodatage}`,
          content: `${t(`revisions.${v.decision}`)} — ${v.codeAgent} — ${formaterDateHeure(v.horodatage, i18n.language)}${v.motif ? ` — ${v.motif}` : ''}`,
        }))}
      />
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
      align: 'right',
      render: (v: string) => <Montant valeur={v} />,
    },
    { title: t('revisions.motif'), dataIndex: 'motif' },
    { title: t('revisions.statut'), key: 'statut', render: (_, r) => statut(r) },
    { title: t('revisions.visas'), key: 'visas', render: (_, r) => visas(r) },
    {
      title: t('revisions.creeLe'),
      dataIndex: 'creeLe',
      render: (v: string) => formaterDateHeure(v, i18n.language),
    },
    { key: 'actions', render: (_, r) => actions(r) },
  ]

  return (
    <Flex vertical gap="middle">
      {peutDemander && (
        <Button type="primary" style={{ alignSelf: 'flex-start' }} onClick={() => setDemande(true)}>
          {t('revisions.creer')}
        </Button>
      )}
      <TableauServeur<RevisionSortie>
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
            {visas(r)}
            {actions(r)}
          </Space>
        )}
      />
      {demande && <Demande budgetId={budgetId} fermer={() => setDemande(false)} />}
    </Flex>
  )
}
