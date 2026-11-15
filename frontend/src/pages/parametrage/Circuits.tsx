import { MinusCircleOutlined, PlusOutlined } from '@ant-design/icons'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import {
  App,
  Button,
  Checkbox,
  Flex,
  Form,
  Input,
  Modal,
  Select,
  Space,
  Switch,
  Typography,
} from 'antd'
import type { ColumnsType } from 'antd/es/table/interface'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useAfficherErreur } from '../../api/erreurs'
import {
  creerCircuitValidation,
  getListerCircuitsValidationQueryKey,
  modifierCircuitValidation,
  useListerCircuitsValidation,
} from '../../api/genere/budget'
import type { CircuitCreation, CircuitSortie } from '../../api/genere/budget.schemas'
import { useAProfil } from '../../auth/session'
import { BadgeStatut } from '../../composants/BadgeStatut'
import { Montant } from '../../composants/Montant'
import { TableauServeur, type EtatTableau } from '../../composants/TableauServeur'
import { useOptions } from './PageReferentiel'
import { TYPES_OBJETS } from './ressources'

// Profils qui valident un objet dans la matrice (le contrôle financier pour les engagements) ;
// le serveur refuse un profil sans droit sur le type d'objet choisi.
const PROFILS_VALIDEURS = ['AF', 'VAL', 'ORD']

function Formulaire({ circuit, fermer }: { circuit?: CircuitSortie; fermer: () => void }) {
  const { t } = useTranslation('workflow')
  const { t: tCommun } = useTranslation()
  const { t: tProfils } = useTranslation('habilitations')
  const { message } = App.useApp()
  const afficherErreur = useAfficherErreur()
  const client = useQueryClient()
  const [formulaire] = Form.useForm<CircuitCreation>()
  const [cle] = useState(() => crypto.randomUUID())
  const etablissements = useOptions('etablissements')
  const centres = useOptions('centres-responsabilite')
  const envoi = useMutation({
    mutationFn: (v: CircuitCreation) => {
      const corps = { ...v, etapes: v.etapes.map((e, i) => ({ ...e, ordre: i + 1 })) }
      return circuit
        ? modifierCircuitValidation(
            circuit.id,
            {
              libelle: corps.libelle,
              seuilMin: corps.seuilMin,
              seuilMax: corps.seuilMax || null,
              separationTaches: corps.separationTaches,
              etapes: corps.etapes,
            },
            { headers: { 'If-Match': `"${circuit.version}"` } },
          )
        : creerCircuitValidation(
            { ...corps, seuilMax: corps.seuilMax || null },
            { headers: { 'Idempotency-Key': cle } },
          )
    },
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: getListerCircuitsValidationQueryKey() })
      void message.success(t('circuits.enregistre'))
      fermer()
    },
    onError: (erreur) => afficherErreur(erreur, formulaire),
  })
  const requis = [{ required: true, message: tCommun('connexion.obligatoire') }]

  return (
    <Modal
      open
      width={720}
      title={circuit ? t('circuits.modifier') : t('circuits.creer')}
      okText={tCommun('actions.enregistrer')}
      cancelText={tCommun('actions.annuler')}
      confirmLoading={envoi.isPending}
      onOk={() => formulaire.submit()}
      onCancel={fermer}
    >
      <Form
        form={formulaire}
        layout="vertical"
        initialValues={
          circuit ?? {
            typeObjet: 'RevisionBudgetaire',
            seuilMin: '0.00',
            separationTaches: true,
            etapes: [
              { libelle: '', profil: 'VAL', obligatoire: true },
              { libelle: '', profil: 'ORD', obligatoire: true },
            ],
          }
        }
        onFinish={(v) => envoi.mutate(v)}
      >
        {!circuit && (
          <>
            <Form.Item name="etablissementId" label={t('circuits.etablissementId')} rules={requis}>
              <Select options={etablissements} />
            </Form.Item>
            <Form.Item name="typeObjet" label={t('circuits.typeObjet')} rules={requis}>
              <Select
                options={TYPES_OBJETS.map((v) => ({
                  value: v,
                  label: t(`circuits.types.${v}`),
                }))}
              />
            </Form.Item>
            <Form.Item name="centreId" label={t('circuits.centreId')}>
              <Select allowClear showSearch optionFilterProp="label" options={centres} />
            </Form.Item>
          </>
        )}
        <Form.Item name="libelle" label={t('circuits.libelle')} rules={requis}>
          <Input maxLength={200} />
        </Form.Item>
        <Flex gap="middle" wrap>
          <Form.Item name="seuilMin" label={t('circuits.seuilMin')} rules={requis}>
            <Input inputMode="decimal" />
          </Form.Item>
          <Form.Item name="seuilMax" label={t('circuits.seuilMax')}>
            <Input inputMode="decimal" />
          </Form.Item>
          <Form.Item
            name="separationTaches"
            label={t('circuits.separationTaches')}
            valuePropName="checked"
          >
            <Switch />
          </Form.Item>
        </Flex>
        <Typography.Text strong>{t('circuits.etapes')}</Typography.Text>
        <Typography.Paragraph type="secondary">{t('circuits.aide')}</Typography.Paragraph>
        <Form.List name="etapes">
          {(champs, { add, remove }) => (
            <>
              {champs.map((champ) => (
                <Space key={champ.key} align="baseline" wrap>
                  <Form.Item name={[champ.name, 'libelle']} rules={requis}>
                    <Input aria-label={t('circuits.libelle')} placeholder={t('circuits.libelle')} />
                  </Form.Item>
                  <Form.Item name={[champ.name, 'profil']} rules={requis}>
                    <Select
                      aria-label={t('circuits.profil')}
                      style={{ minWidth: 200 }}
                      options={PROFILS_VALIDEURS.map((p) => ({
                        value: p,
                        label: tProfils(`profils.${p}`),
                      }))}
                    />
                  </Form.Item>
                  <Form.Item name={[champ.name, 'obligatoire']} valuePropName="checked">
                    <Checkbox>{t('circuits.obligatoire')}</Checkbox>
                  </Form.Item>
                  <Button
                    type="text"
                    aria-label={t('circuits.retirer')}
                    icon={<MinusCircleOutlined aria-hidden />}
                    onClick={() => remove(champ.name)}
                  />
                </Space>
              ))}
              <Button
                type="dashed"
                icon={<PlusOutlined aria-hidden />}
                onClick={() => add({ libelle: '', profil: 'VAL', obligatoire: true })}
              >
                {t('circuits.ajouterEtape')}
              </Button>
            </>
          )}
        </Form.List>
      </Form>
    </Modal>
  )
}

/** Circuits de validation par établissement, objet, service et tranche de montant (T-112). */
export function Circuits() {
  const { t } = useTranslation('workflow')
  const { t: tProfils } = useTranslation('habilitations')
  const { t: tCommun } = useTranslation()
  const peutEcrire = useAProfil(['ADM'])
  const [etat, setEtat] = useState<EtatTableau>({ page: 1, taille: 25 })
  const [formulaire, setFormulaire] = useState<{ circuit?: CircuitSortie } | null>(null)
  const { data, isFetching } = useListerCircuitsValidation({
    page: etat.page,
    taille: etat.taille,
  })
  const etapes = (c: CircuitSortie) =>
    c.etapes.map((e) => `${e.ordre}. ${e.libelle} (${tProfils(`profils.${e.profil}`)})`).join(' ; ')
  const seuils = (c: CircuitSortie) => (
    <>
      <Montant valeur={c.seuilMin} />
      {c.seuilMax && (
        <>
          {' – '}
          <Montant valeur={c.seuilMax} />
        </>
      )}
    </>
  )
  const statut = (c: CircuitSortie) =>
    c.actif ? (
      <BadgeStatut ton="succes" libelle={tCommun('statut.actif')} />
    ) : (
      <BadgeStatut ton="neutre" libelle={tCommun('statut.inactif')} />
    )
  const modifier = (c: CircuitSortie) =>
    peutEcrire && (
      <Button size="small" onClick={() => setFormulaire({ circuit: c })}>
        {t('circuits.modifier')}
      </Button>
    )
  const colonnes: ColumnsType<CircuitSortie> = [
    { title: t('circuits.libelle'), dataIndex: 'libelle', sorter: true },
    {
      title: t('circuits.typeObjet'),
      dataIndex: 'typeObjet',
      render: (v: string) => t(`circuits.types.${v}`),
    },
    { title: t('circuits.seuilMin'), key: 'seuils', render: (_, c) => seuils(c) },
    {
      title: t('circuits.separationTaches'),
      dataIndex: 'separationTaches',
      render: (v: boolean) => (v ? t('circuits.oui') : t('circuits.non')),
    },
    { title: t('circuits.etapes'), key: 'etapes', render: (_, c) => etapes(c) },
    { title: t('circuits.actif'), key: 'actif', render: (_, c) => statut(c) },
    { key: 'actions', render: (_, c) => modifier(c) },
  ]

  return (
    <Flex vertical gap="middle">
      <Typography.Paragraph>{t('circuits.intro')}</Typography.Paragraph>
      {peutEcrire && (
        <Button
          type="primary"
          style={{ alignSelf: 'flex-start' }}
          onClick={() => setFormulaire({})}
        >
          {t('circuits.creer')}
        </Button>
      )}
      <TableauServeur<CircuitSortie>
        colonnes={colonnes}
        donnees={data?.donnees ?? []}
        total={data?.pagination.total ?? 0}
        chargement={isFetching}
        etat={etat}
        surChangement={setEtat}
        cleLigne={(c) => c.id}
        carte={(c) => (
          <Space direction="vertical">
            <Typography.Text strong>{c.libelle}</Typography.Text>
            <Typography.Text>{seuils(c)}</Typography.Text>
            <Typography.Text>{etapes(c)}</Typography.Text>
            {statut(c)}
            {modifier(c)}
          </Space>
        )}
      />
      {formulaire && <Formulaire circuit={formulaire.circuit} fermer={() => setFormulaire(null)} />}
    </Flex>
  )
}
