import { MinusCircleOutlined, PlusOutlined } from '@ant-design/icons'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  App,
  Button,
  Card,
  Flex,
  Form,
  Input,
  Modal,
  Select,
  Space,
  Switch,
  Table,
  Typography,
} from 'antd'
import type { ColumnsType } from 'antd/es/table/interface'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'
import { useAfficherErreur } from '../../api/erreurs'
import { emettreCommande, listerBonsCommande, listerReserves } from '../../api/genere/budget'
import type { BonCommandeCreation, BonCommandeSortie } from '../../api/genere/budget.schemas'
import { BadgeStatut } from '../../composants/BadgeStatut'
import { Montant } from '../../composants/Montant'
import { formaterDate } from '../../format/format'

export const TYPES_ORDRE = ['BON_COMMANDE', 'TRANCHE', 'ORDRE_SERVICE']

/** Délai écrit en clair, jamais par la seule couleur (IHM-06). */
export function Delai({ commande }: { commande: BonCommandeSortie }) {
  const { t } = useTranslation('commandes')
  return commande.enRetard ? (
    <BadgeStatut ton="erreur" libelle={t('retard')} />
  ) : (
    <BadgeStatut ton="succes" libelle={t('aJour')} />
  )
}

/** Bons de commande : tous, ceux d'un engagement, ou seulement ceux en retard (EF-REC-06). */
export function ListeCommandes({
  engagementId,
  enRetard = false,
}: {
  engagementId?: string
  enRetard?: boolean
}) {
  const { t, i18n } = useTranslation('commandes')
  const { t: tCommun } = useTranslation()
  const parametres = { engagementId, enRetard: enRetard || undefined, taille: 100 }
  const { data, isFetching } = useQuery({
    queryKey: ['bons-commande', parametres],
    queryFn: () => listerBonsCommande(parametres),
  })
  const colonnes: ColumnsType<BonCommandeSortie> = [
    {
      title: t('champs.numero'),
      dataIndex: 'numero',
      render: (v: string, c) => <Link to={`/bons-commande/${c.id}`}>{v}</Link>,
    },
    { title: t('champs.type'), dataIndex: 'type', render: (v: string) => t(`valeurs.${v}`) },
    {
      title: t('champs.dateEmission'),
      dataIndex: 'dateEmission',
      render: (v: string) => formaterDate(v, i18n.language),
    },
    {
      title: t('champs.dateLivraisonPrevue'),
      dataIndex: 'dateLivraisonPrevue',
      render: (v?: string | null) => (v ? formaterDate(v, i18n.language) : ''),
    },
    {
      title: t('champs.montantTtc'),
      dataIndex: 'montantTtc',
      align: 'right',
      render: (v: string) => <Montant valeur={v} />,
    },
    { title: t('champs.enRetard'), key: 'retard', render: (_, c) => <Delai commande={c} /> },
  ]
  return (
    <Table<BonCommandeSortie>
      rowKey="id"
      loading={isFetching}
      columns={colonnes}
      dataSource={data?.donnees ?? []}
      pagination={false}
      scroll={{ x: 'max-content' }}
      locale={{ emptyText: tCommun('tableau.aucun') }}
    />
  )
}

/** Émission d'une commande avec ses lignes, sur un engagement validé (EF-CMD-01). */
export function FormulaireCommande({
  engagementId,
  fermer,
}: {
  engagementId: string
  fermer: () => void
}) {
  const { t } = useTranslation('commandes')
  const { t: tCommun } = useTranslation()
  const { message } = App.useApp()
  const afficherErreur = useAfficherErreur()
  const client = useQueryClient()
  const [formulaire] = Form.useForm<BonCommandeCreation>()
  const [cle] = useState(() => crypto.randomUUID())
  const envoi = useMutation({
    mutationFn: (v: BonCommandeCreation) =>
      emettreCommande(engagementId, v, { headers: { 'Idempotency-Key': cle } }),
    onSuccess: () => {
      void message.success(t('emise'))
      void client.invalidateQueries({ queryKey: ['bons-commande'] })
      fermer()
    },
    onError: (erreur) => afficherErreur(erreur, formulaire),
  })
  const requis = [{ required: true, message: tCommun('connexion.obligatoire') }]

  return (
    <Modal
      open
      width={760}
      title={t('emettre')}
      okText={tCommun('actions.enregistrer')}
      cancelText={tCommun('actions.annuler')}
      confirmLoading={envoi.isPending}
      onOk={() => formulaire.submit()}
      onCancel={fermer}
    >
      <Form
        form={formulaire}
        layout="vertical"
        initialValues={{ type: 'BON_COMMANDE', lignes: [{ tauxTaxe: '0' }] }}
        onFinish={(v) => envoi.mutate(v)}
      >
        <Flex gap="middle" wrap>
          <Form.Item name="type" label={t('champs.type')} rules={requis}>
            <Select
              style={{ minWidth: 180 }}
              options={TYPES_ORDRE.map((v) => ({ value: v, label: t(`valeurs.${v}`) }))}
            />
          </Form.Item>
          <Form.Item name="dateEmission" label={t('champs.dateEmission')} rules={requis}>
            <Input type="date" />
          </Form.Item>
          <Form.Item name="dateLivraisonPrevue" label={t('champs.dateLivraisonPrevue')}>
            <Input type="date" />
          </Form.Item>
        </Flex>
        <Form.Item name="lieuLivraison" label={t('champs.lieuLivraison')}>
          <Input maxLength={300} />
        </Form.Item>
        <Typography.Text strong>{t('champs.lignes')}</Typography.Text>
        <Form.List name="lignes">
          {(lignes, { add, remove }) => (
            <>
              {lignes.map((c) => (
                <Space key={c.key} align="baseline" wrap>
                  <Form.Item name={[c.name, 'designation']} rules={requis}>
                    <Input
                      aria-label={t('champs.designation')}
                      placeholder={t('champs.designation')}
                    />
                  </Form.Item>
                  <Form.Item name={[c.name, 'quantite']} rules={requis}>
                    <Input
                      aria-label={t('champs.quantite')}
                      placeholder={t('champs.quantite')}
                      inputMode="decimal"
                      style={{ width: 110 }}
                    />
                  </Form.Item>
                  <Form.Item name={[c.name, 'prixUnitaire']} rules={requis}>
                    <Input
                      aria-label={t('champs.prixUnitaire')}
                      placeholder={t('champs.prixUnitaire')}
                      inputMode="decimal"
                      style={{ width: 140 }}
                    />
                  </Form.Item>
                  <Form.Item name={[c.name, 'tauxTaxe']}>
                    <Input
                      aria-label={t('champs.tauxTaxe')}
                      placeholder={t('champs.tauxTaxe')}
                      inputMode="decimal"
                      style={{ width: 90 }}
                    />
                  </Form.Item>
                  <Button
                    type="text"
                    aria-label={t('retirer')}
                    icon={<MinusCircleOutlined aria-hidden />}
                    onClick={() => remove(c.name)}
                  />
                </Space>
              ))}
              <Button
                type="dashed"
                icon={<PlusOutlined aria-hidden />}
                onClick={() => add({ tauxTaxe: '0' })}
              >
                {t('ajouterLigne')}
              </Button>
            </>
          )}
        </Form.List>
      </Form>
    </Modal>
  )
}

function ReservesALever() {
  const { t, i18n } = useTranslation('commandes')
  const { data: reserves = [] } = useQuery({
    queryKey: ['reserves', 'nonLevees'],
    queryFn: () => listerReserves({ nonLevees: true }),
  })
  return (
    <Card title={t('reservesALever')} size="small">
      <Table
        rowKey="id"
        size="small"
        pagination={false}
        dataSource={reserves}
        locale={{ emptyText: t('aucuneReserve') }}
        scroll={{ x: 'max-content' }}
        columns={[
          { title: t('reserves.description'), dataIndex: 'description' },
          {
            title: t('reserves.dateConstat'),
            dataIndex: 'dateConstat',
            render: (v: string) => formaterDate(v, i18n.language),
          },
        ]}
      />
    </Card>
  )
}

/** Suivi des commandes : retards et réserves à lever (EF-REC-06, T-166, T-167). */
export function Commandes() {
  const { t } = useTranslation('commandes')
  const [enRetard, setEnRetard] = useState(false)
  return (
    <Flex vertical gap="middle">
      <Typography.Title level={1}>{t('titre')}</Typography.Title>
      <Typography.Paragraph>{t('intro')}</Typography.Paragraph>
      <Space>
        <Switch checked={enRetard} onChange={setEnRetard} aria-label={t('enRetard')} />
        <Typography.Text>{t('enRetard')}</Typography.Text>
      </Space>
      <ListeCommandes enRetard={enRetard} />
      <ReservesALever />
    </Flex>
  )
}
