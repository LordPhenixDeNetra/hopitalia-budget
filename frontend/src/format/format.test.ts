import { describe, expect, test } from 'vitest'
import { additionnerMontants, formaterDate, formaterMontant, formaterNombre } from './format'

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

describe('somme exacte des montants saisis (ventilation d’un paiement)', () => {
  test('en centimes entiers, sans perte au-delà de 2^53', () => {
    expect(additionnerMontants(['0.1', '0.2'])).toBe('0.30')
    expect(additionnerMontants(['9007199254740993.01', '1'])).toBe('9007199254740994.01')
    expect(additionnerMontants(['6000000', '', null, 'abc', '1.5'])).toBe('6000001.50')
    expect(additionnerMontants(['-2.05', '1'])).toBe('-1.05')
    expect(additionnerMontants([])).toBe('0.00')
  })
})
