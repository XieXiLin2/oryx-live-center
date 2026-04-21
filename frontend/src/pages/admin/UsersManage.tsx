import { ReloadOutlined } from '@ant-design/icons';
import { App, Avatar, Button, Input, Space, Switch, Table, Tag, Typography } from 'antd';
import React, { useCallback, useEffect, useState } from 'react';
import { adminApi } from '../../api';
import type { User } from '../../types';
import { resolveAvatar } from '../../utils/avatar';

const { Title } = Typography;

const UsersManage: React.FC = () => {
  const { message } = App.useApp();
  const [rows, setRows] = useState<User[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(false);

  const PAGE_SIZE = 20;

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await adminApi.listUsers({
        limit: PAGE_SIZE,
        offset: (page - 1) * PAGE_SIZE,
        search: search || undefined,
      });
      setRows(data.users);
      setTotal(data.total);
    } finally {
      setLoading(false);
    }
  }, [page, search]);

  useEffect(() => {
    load();
  }, [load]);

  const toggleBan = async (u: User, banned: boolean) => {
    await adminApi.banUser(u.id, banned);
    message.success(banned ? '已封禁' : '已解封');
    load();
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Title level={3} style={{ margin: 0 }}>用户管理</Title>
        <Space>
          <Input.Search
            placeholder="搜索用户名 / 邮箱"
            allowClear
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onSearch={() => { setPage(1); load(); }}
            style={{ width: 240 }}
          />
          <Button icon={<ReloadOutlined />} onClick={load}>刷新</Button>
        </Space>
      </div>

      <Table<User>
        rowKey="id"
        loading={loading}
        dataSource={rows}
        pagination={{
          current: page,
          pageSize: PAGE_SIZE,
          total,
          onChange: setPage,
        }}
        columns={[
          { title: '#', dataIndex: 'id', width: 80 },
          {
            title: '用户',
            render: (_, u) => (
              <Space>
                <Avatar src={resolveAvatar(u.avatar_url, u.email, { size: 48 })} size="small">
                  {(u.display_name || u.username)[0]}
                </Avatar>
                <span>{u.display_name || u.username}</span>
              </Space>
            ),
          },
          { title: '邮箱', dataIndex: 'email' },
          {
            title: '角色',
            render: (_, u) => u.is_admin ? <Tag color="purple">管理员</Tag> : <Tag>普通用户</Tag>,
          },
          {
            title: '状态',
            render: (_, u) => u.is_banned
              ? <Tag color="red">封禁</Tag>
              : <Tag color="green">正常</Tag>,
          },
          { title: '注册时间', dataIndex: 'created_at' },
          {
            title: '封禁',
            render: (_, u) => (
              <Switch
                checked={!!u.is_banned}
                onChange={(v) => toggleBan(u, v)}
              />
            ),
          },
        ]}
      />
    </div>
  );
};

export default UsersManage;
