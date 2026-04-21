import { Card, Descriptions, Spin, Typography } from 'antd';
import React, { useEffect, useState } from 'react';
import { adminApi } from '../../api';

const { Title, Paragraph } = Typography;

const Settings: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState<Record<string, string>>({});

  useEffect(() => {
    adminApi.getSettings()
      .then(setData)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <Spin size="large" />;

  return (
    <div>
      <Title level={3}>系统设置</Title>
      <Paragraph type="secondary">
        以下配置由后端 <code>.env</code> 管理，修改需重启服务。
      </Paragraph>
      <Card>
        <Descriptions column={1} bordered size="small">
          {Object.entries(data).map(([k, v]) => (
            <Descriptions.Item key={k} label={k}>
              <code>{String(v)}</code>
            </Descriptions.Item>
          ))}
        </Descriptions>
      </Card>
    </div>
  );
};

export default Settings;
