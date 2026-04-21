import { DisconnectOutlined, ReloadOutlined } from '@ant-design/icons';
import { App, Button, Popconfirm, Space, Table, Tag, Typography } from 'antd';
import React, { useEffect, useState } from 'react';
import { adminApi } from '../../api';

const { Title } = Typography;

const SrsClients: React.FC = () => {
  const { message } = App.useApp();
  const [rows, setRows] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const data: any = await adminApi.getSrsClients();
      const list = Array.isArray(data) ? data : data?.clients ?? [];
      setRows(list);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    const t = setInterval(load, 10000);
    return () => clearInterval(t);
  }, []);

  const kick = async (id: string) => {
    await adminApi.kickSrsClient(id);
    message.success('已踢出');
    load();
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Title level={3} style={{ margin: 0 }}>SRS 客户端</Title>
        <Button icon={<ReloadOutlined />} onClick={load}>刷新</Button>
      </div>

      <Table
        rowKey="id"
        loading={loading}
        dataSource={rows}
        size="small"
        pagination={{ pageSize: 50 }}
        columns={[
          { title: 'ID', dataIndex: 'id', width: 120 },
          { title: '类型', dataIndex: 'type', render: (v) => <Tag>{v}</Tag> },
          { title: '流', render: (_, r) => `${r.vhost || ''}/${r.app || ''}/${r.stream || ''}` },
          { title: 'IP', dataIndex: 'ip' },
          { title: '协议', dataIndex: 'publish', render: (p: any) => p?.active ? <Tag color="green">推流</Tag> : <Tag color="blue">播放</Tag> },
          { title: '时长', dataIndex: 'alive', render: (v: number) => v ? `${Math.floor(v)}s` : '—' },
          {
            title: '操作',
            render: (_, r) => (
              <Popconfirm title="断开该客户端?" onConfirm={() => kick(r.id)}>
                <Button size="small" danger icon={<DisconnectOutlined />}>踢出</Button>
              </Popconfirm>
            ),
          },
        ]}
      />
    </div>
  );
};

export default SrsClients;
