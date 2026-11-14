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
      colorBorder: '#E2E8F0',
      fontFamily: "'Source Sans 3', system-ui, sans-serif",
      fontSize: 14,
      borderRadius: 6,
      // Préférence « mouvement réduit » du système : animations coupées (IHM-11, T-074).
      motion: !mouvementReduit,
    },
    components: {
      Input: { inputFontSize: 16 },
      InputNumber: { inputFontSize: 16 },
      Select: { fontSize: 16 },
    },
  }
}
