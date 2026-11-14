import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  ExclamationCircleOutlined,
  InfoCircleOutlined,
  MinusCircleOutlined,
} from '@ant-design/icons'
import { Tag } from 'antd'
import type { ReactNode } from 'react'

export type Ton = 'succes' | 'attention' | 'erreur' | 'info' | 'neutre'

const ICONES: Record<Ton, ReactNode> = {
  succes: <CheckCircleOutlined aria-hidden />,
  attention: <ExclamationCircleOutlined aria-hidden />,
  erreur: <CloseCircleOutlined aria-hidden />,
  info: <InfoCircleOutlined aria-hidden />,
  neutre: <MinusCircleOutlined aria-hidden />,
}

// Couleurs prédéfinies d'Ant Design, issues des jetons du thème.
const COULEURS: Record<Ton, string> = {
  succes: 'success',
  attention: 'warning',
  erreur: 'error',
  info: 'processing',
  neutre: 'default',
}

/** Statut toujours signalé par un libellé et une icône, jamais par la seule couleur (IHM-06). */
export function BadgeStatut({ ton, libelle }: { ton: Ton; libelle: string }) {
  return (
    <Tag icon={ICONES[ton]} color={COULEURS[ton]}>
      {libelle}
    </Tag>
  )
}
