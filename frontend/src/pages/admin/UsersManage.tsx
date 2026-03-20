import { SearchOutlined, StopOutlined, UserOutlined } from '@ant-design/icons';
import { Avatar, Button, Input, message, Popconfirm, Space, Table, Tag, Typography } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import React, { useCallback, useEffect, useState } from 'react';
import { adminApi } from '../../api';
import type { User } from '../../types';

const { Title } = Typography;

const UsersManage: React.FC = () => {
  const [users, setUsers] = useState<User[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const pageSize = 20;

  const fetchUsers = useCallback(async () => {
    setLoading(true);
    try {
      const data = await adminApi.listUsers({
        limit: pageSize,
        offset: (page - 1) * pageSize,
        search,
      });
      setUsers(data.users);
      setTotal(data.total);
    } catch {
      message.error('获取用户列表失败');
    } finally {
      setLoading(false);
    }
  }, [page, search]);

  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  const handleBan = async (userId: number, ban: boolean) => {
    try {
      await adminApi.banUser(userId, ban);
      message.success(ban ? '已封禁用户' : '已解封用户');
      fetchUsers();
    } catch {
      message.error('操作失败');
    }
  };

  const columns: ColumnsType<User> = [
    {
      title: '用户',
      key: 'user',
      render: (_, record) => (
        <Space>
          <Avatar
            src={record.avatar_url || undefined}
            icon={!record.avatar_url ? <UserOutlined /> : undefined}
            size="small"
          />
          <span>{record.display_name || record.username}</span>
        </Space>
      ),
    },
    { title: '用户名', dataIndex: 'username', key: 'username' },
    { title: '邮箱', dataIndex: 'email', key: 'email' },
    {
      title: '角色',
      key: 'role',
      render: (_, record) => (
        <Space>
          {record.is_admin && <Tag color="red">管理员</Tag>}
        </Space>
      ),
    },
    {
      title: '注册时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (v: string) => new Date(v).toLocaleString(),
    },
    {
      title: '操作',
      key: 'actions',
      render: (_, record) => (
        <Space>
          {record.is_admin ? (
            <Tag color="blue">管理员</Tag>
          ) : (
            <Popconfirm
              title={`确定要${'封禁'}此用户吗？`}
              onConfirm={() => handleBan(record.id, true)}
            >
              <Button size="small" danger icon={<StopOutlined />}>
                封禁
              </Button>
            </Popconfirm>
          )}
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Title level={4}>
        <UserOutlined /> 用户管理
      </Title>

      <Space style={{ marginBottom: 16 }}>
        <Input
          placeholder="搜索用户..."
          prefix={<SearchOutlined />}
          value={search}
          onChange={(e) => { setSearch(e.target.value); setPage(1); }}
          allowClear
          style={{ width: 300 }}
        />
      </Space>

      <Table
        columns={columns}
        dataSource={users}
        rowKey="id"
        loading={loading}
        pagination={{
          current: page,
          pageSize,
          total,
          onChange: setPage,
          showTotal: (t) => `共 ${t} 个用户`,
        }}
      />
    </div>
  );
};

export default UsersManage;
