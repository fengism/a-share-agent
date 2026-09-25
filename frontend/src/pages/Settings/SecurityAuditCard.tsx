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
import { Button, Card, Input, Select, Space, Table, Tag, Tooltip } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useLoginAuditLogs } from "../../api/queries";
import SectionDataState from "../../components/SectionDataState";
import { useMediaQuery } from "../../hooks/useMediaQuery";
import { semanticTagStyle, useColors, useStyles } from "../../styles/ui";
import type { LoginAuditLogItem } from "../../types/auth";

export default function SecurityAuditCard() {
  const { cardStyle, sectionCardBodyStyle } = useStyles();
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

  const statusTag = (status: string) => {
    switch (status) {
      case "success":
        return (
          <Tag icon={<CheckCircleOutlined />} style={semanticTagStyle("down")}>
            登录成功
          </Tag>
        );
      case "failed_credentials":
        return (
          <Tag icon={<CloseCircleOutlined />} style={semanticTagStyle("warning")}>
            密码错误
          </Tag>
        );
      case "failed_disabled":
        return (
          <Tag icon={<StopOutlined />} style={semanticTagStyle("up")}>
            账号已停用
          </Tag>
        );
      case "failed_rate_limited":
        return (
          <Tag icon={<ExclamationCircleOutlined />} color="default">
            限流阻断
          </Tag>
        );
      default:
        return <Tag>{status}</Tag>;
    }
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
            <Tag style={{ fontSize: "10px", lineHeight: "16px", padding: "0 4px" }}>
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
            <span style={{ color: colors.textMuted, fontSize: "12px", cursor: "pointer" }}>
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

  return (
    <Card
      title={<span><SafetyCertificateOutlined style={{ marginRight: 8 }} />安全与登录审计日志</span>}
      style={{ ...cardStyle, marginBottom: 16 }}
      styles={{ body: sectionCardBodyStyle }}
    >
      <div style={{ fontSize: "var(--c-font-sm)", color: colors.textMuted, marginBottom: 12 }}>
        实时记录系统所有用户的登录尝试、认证失败、禁用拦截与限流防御事件，便于追踪异常访问与安全合规审计。
      </div>

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
            options={[
              { value: "success", label: "登录成功" },
              { value: "failed_credentials", label: "密码错误" },
              { value: "failed_disabled", label: "账号已停用" },
              { value: "failed_rate_limited", label: "限流阻断" },
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
        isLoading={isLoading && items.length === 0}
        error={items.length > 0 ? undefined : error}
        onRetry={() => refetch()}
        isEmpty={!isLoading && !error && items.length === 0}
        emptyText="暂无安全审计日志记录"
        errorTitle="安全日志加载失败"
        minHeight={140}
      >
        <Table<LoginAuditLogItem>
          rowKey="id"
          columns={columns}
          dataSource={items}
          pagination={{
            current: page,
            pageSize,
            total,
            showSizeChanger: true,
            pageSizeOptions: ["10", "20", "50", "100"],
            size: "small",
            onChange: (p, ps) => {
              setPage(p);
              setPageSize(ps);
            },
          }}
          size="small"
          scroll={{ x: 750 }}
        />
      </SectionDataState>
    </Card>
  );
}
