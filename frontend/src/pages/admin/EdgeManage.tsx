/**
 * Edge / CDN node management.
 *
 * Mounted at ``/admin/edge-nodes``. Lets admins maintain the set of alternate
 * playback hosts the player advertises in its "source" dropdown.
 *
 * The backend does not route any media traffic through these; they are
 * simply a list of ``{scheme}://host[:port]`` prefixes that replace the
 * ``public_base_url`` when a viewer picks a different source. Auth tokens
 * and paths on the play URL are preserved.
 */

import {
  CloudServerOutlined,
  DeleteOutlined,
  EditOutlined,
  PlusOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import {
  App,
  Button,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Space,
  Switch,
  Table,
  Tag,
  Typography,
} from 'antd';
import React, { useEffect, useState } from 'react';
import { edgeApi } from '../../api';
import type { EdgeNode } from '../../types';

const { Title, Paragraph } = Typography;

interface FormValues {
  slug: string;
  name: string;
  base_url: string;
  description?: string;
  enabled: boolean;
  sort_order: number;
}

const EdgeManage: React.FC = () => {
  const { message } = App.useApp();
  const [rows, setRows] = useState<EdgeNode[]>([]);
  const [loading, setLoading] = useState(false);
  const [modal, setModal] = useState<{ open: boolean; row?: EdgeNode | null }>({
    open: false,
  });
  const [form] = Form.useForm<FormValues>();

  const load = async () => {
    setLoading(true);
    try {
      const data = await edgeApi.listNodes();
      setRows(data);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const openEdit = (row?: EdgeNode) => {
    form.resetFields();
    if (row) {
      form.setFieldsValue({
        slug: row.slug,
        name: row.name,
        base_url: row.base_url,
        description: row.description,
        enabled: row.enabled,
        sort_order: row.sort_order,
      });
    } else {
      form.setFieldsValue({ enabled: true, sort_order: 0 });
    }
    setModal({ open: true, row });
  };

  const submit = async () => {
    const v = await form.validateFields();
    try {
      if (modal.row) {
        await edgeApi.updateNode(modal.row.id, {
          name: v.name,
          base_url: v.base_url,
          description: v.description ?? '',
          enabled: v.enabled,
          sort_order: v.sort_order,
        });
      } else {
        await edgeApi.createNode({
          slug: v.slug,
          name: v.name,
          base_url: v.base_url,
          description: v.description ?? '',
          enabled: v.enabled,
          sort_order: v.sort_order,
        });
      }
      message.success('已保存');
      setModal({ open: false });
      load();
    } catch (e: unknown) {
      const err = e as { response?: { status?: number; data?: { detail?: string } } };
      if (err.response?.status === 409) {
        message.error('slug 已存在');
      } else {
        message.error(err.response?.data?.detail || '保存失败');
      }
    }
  };

  const del = async (id: number) => {
    await edgeApi.deleteNode(id);
    message.success('已删除');
    load();
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <div>
          <Title level={3} style={{ margin: 0 }}>
            <CloudServerOutlined /> Edge 节点
          </Title>
          <Paragraph type="secondary" style={{ margin: '4px 0 0' }}>
            维护可供观众切换的 CDN / SRS-Edge 节点。观众在播放器中选择节点后，
            前端会把播放 URL 的 host 替换为所选节点的 <code>base_url</code>，
            路径与鉴权参数保持不变。
          </Paragraph>
        </div>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={load}>
            刷新
          </Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => openEdit()}>
            新建节点
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
            title: '顺序',
            dataIndex: 'sort_order',
            width: 70,
          },
          {
            title: 'Slug',
            dataIndex: 'slug',
            render: (v: string) => <code>{v}</code>,
          },
          { title: '名称', dataIndex: 'name' },
          {
            title: 'base_url',
            dataIndex: 'base_url',
            render: (v: string) => <code>{v}</code>,
          },
          {
            title: '状态',
            dataIndex: 'enabled',
            width: 100,
            render: (v: boolean) =>
              v ? <Tag color="green">启用</Tag> : <Tag>停用</Tag>,
          },
          { title: '备注', dataIndex: 'description', ellipsis: true },
          {
            title: '操作',
            width: 160,
            render: (_, r) => (
              <Space>
                <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(r)}>
                  编辑
                </Button>
                <Popconfirm title="删除此节点?" onConfirm={() => del(r.id)}>
                  <Button size="small" danger icon={<DeleteOutlined />} />
                </Popconfirm>
              </Space>
            ),
          },
        ]}
      />

      <Modal
        open={modal.open}
        title={modal.row ? '编辑 Edge 节点' : '新建 Edge 节点'}
        onCancel={() => setModal({ open: false })}
        onOk={submit}
        destroyOnHidden
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="slug"
            label="Slug (唯一标识)"
            rules={[
              {
                required: true,
                pattern: /^[a-zA-Z0-9][a-zA-Z0-9_-]{0,62}$/,
                message: '仅支持字母数字、下划线和连字符',
              },
            ]}
          >
            <Input
              placeholder="例如 hk-1 / us-west-1"
              disabled={!!modal.row}
            />
          </Form.Item>
          <Form.Item
            name="name"
            label="显示名称"
            rules={[{ required: true, message: '请输入名称' }]}
          >
            <Input placeholder="例如 香港 Edge / 美西 CDN" />
          </Form.Item>
          <Form.Item
            name="base_url"
            label="base_url"
            extra="形如 https://edge-hk.example.com。不要以 / 结尾，也不要带路径；协议省略时默认 https。"
            rules={[{ required: true, message: '请输入 base_url' }]}
          >
            <Input placeholder="https://edge-hk.example.com" />
          </Form.Item>
          <Form.Item name="description" label="备注">
            <Input.TextArea rows={2} placeholder="可填地域、带宽等说明" />
          </Form.Item>
          <Form.Item name="sort_order" label="排序" tooltip="数值越小越靠前">
            <InputNumber min={0} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="enabled" label="启用" valuePropName="checked">
            <Switch checkedChildren="启用" unCheckedChildren="停用" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default EdgeManage;
