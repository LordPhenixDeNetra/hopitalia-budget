import { PlusOutlined } from '@ant-design/icons'
import { useQuery } from '@tanstack/react-query'
import { Button, Flex, Input, Progress, Select, Space, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table/interface'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useSearchParams } from 'react-router'
import { getListerContratsQueryKey, listerContrats } from '../../api/genere/budget'
import type { ContratResume, ListerContratsParams } from '../../api/genere/budget.schemas'
import { useAProfil } from '../../auth/session'
import { BadgeStatut, type Ton } from '../../composants/BadgeStatut'
import { Montant } from '../../composants/Montant'
import { TableauServeur } from '../../composants/TableauServeur'
import { formaterDate } from '../../format/format'
import { useOptions } from '../parametrage/PageReferentiel'
import { FormulaireContrat, TYPES } from './FormulaireContrat'

export const TONS_STATUT: Record<string, Ton> = {
  BROUILLON: 'neutre',
  SOUMIS: 'info',
  EN_VALIDATION: 'attention',
  A_CORRIGER: 'attention',
  VALIDE: 'succes',
  REJETE: 'erreur',
}
const STATUTS = Object.keys(TONS_STATUT)

/** Consommation affichée en texte et en barre : jamais par la seule couleur (IHM-06). */
export function Consommation({ taux }: { taux?: string | null }) {
  if (taux == null) return null
  const valeur = Number(taux)
  return (
    <Progress
      percent={Math.min(valeur, 100)}
      format={() => `${taux} %`}
      status={valeur >= 100 ? 'exception' : 'normal'}
      size="small"
    />
  )
}

/** Liste des contrats : filtres de l'annexe 18.1, dont le niveau de consommation (T-138). */
export function Contrats() {
  const { t, i18n } = useTranslation('contrats')
  const naviguer = useNavigate()
  const peutSaisir = useAProfil(['GMC'])
  const [creation, setCreation] = useState(false)
  const [parametres, setParametres] = useSearchParams()
  const filtres: ListerContratsParams = {
    page: Number(parametres.get('page') ?? 1),
    taille: Number(parametres.get('taille') ?? 25),
    ...Object.fromEntries(
      ['type', 'statut', 'fournisseurId', 'centreId', 'consommationMin', 'tri']
        .map((k) => [k, parametres.get(k)])
        .filter(([, v]) => v),
    ),
  }
  const { data, isFetching } = useQuery({
    queryKey: getListerContratsQueryKey(filtres),
    queryFn: () => listerContrats(filtres),
  })
  const fournisseurs = useOptions('fournisseurs')
  const centres = useOptions('centres-responsabilite')
  const filtrer = (cle: string, valeur?: string | null) => {
    const suivants = new URLSearchParams(parametres)
    if (valeur) suivants.set(cle, valeur)
    else suivants.delete(cle)
    suivants.delete('page')
    setParametres(suivants)
  }
  const choix = (valeurs: string[]) => valeurs.map((v) => ({ value: v, label: t(`valeurs.${v}`) }))
  const statut = (c: ContratResume) => (
    <BadgeStatut ton={TONS_STATUT[c.statut] ?? 'neutre'} libelle={t(`valeurs.${c.statut}`)} />
  )
  const colonnes: ColumnsType<ContratResume> = [
    {
      title: t('champs.numero'),
      dataIndex: 'numero',
      sorter: true,
      render: (v: string, c) => <Link to={`/contrats/${c.id}`}>{v}</Link>,
    },
    { title: t('champs.intitule'), dataIndex: 'intitule' },
    { title: t('champs.type'), dataIndex: 'type', render: (v: string) => t(`valeurs.${v}`) },
    { title: t('champs.fournisseur'), dataIndex: 'fournisseur' },
    { title: t('champs.statut'), key: 'statut', render: (_, c) => statut(c) },
    {
      title: t('champs.montantActualise'),
      dataIndex: 'montantActualise',
      align: 'end',
      render: (v: string) => <Montant valeur={v} />,
    },
    {
      title: t('champs.tauxConsommation'),
      key: 'taux',
      width: 160,
      render: (_, c) => <Consommation taux={c.tauxConsommation} />,
    },
    {
      title: t('champs.dateEcheance'),
      dataIndex: 'dateEcheance',
      sorter: true,
      render: (v?: string | null) => (v ? formaterDate(v, i18n.language) : ''),
    },
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
          aria-label={t('filtres.type')}
          placeholder={t('filtres.type')}
          allowClear
          style={{ minWidth: 160 }}
          value={parametres.get('type') ?? undefined}
          onChange={(v) => filtrer('type', v)}
          options={choix(TYPES)}
        />
        <Select
          aria-label={t('filtres.statut')}
          placeholder={t('filtres.statut')}
          allowClear
          style={{ minWidth: 160 }}
          value={parametres.get('statut') ?? undefined}
          onChange={(v) => filtrer('statut', v)}
          options={choix(STATUTS)}
        />
        <Select
          aria-label={t('filtres.fournisseur')}
          placeholder={t('filtres.fournisseur')}
          allowClear
          showSearch
          optionFilterProp="label"
          style={{ minWidth: 220 }}
          value={parametres.get('fournisseurId') ?? undefined}
          onChange={(v) => filtrer('fournisseurId', v)}
          options={fournisseurs}
        />
        <Select
          aria-label={t('filtres.centre')}
          placeholder={t('filtres.centre')}
          allowClear
          showSearch
          optionFilterProp="label"
          style={{ minWidth: 220 }}
          value={parametres.get('centreId') ?? undefined}
          onChange={(v) => filtrer('centreId', v)}
          options={centres}
        />
        <Input
          aria-label={t('filtres.consommationMin')}
          placeholder={t('filtres.consommationMin')}
          inputMode="decimal"
          style={{ width: 220 }}
          defaultValue={parametres.get('consommationMin') ?? ''}
          onBlur={(e) => filtrer('consommationMin', e.target.value)}
        />
      </Flex>
      <TableauServeur<ContratResume>
        nom="contrats"
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
        cleLigne={(c) => c.id}
        carte={(c) => (
          <Space direction="vertical" style={{ width: '100%' }}>
            <Link to={`/contrats/${c.id}`}>{`${c.numero} — ${c.intitule}`}</Link>
            <Typography.Text>{c.fournisseur}</Typography.Text>
            {statut(c)}
            <Montant valeur={c.montantActualise} />
            <Consommation taux={c.tauxConsommation} />
          </Space>
        )}
      />
      {creation && (
        <FormulaireContrat
          fermer={() => setCreation(false)}
          enregistre={(c) => naviguer(`/contrats/${c.id}`)}
        />
      )}
    </Flex>
  )
}
