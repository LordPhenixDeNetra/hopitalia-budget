import { useMutation, useQueryClient } from '@tanstack/react-query'
import { App, Button, Card, Descriptions, Flex, Form, Input, Result, Spin, Typography } from 'antd'
import { useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router'
import { ErreurApi } from '../api/client'
import { useAfficherErreur } from '../api/erreurs'
import {
  getListerEtablissementsQueryKey,
  getObtenirEtablissementQueryKey,
  modifierEtablissement,
  useObtenirEtablissement,
} from '../api/genere/budget'
import type { EtablissementModification } from '../api/genere/budget.schemas'
import { BadgeStatut } from '../composants/BadgeStatut'
import { ParametresCalcul } from './parametrage/Parametrage'

/** Fiche accessible par lien profond : /etablissements/:id (T-065). */
export function FicheEtablissement() {
  const { id = '' } = useParams()
  const { t } = useTranslation('etablissements')
  const { t: tCommun } = useTranslation()
  const { message } = App.useApp()
  const afficherErreur = useAfficherErreur()
  const client = useQueryClient()
  const [formulaire] = Form.useForm<EtablissementModification>()
  const { data: etablissement, error, isLoading } = useObtenirEtablissement(id)

  useEffect(() => {
    if (etablissement) formulaire.setFieldsValue({ nom: etablissement.nom })
  }, [etablissement, formulaire])

  const modification = useMutation({
    mutationFn: (donnees: EtablissementModification) =>
      modifierEtablissement(id, donnees, {
        headers: { 'If-Match': `"${etablissement?.version ?? 0}"` },
      }),
    onSuccess: (modifie) => {
      client.setQueryData(getObtenirEtablissementQueryKey(id), modifie)
      void client.invalidateQueries({ queryKey: getListerEtablissementsQueryKey() })
      void message.success(t('notifications.modifie', { code: modifie.code }))
    },
    onError: (erreur) => {
      // 412 : la fiche a changé entre-temps ; on la recharge avant de laisser recommencer.
      if (erreur instanceof ErreurApi && erreur.probleme.status === 412) {
        void client.invalidateQueries({ queryKey: getObtenirEtablissementQueryKey(id) })
      }
      afficherErreur(erreur, formulaire)
    },
  })

  if (isLoading) return <Spin aria-label={tCommun('tableau.chargement')} />
  if (error || !etablissement) {
    return (
      <Result
        status="404"
        title={tCommun('introuvable.titre')}
        subTitle={tCommun('introuvable.detail')}
        extra={<Link to="/etablissements">{t('titre')}</Link>}
      />
    )
  }

  return (
    <Flex vertical gap="middle">
      <Typography.Title level={1}>
        {etablissement.code} — {etablissement.nom}
      </Typography.Title>
      <Card>
        <Descriptions
          column={1}
          items={[
            { key: 'code', label: t('colonnes.code'), children: etablissement.code },
            {
              key: 'statut',
              label: t('colonnes.statut'),
              children: etablissement.actif ? (
                <BadgeStatut ton="succes" libelle={tCommun('statut.actif')} />
              ) : (
                <BadgeStatut ton="neutre" libelle={tCommun('statut.inactif')} />
              ),
            },
          ]}
        />
        <Form
          form={formulaire}
          layout="vertical"
          onFinish={(valeurs) => modification.mutate(valeurs)}
        >
          <Form.Item
            name="nom"
            label={t('formulaire.nom')}
            rules={[{ required: true, message: tCommun('connexion.obligatoire') }]}
          >
            <Input maxLength={200} />
          </Form.Item>
          <Flex gap="small" wrap>
            <Button type="primary" htmlType="submit" loading={modification.isPending}>
              {tCommun('actions.enregistrer')}
            </Button>
            <Button onClick={() => modification.mutate({ actif: !etablissement.actif })}>
              {etablissement.actif ? t('actions.desactiver') : t('actions.activer')}
            </Button>
          </Flex>
        </Form>
      </Card>
      <ParametresCalcul etablissementId={id} />
    </Flex>
  )
}
