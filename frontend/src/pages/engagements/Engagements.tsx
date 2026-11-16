import { PlusOutlined } from '@ant-design/icons'
import { useQuery } from '@tanstack/react-query'
import { Button, Flex, Select, Space, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table/interface'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useSearchParams } from 'react-router'
import { getListerEngagementsQueryKey, listerEngagements } from '../../api/genere/budget'
import type { EngagementSortie, ListerEngagementsParams } from '../../api/genere/budget.schemas'
import { useAProfil } from '../../auth/session'
import { BadgeStatut, type Ton } from '../../composants/BadgeStatut'
import { Montant } from '../../composants/Montant'
import { TableauServeur } from '../../composants/TableauServeur'
import { formaterDate } from '../../format/format'
import { FormulaireEngagement, ORIGINES } from './FormulaireEngagement'

export const TONS_ENGAGEMENT: Record<string, Ton> = {
  BROUILLON: 'neutre',
  SOUMIS: 'info',
  EN_CONTROLE: 'attention',
  A_CORRIGER: 'attention',
  VALIDE: 'succes',
  REJETE: 'erreur',
  PARTIELLEMENT_EXECUTE: 'info',
  EXECUTE: 'succes',
  CLOTURE: 'neutre',
  ANNULE: 'neutre',
}
// Profils qui saisissent les engagements (DEMANDER_ENGAGEMENT, matrice des habilitations).
export const SAISIE_ENGAGEMENT = ['GMC', 'SD']

/** Liste des engagements, filtrable par statut et par origine (T-150). */
export function Engagements() {
  const { t, i18n } = useTranslation('engagements')
  const naviguer = useNavigate()
  const peutSaisir = useAProfil(SAISIE_ENGAGEMENT)
  const [creation, setCreation] = useState(false)
  const [parametres, setParametres] = useSearchParams()
  const filtres: ListerEngagementsParams = {
    page: Number(parametres.get('page') ?? 1),
    taille: Number(parametres.get('taille') ?? 25),
    ...Object.fromEntries(
      ['statut', 'origine', 'tri'].map((k) => [k, parametres.get(k)]).filter(([, v]) => v),
    ),
  }
  const { data, isFetching } = useQuery({
    queryKey: getListerEngagementsQueryKey(filtres),
    queryFn: () => listerEngagements(filtres),
  })
  const filtrer = (cle: string, valeur?: string | null) => {
    const suivants = new URLSearchParams(parametres)
    if (valeur) suivants.set(cle, valeur)
    else suivants.delete(cle)
    suivants.delete('page')
    setParametres(suivants)
  }
  const choix = (valeurs: string[]) => valeurs.map((v) => ({ value: v, label: t(`valeurs.${v}`) }))
  const statut = (e: EngagementSortie) => (
    <BadgeStatut ton={TONS_ENGAGEMENT[e.statut] ?? 'neutre'} libelle={t(`valeurs.${e.statut}`)} />
  )
  const colonnes: ColumnsType<EngagementSortie> = [
    {
      title: t('champs.numero'),
      dataIndex: 'numero',
      sorter: true,
      render: (v: string, e) => <Link to={`/engagements/${e.id}`}>{v}</Link>,
    },
    {
      title: t('champs.dateEngagement'),
      dataIndex: 'dateEngagement',
      sorter: true,
      render: (v: string) => formaterDate(v, i18n.language),
    },
    { title: t('champs.objet'), dataIndex: 'objet' },
    { title: t('champs.origine'), dataIndex: 'origine', render: (v: string) => t(`valeurs.${v}`) },
    {
      title: t('champs.montant'),
      dataIndex: 'montant',
      align: 'end',
      sorter: true,
      render: (v: string) => <Montant valeur={v} />,
    },
    { title: t('champs.statut'), key: 'statut', render: (_, e) => statut(e) },
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
            onClick={() => setCreation(true)}
          >
            {t('creer')}
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
          options={choix(Object.keys(TONS_ENGAGEMENT))}
        />
        <Select
          aria-label={t('filtres.origine')}
          placeholder={t('filtres.origine')}
          allowClear
          style={{ minWidth: 200 }}
          value={parametres.get('origine') ?? undefined}
          onChange={(v) => filtrer('origine', v)}
          options={choix(ORIGINES)}
        />
      </Flex>
      <TableauServeur<EngagementSortie>
        nom="engagements"
        colonnes={colonnes}
        donnees={data?.donnees ?? []}
        total={data?.pagination.total ?? 0}
        chargement={isFetching}
        etat={{
          page: filtres.page ?? 1,
          taille: filtres.taille ?? 25,
          tri: filtres.tri ?? undefined,
        }}
        surChangement={(e) => {
          const suivants = new URLSearchParams(parametres)
          suivants.set('page', String(e.page))
          suivants.set('taille', String(e.taille))
          if (e.tri) suivants.set('tri', e.tri)
          else suivants.delete('tri')
          setParametres(suivants)
        }}
        cleLigne={(e) => e.id}
        carte={(e) => (
          <Space direction="vertical">
            <Link to={`/engagements/${e.id}`}>{`${e.numero} — ${e.objet}`}</Link>
            <Montant valeur={e.montant} />
            {statut(e)}
          </Space>
        )}
      />
      {creation && (
        <FormulaireEngagement
          fermer={() => setCreation(false)}
          enregistre={(e) => naviguer(`/engagements/${e.id}`)}
        />
      )}
    </Flex>
  )
}
