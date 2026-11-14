import { UploadOutlined } from '@ant-design/icons'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Alert, Button, Card, Col, Flex, List, Row, Tree, Typography, Upload } from 'antd'
import type { DataNode } from 'antd/es/tree'
import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { appelerApi } from '../../api/client'
import { useAfficherErreur } from '../../api/erreurs'
import {
  getListerNomenclatureQueryKey,
  getImporterNomenclatureUrl,
  useListerNomenclature,
  useObtenirCompteComptable,
} from '../../api/genere/budget'
import type { NoeudSortie, RapportImport } from '../../api/genere/budget.schemas'
import { useAProfil } from '../../auth/session'

function arbre(noeuds: NoeudSortie[], niveau: (n: NoeudSortie) => string): DataNode[] {
  const enfants = new Map<string | null, NoeudSortie[]>()
  for (const n of noeuds)
    enfants.set(n.parentId ?? null, [...(enfants.get(n.parentId ?? null) ?? []), n])
  const construire = (parent: string | null): DataNode[] =>
    (enfants.get(parent) ?? []).map((n) => ({
      key: n.id,
      title: `${niveau(n)} ${n.code} — ${n.libelle}`,
      children: construire(n.id),
      isLeaf: !enfants.has(n.id),
    }))
  return construire(null)
}

/** Correspondance comptable d'un compte budgétaire, dans les deux sens (T-082). */
function Correspondance({ noeud }: { noeud: NoeudSortie }) {
  const { t } = useTranslation('parametrage')
  const code = noeud.compteComptableCode ?? ''
  const { data } = useObtenirCompteComptable(code, { query: { enabled: Boolean(code) } })
  return (
    <Flex vertical gap="small">
      <Typography.Text strong>
        {noeud.code} — {noeud.libelle}
      </Typography.Text>
      {data && (
        <>
          <Typography.Text>
            {t('nomenclature.compteComptable')} : {data.code} — {data.libelle}
          </Typography.Text>
          <Typography.Text>{t('nomenclature.comptesBudgetaires')}</Typography.Text>
          <List
            size="small"
            dataSource={data.comptesBudgetaires}
            renderItem={(c) => <List.Item key={c.id}>{`${c.code} — ${c.libelle}`}</List.Item>}
          />
        </>
      )}
    </Flex>
  )
}

/** Nomenclature budgétaire : arbre, import CSV et correspondance SYSCOHADA (T-082). */
export function Nomenclature() {
  const { t } = useTranslation('parametrage')
  const { t: tBudget } = useTranslation('budget')
  const afficherErreur = useAfficherErreur()
  const client = useQueryClient()
  const peutImporter = useAProfil(['ADM'])
  const { data: noeuds = [] } = useListerNomenclature()
  const [choisi, setChoisi] = useState<NoeudSortie>()
  const donnees = useMemo(() => arbre(noeuds, (n) => t(`nomenclature.${n.niveau}`)), [noeuds, t])

  // Le client généré enverrait du JSON : le fichier part tel quel, en text/csv.
  const envoi = useMutation({
    mutationFn: async (fichier: File) =>
      appelerApi<RapportImport>(getImporterNomenclatureUrl(), {
        method: 'POST',
        headers: { 'Content-Type': 'text/csv' },
        body: await fichier.text(),
      }),
    onSuccess: () => void client.invalidateQueries({ queryKey: getListerNomenclatureQueryKey() }),
    onError: (erreur) => afficherErreur(erreur),
  })
  const rapport = envoi.data

  return (
    <Flex vertical gap="middle">
      <Typography.Title level={1}>{t('nomenclature.titre')}</Typography.Title>
      <Typography.Paragraph>{t('nomenclature.intro')}</Typography.Paragraph>
      {peutImporter && (
        <Upload
          accept=".csv,text/csv"
          showUploadList={false}
          beforeUpload={(fichier) => {
            envoi.mutate(fichier)
            return false
          }}
        >
          <Button icon={<UploadOutlined aria-hidden />} loading={envoi.isPending}>
            {t('nomenclature.importer')}
          </Button>
        </Upload>
      )}
      {rapport && (
        <Alert
          type={rapport.anomalies.length ? 'warning' : 'success'}
          showIcon
          title={t('nomenclature.rapport', {
            crees: rapport.crees,
            misAJour: rapport.misAJour,
            anomalies: rapport.anomalies.length,
          })}
          description={rapport.anomalies.map((a) => (
            <div key={`${a.ligne}-${a.code}`}>
              {`${tBudget('import.ligne')} ${a.ligne} : ${tBudget(`anomalies.${a.code}`, {
                defaultValue: tBudget('anomalies.autre'),
              })} ${a.valeur}`}
            </div>
          ))}
        />
      )}
      <Row gutter={[16, 16]}>
        <Col xs={24} lg={14}>
          <Card>
            <Tree
              treeData={donnees}
              onSelect={(cles) => setChoisi(noeuds.find((n) => n.id === cles[0]))}
            />
          </Card>
        </Col>
        <Col xs={24} lg={10}>
          <Card>
            {choisi ? (
              <Correspondance noeud={choisi} />
            ) : (
              <Typography.Text>{t('nomenclature.choisir')}</Typography.Text>
            )}
          </Card>
        </Col>
      </Row>
    </Flex>
  )
}
