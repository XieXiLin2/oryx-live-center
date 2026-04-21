import { Card, Col, Row, Spin, Statistic, Table, Tag, Typography } from 'antd';
import React, { useEffect, useState } from 'react';
import { adminApi } from '../../api';

const { Title } = Typography;

const Dashboard: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [summary, setSummary] = useState<any>(null);
  const [srsStreams, setSrsStreams] = useState<any[]>([]);

  const load = async () => {
    try {
      const [s, st] = await Promise.all([
        adminApi.getSrsSummary().catch(() => null),
        adminApi.getSrsStreams().catch(() => ({ streams: [] })),
      ]);
      setSummary(s);
      setSrsStreams(Array.isArray(st) ? st : st?.streams ?? []);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    const t = setInterval(load, 10000);
    return () => clearInterval(t);
  }, []);

  if (loading) return <Spin size="large" />;

  const srs = summary?.data?.self ?? summary?.self ?? {};

  return (
    <div>
      <Title level={3}>总览</Title>
      <Row gutter={16}>
        <Col span={6}>
          <Card><Statistic title="CPU" value={srs?.cpu_percent ?? 0} suffix="%" precision={1} /></Card>
        </Col>
        <Col span={6}>
          <Card><Statistic title="内存" value={(srs?.mem_percent ?? 0)} suffix="%" precision={1} /></Card>
        </Col>
        <Col span={6}>
          <Card><Statistic title="在线流" value={srsStreams.length} /></Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="SRS 版本"
              value={summary?.data?.version ?? summary?.version ?? '—'}
            />
          </Card>
        </Col>
      </Row>

      <Card title="实时流列表" style={{ marginTop: 24 }}>
        <Table
          rowKey="id"
          size="small"
          dataSource={srsStreams}
          pagination={false}
          columns={[
            { title: '流名', dataIndex: 'name' },
            { title: '应用', dataIndex: 'app' },
            { title: '观众', dataIndex: 'clients' },
            {
              title: '视频',
              dataIndex: 'video',
              render: (v: any) => v?.codec ? <Tag>{v.codec}</Tag> : '—',
            },
            {
              title: '音频',
              dataIndex: 'audio',
              render: (a: any) => a?.codec ? <Tag>{a.codec}</Tag> : '—',
            },
            {
              title: '状态',
              dataIndex: 'publish',
              render: (p: any) => p?.active ? <Tag color="green">直播中</Tag> : <Tag>离线</Tag>,
            },
          ]}
        />
      </Card>
    </div>
  );
};

export default Dashboard;
