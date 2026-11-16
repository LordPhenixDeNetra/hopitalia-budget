import { expect, test, type Page } from '@playwright/test'
import { mkdirSync } from 'node:fs'

// Captures d'écran de la documentation (site/src/assets/captures/fr/), prises dans l'environnement de
// démonstration (simulation/demonstration.py) : interface réelle, API réelle, Hopitalia simulé.
// Lancer : npx playwright test -c playwright.captures.config.ts. Aucune capture ne modifie de donnée.

const DOSSIER = '../site/src/assets/captures/fr'

interface Capture {
  nom: string
  compte?: string
  chemin: string
  /** Gestes avant la capture : ouvrir une fiche, un onglet, choisir un établissement. */
  avant?: (page: Page) => Promise<void>
}

const onglet = (nom: string) => async (page: Page) => {
  await page.getByRole('tab', { name: nom, exact: true }).click()
}
const ouvrir = (nom: string | RegExp) => async (page: Page) => {
  const liste = page.url()
  await page.getByRole('link', { name: nom }).first().click()
  // La fiche se charge à part : attendre son adresse, puis son titre.
  await expect(page).not.toHaveURL(liste)
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
}

const CAPTURES: Capture[] = [
  { nom: 'connexion', chemin: '/connexion' },
  { nom: 'accueil', compte: 'agent002', chemin: '/' },
  { nom: 'tableau-de-bord', compte: 'agent002', chemin: '/tableau-de-bord' },
  { nom: 'budget-situation', compte: 'agent002', chemin: '/budgets', avant: ouvrir(/BP-2026/) },
  { nom: 'contrats', compte: 'agent011', chemin: '/contrats' },
  { nom: 'contrat-synthese', compte: 'agent011', chemin: '/contrats', avant: ouvrir(/^M-2026/) },
  { nom: 'engagements', compte: 'agent003', chemin: '/engagements' },
  {
    nom: 'engagement-validation',
    compte: 'agent003',
    chemin: '/engagements',
    avant: async (page) => {
      await ouvrir('ENG-2026-00006')(page)
      await onglet('Validation et pièces')(page)
    },
  },
  { nom: 'commandes', compte: 'agent013', chemin: '/commandes' },
  { nom: 'commandes-pharmacie', compte: 'agent012', chemin: '/commandes-pharmacie' },
  { nom: 'factures', compte: 'agent012', chemin: '/factures' },
  {
    nom: 'facture-rapprochement',
    compte: 'agent012',
    chemin: '/factures',
    avant: async (page) => {
      await page.getByRole('table').getByRole('link').first().click()
      await onglet('Rapprochement')(page)
    },
  },
  { nom: 'paiements', compte: 'agent004', chemin: '/paiements' },
  { nom: 'recettes', compte: 'agent002', chemin: '/recettes' },
  { nom: 'etats', compte: 'agent002', chemin: '/etats' },
  { nom: 'alertes', compte: 'agent002', chemin: '/alertes' },
  { nom: 'delegations', compte: 'agent003', chemin: '/delegations' },
  {
    nom: 'cloture-exercice',
    compte: 'agent002',
    chemin: '/cloture-exercice',
    avant: async (page) => {
      await page.getByLabel('Exercice', { exact: true }).click()
      await page.getByTitle('2026', { exact: true }).click()
      await expect(page.getByLabel('Motif')).toBeVisible()
    },
  },
  { nom: 'journal-audit', compte: 'agent007', chemin: '/audit' },
  { nom: 'etablissement', compte: 'agent001', chemin: '/etablissements', avant: ouvrir('CHU-A') },
  { nom: 'habilitations', compte: 'agent001', chemin: '/habilitations' },
  { nom: 'parametrage', compte: 'agent001', chemin: '/parametrage/centres-responsabilite' },
  { nom: 'circuits', compte: 'agent001', chemin: '/parametrage/circuits-validation' },
  {
    nom: 'alertes-regles',
    compte: 'agent001',
    chemin: '/alertes',
    avant: async (page) => {
      await onglet('Règles')(page)
      await page.getByRole('tabpanel', { name: 'Règles' }).getByLabel('Établissement').click()
      await page.getByTitle('CHU-A — CHU A').click()
      await expect(page.getByRole('table')).toBeVisible()
    },
  },
  { nom: 'integrations', compte: 'agent001', chemin: '/integrations' },
]

async function connecter(page: Page, compte: string) {
  await page.goto('/connexion')
  await page.getByLabel('Identifiant').fill(compte)
  await page.getByLabel('Mot de passe').fill('recette')
  await page.getByRole('button', { name: 'Se connecter' }).click()
  await expect(page.getByText(`Bienvenue, Agent ${compte.slice(5)}`)).toBeVisible()
}

test.beforeAll(() => mkdirSync(DOSSIER, { recursive: true }))

for (const capture of CAPTURES) {
  test(`capture ${capture.nom}`, async ({ page }) => {
    if (capture.compte) await connecter(page, capture.compte)
    await page.goto(capture.chemin)
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
    await capture.avant?.(page)
    await page.waitForLoadState('networkidle')
    await page.screenshot({ path: `${DOSSIER}/${capture.nom}.png` })
  })
}
