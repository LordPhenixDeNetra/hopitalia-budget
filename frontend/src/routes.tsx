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

// Écrans métier chargés à la demande : le paquet initial reste léger.
const budget = () => import('./pages/budget/FicheBudget')
const parametrage = () => import('./pages/parametrage/Parametrage')

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
      {
        path: 'contrats',
        handle: fil('menu.contrats'),
        children: [
          {
            index: true,
            lazy: () =>
              import('./pages/contrats/Contrats').then((m) => ({ Component: m.Contrats })),
          },
          {
            path: ':id',
            lazy: () =>
              import('./pages/contrats/FicheContrat').then((m) => ({ Component: m.FicheContrat })),
          },
        ],
      },
      {
        path: 'engagements',
        handle: fil('menu.engagements'),
        children: [
          {
            index: true,
            lazy: () =>
              import('./pages/engagements/Engagements').then((m) => ({
                Component: m.Engagements,
              })),
          },
          {
            path: ':id',
            lazy: () =>
              import('./pages/engagements/FicheEngagement').then((m) => ({
                Component: m.FicheEngagement,
              })),
          },
        ],
      },
      {
        path: 'commandes',
        handle: fil('menu.commandes'),
        lazy: () => import('./pages/commandes/Commandes').then((m) => ({ Component: m.Commandes })),
      },
      {
        path: 'bons-commande/:id',
        handle: fil('menu.commandes'),
        lazy: () =>
          import('./pages/commandes/FicheCommande').then((m) => ({ Component: m.FicheCommande })),
      },
      {
        path: 'factures',
        handle: fil('menu.factures'),
        children: [
          {
            index: true,
            lazy: () =>
              import('./pages/factures/Factures').then((m) => ({ Component: m.Factures })),
          },
          {
            path: ':id',
            lazy: () =>
              import('./pages/factures/FicheFacture').then((m) => ({ Component: m.FicheFacture })),
          },
        ],
      },
      {
        path: 'delegations',
        lazy: () => import('./pages/Delegations').then((m) => ({ Component: m.Delegations })),
        handle: fil('menu.delegations'),
      },
      {
        path: 'parametrage',
        handle: fil('menu.parametrage'),
        children: [
          { index: true, lazy: () => parametrage().then((m) => ({ Component: m.Parametrage })) },
          {
            path: ':ressource',
            lazy: () => parametrage().then((m) => ({ Component: m.Parametrage })),
          },
        ],
      },
      {
        path: 'nomenclature',
        lazy: () =>
          import('./pages/parametrage/Nomenclature').then((m) => ({ Component: m.Nomenclature })),
        handle: fil('menu.nomenclature'),
      },
      {
        path: 'budgets',
        handle: fil('menu.budgets'),
        children: [
          { index: true, lazy: () => budget().then((m) => ({ Component: m.Budgets })) },
          { path: ':id', lazy: () => budget().then((m) => ({ Component: m.FicheBudget })) },
        ],
      },
      {
        path: 'lignes-budgetaires/:id',
        lazy: () => import('./pages/budget/FicheLigne').then((m) => ({ Component: m.FicheLigne })),
        handle: fil('menu.budgets'),
      },
      { path: '*', element: <PageIntrouvable /> },
    ],
  },
]

export const creerRouteur = () => createBrowserRouter(routes)
