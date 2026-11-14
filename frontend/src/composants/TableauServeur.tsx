import { Card, Flex, Grid, List, Pagination, Table, Typography } from 'antd'
import type { ColumnsType, SorterResult, TablePaginationConfig } from 'antd/es/table/interface'
import { useState, type Key, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

export interface EtatTableau {
  page: number
  taille: number
  tri?: string
}

interface Proprietes<T> {
  colonnes: ColumnsType<T>
  donnees: T[]
  total: number
  chargement: boolean
  etat: EtatTableau
  surChangement: (etat: EtatTableau) => void
  cleLigne: (ligne: T) => string
  /** Rendu en carte, utilisé sur petit écran (IHM-08). */
  carte: (ligne: T) => ReactNode
  /** Actions groupées sur la sélection (IHM-09) ; absent : pas de sélection multiple. */
  actionsGroupees?: (selection: string[], vider: () => void) => ReactNode
}

function versTri<T>(tri: SorterResult<T> | SorterResult<T>[]): string | undefined {
  const premier = Array.isArray(tri) ? tri[0] : tri
  if (!premier?.order || !premier.field) return undefined
  return `${premier.order === 'descend' ? '-' : ''}${String(premier.field)}`
}

/** Tableau paginé, trié et filtré côté serveur (T-070) ; en cartes sur petit écran (T-073). */
export function TableauServeur<T extends object>({
  colonnes,
  donnees,
  total,
  chargement,
  etat,
  surChangement,
  cleLigne,
  carte,
  actionsGroupees,
}: Proprietes<T>) {
  const { t } = useTranslation()
  const ecrans = Grid.useBreakpoint()
  const [selection, setSelection] = useState<Key[]>([])
  const vider = () => setSelection([])

  const barreSelection = actionsGroupees && selection.length > 0 && (
    <Flex gap="small" align="center" wrap>
      <Typography.Text>{t('tableau.selection', { count: selection.length })}</Typography.Text>
      {actionsGroupees(selection.map(String), vider)}
    </Flex>
  )

  if (ecrans.md === false) {
    return (
      <Flex vertical gap="small">
        <List
          loading={chargement}
          dataSource={donnees}
          locale={{ emptyText: t('tableau.aucun') }}
          renderItem={(ligne) => (
            <List.Item key={cleLigne(ligne)}>
              <Card style={{ width: '100%' }}>{carte(ligne)}</Card>
            </List.Item>
          )}
        />
        <Pagination
          current={etat.page}
          pageSize={etat.taille}
          total={total}
          simple
          onChange={(page, taille) => surChangement({ ...etat, page, taille })}
        />
      </Flex>
    )
  }

  return (
    <Flex vertical gap="small">
      {barreSelection}
      <Table<T>
        columns={colonnes}
        dataSource={donnees}
        rowKey={cleLigne}
        loading={chargement}
        scroll={{ x: 'max-content' }}
        locale={{ emptyText: t('tableau.aucun') }}
        rowSelection={
          actionsGroupees ? { selectedRowKeys: selection, onChange: setSelection } : undefined
        }
        pagination={{
          current: etat.page,
          pageSize: etat.taille,
          total,
          showSizeChanger: true,
          pageSizeOptions: [10, 25, 50, 100],
          showTotal: (nombre) => t('tableau.total', { count: nombre }),
        }}
        onChange={(pagination: TablePaginationConfig, _filtres, tri) =>
          surChangement({
            page: pagination.current ?? 1,
            taille: pagination.pageSize ?? etat.taille,
            tri: versTri(tri),
          })
        }
      />
    </Flex>
  )
}
