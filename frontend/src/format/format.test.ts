import { describe, expect, test } from 'vitest'
import { formaterDate, formaterMontant, formaterNombre } from './format'

// Espaces insécables d'Intl (couvertes par \s) ramenées à des espaces simples.
const simple = (texte: string) => texte.replace(/\s/g, ' ')

describe('formats selon la langue (I18N-05)', () => {
  test('montant en francs CFA avec le code de devise', () => {
    expect(simple(formaterMontant('45000000.00', 'fr'))).toBe('45 000 000 XOF')
    expect(simple(formaterMontant('45000000.00', 'en'))).toBe('XOF 45,000,000')
  })

  test('montant au-delà de 2^53 formaté sans perte', () => {
    expect(simple(formaterMontant('9999999999999999.99', 'fr'))).toBe(
      '9 999 999 999 999 999,99 XOF',
    )
  })

  test('nombres et dates', () => {
    expect(simple(formaterNombre(1234.5, 'fr'))).toBe('1 234,5')
    expect(formaterNombre(1234.5, 'en')).toBe('1,234.5')
    expect(formaterDate('2026-11-14T09:00:00Z', 'en')).toBe('Nov 14, 2026')
  })
})
