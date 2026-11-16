import { afterEach, describe, expect, test } from 'vitest'
import { langueInitiale, memoriserLangue } from './langue'

const fichiers = import.meta.glob<{ default: object }>('./locales/*/*.json', { eager: true })

function cles(objet: object, prefixe = ''): string[] {
  return Object.entries(objet).flatMap(([cle, valeur]) =>
    typeof valeur === 'object' && valeur !== null
      ? cles(valeur as object, `${prefixe}${cle}.`)
      : [`${prefixe}${cle}`],
  )
}

const domaines = Object.keys(fichiers)
  .filter((chemin) => chemin.startsWith('./locales/fr/'))
  .map((chemin) => chemin.replace('./locales/fr/', ''))

describe('fichiers de traduction (I18N-03)', () => {
  test.each(domaines)('%s : mêmes clés en français et en anglais', (domaine) => {
    const francais = cles(fichiers[`./locales/fr/${domaine}`].default)
    const anglais = cles(fichiers[`./locales/en/${domaine}`]?.default ?? {})
    expect(anglais.sort()).toEqual(francais.sort())
  })
})

// Accents ou mots outils du français : signe d'un texte laissé non traduit.
const FRANCAIS = /[àâçéèêëîïôûùüÿœ]|\b(le|la|les|des|du|une|est|pour|avec|aux|sur|et)\b/i
// Seule exception : le nom de chaque langue s'écrit dans cette langue.
const EXCEPTIONS = new Set(['commun.json:langues.fr'])

function valeurs(objet: object, prefixe = ''): [string, string][] {
  return Object.entries(objet).flatMap(([cle, valeur]) =>
    typeof valeur === 'object' && valeur !== null
      ? valeurs(valeur as object, `${prefixe}${cle}.`)
      : [[`${prefixe}${cle}`, String(valeur)] as [string, string]],
  )
}

describe('traduction anglaise complète (T-272, I18N-01)', () => {
  test.each(domaines)('%s : aucun texte anglais vide ou resté en français', (domaine) => {
    const defauts = valeurs(fichiers[`./locales/en/${domaine}`].default).filter(
      ([cle, texte]) =>
        !EXCEPTIONS.has(`${domaine}:${cle}`) && (texte.trim() === '' || FRANCAIS.test(texte)),
    )
    expect(defauts).toEqual([])
  })
})

describe('choix de la langue avant connexion (I18N-04)', () => {
  afterEach(() => localStorage.clear())

  test('langue du navigateur, sinon français', () => {
    expect(langueInitiale(['en-GB', 'fr'])).toBe('en')
    expect(langueInitiale(['wo-SN', 'de'])).toBe('fr')
  })

  test('le dernier choix mémorisé prime sur le navigateur', () => {
    memoriserLangue('en')
    expect(langueInitiale(['fr-FR'])).toBe('en')
  })
})
