import { PlusOutlined } from '@ant-design/icons'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import {
  App,
  Button,
  Flex,
  Form,
  Input,
  Modal,
  Popconfirm,
  Select,
  Space,
  Tag,
  Typography,
} from 'antd'
import type { ColumnsType } from 'antd/es/table/interface'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useSearchParams } from 'react-router'
import { useAfficherErreur } from '../api/erreurs'
import {
  attribuerHabilitation,
  getListerHabilitationsQueryKey,
  retirerHabilitation,
  useListerEtablissements,
  useListerHabilitations,
} from '../api/genere/budget'
import {
  Profil,
  type HabilitationCreation,
  type HabilitationSortie,
} from '../api/genere/budget.schemas'
import { useSession } from '../auth/session'
import { TableauServeur, type EtatTableau } from '../composants/TableauServeur'

const PROFILS = Object.values(Profil)
const TOUS = 'tous'

/** Établissements où l'utilisateur peut attribuer : null dans la liste = « tous » (global). */
function useEtablissementsAdministres(): (string | null)[] {
  const { moi } = useSession()
  return (moi?.habilitations ?? [])
    .filter((h) => h.profil === Profil.ADM)
    .map((h) => h.etablissementId ?? null)
}

function FormulaireAttribution({ ouvert, fermer }: { ouvert: boolean; fermer: () => void }) {
  const { t } = useTranslation('habilitations')
  const { t: tCommun } = useTranslation()
  const { message } = App.useApp()
  const afficherErreur = useAfficherErreur()
  const client = useQueryClient()
  const [formulaire] = Form.useForm<HabilitationCreation & { etablissementId: string }>()
  // Une clé par ouverture du formulaire : un double envoi n'attribue qu'une fois.
  const [cle, setCle] = useState(() => crypto.randomUUID())
  const administres = useEtablissementsAdministres()
  const global = administres.includes(null)
  const { data: etablissements } = useListerEtablissements({ actif: true, taille: 100 })
  const choix = (etablissements?.donnees ?? []).filter((e) => global || administres.includes(e.id))

  const attribution = useMutation({
    mutationFn: ({
      etablissementId,
      ...reste
    }: HabilitationCreation & { etablissementId: string }) =>
      attribuerHabilitation(
        { ...reste, etablissementId: etablissementId === TOUS ? null : etablissementId },
        { headers: { 'Idempotency-Key': cle } },
      ),
    onSuccess: (cree) => {
      void client.invalidateQueries({ queryKey: getListerHabilitationsQueryKey() })
      void message.success(
        t('notifications.attribue', {
          profil: t(`profils.${cree.profil}`),
          agent: cree.nomAgent || cree.codeAgent,
        }),
      )
      formulaire.resetFields()
      setCle(crypto.randomUUID())
      fermer()
    },
    onError: (erreur) => afficherErreur(erreur, formulaire),
  })

  return (
    <Modal
      open={ouvert}
      title={t('formulaire.titre')}
      okText={tCommun('actions.enregistrer')}
      cancelText={tCommun('actions.annuler')}
      confirmLoading={attribution.isPending}
      onOk={() => formulaire.submit()}
      onCancel={fermer}
    >
      <Form
        form={formulaire}
        layout="vertical"
        initialValues={{ etablissementId: global ? TOUS : choix[0]?.id }}
        onFinish={(valeurs) => attribution.mutate(valeurs)}
      >
        <Form.Item
          name="codeAgent"
          label={t('formulaire.codeAgent')}
          extra={t('formulaire.aideCode')}
          rules={[{ required: true, message: tCommun('connexion.obligatoire') }]}
        >
          <Input maxLength={20} autoComplete="off" />
        </Form.Item>
        <Form.Item
          name="profil"
          label={t('formulaire.profil')}
          rules={[{ required: true, message: tCommun('connexion.obligatoire') }]}
        >
          <Select
            options={PROFILS.map((p) => ({ value: p, label: `${p} — ${t(`profils.${p}`)}` }))}
          />
        </Form.Item>
        <Form.Item
          name="etablissementId"
          label={t('formulaire.etablissement')}
          extra={t('formulaire.aideEtablissement')}
          rules={[{ required: true, message: tCommun('connexion.obligatoire') }]}
        >
          <Select
            options={[
              ...(global ? [{ value: TOUS, label: t('tousEtablissements') }] : []),
              ...choix.map((e) => ({ value: e.id, label: `${e.code} — ${e.nom}` })),
            ]}
          />
        </Form.Item>
      </Form>
    </Modal>
  )
}

/** Gestion des habilitations dans le module (T-121). */
export function Habilitations() {
  const { t } = useTranslation('habilitations')
  const { message } = App.useApp()
  const afficherErreur = useAfficherErreur()
  const client = useQueryClient()
  const { moi } = useSession()
  const [recherche, setRecherche] = useSearchParams()
  const [attributionOuverte, setAttributionOuverte] = useState(false)
  const peutAttribuer = useEtablissementsAdministres().length > 0
  const etat: EtatTableau = {
    page: Number(recherche.get('page') ?? 1),
    taille: Number(recherche.get('taille') ?? 25),
    tri: recherche.get('tri') ?? undefined,
  }
  const profil = recherche.get('profil') ?? undefined
  const etablissementId = recherche.get('etablissementId') ?? undefined
  const { data, isFetching } = useListerHabilitations({
    ...etat,
    profil: profil as Profil | undefined,
    etablissementId,
  })
  const { data: etablissements } = useListerEtablissements({ taille: 100 })
  const nomEtablissement = (id: string | null | undefined) => {
    if (!id) return t('tousEtablissements')
    const e = etablissements?.donnees.find((x) => x.id === id)
    return e ? `${e.code} — ${e.nom}` : id
  }

  const changer = (suivant: Record<string, string | number | undefined>) => {
    const valeurs = { ...etat, profil, etablissementId, ...suivant }
    const nouvelle = new URLSearchParams()
    for (const [cle, valeur] of Object.entries(valeurs)) {
      if (valeur !== undefined && valeur !== '') nouvelle.set(cle, String(valeur))
    }
    setRecherche(nouvelle)
  }

  const retrait = useMutation({
    mutationFn: (id: string) => retirerHabilitation(id),
    onSuccess: () => void message.success(t('notifications.retire')),
    onError: (erreur) => afficherErreur(erreur),
    onSettled: () => void client.invalidateQueries({ queryKey: getListerHabilitationsQueryKey() }),
  })

  const actions = (h: HabilitationSortie) =>
    h.utilisateurId === moi?.idHopitalia ? (
      <Typography.Text type="secondary">{t('actions.vosDroits')}</Typography.Text>
    ) : (
      <Popconfirm
        title={t('actions.confirmerRetrait', {
          profil: h.profil,
          agent: h.nomAgent || h.codeAgent,
        })}
        onConfirm={() => retrait.mutate(h.id)}
      >
        <Button danger size="small" loading={retrait.isPending && retrait.variables === h.id}>
          {t('actions.retirer')}
        </Button>
      </Popconfirm>
    )

  const colonnes: ColumnsType<HabilitationSortie> = [
    { title: t('colonnes.codeAgent'), dataIndex: 'codeAgent', sorter: true },
    { title: t('colonnes.nomAgent'), dataIndex: 'nomAgent', sorter: true },
    {
      title: t('colonnes.profil'),
      dataIndex: 'profil',
      sorter: true,
      render: (p: Profil) => (
        <Space>
          <Tag>{p}</Tag>
          {t(`profils.${p}`)}
        </Space>
      ),
    },
    {
      title: t('colonnes.etablissement'),
      dataIndex: 'etablissementId',
      render: (id: string | null) => nomEtablissement(id),
    },
    ...(peutAttribuer ? [{ title: t('colonnes.actions'), key: 'actions', render: actions }] : []),
  ]

  return (
    <Flex vertical gap="middle">
      <Flex justify="space-between" align="center" wrap gap="small">
        <Typography.Title level={1} style={{ margin: 0 }}>
          {t('titre')}
        </Typography.Title>
        {peutAttribuer && (
          <Button
            type="primary"
            icon={<PlusOutlined aria-hidden />}
            onClick={() => setAttributionOuverte(true)}
          >
            {t('actions.attribuer')}
          </Button>
        )}
      </Flex>
      <Typography.Paragraph type="secondary">{t('intro')}</Typography.Paragraph>
      <Flex gap="small" wrap>
        <Select
          aria-label={t('filtres.profil')}
          style={{ minWidth: 220 }}
          value={profil ?? ''}
          onChange={(valeur) => changer({ profil: valeur || undefined, page: 1 })}
          options={[
            { value: '', label: `${t('filtres.profil')} : ${t('filtres.tous')}` },
            ...PROFILS.map((p) => ({ value: p, label: `${p} — ${t(`profils.${p}`)}` })),
          ]}
        />
        <Select
          aria-label={t('filtres.etablissement')}
          style={{ minWidth: 220 }}
          value={etablissementId ?? ''}
          onChange={(valeur) => changer({ etablissementId: valeur || undefined, page: 1 })}
          options={[
            { value: '', label: `${t('filtres.etablissement')} : ${t('filtres.tous')}` },
            ...(etablissements?.donnees ?? []).map((e) => ({
              value: e.id,
              label: `${e.code} — ${e.nom}`,
            })),
          ]}
        />
      </Flex>
      <TableauServeur<HabilitationSortie>
        nom="habilitations"
        colonnes={colonnes}
        donnees={data?.donnees ?? []}
        total={data?.pagination.total ?? 0}
        chargement={isFetching}
        etat={etat}
        surChangement={(suivant) => changer({ ...suivant })}
        cleLigne={(h) => h.id}
        carte={(h) => (
          <Space direction="vertical">
            <Typography.Text strong>
              {h.codeAgent} — {h.nomAgent}
            </Typography.Text>
            <Typography.Text>{t(`profils.${h.profil}`)}</Typography.Text>
            <Typography.Text type="secondary">
              {nomEtablissement(h.etablissementId)}
            </Typography.Text>
            {peutAttribuer && actions(h)}
          </Space>
        )}
      />
      <FormulaireAttribution
        ouvert={attributionOuverte}
        fermer={() => setAttributionOuverte(false)}
      />
    </Flex>
  )
}
