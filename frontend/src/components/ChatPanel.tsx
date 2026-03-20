import { LoginOutlined, SendOutlined, UserOutlined } from '@ant-design/icons';
import { Avatar, Badge, Button, Input, Space, Tag, Typography } from 'antd';
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useAuth } from '../store/auth';
import type { WsMessage } from '../types';

const { Text } = Typography;

interface ChatPanelProps {
  streamName: string;
}

const ChatPanel: React.FC<ChatPanelProps> = ({ streamName }) => {
  const { user, token, login } = useAuth();
  const [messages, setMessages] = useState<WsMessage[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [onlineCount, setOnlineCount] = useState(0);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const listRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = useCallback(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, []);

  useEffect(() => {
    if (!streamName) return;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/api/chat/ws/${streamName}${token ? `?token=${token}` : ''}`;

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
    };

    ws.onmessage = (event) => {
      try {
        const msg: WsMessage = JSON.parse(event.data);
        if (msg.online_count !== undefined) {
          setOnlineCount(msg.online_count);
        }
        setMessages((prev) => [...prev.slice(-200), msg]); // Keep last 200 messages
        setTimeout(scrollToBottom, 50);
      } catch (e) {
        console.error('Failed to parse WS message:', e);
      }
    };

    ws.onclose = () => {
      setConnected(false);
    };

    ws.onerror = () => {
      setConnected(false);
    };

    return () => {
      ws.close();
      wsRef.current = null;
    };
  }, [streamName, token, scrollToBottom]);

  const sendMessage = () => {
    if (!inputValue.trim() || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
    wsRef.current.send(JSON.stringify({ content: inputValue.trim() }));
    setInputValue('');
  };

  const renderMessage = (msg: WsMessage, index: number) => {
    if (msg.type === 'system') {
      return (
        <div key={index} style={{ textAlign: 'center', padding: '4px 0' }}>
          <Text type="secondary" style={{ fontSize: 12 }}>
            {msg.content}
          </Text>
        </div>
      );
    }

    if (msg.type === 'error') {
      return (
        <div key={index} style={{ textAlign: 'center', padding: '4px 0' }}>
          <Text type="danger" style={{ fontSize: 12 }}>
            {msg.content}
          </Text>
        </div>
      );
    }

    return (
      <div key={msg.id || index} style={{ padding: '4px 8px', borderRadius: 4 }}>
        <Space size={4} align="start">
          <Avatar
            src={msg.avatar_url || undefined}
            icon={!msg.avatar_url ? <UserOutlined /> : undefined}
            size={20}
          />
          <div>
            <Space size={4}>
              <Text strong style={{ fontSize: 13, color: msg.is_admin ? '#f5222d' : undefined }}>
                {msg.display_name || msg.username}
              </Text>
              {msg.is_admin && (
                <Tag color="red" style={{ fontSize: 10, lineHeight: '16px', padding: '0 4px' }}>
                  管理
                </Tag>
              )}
            </Space>
            <div>
              <Text style={{ fontSize: 13, wordBreak: 'break-word' }}>{msg.content}</Text>
            </div>
          </div>
        </Space>
      </div>
    );
  };

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        border: '1px solid #f0f0f0',
        borderRadius: 8,
        overflow: 'hidden',
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: '8px 12px',
          borderBottom: '1px solid #f0f0f0',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
      >
        <Text strong>聊天</Text>
        <Space>
          <Badge status={connected ? 'success' : 'error'} />
          <Text type="secondary" style={{ fontSize: 12 }}>
            {onlineCount} 在线
          </Text>
        </Space>
      </div>

      {/* Messages */}
      <div ref={listRef} style={{ flex: 1, overflowY: 'auto', padding: '8px 0' }}>
        {messages.length === 0 ? (
          <div style={{ textAlign: 'center', padding: 24 }}>
            <Text type="secondary">暂无消息</Text>
          </div>
        ) : (
          messages.map((msg, i) => renderMessage(msg, i))
        )}
      </div>

      {/* Input */}
      <div style={{ padding: 8, borderTop: '1px solid #f0f0f0' }}>
        {user ? (
          <Space.Compact style={{ width: '100%' }}>
            <Input
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onPressEnter={sendMessage}
              placeholder="发送弹幕..."
              maxLength={500}
              disabled={!connected}
            />
            <Button
              type="primary"
              icon={<SendOutlined />}
              onClick={sendMessage}
              disabled={!connected || !inputValue.trim()}
            />
          </Space.Compact>
        ) : (
          <Button type="primary" icon={<LoginOutlined />} block onClick={login}>
            登录后发送弹幕
          </Button>
        )}
      </div>
    </div>
  );
};

export default ChatPanel;
