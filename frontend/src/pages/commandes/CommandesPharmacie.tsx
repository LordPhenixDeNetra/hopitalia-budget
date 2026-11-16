import { LinkOutlined } from '@ant-design/icons'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { App, Button, Flex, Segmented, Select, Space, Table, Typography } from 'antd'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'
import { useAfficherErreur } from '../../api/erreurs'
import { listerCommandesPharmacie, rattacherCommandePharmacie } from '../../api/genere/budget'
import type { CommandePharmacieSortie } from '../../api/genere/budget.schemas'
import { useSession } from '../../auth/session'
import { Montant } from '../../composants/Montant'
import { formaterDate } from '../../format/format'

const VUES = ['aRattacher', 'rattachees'] as const
type Vue = (typeof VUES)[number]

/** Commandes de la pharmacie importées d'Hopitalia, à rattacher aux engagements (EF-REC-07). */
export function CommandesPharmacie() {
  const { t, i18n } = useTranslation('integrations')
  const { t: tCommun } = useTranslation()
  const { moi } = useSession()
  // Matrice : l'agent financier rattache ; GMC et AUD consultent.
  const rattache = (moi?.habilitations ?? []).some((h) => h.profil === 'AF')
  const [vue, setVue] = useState<Vue>('aRattacher')
  const [page, setPage] = useState(1)
  const { data, isFetching } = useQuery({
    queryKey: ['commandes-pharmacie', vue, page],
    queryFn: () => listerCommandesPharmacie({ rattachee: vue === 'rattachees', page, taille: 25 }),
  })

  return (
    <Flex vertical gap="middle">
      <Typography.Title level={1} style={{ margin: 0 }}>
        {t('pharmacie.titre')}
      </Typography.Title>
      <Typography.Paragraph>{t('pharmacie.intro')}</Typography.Paragraph>
      <Segmented<Vue>
        value={vue}
        onChange={(v) => {
          setVue(v)
          setPage(1)
        }}
        options={VUES.map((v) => ({ value: v, label: t(`pharmacie.vues.${v}`) }))}
      />
      <Table<CommandePharmacieSortie>
        rowKey="id"
        size="small"
        loading={isFetching}
        dataSource={data?.donnees ?? []}
        scroll={{ x: 'max-content' }}
        locale={{ emptyText: tCommun('tableau.aucun') }}
        pagination={{
          current: page,
          pageSize: 25,
          total: data?.pagination.total ?? 0,
          onChange: setPage,
        }}
        expandable={{
          expandedRowRender: (c) => (
            <Table
              rowKey="codeProduit"
              size="small"
              pagination={false}
              dataSource={c.lignes}
              columns={[
                { title: t('pharmacie.colonnes.produit'), dataIndex: 'codeProduit' },
                { title: t('pharmacie.colonnes.designation'), dataIndex: 'nomProduit' },
                { title: t('pharmacie.colonnes.quantite'), dataIndex: 'quantite' },
                {
                  title: t('pharmacie.colonnes.montant'),
                  dataIndex: 'montant',
                  render: (v: string) => <Montant valeur={v} />,
                },
              ]}
            />
          ),
        }}
        columns={[
          { title: t('pharmacie.colonnes.numero'), dataIndex: 'numero' },
          {
            title: t('pharmacie.colonnes.date'),
            dataIndex: 'dateCommande',
            render: (v: string) => formaterDate(v, i18n.language),
          },
          { title: t('pharmacie.colonnes.fournisseur'), dataIndex: 'codeFournisseur' },
          { title: t('pharmacie.colonnes.service'), dataIndex: 'service' },
          {
            title: t('pharmacie.colonnes.montant'),
            dataIndex: 'montant',
            render: (v: string) => <Montant valeur={v} />,
          },
          {
            title: t('pharmacie.colonnes.approvisionnements'),
            dataIndex: 'approvisionnementsEnAttente',
          },
          {
            title: t('pharmacie.colonnes.rattachement'),
            key: 'rattachement',
            render: (_, c) =>
              c.bonCommandeId ? (
                <Link to={`/bons-commande/${c.bonCommandeId}`}>{t('pharmacie.voirCommande')}</Link>
              ) : rattache ? (
                <Rattacher commande={c} />
              ) : null,
          },
        ]}
      />
    </Flex>
  )
}

/** Choix de l'engagement parmi les propositions (même fournisseur, reste suffisant). */
function Rattacher({ commande }: { commande: CommandePharmacieSortie }) {
  const { t } = useTranslation('integrations')
  const { message } = App.useApp()
  const afficherErreur = useAfficherErreur()
  const client = useQueryClient()
  const [engagementId, setEngagementId] = useState<string>()
  const [cle] = useState(() => crypto.randomUUID())
  const envoi = useMutation({
    mutationFn: (id: string) =>
      rattacherCommandePharmacie(
        commande.id,
        { engagementId: id },
        { headers: { 'Idempotency-Key': cle } },
      ),
    onSuccess: () => {
      void message.success(t('pharmacie.rattachee'))
      void client.invalidateQueries({ queryKey: ['commandes-pharmacie'] })
    },
    onError: (erreur) => afficherErreur(erreur),
  })
  if (commande.propositions.length === 0) {
    return <Typography.Text type="secondary">{t('pharmacie.aucuneProposition')}</Typography.Text>
  }
  return (
    <Space wrap>
      <Select
        aria-label={`${t('pharmacie.engagement')} — ${commande.numero}`}
        placeholder={t('pharmacie.engagement')}
        style={{ minWidth: 240 }}
        value={engagementId}
        onChange={setEngagementId}
        options={commande.propositions.map((p) => ({
          value: p.engagementId,
          label: `${p.numero} — ${p.objet}`,
        }))}
      />
      <Button
        type="primary"
        icon={<LinkOutlined aria-hidden />}
        disabled={!engagementId}
        loading={envoi.isPending}
        onClick={() => engagementId && envoi.mutate(engagementId)}
      >
        {t('pharmacie.rattacher')}
      </Button>
    </Space>
  )
}
