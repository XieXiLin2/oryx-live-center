import { DeleteOutlined, EditOutlined, LockOutlined, PlusOutlined, VideoCameraOutlined } from '@ant-design/icons';
import { Button, Form, Input, message, Modal, Popconfirm, Space, Switch, Table, Tag, Typography } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import React, { useCallback, useEffect, useState } from 'react';
import { streamApi } from '../../api';
import type { StreamConfig } from '../../types';

const { Title } = Typography;

const StreamsManage: React.FC = () => {
  const [configs, setConfigs] = useState<StreamConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingName, setEditingName] = useState<string | null>(null);
  const [form] = Form.useForm();

  const fetchConfigs = useCallback(async () => {
    setLoading(true);
    try {
      const data = await streamApi.listConfigs();
      setConfigs(data);
    } catch {
      message.error('获取配置失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchConfigs();
  }, [fetchConfigs]);

  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      const streamName = editingName || values.stream_name;
      await streamApi.updateConfig(streamName, {
        display_name: values.display_name,
        is_encrypted: values.is_encrypted,
        encryption_key: values.encryption_key,
        require_auth: values.require_auth,
      });
      message.success('保存成功');
      setModalOpen(false);
      form.resetFields();
      setEditingName(null);
      fetchConfigs();
    } catch {
      message.error('保存失败');
    }
  };

  const handleDelete = async (streamName: string) => {
    try {
      await streamApi.deleteConfig(streamName);
      message.success('已删除');
      fetchConfigs();
    } catch {
      message.error('删除失败');
    }
  };

  const openEdit = (config: StreamConfig) => {
    setEditingName(config.stream_name);
    form.setFieldsValue({
      stream_name: config.stream_name,
      display_name: config.display_name,
      is_encrypted: config.is_encrypted,
      require_auth: config.require_auth,
      encryption_key: '',
    });
    setModalOpen(true);
  };

  const openCreate = () => {
    setEditingName(null);
    form.resetFields();
    setModalOpen(true);
  };

  const columns: ColumnsType<StreamConfig> = [
    { title: '流名称', dataIndex: 'stream_name', key: 'stream_name' },
    { title: '显示名称', dataIndex: 'display_name', key: 'display_name' },
    {
      title: '状态',
      key: 'status',
      render: (_, record) => (
        <Space>
          {record.is_encrypted && <Tag icon={<LockOutlined />} color="orange">加密</Tag>}
          {record.require_auth && <Tag color="purple">需登录</Tag>}
        </Space>
      ),
    },
    {
      title: '更新时间',
      dataIndex: 'updated_at',
      key: 'updated_at',
      render: (v: string) => new Date(v).toLocaleString(),
    },
    {
      title: '操作',
      key: 'actions',
      render: (_, record) => (
        <Space>
          <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(record)}>
            编辑
          </Button>
          <Popconfirm title="确定删除此配置？" onConfirm={() => handleDelete(record.stream_name)}>
            <Button size="small" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>
          <VideoCameraOutlined /> 直播管理
        </Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
          添加配置
        </Button>
      </div>

      <Table
        columns={columns}
        dataSource={configs}
        rowKey="id"
        loading={loading}
      />

      <Modal
        title={editingName ? '编辑直播配置' : '新建直播配置'}
        open={modalOpen}
        onOk={handleSave}
        onCancel={() => { setModalOpen(false); form.resetFields(); setEditingName(null); }}
        okText="保存"
        cancelText="取消"
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="stream_name"
            label="流名称"
            rules={[{ required: !editingName, message: '请输入流名称' }]}
          >
            <Input disabled={!!editingName} placeholder="例如：livestream" />
          </Form.Item>
          <Form.Item name="display_name" label="显示名称">
            <Input placeholder="例如：我的直播" />
          </Form.Item>
          <Form.Item name="is_encrypted" label="启用加密" valuePropName="checked">
            <Switch />
          </Form.Item>
          <Form.Item name="encryption_key" label="加密密钥">
            <Input.Password placeholder="留空则不修改" />
          </Form.Item>
          <Form.Item name="require_auth" label="需要登录观看" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default StreamsManage;
