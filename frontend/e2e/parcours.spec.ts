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

test('REC-01 : créer un exercice puis importer les crédits du budget', async ({ page }) => {
  const zero = '0.00'
  const totaux = Object.fromEntries(
    [
      'budgetInitial',
      'budgetRevise',
      'engage',
      'disponibleApresEngagements',
      'liquide',
      'paye',
    ].map((c) => [c, zero]),
  )
  const envois: { chemin: string; type: string | null; corps: string }[] = []
  await page.route('**/api/v1/**', async (route) => {
    const requete = route.request()
    const chemin = new URL(requete.url()).pathname
    if (requete.method() === 'POST') {
      envois.push({
        chemin,
        type: await requete.headerValue('content-type'),
        corps: requete.postData() ?? '',
      })
    }
    const vide = { donnees: [], pagination: { page: 1, taille: 25, total: 0, suivant: null } }
    const reponses: Record<string, unknown> = {
      '/api/v1/auth/connexion': { jetonAcces: 'a', jetonRafraichissement: 'r', expireDans: 900 },
      '/api/v1/moi': {
        ...MOI,
        habilitations: [
          { profil: 'ADM', etablissementId: null },
          { profil: 'RB', etablissementId: 'a1' },
        ],
      },
      '/api/v1/exercices': requete.method() === 'POST' ? { id: 'x1', code: '2026' } : vide,
      '/api/v1/budgets/b1': { id: 'b1', reference: 'BP-2026', type: 'PRIMITIF', version: 1 },
      '/api/v1/budgets/b1/situation': { budgetId: 'b1', lignes: [], totaux },
      '/api/v1/budgets/b1/imports': { id: 'i1', statut: 'EN_COURS', anomalies: [] },
      '/api/v1/imports-dotations/i1': {
        id: 'i1',
        budgetId: 'b1',
        statut: 'TERMINE',
        lignesImportees: 2,
        anomalies: [],
        creeLe: '2026-01-05T10:00:00Z',
      },
    }
    await route.fulfill({ json: reponses[chemin] ?? vide })
  })

  await page.goto('/connexion?retour=/parametrage/exercices')
  await page.getByLabel('Identifiant').fill('agent')
  await page.getByLabel('Mot de passe').fill('secret')
  await page.getByRole('button', { name: 'Se connecter' }).click()

  await page.getByRole('button', { name: 'Ajouter' }).click()
  const dialogue = page.getByRole('dialog')
  await dialogue.getByLabel('Code').fill('2026')
  await dialogue.getByLabel('Ouverture').fill('2026-01-01')
  await dialogue.getByLabel('Clôture').fill('2026-12-31')
  await dialogue.getByRole('button', { name: 'Enregistrer' }).click()
  await expect(page.getByText('Élément ajouté.')).toBeVisible()

  await page.goto('/budgets/b1')
  await page.getByRole('tab', { name: 'Import des dotations' }).click()
  await page.locator('input[type=file]').setInputFiles({
    name: 'dotations.csv',
    mimeType: 'text/csv',
    buffer: Buffer.from('code;libelle;compte;centre;source;programme;dotation\n'),
  })
  await expect(page.getByText('Lignes importées : 2')).toBeVisible()
  expect(envois.map((e) => e.chemin)).toEqual([
    '/api/v1/auth/connexion',
    '/api/v1/exercices',
    '/api/v1/budgets/b1/imports',
  ])
  expect(envois[2]!.type).toBe('text/csv')
})
