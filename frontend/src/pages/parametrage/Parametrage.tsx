import { useMutation, useQueryClient } from '@tanstack/react-query'
import {
  App,
  Button,
  Card,
  Checkbox,
  Drawer,
  Flex,
  Form,
  Input,
  List,
  Select,
  Switch,
  Typography,
} from 'antd'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Navigate, useNavigate, useParams } from 'react-router'
import { useAfficherErreur } from '../../api/erreurs'
import {
  ajouterCoordonnee,
  getListerCoordonneesQueryKey,
  getLireParametresCalculQueryKey,
  modifierParametresCalcul,
  useListerCoordonnees,
  useLireParametresCalcul,
} from '../../api/genere/budget'
import type { CoordonneeCreation, ParametresCalculSchema } from '../../api/genere/budget.schemas'
import { useAProfil } from '../../auth/session'
import { PageReferentiel, useOptions, type Enregistrement } from './PageReferentiel'
import { Circuits } from './Circuits'
import { PARAMETRAGE, RESSOURCES } from './ressources'

/** Coordonnées bancaires d'un fournisseur : numéro chiffré, affiché masqué (T-083). */
function Coordonnees({ fournisseur, fermer }: { fournisseur: Enregistrement; fermer: () => void }) {
  const { t } = useTranslation('parametrage')
  const { t: tCommun } = useTranslation()
  const afficherErreur = useAfficherErreur()
  const client = useQueryClient()
  const [formulaire] = Form.useForm<CoordonneeCreation>()
  const etablissements = useOptions('etablissements')
  const peutEcrire = useAProfil(['ADM'])
  const { data: coordonnees = [] } = useListerCoordonnees(fournisseur.id)
  const ajout = useMutation({
    mutationFn: (valeurs: CoordonneeCreation) => ajouterCoordonnee(fournisseur.id, valeurs),
    onSuccess: () => {
      formulaire.resetFields()
      void client.invalidateQueries({ queryKey: getListerCoordonneesQueryKey(fournisseur.id) })
    },
    onError: (erreur) => afficherErreur(erreur, formulaire),
  })

  return (
    <Drawer
      open
      title={`${t('coordonnees.titre')} — ${String(fournisseur.raisonSociale)}`}
      onClose={fermer}
    >
      <List
        dataSource={coordonnees}
        locale={{ emptyText: tCommun('tableau.aucun') }}
        renderItem={(c) => (
          <List.Item key={c.id}>
            <Typography.Text>
              {c.banque} — {c.numeroMasque}
              {c.parDefaut ? ` (${t('coordonnees.parDefaut')})` : ''}
            </Typography.Text>
          </List.Item>
        )}
      />
      {peutEcrire && (
        <Form
          form={formulaire}
          layout="vertical"
          onFinish={(valeurs) => ajout.mutate(valeurs)}
          initialValues={{ parDefaut: false }}
        >
          <Typography.Title level={4}>{t('coordonnees.ajouter')}</Typography.Title>
          <Form.Item
            name="etablissementId"
            label={t('champs.etablissementId')}
            rules={[{ required: true }]}
          >
            <Select options={etablissements} />
          </Form.Item>
          <Form.Item name="banque" label={t('coordonnees.banque')} rules={[{ required: true }]}>
            <Input maxLength={200} />
          </Form.Item>
          <Form.Item
            name="numeroCompte"
            label={t('coordonnees.numeroCompte')}
            extra={t('coordonnees.aide')}
            rules={[{ required: true }]}
          >
            <Input autoComplete="off" maxLength={64} />
          </Form.Item>
          <Form.Item name="parDefaut" valuePropName="checked">
            <Checkbox>{t('coordonnees.parDefaut')}</Checkbox>
          </Form.Item>
          <Button type="primary" htmlType="submit" loading={ajout.isPending}>
            {tCommun('actions.enregistrer')}
          </Button>
        </Form>
      )}
    </Drawer>
  )
}

/** Paramètres de calcul des indicateurs d'un établissement (section 6.1, ARC-S). */
export function ParametresCalcul({ etablissementId }: { etablissementId: string }) {
  const { t } = useTranslation('parametrage')
  const { t: tCommun } = useTranslation()
  const { message } = App.useApp()
  const afficherErreur = useAfficherErreur()
  const client = useQueryClient()
  const peutEcrire = useAProfil(['ADM'])
  const [formulaire] = Form.useForm<ParametresCalculSchema>()
  const { data } = useLireParametresCalcul(etablissementId)
  useEffect(() => {
    if (data) formulaire.setFieldsValue(data)
  }, [data, formulaire])
  const envoi = useMutation({
    mutationFn: (valeurs: ParametresCalculSchema) =>
      modifierParametresCalcul(etablissementId, valeurs),
    onSuccess: (enregistres) => {
      client.setQueryData(getLireParametresCalculQueryKey(etablissementId), enregistres)
      void message.success(t('parametresCalcul.enregistre'))
    },
    onError: (erreur) => afficherErreur(erreur, formulaire),
  })
  const choix = (valeurs: string[]) =>
    valeurs.map((v) => ({ value: v, label: t(`parametresCalcul.${v}`) }))

  return (
    <Card title={t('parametresCalcul.titre')}>
      <Form
        form={formulaire}
        layout="vertical"
        disabled={!peutEcrire}
        onFinish={(v) => envoi.mutate(v)}
      >
        <Form.Item
          name="disponiblePrevisionnelDeduitEnCours"
          label={t('parametresCalcul.disponiblePrevisionnelDeduitEnCours')}
          valuePropName="checked"
        >
          <Switch />
        </Form.Item>
        <Form.Item name="baseTauxExecution" label={t('parametresCalcul.baseTauxExecution')}>
          <Select options={choix(['BUDGET_REVISE', 'BUDGET_INITIAL'])} />
        </Form.Item>
        <Form.Item
          name="baseTauxConsommationMarche"
          label={t('parametresCalcul.baseTauxConsommationMarche')}
        >
          <Select options={choix(['ENGAGE', 'LIQUIDE'])} />
        </Form.Item>
        <Form.Item
          name="consommationDeduitAvanceRecuperee"
          label={t('parametresCalcul.consommationDeduitAvanceRecuperee')}
          valuePropName="checked"
        >
          <Switch />
        </Form.Item>
        {peutEcrire && (
          <Button type="primary" htmlType="submit" loading={envoi.isPending}>
            {tCommun('actions.enregistrer')}
          </Button>
        )}
      </Form>
    </Card>
  )
}

/** Écran de paramétrage : un référentiel à la fois, choisi dans la liste (/parametrage/:ressource). */
export function Parametrage() {
  const { ressource = '' } = useParams()
  const { t } = useTranslation('parametrage')
  const naviguer = useNavigate()
  const [fournisseur, setFournisseur] = useState<Enregistrement | null>(null)
  if (!PARAMETRAGE.includes(ressource))
    return <Navigate to={`/parametrage/${PARAMETRAGE[0]}`} replace />

  return (
    <Flex vertical gap="middle">
      <Typography.Title level={1}>{t('titre')}</Typography.Title>
      <Select
        aria-label={t('titre')}
        style={{ maxWidth: 360 }}
        value={ressource}
        onChange={(r) => naviguer(`/parametrage/${r}`)}
        options={PARAMETRAGE.map((r) => ({ value: r, label: t(`ressources.${r}`) }))}
      />
      {ressource === 'circuits-validation' ? (
        <Circuits />
      ) : (
        <PageReferentiel
          key={ressource}
          definition={RESSOURCES[ressource]!}
          actionsLigne={
            ressource === 'fournisseurs'
              ? (f) => (
                  <Button size="small" onClick={() => setFournisseur(f)}>
                    {t('actions.coordonnees')}
                  </Button>
                )
              : undefined
          }
        />
      )}
      {fournisseur && <Coordonnees fournisseur={fournisseur} fermer={() => setFournisseur(null)} />}
    </Flex>
  )
}
