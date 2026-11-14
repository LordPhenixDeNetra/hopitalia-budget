import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { App as AppAntd, ConfigProvider } from 'antd'
import enUS from 'antd/locale/en_US'
import frFR from 'antd/locale/fr_FR'
import { useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { ErreurApi } from './api/client'
import { FournisseurSession } from './auth/session'
import { creerTheme } from './theme/theme'
import { useMouvementReduit } from './theme/useMouvementReduit'

/** Erreur 4xx : rejouer ne changera rien (409, 412… sont traités par l'écran). */
const rejouer = (tentatives: number, erreur: unknown) =>
  tentatives < 2 && !(erreur instanceof ErreurApi && erreur.probleme.status < 500)

export function creerClientRequetes(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: rejouer, staleTime: 30_000 },
      mutations: { retry: false },
    },
  })
}

/** Thème, langue d'Ant Design, client de requêtes et session : communs à toute l'application. */
export function Fournisseurs({
  children,
  client: clientFourni,
}: {
  children: ReactNode
  client?: QueryClient
}) {
  const { i18n } = useTranslation()
  const mouvementReduit = useMouvementReduit()
  const [client] = useState(() => clientFourni ?? creerClientRequetes())
  return (
    <ConfigProvider
      theme={creerTheme(mouvementReduit)}
      locale={i18n.language === 'en' ? enUS : frFR}
    >
      <AppAntd>
        <QueryClientProvider client={client}>
          <FournisseurSession>{children}</FournisseurSession>
        </QueryClientProvider>
      </AppAntd>
    </ConfigProvider>
  )
}
