import { useMemo, useState } from "react";
import {
  CalendarOutlined,
  CheckCircleFilled,
  CloudDownloadOutlined,
  DatabaseOutlined,
  DeleteOutlined,
  HistoryOutlined,
  InfoCircleOutlined,
  ReloadOutlined,
  RetweetOutlined,
  SafetyCertificateOutlined,
  SaveOutlined,
  SettingOutlined,
  SyncOutlined,
  UndoOutlined,
} from "@ant-design/icons";
import {
  Button,
  Card,
  Checkbox,
  DatePicker,
  Input,
  InputNumber,
  Popconfirm,
  Progress,
  Segmented,
  Select,
  Space,
  Switch,
  Tag,
  message,
} from "antd";
import dayjs from "dayjs";
import {
  useCancelMarketDailyBackfill,
  useCreateMarketDailyBackfill,
  useDeleteMarketDailyBars,
  useInvalidateMarketAdjustmentFactor,
  useMarketAdjustmentFactorStatus,
  useMarketDailyBackfills,
  useMarketDailyRefreshHistory,
  useRefreshMarketAdjustmentFactor,
  useRefreshMarketDailyBars,
  useRetryFailedMarketDailyBackfill,
} from "../../api/queries";
import { semanticTagStyle, useStyles } from "../../styles/ui";
import type {
  ConfigUpdate,
  MarketAdjustmentFactorHealth,
  MarketDailyRefreshCheckpoint,
  MarketDailyRefreshStatus,
  MarketDailySegment,
} from "../../types/settings";
import { summarizeRefreshResult } from "./marketDailyRefreshSummary";
import type { ConfigSectionProps } from "./sectionTypes";
import "./market-daily-bar-manager.css";

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

const backfillStatusLabels = {
  pending: "等待执行",
  running: "执行中",
  succeeded: "已完成",
  failed: "部分失败",
  cancelled: "已取消",
} as const;

const backfillStatusColors = {
  pending: "default",
  running: "processing",
  succeeded: "success",
  failed: "error",
  cancelled: "warning",
} as const;

const providerSourceOptions = [
  { value: 2, label: "TDX + 腾讯（最低双源校验）" },
  { value: 3, label: "再降级到 AkShare 新浪" },
  { value: 4, label: "再降级到东方财富直连" },
  { value: 5, label: "再降级到新浪直连" },
  { value: 6, label: "全部来源（财联社末级兜底）" },
];

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
  isDirty?: boolean;
  onReset?: () => void;
}

interface PanelHeaderProps {
  icon: React.ReactNode;
  title: string;
  description: string;
  extra?: React.ReactNode;
  isDirty?: boolean;
}

function PanelHeader({ icon, title, description, extra, isDirty }: PanelHeaderProps) {
  return (
    <div className="market-daily-panel__header">
      <div className="market-daily-panel__heading">
        <span className="market-daily-panel__icon">{icon}</span>
        <div>
          <div className="market-daily-panel__title" style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
            <span>{title}</span>
            {isDirty && (
              <span
                style={{
                  display: "inline-block",
                  width: 7,
                  height: 7,
                  borderRadius: "50%",
                  backgroundColor: "var(--c-warning, #faad14)",
                }}
                title="存在未保存的修改"
              />
            )}
          </div>
          <div className="market-daily-panel__description">{description}</div>
        </div>
      </div>
      {extra ? <div className="market-daily-panel__extra">{extra}</div> : null}
    </div>
  );
}

export default function MarketDailyBarManagerCard({ form, onChange, onSave, isSaving, isDirty, onReset }: Props) {
  useStyles();
  const [tradeDate, setTradeDate] = useState(dayjs());
  const [backfillRange, setBackfillRange] = useState<[dayjs.Dayjs, dayjs.Dayjs]>([
    dayjs().subtract(1, "year"),
    dayjs().subtract(1, "day"),
  ]);
  const [overwriteBackfill, setOverwriteBackfill] = useState(false);
  const [maxProviderSources, setMaxProviderSources] = useState(4);
  const [checkpoint, setCheckpoint] = useState<MarketDailyRefreshCheckpoint>("recheck");
  const [segments, setSegments] = useState<MarketDailySegment[]>(segmentOptions.map((item) => item.value));
  const [factorCode, setFactorCode] = useState("600519");
  const history = useMarketDailyRefreshHistory(true);
  const backfills = useMarketDailyBackfills(true);
  const createBackfill = useCreateMarketDailyBackfill();
  const cancelBackfill = useCancelMarketDailyBackfill();
  const retryFailedBackfill = useRetryFailedMarketDailyBackfill();
  const factorStatus = useMarketAdjustmentFactorStatus(factorCode, true);
  const refreshFactor = useRefreshMarketAdjustmentFactor();
  const invalidateFactor = useInvalidateMarketAdjustmentFactor();
  const refresh = useRefreshMarketDailyBars();
  const remove = useDeleteMarketDailyBars();

  const selectedDate = tradeDate.format("YYYY-MM-DD");
  const groupedHistory = useMemo(() => {
    const items = history.data?.items ?? [];
    const uniqueDates = Array.from(new Set(items.map((item) => item.trade_date))).sort((a, b) => b.localeCompare(a));
    const top3Dates = uniqueDates.slice(0, 3);
    const datesToShow = top3Dates.length > 0 ? top3Dates : [selectedDate];

    if (!datesToShow.includes(selectedDate) && items.some((item) => item.trade_date === selectedDate)) {
      datesToShow.push(selectedDate);
      datesToShow.sort((a, b) => b.localeCompare(a));
    }

    return datesToShow.map((date) => ({
      date,
      items: items.filter((item) => item.trade_date === date),
    }));
  }, [history.data?.items, selectedDate]);

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

  const startBackfill = () => {
    createBackfill.mutate(
      {
        start_date: backfillRange[0].format("YYYY-MM-DD"),
        end_date: backfillRange[1].format("YYYY-MM-DD"),
        overwrite_existing: overwriteBackfill,
        max_provider_sources: maxProviderSources,
      },
      {
        onSuccess: () => message.success("历史回填任务已创建，将在后台逐股票执行"),
        onError: (error: Error) => message.error(`创建历史回填失败：${error.message}`),
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
  const autoArchiveEnabled = form.market_daily_bar_refresh_enabled ?? true;

  return (
    <Card
      className="market-daily-manager"
      title={(
        <div className="market-daily-manager__title">
          <span className="market-daily-manager__title-icon"><CalendarOutlined /></span>
          <div>
            <span>历史日线归档</span>
            <small>非实时行情</small>
          </div>
        </div>
      )}
      extra={(
        <Space size={10}>
          <Tag className="market-daily-manager__status-tag" color={autoArchiveEnabled ? "success" : "default"}>
            {autoArchiveEnabled ? <CheckCircleFilled /> : null}
            {autoArchiveEnabled ? "自动归档已开启" : "自动归档已暂停"}
          </Tag>
          <Button
            size="small"
            icon={<ReloadOutlined />}
            loading={history.isFetching || backfills.isFetching}
            onClick={() => {
              void history.refetch();
              void backfills.refetch();
            }}
          >
            刷新状态
          </Button>
        </Space>
      )}
    >
      <div className="market-daily-manager__notice">
        <InfoCircleOutlined />
        <div>
          <strong>实时行情由行情页面自动拉取</strong>
          <span>
            交易时段内，指数与分时行情约每 30 秒、市场状态约每 60 秒自动刷新；此处只控制收盘后的历史日线归档，不会改变实时行情频率，也不会把盘中价格写入日线库。
          </span>
        </div>
      </div>

      <section className="market-daily-config" aria-labelledby="market-daily-config-title">
        <PanelHeader
          icon={<SettingOutlined />}
          title="自动归档配置"
          description="设置盘后归档检查频率、失败退避与审计数据保留周期。"
          isDirty={isDirty}
          extra={(
            <Space>
              <Button aria-label="保存归档配置" type="primary" icon={<SaveOutlined />} onClick={onSave} loading={isSaving}>
                保存归档配置
              </Button>
              {isDirty && onReset && (
                <Popconfirm
                  title="撤销此卡片的修改？"
                  description="将还原为上次保存的值，当前未保存的输入将被清空。"
                  onConfirm={onReset}
                  okText="确认撤销"
                  cancelText="继续编辑"
                >
                  <Button
                    icon={<UndoOutlined />}
                    disabled={isSaving}
                  >
                    撤销更改
                  </Button>
                </Popconfirm>
              )}
              {isDirty && (
                <span style={{ fontSize: "var(--c-font-xs, 12px)", color: "var(--c-warning, #faad14)" }}>
                  已更改（未保存）
                </span>
              )}
            </Space>
          )}
        />

        <div className="market-daily-config__switch-row">
          <div>
            <div id="market-daily-config-title" className="market-daily-config__switch-title">启用自动归档</div>
            <div className="market-daily-config__switch-description">收盘后自动检查并归档历史日线数据</div>
          </div>
          <Switch
            aria-label="启用自动归档"
            checked={autoArchiveEnabled}
            onChange={(checked) => update({ market_daily_bar_refresh_enabled: checked })}
          />
        </div>

        <div className="market-daily-config__grid">
          <label className="market-daily-field">
            <span>收盘任务检查间隔</span>
            <Space.Compact style={{ width: "100%" }}>
              <InputNumber
                style={{ width: "100%" }}
                min={15}
                max={3600}
                value={form.market_daily_bar_refresh_poll_seconds ?? 60}
                onChange={(value) => update({ market_daily_bar_refresh_poll_seconds: value ?? 60 })}
              />
              <span className="ant-input-group-addon" style={{ display: "inline-flex", alignItems: "center", padding: "0 11px", background: "var(--c-nested-bg)", border: "1px solid var(--c-border)", borderLeft: 0, borderRadius: "0 6px 6px 0", color: "var(--c-text-secondary)", fontSize: "var(--c-font-sm)" }}>秒</span>
            </Space.Compact>
          </label>
          <label className="market-daily-field">
            <span>失败退避基数</span>
            <Space.Compact style={{ width: "100%" }}>
              <InputNumber
                style={{ width: "100%" }}
                min={1}
                max={1800}
                value={form.market_daily_bar_refresh_retry_base_seconds ?? 60}
                onChange={(value) => update({ market_daily_bar_refresh_retry_base_seconds: value ?? 60 })}
              />
              <span className="ant-input-group-addon" style={{ display: "inline-flex", alignItems: "center", padding: "0 11px", background: "var(--c-nested-bg)", border: "1px solid var(--c-border)", borderLeft: 0, borderRadius: "0 6px 6px 0", color: "var(--c-text-secondary)", fontSize: "var(--c-font-sm)" }}>秒</span>
            </Space.Compact>
          </label>
          <label className="market-daily-field">
            <span>快照明细保留</span>
            <Space.Compact style={{ width: "100%" }}>
              <InputNumber
                style={{ width: "100%" }}
                min={7}
                max={3650}
                value={form.market_daily_observation_retention_days ?? 1095}
                onChange={(value) => update({ market_daily_observation_retention_days: value ?? 1095 })}
              />
              <span className="ant-input-group-addon" style={{ display: "inline-flex", alignItems: "center", padding: "0 11px", background: "var(--c-nested-bg)", border: "1px solid var(--c-border)", borderLeft: 0, borderRadius: "0 6px 6px 0", color: "var(--c-text-secondary)", fontSize: "var(--c-font-sm)" }}>天</span>
            </Space.Compact>
          </label>
          <label className="market-daily-field">
            <span>任务审计保留</span>
            <Space.Compact style={{ width: "100%" }}>
              <InputNumber
                style={{ width: "100%" }}
                min={30}
                max={3650}
                value={form.market_daily_attempt_retention_days ?? 1095}
                onChange={(value) => update({ market_daily_attempt_retention_days: value ?? 1095 })}
              />
              <span className="ant-input-group-addon" style={{ display: "inline-flex", alignItems: "center", padding: "0 11px", background: "var(--c-nested-bg)", border: "1px solid var(--c-border)", borderLeft: 0, borderRadius: "0 6px 6px 0", color: "var(--c-text-secondary)", fontSize: "var(--c-font-sm)" }}>天</span>
            </Space.Compact>
          </label>
        </div>
        <div className="market-daily-config__hint">配置保存后立即生效；审计保留周期在每 6 小时维护任务中应用。</div>
      </section>

      <section className="market-daily-panel market-daily-panel--backfill" aria-labelledby="market-backfill-title">
        <PanelHeader
          icon={<CloudDownloadOutlined />}
          title="A 股全市场历史回填"
          description="后台逐股票拉取未复权日 K，支持断点续跑、双源校验和失败统计。"
        />

        <div className="market-daily-backfill__grid">
          <label className="market-daily-field market-daily-field--wide">
            <span id="market-backfill-title">历史日期范围</span>
            <DatePicker.RangePicker
              value={backfillRange}
              disabledDate={(current) => current != null && !current.isBefore(dayjs(), "day")}
              onChange={(value) => value?.[0] && value?.[1] && setBackfillRange([value[0], value[1]])}
            />
          </label>
          <label className="market-daily-field">
            <span>数据源降级范围</span>
            <Select value={maxProviderSources} options={providerSourceOptions} onChange={setMaxProviderSources} />
          </label>
          <div className="market-daily-overwrite">
            <div>
              <span>覆盖已有日线</span>
              <small>关闭时自动跳过已入库记录</small>
            </div>
            <Switch
              aria-label="覆盖已有日线"
              checked={overwriteBackfill}
              onChange={setOverwriteBackfill}
            />
          </div>
        </div>

        <div className="market-daily-backfill__actions">
          <Popconfirm title="全市场历史回填可能运行较长时间，确认创建任务？" onConfirm={startBackfill}>
            <Button type="primary" icon={<CloudDownloadOutlined />} loading={createBackfill.isPending}>
              创建历史回填任务
            </Button>
          </Popconfirm>
          <span>当前仅支持 A 股个股，结束日期必须早于今天。</span>
        </div>

        <div className="market-daily-job-list">
          {(backfills.data?.items ?? []).length === 0 ? (
            <div className="market-daily-empty">
              <DatabaseOutlined />
              <div>
                <strong>暂无历史回填任务</strong>
                <span>选择日期范围并创建任务后，进度会在此处实时展示。</span>
              </div>
            </div>
          ) : (
            (backfills.data?.items ?? []).slice(0, 5).map((job) => {
              const percent = job.total_instruments > 0
                ? Math.round(job.completed_instruments / job.total_instruments * 100)
                : 0;
              return (
                <div key={job.job_id} className="market-daily-job">
                  <div className="market-daily-job__topline">
                    <div className="market-daily-job__tags">
                      <strong>{job.start_date} 至 {job.end_date}</strong>
                      <Tag color={backfillStatusColors[job.status]}>{backfillStatusLabels[job.status]}</Tag>
                      <Tag>{providerSourceOptions.find((item) => item.value === job.max_provider_sources)?.label ?? `${job.max_provider_sources} 个来源`}</Tag>
                      {job.overwrite_existing ? <Tag color="warning">覆盖已有</Tag> : null}
                      {job.average_quality_score != null ? <Tag color="cyan">质量 {job.average_quality_score.toFixed(1)}</Tag> : null}
                    </div>
                    <Space size={8} wrap>
                      {(job.status === "pending" || job.status === "running") ? (
                        <Popconfirm
                          title="确认取消该回填任务？"
                          description="任务中止后已写入的数据将保留。"
                          okText="确认取消"
                          cancelText="暂不取消"
                          okButtonProps={{ danger: true }}
                          onConfirm={() => cancelBackfill.mutate(job.job_id)}
                        >
                          <Button
                            size="small"
                            danger
                            loading={cancelBackfill.isPending && cancelBackfill.variables === job.job_id}
                          >
                            取消
                          </Button>
                        </Popconfirm>
                      ) : null}
                      {job.status === "failed" && job.retryable_failed_instruments > 0 ? (
                        <Popconfirm
                          title={`确认仅重试 ${job.retryable_failed_instruments} 只临时上游失败股票？`}
                          onConfirm={() => retryFailedBackfill.mutate(job.job_id)}
                        >
                          <Button
                            size="small"
                            icon={<RetweetOutlined />}
                            loading={retryFailedBackfill.isPending && retryFailedBackfill.variables === job.job_id}
                          >
                            重试临时失败
                          </Button>
                        </Popconfirm>
                      ) : null}
                    </Space>
                  </div>
                  <div className="market-daily-job__metrics">
                    <span>成功 <strong>{job.succeeded_instruments}</strong></span>
                    <span>失败 <strong>{job.failed_instruments}</strong></span>
                    <span>写入 <strong>{job.stored_bars}</strong> 根</span>
                    {job.current_code ? <span>正在处理 <strong>{job.current_code}</strong></span> : null}
                  </div>
                  <Progress percent={percent} status={job.status === "failed" ? "exception" : undefined} />
                  {job.last_error ? <div className="market-daily-job__error">最近错误：{job.last_error}</div> : null}
                  {job.failure_details.length > 0 ? (
                    <details className="market-daily-job__details">
                      <summary>查看失败明细（最多展示 {job.failure_details.length} 条）</summary>
                      <div>
                        {job.failure_details.map((failure) => (
                          <p key={`${job.job_id}-${failure.code}`}>
                            <strong>{failure.code}</strong>
                            {failure.kind === "source_inconsistent" ? "（数据冲突）" : failure.retryable ? "（可重试）" : "（数据无效）"}
                            ：{failure.error}
                          </p>
                        ))}
                      </div>
                    </details>
                  ) : null}
                </div>
              );
            })
          )}
        </div>
      </section>

      <section className="market-daily-panel" aria-labelledby="market-daily-manual-title">
        <PanelHeader
          icon={<HistoryOutlined />}
          title="每日归档管理"
          description="按交易日和市场分区执行手动刷新、失败重试或数据重建。"
        />

        <div className="market-daily-manual__grid">
          <label className="market-daily-field">
            <span id="market-daily-manual-title">交易日</span>
            <DatePicker value={tradeDate} onChange={(value) => value && setTradeDate(value)} />
          </label>
          <label className="market-daily-field">
            <span>刷新阶段</span>
            <Segmented
              block
              value={checkpoint}
              options={[{ label: "16:20 首次", value: "initial" }, { label: "17:00 复核", value: "recheck" }]}
              onChange={(value) => setCheckpoint(value as MarketDailyRefreshCheckpoint)}
            />
          </label>
          <div className="market-daily-field market-daily-field--segments">
            <span>分区</span>
            <Checkbox.Group
              options={segmentOptions}
              value={segments}
              onChange={(values) => setSegments(values as MarketDailySegment[])}
            />
          </div>
        </div>

        <div className="market-daily-manual__actions">
          <Button type="primary" icon={<SyncOutlined />} loading={refresh.isPending} disabled={segments.length === 0} onClick={() => executeRefresh({})}>
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
        </div>

        <div className="market-daily-history__header">
          <div>
            <strong>日线归档状态（最新 3 天）</strong>
            <span>当前操作日期：{selectedDate}</span>
          </div>
        </div>

        {groupedHistory.every((group) => group.items.length === 0) ? (
          <div className="market-daily-empty market-daily-empty--compact">
            <HistoryOutlined />
            <div><strong>暂无刷新记录</strong><span>执行归档操作后，状态会在这里展示。</span></div>
          </div>
        ) : (
          <div className="market-daily-history" style={{ opacity: busy ? 0.7 : 1 }}>
            {groupedHistory.map((group) => {
              const hasFailed = group.items.some((item) => item.status === "failed");
              const isRunning = group.items.some((item) => item.status === "running");
              const allSuccess = group.items.length > 0 && group.items.every((item) => item.status === "success" || item.status === "skipped");

              return (
                <div key={group.date} className={`market-daily-history__day${group.date === selectedDate ? " is-active" : ""}`}>
                  <div className="market-daily-history__day-header">
                    <Space size={8} wrap>
                      <strong>{group.date}</strong>
                      {hasFailed ? <Tag color="error">存在失败</Tag> : isRunning ? <Tag color="processing">同步中</Tag> : allSuccess ? <Tag color="success">全部完成</Tag> : null}
                      {group.date === selectedDate ? <Tag color="blue">当前操作日期</Tag> : null}
                    </Space>
                    {group.date !== selectedDate ? (
                      <Button type="link" size="small" onClick={() => setTradeDate(dayjs(group.date))}>设为操作日期</Button>
                    ) : null}
                  </div>
                  {group.items.length === 0 ? (
                    <div className="market-daily-history__empty">暂无记录</div>
                  ) : (
                    <div className="market-daily-history__segments">
                      {segmentOptions.map((segment) => {
                        const initialJob = group.items.find((item) => item.segment === segment.value && item.checkpoint === "initial");
                        const recheckJob = group.items.find((item) => item.segment === segment.value && item.checkpoint === "recheck");
                        if (!initialJob && !recheckJob) return null;
                        const errorMessage = recheckJob?.last_error || initialJob?.last_error;
                        const storedCount = (recheckJob?.stored_count ?? initialJob?.stored_count) ?? 0;
                        const expectedCount = (recheckJob?.expected_count ?? initialJob?.expected_count) ?? 0;

                        return (
                          <div key={segment.value} className="market-daily-history__segment">
                            <div className="market-daily-history__segment-main">
                              <div className="market-daily-history__segment-title">
                                <strong>{segment.label}</strong>
                                <span className="market-daily-history__segment-counts">接收 {expectedCount} 条 · 变更 {storedCount} 条</span>
                              </div>
                              <div className="market-daily-history__segment-tags">
                                {initialJob ? (
                                  <span className="market-daily-history__checkpoint">
                                    <small>16:20</small>
                                    <Tag style={semanticTagStyle(statusStyles[initialJob.status])}>{statusLabels[initialJob.status]}</Tag>
                                  </span>
                                ) : null}
                                {recheckJob ? (
                                  <span className="market-daily-history__checkpoint">
                                    <small>17:00</small>
                                    <Tag style={semanticTagStyle(statusStyles[recheckJob.status])}>{statusLabels[recheckJob.status]}</Tag>
                                  </span>
                                ) : null}
                              </div>
                            </div>
                            {errorMessage ? <div className="market-daily-history__error">{errorMessage}</div> : null}
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </section>

      <section className="market-daily-panel market-daily-panel--factor" aria-labelledby="market-factor-title">
        <PanelHeader
          icon={<SafetyCertificateOutlined />}
          title="A 股复权因子健康"
          description="核验公司行为、前后复权因子覆盖与本地 last-good 状态。"
        />
        <div className="market-daily-factor__toolbar">
          <Input
            aria-label="A股代码"
            value={factorCode}
            maxLength={6}
            onChange={(event) => setFactorCode(event.target.value.replace(/\D/g, "").slice(0, 6))}
            placeholder="例如 600519"
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
        </div>
        {factorStatus.data ? (
          <div className="market-daily-factor__result">
            <div className="market-daily-factor__summary">
              <Space wrap>
                <strong id="market-factor-title">{factorStatus.data.code}</strong>
                <Tag style={semanticTagStyle(factorStatusStyles[factorStatus.data.status])}>
                  {factorStatusLabels[factorStatus.data.status]}
                </Tag>
              </Space>
              <div className="market-daily-factor__metrics">
                <span><small>日线</small><strong>{factorStatus.data.bar_count}</strong></span>
                <span><small>因子</small><strong>{factorStatus.data.factor_count}</strong></span>
                <span><small>公司行为</small><strong>{factorStatus.data.action_count}</strong></span>
              </div>
            </div>
            <div className="market-daily-factor__meta">
              <span>日线范围 {factorStatus.data.first_bar_date ?? "-"} ~ {factorStatus.data.last_bar_date ?? "-"}</span>
              <span>因子范围 {factorStatus.data.first_factor_date ?? "-"} ~ {factorStatus.data.last_factor_date ?? "-"}</span>
              {factorStatus.data.last_checked_at ? <span>最近检查 {new Date(factorStatus.data.last_checked_at).toLocaleString()}</span> : null}
              {factorStatus.data.algorithm_version ? <span>算法 {factorStatus.data.algorithm_version}</span> : null}
            </div>
            {factorStatus.data.last_error ? <div className="market-daily-factor__error">{factorStatus.data.last_error}</div> : null}
          </div>
        ) : (
          <div className="market-daily-empty market-daily-empty--compact">
            <SafetyCertificateOutlined />
            <div><strong>尚未查询因子状态</strong><span>输入 6 位 A 股代码开始检查。</span></div>
          </div>
        )}
      </section>
    </Card>
  );
}
