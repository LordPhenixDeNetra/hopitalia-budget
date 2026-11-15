import { DownloadOutlined, UploadOutlined } from '@ant-design/icons'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { App, Button, Flex, List, Select, Typography, Upload } from 'antd'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { telechargerFichier } from '../../api/client'
import { useAfficherErreur } from '../../api/erreurs'
import {
  deposerPiece,
  getListerPiecesQueryKey,
  getTelechargerPieceUrl,
  useListerPieces,
  useListerTypesPieces,
} from '../../api/genere/budget'
import { formaterDateHeure } from '../../format/format'

export type RessourcePieces = Parameters<typeof deposerPiece>[0]

/** Pièces justificatives d'une ressource : liste, dépôt et téléchargement vérifié (T-120). */
export function Pieces({
  ressource,
  id,
  peutDeposer,
}: {
  ressource: RessourcePieces
  id: string
  peutDeposer: boolean
}) {
  const { t, i18n } = useTranslation('workflow')
  const { message } = App.useApp()
  const afficherErreur = useAfficherErreur()
  const client = useQueryClient()
  const [typePieceId, setTypePieceId] = useState<string>()
  const { data: pieces = [] } = useListerPieces(ressource, id)
  const { data: types } = useListerTypesPieces({ actif: true, taille: 100 })
  const libelles = new Map((types?.donnees ?? []).map((tp) => [tp.id, tp.libelle]))

  const depot = useMutation({
    mutationFn: (fichier: File) =>
      deposerPiece(ressource, id, { fichier, typePieceId: typePieceId! }),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: getListerPiecesQueryKey(ressource, id) })
      void message.success(t('pieces.deposee'))
    },
    onError: (erreur) => afficherErreur(erreur),
  })
  const telechargement = useMutation({
    mutationFn: ({ pieceId, nom }: { pieceId: string; nom: string }) =>
      telechargerFichier(getTelechargerPieceUrl(pieceId), nom),
    onError: (erreur) => afficherErreur(erreur),
  })

  return (
    <Flex vertical gap="small">
      <Typography.Title level={4}>{t('pieces.titre')}</Typography.Title>
      <List
        dataSource={pieces}
        locale={{ emptyText: t('pieces.aucune') }}
        renderItem={(p) => (
          <List.Item
            key={p.id}
            actions={[
              <Button
                key="telecharger"
                icon={<DownloadOutlined aria-hidden />}
                onClick={() => telechargement.mutate({ pieceId: p.id, nom: p.nomFichier })}
              >
                {t('pieces.telecharger')}
              </Button>,
            ]}
          >
            <List.Item.Meta
              title={`${p.nomFichier} — ${libelles.get(p.typePieceId) ?? ''}`}
              description={`${t('pieces.deposePar')} ${p.deposeParCode}, ${formaterDateHeure(p.deposeLe, i18n.language)} — ${t('pieces.empreinte')} ${p.empreinteSha256.slice(0, 16)}…`}
            />
          </List.Item>
        )}
      />
      {peutDeposer && (
        <Flex gap="small" wrap align="center">
          <Select
            aria-label={t('pieces.type')}
            placeholder={t('pieces.type')}
            style={{ minWidth: 220 }}
            value={typePieceId}
            onChange={setTypePieceId}
            options={(types?.donnees ?? []).map((tp) => ({ value: tp.id, label: tp.libelle }))}
          />
          <Upload
            accept=".pdf,.png,.jpg,.jpeg,.docx,.xlsx"
            showUploadList={false}
            disabled={!typePieceId}
            beforeUpload={(fichier) => {
              depot.mutate(fichier)
              return false
            }}
          >
            <Button
              icon={<UploadOutlined aria-hidden />}
              disabled={!typePieceId}
              loading={depot.isPending}
            >
              {t('pieces.deposer')}
            </Button>
          </Upload>
          <Typography.Text type="secondary">{t('pieces.formats')}</Typography.Text>
        </Flex>
      )}
    </Flex>
  )
}
