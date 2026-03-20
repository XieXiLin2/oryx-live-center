import {
  ApiOutlined,
  CloudServerOutlined,
  DashboardOutlined,
  ForwardOutlined,
  SettingOutlined,
  TeamOutlined,
  VideoCameraOutlined,
} from '@ant-design/icons';
import { Layout, Menu, Typography } from 'antd';
import React from 'react';
import { Navigate, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../../store/auth';

const { Sider, Content } = Layout;
const { Text } = Typography;

const AdminLayout: React.FC = () => {
  const { user, loading } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  if (loading) return null;
  if (!user?.is_admin) return <Navigate to="/" replace />;

  const menuItems = [
    { key: '/admin', icon: <DashboardOutlined />, label: '概览' },
    { key: '/admin/streams', icon: <VideoCameraOutlined />, label: '直播管理' },
    { key: '/admin/users', icon: <TeamOutlined />, label: '用户管理' },
    {
      key: 'oryx',
      icon: <CloudServerOutlined />,
      label: 'Oryx 管理',
      children: [
        { key: '/admin/oryx/clients', label: '客户端' },
        { key: '/admin/oryx/dvr', label: '录制 (DVR)' },
        { key: '/admin/oryx/hls', label: 'HLS 配置' },
        { key: '/admin/oryx/forward', icon: <ForwardOutlined />, label: '转推/转发' },
        { key: '/admin/oryx/transcode', label: '转码' },
        { key: '/admin/oryx/hooks', icon: <ApiOutlined />, label: 'HTTP 回调' },
      ],
    },
    { key: '/admin/settings', icon: <SettingOutlined />, label: '系统设置' },
  ];

  const selectedKey = location.pathname;

  return (
    <Layout style={{ minHeight: 'calc(100vh - 128px)', borderRadius: 8, overflow: 'hidden' }}>
      <Sider width={220} theme="light" breakpoint="lg" collapsedWidth={0}>
        <div style={{ padding: '16px', borderBottom: '1px solid #f0f0f0' }}>
          <Text strong>
            <SettingOutlined /> 管理后台
          </Text>
        </div>
        <Menu
          mode="inline"
          selectedKeys={[selectedKey]}
          defaultOpenKeys={['oryx']}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
          style={{ border: 'none' }}
        />
      </Sider>
      <Content style={{ padding: 24, background: '#fff' }}>
        <Outlet />
      </Content>
    </Layout>
  );
};

export default AdminLayout;
