import { MinusCircleOutlined, PlusOutlined } from '@ant-design/icons'
import { useMutation } from '@tanstack/react-query'
import { App, Button, Col, Drawer, Form, Input, Row, Select, Space, Typography } from 'antd'
import { useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { useAfficherErreur } from '../../api/erreurs'
import { creerContrat, modifierContrat } from '../../api/genere/budget'
import type { ContratCreation, ContratSortie } from '../../api/genere/budget.schemas'
import { useOptions } from '../parametrage/PageReferentiel'

export const TYPES = ['MARCHE', 'CONVENTION', 'MAINTENANCE', 'PRESTATION', 'AUTRE']
const NATURES = ['FOURNITURES', 'TRAVAUX', 'SERVICES', 'PRESTATIONS_INTELLECTUELLES']
const PERIODICITES = [
  'PONCTUELLE',
  'A_LA_LIVRAISON',
  'MENSUELLE',
  'TRIMESTRIELLE',
  'SEMESTRIELLE',
  'ANNUELLE',
]

/** Champs vides envoyés à null : l'API distingue « effacé » de « non modifié ». */
const nettoyer = (v: Record<string, unknown>) =>
  Object.fromEntries(Object.entries(v).map(([k, x]) => [k, x === '' ? null : x]))

/** Création ou correction d'un contrat (brouillon ou retour pour correction), T-130 et T-131. */
export function FormulaireContrat({
  contrat,
  fermer,
  enregistre,
}: {
  contrat?: ContratSortie
  fermer: () => void
  enregistre: (c: ContratSortie) => void
}) {
  const { t } = useTranslation('contrats')
  const { t: tCommun } = useTranslation()
  const { message } = App.useApp()
  const afficherErreur = useAfficherErreur()
  const [formulaire] = Form.useForm<ContratCreation>()
  const [cle] = useState(() => crypto.randomUUID())
  const type = Form.useWatch('type', formulaire) ?? contrat?.type
  const options = {
    etablissements: useOptions('etablissements'),
    fournisseurs: useOptions('fournisseurs'),
    centres: useOptions('centres-responsabilite'),
    sites: useOptions('sites'),
    sources: useOptions('sources-financement'),
    familles: useOptions('familles-achats'),
    lignes: useOptions('lignes-budgetaires'),
  }
  const choix = (valeurs: string[]) => valeurs.map((v) => ({ value: v, label: t(`valeurs.${v}`) }))
  const requis = [{ required: true, message: tCommun('connexion.obligatoire') }]

  const envoi = useMutation({
    mutationFn: (v: ContratCreation) => {
      const corps = nettoyer(v as unknown as Record<string, unknown>) as unknown as ContratCreation
      return contrat
        ? modifierContrat(contrat.id, corps, { headers: { 'If-Match': `"${contrat.version}"` } })
        : creerContrat(corps, { headers: { 'Idempotency-Key': cle } })
    },
    onSuccess: (c) => {
      void message.success(t('enregistre'))
      enregistre(c)
    },
    onError: (erreur) => afficherErreur(erreur, formulaire),
  })

  const champ = (nom: string, controle: ReactNode, obligatoire = false) => (
    <Col xs={24} md={12} key={nom}>
      <Form.Item name={nom} label={t(`champs.${nom}`)} rules={obligatoire ? requis : []}>
        {controle}
      </Form.Item>
    </Col>
  )
  const date = <Input type="date" />
  const montant = <Input inputMode="decimal" />
  const liste = (o: { value: string; label: string }[]) => (
    <Select allowClear showSearch optionFilterProp="label" options={o} />
  )

  // Champs par section : [nom, contrôle, obligatoire] ; false masque un champ.
  type Champ = [string, ReactNode, boolean?]
  const sections: { titre: string; aide?: string; champs: (Champ | false)[] }[] = [
    {
      titre: 'identification',
      champs: [
        !contrat && ['etablissementId', liste(options.etablissements), true],
        !contrat && ['type', <Select key="type" options={choix(TYPES)} />, true],
        ['numero', <Input key="numero" maxLength={50} />, true],
        ['intitule', <Input key="intitule" maxLength={300} />, true],
        type === 'MARCHE' && [
          'nature',
          <Select key="nature" allowClear options={choix(NATURES)} />,
        ],
        type === 'MARCHE' && ['numeroLot', <Input key="lot" maxLength={30} />],
        ['fournisseurId', liste(options.fournisseurs), true],
        ['referenceDossier', <Input key="dossier" maxLength={100} />],
        ['objet', <Input.TextArea key="objet" />],
        ['perimetre', <Input.TextArea key="perimetre" />],
      ],
    },
    {
      titre: 'dates',
      aide: 'aideDates',
      champs: [
        ['dateSignature', date],
        ['dateNotification', date],
        ['dateDemarrage', date],
        ['dateEcheance', date],
        ['dureeMois', <Input key="duree" type="number" min={1} />],
      ],
    },
    {
      titre: 'montants',
      champs: [
        ['montantInitialHt', montant, true],
        ['tauxTaxe', montant, true],
        ['devise', <Input key="devise" maxLength={3} />, true],
        ['periodicite', <Select key="periodicite" allowClear options={choix(PERIODICITES)} />],
        ['modaliteFacturation', <Input key="modalite" maxLength={500} />],
      ],
    },
    {
      titre: 'rattachements',
      champs: [
        ['centreId', liste(options.centres), true],
        ['sourceId', liste(options.sources), true],
        ['siteId', liste(options.sites)],
        ['familleAchatId', liste(options.familles)],
        ['responsableCode', <Input key="responsable" maxLength={20} />],
      ],
    },
    {
      titre: 'avanceRetenue',
      champs: [
        ['tauxAvance', montant],
        ['modeRecuperationAvance', <Input key="recuperation" maxLength={300} />],
        ['tauxRetenueGarantie', montant],
        ['conditionLiberationRetenue', <Input key="condition" maxLength={300} />],
        ['dateLiberationRetenue', date],
      ],
    },
  ]

  return (
    <Drawer
      open
      size="large"
      title={contrat ? `${contrat.numero} — ${t('modifier')}` : t('creer')}
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
        initialValues={
          contrat ?? { type: 'MARCHE', devise: 'XOF', tauxTaxe: '0', imputations: [{}] }
        }
        onFinish={(v) => envoi.mutate(v)}
      >
        {sections.map(({ titre, aide, champs }) => (
          <div key={titre}>
            <Typography.Title level={4}>{t(`sections.${titre}`)}</Typography.Title>
            {aide && <Typography.Paragraph type="secondary">{t(aide)}</Typography.Paragraph>}
            <Row gutter={16}>
              {champs
                .filter((c): c is Champ => Boolean(c))
                .map(([nom, controle, obligatoire]) => champ(nom, controle, obligatoire))}
            </Row>
          </div>
        ))}
        <Typography.Title level={4}>{t('sections.ventilation')}</Typography.Title>
        <Typography.Paragraph type="secondary">{t('aideVentilation')}</Typography.Paragraph>
        <Form.List name="imputations">
          {(champs, { add, remove }) => (
            <>
              {champs.map((c) => (
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
