import { theme as themeAntd, type ThemeConfig } from 'antd'

/**
 * Seul endroit où les couleurs sont définies (IHM-03). Les composants utilisent les jetons
 * du thème, jamais une couleur en dur.
 */
export function creerTheme(mouvementReduit: boolean): ThemeConfig {
  return {
    algorithm: themeAntd.compactAlgorithm,
    token: {
      colorPrimary: '#1E40AF',
      colorInfo: '#1E40AF',
      colorSuccess: '#059669',
      colorWarning: '#B45309',
      colorError: '#DC2626',
      colorBgLayout: '#F8FAFC',
      colorBgContainer: '#FFFFFF',
      colorText: '#020617',
      colorTextSecondary: '#475569',
      // Textes dérivés (descriptions, fil d'Ariane, tableaux vides, indications) : contraste
      // d'au moins 4,5:1 sur fond blanc (IHM-07), là où les valeurs d'Ant Design restent en deçà.
      colorTextTertiary: '#475569',
      colorTextDescription: '#475569',
      colorTextPlaceholder: '#64748B',
      // Textes « vides » (tableau ou liste sans élément) : lisibles eux aussi.
      colorTextQuaternary: '#64748B',
      colorTextDisabled: '#64748B',
      // Texte des statuts sur leur fond pâle (BadgeStatut) : nuances foncées de la palette.
      colorSuccessText: '#047857',
      colorWarningText: '#92400E',
      colorErrorText: '#B91C1C',
      colorInfoText: '#1E40AF',
      colorBorder: '#E2E8F0',
      fontFamily: "'Source Sans 3', system-ui, sans-serif",
      fontSize: 14,
      borderRadius: 6,
      // Préférence « mouvement réduit » du système : animations coupées (IHM-11, T-074).
      motion: !mouvementReduit,
    },
    components: {
      // Étiquettes de statut : texte foncé sur fond pâle, contraste d'au moins 4,5:1 (IHM-07).
      Tag: {
        colorSuccess: '#065F46',
        colorWarning: '#92400E',
        colorError: '#B91C1C',
        colorInfo: '#1E40AF',
      },
      Input: { inputFontSize: 16 },
      InputNumber: { inputFontSize: 16 },
      Select: { fontSize: 16 },
    },
  }
}
