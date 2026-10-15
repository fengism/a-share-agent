import { useMemo, useState } from "react";
import {
  CopyOutlined,
  CrownOutlined,
  DeleteOutlined,
  DisconnectOutlined,
  KeyOutlined,
  ReloadOutlined,
  SearchOutlined,
  TeamOutlined,
  UserOutlined,
} from "@ant-design/icons";
import { useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Button,
  Card,
  Col,
  Input,
  message,
  Modal,
  Popconfirm,
  Row,
  Select,
  Space,
  Table,
  Tag,
  Tooltip,
  Typography,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import { adminResetLinkApi } from "../../api/auth";
import {
  useAdminUsers,
  useDeleteUser,
  useRevokeUserSessions,
  useUpdateUserMustChangePassword,
  useUpdateUserRole,
  useUpdateUserStatus,
} from "../../api/queries";
import { queryKeys } from "../../api/queryKeys";
import SectionDataState from "../../components/SectionDataState";
import { useAuthStore } from "../../store/authStore";
import { semanticTagStyle, useColors, useStyles } from "../../styles/ui";
import type { AdminUserItem } from "../../types/auth";

const { Text } = Typography;

export default function UserManagerCard() {
  const { cardStyle, sectionCardBodyStyle } = useStyles();
  const colors = useColors();
  const queryClient = useQueryClient();
  const currentUser = useAuthStore((s) => s.user);

  const { data: users = [], isLoading, error, refetch } = useAdminUsers(true);
  const updateStatus = useUpdateUserStatus();
  const updateRole = useUpdateUserRole();
  const deleteUser = useDeleteUser();
  const revokeSessions = useRevokeUserSessions();
  const updateMustChange = useUpdateUserMustChangePassword();

  // Search & Filter state
  const [searchQuery, setSearchQuery] = useState("");
  const [roleFilter, setRoleFilter] = useState<"all" | "admin" | "normal">("all");
  const [statusFilter, setStatusFilter] = useState<"all" | "active" | "disabled">("all");

  // Reset Link Modal state
  const [resetTarget, setResetTarget] = useState<AdminUserItem | null>(null);
  const [resetHours, setResetHours] = useState(24);
  const [resetLoading, setResetLoading] = useState(false);
  const [resetResult, setResetResult] = useState<{ url: string; expires_at: string } | null>(null);

  const refresh = () => queryClient.invalidateQueries({ queryKey: queryKeys.settings.users });

  // Filtered dataset
  const filteredUsers = useMemo(() => {
    return users.filter((u) => {
      if (searchQuery.trim() && !u.username.toLowerCase().includes(searchQuery.trim().toLowerCase())) {
        return false;
      }
      if (roleFilter === "admin" && !u.is_admin) return false;
      if (roleFilter === "normal" && u.is_admin) return false;
      if (statusFilter === "active" && !u.is_active) return false;
      if (statusFilter === "disabled" && u.is_active) return false;
      return true;
    });
  }, [users, searchQuery, roleFilter, statusFilter]);

  // Statistics
  const stats = useMemo(() => {
    const total = users.length;
    const active = users.filter((u) => u.is_active).length;
    const disabled = users.filter((u) => !u.is_active).length;
    const admins = users.filter((u) => u.is_admin).length;
    return { total, active, disabled, admins };
  }, [users]);

  const handleToggleStatus = (target: AdminUserItem) => {
    const nextStatus = !target.is_active;
    updateStatus.mutate(
      { userId: target.id, isActive: nextStatus },
      {
        onSuccess: () => {
          refresh();
          message.success(nextStatus ? `账号 ${target.username} 已启用` : `账号 ${target.username} 已停用`);
        },
        onError: (err: Error) => message.error(`操作失败: ${err.message}`),
      },
    );
  };

  const handleToggleRole = (target: AdminUserItem) => {
    const nextAdmin = !target.is_admin;
    updateRole.mutate(
      { userId: target.id, isAdmin: nextAdmin },
      {
        onSuccess: () => {
          refresh();
          message.success(nextAdmin ? `已将 ${target.username} 设为管理员` : `已取消 ${target.username} 的管理员权限`);
        },
        onError: (err: Error) => message.error(`操作失败: ${err.message}`),
      },
    );
  };

  const handleDelete = (target: AdminUserItem) => {
    deleteUser.mutate(target.id, {
      onSuccess: () => {
        refresh();
        message.success(`用户 ${target.username} 已删除`);
      },
      onError: (err: Error) => message.error(`删除失败: ${err.message}`),
    });
  };

  const handleRevokeSessions = (target: AdminUserItem) => {
    revokeSessions.mutate(target.id, {
      onSuccess: (res) => {
        message.success(`已强制注销 ${target.username} 的 ${res.revoked_sessions} 个有效会话`);
      },
      onError: (err: Error) => message.error(`踢出会话失败: ${err.message}`),
    });
  };

  const handleToggleMustChangePassword = (target: AdminUserItem) => {
    const nextVal = !target.must_change_password;
    updateMustChange.mutate(
      { userId: target.id, mustChangePassword: nextVal },
      {
        onSuccess: () => {
          refresh();
          message.success(
            nextVal
              ? `已要求 ${target.username} 下次登录时必须修改密码`
              : `已取消 ${target.username} 的强制改密要求`,
          );
        },
        onError: (err: Error) => message.error(`操作失败: ${err.message}`),
      },
    );
  };

  const openResetModal = (target: AdminUserItem) => {
    setResetTarget(target);
    setResetHours(24);
    setResetResult(null);
  };

  const handleGenerateResetLink = async () => {
    if (!resetTarget) return;
    setResetLoading(true);
    try {
      const res = await adminResetLinkApi({
        username: resetTarget.username,
        expires_in_hours: resetHours,
      });
      const url = `${window.location.origin}/reset-password?token=${encodeURIComponent(res.token)}`;
      setResetResult({ url, expires_at: res.expires_at });
      message.success("重置链接已成功生成");
    } catch (err) {
      message.error(err instanceof Error ? err.message : "生成失败");
    } finally {
      setResetLoading(false);
    }
  };

  const copyResetUrl = async () => {
    if (!resetResult) return;
    try {
      await navigator.clipboard.writeText(resetResult.url);
      message.success("重置链接已复制到剪贴板");
    } catch {
      message.warning("复制失败，请手动选择复制");
    }
  };

  const columns: ColumnsType<AdminUserItem> = [
    {
      title: "ID",
      dataIndex: "id",
      width: 65,
    },
    {
      title: "用户名",
      dataIndex: "username",
      render: (name: string, record) => (
        <Space orientation="horizontal" size={4}>
          <UserOutlined style={{ color: colors.textMuted }} />
          <span style={{ fontWeight: 500 }}>{name}</span>
          {record.id === currentUser?.id && (
            <Tag color="blue" style={{ fontSize: "11px", padding: "0 4px", lineHeight: "18px" }}>
              当前账号
            </Tag>
          )}
        </Space>
      ),
    },
    {
      title: "角色",
      dataIndex: "is_admin",
      width: 105,
      render: (isAdmin: boolean) =>
        isAdmin ? (
          <Tag color="purple" icon={<CrownOutlined />}>
            管理员
          </Tag>
        ) : (
          <Tag>普通用户</Tag>
        ),
    },
    {
      title: "账号状态",
      dataIndex: "is_active",
      width: 95,
      render: (isActive: boolean) =>
        isActive ? (
          <Tag style={semanticTagStyle("down")}>正常</Tag>
        ) : (
          <Tag style={semanticTagStyle("up")}>已禁用</Tag>
        ),
    },
    {
      title: "初始改密",
      dataIndex: "must_change_password",
      width: 95,
      render: (mustChange: boolean) =>
        mustChange ? (
          <Tag style={semanticTagStyle("warning")}>待改密</Tag>
        ) : (
          <Tag>已改密</Tag>
        ),
    },
    {
      title: "注册时间",
      dataIndex: "created_at",
      width: 160,
      render: (created: string | null) => created || "—",
    },
    {
      title: "操作",
      key: "actions",
      width: 250,
      render: (_, record) => {
        const isSelf = record.id === currentUser?.id;
        return (
          <Space size="small" wrap>
            {record.is_active ? (
              <Popconfirm
                title="确定禁用该用户？"
                description="禁用后该用户将立即断开所有会话并无法登录。"
                onConfirm={() => handleToggleStatus(record)}
                disabled={isSelf}
              >
                <Button size="small" danger disabled={isSelf}>
                  禁用
                </Button>
              </Popconfirm>
            ) : (
              <Button size="small" onClick={() => handleToggleStatus(record)}>
                启用
              </Button>
            )}

            <Popconfirm
              title={record.is_admin ? "取消该用户的管理员权限？" : "设为管理员？"}
              onConfirm={() => handleToggleRole(record)}
              disabled={isSelf}
            >
              <Button size="small" disabled={isSelf}>
                {record.is_admin ? "降为普通" : "设为管理"}
              </Button>
            </Popconfirm>

            <Tooltip title={record.must_change_password ? "取消下次改密要求" : "要求该用户下次登录时必须修改密码"}>
              <Button
                size="small"
                style={record.must_change_password ? { color: colors.warning } : undefined}
                onClick={() => handleToggleMustChangePassword(record)}
              >
                {record.must_change_password ? "取消改密" : "要求改密"}
              </Button>
            </Tooltip>

            <Tooltip title="生成一次性密码重置链接">
              <Button
                size="small"
                icon={<KeyOutlined />}
                onClick={() => openResetModal(record)}
              />
            </Tooltip>

            <Tooltip title="强制注销该用户的所有在线会话设备">
              <Button
                size="small"
                icon={<DisconnectOutlined />}
                onClick={() => handleRevokeSessions(record)}
              />
            </Tooltip>

            <Popconfirm
              title="确定删除该用户？"
              description="删除后该用户的所有配置、重置记录和登录凭证将被永久清空。"
              onConfirm={() => handleDelete(record)}
              disabled={isSelf}
            >
              <Button size="small" type="text" danger icon={<DeleteOutlined />} disabled={isSelf} />
            </Popconfirm>
          </Space>
        );
      },
    },
  ];

  return (
    <>
      <Card
        title={
          <Space>
            <TeamOutlined />
            <span>用户管理</span>
          </Space>
        }
        extra={
          <Button size="small" icon={<ReloadOutlined />} onClick={() => refetch()} loading={isLoading}>
            刷新
          </Button>
        }
        style={{ ...cardStyle, marginBottom: 16 }}
        styles={{ body: sectionCardBodyStyle }}
      >
        <div style={{ fontSize: "var(--c-font-sm)", color: colors.textMuted, marginBottom: 12 }}>
          管理系统所有注册用户、控制账号状态、调整管理员角色分配以及强制注销远程会话。
        </div>

        {/* User statistics banner */}
        <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
          <Col xs={12} sm={6}>
            <div style={{ padding: "8px 12px", background: colors.hoverBg, borderRadius: 6 }}>
              <div style={{ fontSize: "12px", color: colors.textMuted }}>总用户数</div>
              <div style={{ fontSize: "18px", fontWeight: 600, color: colors.textPrimary }}>
                {stats.total}
              </div>
            </div>
          </Col>
          <Col xs={12} sm={6}>
            <div style={{ padding: "8px 12px", background: colors.hoverBg, borderRadius: 6 }}>
              <div style={{ fontSize: "12px", color: colors.textMuted }}>正常运行</div>
              <div style={{ fontSize: "18px", fontWeight: 600, color: colors.down }}>
                {stats.active}
              </div>
            </div>
          </Col>
          <Col xs={12} sm={6}>
            <div style={{ padding: "8px 12px", background: colors.hoverBg, borderRadius: 6 }}>
              <div style={{ fontSize: "12px", color: colors.textMuted }}>已禁用</div>
              <div style={{ fontSize: "18px", fontWeight: 600, color: stats.disabled > 0 ? colors.up : colors.textMuted }}>
                {stats.disabled}
              </div>
            </div>
          </Col>
          <Col xs={12} sm={6}>
            <div style={{ padding: "8px 12px", background: colors.hoverBg, borderRadius: 6 }}>
              <div style={{ fontSize: "12px", color: colors.textMuted }}>管理员</div>
              <div style={{ fontSize: "18px", fontWeight: 600, color: "#722ed1" }}>
                {stats.admins}
              </div>
            </div>
          </Col>
        </Row>

        {/* Filter bar */}
        <Row gutter={[12, 12]} style={{ marginBottom: 14 }}>
          <Col xs={24} sm={10} md={8}>
            <Input
              placeholder="按用户名搜索"
              prefix={<SearchOutlined style={{ color: colors.textMuted }} />}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              allowClear
              size="middle"
            />
          </Col>
          <Col xs={12} sm={7} md={5}>
            <Select
              style={{ width: "100%" }}
              value={roleFilter}
              onChange={(val) => setRoleFilter(val)}
              options={[
                { value: "all", label: "全部角色" },
                { value: "admin", label: "仅管理员" },
                { value: "normal", label: "仅普通用户" },
              ]}
              size="middle"
            />
          </Col>
          <Col xs={12} sm={7} md={5}>
            <Select
              style={{ width: "100%" }}
              value={statusFilter}
              onChange={(val) => setStatusFilter(val)}
              options={[
                { value: "all", label: "全部状态" },
                { value: "active", label: "仅正常" },
                { value: "disabled", label: "仅已禁用" },
              ]}
              size="middle"
            />
          </Col>
        </Row>

        <SectionDataState
          isLoading={isLoading}
          error={error as Error | null}
          onRetry={() => refetch()}
          isEmpty={filteredUsers.length === 0}
          emptyText={users.length > 0 ? "未找到符合筛选条件的用户" : "暂无用户记录"}
        >
          <Table
            rowKey="id"
            dataSource={filteredUsers}
            columns={columns}
            pagination={{ pageSize: 10, hideOnSinglePage: true }}
            size="middle"
            scroll={{ x: 760 }}
          />
        </SectionDataState>
      </Card>

      {/* Password Reset Modal */}
      <Modal
        width="min(520px, calc(100vw - 24px))"
        title={
          <Space>
            <KeyOutlined style={{ color: colors.primary }} />
            <span>生成重置链接 — {resetTarget?.username}</span>
          </Space>
        }
        open={Boolean(resetTarget)}
        onCancel={() => setResetTarget(null)}
        footer={[
          <Button key="close" onClick={() => setResetTarget(null)}>
            关闭
          </Button>,
          !resetResult ? (
            <Button
              key="generate"
              type="primary"
              onClick={handleGenerateResetLink}
              loading={resetLoading}
            >
              生成重置链接
            </Button>
          ) : (
            <Button key="copy" type="primary" icon={<CopyOutlined />} onClick={copyResetUrl}>
              复制链接
            </Button>
          ),
        ]}
      >
        <div style={{ fontSize: "var(--c-font-sm)", color: colors.textMuted, marginBottom: 16 }}>
          为用户 <strong>{resetTarget?.username}</strong> 生成一次性密码重置令牌。用户打开链接后可自行重置密码，该操作将即刻强制注销其所有现有登录会话。
        </div>

        {!resetResult ? (
          <Space orientation="vertical" style={{ width: "100%" }} size="middle">
            <div>
              <span style={{ fontSize: "13px", color: colors.textPrimary, marginRight: 8 }}>有效期：</span>
              <Select
                value={resetHours}
                onChange={setResetHours}
                style={{ width: 140 }}
                options={[
                  { value: 1, label: "1 小时" },
                  { value: 6, label: "6 小时" },
                  { value: 24, label: "24 小时 (1天)" },
                  { value: 72, label: "72 小时 (3天)" },
                  { value: 168, label: "168 小时 (7天)" },
                ]}
              />
            </div>
          </Space>
        ) : (
          <Space orientation="vertical" style={{ width: "100%" }} size="middle">
            <Alert
              type="success"
              showIcon
              title="重置链接已生成"
              description={`有效至: ${resetResult.expires_at}。链接仅展示一次，请妥善转交给该用户。`}
            />
            <div>
              <Text copyable={{ text: resetResult.url }} code style={{ wordBreak: "break-all" }}>
                {resetResult.url}
              </Text>
            </div>
          </Space>
        )}
      </Modal>
    </>
  );
}
