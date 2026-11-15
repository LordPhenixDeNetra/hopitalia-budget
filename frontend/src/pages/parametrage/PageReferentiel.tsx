import { PlusOutlined } from '@ant-design/icons'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { App, Button, Flex, Form, Input, InputNumber, Modal, Select, Space, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table/interface'
import { useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'
import { appelerApi } from '../../api/client'
import { useAfficherErreur } from '../../api/erreurs'
import { useAProfil } from '../../auth/session'
import { BadgeStatut } from '../../composants/BadgeStatut'
import { Montant } from '../../composants/Montant'
import { TableauServeur, type EtatTableau } from '../../composants/TableauServeur'
import { formaterDate } from '../../format/format'
import type { Champ, DefinitionRessource } from './ressources'

export type Enregistrement = Record<string, unknown> & { id: string; version?: number }

interface PageApi {
  donnees: Enregistrement[]
  pagination: { total: number }
}

const libelle = (e: Enregistrement) =>
  [
    e.code ?? e.numero,
    e.libelle ?? e.raisonSociale ?? e.intitule ?? e.reference ?? e.nom ?? e.objet,
  ]
    .filter(Boolean)
    .join(' — ')

/** Options d'un champ référence : liste paginée ou tableau (nomenclature). */
export function useOptions(chemin?: string) {
  const separateur = chemin?.includes('?') ? '&' : '?'
  const { data } = useQuery({
    queryKey: ['options', chemin],
    enabled: Boolean(chemin),
    queryFn: () =>
      appelerApi<PageApi | Enregistrement[]>(
        `/api/v1/${chemin}${chemin?.startsWith('nomenclature') ? '' : `${separateur}taille=100`}`,
      ),
  })
  const elements = Array.isArray(data) ? data : (data?.donnees ?? [])
  return elements.map((e) => ({ value: e.id, label: libelle(e) }))
}

function Reference({ chemin, valeur }: { chemin: string; valeur: unknown }) {
  const options = useOptions(chemin)
  return <>{options.find((o) => o.value === valeur)?.label ?? ''}</>
}

function useRendu() {
  const { t, i18n } = useTranslation('parametrage')
  const { t: tCommun } = useTranslation()
  return (champ: Champ | undefined, nom: string, valeur: unknown): ReactNode => {
    if (nom === 'actif') {
      return valeur ? (
        <BadgeStatut ton="succes" libelle={tCommun('statut.actif')} />
      ) : (
        <BadgeStatut ton="neutre" libelle={tCommun('statut.inactif')} />
      )
    }
    if (valeur === null || valeur === undefined || valeur === '') return null
    if (champ?.type === 'montant') return <Montant valeur={String(valeur)} />
    if (champ?.type === 'date' || nom.startsWith('date')) {
      return formaterDate(String(valeur), i18n.language)
    }
    if (champ?.type === 'reference' && champ.reference) {
      return <Reference chemin={champ.reference} valeur={valeur} />
    }
    if (Array.isArray(valeur)) return valeur.map((v) => t(`valeurs.${String(v)}`)).join(', ')
    if (champ?.type === 'choix' || nom === 'statut') return t(`valeurs.${String(valeur)}`)
    return String(valeur)
  }
}

/** Form.Item injecte id, value et onChange : ils sont transmis au contrôle réel. */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function ChampFormulaire({ champ, ...controle }: { champ: Champ } & Record<string, any>) {
  const { t } = useTranslation('parametrage')
  const options = useOptions(champ.type === 'reference' ? champ.reference : undefined)
  switch (champ.type) {
    case 'choixMultiple':
      return (
        <Select
          {...controle}
          mode="multiple"
          options={(champ.valeurs ?? []).map((v) => ({ value: v, label: t(`valeurs.${v}`) }))}
        />
      )
    case 'choix':
      return (
        <Select
          {...controle}
          options={(champ.valeurs ?? []).map((v) => ({ value: v, label: t(`valeurs.${v}`) }))}
        />
      )
    case 'reference':
      return (
        <Select {...controle} showSearch optionFilterProp="label" allowClear options={options} />
      )
    case 'entier':
      return <InputNumber {...controle} min={1} style={{ width: '100%' }} />
    case 'date':
      return <Input {...controle} type="date" />
    case 'montant':
      return <Input {...controle} inputMode="decimal" className="montant" />
    default:
      return <Input {...controle} />
  }
}

/** Formulaire de création ou de modification d'un élément d'une ressource. */
export function FormulaireRessource({
  definition,
  element,
  fixes = {},
  ouvert,
  fermer,
}: {
  definition: DefinitionRessource
  element?: Enregistrement
  fixes?: Record<string, string>
  ouvert: boolean
  fermer: () => void
}) {
  const { t } = useTranslation('parametrage')
  const { t: tCommun } = useTranslation()
  const { message } = App.useApp()
  const afficherErreur = useAfficherErreur()
  const client = useQueryClient()
  const [formulaire] = Form.useForm()
  // Une clé par ouverture : un double envoi ne crée qu'un élément (section 11.3).
  const [cle, setCle] = useState(() => crypto.randomUUID())
  const champs = definition.champs.filter(
    (c) => !(c.nom in fixes) && !(element && c.creationSeulement),
  )

  const envoi = useMutation({
    mutationFn: (valeurs: Record<string, unknown>) => {
      const corps = Object.fromEntries(
        Object.entries({ ...valeurs, ...fixes }).map(([k, v]) => [k, v === '' ? null : v]),
      )
      return element
        ? appelerApi(`/api/v1/${definition.chemin}/${element.id}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json', 'If-Match': `"${element.version}"` },
            body: JSON.stringify(corps),
          })
        : appelerApi(`/api/v1/${definition.chemin}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Idempotency-Key': cle },
            body: JSON.stringify(corps),
          })
    },
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ['ressource', definition.chemin] })
      void client.invalidateQueries({ queryKey: ['options'] })
      void message.success(t(element ? 'notifications.modifie' : 'notifications.cree'))
      formulaire.resetFields()
      setCle(crypto.randomUUID())
      fermer()
    },
    onError: (erreur) => afficherErreur(erreur, formulaire),
  })

  return (
    <Modal
      open={ouvert}
      title={t(`ressources.${definition.chemin}`)}
      okText={tCommun('actions.enregistrer')}
      cancelText={tCommun('actions.annuler')}
      confirmLoading={envoi.isPending}
      onOk={() => formulaire.submit()}
      onCancel={fermer}
      destroyOnHidden
    >
      <Form
        form={formulaire}
        layout="vertical"
        initialValues={element}
        onFinish={(valeurs) => envoi.mutate(valeurs)}
      >
        {champs.map((champ) => (
          <Form.Item
            key={champ.nom}
            name={champ.nom}
            label={t(`champs.${champ.nom}`)}
            extra={champ.type === 'montant' ? t('aideMontant') : undefined}
            rules={
              champ.requis ? [{ required: true, message: tCommun('connexion.obligatoire') }] : []
            }
          >
            <ChampFormulaire champ={champ} />
          </Form.Item>
        ))}
      </Form>
    </Modal>
  )
}

/** Liste paginée et triée côté serveur d'une ressource, avec création et modification. */
export function PageReferentiel({
  definition,
  fixes = {},
  titre = true,
  actionsLigne,
}: {
  definition: DefinitionRessource
  /** Filtres imposés (ex. budgetId) : appliqués à la liste et posés en création. */
  fixes?: Record<string, string>
  titre?: boolean
  actionsLigne?: (element: Enregistrement) => ReactNode
}) {
  const { t } = useTranslation('parametrage')
  const { message } = App.useApp()
  const afficherErreur = useAfficherErreur()
  const client = useQueryClient()
  const rendu = useRendu()
  const [etat, setEtat] = useState<EtatTableau>({ page: 1, taille: 25 })
  const [formulaire, setFormulaire] = useState<{ element?: Enregistrement } | null>(null)
  const peutEcrire = useAProfil(definition.ecriture)

  const parametres = new URLSearchParams({
    page: String(etat.page),
    taille: String(etat.taille),
    ...fixes,
    ...(etat.tri ? { tri: etat.tri } : {}),
  })
  const { data, isFetching } = useQuery({
    queryKey: ['ressource', definition.chemin, parametres.toString()],
    queryFn: () => appelerApi<PageApi>(`/api/v1/${definition.chemin}?${parametres}`),
  })

  const activation = useMutation({
    mutationFn: (e: Enregistrement) =>
      appelerApi(`/api/v1/${definition.chemin}/${e.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', 'If-Match': `"${e.version}"` },
        body: JSON.stringify({ actif: !e.actif }),
      }),
    onSuccess: () => void message.success(t('notifications.modifie')),
    onError: (erreur) => afficherErreur(erreur),
    onSettled: () => void client.invalidateQueries({ queryKey: ['ressource', definition.chemin] }),
  })

  const champ = (nom: string) => definition.champs.find((c) => c.nom === nom)
  const colonnes: ColumnsType<Enregistrement> = definition.colonnes.map((nom, rang) => ({
    title: t(`champs.${nom}`),
    dataIndex: nom,
    sorter: definition.tris.includes(nom),
    align: champ(nom)?.type === 'montant' ? 'right' : undefined,
    render: (valeur: unknown, e: Enregistrement) =>
      rang === 0 && definition.fiche ? (
        <Link to={definition.fiche(e.id)}>{String(valeur)}</Link>
      ) : (
        rendu(champ(nom), nom, valeur)
      ),
  }))
  const actions = (e: Enregistrement) => (
    <Space wrap>
      <Button size="small" onClick={() => setFormulaire({ element: e })}>
        {t('actions.modifier')}
      </Button>
      {definition.desactivable && (
        <Button size="small" onClick={() => activation.mutate(e)}>
          {e.actif ? t('actions.desactiver') : t('actions.activer')}
        </Button>
      )}
      {actionsLigne?.(e)}
    </Space>
  )
  if (peutEcrire || actionsLigne) {
    colonnes.push({ title: t('champs.actions'), key: 'actions', render: (_, e) => actions(e) })
  }

  return (
    <Flex vertical gap="middle">
      <Flex justify="space-between" align="center" wrap gap="small">
        {titre && (
          <Typography.Title level={2} style={{ margin: 0 }}>
            {t(`ressources.${definition.chemin}`)}
          </Typography.Title>
        )}
        {peutEcrire && (
          <Button
            type="primary"
            icon={<PlusOutlined aria-hidden />}
            onClick={() => setFormulaire({})}
          >
            {t('actions.creer')}
          </Button>
        )}
      </Flex>
      <TableauServeur<Enregistrement>
        colonnes={colonnes}
        donnees={data?.donnees ?? []}
        total={data?.pagination.total ?? 0}
        chargement={isFetching}
        etat={etat}
        surChangement={setEtat}
        cleLigne={(e) => e.id}
        carte={(e) => (
          <Space direction="vertical">
            {definition.colonnes.map((nom) => (
              <Typography.Text key={nom}>
                {t(`champs.${nom}`)} : {rendu(champ(nom), nom, e[nom])}
              </Typography.Text>
            ))}
            {(peutEcrire || actionsLigne) && actions(e)}
          </Space>
        )}
      />
      {formulaire && (
        <FormulaireRessource
          definition={definition}
          element={formulaire.element}
          fixes={fixes}
          ouvert
          fermer={() => setFormulaire(null)}
        />
      )}
    </Flex>
  )
}
