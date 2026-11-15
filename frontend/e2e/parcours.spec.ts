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

/**
 * Ouvre un onglet de fiche. Sur téléphone, Ant Design fait défiler la barre d'onglets au doigt
 * (pas de menu « … ») : les onglets qui ne tiennent pas sont hors de l'écran. On fait défiler
 * la barre jusqu'à l'onglet, comme l'utilisateur, puis on le touche.
 */
async function ouvrirOnglet(page: Page, nom: string) {
  const onglet = page.getByRole('tab', { name: nom })
  const largeur = page.viewportSize()?.width ?? 0
  const barre = page.locator('.ant-tabs-nav-wrap').first()
  for (let essai = 0; essai < 10; essai++) {
    const boite = await onglet.boundingBox()
    if (boite && boite.x >= 0 && boite.x + boite.width <= largeur) break
    const zone = (await barre.boundingBox())!
    await page.mouse.move(zone.x + zone.width / 2, zone.y + zone.height / 2)
    await page.mouse.wheel(0, 120)
    await page.waitForTimeout(100)
  }
  await onglet.click()
  await expect(onglet).toHaveAttribute('aria-selected', 'true')
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
  await ouvrirOnglet(page, 'Import des dotations')
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

test('REC-02 : enregistrer un marché avec ventilation, échéance et pièce', async ({ page }) => {
  const page1 = (donnees: unknown[]) => ({
    donnees,
    pagination: { page: 1, taille: 100, total: donnees.length, suivant: null },
  })
  const contrat = {
    id: 'c1',
    etablissementId: 'a1',
    type: 'MARCHE',
    numero: 'M-2026-001',
    intitule: 'Fournitures médicales',
    nature: null,
    numeroLot: null,
    fournisseurId: 'f1',
    devise: 'XOF',
    montantInitialHt: '100000000.00',
    tauxTaxe: '0.00',
    montantInitialTtc: '100000000.00',
    centreId: 'ce1',
    sourceId: 's1',
    statut: 'BROUILLON',
    creeParCode: 'AG011',
    creeLe: '2026-01-05T10:00:00Z',
    version: 1,
    imputations: [{ id: 'i1', ligneId: 'l1', montant: '100000000.00' }],
  }
  const envois: { chemin: string; corps: string; type: string | null }[] = []
  await page.route('**/api/v1/**', async (route) => {
    const requete = route.request()
    const chemin = new URL(requete.url()).pathname
    if (requete.method() === 'POST') {
      envois.push({
        chemin,
        corps: requete.postData() ?? '',
        type: await requete.headerValue('content-type'),
      })
    }
    const reponses: Record<string, unknown> = {
      '/api/v1/auth/connexion': { jetonAcces: 'a', jetonRafraichissement: 'r', expireDans: 900 },
      '/api/v1/moi': { ...MOI, habilitations: [{ profil: 'GMC', etablissementId: 'a1' }] },
      '/api/v1/etablissements': page1([{ id: 'a1', code: 'CHU-A', nom: 'CHU A' }]),
      '/api/v1/fournisseurs': page1([
        { id: 'f1', code: 'PHARMA', raisonSociale: 'Pharma Test SA' },
      ]),
      '/api/v1/centres-responsabilite': page1([
        { id: 'ce1', code: 'PHARMA', libelle: 'Pharmacie' },
      ]),
      '/api/v1/sources-financement': page1([
        { id: 's1', code: 'ETAT', libelle: 'Budget de l’État' },
      ]),
      '/api/v1/lignes-budgetaires': page1([{ id: 'l1', code: '604-MED', libelle: 'Médicaments' }]),
      '/api/v1/types-pieces': page1([{ id: 'tp1', code: 'CONTRAT', libelle: 'Contrat signé' }]),
      '/api/v1/contrats': requete.method() === 'POST' ? contrat : page1([]),
      '/api/v1/contrats/c1': contrat,
      '/api/v1/contrats/c1/synthese': { contratId: 'c1', montantActualise: '100000000.00' },
      '/api/v1/contrats/c1/avenants': [],
      '/api/v1/contrats/c1/echeances':
        requete.method() === 'POST'
          ? { id: 'e1', libelle: 'T1', dateEcheance: '2026-03-31', montantPrevu: '25000000.00' }
          : [],
      '/api/v1/contrats/c1/lots': [],
      '/api/v1/contrats/c1/ordres-service': [],
      '/api/v1/contrats/c1/revisions-prix': [],
      '/api/v1/contrats/c1/validations': {
        statut: 'BROUILLON',
        separationTaches: true,
        etapes: [{ ordre: 1, libelle: 'Visa DAF', profil: 'VAL', obligatoire: true }],
        visas: [],
        etapesOuvertes: [],
        peutDecider: false,
      },
      '/api/v1/contrats/c1/pieces':
        requete.method() === 'POST'
          ? {
              id: 'p1',
              typePieceId: 'tp1',
              nomFichier: 'contrat.pdf',
              typeMime: 'application/pdf',
              taille: 10,
              empreinteSha256: 'a'.repeat(64),
              deposeParCode: 'AG011',
              deposeLe: '2026-01-05T10:00:00Z',
            }
          : [],
    }
    await route.fulfill({
      status: requete.method() === 'POST' ? 201 : 200,
      json: reponses[chemin] ?? page1([]),
    })
  })

  await page.goto('/connexion?retour=/contrats')
  await page.getByLabel('Identifiant').fill('agent')
  await page.getByLabel('Mot de passe').fill('secret')
  await page.getByRole('button', { name: 'Se connecter' }).click()
  await page.getByRole('button', { name: 'Enregistrer un contrat' }).click()

  const tiroir = page.getByRole('dialog')
  const choisir = async (libelle: string, option: string) => {
    await tiroir.getByLabel(libelle, { exact: true }).click()
    await page.getByTitle(option).click()
  }
  await choisir('Établissement', 'CHU-A — CHU A')
  await tiroir.getByLabel('Numéro', { exact: true }).fill('M-2026-001')
  await tiroir.getByLabel('Intitulé').fill('Fournitures médicales')
  await choisir('Attributaire', 'PHARMA — Pharma Test SA')
  await tiroir.getByLabel('Date de signature').fill('2026-01-05')
  await tiroir.getByLabel('Montant initial HT').fill('100000000.00')
  await choisir('Service bénéficiaire', 'PHARMA — Pharmacie')
  await choisir('Source de financement', 'ETAT — Budget de l’État')
  await choisir('Ligne budgétaire', '604-MED — Médicaments')
  await tiroir.getByLabel('Montant', { exact: true }).fill('100000000.00')
  await tiroir.getByRole('button', { name: 'Enregistrer' }).click()

  await expect(
    page.getByRole('heading', { name: 'M-2026-001 — Fournitures médicales' }),
  ).toBeVisible()
  await ouvrirOnglet(page, 'Exécution')
  await page.getByLabel('Libellé').first().fill('T1')
  await page.getByLabel('Date').first().fill('2026-03-31')
  await page.getByLabel('Montant prévu').fill('25000000.00')
  await page.getByRole('button', { name: 'Ajouter' }).first().click()
  await expect(page.getByText('Élément ajouté.')).toBeVisible()

  await ouvrirOnglet(page, 'Validation et pièces')
  await page.getByLabel('Type de pièce').click()
  await page.getByTitle('Contrat signé').click()
  await page.locator('input[type=file]').setInputFiles({
    name: 'contrat.pdf',
    mimeType: 'application/pdf',
    buffer: Buffer.from('%PDF-1.4 contrat'),
  })
  await expect(page.getByText('Pièce déposée.')).toBeVisible()

  const creation = JSON.parse(envois.find((e) => e.chemin === '/api/v1/contrats')!.corps)
  expect(creation).toMatchObject({
    etablissementId: 'a1',
    type: 'MARCHE',
    numero: 'M-2026-001',
    fournisseurId: 'f1',
    dateSignature: '2026-01-05',
    montantInitialHt: '100000000.00',
    imputations: [{ ligneId: 'l1', montant: '100000000.00' }],
  })
  expect(envois.map((e) => e.chemin)).toContain('/api/v1/contrats/c1/echeances')
  expect(envois.find((e) => e.chemin === '/api/v1/contrats/c1/pieces')!.type).toContain(
    'multipart/form-data',
  )
})
