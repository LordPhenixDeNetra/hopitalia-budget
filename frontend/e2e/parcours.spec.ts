import { expect, test, type Page } from '@playwright/test'

const MOI = {
  idHopitalia: 1,
  codeAgent: 'AG001',
  nom: 'Awa Diop',
  service: 'DAF',
  habilitations: [{ profil: 'ADM', etablissementId: null }],
  langue: null,
}

const ETABLISSEMENTS = {
  donnees: [
    { id: 'a1', code: 'CHU-FANN', nom: 'CHU de Fann', actif: true, version: 1 },
    { id: 'b2', code: 'HOP-PRINCIPAL', nom: 'Hôpital Principal', actif: false, version: 3 },
  ],
  pagination: { page: 1, taille: 25, total: 2, suivant: null },
}

async function simulerApi(page: Page) {
  await page.route('**/api/v1/**', async (route) => {
    const chemin = new URL(route.request().url()).pathname
    const reponses: Record<string, unknown> = {
      '/api/v1/auth/connexion': { jetonAcces: 'a', jetonRafraichissement: 'r', expireDans: 900 },
      '/api/v1/moi': MOI,
      '/api/v1/moi/preferences': { ...MOI, langue: 'en' },
      '/api/v1/etablissements': ETABLISSEMENTS,
    }
    await route.fulfill({ json: reponses[chemin] ?? {} })
  })
}

test('connexion, liste des établissements et statut lisible', async ({ page }) => {
  const externes: string[] = []
  page.on('request', (requete) => {
    if (!requete.url().startsWith('http://127.0.0.1:4173')) externes.push(requete.url())
  })
  await simulerApi(page)
  await page.goto('/etablissements')
  await expect(page).toHaveURL(/\/connexion\?retour=/)

  await page.getByLabel('Identifiant').fill('agent')
  await page.getByLabel('Mot de passe').fill('secret')
  await page.getByRole('button', { name: 'Se connecter' }).click()

  await expect(page.getByRole('heading', { name: 'Établissements' })).toBeVisible()
  await expect(page.getByText('CHU-FANN')).toBeVisible()
  // Statut signalé par un libellé, pas seulement par la couleur (IHM-06).
  await expect(page.getByText('Inactif', { exact: true })).toBeVisible()

  // Aucun défilement horizontal de la page, même sur téléphone (IHM-08).
  const deborde = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
  )
  expect(deborde).toBe(false)
  // Polices hébergées avec l'application : aucune requête hors du serveur (IHM-04).
  expect(externes).toEqual([])
})

test('changement de langue sans rechargement (I18N-04)', async ({ page, isMobile }) => {
  test.skip(isMobile, 'Le sélecteur de langue est dans l’en-tête du gabarit ordinateur')
  await simulerApi(page)
  await page.goto('/connexion')
  await page.getByLabel('Identifiant').fill('agent')
  await page.getByLabel('Mot de passe').fill('secret')
  await page.getByRole('button', { name: 'Se connecter' }).click()
  await page.getByRole('combobox', { name: 'Langue' }).click()
  await page.getByTitle('English').click()
  await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible()
})
