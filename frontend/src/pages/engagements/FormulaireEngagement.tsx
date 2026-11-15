import { MinusCircleOutlined, PlusOutlined } from '@ant-design/icons'
import { useMutation } from '@tanstack/react-query'
import { App, Button, Col, Drawer, Form, Input, Row, Select, Space, Typography } from 'antd'
import { useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { useAfficherErreur } from '../../api/erreurs'
import { creerEngagement, modifierEngagement } from '../../api/genere/budget'
import type { EngagementCreation, EngagementSortie } from '../../api/genere/budget.schemas'
import { useOptions } from '../parametrage/PageReferentiel'

export const ORIGINES = ['CONTRAT', 'DECISION_AUTORISEE', 'HORS_MARCHE']
const NATURES = [
  'MISSION',
  'PETIT_ACHAT',
  'EAU_ELEC_TELECOM',
  'FONCTIONNEMENT',
  'PRESTATION_PONCTUELLE',
  'AUTRE',
]

const nettoyer = (v: Record<string, unknown>) =>
  Object.fromEntries(Object.entries(v).map(([k, x]) => [k, x === '' ? null : x]))

/** Demande d'engagement ou correction (brouillon, retour pour correction) : T-140, T-147. */
export function FormulaireEngagement({
  engagement,
  fermer,
  enregistre,
}: {
  engagement?: EngagementSortie
  fermer: () => void
  enregistre: (e: EngagementSortie) => void
}) {
  const { t } = useTranslation('engagements')
  const { t: tCommun } = useTranslation()
  const { message } = App.useApp()
  const afficherErreur = useAfficherErreur()
  const [formulaire] = Form.useForm<EngagementCreation>()
  const [cle] = useState(() => crypto.randomUUID())
  const origine = Form.useWatch('origine', formulaire) ?? engagement?.origine
  const options = {
    etablissements: useOptions('etablissements'),
    contrats: useOptions('contrats?statut=VALIDE'),
    fournisseurs: useOptions('fournisseurs'),
    centres: useOptions('centres-responsabilite'),
    types: useOptions('types-depenses'),
    lignes: useOptions('lignes-budgetaires'),
  }
  const choix = (valeurs: string[]) => valeurs.map((v) => ({ value: v, label: t(`valeurs.${v}`) }))
  const requis = [{ required: true, message: tCommun('connexion.obligatoire') }]
  const liste = (o: { value: string; label: string }[]) => (
    <Select allowClear showSearch optionFilterProp="label" options={o} />
  )

  const envoi = useMutation({
    mutationFn: (v: EngagementCreation) => {
      const corps = nettoyer(
        v as unknown as Record<string, unknown>,
      ) as unknown as EngagementCreation
      return engagement
        ? modifierEngagement(engagement.id, corps, {
            headers: { 'If-Match': `"${engagement.version}"` },
          })
        : creerEngagement(corps, { headers: { 'Idempotency-Key': cle } })
    },
    onSuccess: (e) => {
      void message.success(t('enregistre'))
      enregistre(e)
    },
    onError: (erreur) => afficherErreur(erreur, formulaire),
  })

  // [nom, contrôle, obligatoire] ; false masque un champ selon l'origine.
  type Champ = [string, ReactNode, boolean?]
  const champs: (Champ | false)[] = [
    !engagement && ['etablissementId', liste(options.etablissements), true],
    !engagement && ['origine', <Select key="origine" options={choix(ORIGINES)} />, true],
    !engagement && origine === 'CONTRAT' && ['contratId', liste(options.contrats), true],
    ['dateEngagement', <Input key="date" type="date" />, true],
    ['objet', <Input key="objet" maxLength={500} />, true],
    ['montant', <Input key="montant" inputMode="decimal" />, true],
    ['centreId', liste(options.centres), true],
    ['fournisseurId', liste(options.fournisseurs), origine === 'CONTRAT'],
    origine === 'HORS_MARCHE' && ['typeDepenseId', liste(options.types), true],
    origine === 'HORS_MARCHE' && [
      'natureHorsMarche',
      <Select key="nature" options={choix(NATURES)} />,
      true,
    ],
    origine === 'HORS_MARCHE' && [
      'justification',
      <Input.TextArea key="justif" maxLength={1000} />,
    ],
    origine === 'DECISION_AUTORISEE' && [
      'referenceDecision',
      <Input key="decision" maxLength={100} />,
    ],
  ]

  return (
    <Drawer
      open
      size="large"
      title={engagement ? `${engagement.numero} — ${t('modifier')}` : t('creer')}
      onClose={fermer}
      extra={
        <Button type="primary" loading={envoi.isPending} onClick={() => formulaire.submit()}>
          {tCommun('actions.enregistrer')}
        </Button>
      }
    >
      <Form
        form={formulaire}
        layout="vertical"
        initialValues={engagement ?? { origine: 'CONTRAT', imputations: [{}] }}
        onFinish={(v) => envoi.mutate(v)}
      >
        <Row gutter={16}>
          {champs
            .filter((c): c is Champ => Boolean(c))
            .map(([nom, controle, obligatoire]) => (
              <Col xs={24} md={12} key={nom}>
                <Form.Item name={nom} label={t(`champs.${nom}`)} rules={obligatoire ? requis : []}>
                  {controle}
                </Form.Item>
              </Col>
            ))}
        </Row>
        <Typography.Title level={4}>{t('champs.imputations')}</Typography.Title>
        <Typography.Paragraph type="secondary">{t('aideImputations')}</Typography.Paragraph>
        <Form.List name="imputations">
          {(lignes, { add, remove }) => (
            <>
              {lignes.map((c) => (
                <Space key={c.key} align="baseline" wrap>
                  <Form.Item name={[c.name, 'ligneId']} rules={requis}>
                    <Select
                      aria-label={t('champs.ligneId')}
                      style={{ minWidth: 260 }}
                      showSearch
                      optionFilterProp="label"
                      options={options.lignes}
                    />
                  </Form.Item>
                  <Form.Item name={[c.name, 'montant']} rules={requis}>
                    <Input aria-label={t('champs.montant')} inputMode="decimal" />
                  </Form.Item>
                  <Button
                    type="text"
                    aria-label={t('retirer')}
                    icon={<MinusCircleOutlined aria-hidden />}
                    onClick={() => remove(c.name)}
                  />
                </Space>
              ))}
              <Button type="dashed" icon={<PlusOutlined aria-hidden />} onClick={() => add()}>
                {t('ajouterImputation')}
              </Button>
            </>
          )}
        </Form.List>
      </Form>
    </Drawer>
  )
}
