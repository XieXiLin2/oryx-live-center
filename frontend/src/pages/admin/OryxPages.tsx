import {
  ApiOutlined,
  CloudServerOutlined,
  ForwardOutlined,
  PlayCircleOutlined,
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

export const AdminSettings: React.FC = () => (
  <OryxConfigPage
    title="系统设置"
    icon={<SettingOutlined />}
    fetchFn={adminApi.getSettings}
  />
);
