import i18n from 'i18next'
import resourcesToBackend from 'i18next-resources-to-backend'
import { initReactI18next } from 'react-i18next'
import { LANGUES, langueInitiale } from './langue'

// Un fichier JSON par langue et par domaine, chargé à la demande (I18N-03).
void i18n
  .use(
    resourcesToBackend(
      (langue: string, domaine: string) => import(`./locales/${langue}/${domaine}.json`),
    ),
  )
  .use(initReactI18next)
  .init({
    lng: langueInitiale(),
    fallbackLng: 'fr',
    supportedLngs: [...LANGUES],
    ns: ['commun', 'erreurs'],
    defaultNS: 'commun',
    interpolation: { escapeValue: false },
    // En développement et en test, une clé manquante est signalée dans la console.
    saveMissing: import.meta.env.DEV,
    missingKeyHandler: (langues, domaine, cle) =>
      console.error(`Traduction manquante : ${domaine}:${cle} (${langues.join(', ')})`),
  })

export default i18n
