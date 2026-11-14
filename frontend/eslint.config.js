import js from '@eslint/js'
import prettier from 'eslint-config-prettier'
import i18next from 'eslint-plugin-i18next'
import jsxA11y from 'eslint-plugin-jsx-a11y'
import reactHooks from 'eslint-plugin-react-hooks'
import globals from 'globals'
import tseslint from 'typescript-eslint'

export default tseslint.config(
  { ignores: ['dist', 'coverage', 'src/api/genere', 'playwright-report', 'test-results'] },
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      ...tseslint.configs.recommended,
      jsxA11y.flatConfigs.recommended,
    ],
    languageOptions: { globals: globals.browser },
    plugins: { 'react-hooks': reactHooks },
    rules: {
      'react-hooks/rules-of-hooks': 'error',
      'react-hooks/exhaustive-deps': 'warn',
    },
  },
  {
    // Aucun texte en dur dans les composants : tout passe par une clé de traduction (I18N-02).
    files: ['src/**/*.tsx'],
    ignores: ['src/**/*.test.tsx'],
    plugins: { i18next },
    rules: {
      'i18next/no-literal-string': [
        'error',
        {
          mode: 'jsx-only',
          // Attributs qui portent un texte lu par l'utilisateur ; les autres sont techniques.
          'jsx-attributes': {
            include: ['aria-label', 'title', 'placeholder', 'alt', 'label', 'extra', 'subTitle'],
          },
          callees: { exclude: ['t', 'tCommun', 'tErreur', 'i18n.t'] },
        },
      ],
    },
  },
  prettier,
)
