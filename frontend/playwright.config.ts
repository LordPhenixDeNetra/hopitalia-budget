import { defineConfig, devices } from '@playwright/test'

// Parcours de bout en bout sur l'application construite ; l'API est simulée par interception.
export default defineConfig({
  testDir: 'e2e',
  reporter: process.env.CI ? 'github' : 'list',
  use: { baseURL: 'http://127.0.0.1:4173', locale: 'fr-FR' },
  webServer: {
    command: 'npm run build && npx vite preview --host 127.0.0.1 --port 4173 --strictPort',
    url: 'http://127.0.0.1:4173',
    reuseExistingServer: !process.env.CI,
  },
  projects: [
    { name: 'ordinateur', use: { ...devices['Desktop Chrome'] } },
    // Largeur minimale cible (IHM-08) : 375 px.
    { name: 'telephone', use: { ...devices['Pixel 7'], viewport: { width: 375, height: 740 } } },
  ],
})
