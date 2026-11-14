import { Card, Flex, Result, Spin, Typography } from 'antd'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router'
import { useObtenirDisponibilite, useObtenirLigneBudgetaire } from '../../api/genere/budget'
import { Indicateurs } from './FicheBudget'
import { Revisions } from './Revisions'

/** Fiche ligne budgétaire (/lignes-budgetaires/:id) : disponibilité et révisions (T-092). */
export function FicheLigne() {
  const { id = '' } = useParams()
  const { t } = useTranslation('budget')
  const { t: tCommun } = useTranslation()
  const { data: ligne, isLoading, error } = useObtenirLigneBudgetaire(id)
  const { data: disponibilite } = useObtenirDisponibilite(id)

  if (isLoading) return <Spin aria-label={tCommun('tableau.chargement')} />
  if (error || !ligne) {
    return (
      <Result
        status="404"
        title={tCommun('introuvable.titre')}
        subTitle={tCommun('introuvable.detail')}
        extra={<Link to="/budgets">{tCommun('menu.budgets')}</Link>}
      />
    )
  }
  return (
    <Flex vertical gap="middle">
      <Typography.Title level={1}>
        {ligne.code} — {ligne.libelle}
      </Typography.Title>
      <Link to={`/budgets/${ligne.budgetId}`}>{tCommun('menu.budgets')}</Link>
      <Card title={t('ligne.disponibilite')}>
        {disponibilite && <Indicateurs valeurs={disponibilite.indicateurs} />}
      </Card>
      <Card title={t('onglets.revisions')}>
        <Revisions budgetId={ligne.budgetId} ligneId={id} />
      </Card>
    </Flex>
  )
}
