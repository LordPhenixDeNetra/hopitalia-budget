import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  App,
  Button,
  Flex,
  Input,
  List,
  Select,
  Space,
  Switch,
  Table,
  Tabs,
  Typography,
} from 'antd'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'
import { useAfficherErreur } from '../api/erreurs'
import {
  getLireMoiQueryKey,
  lancerAlertesPlanifiees,
  listerAlertes,
  listerRegles,
  marquerAlerte,
  modifierPreferences,
  modifierRegle,
} from '../api/genere/budget'
import type { AlerteSortie, RegleSortie, TypeAlerte } from '../api/genere/budget.schemas'
import { useAProfil, useSession } from '../auth/session'
import { BadgeStatut } from '../composants/BadgeStatut'
import { formaterDateHeure } from '../format/format'
import { useOptions } from './parametrage/PageReferentiel'

// Écran de l'objet concerné, quand il en a un.
const ECRANS: Record<string, string> = {
  Engagement: '/engagements',
  Contrat: '/contrats',
  Facture: '/factures',
}

function LigneAlerte({ alerte, basculer }: { alerte: AlerteSortie; basculer: () => void }) {
  const { t, i18n } = useTranslation('alertes')
  const ecran = ECRANS[alerte.typeObjet]
  return (
    <List.Item
      actions={[
        <Button key="lue" size="small" onClick={basculer}>
          {t(alerte.lue ? 'marquerNonLue' : 'marquerLue')}
        </Button>,
      ]}
    >
      <Flex vertical gap={4}>
        <Space wrap>
          <BadgeStatut
            ton={alerte.gravite === 'BLOCAGE' ? 'erreur' : 'attention'}
            libelle={t(`gravites.${alerte.gravite}`)}
          />
          {!alerte.lue && <BadgeStatut ton="info" libelle={t('nonLue')} />}
          <Typography.Text strong>{t(`types.${alerte.type}`)}</Typography.Text>
        </Space>
        <Typography.Text>
          {t(`messages.${alerte.type}`, { ...alerte.details, defaultValue: '' })}
        </Typography.Text>
        <Typography.Text type="secondary">
          {formaterDateHeure(alerte.creeLe, i18n.language)}
          {alerte.codeAgent ? ` — ${alerte.codeAgent}` : ''}
          {ecran && (
            <>
              {' — '}
              <Link to={`${ecran}/${alerte.idObjet}`}>{t('voir')}</Link>
            </>
          )}
        </Typography.Text>
      </Flex>
    </List.Item>
  )
}

/** Centre d'alertes : les plus récentes d'abord, paginées par curseur (T-224). */
function CentreAlertes() {
  const { t } = useTranslation('alertes')
  const afficherErreur = useAfficherErreur()
  const client = useQueryClient()
  const [nonLues, setNonLues] = useState(true)
  const { data, fetchNextPage, hasNextPage, isFetching } = useInfiniteQuery({
    queryKey: ['alertes', nonLues],
    initialPageParam: undefined as string | undefined,
    queryFn: ({ pageParam }) =>
      listerAlertes({ nonLues: nonLues || undefined, apres: pageParam, taille: 20 }),
    getNextPageParam: (page) => page.suivant ?? undefined,
  })
  const lecture = useMutation({
    mutationFn: (a: AlerteSortie) => marquerAlerte(a.id, { lue: !a.lue }),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ['alertes'] })
      void client.invalidateQueries({ queryKey: ['compteur-alertes'] })
    },
    onError: (erreur) => afficherErreur(erreur),
  })
  const alertes = data?.pages.flatMap((p) => p.donnees) ?? []

  return (
    <Flex vertical gap="middle">
      <Space>
        <Switch checked={nonLues} onChange={setNonLues} aria-label={t('nonLuesSeulement')} />
        <Typography.Text>{t('nonLuesSeulement')}</Typography.Text>
      </Space>
      <List
        loading={isFetching}
        dataSource={alertes}
        locale={{ emptyText: t('aucune') }}
        renderItem={(a) => <LigneAlerte alerte={a} basculer={() => lecture.mutate(a)} />}
      />
      {hasNextPage && (
        <Button style={{ alignSelf: 'center' }} onClick={() => void fetchNextPage()}>
          {t('plus')}
        </Button>
      )}
    </Flex>
  )
}

/** Seuils, délais et activation par établissement (T-220), réservés à l'administrateur. */
function Regles() {
  const { t } = useTranslation('alertes')
  const { t: tCommun } = useTranslation()
  const { message } = App.useApp()
  const afficherErreur = useAfficherErreur()
  const client = useQueryClient()
  const etablissements = useOptions('etablissements')
  const [etablissementId, setEtablissementId] = useState<string>()
  const [saisies, setSaisies] = useState<Record<string, Partial<RegleSortie>>>({})
  const { data: regles = [], isFetching } = useQuery({
    queryKey: ['regles-alertes', etablissementId],
    queryFn: () => listerRegles({ etablissementId: etablissementId! }),
    enabled: Boolean(etablissementId),
  })
  const enregistrement = useMutation({
    mutationFn: (r: RegleSortie) =>
      modifierRegle(
        r.type,
        {
          actif: r.actif,
          seuilPourcent: r.seuilPourcent,
          delaiJours: r.delaiJours,
          notifierParEmail: r.notifierParEmail,
        },
        { etablissementId: etablissementId! },
      ),
    onSuccess: (r) => {
      void message.success(t('regles.enregistree'))
      setSaisies((s) => ({ ...s, [r.type]: {} }))
      void client.invalidateQueries({ queryKey: ['regles-alertes'] })
    },
    onError: (erreur) => afficherErreur(erreur),
  })
  const planification = useMutation({
    mutationFn: () => lancerAlertesPlanifiees(),
    onSuccess: () => {
      void message.success(t('regles.planifiee'))
      void client.invalidateQueries({ queryKey: ['alertes'] })
      void client.invalidateQueries({ queryKey: ['compteur-alertes'] })
    },
    onError: (erreur) => afficherErreur(erreur),
  })
  const valeur = (r: RegleSortie): RegleSortie => ({ ...r, ...saisies[r.type] })
  const modifier = (type: TypeAlerte, champ: Partial<RegleSortie>) =>
    setSaisies((s) => ({ ...s, [type]: { ...s[type], ...champ } }))

  return (
    <Flex vertical gap="middle">
      <Flex gap="small" wrap>
        <Select
          aria-label={t('regles.etablissement')}
          placeholder={t('regles.etablissement')}
          style={{ minWidth: 240 }}
          options={etablissements}
          value={etablissementId}
          onChange={setEtablissementId}
        />
        <Button loading={planification.isPending} onClick={() => planification.mutate()}>
          {t('regles.lancer')}
        </Button>
      </Flex>
      {etablissementId && (
        <Table<RegleSortie>
          rowKey="type"
          size="small"
          loading={isFetching}
          pagination={false}
          dataSource={regles}
          scroll={{ x: 'max-content' }}
          columns={[
            { title: t('regles.type'), dataIndex: 'type', render: (v: string) => t(`types.${v}`) },
            {
              title: t('regles.actif'),
              key: 'actif',
              render: (_, r) => (
                <Switch
                  aria-label={`${t('regles.actif')} — ${t(`types.${r.type}`)}`}
                  checked={valeur(r).actif}
                  onChange={(actif) => modifier(r.type, { actif })}
                />
              ),
            },
            {
              title: t('regles.seuilPourcent'),
              key: 'seuil',
              render: (_, r) =>
                r.seuilPourcent !== null && (
                  <Input
                    aria-label={`${t('regles.seuilPourcent')} — ${t(`types.${r.type}`)}`}
                    inputMode="decimal"
                    style={{ width: 90 }}
                    value={valeur(r).seuilPourcent ?? ''}
                    onChange={(e) => modifier(r.type, { seuilPourcent: e.target.value })}
                  />
                ),
            },
            {
              title: t('regles.delaiJours'),
              key: 'delai',
              render: (_, r) =>
                r.delaiJours !== null && (
                  <Input
                    aria-label={`${t('regles.delaiJours')} — ${t(`types.${r.type}`)}`}
                    inputMode="numeric"
                    style={{ width: 90 }}
                    value={valeur(r).delaiJours ?? ''}
                    onChange={(e) => modifier(r.type, { delaiJours: Number(e.target.value) })}
                  />
                ),
            },
            {
              title: t('regles.parCourriel'),
              key: 'courriel',
              render: (_, r) => (
                <Switch
                  aria-label={`${t('regles.parCourriel')} — ${t(`types.${r.type}`)}`}
                  checked={valeur(r).notifierParEmail}
                  onChange={(notifierParEmail) => modifier(r.type, { notifierParEmail })}
                />
              ),
            },
            {
              key: 'enregistrer',
              render: (_, r) =>
                saisies[r.type] &&
                Object.keys(saisies[r.type]).length > 0 && (
                  <Button
                    size="small"
                    type="primary"
                    onClick={() => enregistrement.mutate(valeur(r))}
                  >
                    {tCommun('actions.enregistrer')}
                  </Button>
                ),
            },
          ]}
        />
      )}
    </Flex>
  )
}

export function Alertes() {
  const { t } = useTranslation('alertes')
  const administrateur = useAProfil(['ADM'])
  return (
    <Flex vertical gap="middle">
      <Typography.Title level={1} style={{ margin: 0 }}>
        {t('titre')}
      </Typography.Title>
      <Typography.Paragraph>{t('intro')}</Typography.Paragraph>
      <CourrielAlertes />
      <Tabs
        items={[
          { key: 'alertes', label: t('onglets.alertes'), children: <CentreAlertes /> },
          ...(administrateur
            ? [{ key: 'regles', label: t('onglets.regles'), children: <Regles /> }]
            : []),
        ]}
      />
    </Flex>
  )
}

/** Adresse où l'agent reçoit ses alertes par courriel (T-225) ; vide : pas de courriel. */
function CourrielAlertes() {
  const { t } = useTranslation('alertes')
  const { moi } = useSession()
  const { message } = App.useApp()
  const afficherErreur = useAfficherErreur()
  const client = useQueryClient()
  const [saisie, setSaisie] = useState<string>()
  const valeur = saisie ?? moi?.courriel ?? ''
  const envoi = useMutation({
    mutationFn: () => modifierPreferences({ courriel: valeur.trim() || null }),
    onSuccess: (enregistre) => {
      client.setQueryData(getLireMoiQueryKey(), enregistre)
      setSaisie(undefined)
      void message.success(t('courriel.enregistre'))
    },
    onError: (erreur) => afficherErreur(erreur),
  })
  return (
    <Flex gap="small" align="center" wrap>
      <Typography.Text id="courriel-alertes">{t('courriel.libelle')}</Typography.Text>
      <Input
        type="email"
        aria-labelledby="courriel-alertes"
        style={{ maxWidth: 280 }}
        value={valeur}
        onChange={(e) => setSaisie(e.target.value)}
        placeholder={t('courriel.exemple')}
      />
      <Button loading={envoi.isPending} onClick={() => envoi.mutate()}>
        {t('courriel.enregistrer')}
      </Button>
    </Flex>
  )
}
