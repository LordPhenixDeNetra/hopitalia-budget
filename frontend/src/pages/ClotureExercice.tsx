import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { App, Button, Card, Flex, Form, Input, Modal, Select, Table, Typography } from 'antd'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useAfficherErreur } from '../api/erreurs'
import { cloturerExercice, listerClotures, reouvrirExercice } from '../api/genere/budget'
import type { ClotureSortie } from '../api/genere/budget.schemas'
import { BadgeStatut } from '../composants/BadgeStatut'
import { Montant } from '../composants/Montant'
import { formaterDateHeure } from '../format/format'
import { useOptions } from './parametrage/PageReferentiel'

interface SaisieCloture {
  etablissementId: string
  exerciceSuivantId: string
  motif: string
}

/** Clôture d'exercice par établissement, avec report des reliquats, et réouverture (T-239, T-240). */
export function ClotureExercice() {
  const { t, i18n } = useTranslation('cloture')
  const { t: tCommun } = useTranslation()
  const { message, modal } = App.useApp()
  const afficherErreur = useAfficherErreur()
  const client = useQueryClient()
  const [formulaire] = Form.useForm<SaisieCloture>()
  const [motif] = Form.useForm<{ motif: string }>()
  const exercices = useOptions('exercices')
  const etablissements = useOptions('etablissements')
  const [exerciceId, setExerciceId] = useState<string>()
  const [aRouvrir, setARouvrir] = useState<ClotureSortie>()
  const { data: historique = [] } = useQuery({
    queryKey: ['clotures', exerciceId],
    queryFn: () => listerClotures(exerciceId!),
    enabled: Boolean(exerciceId),
  })
  const rafraichir = () => void client.invalidateQueries({ queryKey: ['clotures'] })
  const cloture = useMutation({
    mutationFn: (v: SaisieCloture) => cloturerExercice(exerciceId!, v),
    onSuccess: (c) => {
      void message.success(
        t('cloturee', { nombre: c.engagementsReportes, montant: c.montantReporte }),
      )
      formulaire.resetFields(['motif'])
      rafraichir()
    },
    onError: (erreur) => afficherErreur(erreur, formulaire),
  })
  const reouverture = useMutation({
    mutationFn: (v: { motif: string }) =>
      reouvrirExercice(aRouvrir!.exerciceId, {
        etablissementId: aRouvrir!.etablissementId,
        motif: v.motif,
      }),
    onSuccess: () => {
      void message.success(t('rouvert'))
      setARouvrir(undefined)
      motif.resetFields()
      rafraichir()
    },
    onError: (erreur) => afficherErreur(erreur, motif),
  })
  const requis = [{ required: true, message: tCommun('connexion.obligatoire') }]
  const nom = (options: { value: string; label: string }[], id: string) =>
    options.find((o) => o.value === id)?.label ?? id

  return (
    <Flex vertical gap="middle">
      <Typography.Title level={1} style={{ margin: 0 }}>
        {t('titre')}
      </Typography.Title>
      <Typography.Paragraph>{t('intro')}</Typography.Paragraph>
      <Select
        aria-label={t('exercice')}
        placeholder={t('exercice')}
        style={{ maxWidth: 240 }}
        options={exercices}
        value={exerciceId}
        onChange={setExerciceId}
      />
      {exerciceId && (
        <Card size="small" title={t('cloturer')}>
          <Form
            form={formulaire}
            layout="vertical"
            onFinish={(v) =>
              modal.confirm({
                title: t('confirmation'),
                content: t('avertissement'),
                okText: t('cloturer'),
                cancelText: tCommun('actions.annuler'),
                onOk: () => cloture.mutate(v),
              })
            }
          >
            <Flex gap="middle" wrap>
              <Form.Item name="etablissementId" label={t('etablissement')} rules={requis}>
                <Select style={{ minWidth: 240 }} options={etablissements} />
              </Form.Item>
              <Form.Item name="exerciceSuivantId" label={t('suivant')} rules={requis}>
                <Select
                  style={{ minWidth: 160 }}
                  options={exercices.filter((e) => e.value !== exerciceId)}
                />
              </Form.Item>
            </Flex>
            <Form.Item name="motif" label={t('motif')} rules={requis}>
              <Input.TextArea maxLength={500} />
            </Form.Item>
            <Button htmlType="submit" type="primary" danger loading={cloture.isPending}>
              {t('cloturer')}
            </Button>
          </Form>
        </Card>
      )}
      {exerciceId && (
        <Table<ClotureSortie>
          rowKey="id"
          size="small"
          pagination={false}
          dataSource={historique}
          scroll={{ x: 'max-content' }}
          locale={{ emptyText: tCommun('tableau.aucun') }}
          columns={[
            {
              title: t('etablissement'),
              dataIndex: 'etablissementId',
              render: (v: string) => nom(etablissements, v),
            },
            {
              title: t('suivant'),
              dataIndex: 'exerciceSuivantId',
              render: (v: string) => nom(exercices, v),
            },
            {
              title: t('le'),
              dataIndex: 'creeLe',
              render: (v: string) => formaterDateHeure(v, i18n.language),
            },
            { title: t('engagementsReportes'), dataIndex: 'engagementsReportes', align: 'end' },
            {
              title: t('montantReporte'),
              dataIndex: 'montantReporte',
              align: 'end',
              render: (v: string) => <Montant valeur={v} />,
            },
            { title: t('motif'), dataIndex: 'motif' },
            {
              title: t('etat'),
              key: 'etat',
              render: (_, c) =>
                c.reouvertLe ? (
                  <BadgeStatut
                    ton="info"
                    libelle={`${t('rouvertLe')} ${formaterDateHeure(c.reouvertLe, i18n.language)}`}
                  />
                ) : (
                  <Flex gap="small" wrap>
                    <BadgeStatut ton="neutre" libelle={t('clos')} />
                    <Button size="small" onClick={() => setARouvrir(c)}>
                      {t('rouvrir')}
                    </Button>
                  </Flex>
                ),
            },
          ]}
        />
      )}
      <Modal
        open={Boolean(aRouvrir)}
        title={t('rouvrir')}
        okText={tCommun('actions.enregistrer')}
        cancelText={tCommun('actions.annuler')}
        confirmLoading={reouverture.isPending}
        onOk={() => motif.submit()}
        onCancel={() => setARouvrir(undefined)}
        destroyOnHidden
      >
        <Form form={motif} layout="vertical" onFinish={(v) => reouverture.mutate(v)}>
          <Form.Item name="motif" label={t('motif')} rules={requis}>
            <Input.TextArea maxLength={500} />
          </Form.Item>
        </Form>
      </Modal>
    </Flex>
  )
}
