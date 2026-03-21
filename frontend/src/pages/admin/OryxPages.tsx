import {
  ApiOutlined,
  CameraOutlined,
  CloudServerOutlined,
  ForwardOutlined,
  KeyOutlined,
  LockOutlined,
  PlayCircleOutlined,
  SafetyCertificateOutlined,
  SettingOutlined,
  VideoCameraOutlined,
} from '@ant-design/icons';
import React from 'react';
import { adminApi } from '../../api';
import OryxConfigPage from './OryxConfigPage';

export const OryxDvr: React.FC = () => (
  <OryxConfigPage
    title="录制 (DVR)"
    icon={<VideoCameraOutlined />}
    fetchFn={adminApi.getDvr}
    saveFn={adminApi.updateDvr as (config: Record<string, unknown>) => Promise<unknown>}
  />
);

export const OryxHls: React.FC = () => (
  <OryxConfigPage
    title="HLS 配置"
    icon={<PlayCircleOutlined />}
    fetchFn={adminApi.getHls}
    saveFn={adminApi.updateHls as (config: Record<string, unknown>) => Promise<unknown>}
  />
);

export const OryxForward: React.FC = () => (
  <OryxConfigPage
    title="转推/转发"
    icon={<ForwardOutlined />}
    fetchFn={adminApi.getForwards}
    saveFn={adminApi.createForward as (config: Record<string, unknown>) => Promise<unknown>}
  />
);

export const OryxTranscode: React.FC = () => (
  <OryxConfigPage
    title="转码"
    icon={<CloudServerOutlined />}
    fetchFn={adminApi.getTranscodes}
    saveFn={adminApi.createTranscode as (config: Record<string, unknown>) => Promise<unknown>}
  />
);

export const OryxHooks: React.FC = () => (
  <OryxConfigPage
    title="HTTP 回调"
    icon={<ApiOutlined />}
    fetchFn={adminApi.getHooks}
    saveFn={adminApi.updateHooks as (config: Record<string, unknown>) => Promise<unknown>}
  />
);

export const OryxSecret: React.FC = () => (
  <OryxConfigPage
    title="推流密钥"
    icon={<KeyOutlined />}
    fetchFn={adminApi.getSecret}
    saveFn={adminApi.updateSecret as (config: Record<string, unknown>) => Promise<unknown>}
  />
);

export const OryxVlive: React.FC = () => (
  <OryxConfigPage
    title="虚拟直播"
    icon={<PlayCircleOutlined />}
    fetchFn={adminApi.getVlive}
    saveFn={adminApi.updateVlive as (config: Record<string, unknown>) => Promise<unknown>}
  />
);

export const OryxCamera: React.FC = () => (
  <OryxConfigPage
    title="IP 摄像头"
    icon={<CameraOutlined />}
    fetchFn={adminApi.getCamera}
    saveFn={adminApi.updateCamera as (config: Record<string, unknown>) => Promise<unknown>}
  />
);

export const OryxLimits: React.FC = () => (
  <OryxConfigPage
    title="系统限制"
    icon={<LockOutlined />}
    fetchFn={adminApi.getLimits}
    saveFn={adminApi.updateLimits as (config: Record<string, unknown>) => Promise<unknown>}
  />
);

export const OryxCert: React.FC = () => (
  <OryxConfigPage
    title="SSL 证书"
    icon={<SafetyCertificateOutlined />}
    fetchFn={adminApi.getCert}
  />
);

export const AdminSettings: React.FC = () => (
  <OryxConfigPage
    title="系统设置"
    icon={<SettingOutlined />}
    fetchFn={adminApi.getSettings}
  />
);
