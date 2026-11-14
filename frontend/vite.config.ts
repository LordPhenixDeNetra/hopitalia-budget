/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  // En développement, l'API FastAPI tourne à part (README) : même origine pour le navigateur.
  server: { proxy: { '/api': 'http://127.0.0.1:8000' } },
  test: {
    environment: 'jsdom',
    setupFiles: ['src/test/preparation.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
  },
})
