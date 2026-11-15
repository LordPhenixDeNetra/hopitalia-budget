import { Flex, theme, Typography } from 'antd'
import { useTranslation } from 'react-i18next'
import { BadgeStatut, type Ton } from './BadgeStatut'

// Échelle de la barre : un peu au-delà de 100 % pour que le repère 100 % reste visible.
const ECHELLE = 110
const REPERES = [80, 90, 100]

/** Seuil franchi par un taux de consommation (IHM-10) : libellé et ton, pas la seule couleur. */
export function seuil(taux: number | null): [Ton, string] {
  if (taux === null) return ['neutre', 'jauge.sansBase']
  if (taux >= 100) return ['erreur', 'jauge.seuil100']
  if (taux >= 90) return ['attention', 'jauge.seuil90']
  if (taux >= 80) return ['attention', 'jauge.seuil80']
  return ['succes', 'jauge.normal']
}

/**
 * Jauge linéaire (« bullet chart », IHM-10) : barre du taux, repères à 80, 90 et 100 %, taux en
 * texte et seuil écrit en clair. Le tableau équivalent est affiché par la page qui l'utilise.
 */
export function Jauge({ libelle, taux }: { libelle: string; taux: string | null }) {
  const { t, i18n } = useTranslation()
  const { token } = theme.useToken()
  const valeur = taux === null ? null : Number(taux)
  const [ton, cle] = seuil(valeur)
  const couleur = {
    succes: token.colorSuccess,
    attention: token.colorWarning,
    erreur: token.colorError,
    info: token.colorInfo,
    neutre: token.colorTextQuaternary,
  }[ton]
  const texte =
    valeur === null
      ? t('jauge.sansBase')
      : `${new Intl.NumberFormat(i18n.language, { maximumFractionDigits: 2 }).format(valeur)} %`
  return (
    <Flex vertical gap={4} style={{ minWidth: 160 }}>
      <Flex justify="space-between" gap="small" wrap>
        <Typography.Text>{libelle}</Typography.Text>
        <Typography.Text strong style={{ fontVariantNumeric: 'tabular-nums' }}>
          {texte}
        </Typography.Text>
      </Flex>
      <div
        role="meter"
        aria-label={libelle}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={valeur ?? 0}
        aria-valuetext={`${texte} — ${t(cle)}`}
        style={{
          position: 'relative',
          height: 10,
          background: token.colorFillSecondary,
          borderRadius: token.borderRadiusSM,
        }}
      >
        <div
          style={{
            width: `${(Math.min(valeur ?? 0, ECHELLE) / ECHELLE) * 100}%`,
            height: '100%',
            background: couleur,
            borderRadius: token.borderRadiusSM,
          }}
        />
        {REPERES.map((r) => (
          <div
            key={r}
            aria-hidden
            style={{
              position: 'absolute',
              top: -3,
              bottom: -3,
              left: `${(r / ECHELLE) * 100}%`,
              width: 2,
              background: token.colorText,
            }}
          />
        ))}
      </div>
      <BadgeStatut ton={ton} libelle={t(cle)} />
    </Flex>
  )
}
