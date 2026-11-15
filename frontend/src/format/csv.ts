/**
 * Fichier CSV lisible par un tableur français : séparateur « ; », BOM UTF-8, champs entre
 * guillemets si besoin. Les montants restent des chaînes décimales exactes, telles que l'API.
 */
export function versCsv(entetes: string[], lignes: (string | number | null | undefined)[][]) {
  const champ = (v: string | number | null | undefined) => {
    const texte = v === null || v === undefined ? '' : String(v)
    return /[";\n\r]/.test(texte) ? `"${texte.replaceAll('"', '""')}"` : texte
  }
  return '﻿' + [entetes, ...lignes].map((l) => l.map(champ).join(';')).join('\r\n') + '\r\n'
}

export function telechargerCsv(nom: string, contenu: string) {
  const lien = document.createElement('a')
  lien.href = URL.createObjectURL(new Blob([contenu], { type: 'text/csv;charset=utf-8' }))
  lien.download = nom
  lien.click()
  URL.revokeObjectURL(lien.href)
}
