import { useState } from "react";
import { CheckCircleOutlined, ClockCircleOutlined, ReloadOutlined } from "@ant-design/icons";
import { Button, Card, Pagination, Select, Space, Table, Tag, Tooltip } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useMyLoginAuditLogs } from "../../api/queries";
import SectionDataState from "../../components/SectionDataState";
import { useMediaQuery } from "../../hooks/useMediaQuery";
import { formatMarketDateTime } from "../../utils/marketTime";
import { semanticTagStyle, useColors, useStyles } from "../../styles/ui";
import { LOGIN_STATUS_FILTERS, loginStatusMeta } from "./auditMeta";
import { describeUserAgent } from "./sessionDevice";
import SettingsMobileRecordList, { type MobileRecordField } from "./SettingsMobileRecordList";
import type { LoginAuditLogItem } from "../../types/auth";

const PAGE_SIZE = 10;

/**
 * 「我的登录记录」：普通用户自助查看自己的登录/失败尝试。
 *
 * 只读、只覆盖本人记录（后端按登录态 user_id 过滤），用于发现异常 IP 或撞库痕迹。
 */
export default function LoginHistoryCard() {
  const { cardStyle, sectionCardBodyStyle } = useStyles();
  const colors = useColors();
  const isNarrow = useMediaQuery("(max-width: 640px)");

  const [page, setPage] = useState(1);
  const [status, setStatus] = useState<string | undefined>();

  const { data, isLoading, error, refetch } = useMyLoginAuditLogs({
    limit: PAGE_SIZE,
    offset: (page - 1) * PAGE_SIZE,
    status,
  });

  const items = data?.items ?? [];
  const total = data?.total ?? 0;

  const columns: ColumnsType<LoginAuditLogItem> = [
    {
      title: "时间",
      dataIndex: "created_at",
      key: "created_at",
      width: 170,
      render: (value: string) => formatMarketDateTime(value, "—"),
    },
    {
      title: "结果",
      dataIndex: "status",
      key: "status",
      width: 120,
      render: (value: string) => {
        const meta = loginStatusMeta(value);
        return (
          <Tag
            icon={meta.tone === "down" ? <CheckCircleOutlined /> : <ClockCircleOutlined />}
            style={semanticTagStyle(meta.tone)}
          >
            {meta.label}
          </Tag>
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
      title: "设备",
      dataIndex: "user_agent",
      key: "user_agent",
      ellipsis: true,
      render: (ua: string) =>
        ua ? (
          <Tooltip title={ua}>
            <span style={{ color: colors.textMuted, fontSize: "var(--c-font-sm)", cursor: "pointer" }}>
              {describeUserAgent(ua).label}
            </span>
          </Tooltip>
        ) : (
          <span style={{ color: colors.textMuted }}>—</span>
        ),
    },
  ];

  const mobileFields: MobileRecordField<LoginAuditLogItem>[] = [
    {
      label: "时间",
      primary: true,
      render: (item) => formatMarketDateTime(item.created_at, "—"),
    },
    {
      label: "结果",
      render: (item) => {
        const meta = loginStatusMeta(item.status);
        return (
          <Tag icon={meta.tone === "down" ? <CheckCircleOutlined /> : <ClockCircleOutlined />} style={semanticTagStyle(meta.tone)}>
            {meta.label}
          </Tag>
        );
      },
    },
    {
      label: "来源 IP",
      render: (item) => (
        <code style={{ fontFamily: "var(--c-font-mono)", fontSize: "var(--c-font-sm)" }}>
          {item.ip_address || "未知"}
        </code>
      ),
    },
    {
      label: "设备",
      fullWidth: true,
      render: (item) =>
        item.user_agent ? (
          <Tooltip title={item.user_agent}>
            <span style={{ color: colors.textMuted, fontSize: "var(--c-font-sm)" }}>{describeUserAgent(item.user_agent).label}</span>
          </Tooltip>
        ) : (
          <span style={{ color: colors.textMuted }}>—</span>
        ),
    },
  ];

  const pagination = {
    current: page,
    pageSize: PAGE_SIZE,
    total,
    showSizeChanger: false,
    onChange: setPage,
  };

  return (
    <Card
      title={
        <span>
          <ClockCircleOutlined style={{ marginRight: 8 }} />
          我的登录记录
        </span>
      }
      style={{ ...cardStyle, marginBottom: 16 }}
      styles={{ body: sectionCardBodyStyle }}
      extra={
        <Button size="small" icon={<ReloadOutlined />} onClick={() => refetch()} loading={isLoading}>
          刷新
        </Button>
      }
    >
      <div style={{ fontSize: "var(--c-font-sm)", color: colors.textMuted, marginBottom: 12 }}>
        只显示当前账号的登录尝试，便于发现异常 IP 或撞库痕迹；如需让某台设备下线，请在上方「登录设备」中操作。
      </div>

      <Space wrap style={{ marginBottom: 12 }}>
        <Select
          size="small"
          value={status}
          onChange={(value) => {
            setStatus(value);
            setPage(1);
          }}
          placeholder="所有结果"
          allowClear
          style={{ width: isNarrow ? "100%" : 140 }}
          options={LOGIN_STATUS_FILTERS}
        />
      </Space>

      <SectionDataState
        isLoading={isLoading && items.length === 0}
        error={items.length > 0 ? undefined : error}
        onRetry={() => refetch()}
        isEmpty={!isLoading && !error && items.length === 0}
        emptyText="暂无登录记录"
      >
        {isNarrow ? (
          <>
            <SettingsMobileRecordList
              items={items}
              rowKey={(item) => item.id}
              fields={mobileFields}
              ariaLabel="我的登录记录列表"
            />
            {total > PAGE_SIZE && (
              <div className="settings-record-pagination">
                <Pagination {...pagination} size="small" simple />
              </div>
            )}
          </>
        ) : (
          <Table
            size="small"
            rowKey="id"
            columns={columns}
            dataSource={items}
            pagination={{ ...pagination, size: "small" }}
            scroll={{ x: 640 }}
          />
        )}
      </SectionDataState>
    </Card>
  );
}
