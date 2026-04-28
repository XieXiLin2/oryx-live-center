import {
  DeleteOutlined,
  PauseOutlined,
  PlayCircleOutlined,
  PlusOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
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
import { transcodeApi, type TranscodeProfile, type TranscodeTask } from '../../api/transcode';

const TranscodeTasks: React.FC = () => {
  const [tasks, setTasks] = useState<TranscodeTask[]>([]);
  const [profiles, setProfiles] = useState<TranscodeProfile[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [form] = Form.useForm();

  const loadTasks = async () => {
    setLoading(true);
    try {
      const { data } = await transcodeApi.listTasks();
      setTasks(data.tasks);
    } catch {
      message.error('加载转码任务失败');
    } finally {
      setLoading(false);
    }
  };

  const loadProfiles = async () => {
    try {
      const { data } = await transcodeApi.listProfiles();
      setProfiles(data.profiles);
    } catch (err) {
      console.error('加载转码配置失败', err);
    }
  };

  useEffect(() => {
    loadTasks();
    loadProfiles();
  }, []);

  const handleCreate = () => {
    form.resetFields();
    setModalVisible(true);
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      await transcodeApi.createTask(values);
      message.success('创建成功');
      setModalVisible(false);
      loadTasks();
    } catch {
      message.error('创建失败');
    }
  };

  const handleStart = async (id: number) => {
    try {
      await transcodeApi.startTask(id);
      message.success('启动成功');
      loadTasks();
    } catch {
      message.error('启动失败');
    }
  };

  const handleStop = async (id: number) => {
    try {
      await transcodeApi.stopTask(id);
      message.success('停止成功');
      loadTasks();
    } catch {
      message.error('停止失败');
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await transcodeApi.deleteTask(id);
      message.success('删除成功');
      loadTasks();
    } catch {
      message.error('删除失败');
    }
  };

  const columns: ColumnsType<TranscodeTask> = [
    {
      title: '任务 ID',
      dataIndex: 'id',
      key: 'id',
    },
    {
      title: '直播间',
      dataIndex: 'stream_name',
      key: 'stream_name',
    },
    {
      title: '配置 ID',
      dataIndex: 'profile_id',
      key: 'profile_id',
    },
    {
      title: '节点 ID',
      dataIndex: 'node_id',
      key: 'node_id',
      render: (nodeId?: string) => nodeId || '-',
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => {
        const colorMap: Record<string, string> = {
          pending: 'default',
          running: 'green',
          stopped: 'orange',
          failed: 'red',
        };
        return <Tag color={colorMap[status] || 'default'}>{status}</Tag>;
      },
    },
    {
      title: '开始时间',
      dataIndex: 'started_at',
      key: 'started_at',
      render: (time?: string) => time ? new Date(time).toLocaleString() : '-',
    },
    {
      title: '操作',
      key: 'action',
      render: (_, record) => (
        <Space>
          {record.status === 'pending' || record.status === 'stopped' ? (
            <Button
              type="link"
              icon={<PlayCircleOutlined />}
              onClick={() => handleStart(record.id)}
            >
              启动
            </Button>
          ) : null}
          {record.status === 'running' ? (
            <Button
              type="link"
              icon={<PauseOutlined />}
              onClick={() => handleStop(record.id)}
            >
              停止
            </Button>
          ) : null}
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
        title="转码任务"
        extra={
          <Space>
            <Button icon={<ReloadOutlined />} onClick={loadTasks}>
              刷新
            </Button>
            <Button type="primary" icon={<PlusOutlined />} onClick={handleCreate}>
              新建任务
            </Button>
          </Space>
        }
      >
        <Table
          columns={columns}
          dataSource={tasks}
          rowKey="id"
          loading={loading}
          pagination={{ pageSize: 20 }}
        />
      </Card>

      <Modal
        title="新建转码任务"
        open={modalVisible}
        onOk={handleSubmit}
        onCancel={() => setModalVisible(false)}
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="stream_name"
            label="直播间名称"
            rules={[{ required: true, message: '请输入直播间名称' }]}
          >
            <Input placeholder="例如: demo" />
          </Form.Item>
          <Form.Item
            name="profile_id"
            label="转码配置"
            rules={[{ required: true, message: '请选择转码配置' }]}
          >
            <Select placeholder="选择转码配置">
              {profiles.map((profile) => (
                <Select.Option key={profile.id} value={profile.id}>
                  {profile.name}
                </Select.Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item name="region" label="地域">
            <Select placeholder="选择地域（可选）">
              <Select.Option value="beijing">北京</Select.Option>
              <Select.Option value="shanghai">上海</Select.Option>
              <Select.Option value="guangzhou">广州</Select.Option>
            </Select>
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
};

export default TranscodeTasks;
