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

test('REC-03 : engagement lié au marché, crédits et plafond contrôlés', async ({ page }) => {
  const page1 = (donnees: unknown[]) => ({
    donnees,
    pagination: { page: 1, taille: 100, total: donnees.length, suivant: null },
  })
  const engagement = {
    id: 'e1',
    etablissementId: 'a1',
    exerciceId: 'x1',
    numero: 'ENG-2026-00002',
    dateEngagement: '2026-04-01',
    objet: 'Médicaments T2',
    origine: 'CONTRAT',
    montant: '30000000.00',
    montantAnnule: '0.00',
    contratId: 'c1',
    fournisseurId: 'f1',
    centreId: 'ce1',
    statut: 'BROUILLON',
    creeParCode: 'AG011',
    creeLe: '2026-04-01T10:00:00Z',
    version: 1,
    imputations: [{ id: 'i1', ligneId: 'l1', montant: '30000000.00', annule: '0.00' }],
  }
  const envois: { chemin: string; corps: string }[] = []
  await page.route('**/api/v1/**', async (route) => {
    const requete = route.request()
    const chemin = new URL(requete.url()).pathname
    if (requete.method() === 'POST') envois.push({ chemin, corps: requete.postData() ?? '' })
    if (chemin === '/api/v1/engagements/e1/soumissions') {
      await route.fulfill({
        status: 422,
        contentType: 'application/problem+json',
        body: JSON.stringify({ code: 'CONTROLE_BLOQUANT', status: 422, ecarts: [] }),
      })
      return
    }
    const reponses: Record<string, unknown> = {
      '/api/v1/auth/connexion': { jetonAcces: 'a', jetonRafraichissement: 'r', expireDans: 900 },
      '/api/v1/moi': { ...MOI, habilitations: [{ profil: 'GMC', etablissementId: 'a1' }] },
      '/api/v1/etablissements': page1([{ id: 'a1', code: 'CHU-A', nom: 'CHU A' }]),
      '/api/v1/contrats': page1([
        { id: 'c1', numero: 'M-2026-001', intitule: 'Fournitures médicales' },
      ]),
      '/api/v1/fournisseurs': page1([
        { id: 'f1', code: 'PHARMA', raisonSociale: 'Pharma Test SA' },
      ]),
      '/api/v1/centres-responsabilite': page1([
        { id: 'ce1', code: 'PHARMA', libelle: 'Pharmacie' },
      ]),
      '/api/v1/lignes-budgetaires': page1([{ id: 'l1', code: '604-CMD', libelle: 'Consommables' }]),
      '/api/v1/engagements': requete.method() === 'POST' ? engagement : page1([]),
      '/api/v1/engagements/e1': engagement,
      '/api/v1/engagements/e1/controles': [
        {
          code: 'CREDIT_INSUFFISANT',
          nature: 'CREDIT',
          depassement: '20000000.00',
          details: { ligne: '604-CMD', disponible: '10000000.00' },
          leve: false,
        },
        {
          code: 'PLAFOND_DEPASSE',
          nature: 'PLAFOND_CONTRAT',
          depassement: '10000000.00',
          details: { resteAEngager: '20000000.00' },
          leve: false,
        },
      ],
      '/api/v1/engagements/e1/derogations': [],
    }
    await route.fulfill({
      status: requete.method() === 'POST' ? 201 : 200,
      json: reponses[chemin] ?? page1([]),
    })
  })

  await page.goto('/connexion?retour=/engagements')
  await page.getByLabel('Identifiant').fill('agent')
  await page.getByLabel('Mot de passe').fill('secret')
  await page.getByRole('button', { name: 'Se connecter' }).click()
  await page.getByRole('button', { name: 'Demander un engagement' }).click()

  const tiroir = page.getByRole('dialog')
  const choisir = async (libelle: string, option: string) => {
    await tiroir.getByLabel(libelle, { exact: true }).click()
    await page.getByTitle(option).click()
  }
  await choisir('Établissement', 'CHU-A — CHU A')
  await choisir('Marché ou contrat', 'M-2026-001 — Fournitures médicales')
  await tiroir.getByLabel('Date', { exact: true }).fill('2026-04-01')
  await tiroir.getByLabel('Objet').fill('Médicaments T2')
  await tiroir.getByLabel('Montant', { exact: true }).first().fill('30000000.00')
  await choisir('Service demandeur', 'PHARMA — Pharmacie')
  await choisir('Bénéficiaire', 'PHARMA — Pharma Test SA')
  await choisir('Ligne budgétaire', '604-CMD — Consommables')
  await tiroir.getByLabel('Montant', { exact: true }).last().fill('30000000.00')
  await tiroir.getByRole('button', { name: 'Enregistrer' }).click()

  await expect(page.getByRole('heading', { name: 'ENG-2026-00002 — Médicaments T2' })).toBeVisible()
  await ouvrirOnglet(page, 'Contrôles')
  await expect(page.getByText('Crédit insuffisant')).toBeVisible()
  await expect(page.getByText('Plafond du marché dépassé')).toBeVisible()
  await page.getByRole('button', { name: 'Soumettre au circuit' }).click()
  await expect(page.getByText(/Un contrôle automatique a relevé un écart/)).toBeVisible()

  const creation = JSON.parse(envois.find((e) => e.chemin === '/api/v1/engagements')!.corps)
  expect(creation).toMatchObject({
    etablissementId: 'a1',
    origine: 'CONTRAT',
    contratId: 'c1',
    montant: '30000000.00',
    imputations: [{ ligneId: 'l1', montant: '30000000.00' }],
  })
})

test('REC-05 : livraison partielle enregistrée avec son procès-verbal', async ({ page }) => {
  const page1 = (donnees: unknown[]) => ({
    donnees,
    pagination: { page: 1, taille: 100, total: donnees.length, suivant: null },
  })
  const commande = {
    id: 'b1',
    etablissementId: 'a1',
    engagementId: 'e1',
    fournisseurId: 'f1',
    numero: 'BC-2026-00001',
    type: 'BON_COMMANDE',
    dateEmission: '2026-03-05',
    lieuLivraison: 'Pharmacie centrale',
    dateLivraisonPrevue: '2026-04-30',
    montantTtc: '10000000.00',
    enRetard: false,
    creeParCode: 'AG011',
    creeLe: '2026-03-05T10:00:00Z',
    lignes: [
      {
        id: 'lc1',
        rang: 1,
        designation: "Gants d'examen",
        quantite: '100.000',
        prixUnitaire: '100000.00',
        tauxTaxe: '0.00',
        montantTtc: '10000000.00',
        quantiteAcceptee: '0.000',
        resteARecevoir: '100.000',
      },
    ],
  }
  const reception = {
    id: 'r1',
    etablissementId: 'a1',
    bonCommandeId: 'b1',
    numero: 'REC-2026-00001',
    dateReception: '2026-04-10',
    type: 'PARTIELLE',
    centreId: 'ce1',
    agentResponsableCode: 'AG013',
    observations: null,
    statut: 'BROUILLON',
    creeParCode: 'AG013',
    creeLe: '2026-04-10T10:00:00Z',
    version: 1,
    lignes: [
      {
        ligneCommandeId: 'lc1',
        quantiteRecue: '40.000',
        quantiteAcceptee: '35.000',
        quantiteRejetee: '5.000',
      },
    ],
    reserves: [],
    attestation: null,
  }
  let receptions: unknown[] = []
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
    if (chemin === '/api/v1/bons-commande/b1/receptions' && requete.method() === 'POST') {
      receptions = [reception]
      await route.fulfill({ status: 201, json: reception })
      return
    }
    const reponses: Record<string, unknown> = {
      '/api/v1/auth/connexion': { jetonAcces: 'a', jetonRafraichissement: 'r', expireDans: 900 },
      '/api/v1/moi': { ...MOI, habilitations: [{ profil: 'REC', etablissementId: 'a1' }] },
      '/api/v1/centres-responsabilite': page1([
        { id: 'ce1', code: 'PHARMA', libelle: 'Pharmacie' },
      ]),
      '/api/v1/types-pieces': page1([{ id: 'pv', code: 'PV', libelle: 'Procès-verbal' }]),
      '/api/v1/bons-commande/b1': commande,
      '/api/v1/bons-commande/b1/receptions': receptions,
      '/api/v1/receptions/r1/validations': {
        statut: 'BROUILLON',
        separationTaches: true,
        etapes: [{ ordre: 1, libelle: 'Service fait', profil: 'VAL', obligatoire: true }],
        visas: [],
        etapesOuvertes: [],
        peutDecider: false,
      },
      '/api/v1/receptions/r1/pieces':
        requete.method() === 'POST'
          ? {
              id: 'p1',
              typePieceId: 'pv',
              nomFichier: 'pv.pdf',
              typeMime: 'application/pdf',
              taille: 10,
              empreinteSha256: 'b'.repeat(64),
              deposeParCode: 'AG013',
              deposeLe: '2026-04-10T10:00:00Z',
            }
          : [],
    }
    await route.fulfill({
      status: requete.method() === 'POST' ? 201 : 200,
      json: reponses[chemin] ?? page1([]),
    })
  })

  await page.goto('/connexion?retour=/bons-commande/b1')
  await page.getByLabel('Identifiant').fill('agent')
  await page.getByLabel('Mot de passe').fill('secret')
  await page.getByRole('button', { name: 'Se connecter' }).click()
  await page.getByRole('button', { name: 'Enregistrer une réception' }).click()

  const tiroir = page.getByRole('dialog')
  await tiroir.getByLabel('Date de réception').fill('2026-04-10')
  await tiroir.getByLabel('Service réceptionnaire').click()
  await page.getByTitle('PHARMA — Pharmacie').click()
  await tiroir.getByLabel('Code agent responsable').fill('AG013')
  await tiroir.getByLabel("Reçue — Gants d'examen").fill('40')
  await tiroir.getByLabel("Acceptée — Gants d'examen").fill('35')
  await tiroir.getByLabel("Rejetée — Gants d'examen").fill('5')
  await tiroir.getByRole('button', { name: 'Enregistrer' }).click()
  await expect(page.getByText('Réception enregistrée en brouillon.')).toBeVisible()

  await page.getByRole('button', { name: 'Détail' }).click()
  await page.getByLabel('Type de pièce').click()
  await page.getByTitle('Procès-verbal').click()
  await page.locator('input[type=file]').setInputFiles({
    name: 'pv.pdf',
    mimeType: 'application/pdf',
    buffer: Buffer.from('%PDF-1.4 pv'),
  })
  await expect(page.getByText('Pièce déposée.')).toBeVisible()

  const saisie = JSON.parse(
    envois.find((e) => e.chemin === '/api/v1/bons-commande/b1/receptions')!.corps,
  )
  expect(saisie).toMatchObject({
    dateReception: '2026-04-10',
    centreId: 'ce1',
    agentResponsableCode: 'AG013',
    lignes: [
      { ligneCommandeId: 'lc1', quantiteRecue: '40', quantiteAcceptee: '35', quantiteRejetee: '5' },
    ],
  })
  expect(envois.find((e) => e.chemin === '/api/v1/receptions/r1/pieces')!.type).toContain(
    'multipart/form-data',
  )
})

const FACTURE = {
  id: 'f1',
  etablissementId: 'a1',
  engagementId: 'e1',
  fournisseurId: 'fo1',
  bonCommandeId: null,
  factureOrigineId: null,
  numero: 'FA-778',
  type: 'PARTIELLE',
  objet: 'Livraison de mars',
  dateEmission: '2026-04-01',
  dateReception: '2026-04-03',
  dateEcheance: null,
  dateLimiteTraitement: null,
  periodeRattachement: null,
  montantHt: '6000000.00',
  montantTaxes: '0.00',
  montantTtc: '6000000.00',
  numeroDecompte: null,
  montantCumuleDecomptes: null,
  liquideValide: '0.00',
  resteAPayer: '6000000.00',
  statut: 'RECUE',
  motifStatut: null as string | null,
  motifLeveeDoublon: null,
  creeParCode: 'AG020',
  creeLe: '2026-04-03T10:00:00Z',
  version: 1,
}
const CIRCUIT_VIDE = {
  statut: 'BROUILLON',
  separationTaches: true,
  etapes: [],
  visas: [],
  etapesOuvertes: [],
  peutDecider: false,
}
const pageDe = (donnees: unknown[]) => ({
  donnees,
  pagination: { page: 1, taille: 100, total: donnees.length, suivant: null },
})

async function connecterAgentFinancier(page: Page, retour: string) {
  await page.goto(`/connexion?retour=${retour}`)
  await page.getByLabel('Identifiant').fill('agent')
  await page.getByLabel('Mot de passe').fill('secret')
  await page.getByRole('button', { name: 'Se connecter' }).click()
}

test('REC-06 : facture partielle enregistrée, contrôlée et liquidée', async ({ page }) => {
  let facture: typeof FACTURE | null = null
  let liquidations: unknown[] = []
  const envois: { chemin: string; corps: string; cle: string | null }[] = []
  const liquidation = {
    id: 'l1',
    factureId: 'f1',
    imputationId: 'i1',
    numero: 'LIQ-2026-00001',
    dateLiquidation: '2026-04-05',
    montantBase: '6000000.00',
    montantLiquide: '6000000.00',
    deductionsTotal: '300000.00',
    netAPayer: '5700000.00',
    consommationBudgetaire: '6000000.00',
    observations: null,
    statut: 'BROUILLON',
    receptionIds: [],
    deductions: [
      { type: 'RETENUE_GARANTIE', montant: '300000.00', taux: '5', motif: null, baseCalcul: null },
    ],
    creeParCode: 'AG020',
    creeLe: '2026-04-05T10:00:00Z',
    version: 1,
  }
  await page.route('**/api/v1/**', async (route) => {
    const requete = route.request()
    const chemin = new URL(requete.url()).pathname
    const methode = requete.method()
    if (methode === 'POST') {
      envois.push({
        chemin,
        corps: requete.postData() ?? '',
        cle: await requete.headerValue('idempotency-key'),
      })
    }
    if (chemin === '/api/v1/factures' && methode === 'POST') {
      facture = FACTURE
      await route.fulfill({ status: 201, json: facture })
      return
    }
    if (chemin === '/api/v1/factures/f1/liquidations' && methode === 'POST') {
      liquidations = [liquidation]
      facture = { ...FACTURE, statut: 'EN_CONTROLE' }
      await route.fulfill({ status: 201, json: liquidation })
      return
    }
    if (chemin === '/api/v1/liquidations/l1/soumissions') {
      liquidations = [{ ...liquidation, statut: 'SOUMIS' }]
      await route.fulfill({ status: 201, json: { ...CIRCUIT_VIDE, statut: 'SOUMIS' } })
      return
    }
    const reponses: Record<string, unknown> = {
      '/api/v1/auth/connexion': { jetonAcces: 'a', jetonRafraichissement: 'r', expireDans: 900 },
      '/api/v1/moi': { ...MOI, habilitations: [{ profil: 'AF', etablissementId: 'a1' }] },
      '/api/v1/engagements': pageDe([{ id: 'e1', numero: 'ENG-2026-00001', objet: 'Médicaments' }]),
      '/api/v1/engagements/e1': {
        id: 'e1',
        imputations: [{ id: 'i1', ligneId: 'lb1', montant: '9000000.00', annule: '0.00' }],
      },
      '/api/v1/lignes-budgetaires': pageDe([{ id: 'lb1', code: '6011', libelle: 'Médicaments' }]),
      '/api/v1/factures': pageDe(facture ? [facture] : []),
      '/api/v1/factures/f1': facture,
      '/api/v1/factures/f1/liquidations': liquidations,
      '/api/v1/liquidations/l1/controles': [],
      '/api/v1/liquidations/l1/validations': CIRCUIT_VIDE,
      '/api/v1/liquidations/l1/pieces': [],
    }
    await route.fulfill({ json: reponses[chemin] ?? pageDe([]) })
  })

  await connecterAgentFinancier(page, '/factures')
  await page.getByRole('button', { name: 'Enregistrer une facture' }).click()
  const tiroir = page.getByRole('dialog')
  await tiroir.getByLabel('Engagement').click()
  await page.getByTitle('ENG-2026-00001 — Médicaments').click()
  await tiroir.getByLabel('Numéro du fournisseur').fill('FA-778')
  await tiroir.getByLabel('Objet').fill('Livraison de mars')
  await tiroir.getByLabel('Émise le').fill('2026-04-01')
  await tiroir.getByLabel('Reçue le').fill('2026-04-03')
  await tiroir.getByLabel('Montant HT').fill('6000000')
  await tiroir.getByLabel('Montant TTC').fill('6000000')
  await tiroir.getByRole('button', { name: 'Enregistrer' }).click()
  await expect(page.getByText('Facture enregistrée.')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'FA-778 — Livraison de mars' })).toBeVisible()

  await ouvrirOnglet(page, 'Liquidations')
  await page.getByRole('button', { name: 'Liquider' }).click()
  const saisie = page.getByRole('dialog')
  // Une seule imputation : proposée d'office, libellée par sa ligne budgétaire.
  await expect(saisie.getByText('6011 — Médicaments')).toBeVisible()
  await saisie.getByLabel('Date', { exact: true }).fill('2026-04-05')
  await saisie.getByRole('button', { name: 'Ajouter une déduction' }).click()
  await saisie.getByLabel('Taux (%)').fill('5')
  await saisie.getByRole('button', { name: 'Enregistrer' }).click()
  await expect(page.getByText('Liquidation enregistrée en brouillon.')).toBeVisible()

  // Montants de la formule 6.3 et contrôles, puis soumission au circuit.
  const detail = page.getByRole('dialog', { name: 'LIQ-2026-00001' })
  await expect(detail.getByText('Aucun écart.')).toBeVisible()
  await expect(detail.getByText('Net à payer')).toBeVisible()
  await detail.getByRole('button', { name: 'Soumettre au circuit' }).click()
  await expect(page.getByText('Liquidation soumise.')).toBeVisible()

  const facturee = JSON.parse(envois.find((e) => e.chemin === '/api/v1/factures')!.corps)
  expect(facturee).toMatchObject({
    engagementId: 'e1',
    type: 'PARTIELLE',
    numero: 'FA-778',
    montantHt: '6000000',
    montantTtc: '6000000',
  })
  const liquidee = envois.find((e) => e.chemin === '/api/v1/factures/f1/liquidations')!
  expect(liquidee.cle).toBeTruthy()
  expect(JSON.parse(liquidee.corps)).toMatchObject({
    imputationId: 'i1',
    dateLiquidation: '2026-04-05',
    montantBase: '6000000.00',
    deductions: [{ type: 'RETENUE_GARANTIE', montant: null, taux: '5' }],
  })
})

test('REC-12 : facture retournée, corrigée puis rejetée avec motif', async ({ page }) => {
  let facture = { ...FACTURE }
  const ecritures: { chemin: string; methode: string; corps: string; version: string | null }[] = []
  await page.route('**/api/v1/**', async (route) => {
    const requete = route.request()
    const chemin = new URL(requete.url()).pathname
    const methode = requete.method()
    if (methode !== 'GET' && chemin.startsWith('/api/v1/factures')) {
      ecritures.push({
        chemin,
        methode,
        corps: requete.postData() ?? '',
        version: await requete.headerValue('if-match'),
      })
    }
    if (chemin === '/api/v1/factures/f1/retours') {
      facture = { ...facture, statut: 'RETOURNEE', motifStatut: 'Numéro illisible' }
      await route.fulfill({ status: 201, json: facture })
      return
    }
    if (chemin === '/api/v1/factures/f1' && methode === 'PATCH') {
      facture = { ...facture, numero: 'FA-779', statut: 'RECUE', version: 2 }
      await route.fulfill({ json: facture })
      return
    }
    if (chemin === '/api/v1/factures/f1/rejets') {
      facture = { ...facture, statut: 'REJETEE', motifStatut: 'Prix non conformes' }
      await route.fulfill({ status: 201, json: facture })
      return
    }
    const reponses: Record<string, unknown> = {
      '/api/v1/auth/connexion': { jetonAcces: 'a', jetonRafraichissement: 'r', expireDans: 900 },
      '/api/v1/moi': { ...MOI, habilitations: [{ profil: 'AF', etablissementId: 'a1' }] },
      '/api/v1/factures/f1': facture,
    }
    await route.fulfill({ json: reponses[chemin] ?? pageDe([]) })
  })

  await connecterAgentFinancier(page, '/factures/f1')
  await page.getByRole('button', { name: 'Retourner pour correction' }).click()
  await page.getByRole('dialog').getByLabel('Motif').fill('Numéro illisible')
  await page.getByRole('dialog').getByRole('button', { name: 'Enregistrer' }).click()
  await expect(page.getByText('Facture retournée.')).toBeVisible()
  await expect(page.getByText('Retournée', { exact: true })).toBeVisible()

  await page.getByRole('button', { name: 'Corriger' }).click()
  const tiroir = page.getByRole('dialog')
  await tiroir.getByLabel('Numéro du fournisseur').fill('FA-779')
  await tiroir.getByRole('button', { name: 'Enregistrer' }).click()
  await expect(page.getByText('Facture corrigée.')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'FA-779 — Livraison de mars' })).toBeVisible()

  await page.getByRole('button', { name: 'Rejeter' }).click()
  await page.getByRole('dialog').getByLabel('Motif').fill('Prix non conformes')
  await page.getByRole('dialog').getByRole('button', { name: 'Enregistrer' }).click()
  await expect(page.getByText('Facture rejetée.')).toBeVisible()
  await expect(page.getByText('Rejetée', { exact: true })).toBeVisible()
  // Facture rejetée : plus aucune action de traitement.
  await expect(page.getByRole('button', { name: 'Rejeter' })).toHaveCount(0)

  expect(ecritures.map((e) => `${e.methode} ${e.chemin}`)).toEqual([
    'POST /api/v1/factures/f1/retours',
    'PATCH /api/v1/factures/f1',
    'POST /api/v1/factures/f1/rejets',
  ])
  expect(ecritures[1].version).toBe('"1"')
  expect(JSON.parse(ecritures[1].corps)).toMatchObject({ numero: 'FA-779' })
  expect(JSON.parse(ecritures[2].corps)).toEqual({ motif: 'Prix non conformes' })
})

/**
 * API simulée du lot 5 : liquidations à ordonnancer puis à payer, ordonnancement et paiements,
 * avec leur état (statuts, payé) mis à jour à chaque écriture, comme le serveur.
 */
async function simulerPaiements(page: Page, nets: Record<string, string>) {
  const liquidations = Object.entries(nets).map(([n, net], i) => ({
    id: `l${i + 1}`,
    numero: `LIQ-2026-0000${i + 1}`,
    factureId: `f${i + 1}`,
    factureNumero: n,
    fournisseurId: 'fo1',
    netAPayer: net,
    paye: '0.00',
    resteAPayer: net,
    ordonnancementId: null as string | null,
  }))
  let ordonnancement: Record<string, unknown> | null = null
  const paiements: Record<string, unknown>[] = []
  const envois: { chemin: string; corps: Record<string, unknown> }[] = []
  const centimes = (m: string) => Math.round(Number(m) * 100)
  await page.route('**/api/v1/**', async (route) => {
    const requete = route.request()
    const url = new URL(requete.url())
    const chemin = url.pathname
    const corps = requete.postData() ? JSON.parse(requete.postData()!) : {}
    if (requete.method() === 'POST' && !chemin.startsWith('/api/v1/auth')) {
      envois.push({ chemin, corps })
    }
    if (chemin === '/api/v1/ordonnancements' && requete.method() === 'POST') {
      ordonnancement = {
        id: 'o1',
        etablissementId: 'a1',
        referencePiece: corps.referencePiece,
        typePiece: corps.typePiece,
        serviceDestinataire: corps.serviceDestinataire,
        dateTransmission: null,
        statut: 'PREPARE',
        motifStatut: null,
        montant: '0.00',
        lignes: liquidations
          .filter((lq) => corps.liquidationIds.includes(lq.id))
          .map((lq) => ({
            liquidationId: lq.id,
            liquidationNumero: lq.numero,
            factureId: lq.factureId,
            factureNumero: lq.factureNumero,
            montant: lq.netAPayer,
          })),
        creeParCode: 'AG030',
        creeLe: '2026-05-01T10:00:00Z',
        version: 1,
      }
      for (const lq of liquidations) {
        if (corps.liquidationIds.includes(lq.id)) lq.ordonnancementId = 'o1'
      }
      await route.fulfill({ status: 201, json: ordonnancement })
      return
    }
    if (chemin === '/api/v1/ordonnancements/o1/decisions') {
      const statuts: Record<string, string> = {
        TRANSMETTRE: 'TRANSMIS',
        PRENDRE_EN_CHARGE: 'PRIS_EN_CHARGE',
      }
      ordonnancement = {
        ...ordonnancement,
        statut: statuts[corps.action],
        dateTransmission: '2026-05-02',
      }
      await route.fulfill({ status: 201, json: ordonnancement })
      return
    }
    if (chemin === '/api/v1/paiements' && requete.method() === 'POST') {
      const paiement = {
        id: `p${paiements.length + 1}`,
        numero: `PAI-2026-0000${paiements.length + 1}`,
        datePaiement: corps.datePaiement,
        montant: corps.montant,
        statut: 'EXECUTE',
        allocations: corps.allocations.map((a: { liquidationId: string; montant: string }) => {
          const lq = liquidations.find((l) => l.id === a.liquidationId)!
          const paye = centimes(lq.paye) + centimes(a.montant)
          lq.paye = (paye / 100).toFixed(2)
          lq.resteAPayer = ((centimes(lq.netAPayer) - paye) / 100).toFixed(2)
          return { ...a, factureId: lq.factureId, factureNumero: lq.factureNumero }
        }),
      }
      paiements.unshift(paiement)
      await route.fulfill({ status: 201, json: paiement })
      return
    }
    const etape = url.searchParams.get('etape')
    const reponses: Record<string, unknown> = {
      '/api/v1/auth/connexion': { jetonAcces: 'a', jetonRafraichissement: 'r', expireDans: 900 },
      '/api/v1/moi': {
        ...MOI,
        habilitations: [
          { profil: 'ORD', etablissementId: 'a1' },
          { profil: 'CPT', etablissementId: 'a1' },
        ],
      },
      '/api/v1/fournisseurs': pageDe([{ id: 'fo1', code: 'F01', raisonSociale: 'Medipharm' }]),
      '/api/v1/modes-reglement': pageDe([{ id: 'vir', code: 'VIR', libelle: 'Virement' }]),
      '/api/v1/comptes-tresorerie': pageDe([{ id: 'bq', code: 'BQ1', libelle: 'Banque' }]),
      '/api/v1/ordonnancements': pageDe(ordonnancement ? [ordonnancement] : []),
      '/api/v1/paiements': pageDe(paiements),
      '/api/v1/liquidations': liquidations.filter((lq) =>
        etape === 'A_ORDONNANCER'
          ? lq.ordonnancementId === null
          : ordonnancement?.statut === 'PRIS_EN_CHARGE' &&
            lq.ordonnancementId &&
            lq.resteAPayer !== '0.00',
      ),
    }
    await route.fulfill({ json: reponses[chemin] ?? pageDe([]) })
  })
  return envois
}

async function ordonnancerEtPrendreEnCharge(page: Page, factures: string[]) {
  await page.getByRole('button', { name: 'Préparer un ordonnancement' }).click()
  const tiroir = page.getByRole('dialog')
  await tiroir.getByLabel('Référence du mandat').fill('MD-2026-014')
  await tiroir.getByLabel('Service destinataire').fill('Agence comptable')
  for (const facture of factures) {
    await tiroir.getByRole('checkbox', { name: new RegExp(facture) }).check()
  }
  await tiroir.getByRole('button', { name: 'Enregistrer' }).click()
  await expect(page.getByText('Ordonnancement préparé.')).toBeVisible()
  await page.getByRole('button', { name: 'Détail' }).click()
  await page.getByRole('button', { name: 'Transmettre au comptable' }).click()
  await expect(page.getByRole('dialog').getByText('Transmis', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Prendre en charge' }).click()
  await expect(page.getByRole('dialog').getByText('Pris en charge', { exact: true })).toBeVisible()
  await page
    .getByRole('dialog')
    .getByRole('button', { name: /close|fermer/i })
    .click()
}

async function payer(page: Page, parts: Record<string, string>) {
  await page.getByRole('button', { name: 'Enregistrer un paiement' }).click()
  const tiroir = page.getByRole('dialog')
  await tiroir.getByLabel('Bénéficiaire').click()
  await page.getByTitle('F01 — Medipharm').click()
  await tiroir.getByLabel('Date du paiement').fill('2026-05-10')
  await tiroir.getByLabel('Mode de règlement').click()
  await page.getByTitle('VIR — Virement').click()
  await tiroir.getByLabel('Compte de trésorerie').click()
  await page.getByTitle('BQ1 — Banque').click()
  for (const [liquidation, montant] of Object.entries(parts)) {
    await tiroir.getByLabel(`Part payée — ${liquidation}`).fill(montant)
  }
  await tiroir.getByRole('button', { name: 'Enregistrer' }).click()
  // Deux paiements rapprochés laissent deux messages à l'écran : le tiroir fermé fait foi.
  await expect(page.getByText('Paiement enregistré.').first()).toBeVisible()
  await expect(page.getByRole('dialog')).toHaveCount(0)
}

test('REC-08 et REC-09 : ordonnancer, payer en partie, puis solder', async ({ page }) => {
  const envois = await simulerPaiements(page, { 'FA-778': '6000000.00' })
  await connecterAgentFinancier(page, '/paiements')
  await ordonnancerEtPrendreEnCharge(page, ['FA-778'])

  await ouvrirOnglet(page, 'Paiements')
  await payer(page, { 'LIQ-2026-00001': '2000000' })
  // REC-09 : le second paiement part du solde restant, recalculé.
  await page.getByRole('button', { name: 'Enregistrer un paiement' }).click()
  const tiroir = page.getByRole('dialog')
  await tiroir.getByLabel('Bénéficiaire').click()
  await page.getByTitle('F01 — Medipharm').click()
  await expect(tiroir.getByRole('cell', { name: /4\s?000\s?000/ })).toBeVisible()
  await tiroir.getByRole('button', { name: /close|fermer/i }).click()
  await payer(page, { 'LIQ-2026-00001': '4000000' })
  await expect(page.getByText('PAI-2026-00002')).toBeVisible()

  const paiementsEnvoyes = envois.filter((e) => e.chemin === '/api/v1/paiements')
  expect(paiementsEnvoyes.map((e) => e.corps.montant)).toEqual(['2000000.00', '4000000.00'])
  expect(envois.find((e) => e.chemin === '/api/v1/ordonnancements')!.corps).toMatchObject({
    referencePiece: 'MD-2026-014',
    typePiece: 'MANDAT',
    liquidationIds: ['l1'],
  })
  expect(envois.filter((e) => e.chemin.endsWith('/decisions')).map((e) => e.corps.action)).toEqual([
    'TRANSMETTRE',
    'PRENDRE_EN_CHARGE',
  ])
})

test('REC-10 : paiement groupé ventilé facture par facture', async ({ page }) => {
  const envois = await simulerPaiements(page, { 'FA-778': '6000000.00', 'FA-779': '4000000.00' })
  await connecterAgentFinancier(page, '/paiements')
  await ordonnancerEtPrendreEnCharge(page, ['FA-778', 'FA-779'])

  await ouvrirOnglet(page, 'Paiements')
  await payer(page, { 'LIQ-2026-00001': '6000000', 'LIQ-2026-00002': '1500000.50' })
  const ligne = page.getByRole('row', { name: /PAI-2026-00001/ })
  await expect(ligne.getByRole('link', { name: 'FA-778' })).toBeVisible()
  await expect(ligne.getByRole('link', { name: 'FA-779' })).toBeVisible()

  const paiement = envois.find((e) => e.chemin === '/api/v1/paiements')!.corps
  expect(paiement).toMatchObject({
    montant: '7500000.50',
    allocations: [
      { liquidationId: 'l1', montant: '6000000' },
      { liquidationId: 'l2', montant: '1500000.50' },
    ],
  })
})
