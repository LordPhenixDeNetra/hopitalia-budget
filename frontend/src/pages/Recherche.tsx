import { useQuery } from '@tanstack/react-query'
import { Flex, Input, List, Space, Tag, Typography } from 'antd'
import { useTranslation } from 'react-i18next'
import { Link, useSearchParams } from 'react-router'
import { rechercher } from '../api/genere/budget'
import { Montant } from '../composants/Montant'
import { formaterDate } from '../format/format'

/** Recherche transverse par numéro, fournisseur, montant, date, compte ou service (T-238). */
export function Recherche() {
  const { t, i18n } = useTranslation('recherche')
  const [parametres, setParametres] = useSearchParams()
  const q = parametres.get('q') ?? ''
  const { data = [], isFetching } = useQuery({
    queryKey: ['recherche', q],
    queryFn: () => rechercher({ q }),
    enabled: q.trim().length >= 2,
  })

  return (
    <Flex vertical gap="middle">
      <Typography.Title level={1} style={{ margin: 0 }}>
        {t('titre')}
      </Typography.Title>
      <Typography.Paragraph>{t('intro')}</Typography.Paragraph>
      <Input.Search
        aria-label={t('champ')}
        placeholder={t('exemple')}
        defaultValue={q}
        enterButton={t('chercher')}
        allowClear
        onSearch={(valeur) => setParametres(valeur ? { q: valeur } : {})}
        style={{ maxWidth: 560 }}
      />
      {q.trim().length >= 2 && (
        <List
          loading={isFetching}
          dataSource={data}
          locale={{ emptyText: t('aucun') }}
          renderItem={(r) => (
            <List.Item>
              <Flex vertical gap={2}>
                <Space wrap>
                  <Tag>{t(`types.${r.type}`)}</Tag>
                  <Link to={r.lien}>{r.numero}</Link>
                  {r.montant && <Montant valeur={r.montant} />}
                  {r.date && (
                    <Typography.Text type="secondary">
                      {formaterDate(r.date, i18n.language)}
                    </Typography.Text>
                  )}
                </Space>
                {r.libelle && <Typography.Text>{r.libelle}</Typography.Text>}
              </Flex>
            </List.Item>
          )}
        />
      )}
    </Flex>
  )
}
