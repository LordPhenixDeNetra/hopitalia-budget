import type { ReactNode } from 'react'
import { Navigate, createBrowserRouter, useLocation, type RouteObject } from 'react-router'
import { useSession } from './auth/session'
import { Gabarit, type Poignee } from './composants/Gabarit'
import { Accueil } from './pages/Accueil'
import { Connexion } from './pages/Connexion'
import { Etablissements } from './pages/Etablissements'
import { FicheEtablissement } from './pages/FicheEtablissement'
import { Habilitations } from './pages/Habilitations'
import { PageIntrouvable } from './pages/PageIntrouvable'

/** Sans session, renvoie vers la connexion en gardant l'adresse demandée (lien profond). */
function RouteProtegee({ children }: { children: ReactNode }) {
  const { connecte } = useSession()
  const { pathname, search } = useLocation()
  if (!connecte) {
    return <Navigate to={`/connexion?retour=${encodeURIComponent(pathname + search)}`} replace />
  }
  return children
}

const fil = (cle: string): Poignee => ({ fil: cle })

export const routes: RouteObject[] = [
  { path: '/connexion', element: <Connexion /> },
  {
    path: '/',
    element: (
      <RouteProtegee>
        <Gabarit />
      </RouteProtegee>
    ),
    handle: fil('menu.accueil'),
    children: [
      { index: true, element: <Accueil /> },
      {
        path: 'etablissements',
        handle: fil('menu.etablissements'),
        children: [
          { index: true, element: <Etablissements /> },
          { path: ':id', element: <FicheEtablissement /> },
        ],
      },
      { path: 'habilitations', element: <Habilitations />, handle: fil('menu.habilitations') },
      { path: '*', element: <PageIntrouvable /> },
    ],
  },
]

export const creerRouteur = () => createBrowserRouter(routes)
