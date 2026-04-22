import { Card, Col, Row, Spin, Statistic, Table, Tag, Typography } from 'antd';
import React, { useEffect, useState } from 'react';
import { adminApi } from '../../api';

const { Title } = Typography;

type SrsSelf = {
  cpu_percent?: number;
  mem_percent?: number;
  version?: string;
};
type SrsSummary = {
  data?: { self?: SrsSelf; version?: string } & SrsSelf;
  self?: SrsSelf;
  version?: string;
};

interface SrsStreamRow {
  id?: string;
  name?: string;
  app?: string;
  clients?: number;
  video?: { codec?: string } | null;
  audio?: { codec?: string } | null;
  publish?: { active?: boolean };
}
type SrsStreamListResponse = { streams?: SrsStreamRow[] };

const Dashboard: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [summary, setSummary] = useState<SrsSummary | null>(null);
  const [srsStreams, setSrsStreams] = useState<SrsStreamRow[]>([]);

  const load = async () => {
    try {
      const [s, st] = await Promise.all([
        adminApi.getSrsSummary().catch(() => null) as Promise<SrsSummary | null>,
        adminApi.getSrsStreams().catch(() => ({ streams: [] })) as Promise<
          SrsStreamListResponse | SrsStreamRow[]
        >,
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

  const srs: SrsSelf = summary?.data?.self ?? summary?.self ?? {};
  const version = summary?.data?.self?.version ?? summary?.data?.version ?? summary?.version ?? '—';
  const onlineStreams = srsStreams.filter((s) => s.publish?.active).length;

  return (
    <div>
      <Title level={3}>总览</Title>
      <Row gutter={16}>
        <Col span={6}>
          <Card>
            <Statistic title="CPU" value={srs.cpu_percent ?? 0} suffix="%" precision={1} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="内存" value={srs.mem_percent ?? 0} suffix="%" precision={1} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="在线流" value={onlineStreams} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="SRS 版本" value={version} />
          </Card>
        </Col>
      </Row>

      <Card title="实时流列表" style={{ marginTop: 24 }}>
        <Table<SrsStreamRow>
          rowKey={(r) => r.id ?? `${r.app}/${r.name}`}
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
              render: (v: SrsStreamRow['video']) => (v?.codec ? <Tag>{v.codec}</Tag> : '—'),
            },
            {
              title: '音频',
              dataIndex: 'audio',
              render: (a: SrsStreamRow['audio']) => (a?.codec ? <Tag>{a.codec}</Tag> : '—'),
            },
            {
              title: '状态',
              dataIndex: 'publish',
              render: (p: SrsStreamRow['publish']) =>
                p?.active ? <Tag color="green">直播中</Tag> : <Tag>离线</Tag>,
            },
          ]}
        />
      </Card>
    </div>
  );
};

export default Dashboard;
