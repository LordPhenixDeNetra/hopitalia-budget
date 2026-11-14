import { useMutation, useQueryClient } from '@tanstack/react-query'
import { App, Button, Card, Flex, Form, Input, Space, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table/interface'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useAfficherErreur } from '../api/erreurs'
import {
  creerDelegation,
  getListerDelegationsQueryKey,
  modifierDelegation,
  useListerDelegations,
} from '../api/genere/budget'
import type { DelegationCreation, DelegationSortie } from '../api/genere/budget.schemas'
import { BadgeStatut } from '../composants/BadgeStatut'
import { TableauServeur, type EtatTableau } from '../composants/TableauServeur'
import { formaterDate } from '../format/format'

const aujourdhui = () => new Date().toISOString().slice(0, 10)

/** Délégations temporaires de visa (T-115) : données et reçues ; toutes pour ADM et AUD. */
export function Delegations() {
  const { t, i18n } = useTranslation('workflow')
  const { t: tCommun } = useTranslation()
  const { message } = App.useApp()
  const afficherErreur = useAfficherErreur()
  const client = useQueryClient()
  const [formulaire] = Form.useForm<DelegationCreation>()
  const [cle, setCle] = useState(() => crypto.randomUUID())
  const [etat, setEtat] = useState<EtatTableau>({ page: 1, taille: 25 })
  const { data, isFetching } = useListerDelegations({ page: etat.page, taille: etat.taille })
  const rafraichir = () =>
    void client.invalidateQueries({ queryKey: getListerDelegationsQueryKey() })

  const creation = useMutation({
    mutationFn: (v: DelegationCreation) =>
      creerDelegation(v, { headers: { 'Idempotency-Key': cle } }),
    onSuccess: () => {
      formulaire.resetFields()
      setCle(crypto.randomUUID())
      rafraichir()
      void message.success(t('delegations.creee'))
    },
    onError: (erreur) => afficherErreur(erreur, formulaire),
  })
  // Révoquer : la délégation se termine la veille, elle n'autorise plus rien dès aujourd'hui.
  const revocation = useMutation({
    mutationFn: (d: DelegationSortie) => {
      const veille = new Date(Date.now() - 86_400_000).toISOString().slice(0, 10)
      return modifierDelegation(
        d.id,
        { dateFin: veille },
        { headers: { 'If-Match': `"${d.version}"` } },
      )
    },
    onSuccess: () => {
      rafraichir()
      void message.success(t('delegations.revoquee'))
    },
    onError: (erreur) => afficherErreur(erreur),
  })

  const etatDelegation = (d: DelegationSortie) => {
    const jour = aujourdhui()
    if (d.dateFin < jour || d.dateFin < d.dateDebut)
      return <BadgeStatut ton="neutre" libelle={t('delegations.terminee')} />
    if (d.dateDebut > jour) return <BadgeStatut ton="info" libelle={t('delegations.aVenir')} />
    return <BadgeStatut ton="succes" libelle={t('delegations.active')} />
  }
  const date = (v: string) => formaterDate(v, i18n.language)
  const revoquer = (d: DelegationSortie) =>
    d.dateFin >= aujourdhui() && (
      <Button size="small" danger onClick={() => revocation.mutate(d)}>
        {t('delegations.revoquer')}
      </Button>
    )
  const colonnes: ColumnsType<DelegationSortie> = [
    { title: t('delegations.delegantCode'), dataIndex: 'delegantCode' },
    { title: t('delegations.delegataireCode'), dataIndex: 'delegataireCode' },
    { title: t('delegations.dateDebut'), dataIndex: 'dateDebut', render: date },
    { title: t('delegations.dateFin'), dataIndex: 'dateFin', render: date },
    { title: t('delegations.motif'), dataIndex: 'motif' },
    { title: t('delegations.etat'), key: 'etat', render: (_, d) => etatDelegation(d) },
    { key: 'actions', render: (_, d) => revoquer(d) },
  ]
  const requis = [{ required: true, message: tCommun('connexion.obligatoire') }]

  return (
    <Flex vertical gap="middle">
      <Typography.Title level={1}>{t('delegations.titre')}</Typography.Title>
      <Typography.Paragraph>{t('delegations.intro')}</Typography.Paragraph>
      <Card>
        <Form
          form={formulaire}
          layout="vertical"
          initialValues={{ dateDebut: aujourdhui() }}
          onFinish={(v) => creation.mutate(v)}
        >
          <Flex gap="middle" wrap>
            <Form.Item
              name="delegataireCode"
              label={t('delegations.delegataireCode')}
              rules={requis}
            >
              <Input maxLength={20} />
            </Form.Item>
            <Form.Item name="dateDebut" label={t('delegations.dateDebut')} rules={requis}>
              <Input type="date" />
            </Form.Item>
            <Form.Item name="dateFin" label={t('delegations.dateFin')} rules={requis}>
              <Input type="date" />
            </Form.Item>
          </Flex>
          <Form.Item name="motif" label={t('delegations.motif')} rules={requis}>
            <Input maxLength={500} />
          </Form.Item>
          <Button type="primary" htmlType="submit" loading={creation.isPending}>
            {t('delegations.creer')}
          </Button>
        </Form>
      </Card>
      <TableauServeur<DelegationSortie>
        colonnes={colonnes}
        donnees={data?.donnees ?? []}
        total={data?.pagination.total ?? 0}
        chargement={isFetching}
        etat={etat}
        surChangement={setEtat}
        cleLigne={(d) => d.id}
        carte={(d) => (
          <Space direction="vertical">
            <Typography.Text strong>
              {d.delegantCode} → {d.delegataireCode}
            </Typography.Text>
            <Typography.Text>
              {date(d.dateDebut)} – {date(d.dateFin)}
            </Typography.Text>
            <Typography.Text>{d.motif}</Typography.Text>
            {etatDelegation(d)}
            {revoquer(d)}
          </Space>
        )}
      />
    </Flex>
  )
}
