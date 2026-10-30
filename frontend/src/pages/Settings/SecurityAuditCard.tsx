import { useState } from "react";
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  ExclamationCircleOutlined,
  ReloadOutlined,
  SafetyCertificateOutlined,
  SearchOutlined,
  StopOutlined,
} from "@ant-design/icons";
import { Button, Card, Input, Pagination, Select, Space, Table, Tabs, Tag, Tooltip } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useAdminAuditActions, useLoginAuditLogs } from "../../api/queries";
import SectionDataState from "../../components/SectionDataState";
import { useMediaQuery } from "../../hooks/useMediaQuery";
import { semanticTagStyle, useColors, useStyles } from "../../styles/ui";
import SettingsMobileRecordList, { type MobileRecordField } from "./SettingsMobileRecordList";
import {
  ACTION_FILTERS,
  ACTION_LABELS,
  LOGIN_STATUS_FILTERS,
  loginStatusMeta,
  summarizeDetails,
} from "./auditMeta";
import type { AdminAuditActionItem, LoginAuditLogItem } from "../../types/auth";

function LoginAuditSection() {
  const colors = useColors();
  const isNarrow = useMediaQuery("(max-width: 640px)");

  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [searchUsername, setSearchUsername] = useState("");
  const [selectedStatus, setSelectedStatus] = useState<string | undefined>();

  const offset = (page - 1) * pageSize;

  const { data, isLoading, error, refetch } = useLoginAuditLogs({
    limit: pageSize,
    offset,
    username: searchUsername.trim() || undefined,
    status: selectedStatus || undefined,
  });

  const items = data?.items ?? [];
  const total = data?.total ?? 0;

  const statusIcon = (status: string) => {
    switch (status) {
      case "success":
        return <CheckCircleOutlined />;
      case "failed_credentials":
        return <CloseCircleOutlined />;
      case "failed_disabled":
        return <StopOutlined />;
      case "failed_rate_limited":
        return <ExclamationCircleOutlined />;
      default:
        return undefined;
    }
  };

  // 文案与语义色统一取自 auditMeta，避免与「我的登录记录」两处漂移
  const statusTag = (status: string) => {
    const meta = loginStatusMeta(status);
    return (
      <Tag icon={statusIcon(status)} style={semanticTagStyle(meta.tone)}>
        {meta.label}
      </Tag>
    );
  };

  const columns: ColumnsType<LoginAuditLogItem> = [
    {
      title: "时间",
      dataIndex: "created_at",
      key: "created_at",
      width: 165,
      render: (val: string) => val || "—",
    },
    {
      title: "尝试账号",
      dataIndex: "username",
      key: "username",
      width: 140,
      render: (val: string, record) => (
        <Space size={4}>
          <span style={{ fontWeight: 600, color: colors.textPrimary }}>{val}</span>
          {record.user_id && (
            <Tag style={{ fontSize: "var(--c-font-xs, 11px)", lineHeight: "16px", padding: "0 4px" }}>
              #{record.user_id}
            </Tag>
          )}
        </Space>
      ),
    },
    {
      title: "结果 / 状态",
      dataIndex: "status",
      key: "status",
      width: 130,
      render: (status: string) => statusTag(status),
    },
    {
      title: "IP 地址",
      dataIndex: "ip_address",
      key: "ip_address",
      width: 130,
      render: (ip: string) => (
        <code style={{ fontFamily: "var(--c-font-mono)", fontSize: "var(--c-font-sm)" }}>
          {ip || "未知"}
        </code>
      ),
    },
    {
      title: "客户端 User-Agent",
      dataIndex: "user_agent",
      key: "user_agent",
      ellipsis: true,
      render: (ua: string) =>
        ua ? (
          <Tooltip title={ua}>
            <span style={{ color: colors.textMuted, fontSize: "var(--c-font-sm)", cursor: "pointer" }}>
              {ua.length > 50 ? `${ua.slice(0, 50)}...` : ua}
            </span>
          </Tooltip>
        ) : (
          <span style={{ color: colors.textMuted }}>—</span>
        ),
    },
    {
      title: "详情说明",
      dataIndex: "details",
      key: "details",
      width: 140,
      ellipsis: true,
      render: (val: string) => val || "—",
    },
  ];

  const mobileFields: MobileRecordField<LoginAuditLogItem>[] = [
    { label: "时间", primary: true, render: (item) => item.created_at || "—" },
    {
      label: "账号",
      primary: true,
      render: (item) => (
        <span>
          {item.username}
          {item.user_id ? <Tag style={{ marginLeft: 4, fontSize: "var(--c-font-xs, 11px)", lineHeight: "16px", padding: "0 4px" }}>#{item.user_id}</Tag> : null}
        </span>
      ),
    },
    { label: "结果", render: (item) => statusTag(item.status) },
    {
      label: "来源 IP",
      render: (item) => (
        <code style={{ fontFamily: "var(--c-font-mono)", fontSize: "var(--c-font-sm)" }}>{item.ip_address || "未知"}</code>
      ),
    },
    {
      label: "客户端",
      fullWidth: true,
      render: (item) => (
        <span style={{ color: colors.textMuted, fontSize: "var(--c-font-sm)", wordBreak: "break-all" }}>{item.user_agent || "—"}</span>
      ),
    },
    { label: "详情", fullWidth: true, render: (item) => item.details || "—" },
  ];

  const pagination = {
    current: page,
    pageSize,
    total,
    showSizeChanger: true,
    pageSizeOptions: ["10", "20", "50", "100"],
    onChange: (p: number, ps: number) => {
      setPage(p);
      setPageSize(ps);
    },
  };

  return (
    <>
      <div style={{ fontSize: "var(--c-font-sm)", color: colors.textMuted, marginBottom: 12 }}>
        实时记录系统所有用户的登录尝试、认证失败、禁用拦截与限流防御事件，便于追踪异常访问与安全合规审计。
      </div>

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
            placeholder="搜索用户名..."
            prefix={<SearchOutlined style={{ color: colors.textMuted }} />}
            value={searchUsername}
            onChange={(e) => {
              setSearchUsername(e.target.value);
              setPage(1);
            }}
            allowClear
            size="small"
            style={{ width: isNarrow ? "100%" : 160 }}
          />
          <Select
            size="small"
            value={selectedStatus}
            onChange={(val) => {
              setSelectedStatus(val);
              setPage(1);
            }}
            placeholder="所有认证结果"
            allowClear
            style={{ width: 140 }}
            options={LOGIN_STATUS_FILTERS}
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
        isLoading={isLoading && items.length === 0}
        error={items.length > 0 ? undefined : error}
        onRetry={() => refetch()}
        isEmpty={!isLoading && !error && items.length === 0}
        emptyText="暂无安全审计日志记录"
        errorTitle="安全日志加载失败"
        minHeight={140}
      >
        {isNarrow ? (
          <>
            <SettingsMobileRecordList
              items={items}
              rowKey={(item) => item.id}
              fields={mobileFields}
              ariaLabel="登录审计记录列表"
            />
            {total > pageSize && (
              <div className="settings-record-pagination">
                <Pagination {...pagination} size="small" simple />
              </div>
            )}
          </>
        ) : (
          <Table<LoginAuditLogItem>
            rowKey="id"
            columns={columns}
            dataSource={items}
            pagination={{ ...pagination, size: "small" }}
            size="small"
            scroll={{ x: 750 }}
          />
        )}
      </SectionDataState>
    </>
  );
}

function AdminActionSection() {
  const colors = useColors();
  const isNarrow = useMediaQuery("(max-width: 640px)");

  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [searchActor, setSearchActor] = useState("");
  const [selectedAction, setSelectedAction] = useState<string | undefined>();

  const { data, isLoading, error, refetch } = useAdminAuditActions({
    limit: pageSize,
    offset: (page - 1) * pageSize,
    actor_username: searchActor.trim() || undefined,
    action: selectedAction || undefined,
  });

  const items = data?.items ?? [];
  const total = data?.total ?? 0;

  const columns: ColumnsType<AdminAuditActionItem> = [
    {
      title: "时间",
      dataIndex: "created_at",
      key: "created_at",
      width: 165,
      render: (val: string) => val || "—",
    },
    {
      title: "操作者",
      dataIndex: "actor_username",
      key: "actor_username",
      width: 150,
      render: (val: string, record) => (
        <Space size={4}>
          <span style={{ fontWeight: 600, color: colors.textPrimary }}>{val || "系统"}</span>
          {record.actor_id ? (
            <Tag style={{ fontSize: "var(--c-font-xs, 11px)", lineHeight: "16px", padding: "0 4px" }}>
              #{record.actor_id}
            </Tag>
          ) : null}
        </Space>
      ),
    },
    {
      title: "操作",
      dataIndex: "action",
      key: "action",
      width: 150,
      render: (action: string) => (
        <Tag color="blue">{ACTION_LABELS[action] ?? action}</Tag>
      ),
    },
    {
      title: "对象",
      key: "target",
      width: 170,
      render: (_, record) =>
        record.target_label ? (
          <span>
            {record.target_label}
            {record.target_type ? (
              <span style={{ color: colors.textMuted, fontSize: "var(--c-font-xs)" }}>（{record.target_type}）</span>
            ) : null}
          </span>
        ) : (
          <span style={{ color: colors.textMuted }}>{record.target_id || "—"}</span>
        ),
    },
    {
      title: "变更内容",
      dataIndex: "details",
      key: "details",
      ellipsis: true,
      render: (details: string) => {
        const summary = summarizeDetails(details);
        return summary === "—" ? (
          <span style={{ color: colors.textMuted }}>—</span>
        ) : (
          <Tooltip title={details}>
            <span style={{ fontSize: "var(--c-font-sm)" }}>{summary}</span>
          </Tooltip>
        );
      },
    },
    {
      title: "来源 IP",
      dataIndex: "actor_ip",
      key: "actor_ip",
      width: 130,
      render: (ip: string) => (
        <code style={{ fontFamily: "var(--c-font-mono)", fontSize: "var(--c-font-sm)" }}>
          {ip || "未知"}
        </code>
      ),
    },
  ];

  const mobileFields: MobileRecordField<AdminAuditActionItem>[] = [
    { label: "时间", primary: true, render: (item) => item.created_at || "—" },
    {
      label: "操作者",
      primary: true,
      render: (item) => (
        <span>
          {item.actor_username || "系统"}
          {item.actor_id ? <Tag style={{ marginLeft: 4, fontSize: "var(--c-font-xs, 11px)", lineHeight: "16px", padding: "0 4px" }}>#{item.actor_id}</Tag> : null}
        </span>
      ),
    },
    { label: "操作", render: (item) => <Tag color="blue">{ACTION_LABELS[item.action] ?? item.action}</Tag> },
    {
      label: "对象",
      render: (item) =>
        item.target_label ? (
          <span>
            {item.target_label}
            {item.target_type ? <span style={{ color: colors.textMuted, fontSize: "var(--c-font-xs)" }}>（{item.target_type}）</span> : null}
          </span>
        ) : (
          <span style={{ color: colors.textMuted }}>{item.target_id || "—"}</span>
        ),
    },
    {
      label: "变更内容",
      fullWidth: true,
      render: (item) => {
        const summary = summarizeDetails(item.details);
        return summary === "—" ? <span style={{ color: colors.textMuted }}>—</span> : <span style={{ fontSize: "var(--c-font-sm)" }}>{summary}</span>;
      },
    },
    {
      label: "来源 IP",
      render: (item) => (
        <code style={{ fontFamily: "var(--c-font-mono)", fontSize: "var(--c-font-sm)" }}>{item.actor_ip || "未知"}</code>
      ),
    },
  ];

  const pagination = {
    current: page,
    pageSize,
    total,
    showSizeChanger: true,
    pageSizeOptions: ["10", "20", "50", "100"],
    onChange: (p: number, ps: number) => {
      setPage(p);
      setPageSize(ps);
    },
  };

  return (
    <>
      <div style={{ fontSize: "var(--c-font-sm)", color: colors.textMuted, marginBottom: 12 }}>
        记录管理员对账号、邀请码与全局配置的每一次变更。<strong>只记录改动了哪些字段</strong>，
        不会保存密钥类取值（API Key、密码等）。
      </div>

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
            placeholder="搜索操作者..."
            prefix={<SearchOutlined style={{ color: colors.textMuted }} />}
            value={searchActor}
            onChange={(e) => {
              setSearchActor(e.target.value);
              setPage(1);
            }}
            allowClear
            size="small"
            style={{ width: isNarrow ? "100%" : 160 }}
          />
          <Select
            size="small"
            value={selectedAction}
            onChange={(val) => {
              setSelectedAction(val);
              setPage(1);
            }}
            placeholder="所有操作类型"
            allowClear
            style={{ width: 160 }}
            options={ACTION_FILTERS}
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
        isLoading={isLoading && items.length === 0}
        error={items.length > 0 ? undefined : error}
        onRetry={() => refetch()}
        isEmpty={!isLoading && !error && items.length === 0}
        emptyText="暂无管理员操作记录"
        errorTitle="管理员操作记录加载失败"
        minHeight={140}
      >
        {isNarrow ? (
          <>
            <SettingsMobileRecordList
              items={items}
              rowKey={(item) => item.id}
              fields={mobileFields}
              ariaLabel="管理员操作记录列表"
            />
            {total > pageSize && (
              <div className="settings-record-pagination">
                <Pagination {...pagination} size="small" simple />
              </div>
            )}
          </>
        ) : (
          <Table<AdminAuditActionItem>
            rowKey="id"
            columns={columns}
            dataSource={items}
            pagination={{ ...pagination, size: "small" }}
            size="small"
            scroll={{ x: 820 }}
          />
        )}
      </SectionDataState>
    </>
  );
}

export default function SecurityAuditCard() {
  const { cardStyle, sectionCardBodyStyle } = useStyles();
  const [activeTab, setActiveTab] = useState("login");

  return (
    <Card
      title={<span><SafetyCertificateOutlined style={{ marginRight: 8 }} />安全与登录审计日志</span>}
      style={{ ...cardStyle, marginBottom: 16 }}
      styles={{ body: sectionCardBodyStyle }}
    >
      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        size="small"
        items={[
          { key: "login", label: "登录审计", children: <LoginAuditSection /> },
          { key: "admin", label: "管理员操作", children: <AdminActionSection /> },
        ]}
      />
    </Card>
  );
}
