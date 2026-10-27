import { useState } from "react";
import {
  DesktopOutlined,
  MobileOutlined,
  ReloadOutlined,
  SafetyOutlined,
} from "@ant-design/icons";
import { Button, Card, Popconfirm, Space, Table, Tag, Tooltip, message } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useRevokeSession, useSessions } from "../../api/queries";
import SectionDataState from "../../components/SectionDataState";
import { useMediaQuery } from "../../hooks/useMediaQuery";
import { formatMarketDateTime } from "../../utils/marketTime";
import { describeUserAgent } from "./sessionDevice";
import { useColors, useStyles } from "../../styles/ui";
import type { SessionItem } from "../../types/auth";

export default function SessionManagerCard() {
  const { cardStyle, sectionCardBodyStyle } = useStyles();
  const colors = useColors();
  const isNarrow = useMediaQuery("(max-width: 640px)");
  const [pendingId, setPendingId] = useState<string | null>(null);

  const { data, isLoading, error, refetch } = useSessions();
  const revokeSession = useRevokeSession();

  const items = data?.items ?? [];

  const handleRevoke = (record: SessionItem) => {
    setPendingId(record.session_id);
    revokeSession.mutate(record.session_id, {
      onSuccess: () => {
        if (record.is_current) {
          message.success("当前设备已退出，请重新登录");
          window.location.href = "/login";
          return;
        }
        message.success("该设备已退出登录");
      },
      onSettled: () => setPendingId(null),
    });
  };

  const columns: ColumnsType<SessionItem> = [
    {
      title: "设备",
      key: "device",
      width: 190,
      render: (_, record) => {
        const device = describeUserAgent(record.user_agent);
        return (
          <Space size={6}>
            {device.icon === "mobile" ? <MobileOutlined /> : <DesktopOutlined />}
            <span style={{ color: colors.textPrimary }}>{device.label}</span>
            {record.is_current ? (
              <Tag color="green" style={{ marginInlineStart: 4 }}>
                当前
              </Tag>
            ) : null}
          </Space>
        );
      },
    },
    {
      title: "来源 IP",
      dataIndex: "ip_address",
      key: "ip_address",
      width: 140,
      render: (ip: string) => (
        <code style={{ fontFamily: "var(--c-font-mono)", fontSize: "var(--c-font-sm)" }}>
          {ip || "未知"}
        </code>
      ),
    },
    {
      title: "登录时间",
      dataIndex: "created_at",
      key: "created_at",
      width: 170,
      render: (value: string) => formatMarketDateTime(value, "—"),
    },
    {
      title: "最近活跃",
      dataIndex: "last_seen_at",
      key: "last_seen_at",
      width: 170,
      render: (value: string) => formatMarketDateTime(value, "—"),
    },
    {
      title: "失效时间",
      dataIndex: "expires_at",
      key: "expires_at",
      width: 170,
      render: (value: string) => formatMarketDateTime(value, "—"),
    },
    {
      title: "客户端 UA",
      dataIndex: "user_agent",
      key: "user_agent",
      ellipsis: true,
      render: (ua: string) =>
        ua ? (
          <Tooltip title={ua}>
            <span style={{ color: colors.textMuted, fontSize: "12px", cursor: "pointer" }}>
              {ua.length > 44 ? `${ua.slice(0, 44)}...` : ua}
            </span>
          </Tooltip>
        ) : (
          <span style={{ color: colors.textMuted }}>—</span>
        ),
    },
    {
      title: "操作",
      key: "actions",
      width: 110,
      render: (_, record) => (
        <Popconfirm
          title={record.is_current ? "退出当前设备？" : "让该设备下线？"}
          description={
            record.is_current
              ? "退出后需要重新输入账号密码登录。"
              : "该设备的登录状态会立即失效。"
          }
          okText="确认退出"
          cancelText="取消"
          onConfirm={() => handleRevoke(record)}
        >
          <Button
            type="link"
            size="small"
            danger
            loading={pendingId === record.session_id}
            disabled={pendingId !== null && pendingId !== record.session_id}
          >
            退出
          </Button>
        </Popconfirm>
      ),
    },
  ];

  return (
    <Card
      title={<span><SafetyOutlined style={{ marginRight: 8 }} />登录设备</span>}
      style={{ ...cardStyle, marginBottom: 16 }}
      styles={{ body: sectionCardBodyStyle }}
      extra={
        <Button size="small" icon={<ReloadOutlined />} onClick={() => refetch()} loading={isLoading}>
          刷新
        </Button>
      }
    >
      <div style={{ fontSize: "var(--c-font-sm)", color: colors.textMuted, marginBottom: 12 }}>
        这里列出当前账号仍然有效的登录会话。发现陌生设备时请立即退出，并修改密码
        （修改密码会自动踢出其它设备）。
      </div>

      <SectionDataState
        isLoading={isLoading && items.length === 0}
        error={items.length > 0 ? undefined : error}
        onRetry={() => refetch()}
        isEmpty={!isLoading && !error && items.length === 0}
        emptyText="暂无有效登录会话"
        errorTitle="登录设备加载失败"
        minHeight={120}
      >
        <Table<SessionItem>
          rowKey="session_id"
          columns={columns}
          dataSource={items}
          pagination={false}
          size="small"
          scroll={{ x: isNarrow ? 620 : undefined }}
        />
      </SectionDataState>
    </Card>
  );
}
