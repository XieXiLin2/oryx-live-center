/**
 * Streams management (list view).
 *
 * Kept deliberately minimal: the list only shows stream name, display name,
 * visibility, live state and a tiny action bar (open detail / delete). All
 * the actual knobs (publish secret, watch token, WebRTC toggle, push URL
 * templates, OBS / ffmpeg tutorials, low-latency tweaks) live on the
 * per-stream detail page at ``/admin/streams/:name``.
 *
 * The "new room" modal is equally minimal — admins only pick the stream
 * name, display name and whether the room is private. Publish secret and
 * watch token are auto-generated server-side; the admin can inspect and
 * rotate them from the detail page.
 */

import { DeleteOutlined, PlusOutlined, ReloadOutlined, SettingOutlined } from '@ant-design/icons';
import {
  App,
  Button,
  Form,
  Input,
  Modal,
  Popconfirm,
  Space,
  Switch,
  Table,
  Tag,
  Typography,
} from 'antd';
import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { streamApi } from '../../api';
import type { StreamConfig } from '../../types';

const { Title } = Typography;

const StreamsManage: React.FC = () => {
  const { message } = App.useApp();
  const navigate = useNavigate();
  const [rows, setRows] = useState<StreamConfig[]>([]);
  const [loading, setLoading] = useState(false);
  const [newModalOpen, setNewModalOpen] = useState(false);
  const [form] = Form.useForm();

  const load = async () => {
    setLoading(true);
    try {
      const data = await streamApi.listConfigs();
      setRows(data);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const openNew = () => {
    form.resetFields();
    form.setFieldsValue({ is_private: false });
    setNewModalOpen(true);
  };

  const submitNew = async () => {
    const v = await form.validateFields();
    const streamName = v.stream_name?.trim();
    if (!streamName) return;
    try {
      await streamApi.createConfig(streamName, {
        display_name: v.display_name || streamName,
        is_private: !!v.is_private,
      });
      message.success('直播间已创建');
      setNewModalOpen(false);
      // Jump straight into the detail page so the admin can copy
      // the push key / watch token right away.
      navigate(`/admin/streams/${encodeURIComponent(streamName)}`);
    } catch (e: unknown) {
      const err = e as { response?: { status?: number; data?: { detail?: string } } };
      if (err.response?.status === 409) {
        message.error('该流名已存在');
      } else {
        message.error(err.response?.data?.detail || '创建失败');
      }
    }
  };

  const del = async (name: string) => {
    await streamApi.deleteConfig(name);
    message.success('已删除');
    load();
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Title level={3} style={{ margin: 0 }}>
          直播间管理
        </Title>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={load}>
            刷新
          </Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={openNew}>
            新建直播间
          </Button>
        </Space>
      </div>

      <Table
        rowKey="id"
        loading={loading}
        dataSource={rows}
        pagination={{ pageSize: 20 }}
        columns={[
          {
            title: '流名',
            dataIndex: 'stream_name',
            render: (name: string) => <code>{name}</code>,
          },
          {
            title: '显示名',
            dataIndex: 'display_name',
            render: (v: string, r) => v || r.stream_name,
          },
          {
            title: '可见性',
            dataIndex: 'is_private',
            width: 110,
            render: (v: boolean) =>
              v ? <Tag color="purple">私有</Tag> : <Tag color="blue">公开</Tag>,
          },
          {
            title: '状态',
            dataIndex: 'is_live',
            width: 110,
            render: (v: boolean) =>
              v ? <Tag color="green">直播中</Tag> : <Tag>离线</Tag>,
          },
          {
            title: '操作',
            width: 220,
            render: (_, r) => (
              <Space>
                <Button
                  size="small"
                  icon={<SettingOutlined />}
                  onClick={() =>
                    navigate(`/admin/streams/${encodeURIComponent(r.stream_name)}`)
                  }
                >
                  查看配置
                </Button>
                <Popconfirm
                  title="删除此直播间?"
                  description="将会同时失效推流密钥与观看 Token。"
                  onConfirm={() => del(r.stream_name)}
                >
                  <Button size="small" danger icon={<DeleteOutlined />}>
                    删除
                  </Button>
                </Popconfirm>
              </Space>
            ),
          },
        ]}
      />

      <Modal
        open={newModalOpen}
        title="新建直播间"
        onCancel={() => setNewModalOpen(false)}
        onOk={submitNew}
        destroyOnHidden
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="stream_name"
            label="流名 (URL 最后一段)"
            rules={[
              {
                required: true,
                pattern: /^[a-zA-Z0-9_-]+$/,
                message: '仅支持字母数字、下划线与连字符',
              },
            ]}
          >
            <Input placeholder="例如 demo" />
          </Form.Item>
          <Form.Item name="display_name" label="显示名称">
            <Input placeholder="例如 我的直播间 (留空则使用流名)" />
          </Form.Item>
          <Form.Item
            name="is_private"
            label="私有直播"
            valuePropName="checked"
            extra="开启后需要登录或观看 Token 才能播放。"
          >
            <Switch checkedChildren="是" unCheckedChildren="否" />
          </Form.Item>
          <Typography.Paragraph type="secondary" style={{ marginTop: 8, marginBottom: 0 }}>
            推流密钥 / 观看 Token / 播放协议等详细配置请在创建后的配置详情页中调整。
          </Typography.Paragraph>
        </Form>
      </Modal>
    </div>
  );
};

export default StreamsManage;
