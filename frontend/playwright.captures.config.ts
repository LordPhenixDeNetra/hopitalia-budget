import { defineConfig, devices } from '@playwright/test'

// Captures d'écran de la documentation (site/) : l'interface de l'environnement de démonstration,
// servie par nginx, avec l'API réelle et l'Hopitalia simulé (docs : installer/demonstration).
// Lancer après `simulation/demonstration.py` : npx playwright test -c playwright.captures.config.ts
export default defineConfig({
  testDir: 'e2e-captures',
  workers: 1,
  reporter: 'list',
  use: {
    baseURL: 'http://127.0.0.1:8080',
    locale: 'fr-FR',
    ...devices['Desktop Chrome'],
    viewport: { width: 1440, height: 900 },
  },
})
