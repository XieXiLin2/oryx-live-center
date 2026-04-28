import { DeleteOutlined, EditOutlined, PlusOutlined, ReloadOutlined } from '@ant-design/icons';
import {
  Button,
  Card,
  Form,
  Input,
  message,
  Modal,
  Select,
  Space,
  Table,
  Tag,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import React, { useEffect, useState } from 'react';
import { transcodeApi, type TranscodeProfile } from '../../api/transcode';

const TranscodeProfiles: React.FC = () => {
  const [profiles, setProfiles] = useState<TranscodeProfile[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [editingProfile, setEditingProfile] = useState<TranscodeProfile | null>(null);
  const [form] = Form.useForm();

  const loadProfiles = async () => {
    setLoading(true);
    try {
      const { data } = await transcodeApi.listProfiles();
      setProfiles(data.profiles);
    } catch {
      message.error('加载转码配置失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadProfiles();
  }, []);

  const handleCreate = () => {
    setEditingProfile(null);
    form.resetFields();
    setModalVisible(true);
  };

  const handleEdit = (profile: TranscodeProfile) => {
    setEditingProfile(profile);
    form.setFieldsValue(profile);
    setModalVisible(true);
  };

  const handleDelete = async (id: number) => {
    try {
      await transcodeApi.deleteProfile(id);
      message.success('删除成功');
      loadProfiles();
    } catch {
      message.error('删除失败');
    }
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      if (editingProfile) {
        await transcodeApi.updateProfile(editingProfile.id, values);
        message.success('更新成功');
      } else {
        await transcodeApi.createProfile(values);
        message.success('创建成功');
      }
      setModalVisible(false);
      loadProfiles();
    } catch {
      message.error('操作失败');
    }
  };

  const columns: ColumnsType<TranscodeProfile> = [
    {
      title: '配置名称',
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
    },
    {
      title: '源协议',
      dataIndex: 'source_protocol',
      key: 'source_protocol',
      render: (protocol: string) => <Tag>{protocol.toUpperCase()}</Tag>,
    },
    {
      title: '输出数量',
      key: 'outputs',
      render: (_, record) => record.outputs?.length || 0,
    },
    {
      title: '延迟模式',
      dataIndex: 'latency_mode',
      key: 'latency_mode',
      render: (mode: string) => <Tag color="blue">{mode}</Tag>,
    },
    {
      title: '操作',
      key: 'action',
      render: (_, record) => (
        <Space>
          <Button
            type="link"
            icon={<EditOutlined />}
            onClick={() => handleEdit(record)}
          >
            编辑
          </Button>
          <Button
            type="link"
            danger
            icon={<DeleteOutlined />}
            onClick={() => handleDelete(record.id)}
          >
            删除
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <>
      <Card
        title="转码配置"
        extra={
          <Space>
            <Button icon={<ReloadOutlined />} onClick={loadProfiles}>
              刷新
            </Button>
            <Button type="primary" icon={<PlusOutlined />} onClick={handleCreate}>
              新建配置
            </Button>
          </Space>
        }
      >
        <Table
          columns={columns}
          dataSource={profiles}
          rowKey="id"
          loading={loading}
          pagination={false}
        />
      </Card>

      <Modal
        title={editingProfile ? '编辑转码配置' : '新建转码配置'}
        open={modalVisible}
        onOk={handleSubmit}
        onCancel={() => setModalVisible(false)}
        width={600}
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="name"
            label="配置名称"
            rules={[{ required: true, message: '请输入配置名称' }]}
          >
            <Input />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item
            name="source_protocol"
            label="源协议"
            rules={[{ required: true, message: '请选择源协议' }]}
          >
            <Select>
              <Select.Option value="rtmp">RTMP</Select.Option>
              <Select.Option value="srt">SRT</Select.Option>
              <Select.Option value="whip">WHIP</Select.Option>
            </Select>
          </Form.Item>
          <Form.Item
            name="latency_mode"
            label="延迟模式"
            rules={[{ required: true, message: '请选择延迟模式' }]}
          >
            <Select>
              <Select.Option value="ultra_low">超低延迟</Select.Option>
              <Select.Option value="low">低延迟</Select.Option>
              <Select.Option value="normal">正常</Select.Option>
            </Select>
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
};

export default TranscodeProfiles;
