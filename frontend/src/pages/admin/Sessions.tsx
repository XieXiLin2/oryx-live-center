import { ReloadOutlined } from '@ant-design/icons';
import { Button, Input, Space, Table, Tabs, Tag, Typography } from 'antd';
import React, { useCallback, useEffect, useState } from 'react';
import { adminApi } from '../../api';
import type { StreamPlaySessionItem, StreamPublishSessionItem } from '../../types';

const { Title } = Typography;

const fmtDuration = (s: number) => {
  if (!s) return '—';
  const m = Math.floor(s / 60);
  const sec = s % 60;
  return m ? `${m}m ${sec}s` : `${sec}s`;
};

const Sessions: React.FC = () => {
  const [filter, setFilter] = useState('');
  const [plays, setPlays] = useState<StreamPlaySessionItem[]>([]);
  const [pubs, setPubs] = useState<StreamPublishSessionItem[]>([]);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [p, pb] = await Promise.all([
        adminApi.getPlaySessions(filter, 200, 0),
        adminApi.getPublishSessions(filter, 200, 0),
      ]);
      setPlays(p);
      setPubs(pb);
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Title level={3} style={{ margin: 0 }}>播放统计</Title>
        <Space>
          <Input.Search
            placeholder="按流名筛选"
            allowClear
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            onSearch={load}
            style={{ width: 240 }}
          />
          <Button icon={<ReloadOutlined />} onClick={load}>刷新</Button>
        </Space>
      </div>

      <Tabs
        items={[
          {
            key: 'play',
            label: '观看会话',
            children: (
              <Table<StreamPlaySessionItem>
                rowKey="id"
                loading={loading}
                dataSource={plays}
                size="small"
                pagination={{ pageSize: 30 }}
                columns={[
                  { title: '#', dataIndex: 'id', width: 70 },
                  { title: '流名', dataIndex: 'stream_name' },
                  { title: '用户', dataIndex: 'user_id', render: (v) => v ?? <Tag>游客</Tag> },
                  { title: 'IP', dataIndex: 'client_ip' },
                  { title: '开始', dataIndex: 'started_at' },
                  {
                    title: '状态',
                    dataIndex: 'ended_at',
                    render: (v) => v ? <Tag>已结束</Tag> : <Tag color="green">观看中</Tag>,
                  },
                  { title: '时长', dataIndex: 'duration_seconds', render: fmtDuration },
                ]}
              />
            ),
          },
          {
            key: 'publish',
            label: '推流会话',
            children: (
              <Table<StreamPublishSessionItem>
                rowKey="id"
                loading={loading}
                dataSource={pubs}
                size="small"
                pagination={{ pageSize: 30 }}
                columns={[
                  { title: '#', dataIndex: 'id', width: 70 },
                  { title: '流名', dataIndex: 'stream_name' },
                  { title: 'IP', dataIndex: 'client_ip' },
                  { title: '开始', dataIndex: 'started_at' },
                  {
                    title: '状态',
                    dataIndex: 'ended_at',
                    render: (v) => v ? <Tag>已下播</Tag> : <Tag color="green">直播中</Tag>,
                  },
                  { title: '时长', dataIndex: 'duration_seconds', render: fmtDuration },
                ]}
              />
            ),
          },
        ]}
      />
    </div>
  );
};

export default Sessions;
