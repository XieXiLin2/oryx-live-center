import { ConfigProvider, Spin, theme } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import React from 'react';
import { BrowserRouter, Route, Routes } from 'react-router-dom';
import AppLayout from './components/AppLayout';
import AuthCallback from './pages/AuthCallback';
import Home from './pages/Home';
import AdminLayout from './pages/admin/AdminLayout';
import Dashboard from './pages/admin/Dashboard';
import OryxClients from './pages/admin/OryxClients';
import {
  AdminSettings,
  OryxDvr,
  OryxForward,
  OryxHls,
  OryxHooks,
  OryxTranscode,
} from './pages/admin/OryxPages';
import StreamsManage from './pages/admin/StreamsManage';
import UsersManage from './pages/admin/UsersManage';
import { AuthProvider, useAuth } from './store/auth';

const AppContent: React.FC = () => {
  const { loading } = useAuth();

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <Spin size="large" tip="加载中..." />
      </div>
    );
  }

  return (
    <Routes>
      <Route path="/auth/callback" element={<AuthCallback />} />
      <Route element={<AppLayout />}>
        <Route index element={<Home />} />
        <Route path="admin" element={<AdminLayout />}>
          <Route index element={<Dashboard />} />
          <Route path="streams" element={<StreamsManage />} />
          <Route path="users" element={<UsersManage />} />
          <Route path="oryx/clients" element={<OryxClients />} />
          <Route path="oryx/dvr" element={<OryxDvr />} />
          <Route path="oryx/hls" element={<OryxHls />} />
          <Route path="oryx/forward" element={<OryxForward />} />
          <Route path="oryx/transcode" element={<OryxTranscode />} />
          <Route path="oryx/hooks" element={<OryxHooks />} />
          <Route path="settings" element={<AdminSettings />} />
        </Route>
      </Route>
    </Routes>
  );
};

const App: React.FC = () => {
  return (
    <ConfigProvider
      locale={zhCN}
      theme={{
        algorithm: theme.defaultAlgorithm,
        token: {
          colorPrimary: '#1677ff',
          borderRadius: 8,
        },
      }}
    >
      <BrowserRouter>
        <AuthProvider>
          <AppContent />
        </AuthProvider>
      </BrowserRouter>
    </ConfigProvider>
  );
};

export default App;
