import { DeleteOutlined, ReloadOutlined } from '@ant-design/icons';
import { Button, Card, message, Space, Table, Tag } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import React, { useEffect, useState } from 'react';
import { transcodeApi, type TranscodeNode } from '../../api/transcode';

const TranscodeNodes: React.FC = () => {
  const [nodes, setNodes] = useState<TranscodeNode[]>([]);
  const [loading, setLoading] = useState(false);

  const loadNodes = async () => {
    setLoading(true);
    try {
      const { data } = await transcodeApi.listNodes();
      setNodes(data.nodes);
    } catch {
      message.error('加载转码节点失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadNodes();
  }, []);

  const handleDelete = async (nodeId: string) => {
    try {
      await transcodeApi.deleteNode(nodeId);
      message.success('删除成功');
      loadNodes();
    } catch {
      message.error('删除失败');
    }
  };

  const columns: ColumnsType<TranscodeNode> = [
    {
      title: '节点名称',
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: '地域',
      dataIndex: 'region',
      key: 'region',
      render: (region: string) => <Tag color="blue">{region}</Tag>,
    },
    {
      title: 'IP 地址',
      dataIndex: 'ip_address',
      key: 'ip_address',
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => {
        const color = status === 'online' ? 'green' : status === 'busy' ? 'orange' : 'red';
        return <Tag color={color}>{status}</Tag>;
      },
    },
    {
      title: '任务',
      key: 'tasks',
      render: (_, record) => `${record.current_tasks} / ${record.max_tasks}`,
    },
    {
      title: 'CPU',
      dataIndex: 'cpu_usage',
      key: 'cpu_usage',
      render: (usage?: number) => usage ? `${usage.toFixed(1)}%` : '-',
    },
    {
      title: '内存',
      dataIndex: 'memory_usage',
      key: 'memory_usage',
      render: (usage?: number) => usage ? `${usage.toFixed(1)}%` : '-',
    },
    {
      title: 'GPU',
      dataIndex: 'gpu_usage',
      key: 'gpu_usage',
      render: (usage?: number) => usage ? `${usage.toFixed(1)}%` : '-',
    },
    {
      title: '延迟',
      dataIndex: 'network_latency',
      key: 'network_latency',
      render: (latency?: number) => latency ? `${latency}ms` : '-',
    },
    {
      title: '操作',
      key: 'action',
      render: (_, record) => (
        <Button
          type="link"
          danger
          icon={<DeleteOutlined />}
          onClick={() => handleDelete(record.id)}
        >
          删除
        </Button>
      ),
    },
  ];

  return (
    <Card
      title="转码节点"
      extra={
        <Space>
          <Button icon={<ReloadOutlined />} onClick={loadNodes}>
            刷新
          </Button>
        </Space>
      }
    >
      <Table
        columns={columns}
        dataSource={nodes}
        rowKey="id"
        loading={loading}
        pagination={false}
      />
    </Card>
  );
};

export default TranscodeNodes;
