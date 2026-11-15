import {
  ApartmentOutlined,
  AuditOutlined,
  ContainerOutlined,
  FundOutlined,
  HomeOutlined,
  LogoutOutlined,
  SafetyOutlined,
  SettingOutlined,
  ShopOutlined,
  ShoppingCartOutlined,
  SwapOutlined,
} from '@ant-design/icons'
import { Breadcrumb, Button, Flex, Layout, Menu, Select, Typography, theme } from 'antd'
import { Link, Outlet, useLocation, useMatches, useNavigate } from 'react-router'
import { useTranslation } from 'react-i18next'
import { useModifierPreferences } from '../api/genere/budget'
import { useSession } from '../auth/session'
import { LANGUES, estLangue, memoriserLangue, type Langue } from '../i18n/langue'
import { useEtablissementCourant } from './etablissementCourant'

export interface Poignee {
  fil?: string
}

/** Gabarit commun (T-064) : menu, fil d'Ariane, utilisateur, établissement, langue. */
export function Gabarit() {
  const { t, i18n } = useTranslation()
  const { token } = theme.useToken()
  const { moi, deconnecter } = useSession()
  const naviguer = useNavigate()
  const { pathname } = useLocation()
  const correspondances = useMatches()
  const preferences = useModifierPreferences()
  const { etablissements, courant, choisir } = useEtablissementCourant()
  // Consulter les habilitations : profils ayant « Paramétrer » dans la matrice validée.
  const voitHabilitations = (moi?.habilitations ?? []).some((h) =>
    ['ADM', 'RB', 'AUD'].includes(h.profil),
  )

  const changerLangue = (langue: Langue) => {
    memoriserLangue(langue)
    void i18n.changeLanguage(langue)
    preferences.mutate({ data: { langue } })
  }

  const fil = correspondances
    .filter((c) => (c.handle as Poignee | undefined)?.fil)
    .map((c) => ({
      key: c.id,
      title: <Link to={c.pathname}>{t((c.handle as Poignee).fil!)}</Link>,
    }))

  const sectionActive = '/' + (pathname.split('/')[1] ?? '')

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Layout.Sider breakpoint="lg" collapsedWidth={0} theme="light">
        <Typography.Title level={4} style={{ padding: token.padding, margin: 0 }}>
          {t('application.nom')}
        </Typography.Title>
        <Menu
          aria-label={t('menu.navigation')}
          mode="inline"
          selectedKeys={[sectionActive]}
          onClick={({ key }) => naviguer(key)}
          items={[
            { key: '/', icon: <HomeOutlined aria-hidden />, label: t('menu.accueil') },
            {
              key: '/etablissements',
              icon: <ShopOutlined aria-hidden />,
              label: t('menu.etablissements'),
            },
            {
              key: '/budgets',
              icon: <FundOutlined aria-hidden />,
              label: t('menu.budgets'),
            },
            {
              key: '/contrats',
              icon: <ContainerOutlined aria-hidden />,
              label: t('menu.contrats'),
            },
            {
              key: '/engagements',
              icon: <AuditOutlined aria-hidden />,
              label: t('menu.engagements'),
            },
            {
              key: '/commandes',
              icon: <ShoppingCartOutlined aria-hidden />,
              label: t('menu.commandes'),
            },
            {
              key: '/nomenclature',
              icon: <ApartmentOutlined aria-hidden />,
              label: t('menu.nomenclature'),
            },
            {
              key: '/delegations',
              icon: <SwapOutlined aria-hidden />,
              label: t('menu.delegations'),
            },
            {
              key: '/parametrage',
              icon: <SettingOutlined aria-hidden />,
              label: t('menu.parametrage'),
            },
            ...(voitHabilitations
              ? [
                  {
                    key: '/habilitations',
                    icon: <SafetyOutlined aria-hidden />,
                    label: t('menu.habilitations'),
                  },
                ]
              : []),
          ]}
        />
      </Layout.Sider>
      <Layout>
        <Layout.Header style={{ background: token.colorBgContainer, paddingInline: token.padding }}>
          <Flex justify="flex-end" align="center" gap="middle" wrap style={{ height: '100%' }}>
            <Select
              aria-label={t('entete.etablissement')}
              style={{ minWidth: 200 }}
              value={courant ?? ''}
              onChange={(valeur) => choisir(valeur || null)}
              options={[
                { value: '', label: t('entete.tousEtablissements') },
                ...etablissements.map((e) => ({ value: e.id, label: `${e.code} — ${e.nom}` })),
              ]}
            />
            <Select
              aria-label={t('entete.langue')}
              value={estLangue(i18n.language) ? i18n.language : 'fr'}
              onChange={changerLangue}
              options={LANGUES.map((l) => ({ value: l, label: t(`langues.${l}`) }))}
            />
            <Typography.Text>{moi?.nom}</Typography.Text>
            <Button icon={<LogoutOutlined aria-hidden />} onClick={() => void deconnecter()}>
              {t('entete.deconnexion')}
            </Button>
          </Flex>
        </Layout.Header>
        <Layout.Content style={{ padding: token.paddingLG }}>
          <Breadcrumb items={fil} style={{ marginBottom: token.margin }} />
          <Outlet />
        </Layout.Content>
      </Layout>
    </Layout>
  )
}
