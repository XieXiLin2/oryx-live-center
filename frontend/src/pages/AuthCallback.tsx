import { message, Spin } from 'antd';
import React, { useEffect, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { authApi } from '../api';
import { useAuth } from '../store/auth';

const AuthCallback: React.FC = () => {
  const [searchParams] = useSearchParams();
  const { setAuth } = useAuth();
  const navigate = useNavigate();
  const processed = useRef(false);

  useEffect(() => {
    if (processed.current) return;
    processed.current = true;

    const code = searchParams.get('code');
    const state = searchParams.get('state');

    if (!code) {
      message.error('OAuth 回调缺少授权码');
      navigate('/');
      return;
    }

    authApi
      .callback(code, state || undefined)
      .then((data) => {
        setAuth(data.access_token, data.user);
        message.success(`欢迎, ${data.user.display_name || data.user.username}!`);
        navigate('/');
      })
      .catch((err) => {
        console.error('OAuth callback error:', err);
        message.error('登录失败，请重试');
        navigate('/');
      });
  }, [searchParams, setAuth, navigate]);

  return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '60vh' }}>
      <Spin size="large" tip="正在登录..." />
    </div>
  );
};

export default AuthCallback;
