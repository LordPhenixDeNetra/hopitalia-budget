import { useMutation, useQueryClient } from '@tanstack/react-query'
import { App, Button, Flex, Input, Space, Steps, Timeline, Typography } from 'antd'
import { useTranslation } from 'react-i18next'
import { useAfficherErreur } from '../../api/erreurs'
import { decider, getLireValidationsQueryKey, useLireValidations } from '../../api/genere/budget'
import type { Decision } from '../../api/genere/budget.schemas'
import { formaterDateHeure } from '../../format/format'

export type RessourceValidable = Parameters<typeof decider>[0]

/**
 * Circuit, historique des visas et décision (T-120), pour toute ressource validable.
 * Les boutons n'apparaissent que si le serveur indique que l'agent peut décider.
 */
export function Validations({
  ressource,
  id,
  surDecision,
}: {
  ressource: RessourceValidable
  id: string
  surDecision?: () => void
}) {
  const { t, i18n } = useTranslation('workflow')
  const { t: tCommun } = useTranslation()
  const { t: tProfils } = useTranslation('habilitations')
  const { message, modal } = App.useApp()
  const afficherErreur = useAfficherErreur()
  const client = useQueryClient()
  const { data: etat } = useLireValidations(ressource, id)

  const envoi = useMutation({
    mutationFn: (corps: { decision: Decision; motif?: string }) => decider(ressource, id, corps),
    onSuccess: (nouvel) => {
      client.setQueryData(getLireValidationsQueryKey(ressource, id), nouvel)
      void message.success(t('validations.enregistree'))
      surDecision?.()
    },
    onError: (erreur) => afficherErreur(erreur),
  })

  // Rejet et retour exigent un motif, saisi dans une boîte de dialogue.
  const avecMotif = (decision: Decision, titre: string) => {
    let motif = ''
    modal.confirm({
      title: titre,
      content: (
        <Input.TextArea
          aria-label={t('validations.motif')}
          maxLength={500}
          onChange={(e) => (motif = e.target.value)}
        />
      ),
      okText: titre,
      cancelText: tCommun('actions.annuler'),
      onOk: () => envoi.mutateAsync({ decision, motif }),
    })
  }

  if (!etat) return null
  // Étapes visées dans le cycle courant : un retour pour correction fait repartir le circuit.
  const debut = etat.visas.map((v) => v.decision).lastIndexOf('A_CORRIGER') + 1
  const vises = new Set(
    etat.visas
      .slice(debut)
      .filter((v) => v.decision === 'VALIDE')
      .map((v) => v.ordre),
  )
  return (
    <Flex vertical gap="middle">
      <Typography.Title level={4}>{t('validations.circuit')}</Typography.Title>
      <Steps
        size="small"
        current={etat.etapesOuvertes[0] ? etat.etapesOuvertes[0] - 1 : etat.etapes.length}
        items={etat.etapes.map((e) => ({
          title: e.libelle,
          description: `${tProfils(`profils.${e.profil}`)}${e.obligatoire ? '' : ` (${t('validations.facultative')})`}`,
          status: vises.has(e.ordre)
            ? 'finish'
            : etat.etapesOuvertes.includes(e.ordre)
              ? 'process'
              : 'wait',
        }))}
      />
      {etat.visas.length === 0 ? (
        <Typography.Text>{t('validations.aucunVisa')}</Typography.Text>
      ) : (
        <Timeline
          items={etat.visas.map((v) => ({
            key: `${v.horodatage}-${v.ordre}-${v.codeAgent}`,
            content: [
              t(`validations.${v.decision}`),
              v.codeAgent,
              v.delegantCode ? t('validations.parDelegation', { code: v.delegantCode }) : '',
              formaterDateHeure(v.horodatage, i18n.language),
              v.motif ?? '',
            ]
              .filter(Boolean)
              .join(' — '),
          }))}
        />
      )}
      {etat.peutDecider && (
        <Space wrap>
          <Button
            type="primary"
            loading={envoi.isPending}
            onClick={() => envoi.mutate({ decision: 'VALIDE' })}
          >
            {t('validations.valider')}
          </Button>
          <Button onClick={() => avecMotif('A_CORRIGER', t('validations.retourner'))}>
            {t('validations.retourner')}
          </Button>
          <Button danger onClick={() => avecMotif('REJETE', t('validations.rejeter'))}>
            {t('validations.rejeter')}
          </Button>
        </Space>
      )}
    </Flex>
  )
}
