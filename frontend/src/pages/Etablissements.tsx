import { PlusOutlined } from '@ant-design/icons'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { App, Button, Flex, Form, Input, Modal, Segmented, Space, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table/interface'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useSearchParams } from 'react-router'
import { useAfficherErreur } from '../api/erreurs'
import {
  creerEtablissement,
  getListerEtablissementsQueryKey,
  modifierEtablissement,
  useListerEtablissements,
} from '../api/genere/budget'
import type { EtablissementCreation, EtablissementSortie } from '../api/genere/budget.schemas'
import { useSession } from '../auth/session'
import { BadgeStatut } from '../composants/BadgeStatut'
import { TableauServeur, type EtatTableau } from '../composants/TableauServeur'

const STATUTS = ['tous', 'actifs', 'inactifs'] as const

function Statut({ actif }: { actif: boolean }) {
  const { t } = useTranslation()
  return actif ? (
    <BadgeStatut ton="succes" libelle={t('statut.actif')} />
  ) : (
    <BadgeStatut ton="neutre" libelle={t('statut.inactif')} />
  )
}

function FormulaireCreation({ ouvert, fermer }: { ouvert: boolean; fermer: () => void }) {
  const { t } = useTranslation('etablissements')
  const { t: tCommun } = useTranslation()
  const { message } = App.useApp()
  const afficherErreur = useAfficherErreur()
  const client = useQueryClient()
  const [formulaire] = Form.useForm<EtablissementCreation>()
  // Une clé par ouverture du formulaire : un double envoi ne crée qu'un établissement (§11.3).
  const [cle, setCle] = useState(() => crypto.randomUUID())
  const creation = useMutation({
    mutationFn: (donnees: EtablissementCreation) =>
      creerEtablissement(donnees, { headers: { 'Idempotency-Key': cle } }),
    onSuccess: (cree) => {
      void client.invalidateQueries({ queryKey: getListerEtablissementsQueryKey() })
      void message.success(t('notifications.cree', { code: cree.code }))
      formulaire.resetFields()
      setCle(crypto.randomUUID())
      fermer()
    },
    onError: (erreur) => afficherErreur(erreur, formulaire),
  })
  return (
    <Modal
      open={ouvert}
      title={t('formulaire.titreCreation')}
      okText={tCommun('actions.enregistrer')}
      cancelText={tCommun('actions.annuler')}
      confirmLoading={creation.isPending}
      onOk={() => formulaire.submit()}
      onCancel={fermer}
    >
      <Form form={formulaire} layout="vertical" onFinish={(v) => creation.mutate(v)}>
        <Form.Item
          name="code"
          label={t('formulaire.code')}
          extra={t('formulaire.aideCode')}
          rules={[{ required: true, message: tCommun('connexion.obligatoire') }]}
        >
          <Input maxLength={20} />
        </Form.Item>
        <Form.Item
          name="nom"
          label={t('formulaire.nom')}
          rules={[{ required: true, message: tCommun('connexion.obligatoire') }]}
        >
          <Input maxLength={200} />
        </Form.Item>
      </Form>
    </Modal>
  )
}

export function Etablissements() {
  const { t } = useTranslation('etablissements')
  const { message } = App.useApp()
  const afficherErreur = useAfficherErreur()
  const client = useQueryClient()
  const { moi } = useSession()
  // État de la liste dans l'adresse : lien profond, retour arrière et partage (T-065).
  const [recherche, setRecherche] = useSearchParams()
  const [creationOuverte, setCreationOuverte] = useState(false)
  const etat: EtatTableau = {
    page: Number(recherche.get('page') ?? 1),
    taille: Number(recherche.get('taille') ?? 25),
    tri: recherche.get('tri') ?? undefined,
  }
  const statut = recherche.get('statut') ?? 'tous'
  const parametres = {
    page: etat.page,
    taille: etat.taille,
    tri: etat.tri,
    actif: statut === 'tous' ? undefined : statut === 'actifs',
  }
  const { data, isFetching } = useListerEtablissements(parametres)
  const administrateurGlobal =
    moi?.habilitations.some((h) => h.profil === 'ADM' && h.etablissementId === null) ?? false

  const changer = (suivant: Partial<EtatTableau> & { statut?: string }) => {
    const valeurs = { ...etat, statut, ...suivant }
    const nouvelle = new URLSearchParams()
    for (const [cle, valeur] of Object.entries(valeurs)) {
      if (valeur !== undefined && valeur !== '') nouvelle.set(cle, String(valeur))
    }
    setRecherche(nouvelle)
  }

  const desactivation = useMutation({
    mutationFn: (selection: EtablissementSortie[]) =>
      Promise.all(
        selection.map((e) =>
          modifierEtablissement(
            e.id,
            { actif: false },
            { headers: { 'If-Match': `"${e.version}"` } },
          ),
        ),
      ),
    onSuccess: (modifies) => {
      void message.success(t('notifications.desactives', { count: modifies.length }))
    },
    onError: (erreur) => afficherErreur(erreur),
    onSettled: () => void client.invalidateQueries({ queryKey: getListerEtablissementsQueryKey() }),
  })

  const colonnes: ColumnsType<EtablissementSortie> = [
    {
      title: t('colonnes.code'),
      dataIndex: 'code',
      sorter: true,
      render: (code: string, e) => <Link to={`/etablissements/${e.id}`}>{code}</Link>,
    },
    { title: t('colonnes.nom'), dataIndex: 'nom', sorter: true },
    {
      title: t('colonnes.statut'),
      dataIndex: 'actif',
      render: (actif: boolean) => <Statut actif={actif} />,
    },
  ]
  const donnees = data?.donnees ?? []

  return (
    <Flex vertical gap="middle">
      <Flex justify="space-between" align="center" wrap gap="small">
        <Typography.Title level={1} style={{ margin: 0 }}>
          {t('titre')}
        </Typography.Title>
        {administrateurGlobal && (
          <Button
            type="primary"
            icon={<PlusOutlined aria-hidden />}
            onClick={() => setCreationOuverte(true)}
          >
            {t('actions.creer')}
          </Button>
        )}
      </Flex>
      <Segmented
        aria-label={t('filtres.statut')}
        value={statut}
        onChange={(valeur) => changer({ statut: String(valeur), page: 1 })}
        options={STATUTS.map((s) => ({ value: s, label: t(`filtres.${s}`) }))}
      />
      <TableauServeur<EtablissementSortie>
        nom="etablissements"
        colonnes={colonnes}
        donnees={donnees}
        total={data?.pagination.total ?? 0}
        chargement={isFetching}
        etat={etat}
        surChangement={changer}
        cleLigne={(e) => e.id}
        carte={(e) => (
          <Space direction="vertical">
            <Link to={`/etablissements/${e.id}`}>{e.code}</Link>
            <Typography.Text>{e.nom}</Typography.Text>
            <Statut actif={e.actif} />
          </Space>
        )}
        actionsGroupees={
          administrateurGlobal
            ? (selection, vider) => (
                <Button
                  loading={desactivation.isPending}
                  onClick={() =>
                    desactivation.mutate(
                      donnees.filter((e) => selection.includes(e.id) && e.actif),
                      { onSuccess: vider },
                    )
                  }
                >
                  {t('actions.desactiver')}
                </Button>
              )
            : undefined
        }
      />
      <FormulaireCreation ouvert={creationOuverte} fermer={() => setCreationOuverte(false)} />
    </Flex>
  )
}
