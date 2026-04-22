import {
  AppstoreOutlined,
  CloudServerOutlined,
  DashboardOutlined,
  PlayCircleOutlined,
  SettingOutlined,
  TeamOutlined,
  VideoCameraOutlined,
} from '@ant-design/icons';
import { Layout, Menu, Result } from 'antd';
import React from 'react';
import { Navigate, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../../store/auth';

const { Sider, Content } = Layout;

const items = [
  { key: '/admin',              icon: <DashboardOutlined />,   label: '总览' },
  { key: '/admin/streams',      icon: <VideoCameraOutlined />, label: '直播间管理' },
  { key: '/admin/edge-nodes',   icon: <CloudServerOutlined />, label: 'Edge 节点' },
  { key: '/admin/sessions',     icon: <PlayCircleOutlined />,  label: '播放统计' },
  { key: '/admin/srs-clients',  icon: <AppstoreOutlined />,    label: 'SRS 客户端' },
  { key: '/admin/users',        icon: <TeamOutlined />,        label: '用户管理' },
  { key: '/admin/settings',     icon: <SettingOutlined />,     label: '系统设置' },
];

/**
 * Pick the best-matching top-level menu key for the current URL so that the
 * sidebar still highlights "直播间管理" when we are on
 * ``/admin/streams/:name`` (detail page).
 */
const resolveSelectedKey = (pathname: string): string => {
  // Longest prefix wins. Exclude the bare "/admin" key from the prefix match
  // so every sub-route doesn't activate it.
  const keys = items.map((i) => i.key).filter((k) => k !== '/admin');
  const match = keys
    .filter((k) => pathname === k || pathname.startsWith(k + '/'))
    .sort((a, b) => b.length - a.length)[0];
  if (match) return match;
  if (pathname === '/admin' || pathname === '/admin/') return '/admin';
  return '/admin';
};

const AdminLayout: React.FC = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  if (!user) return <Navigate to="/" replace />;
  if (!user.is_admin) {
    return <Result status="403" title="403" subTitle="无权访问管理后台" />;
  }

  return (
    <Layout style={{ background: 'transparent', minHeight: 'calc(100vh - 134px)' }}>
      <Sider width={220} style={{ background: '#fff', borderRadius: 8 }}>
        <Menu
          mode="inline"
          selectedKeys={[resolveSelectedKey(location.pathname)]}
          items={items}
          onClick={({ key }) => navigate(key)}
          style={{ border: 'none', borderRadius: 8, paddingTop: 16 }}
        />
      </Sider>
      <Content style={{ paddingLeft: 24 }}>
        <Outlet />
      </Content>
    </Layout>
  );
};

export default AdminLayout;
