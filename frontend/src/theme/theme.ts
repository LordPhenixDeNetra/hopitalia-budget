import { theme as themeAntd, type ThemeConfig } from 'antd'

export interface OptionsTheme {
  /** Thème sombre (IHM-01, T-270). */
  sombre?: boolean
  /** Densité compacte, par défaut (IHM-02) ; sinon confortable (T-271). */
  compacte?: boolean
}

/** Palette claire (IHM-03) ; textes dérivés et statuts foncés pour 4,5:1 sur blanc (IHM-07). */
const CLAIR = {
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
  },
  menu: {},
  // Étiquettes de statut : texte foncé sur fond pâle, contraste d'au moins 4,5:1 (IHM-07).
  tag: {
    colorSuccess: '#065F46',
    colorWarning: '#92400E',
    colorError: '#B91C1C',
    colorInfo: '#1E40AF',
  },
}

/**
 * Palette sombre (T-270) : fonds ardoise, textes clairs, couleurs de la palette éclaircies. Tous
 * les textes atteignent 4,5:1 sur les trois fonds (page, carte, menu déroulant). Sur un bouton
 * plein, le texte est foncé : le blanc n'atteint pas 4,5:1 sur une couleur assez claire pour être
 * lisible comme texte sur fond sombre.
 */
const SOMBRE = {
  token: {
    colorPrimary: '#60A5FA',
    colorInfo: '#60A5FA',
    colorSuccess: '#34D399',
    colorWarning: '#FBBF24',
    colorError: '#F87171',
    colorLink: '#93C5FD',
    colorBgLayout: '#020617',
    colorBgContainer: '#0F172A',
    colorBgElevated: '#1E293B',
    colorText: '#F1F5F9',
    colorTextSecondary: '#CBD5E1',
    colorTextTertiary: '#CBD5E1',
    colorTextDescription: '#CBD5E1',
    colorTextPlaceholder: '#94A3B8',
    colorTextQuaternary: '#94A3B8',
    colorTextDisabled: '#94A3B8',
    colorTextLightSolid: '#020617',
    colorSuccessText: '#34D399',
    colorWarningText: '#FBBF24',
    colorErrorText: '#F87171',
    colorInfoText: '#60A5FA',
    colorBorder: '#334155',
  },
  // Élément de menu sélectionné : texte clair sur bleu foncé (le bleu clair sur son fond pâle
  // dérivé n'atteint pas 4,5:1).
  menu: { itemSelectedBg: '#1E3A8A', itemSelectedColor: '#F1F5F9' },
  tag: {
    colorSuccess: '#34D399',
    colorWarning: '#FBBF24',
    colorError: '#F87171',
    colorInfo: '#93C5FD',
  },
}

/**
 * Seul endroit où les couleurs sont définies (IHM-03). Les composants utilisent les jetons
 * du thème, jamais une couleur en dur.
 */
export function creerTheme(mouvementReduit: boolean, options: OptionsTheme = {}): ThemeConfig {
  const { sombre = false, compacte = true } = options
  const palette = sombre ? SOMBRE : CLAIR
  return {
    algorithm: [
      sombre ? themeAntd.darkAlgorithm : themeAntd.defaultAlgorithm,
      ...(compacte ? [themeAntd.compactAlgorithm] : []),
    ],
    token: {
      ...palette.token,
      fontFamily: "'Source Sans 3', system-ui, sans-serif",
      fontSize: 14,
      borderRadius: 6,
      // Préférence « mouvement réduit » du système : animations coupées (IHM-11, T-074).
      motion: !mouvementReduit,
    },
    components: {
      Tag: palette.tag,
      Menu: palette.menu,
      Input: { inputFontSize: 16 },
      InputNumber: { inputFontSize: 16 },
      Select: { fontSize: 16 },
    },
  }
}
