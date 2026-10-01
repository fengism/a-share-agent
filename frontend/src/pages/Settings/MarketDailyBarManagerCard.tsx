import { useMemo, useState } from "react";
import {
  CalendarOutlined,
  DeleteOutlined,
  ReloadOutlined,
  RetweetOutlined,
  SyncOutlined,
} from "@ant-design/icons";
import {
  Button,
  Card,
  Checkbox,
  Col,
  DatePicker,
  Alert,
  Input,
  InputNumber,
  Popconfirm,
  Row,
  Segmented,
  Space,
  Switch,
  Tag,
  message,
} from "antd";
import dayjs from "dayjs";
import {
  useDeleteMarketDailyBars,
  useInvalidateMarketAdjustmentFactor,
  useMarketAdjustmentFactorStatus,
  useMarketDailyRefreshHistory,
  useRefreshMarketAdjustmentFactor,
  useRefreshMarketDailyBars,
} from "../../api/queries";
import { useColors, useStyles, semanticTagStyle } from "../../styles/ui";
import type {
  ConfigUpdate,
  MarketAdjustmentFactorHealth,
  MarketDailyRefreshCheckpoint,
  MarketDailySegment,
  MarketDailyRefreshStatus,
} from "../../types/settings";
import { summarizeRefreshResult } from "./marketDailyRefreshSummary";
import type { ConfigSectionProps } from "./sectionTypes";

const segmentOptions: Array<{ label: string; value: MarketDailySegment }> = [
  { label: "A股个股", value: "cn_stock" },
  { label: "A股指数", value: "cn_index" },
  { label: "港股个股", value: "hk_stock" },
  { label: "港股指数", value: "hk_index" },
];

const statusLabels: Record<MarketDailyRefreshStatus, string> = {
  pending: "等待",
  running: "执行中",
  success: "成功",
  skipped: "跳过",
  failed: "失败",
};

const statusStyles: Record<MarketDailyRefreshStatus, Parameters<typeof semanticTagStyle>[0]> = {
  pending: "info",
  running: "primary",
  success: "down",
  skipped: "warning",
  failed: "up",
};

const factorStatusLabels: Record<MarketAdjustmentFactorHealth, string> = {
  missing: "未生成",
  healthy: "健康",
  stale: "待复核",
  degraded: "使用 last-good",
  incomplete: "覆盖不完整",
};

const factorStatusStyles: Record<MarketAdjustmentFactorHealth, Parameters<typeof semanticTagStyle>[0]> = {
  missing: "info",
  healthy: "down",
  stale: "warning",
  degraded: "up",
  incomplete: "up",
};

interface Props extends ConfigSectionProps {
  onSave: () => void;
}

export default function MarketDailyBarManagerCard({ form, onChange, onSave, isSaving }: Props) {
  const { cardStyle, sectionCardBodyStyle, fieldLabelStyle } = useStyles();
  const colors = useColors();
  const [tradeDate, setTradeDate] = useState(dayjs());
  const [checkpoint, setCheckpoint] = useState<MarketDailyRefreshCheckpoint>("recheck");
  const [segments, setSegments] = useState<MarketDailySegment[]>(segmentOptions.map((item) => item.value));
  const [factorCode, setFactorCode] = useState("600519");
  const history = useMarketDailyRefreshHistory(true);
  const factorStatus = useMarketAdjustmentFactorStatus(factorCode, true);
  const refreshFactor = useRefreshMarketAdjustmentFactor();
  const invalidateFactor = useInvalidateMarketAdjustmentFactor();
  const refresh = useRefreshMarketDailyBars();
  const remove = useDeleteMarketDailyBars();

  const selectedDate = tradeDate.format("YYYY-MM-DD");
  const selectedHistory = useMemo(
    () => (history.data?.items ?? []).filter((item) => item.trade_date === selectedDate),
    [history.data?.items, selectedDate],
  );

  const executeRefresh = (options: { retryFailedOnly?: boolean; force?: boolean }) => {
    refresh.mutate(
      {
        trade_date: selectedDate,
        checkpoint,
        segments,
        retry_failed_only: options.retryFailedOnly,
        force: options.force,
      },
      {
        onSuccess: (result) => {
          const summary = summarizeRefreshResult(result);
          const detail = `成功 ${summary.success}，跳过 ${summary.skipped}，失败 ${summary.failed}`;
          if (summary.total === 0) {
            message.info("没有符合条件的失败分区需要重试");
          } else if (summary.failed > 0) {
            message.warning(`刷新完成但存在失败分区：${detail}`);
          } else {
            message.success(`刷新完成：${detail}`);
          }
          void history.refetch();
        },
        onError: (error: Error) => message.error(`刷新失败：${error.message}`),
      },
    );
  };

  const deleteDay = (rebuild: boolean) => {
    remove.mutate(
      {
        trade_date: selectedDate,
        segments,
        rebuild,
        checkpoint,
      },
      {
        onSuccess: (result) => {
          message.success(
            rebuild
              ? `已清理并重建，删除 ${result.deleted_bars} 条日行情`
              : `已删除 ${result.deleted_bars} 条日行情`,
          );
          void history.refetch();
        },
        onError: (error: Error) => message.error(`操作失败：${error.message}`),
      },
    );
  };

  const refreshAdjustmentFactor = () => {
    refreshFactor.mutate(factorCode, {
      onSuccess: (result) => {
        message.success(`复权因子复核完成：${factorStatusLabels[result.status]}`);
        void factorStatus.refetch();
      },
      onError: (error: Error) => message.error(`复权因子复核失败：${error.message}`),
    });
  };

  const invalidateAdjustmentFactor = () => {
    invalidateFactor.mutate(factorCode, {
      onSuccess: () => {
        message.success("复权因子已失效，下次复权请求会重新获取 XDXR");
        void factorStatus.refetch();
      },
      onError: (error: Error) => message.error(`复权因子失效失败：${error.message}`),
    });
  };

  const update = (patch: ConfigUpdate) => onChange(patch);
  const busy = refresh.isPending || remove.isPending;

  return (
    <Card
      title={<span><CalendarOutlined style={{ marginRight: 8 }} />历史日线归档（非实时行情）</span>}
      extra={(
        <Button size="small" icon={<ReloadOutlined />} loading={history.isFetching} onClick={() => history.refetch()}>
          刷新状态
        </Button>
      )}
      style={{ ...cardStyle, marginBottom: 16 }}
      styles={{ body: sectionCardBodyStyle }}
    >
      <Alert
        type="info"
        showIcon
        title="实时行情由行情页面自动拉取"
        description="交易时段内，指数与分时行情约每 30 秒、市场状态约每 60 秒自动刷新；此处只控制收盘后的历史日线归档，不会改变实时行情频率，也不会把盘中价格写入日线库。"
        style={{ marginBottom: 16 }}
      />
      <Row gutter={[16, 16]}>
        <Col xs={24} md={8}>
          <div style={fieldLabelStyle}>自动归档</div>
          <Switch
            checked={form.market_daily_bar_refresh_enabled ?? true}
            onChange={(checked) => update({ market_daily_bar_refresh_enabled: checked })}
            checkedChildren="启用"
            unCheckedChildren="暂停"
          />
        </Col>
        <Col xs={12} md={8}>
          <div style={fieldLabelStyle}>收盘任务检查间隔（秒）</div>
          <InputNumber
            min={15}
            max={3600}
            value={form.market_daily_bar_refresh_poll_seconds ?? 60}
            onChange={(value) => update({ market_daily_bar_refresh_poll_seconds: value ?? 60 })}
            style={{ width: "100%" }}
          />
        </Col>
        <Col xs={12} md={8}>
          <div style={fieldLabelStyle}>失败退避基数（秒）</div>
          <InputNumber
            min={1}
            max={1800}
            value={form.market_daily_bar_refresh_retry_base_seconds ?? 60}
            onChange={(value) => update({ market_daily_bar_refresh_retry_base_seconds: value ?? 60 })}
            style={{ width: "100%" }}
          />
        </Col>
        <Col xs={12} md={8}>
          <div style={fieldLabelStyle}>快照明细保留（天，默认 3 年）</div>
          <InputNumber
            min={7}
            max={3650}
            value={form.market_daily_observation_retention_days ?? 1095}
            onChange={(value) => update({ market_daily_observation_retention_days: value ?? 1095 })}
            style={{ width: "100%" }}
          />
        </Col>
        <Col xs={12} md={8}>
          <div style={fieldLabelStyle}>任务审计保留（天，默认 3 年）</div>
          <InputNumber
            min={30}
            max={3650}
            value={form.market_daily_attempt_retention_days ?? 1095}
            onChange={(value) => update({ market_daily_attempt_retention_days: value ?? 1095 })}
            style={{ width: "100%" }}
          />
        </Col>
        <Col span={24}>
          <Button type="primary" onClick={onSave} loading={isSaving}>保存归档配置</Button>
          <span style={{ marginLeft: 12, color: colors.textMuted, fontSize: "var(--c-font-sm)" }}>
            归档检查配置立即生效；审计保留周期在每 6 小时维护任务中应用。
          </span>
        </Col>
      </Row>

      <div style={{ borderTop: `1px solid ${colors.border}`, margin: "20px 0 16px" }} />
      <Row gutter={[16, 16]}>
        <Col xs={24} md={8}>
          <div style={fieldLabelStyle}>交易日</div>
          <DatePicker value={tradeDate} onChange={(value) => value && setTradeDate(value)} style={{ width: "100%" }} />
        </Col>
        <Col xs={24} md={8}>
          <div style={fieldLabelStyle}>刷新阶段</div>
          <Segmented
            block
            value={checkpoint}
            options={[{ label: "16:20 首次", value: "initial" }, { label: "17:00 复核", value: "recheck" }]}
            onChange={(value) => setCheckpoint(value as MarketDailyRefreshCheckpoint)}
          />
        </Col>
        <Col xs={24} md={8}>
          <div style={fieldLabelStyle}>分区</div>
          <Checkbox.Group
            options={segmentOptions}
            value={segments}
            onChange={(values) => setSegments(values as MarketDailySegment[])}
          />
        </Col>
        <Col span={24}>
          <Space wrap>
            <Button icon={<SyncOutlined />} loading={refresh.isPending} disabled={segments.length === 0} onClick={() => executeRefresh({})}>
              手动刷新
            </Button>
            <Button icon={<RetweetOutlined />} loading={refresh.isPending} disabled={segments.length === 0} onClick={() => executeRefresh({ retryFailedOnly: true })}>
              仅重试失败
            </Button>
            <Popconfirm title="强制重刷会覆盖该阶段已有结果，是否继续？" onConfirm={() => executeRefresh({ force: true })}>
              <Button danger loading={refresh.isPending} disabled={segments.length === 0}>强制重刷</Button>
            </Popconfirm>
            <Popconfirm title="确认删除所选日期和分区的数据？" onConfirm={() => deleteDay(false)}>
              <Button danger icon={<DeleteOutlined />} loading={remove.isPending} disabled={segments.length === 0}>清理数据</Button>
            </Popconfirm>
            <Popconfirm title="确认删除后立即重新拉取？" onConfirm={() => deleteDay(true)}>
              <Button icon={<ReloadOutlined />} loading={remove.isPending} disabled={segments.length === 0}>清理并重建</Button>
            </Popconfirm>
          </Space>
        </Col>
      </Row>

      <div style={{ borderTop: `1px solid ${colors.border}`, margin: "20px 0 12px" }} />
      <div style={{ color: colors.textPrimary, fontWeight: 600, marginBottom: 8 }}>
        {selectedDate} 刷新状态
      </div>
      {selectedHistory.length === 0 ? (
        <div style={{ color: colors.textMuted }}>暂无该日期的刷新记录</div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 8, opacity: busy ? 0.7 : 1 }}>
          {selectedHistory.map((item) => (
            <div
              key={`${item.trade_date}-${item.checkpoint}-${item.segment}`}
              style={{ border: `1px solid ${colors.border}`, padding: "10px 12px", borderRadius: 8 }}
            >
              <Space wrap>
                <strong>{segmentOptions.find((option) => option.value === item.segment)?.label ?? item.segment}</strong>
                <Tag>{item.checkpoint === "initial" ? "16:20" : "17:00"}</Tag>
                <Tag style={semanticTagStyle(statusStyles[item.status])}>{statusLabels[item.status]}</Tag>
                <span style={{ color: colors.textMuted }}>
                  尝试 {item.attempts} 次 · 接收 {item.expected_count ?? 0} 条 · 变更 {item.stored_count ?? 0} 条
                </span>
              </Space>
              {item.last_error && (
                <div style={{ color: "var(--c-error)", marginTop: 6, fontSize: "var(--c-font-sm)" }}>{item.last_error}</div>
              )}
            </div>
          ))}
        </div>
      )}

      <div style={{ borderTop: `1px solid ${colors.border}`, margin: "20px 0 12px" }} />
      <div style={{ color: colors.textPrimary, fontWeight: 600, marginBottom: 8 }}>A 股复权因子健康</div>
      <Space wrap style={{ marginBottom: 12 }}>
        <Input
          aria-label="A股代码"
          value={factorCode}
          maxLength={6}
          onChange={(event) => setFactorCode(event.target.value.replace(/\D/g, "").slice(0, 6))}
          placeholder="例如 600519"
          style={{ width: 150 }}
        />
        <Button onClick={() => factorStatus.refetch()} loading={factorStatus.isFetching} disabled={!/^\d{6}$/.test(factorCode)}>
          查询因子状态
        </Button>
        <Button type="primary" icon={<SyncOutlined />} onClick={refreshAdjustmentFactor} loading={refreshFactor.isPending} disabled={!/^\d{6}$/.test(factorCode)}>
          强制复核 XDXR
        </Button>
        <Popconfirm title="使本地衍生因子失效？公司行为审计记录会保留。" onConfirm={invalidateAdjustmentFactor}>
          <Button danger disabled={!/^\d{6}$/.test(factorCode)} loading={invalidateFactor.isPending}>使因子失效</Button>
        </Popconfirm>
      </Space>
      {factorStatus.data ? (
        <div style={{ border: `1px solid ${colors.border}`, padding: 12, borderRadius: 8 }}>
          <Space wrap>
            <strong>{factorStatus.data.code}</strong>
            <Tag style={semanticTagStyle(factorStatusStyles[factorStatus.data.status])}>
              {factorStatusLabels[factorStatus.data.status]}
            </Tag>
            <span style={{ color: colors.textMuted }}>
              日线 {factorStatus.data.bar_count} · 因子 {factorStatus.data.factor_count} · 公司行为 {factorStatus.data.action_count}
            </span>
          </Space>
          <div style={{ marginTop: 8, color: colors.textMuted, fontSize: "var(--c-font-sm)" }}>
            日线范围 {factorStatus.data.first_bar_date ?? "-"} ~ {factorStatus.data.last_bar_date ?? "-"}
            {` · 因子范围 ${factorStatus.data.first_factor_date ?? "-"} ~ ${factorStatus.data.last_factor_date ?? "-"}`}
            {factorStatus.data.last_checked_at ? ` · 最近检查 ${new Date(factorStatus.data.last_checked_at).toLocaleString()}` : ""}
          </div>
          {factorStatus.data.algorithm_version && (
            <div style={{ marginTop: 4, color: colors.textMuted, fontSize: "var(--c-font-sm)" }}>算法 {factorStatus.data.algorithm_version}</div>
          )}
          {factorStatus.data.last_error && (
            <div style={{ marginTop: 6, color: "var(--c-error)", fontSize: "var(--c-font-sm)" }}>{factorStatus.data.last_error}</div>
          )}
        </div>
      ) : (
        <div style={{ color: colors.textMuted }}>输入 6 位 A 股代码查询复权因子状态</div>
      )}
    </Card>
  );
}
