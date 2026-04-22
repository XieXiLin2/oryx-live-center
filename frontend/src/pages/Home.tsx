import {
  EyeOutlined,
  LockOutlined,
  PlayCircleOutlined,
  ReloadOutlined,
  VideoCameraOutlined,
} from '@ant-design/icons';
import {
  Button,
  Card,
  Col,
  Empty,
  Row,
  Space,
  Spin,
  Tag,
  Typography,
} from 'antd';
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { streamApi } from '../api';
import { useAuth } from '../store/auth';
import { usePageTitle } from '../store/branding';
import type { StreamInfo } from '../types';


/**
 * Rewrite the host portion of a play URL with the Edge node's base_url.
 *
 * The backend's `/api/streams/play` always returns URLs prefixed by
 * ``public_base_url`` (or a relative path if that isn't configured). To switch
 * playback to an Edge node we strip that prefix and splice in the node's
 * ``base_url`` — preserving path + query (so the watch token survives).
 *
 * If the rewrite cannot be performed (e.g. original URL was relative), the
 * original URL is returned unchanged.
 */
function applyEdgeRewrite(originalUrl: string, edgeBaseUrl: string): string {
  if (!originalUrl) return originalUrl;
  // Full absolute URL: `https://origin.example.com/live/demo.flv?token=x`
  if (/^https?:\/\//i.test(originalUrl)) {
    try {
      const u = new URL(originalUrl);
      const eb = new URL(edgeBaseUrl);
      return `${eb.origin}${u.pathname}${u.search}${u.hash}`;
    } catch {
      return originalUrl;
    }
  }
  // Relative URL (no origin configured server-side). Prefix with the edge.
  try {
    const eb = new URL(edgeBaseUrl);
    const path = originalUrl.startsWith('/') ? originalUrl : `/${originalUrl}`;
    return `${eb.origin}${path}`;
  } catch {
    return originalUrl;
  }
}


const { Title, Text } = Typography;

const Home: React.FC = () => {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [streams, setStreams] = useState<StreamInfo[]>([]);
  const [loading, setLoading] = useState(true);

  usePageTitle('主页');

  // Handle backward compatibility: ?room=roomname redirects to /live/roomname
  useEffect(() => {
    const roomParam = searchParams.get('room');
    if (roomParam) {
      const token = searchParams.get('token');
      navigate(token ? `/live/${roomParam}?token=${token}` : `/live/${roomParam}`, {
        replace: true,
      });
    }
  }, [searchParams, navigate]);

  const fetchStreams = useCallback(async () => {
    setLoading(true);
    try {
      const data = await streamApi.list();
      setStreams(data.streams);
      return data.streams;
    } catch (err) {
      console.error('Failed to fetch streams:', err);
      return [];
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStreams();
    const interval = setInterval(fetchStreams, 5000);
    return () => clearInterval(interval);
  }, [fetchStreams]);

  const handleStreamClick = useCallback(
    (stream: StreamInfo) => {
      navigate(`/live/${stream.name}`);
    },
    [navigate],
  );

  const publicStreams = useMemo(() => streams.filter((s) => !s.is_private), [streams]);
  const privateStreams = useMemo(() => streams.filter((s) => s.is_private), [streams]);

  // Resolve the actual URL fed to <LivePlayer> after applying the Edge
  // rewrite. When the user picks "origin" (or no sources are loaded yet),
  // the original URL is used verbatim.
  const resolvedPlayUrl = useMemo(() => {
    if (!playData?.url) return '';
    if (!sources || selectedSource === 'origin') return playData.url;
    const edge = sources.edges.find((e) => e.slug === selectedSource);
    if (!edge || !edge.base_url) return playData.url;
    return applyEdgeRewrite(playData.url, edge.base_url);
  }, [playData, sources, selectedSource]);

  // Source-selector options. "Origin" is always present; enabled edges come
  // from the backend in their configured order.
  const sourceOptions = useMemo(() => {
    const opts: { label: string; value: string }[] = [{ label: 'Origin', value: 'origin' }];
    if (sources) {
      sources.edges.forEach((e) => opts.push({ label: e.name, value: e.slug }));
    }
    return opts;
  }, [sources]);


  const renderStreamCard = (stream: StreamInfo) => (
    <Col xs={24} sm={12} md={8} lg={6} key={stream.name}>
      <Card
        hoverable
        onClick={() => handleStreamClick(stream)}
        styles={{ body: { padding: 16 } }}
      >
        <div style={{ display: 'flex', alignItems: 'center', marginBottom: 8 }}>
          <VideoCameraOutlined
            style={{ fontSize: 20, color: stream.is_live ? '#f5222d' : '#bfbfbf', marginRight: 8 }}
          />
          <Text strong ellipsis style={{ flex: 1 }}>
            {stream.display_name}
          </Text>
        </div>
        <Space wrap size={4}>
          {stream.is_live ? <Tag color="red">LIVE</Tag> : <Tag>离线</Tag>}
          <Tag>
            <EyeOutlined /> {stream.clients}
          </Tag>
          {stream.is_private && (
            <Tag icon={<LockOutlined />} color="purple">
              私有
            </Tag>
          )}
          {!stream.chat_enabled && <Tag>弹幕关闭</Tag>}
        </Space>
        <div style={{ marginTop: 8 }}>
          {stream.formats.map((f) => (
            <Tag key={f} style={{ fontSize: 11 }}>
              {f.toUpperCase()}
            </Tag>
          ))}
        </div>
      </Card>
    </Col>
  );

  return (
    <div>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 16,
        }}
      >
        <Title level={4} style={{ margin: 0 }}>
          <PlayCircleOutlined /> 直播间
        </Title>
        <Button icon={<ReloadOutlined />} onClick={fetchStreams} loading={loading}>
          刷新
        </Button>
      </div>

      {loading && streams.length === 0 ? (
        <div style={{ textAlign: 'center', padding: 60 }}>
          <Spin size="large" />
        </div>
      ) : streams.length === 0 ? (
        <Empty description="暂无直播间" />
      ) : (
        <>
          {publicStreams.length > 0 && (
            <>
              <Title level={5} style={{ marginTop: 8 }}>
                公开直播
              </Title>
              <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
                {publicStreams.map(renderStreamCard)}
              </Row>
            </>
          )}
          {privateStreams.length > 0 && (
            <>
              <Title level={5}>
                <LockOutlined /> 私有直播
              </Title>
              <Row gutter={[16, 16]}>{privateStreams.map(renderStreamCard)}</Row>
            </>
          )}
        </>
      )}
    </div>
  );
};

export default Home;
