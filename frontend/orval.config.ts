import { defineConfig } from 'orval'

// Client d'API généré depuis l'OpenAPI du backend (T-066). Régénérer avec : npm run api
export default defineConfig({
  budget: {
    input: './openapi.json',
    output: {
      mode: 'split',
      target: 'src/api/genere/budget.ts',
      client: 'react-query',
      httpClient: 'fetch',
      clean: true,
      override: {
        mutator: { path: 'src/api/client.ts', name: 'appelerApi' },
        fetch: { includeHttpResponseReturnType: false },
      },
    },
  },
})
