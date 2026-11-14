import { Alert, Button, Card, Flex, Form, Input, Typography } from 'antd'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Navigate, useSearchParams } from 'react-router'
import { codeErreur } from '../api/erreurs'
import { useSession } from '../auth/session'

interface Identifiants {
  identifiant: string
  motDePasse: string
}

export function Connexion() {
  const { t } = useTranslation()
  const { t: tErreur } = useTranslation('erreurs')
  const { connecte, expiree, connecter } = useSession()
  const [parametres] = useSearchParams()
  const [erreur, setErreur] = useState<string | null>(null)
  const [envoi, setEnvoi] = useState(false)

  if (connecte) return <Navigate to={parametres.get('retour') ?? '/'} replace />

  const valider = async ({ identifiant, motDePasse }: Identifiants) => {
    setEnvoi(true)
    setErreur(null)
    try {
      await connecter(identifiant, motDePasse)
    } catch (e) {
      setErreur(tErreur(codeErreur(e)))
    } finally {
      setEnvoi(false)
    }
  }

  return (
    <Flex justify="center" align="center" style={{ minHeight: '100vh', padding: 16 }}>
      <Card style={{ width: '100%', maxWidth: 400 }}>
        <Typography.Title level={2}>{t('application.nom')}</Typography.Title>
        <Typography.Paragraph type="secondary">{t('connexion.sousTitre')}</Typography.Paragraph>
        {expiree && <Alert type="warning" showIcon title={t('connexion.sessionExpiree')} />}
        {erreur && <Alert type="error" showIcon title={erreur} role="alert" />}
        <Form<Identifiants> layout="vertical" onFinish={valider} requiredMark={false}>
          <Form.Item
            label={t('connexion.identifiant')}
            name="identifiant"
            rules={[{ required: true, message: t('connexion.obligatoire') }]}
          >
            <Input autoComplete="username" />
          </Form.Item>
          <Form.Item
            label={t('connexion.motDePasse')}
            name="motDePasse"
            rules={[{ required: true, message: t('connexion.obligatoire') }]}
          >
            <Input.Password autoComplete="current-password" />
          </Form.Item>
          <Button type="primary" htmlType="submit" loading={envoi} block>
            {t('connexion.valider')}
          </Button>
        </Form>
      </Card>
    </Flex>
  )
}
