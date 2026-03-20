import { ReloadOutlined, SaveOutlined } from '@ant-design/icons';
import { Button, Card, message, Space, Spin, Typography } from 'antd';
import React, { useCallback, useEffect, useState } from 'react';

const { Title } = Typography;

interface OryxConfigPageProps {
  title: string;
  icon: React.ReactNode;
  fetchFn: () => Promise<unknown>;
  saveFn?: (config: Record<string, unknown>) => Promise<unknown>;
}

const OryxConfigPage: React.FC<OryxConfigPageProps> = ({ title, icon, fetchFn, saveFn }) => {
  const [config, setConfig] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const fetchConfig = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchFn();
      setConfig(JSON.stringify(data, null, 2));
    } catch {
      message.error('获取配置失败');
    } finally {
      setLoading(false);
    }
  }, [fetchFn]);

  useEffect(() => {
    fetchConfig();
  }, [fetchConfig]);

  const handleSave = async () => {
    if (!saveFn) return;
    setSaving(true);
    try {
      const parsed = JSON.parse(config);
      await saveFn(parsed);
      message.success('保存成功');
      fetchConfig();
    } catch (err) {
      if (err instanceof SyntaxError) {
        message.error('JSON 格式错误');
      } else {
        message.error('保存失败');
      }
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 60 }}>
        <Spin size="large" />
      </div>
    );
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>
          {icon} {title}
        </Title>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={fetchConfig}>
            刷新
          </Button>
          {saveFn && (
            <Button type="primary" icon={<SaveOutlined />} onClick={handleSave} loading={saving}>
              保存
            </Button>
          )}
        </Space>
      </div>

      <Card>
        <textarea
          value={config}
          onChange={(e) => setConfig(e.target.value)}
          style={{
            width: '100%',
            minHeight: 400,
            fontFamily: 'monospace',
            fontSize: 13,
            padding: 12,
            border: '1px solid #d9d9d9',
            borderRadius: 6,
            resize: 'vertical',
            outline: 'none',
          }}
          readOnly={!saveFn}
        />
      </Card>
    </div>
  );
};

export default OryxConfigPage;
