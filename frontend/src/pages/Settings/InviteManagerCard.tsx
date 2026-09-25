import { useMemo, useState } from "react";
import {
  ClearOutlined,
  CopyOutlined,
  DeleteOutlined,
  PlusOutlined,
  ReloadOutlined,
  SearchOutlined,
  TeamOutlined,
} from "@ant-design/icons";
import {
  Button,
  Card,
  Col,
  Input,
  message,
  Popconfirm,
  Row,
  Select,
  Space,
  Table,
  Tag,
  Tooltip,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import { useQueryClient } from "@tanstack/react-query";
import {
  useCleanupExpiredInvites,
  useCreateInvite,
  useInvites,
  useRevokeInvite,
} from "../../api/queries";
import { queryKeys } from "../../api/queryKeys";
import SectionDataState from "../../components/SectionDataState";
import { useMediaQuery } from "../../hooks/useMediaQuery";
import { semanticTagStyle, useColors, useStyles } from "../../styles/ui";
import type { InviteItem } from "../../types/auth";

export default function InviteManagerCard() {
  const { cardStyle, sectionCardBodyStyle } = useStyles();
  const colors = useColors();
  const isNarrow = useMediaQuery("(max-width: 640px)");
  const queryClient = useQueryClient();
  const { data: invites = [], isLoading, error, refetch } = useInvites(true);
  const createInvite = useCreateInvite();
  const revokeInvite = useRevokeInvite();
  const cleanupInvites = useCleanupExpiredInvites();

  const [expiresInDays, setExpiresInDays] = useState<number | undefined>();
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | "unused" | "used" | "expired">("all");

  const refresh = () => queryClient.invalidateQueries({ queryKey: queryKeys.settings.invites });

  // Filtered dataset
  const filteredInvites = useMemo(() => {
    return invites.filter((inv) => {
      if (searchQuery.trim() && !inv.code.toLowerCase().includes(searchQuery.trim().toLowerCase())) {
        return false;
      }
      if (statusFilter === "unused" && (inv.used || inv.expired)) return false;
      if (statusFilter === "used" && !inv.used) return false;
      if (statusFilter === "expired" && (!inv.expired || inv.used)) return false;
      return true;
    });
  }, [invites, searchQuery, statusFilter]);

  // Stats calculation
  const stats = useMemo(() => {
    const total = invites.length;
    const used = invites.filter((i) => i.used).length;
    const expired = invites.filter((i) => !i.used && i.expired).length;
    const unused = invites.filter((i) => !i.used && !i.expired).length;
    return { total, used, expired, unused };
  }, [invites]);

  const handleGenerate = () => {
    createInvite.mutate(expiresInDays, {
      onSuccess: () => {
        refresh();
        message.success("已生成新的邀请码");
      },
      onError: (error: Error) => message.error(`生成失败: ${error.message}`),
    });
  };

  const handleRevoke = (code: string) => {
    revokeInvite.mutate(code, {
      onSuccess: () => {
        refresh();
        message.success("邀请码已撤销");
      },
      onError: (error: Error) => message.error(`撤销失败: ${error.message}`),
    });
  };

  const handleCleanupExpired = () => {
    cleanupInvites.mutate(undefined, {
      onSuccess: (res) => {
        refresh();
        message.success(`已清理 ${res.cleaned_count} 个过期未使用的邀请码`);
      },
      onError: (err: Error) => message.error(`清理失败: ${err.message}`),
    });
  };

  const copyCode = async (code: string) => {
    try {
      await navigator.clipboard.writeText(code);
      message.success("邀请码已复制");
    } catch {
      message.warning("复制失败，请手动选择复制");
    }
  };

  const renderStatus = (invite: InviteItem) => {
    if (invite.used) return <Tag color="default">已使用</Tag>;
    if (invite.expired) return <Tag style={semanticTagStyle("up")}>已过期</Tag>;
    return <Tag style={semanticTagStyle("down")}>有效未使用</Tag>;
  };

  const columns: ColumnsType<InviteItem> = [
    {
      title: "邀请码",
      dataIndex: "code",
      key: "code",
      render: (code: string) => (
        <Space size={6}>
          <code
            style={{
              fontFamily: "var(--c-font-mono)",
              fontSize: "var(--c-font-md)",
              color: colors.textPrimary,
              fontWeight: 600,
            }}
          >
            {code}
          </code>
          <Tooltip title="复制邀请码">
            <Button
              type="text"
              size="small"
              icon={<CopyOutlined />}
              onClick={() => copyCode(code)}
            />
          </Tooltip>
        </Space>
      ),
    },
    {
      title: "状态",
      key: "status",
      width: 120,
      render: (_, record) => renderStatus(record),
    },
    {
      title: "创建时间",
      dataIndex: "created_at",
      key: "created_at",
      width: 160,
      render: (val: string | null) => val || "—",
    },
    {
      title: "有效期",
      dataIndex: "expires_at",
      key: "expires_at",
      width: 170,
      render: (val: string | null, record) => {
        if (!val) return <Tag color="blue">永不过期</Tag>;
        return record.expired && !record.used ? (
          <span style={{ color: colors.up }}>{val}</span>
        ) : (
          val
        );
      },
    },
    {
      title: "使用情况",
      key: "usage",
      width: 160,
      render: (_, record) => {
        if (!record.used) return <span style={{ color: colors.textMuted }}>—</span>;
        return (
          <div style={{ fontSize: "var(--c-font-xs)", color: colors.textMuted }}>
            <div>使用者 ID: {record.used_by ?? "未知"}</div>
            {record.used_at && <div>时间: {record.used_at}</div>}
          </div>
        );
      },
    },
    {
      title: "操作",
      key: "action",
      width: 100,
      render: (_, record) =>
        !record.used ? (
          <Popconfirm
            title="撤销该邀请码？"
            description="撤销后将无法用于注册。"
            okText="撤销"
            cancelText="取消"
            okButtonProps={{ danger: true }}
            onConfirm={() => handleRevoke(record.code)}
          >
            <Button size="small" danger icon={<DeleteOutlined />} loading={revokeInvite.isPending}>
              撤销
            </Button>
          </Popconfirm>
        ) : (
          <span style={{ color: colors.textMuted, fontSize: "12px" }}>不可撤销</span>
        ),
    },
  ];

  const inviteControls = (
    <Space wrap style={{ width: isNarrow ? "100%" : undefined }}>
      <Select
        size="small"
        value={expiresInDays ?? 0}
        style={{ width: isNarrow ? "100%" : 120, minWidth: 120 }}
        onChange={(value) => setExpiresInDays(value === 0 ? undefined : value)}
        options={[
          { value: 0, label: "永不过期" },
          { value: 1, label: "1 天有效" },
          { value: 7, label: "7 天有效" },
          { value: 30, label: "30 天有效" },
        ]}
      />
      <Button
        type="primary"
        size="small"
        icon={<PlusOutlined />}
        onClick={handleGenerate}
        loading={createInvite.isPending}
      >
        生成邀请码
      </Button>
      {stats.expired > 0 && (
        <Popconfirm
          title="清理所有过期且未使用的邀请码？"
          description={`将删除 ${stats.expired} 个已过期邀请码，已使用的不会受影响。`}
          onConfirm={handleCleanupExpired}
        >
          <Button
            size="small"
            icon={<ClearOutlined />}
            loading={cleanupInvites.isPending}
          >
            清理过期({stats.expired})
          </Button>
        </Popconfirm>
      )}
    </Space>
  );

  return (
    <Card
      title={<span><TeamOutlined style={{ marginRight: 8 }} />邀请码管理</span>}
      extra={isNarrow ? undefined : inviteControls}
      style={{ ...cardStyle, marginBottom: 16 }}
      styles={{ body: sectionCardBodyStyle }}
    >
      <div style={{ fontSize: "var(--c-font-sm)", color: colors.textMuted, marginBottom: 12 }}>
        新用户注册需填写有效且未使用的邀请码；每个邀请码仅可使用一次。管理员可随时发放、撤销或按需一键清理过期邀请码。
      </div>

      {isNarrow && <div style={{ marginBottom: 12 }}>{inviteControls}</div>}

      {/* Metrics Bar */}
      <Row gutter={[12, 12]} style={{ marginBottom: 14 }}>
        <Col xs={12} sm={6}>
          <div
            style={{
              padding: "8px 12px",
              background: colors.hoverBg,
              borderRadius: 6,
              border: `1px solid ${colors.border}`,
            }}
          >
            <div style={{ fontSize: "11px", color: colors.textMuted }}>总邀请码</div>
            <div style={{ fontSize: "18px", fontWeight: 700, color: colors.textPrimary }}>
              {stats.total}
            </div>
          </div>
        </Col>
        <Col xs={12} sm={6}>
          <div
            style={{
              padding: "8px 12px",
              background: colors.hoverBg,
              borderRadius: 6,
              border: `1px solid ${colors.border}`,
            }}
          >
            <div style={{ fontSize: "11px", color: colors.textMuted }}>有效未使用</div>
            <div style={{ fontSize: "18px", fontWeight: 700, color: colors.success }}>
              {stats.unused}
            </div>
          </div>
        </Col>
        <Col xs={12} sm={6}>
          <div
            style={{
              padding: "8px 12px",
              background: colors.hoverBg,
              borderRadius: 6,
              border: `1px solid ${colors.border}`,
            }}
          >
            <div style={{ fontSize: "11px", color: colors.textMuted }}>已使用</div>
            <div style={{ fontSize: "18px", fontWeight: 700, color: colors.primary }}>
              {stats.used}
            </div>
          </div>
        </Col>
        <Col xs={12} sm={6}>
          <div
            style={{
              padding: "8px 12px",
              background: colors.hoverBg,
              borderRadius: 6,
              border: `1px solid ${colors.border}`,
            }}
          >
            <div style={{ fontSize: "11px", color: colors.textMuted }}>已过期</div>
            <div style={{ fontSize: "18px", fontWeight: 700, color: colors.textMuted }}>
              {stats.expired}
            </div>
          </div>
        </Col>
      </Row>

      {/* Toolbar */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: 10,
          marginBottom: 12,
        }}
      >
        <Space wrap>
          <Input
            placeholder="搜索邀请码..."
            prefix={<SearchOutlined style={{ color: colors.textMuted }} />}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            allowClear
            size="small"
            style={{ width: isNarrow ? "100%" : 180 }}
          />
          <Select
            size="small"
            value={statusFilter}
            onChange={(val) => setStatusFilter(val)}
            style={{ width: 120 }}
            options={[
              { value: "all", label: "全部状态" },
              { value: "unused", label: "有效未使用" },
              { value: "used", label: "已使用" },
              { value: "expired", label: "已过期" },
            ]}
          />
        </Space>

        <Button
          size="small"
          icon={<ReloadOutlined />}
          onClick={() => refetch()}
          loading={isLoading}
        >
          刷新
        </Button>
      </div>

      <SectionDataState
        isLoading={isLoading && invites.length === 0}
        error={invites.length > 0 ? undefined : error}
        onRetry={() => refetch()}
        isEmpty={!isLoading && !error && invites.length === 0}
        emptyText="暂无邀请码，可通过上方操作生成"
        errorTitle="邀请码加载失败"
        minHeight={120}
      >
        <Table<InviteItem>
          rowKey="code"
          columns={columns}
          dataSource={filteredInvites}
          pagination={{
            pageSize: 10,
            showSizeChanger: false,
            size: "small",
            hideOnSinglePage: true,
          }}
          size="small"
          scroll={{ x: 650 }}
        />
      </SectionDataState>
    </Card>
  );
}

