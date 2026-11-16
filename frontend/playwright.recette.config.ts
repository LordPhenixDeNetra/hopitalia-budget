import { defineConfig, devices } from '@playwright/test'

// Recette blanche (docs/recette/recette-blanche.md) : l'interface de la pile de simulation, servie
// par nginx, avec l'API réelle et l'Hopitalia simulé ; rien n'est simulé dans le navigateur.
// Lancer après `simulation/recette_blanche.py` : npx playwright test -c playwright.recette.config.ts
export default defineConfig({
  testDir: 'e2e-recette',
  reporter: [['list'], ['html', { outputFolder: 'playwright-report-recette', open: 'never' }]],
  use: { baseURL: 'http://127.0.0.1:8080', locale: 'fr-FR', screenshot: 'on' },
  projects: [{ name: 'ordinateur', use: { ...devices['Desktop Chrome'] } }],
})
