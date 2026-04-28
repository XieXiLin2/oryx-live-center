import axios from 'axios';

const API_BASE = '/api/admin/transcode';

export interface TranscodeNode {
  id: string;
  name: string;
  region: string;
  ip_address?: string;
  status: string;
  max_tasks: number;
  current_tasks: number;
  cpu_usage?: number;
  memory_usage?: number;
  gpu_usage?: number;
  network_latency?: number;
  last_heartbeat?: string;
  capabilities?: {
    protocols?: string[];
    codecs?: string[];
    gpu?: boolean;
  };
}

export interface TranscodeProfile {
  id: number;
  name: string;
  description?: string;
  source_protocol: string;
  outputs: Array<{
    protocol: string;
    resolution: string;
    bitrate: string;
    fps: number;
    codec?: string;
    audio_codec?: string;
    audio_bitrate?: string;
  }>;
  latency_mode: string;
  created_at?: string;
}

export interface TranscodeTask {
  id: number;
  stream_name: string;
  profile_id: number;
  node_id?: string;
  source_protocol?: string;
  source_url?: string;
  outputs?: Array<{
    protocol: string;
    url: string;
    resolution?: string;
    bitrate?: string;
    fps?: number;
  }>;
  status: string;
  started_at?: string;
  stopped_at?: string;
  error_message?: string;
  metrics?: {
    latency?: number;
    fps?: number;
    bitrate?: number;
    packet_loss?: number;
  };
}

export const transcodeApi = {
  // Nodes
  listNodes: () => axios.get<{ nodes: TranscodeNode[] }>(`${API_BASE}/nodes`),
  registerNode: (data: Partial<TranscodeNode>) => axios.post(`${API_BASE}/nodes/register`, data),
  deleteNode: (nodeId: string) => axios.delete(`${API_BASE}/nodes/${nodeId}`),

  // Profiles
  listProfiles: () => axios.get<{ profiles: TranscodeProfile[] }>(`${API_BASE}/profiles`),
  getProfile: (id: number) => axios.get<TranscodeProfile>(`${API_BASE}/profiles/${id}`),
  createProfile: (data: Partial<TranscodeProfile>) => axios.post(`${API_BASE}/profiles`, data),
  updateProfile: (id: number, data: Partial<TranscodeProfile>) =>
    axios.put(`${API_BASE}/profiles/${id}`, data),
  deleteProfile: (id: number) => axios.delete(`${API_BASE}/profiles/${id}`),

  // Tasks
  listTasks: (params?: { region?: string; status?: string }) =>
    axios.get<{ tasks: TranscodeTask[] }>(`${API_BASE}/tasks`, { params }),
  getTask: (id: number) => axios.get<TranscodeTask>(`${API_BASE}/tasks/${id}`),
  createTask: (data: { stream_name: string; profile_id: number; region?: string; auto_start?: boolean }) =>
    axios.post(`${API_BASE}/tasks`, data),
  startTask: (id: number) => axios.post(`${API_BASE}/tasks/${id}/start`),
  stopTask: (id: number) => axios.post(`${API_BASE}/tasks/${id}/stop`),
  deleteTask: (id: number) => axios.delete(`${API_BASE}/tasks/${id}`),

  // Regions
  listRegions: () => axios.get<{ regions: Array<{
    name: string;
    display_name: string;
    nodes: number;
    online_nodes: number;
    total_capacity: number;
    used_capacity: number;
    avg_latency: number;
  }> }>(`${API_BASE}/regions`),
};
