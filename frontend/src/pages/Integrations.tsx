import { RedoOutlined, SyncOutlined } from '@ant-design/icons'
import { useInfiniteQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { App, Button, Flex, Select, Space, Table, Typography } from 'antd'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useAfficherErreur } from '../api/erreurs'
import { lancerEchange, listerEchanges, reprendreEchange } from '../api/genere/budget'
import {
  StatutEchange,
  TypeEchange,
  type EchangeSortie,
  type ListerEchangesParams,
} from '../api/genere/budget.schemas'
import { useSession } from '../auth/session'
import { BadgeStatut, type Ton } from '../composants/BadgeStatut'
import { formaterDateHeure } from '../format/format'

const TONS: Record<string, Ton> = { EN_COURS: 'info', SUCCES: 'succes', ECHEC: 'erreur' }

/** Journal des échanges avec Hopitalia et reprises (T-200, INT-07). */
export function Integrations() {
  const { t, i18n } = useTranslation('integrations')
  const { t: tCommun } = useTranslation()
  const { t: tErreurs } = useTranslation('erreurs')
  // Code d'erreur traduit quand il est connu (I18N-07), sinon affiché tel quel.
  const erreur = (code: string) => tErreurs(code, { defaultValue: code })
  const { message } = App.useApp()
  const afficherErreur = useAfficherErreur()
  const client = useQueryClient()
  const { moi } = useSession()
  // Matrice : l'administrateur lance et reprend ; RB et AUD consultent.
  const administre = (moi?.habilitations ?? []).some((h) => h.profil === 'ADM')
  const [filtres, setFiltres] = useState<ListerEchangesParams>({})
  const { data, fetchNextPage, hasNextPage, isFetching } = useInfiniteQuery({
    queryKey: ['journal-integration', filtres],
    initialPageParam: undefined as string | undefined,
    queryFn: ({ pageParam }) => listerEchanges({ ...filtres, apres: pageParam, taille: 50 }),
    getNextPageParam: (page) => page.pagination.suivant ?? undefined,
  })
  const lignes = data?.pages.flatMap((p) => p.donnees) ?? []
  const apres = (echange: EchangeSortie) => {
    if (echange.statut === 'SUCCES') void message.success(t('reussi'))
    else void message.error(t('echoue', { erreur: erreur(echange.erreur ?? '') }))
    void client.invalidateQueries({ queryKey: ['journal-integration'] })
  }
  const lancement = useMutation({
    mutationFn: (typeDonnees: TypeEchange) => lancerEchange({ typeDonnees }),
    onSuccess: apres,
    onError: (erreur) => afficherErreur(erreur),
  })
  const reprise = useMutation({
    mutationFn: (id: number) => reprendreEchange(id),
    onSuccess: apres,
    onError: (erreur) => afficherErreur(erreur),
  })

  return (
    <Flex vertical gap="middle">
      <Typography.Title level={1} style={{ margin: 0 }}>
        {t('titre')}
      </Typography.Title>
      <Typography.Paragraph>{t('intro')}</Typography.Paragraph>
      {administre && (
        <Space wrap>
          {Object.values(TypeEchange).map((type) => (
            <Button
              key={type}
              icon={<SyncOutlined aria-hidden />}
              loading={lancement.isPending && lancement.variables === type}
              onClick={() => lancement.mutate(type)}
            >
              {t(`lancer.${type}`)}
            </Button>
          ))}
        </Space>
      )}
      <Flex gap="small" wrap>
        <Select
          allowClear
          aria-label={t('filtres.type')}
          placeholder={t('filtres.type')}
          style={{ minWidth: 200 }}
          value={filtres.typeDonnees}
          onChange={(typeDonnees) => setFiltres((f) => ({ ...f, typeDonnees }))}
          options={Object.values(TypeEchange).map((v) => ({ value: v, label: t(`types.${v}`) }))}
        />
        <Select
          allowClear
          aria-label={t('filtres.statut')}
          placeholder={t('filtres.statut')}
          style={{ minWidth: 160 }}
          value={filtres.statut}
          onChange={(statut) => setFiltres((f) => ({ ...f, statut }))}
          options={Object.values(StatutEchange).map((v) => ({
            value: v,
            label: t(`statuts.${v}`),
          }))}
        />
      </Flex>
      <Table<EchangeSortie>
        rowKey="id"
        size="small"
        loading={isFetching}
        dataSource={lignes}
        pagination={false}
        scroll={{ x: 'max-content' }}
        locale={{ emptyText: tCommun('tableau.aucun') }}
        columns={[
          {
            title: t('colonnes.date'),
            dataIndex: 'date',
            render: (v: string) => formaterDateHeure(v, i18n.language),
          },
          {
            title: t('colonnes.type'),
            dataIndex: 'typeDonnees',
            render: (v: string) => t(`types.${v}`),
          },
          {
            title: t('colonnes.periode'),
            key: 'periode',
            render: (_, e) => Object.values(e.parametres).join(' – '),
          },
          {
            title: t('colonnes.statut'),
            dataIndex: 'statut',
            render: (v: string) => (
              <BadgeStatut ton={TONS[v] ?? 'neutre'} libelle={t(`statuts.${v}`)} />
            ),
          },
          { title: t('colonnes.tentatives'), dataIndex: 'tentatives' },
          {
            title: t('colonnes.resultat'),
            key: 'resultat',
            render: (_, e) =>
              e.erreur
                ? erreur(e.erreur)
                : Object.entries(e.resultat ?? {})
                    .map(([cle, n]) => t(`resultats.${cle}`, { count: n }))
                    .join(', '),
          },
          { title: t('colonnes.declencheur'), dataIndex: 'declencheParCode' },
          {
            title: t('colonnes.actions'),
            key: 'actions',
            render: (_, e) =>
              administre && e.statut === 'ECHEC' ? (
                <Button
                  size="small"
                  icon={<RedoOutlined aria-hidden />}
                  loading={reprise.isPending && reprise.variables === e.id}
                  onClick={() => reprise.mutate(e.id)}
                >
                  {t('reprendre')}
                </Button>
              ) : null,
          },
        ]}
      />
      {hasNextPage && (
        <Button style={{ alignSelf: 'center' }} onClick={() => void fetchNextPage()}>
          {t('plus')}
        </Button>
      )}
    </Flex>
  )
}
