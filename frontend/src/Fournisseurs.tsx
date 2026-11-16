import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { App as AppAntd, ConfigProvider, theme as themeAntd } from 'antd'
import enUS from 'antd/locale/en_US'
import frFR from 'antd/locale/fr_FR'
import { useEffect, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { ErreurApi } from './api/client'
import { FournisseurSession } from './auth/session'
import { directionDeTest, usePreferencesAffichage, useSombre } from './theme/preferences'
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
  const [client] = useState(() => clientFourni ?? creerClientRequetes())
  return (
    <QueryClientProvider client={client}>
      <FournisseurSession>
        <Affichage>{children}</Affichage>
      </FournisseurSession>
    </QueryClientProvider>
  )
}

/** Thème, densité et direction d'écriture, selon les préférences de l'agent (T-270 à T-273). */
function Affichage({ children }: { children: ReactNode }) {
  const { i18n } = useTranslation()
  const mouvementReduit = useMouvementReduit()
  const { theme, densite } = usePreferencesAffichage()
  const sombre = useSombre(theme)
  // Droite à gauche selon la langue (I18N-10) ; forcé pour le test, aucune langue de ce type
  // n'étant prévue.
  const direction = directionDeTest() ?? i18n.dir(i18n.language)
  useEffect(() => {
    document.documentElement.dir = direction
    document.documentElement.lang = i18n.language
  }, [direction, i18n.language])
  return (
    <ConfigProvider
      theme={creerTheme(mouvementReduit, { sombre, compacte: densite === 'COMPACTE' })}
      locale={i18n.language === 'en' ? enUS : frFR}
      direction={direction}
    >
      <AppAntd>
        <FondPage sombre={sombre} />
        {children}
      </AppAntd>
    </ConfigProvider>
  )
}

/** Fond et couleur du texte de la page, pris dans le thème (l'écran de connexion n'a pas de
 * gabarit). */
function FondPage({ sombre }: { sombre: boolean }) {
  const { token } = themeAntd.useToken()
  useEffect(() => {
    document.body.style.backgroundColor = token.colorBgLayout
    document.body.style.color = token.colorText
    // Barres de défilement et contrôles natifs assortis au thème.
    document.documentElement.style.colorScheme = sombre ? 'dark' : 'light'
  }, [token.colorBgLayout, token.colorText, sombre])
  return null
}
