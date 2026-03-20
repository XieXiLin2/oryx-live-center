import { DeleteOutlined, ReloadOutlined, TeamOutlined } from '@ant-design/icons';
import { Button, message, Popconfirm, Table, Tag, Typography } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import React, { useCallback, useEffect, useState } from 'react';
import { adminApi } from '../../api';

const { Title } = Typography;

interface ClientInfo {
  id: string;
  vhost: string;
  stream: string;
  ip: string;
  url: string;
  type: string;
  publish: boolean;
  alive: number;
}

const OryxClients: React.FC = () => {
  const [clients, setClients] = useState<ClientInfo[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchClients = useCallback(async () => {
    setLoading(true);
    try {
      const data = await adminApi.getClients();
      setClients(data?.clients || []);
    } catch {
      message.error('获取客户端列表失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchClients();
  }, [fetchClients]);

  const handleKick = async (clientId: string) => {
    try {
      await adminApi.kickClient(clientId);
      message.success('已踢出客户端');
      fetchClients();
    } catch {
      message.error('操作失败');
    }
  };

  const columns: ColumnsType<ClientInfo> = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 80 },
    { title: 'IP', dataIndex: 'ip', key: 'ip' },
    { title: '流', dataIndex: 'stream', key: 'stream' },
    { title: 'URL', dataIndex: 'url', key: 'url', ellipsis: true },
    {
      title: '类型',
      key: 'type',
      render: (_, record) => (
        <Tag color={record.publish ? 'red' : 'blue'}>
          {record.publish ? '推流' : '播放'}
        </Tag>
      ),
    },
    {
      title: '在线时长(s)',
      dataIndex: 'alive',
      key: 'alive',
      render: (v: number) => Math.round(v),
    },
    {
      title: '操作',
      key: 'actions',
      render: (_, record) => (
        <Popconfirm title="确定踢出此客户端？" onConfirm={() => handleKick(record.id)}>
          <Button size="small" danger icon={<DeleteOutlined />}>踢出</Button>
        </Popconfirm>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>
          <TeamOutlined /> 客户端管理
        </Title>
        <Button icon={<ReloadOutlined />} onClick={fetchClients} loading={loading}>
          刷新
        </Button>
      </div>
      <Table columns={columns} dataSource={clients} rowKey="id" loading={loading} />
    </div>
  );
};

export default OryxClients;
