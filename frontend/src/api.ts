import axios from 'axios';
import type {
  AuthURLResponse,
  ChatHistoryResponse,
  StreamConfig,
  StreamInfo,
  StreamPlayResponse,
  TokenResponse,
  User,
  UserListResponse,
} from './types';

const api = axios.create({
  baseURL: '/api',
  timeout: 15000,
});

// Attach token to requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle 401 responses
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('token');
      localStorage.removeItem('user');
    }
    return Promise.reject(err);
  }
);

// ---- Auth ----
export const authApi = {
  getLoginUrl: () => api.get<AuthURLResponse>('/auth/login').then((r) => r.data),
  callback: (code: string, state?: string) =>
    api.post<TokenResponse>('/auth/callback', { code, state }).then((r) => r.data),
  getMe: () => api.get<User>('/auth/me').then((r) => r.data),
  logout: () => api.get<{ logout_url: string | null }>('/auth/logout').then((r) => r.data),
};

// ---- Streams ----
export const streamApi = {
  list: () => api.get<{ streams: StreamInfo[] }>('/streams/').then((r) => r.data),
  play: (stream_name: string, format: string, key?: string) =>
    api.post<StreamPlayResponse>('/streams/play', { stream_name, format, key }).then((r) => r.data),
  // Admin
  listConfigs: () => api.get<StreamConfig[]>('/streams/config').then((r) => r.data),
  updateConfig: (stream_name: string, data: Partial<StreamConfig> & { encryption_key?: string }) =>
    api.put<StreamConfig>(`/streams/config/${stream_name}`, data).then((r) => r.data),
  deleteConfig: (stream_name: string) => api.delete(`/streams/config/${stream_name}`),
};

// ---- Chat ----
export const chatApi = {
  getHistory: (stream_name: string, limit = 50, offset = 0) =>
    api
      .get<ChatHistoryResponse>(`/chat/history/${stream_name}`, { params: { limit, offset } })
      .then((r) => r.data),
  getOnlineCount: (stream_name: string) =>
    api.get<{ online_count: number }>(`/chat/online/${stream_name}`).then((r) => r.data),
};

// ---- Admin ----
export const adminApi = {
  // Users
  listUsers: (params?: { limit?: number; offset?: number; search?: string }) =>
    api.get<UserListResponse>('/admin/users', { params }).then((r) => r.data),
  banUser: (userId: number, is_banned: boolean) =>
    api.put(`/admin/users/${userId}/ban`, { is_banned }),
  deleteMessage: (messageId: number) => api.delete(`/admin/chat/messages/${messageId}`),

  // Oryx
  getSystemInfo: () => api.get('/admin/oryx/system').then((r) => r.data),
  getVersions: () => api.get('/admin/oryx/versions').then((r) => r.data),
  getStreams: () => api.get('/admin/oryx/streams').then((r) => r.data),
  getClients: () => api.get('/admin/oryx/clients').then((r) => r.data),
  kickClient: (clientId: string) => api.delete(`/admin/oryx/clients/${clientId}`),

  // Vhosts
  getVhosts: () => api.get('/admin/oryx/vhosts').then((r) => r.data),

  // DVR
  getDvr: () => api.get('/admin/oryx/dvr').then((r) => r.data),
  updateDvr: (config: Record<string, unknown>) => api.post('/admin/oryx/dvr', config),

  // HLS
  getHls: () => api.get('/admin/oryx/hls').then((r) => r.data),
  updateHls: (config: Record<string, unknown>) => api.post('/admin/oryx/hls', config),

  // Forward
  getForwards: () => api.get('/admin/oryx/forward').then((r) => r.data),
  createForward: (config: Record<string, unknown>) => api.post('/admin/oryx/forward', config),
  deleteForward: (id: string) => api.delete(`/admin/oryx/forward/${id}`),

  // Transcode
  getTranscodes: () => api.get('/admin/oryx/transcode').then((r) => r.data),
  createTranscode: (config: Record<string, unknown>) => api.post('/admin/oryx/transcode', config),
  deleteTranscode: (id: string) => api.delete(`/admin/oryx/transcode/${id}`),

  // Hooks
  getHooks: () => api.get('/admin/oryx/hooks').then((r) => r.data),
  updateHooks: (config: Record<string, unknown>) => api.post('/admin/oryx/hooks', config),

  // Settings
  getSettings: () => api.get('/admin/settings').then((r) => r.data),
  getCdnConfig: () => api.get('/admin/cdn/config').then((r) => r.data),
};

export default api;
