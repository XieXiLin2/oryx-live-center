import {
  EyeOutlined,
  KeyOutlined,
  LockOutlined,
  PlayCircleOutlined,
  ReloadOutlined,
  VideoCameraOutlined,
} from '@ant-design/icons';
import {
  Alert,
  Button,
  Card,
  Col,
  Empty,
  Input,
  message,
  Modal,
  Row,
  Select,
  Space,
  Spin,
  Tag,
  Typography,
} from 'antd';
import React, { useCallback, useEffect, useState } from 'react';
import { streamApi } from '../api';
import ChatPanel from '../components/ChatPanel';
import LivePlayer from '../components/LivePlayer';
import { useAuth } from '../store/auth';
import type { StreamInfo, StreamPlayResponse } from '../types';

const { Title, Text } = Typography;

const Home: React.FC = () => {
  const { user, login } = useAuth();
  const [streams, setStreams] = useState<StreamInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedStream, setSelectedStream] = useState<StreamInfo | null>(null);
  const [selectedFormat, setSelectedFormat] = useState<string>('flv');
  const [playData, setPlayData] = useState<StreamPlayResponse | null>(null);
  const [keyModalOpen, setKeyModalOpen] = useState(false);
  const [streamKey, setStreamKey] = useState('');

  const fetchStreams = useCallback(async () => {
    setLoading(true);
    try {
      const data = await streamApi.list();
      setStreams(data.streams);
    } catch (err) {
      console.error('Failed to fetch streams:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStreams();
    const interval = setInterval(fetchStreams, 15000);
    return () => clearInterval(interval);
  }, [fetchStreams]);

  const handlePlay = async (stream: StreamInfo, format: string, key?: string) => {
    // Check if auth required
    if (stream.require_auth && !user) {
      message.warning('此直播需要登录后观看');
      login();
      return;
    }

    // Check if encrypted
    if (stream.is_encrypted && !key) {
      setSelectedStream(stream);
      setSelectedFormat(format);
      setKeyModalOpen(true);
      return;
    }

    try {
      const data = await streamApi.play(stream.name, format, key);
      setPlayData(data);
      setSelectedStream(stream);
      setSelectedFormat(format);
      setKeyModalOpen(false);
      setStreamKey('');
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } };
      message.error(error.response?.data?.detail || '获取播放地址失败');
    }
  };

  const handleKeySubmit = () => {
    if (selectedStream) {
      handlePlay(selectedStream, selectedFormat, streamKey);
    }
  };

  const selectStream = (stream: StreamInfo) => {
    setSelectedStream(stream);
    const fmt = stream.formats.includes('flv') ? 'flv' : stream.formats[0] || 'flv';
    setSelectedFormat(fmt);
    handlePlay(stream, fmt);
  };

  return (
    <div>
      {/* Player area */}
      {playData && selectedStream ? (
        <Row gutter={16} style={{ marginBottom: 24 }}>
          <Col xs={24} lg={16}>
            <Card
              title={
                <Space>
                  <VideoCameraOutlined />
                  <span>{selectedStream.display_name}</span>
                  <Tag color="red">LIVE</Tag>
                </Space>
              }
              extra={
                <Space>
                  <Select
                    value={selectedFormat}
                    onChange={(fmt) => handlePlay(selectedStream, fmt)}
                    style={{ width: 100 }}
                    options={selectedStream.formats.map((f) => ({ label: f.toUpperCase(), value: f }))}
                  />
                  <Button
                    icon={<ReloadOutlined />}
                    onClick={() => handlePlay(selectedStream, selectedFormat)}
                    size="small"
                  >
                    刷新
                  </Button>
                </Space>
              }
              styles={{ body: { padding: 0 } }}
            >
              <LivePlayer url={playData.url} format={selectedFormat} />
              <div style={{ padding: '8px 16px' }}>
                <Space>
                  <Text type="secondary">
                    <EyeOutlined /> {selectedStream.clients} 观众
                  </Text>
                  {selectedStream.video_codec && (
                    <Tag>{selectedStream.video_codec}</Tag>
                  )}
                  {selectedStream.audio_codec && (
                    <Tag>{selectedStream.audio_codec}</Tag>
                  )}
                  <Tag color="blue">{selectedFormat.toUpperCase()}</Tag>
                </Space>
              </div>
            </Card>
          </Col>
          <Col xs={24} lg={8}>
            <div style={{ height: 500 }}>
              <ChatPanel streamName={selectedStream.name} />
            </div>
          </Col>
        </Row>
      ) : (
        !loading && streams.length > 0 && (
          <Alert
            message="选择一个直播流开始观看"
            type="info"
            showIcon
            style={{ marginBottom: 16 }}
          />
        )
      )}

      {/* Stream list */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>
          <PlayCircleOutlined /> 在线直播
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
        <Empty description="暂无在线直播" />
      ) : (
        <Row gutter={[16, 16]}>
          {streams.map((stream) => (
            <Col xs={24} sm={12} md={8} lg={6} key={stream.name}>
              <Card
                hoverable
                onClick={() => selectStream(stream)}
                styles={{
                  body: { padding: 16 },
                }}
                style={{
                  border: selectedStream?.name === stream.name ? '2px solid #1677ff' : undefined,
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', marginBottom: 8 }}>
                  <VideoCameraOutlined style={{ fontSize: 20, color: '#f5222d', marginRight: 8 }} />
                  <Text strong ellipsis style={{ flex: 1 }}>
                    {stream.display_name}
                  </Text>
                </div>
                <Space wrap size={4}>
                  <Tag color="red">LIVE</Tag>
                  <Tag icon={<EyeOutlined />}>{stream.clients}</Tag>
                  {stream.is_encrypted && <Tag icon={<LockOutlined />} color="orange">加密</Tag>}
                  {stream.require_auth && <Tag icon={<KeyOutlined />} color="purple">需登录</Tag>}
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
          ))}
        </Row>
      )}

      {/* Key input modal */}
      <Modal
        title={
          <Space>
            <LockOutlined />
            输入直播密钥
          </Space>
        }
        open={keyModalOpen}
        onOk={handleKeySubmit}
        onCancel={() => { setKeyModalOpen(false); setStreamKey(''); }}
        okText="确认"
        cancelText="取消"
      >
        <Input.Password
          value={streamKey}
          onChange={(e) => setStreamKey(e.target.value)}
          placeholder="请输入直播密钥"
          onPressEnter={handleKeySubmit}
        />
      </Modal>
    </div>
  );
};

export default Home;
