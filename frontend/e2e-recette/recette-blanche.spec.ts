import { expect, test, type Page } from '@playwright/test'

// Agents de l'Hopitalia simulé (agentNNN / recette) et profils attribués par la recette blanche.
const AGENTS = [
  { compte: 'agent002', profil: 'RB', ecran: '/tableau-de-bord', attendu: 'Tableau de bord' },
  { compte: 'agent011', profil: 'GMC', ecran: '/contrats', attendu: 'Fournitures médicales' },
  { compte: 'agent012', profil: 'AF', ecran: '/commandes-pharmacie', attendu: 'BCP-' },
  { compte: 'agent013', profil: 'REC', ecran: '/commandes', attendu: 'BC-2026-00001' },
  { compte: 'agent003', profil: 'VAL', ecran: '/engagements', attendu: 'ENG-2026-00001' },
  {
    compte: 'agent004',
    profil: 'ORD',
    ecran: '/paiements',
    attendu: 'Ordonnancement et paiements',
  },
  { compte: 'agent014', profil: 'CPT', ecran: '/paiements', attendu: 'Pris en charge' },
  { compte: 'agent007', profil: 'AUD', ecran: '/audit', attendu: 'Journal' },
  { compte: 'agent002', profil: 'RB', ecran: '/recettes', attendu: 'RCT-2026-00001' },
]

async function connecter(page: Page, compte: string) {
  await page.goto('/connexion')
  await page.getByLabel('Identifiant').fill(compte)
  await page.getByLabel('Mot de passe').fill('recette')
  await page.getByRole('button', { name: 'Se connecter' }).click()
  // Langue du profil (I18N-04) : l'agent financier a choisi l'anglais pendant la recette blanche.
  await expect(
    page.getByText(new RegExp(`(Bienvenue|Welcome), Agent ${compte.slice(5)}`)),
  ).toBeVisible()
}

for (const agent of AGENTS) {
  test(`recette blanche : ${agent.profil} se connecte par Hopitalia et ouvre ${agent.ecran}`, async ({
    page,
  }, infos) => {
    await connecter(page, agent.compte)
    await page.goto(agent.ecran)
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
    await expect(page.getByText(agent.attendu).first()).toBeVisible()
    await infos.attach(`${agent.profil}${agent.ecran.replaceAll('/', '_')}`, {
      body: await page.screenshot({ fullPage: true }),
      contentType: 'image/png',
    })
  })
}

test('recette blanche : le tableau de bord montre les montants du jeu d’essai', async ({
  page,
}) => {
  await connecter(page, 'agent002')
  await page.goto('/tableau-de-bord')
  // Engagé du jeu d'essai (80 M) et payé (30 M), formatés en français.
  await expect(page.getByText(/80\s000\s000/).first()).toBeVisible()
  await expect(page.getByText(/30\s000\s000/).first()).toBeVisible()
})
