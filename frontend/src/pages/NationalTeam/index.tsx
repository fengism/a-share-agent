import { useMemo, useState } from "react";
import {
  Alert,
  Button,
  Card,
  Col,
  Input,
  Popover,
  Row,
  Segmented,
  Space,
  Statistic,
  Table,
  Tag,
  Tooltip,
  Typography,
  message,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import {
  BankOutlined,
  CalendarOutlined,
  DatabaseOutlined,
  DownOutlined,
  DownloadOutlined,
  FallOutlined,
  FileImageOutlined,
  InfoCircleOutlined,
  QuestionCircleOutlined,
  ReloadOutlined,
  RiseOutlined,
  SafetyCertificateOutlined,
  SearchOutlined,
  StarFilled,
  StarOutlined,
  ThunderboltOutlined,
  UpOutlined,
} from "@ant-design/icons";
import { useNationalTeamBacktest, useNationalTeamHoldings } from "../../api/queries";
import PreloadLink from "../../components/PreloadLink";
import SectionDataState from "../../components/SectionDataState";
import CategoryOverviewCards from "./components/CategoryOverviewCards";
import FlowHeatmapTable from "./components/FlowHeatmapTable";
import MacroFlowChart from "./components/MacroFlowChart";
import NationalTeamAnomalyBanner from "./components/NationalTeamAnomalyBanner";
import NationalTeamConcentrationCard from "./components/NationalTeamConcentrationCard";
import NationalTeamDataStatusPanel from "./components/NationalTeamDataStatusPanel";
import NationalTeamReportModal from "./components/NationalTeamReportModal";
import NationalTeamIntradayMonitor from "./components/NationalTeamIntradayMonitor";
import LazyChart from "./components/LazyChart";
import StockWorkspaceDrawer from "../../components/StockWorkspaceDrawer";
import IndexDualAxisChart from "./components/IndexDualAxisChart";
import SupportScoreRadarCard from "./components/SupportScoreRadarCard";
import MilestoneTimelineBar from "./components/MilestoneTimelineBar";
import SupportZonesCard from "./components/SupportZonesCard";
import NationalTeamPortraitPanel from "./components/NationalTeamPortraitPanel";
import { useMediaQuery } from "../../hooks/useMediaQuery";
import { useColors } from "../../styles/ui";
import { formatNumberWithSeparators } from "../../utils/format";
import { buildStockProfileUrl } from "../../utils/stockLinks";
import { useSearchParams } from "react-router-dom";
import { updateUrlSearchParam, useUrlSearchParam } from "../../hooks/useUrlSearchParam";
import type {
  NationalTeamEtfSeries,
  NationalTeamIndexSeries,
} from "../../types/stock";
import {
  CATEGORY_OPTIONS,
  CATEGORY_TAG_LABELS,
  HISTORY_WINDOWS,
  INDEX_ORDER,
  INDEX_TAG_COLORS,
  QUALITY_LABELS,
  indexOrder,
} from "./constants";
import { downloadNationalTeamCsv } from "./utils/download";
import { formatShares, formatSigned, valueColor } from "./utils/format";
import "./styles/index.css";

const { Text, Title } = Typography;

export default function NationalTeam() {
  const colors = useColors();
  const isMobile = useMediaQuery("(max-width: 640px)");
  const [, setSearchParams] = useSearchParams();
  const [daysParam, setDaysParam] = useUrlSearchParam("days", "120", {
    allowedValues: ["30", "60", "120", "240", "365"],
  });
  const days = Number(daysParam) as (typeof HISTORY_WINDOWS)[number];

  const [view, setView] = useUrlSearchParam("view", "etf", {
    allowedValues: ["etf", "portrait"],
  });

  const [tabParam, setTabParam] = useUrlSearchParam("tab", "flow", {
    allowedValues: ["flow", "intraday", "radar", "etf", "portrait", "all"],
  });

  const [assetSubView, setAssetSubView] = useState<"etf" | "portrait">(
    tabParam === "portrait" || view === "portrait" ? "portrait" : "etf"
  );

  const activeTab = useMemo(() => {
    if (tabParam === "portrait" || view === "portrait") return "etf";
    return tabParam;
  }, [tabParam, view]);

  const handleTabChange = (val: string) => {
    if (val === "portrait") {
      setView("portrait");
      setTabParam("etf");
      setAssetSubView("portrait");
    } else if (val === "etf") {
      setTabParam("etf");
    } else {
      setView("etf");
      setTabParam(val);
    }
  };

  const tabOptions = useMemo(() => {
    const list = [
      { label: "📊 资金流向", value: "flow" },
      { label: "⏱️ 盘中监控", value: "intraday" },
      { label: "🛡️ 托底雷达", value: "radar" },
      { label: "📈 标的与底仓", value: "etf" },
    ];
    if (tabParam === "all") {
      list.push({ label: "📑 全景总览", value: "all" });
    }
    return list;
  }, [tabParam]);

  const [category] = useUrlSearchParam("category", "all", {
    allowedValues: ["all", "core_broad", "a500", "growth", "dividend"],
  });

  const [rotationWindowParam, setRotationWindowParam] = useUrlSearchParam("rotation", "20", {
    allowedValues: ["20", "5", "1"],
  });
  const rotationWindow = Number(rotationWindowParam) as 20 | 5 | 1;

  const [selectedFilterIndex, setSelectedFilterIndex] = useUrlSearchParam("index", "ALL");
  type TableSortPreset = "default" | "flow1d" | "flow5d" | "amount" | "shares" | "abnormal";
  const [tableSortPreset, setTableSortPreset] = useState<TableSortPreset>("default");
  // 搜索词逐步输入，用 replace 避免每敲一个字就压一条历史记录（返回键要按十几次）。
  const [searchKeyword, setSearchKeyword] = useUrlSearchParam("q", "", { replace: true });
  const [showPartialDetails, setShowPartialDetails] = useState<boolean>(false);
  const [chartsCollapsed, setChartsCollapsed] = useState<boolean>(false);
  const [reportModalOpen, setReportModalOpen] = useState(false);
  const [previewStock, setPreviewStock] = useState<{ code: string; name: string } | null>(null);
  const [starredCodes, setStarredCodes] = useState<string[]>(() => {
    try {
      return JSON.parse(localStorage.getItem("national-team-starred-etfs") || "[]");
    } catch {
      return [];
    }
  });

  const toggleStar = (code: string) => {
    setStarredCodes((prev) => {
      const next = prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code];
      try {
        localStorage.setItem("national-team-starred-etfs", JSON.stringify(next));
      } catch {
        // ignore
      }
      return next;
    });
  };

  const holdingsQuery = useNationalTeamHoldings(days);
  const data = holdingsQuery?.data;
  const isLoading = holdingsQuery?.isLoading ?? false;
  const isFetching = holdingsQuery?.isFetching ?? false;
  const error = holdingsQuery?.error ?? null;
  const refetch = holdingsQuery?.refetch ?? (() => {});
  const backtestResult = useNationalTeamBacktest(365, data?.fetched_at);
  const backtest = backtestResult?.data;

  const indices = useMemo(() => [...(data?.indices ?? [])].sort(
    (a, b) => indexOrder(a.index_name) - indexOrder(b.index_name),
  ), [data?.indices]);

  const filteredIndices = useMemo(() => {
    if (category === "all") return indices;
    return indices.filter((item) => (item.category ?? "core_broad") === category);
  }, [category, indices]);

  const etfs = useMemo(() => data?.etfs ?? [], [data?.etfs]);
  const hasData = indices.length > 0 || etfs.length > 0;
  const abnormalEtfs = useMemo(() => etfs.filter((item) => item.is_abnormal_volume), [etfs]);

  const categoryEtfs = useMemo(() => {
    if (category === "all") return etfs;
    return etfs.filter((item) => (item.category ?? "core_broad") === category);
  }, [category, etfs]);

  const rotation = useMemo(() => {
    const getVal = (item: NationalTeamIndexSeries) => {
      if (rotationWindow === 1) return item.latest_change_1d_100m;
      if (rotationWindow === 5) return item.change_5d_100m;
      return item.change_20d_100m;
    };
    const targetIndices = category === "all" ? indices : indices.filter((item) => (item.category ?? "core_broad") === category);
    return [...targetIndices].sort(
      (a, b) => (getVal(b) ?? Number.NEGATIVE_INFINITY) - (getVal(a) ?? Number.NEGATIVE_INFINITY),
    );
  }, [category, indices, rotationWindow]);

  const maxAbsRotation = useMemo(() => {
    const getVal = (item: NationalTeamIndexSeries) => {
      if (rotationWindow === 1) return item.latest_change_1d_100m;
      if (rotationWindow === 5) return item.change_5d_100m;
      return item.change_20d_100m;
    };
    const vals = rotation.map((item) => Math.abs(getVal(item) ?? 0));
    return Math.max(...vals, 0.01);
  }, [rotation, rotationWindow]);

  const filteredEtfs = useMemo(() => {
    let result = categoryEtfs;
    if (selectedFilterIndex === "STARRED") {
      result = result.filter((item) => starredCodes.includes(item.code));
    } else if (selectedFilterIndex !== "ALL") {
      result = result.filter((item) => item.index_name === selectedFilterIndex);
    }
    if (searchKeyword.trim()) {
      const kw = searchKeyword.trim().toLowerCase();
      result = result.filter(
        (item) =>
          item.code.toLowerCase().includes(kw) ||
          item.name.toLowerCase().includes(kw) ||
          item.fund_manager.toLowerCase().includes(kw) ||
          item.index_name.toLowerCase().includes(kw),
      );
    }
    if (tableSortPreset === "flow1d") {
      return [...result].sort((a, b) => (b.latest_estimated_net_flow_100m ?? -Infinity) - (a.latest_estimated_net_flow_100m ?? -Infinity));
    }
    if (tableSortPreset === "flow5d") {
      return [...result].sort((a, b) => (b.change_5d_100m ?? -Infinity) - (a.change_5d_100m ?? -Infinity));
    }
    if (tableSortPreset === "amount") {
      return [...result].sort((a, b) => (b.latest_amount_100m ?? -Infinity) - (a.latest_amount_100m ?? -Infinity));
    }
    if (tableSortPreset === "shares") {
      return [...result].sort((a, b) => (b.latest_shares_100m ?? -Infinity) - (a.latest_shares_100m ?? -Infinity));
    }
    if (tableSortPreset === "abnormal") {
      return [...result].sort((a, b) => {
        const abDiff = (b.is_abnormal_volume ? 1 : 0) - (a.is_abnormal_volume ? 1 : 0);
        if (abDiff !== 0) return abDiff;
        return (b.volume_ratio ?? 0) - (a.volume_ratio ?? 0);
      });
    }
    return result;
  }, [categoryEtfs, searchKeyword, selectedFilterIndex, starredCodes, tableSortPreset]);

  const filterOptions = useMemo(() => {
    const baseOptions = [
      { label: `全部 (${categoryEtfs.length})`, value: "ALL" },
      ...INDEX_ORDER.filter((name) => categoryEtfs.some((e) => e.index_name === name)).map((name) => ({
        label: `${name} (${categoryEtfs.filter((e) => e.index_name === name).length})`,
        value: name,
      })),
    ];
    if (starredCodes.length > 0) {
      const starredCount = categoryEtfs.filter((e) => starredCodes.includes(e.code)).length;
      return [
        { label: `⭐ 我的自选 (${starredCount})`, value: "STARRED" },
        ...baseOptions,
      ];
    }
    return baseOptions;
  }, [categoryEtfs, starredCodes]);

  const handleCategoryChange = (newCat: string) => {
    setSearchParams((current) => {
      const next = updateUrlSearchParam(current, "category", newCat, "all");
      return updateUrlSearchParam(next, "index", "ALL", "ALL");
    });
  };

  const columns: ColumnsType<NationalTeamEtfSeries> = useMemo(() => [
    {
      title: "自选",
      key: "star",
      width: 46,
      align: "center",
      fixed: isMobile ? undefined : "left",
      render: (_, item) => {
        const isStarred = starredCodes.includes(item.code);
        return (
          <Button
            type="text"
            size="small"
            className={`national-team-star-btn${isStarred ? " is-starred" : ""}`}
            icon={isStarred ? <StarFilled /> : <StarOutlined />}
            onClick={() => toggleStar(item.code)}
            title={isStarred ? "取消自选关注" : "添加自选关注"}
            aria-label={isStarred ? `取消自选 ${item.code}` : `加入自选 ${item.code}`}
          />
        );
      },
    },
    {
      title: "宽基",
      dataIndex: "index_name",
      key: "index_name",
      width: isMobile ? 85 : 120,
      fixed: isMobile ? undefined : "left",
      render: (name: string, item: NationalTeamEtfSeries) => {
        const catMeta = CATEGORY_TAG_LABELS[item.category ?? "core_broad"];
        return (
          <div className="national-team-index-col">
            <Tag color={INDEX_TAG_COLORS[name] || "default"} className="national-team-index-tag">
              {name}
            </Tag>
            {catMeta && (
              <Tag color={catMeta.color} className="national-team-cat-tag">
                {catMeta.label}
              </Tag>
            )}
          </div>
        );
      },
    },
    {
      title: "ETF",
      key: "etf",
      width: isMobile ? 130 : 210,
      fixed: isMobile ? undefined : "left",
      render: (_, item) => (
        <div className="national-team-etf-name">
          <div className="national-team-etf-code-row">
            <PreloadLink
              to={buildStockProfileUrl(item.code)}
              className="national-team-code national-team-code-link financial-num"
              title={`查看 ${item.name}（${item.code}）行情`}
            >
              {item.code}
            </PreloadLink>
            <Tag className="national-team-exchange-tag">
              {item.exchange === "SH" ? "沪" : "深"}
            </Tag>
          </div>
          <Text type="secondary" className="national-team-etf-fullname" ellipsis title={item.name}>
            {item.name}
          </Text>
        </div>
      ),
    },
    {
      title: "最新份额",
      dataIndex: "latest_shares_100m",
      key: "latest_shares_100m",
      width: isMobile ? 95 : 125,
      align: "right",
      sorter: (a, b) => (a.latest_shares_100m ?? 0) - (b.latest_shares_100m ?? 0),
      render: (value) => (
        <span className="national-team-shares-val">{formatShares(value)}</span>
      ),
    },
    ...([1, 5, 20] as const).map((window): ColumnsType<NationalTeamEtfSeries>[number] => {
      const key = window === 1 ? "latest_change_1d_100m" : (`change_${window}d_100m` as const);
      return {
        title: `${window} 日变化`,
        key,
        width: isMobile ? 85 : 115,
        align: "right",
        sorter: (a, b) => (a[key] ?? 0) - (b[key] ?? 0),
        render: (_, item) => {
          const value = item[key];
          const color = valueColor(value, colors.up, colors.down, colors.textSecondary);
          const bg = (value ?? 0) > 0 ? colors.upBg : (value ?? 0) < 0 ? colors.downBg : "transparent";
          return (
            <span className="national-team-delta-pill" style={{ color, background: bg }}>
              {formatSigned(value)}
            </span>
          );
        },
      };
    }),
    {
      title: "1日估算净申购",
      key: "estimated_net_flow_1d",
      width: isMobile ? 110 : 130,
      align: "right",
      sorter: (a, b) =>
        (a.latest_estimated_net_flow_100m ?? 0) - (b.latest_estimated_net_flow_100m ?? 0),
      render: (_, item) => {
        const flow = item.latest_estimated_net_flow_100m;
        const color = valueColor(flow, colors.up, colors.down, colors.textSecondary);
        const bg = (flow ?? 0) > 0 ? colors.upBg : (flow ?? 0) < 0 ? colors.downBg : "transparent";
        return (
          <span className="national-team-delta-pill" style={{ color, background: bg }}>
            {formatSigned(flow, "亿元")}
          </span>
        );
      },
    },
    {
      title: "成交额",
      dataIndex: "latest_amount_100m",
      key: "latest_amount_100m",
      width: isMobile ? 85 : 105,
      align: "right",
      sorter: (a, b) => (a.latest_amount_100m ?? 0) - (b.latest_amount_100m ?? 0),
      render: (value: number | null | undefined) => (
        <span className="financial-num u-text-xs">
          {value != null ? `${value.toFixed(1)}亿` : "-"}
        </span>
      ),
    },
    {
      title: "量比",
      dataIndex: "volume_ratio",
      key: "volume_ratio",
      width: isMobile ? 85 : 100,
      align: "right",
      sorter: (a, b) => (a.volume_ratio ?? 0) - (b.volume_ratio ?? 0),
      render: (value: number | null | undefined, item: NationalTeamEtfSeries) => {
        if (value == null) return <span className="u-text-muted">-</span>;
        if (item.is_abnormal_volume) {
          return (
            <Tooltip title={`5日均量放大至 ${value} 倍，触发显著异动放量`}>
              <Tag color="orange" className="national-team-volume-ratio-tag">
                放量 {value}x
              </Tag>
            </Tooltip>
          );
        }
        return (
          <span className="financial-num u-text-xs">
            {value.toFixed(2)}x
          </span>
        );
      },
    },
    {
      title: "基金公司",
      dataIndex: "fund_manager",
      key: "fund_manager",
      width: isMobile ? 95 : 110,
      render: (val: string) => <Text className="national-team-subtle-text">{val || "-"}</Text>,
    },
    {
      title: "最新日期",
      dataIndex: "latest_date",
      key: "latest_date",
      width: isMobile ? 90 : 100,
      render: (value, item) => {
        const point = item.points?.find((entry) => entry.date === value);
        const source = point?.source === "sse_history" ? "上交所历史份额"
          : point?.source === "szse_history" ? "深交所历史份额" : point?.source || "未知";
        return (
          <Tooltip title={`来源：${source}；业务日期：${value || "未知"}；抓取时间：${point?.fetched_at || "未知"}；${point?.verification_status === "verified" ? "日期已确认" : "待确认"}`}>
            <span className="national-team-date">{value || "-"}</span>
          </Tooltip>
        );
      },
    },
    {
      title: "操作",
      key: "actions",
      width: isMobile ? 65 : 80,
      fixed: isMobile ? undefined : "right",
      align: "center",
      render: (_, item) => (
        <Button
          type="link"
          size="small"
          icon={<ThunderboltOutlined />}
          className="national-team-chart-btn"
          onClick={() => setPreviewStock({ code: item.code, name: item.name })}
          title={`快速预览 ${item.name} 分时/日K行情`}
        >
          {isMobile ? "看盘" : "分时K线"}
        </Button>
      ),
    },
  ], [colors, isMobile, starredCodes]);

  return (
    <section className="national-team-page" aria-labelledby="national-team-title">
      {/* 头部控制栏：精简流线型高光控制栏 */}
      <header className="national-team-hero">
        <div className="national-team-hero__brand">
          <div className="national-team-hero__icon">
            <BankOutlined />
          </div>
          <div className="national-team-hero__title-wrap">
            <div className="national-team-hero__title-row">
              <Title id="national-team-title" level={1} className="national-team-hero__title">国家队</Title>
              <Tag color="blue" className="national-team-hero__tag">宽基 ETF 监测</Tag>
              <span className="national-team-hero__as-of">
                <CalendarOutlined className="national-team-stat-icon" />
                截至 <strong>{data?.as_of_date || "-"}</strong>
              </span>
            </div>
            <div className="national-team-hero__meta">
              <span className="national-team-hero__meta-item">
                <DatabaseOutlined className="national-team-stat-icon" />
                数据源：{data?.source || "上交所 / 深交所 / 东方财富"}
              </span>
              <span className="national-team-hero__meta-dot">·</span>
              <span className="national-team-hero__meta-item">
                覆盖 {data?.total_etf_count ?? etfs.length ?? 22} 只核心宽基 ETF
              </span>
            </div>
          </div>
        </div>

        <div className="national-team-hero__controls">
          <Segmented
            aria-label="历史区间"
            value={days}
            options={HISTORY_WINDOWS.map((value) => ({ label: `${value} 天`, value }))}
            onChange={(value) => setDaysParam(String(value))}
            className="national-team-segmented"
          />
          <Button
            icon={<FileImageOutlined />}
            onClick={() => setReportModalOpen(true)}
            data-testid="national-team-report-btn"
          >
            资金简报
          </Button>
          <Button
            type="primary"
            ghost
            icon={<ReloadOutlined spin={isFetching} />}
            loading={isFetching}
            onClick={() => refetch()}
            className="national-team-refresh-btn"
          >
            刷新
          </Button>
        </div>
      </header>

      {/* 警示与说明区域：轻量通透的提示条 */}
      <div className="national-team-alerts">
        <Alert
          className="national-team-disclaimer"
          type="info"
          showIcon
          icon={<InfoCircleOutlined />}
          title="代理口径说明"
          description={
            <div className="national-team-disclaimer__desc">
              <span>{data?.disclaimer || "ETF 份额变化仅作为资金行为代理指标，不等于中央汇金真实持仓或实际交易。"}</span>
              <Popover
                title="国家队 ETF 估算方法与口径规范"
                content={
                  <div className="national-team-disclaimer__popover">
                    <div className="national-team-disclaimer__popover-row">
                      <strong>估算方法：</strong>
                      <div className="u-text-secondary">
                        {data?.methodology || "ETF 当日份额变化 × ETF 当日收盘价，逐只计算后按宽基汇总。"}
                      </div>
                    </div>
                    <div className="national-team-disclaimer__popover-note">
                      <strong>特别提示：</strong>
                      <div>
                        ETF 份额变动为全市场一级市场申购赎回代理汇总结果，包含各类公募、私募、保险及散户资金；成交额为二级市场交易额，严禁将成交额误称为“真实资金净流入”。
                      </div>
                    </div>
                  </div>
                }
              >
                <Button type="link" size="small" className="national-team-disclaimer__btn">
                  查看口径规范与说明 <QuestionCircleOutlined className="u-text-xs" />
                </Button>
              </Popover>
            </div>
          }
        />

        {data?.partial && (
          <Alert
            className="national-team-partial-alert"
            type="warning"
            showIcon
            title={
              <div className="national-team-partial-alert__title">
                <span>{data.refreshing ? "数据不完整 · 后台更新中" : "数据不完整"}</span>
                <Button
                  type="link"
                  size="small"
                  onClick={() => setShowPartialDetails((prev) => !prev)}
                  className="national-team-partial-alert__btn"
                >
                  {showPartialDetails ? (
                    <>收起明细 <UpOutlined className="national-team-quick-nav__toggle-icon" /></>
                  ) : (
                    <>查看明细 <DownOutlined className="national-team-quick-nav__toggle-icon" /></>
                  )}
                </Button>
              </div>
            }
            description={
              showPartialDetails ? (
                <div className="national-team-partial-alert__desc">
                  {[
                    data.stale ? `份额截至 ${data.as_of_date || "未知"}，预期交易日 ${data.expected_date || "待确认"}。` : "",
                    data.calendar_degraded ? "交易日历暂不可用，新鲜度与区间完整性待确认。" : "",
                    data.missing_share_etfs?.length ? `份额缺失或区间不完整：${data.missing_share_etfs.join("、")}。` : "",
                    data.missing_price_etfs?.length ? `ETF 行情缺失：${data.missing_price_etfs.join("、")}。` : "",
                    data.missing_indices?.length ? `指数行情缺失：${data.missing_indices.map((key) => data.indices?.find((item) => item.index_key === key)?.index_name || key).join("、")}。` : "",
                    data.observations?.length ? "无业务日期的当前份额仅作未确认观察，不计入历史与资金估算。" : "",
                    "汇总仅覆盖截至日有份额数据的 ETF；变化按相同标的、相同交易日比较，无法计算时显示“-”，不代表零变化。请谨慎解读。",
                  ].join("")}
                </div>
              ) : (
                <div>
                  {[
                    data.stale ? `份额截至 ${data.as_of_date || "未知"}，预期交易日 ${data.expected_date || "待确认"}。` : "",
                    data.calendar_degraded ? "交易日历暂不可用。" : "",
                    data.missing_share_etfs?.length ? `${data.missing_share_etfs.length} 只 ETF 份额待同步。` : "",
                    data.missing_price_etfs?.length ? `${data.missing_price_etfs.length} 只 ETF 行情待同步。` : "",
                    data.missing_indices?.length ? `${data.missing_indices.length} 个指数行情待同步。` : "",
                    data.observations?.length ? "无业务日期的当前份额仅作未确认观察。" : "",
                  ].filter(Boolean).join(" ") || "部分标的行情或份额正在后台回填中，暂不影响整体观察。"}
                </div>
              )
            }
          />
        )}

        {abnormalEtfs.length > 0 && (
          <Alert
            className="national-team-sweep-alert"
            type="error"
            showIcon
            title={
              <div className="national-team-sweep-alert__title">
                <div className="national-team-sweep-alert__title-main">
                  <span className="u-text-semibold">盘中主力放量异动监测</span>
                  <Tag color="orange" className="national-team-volume-ratio-tag">
                    {abnormalEtfs.length} 只 ETF 显著放量
                  </Tag>
                </div>
                <span className="national-team-sweep-alert__subtitle">
                  （5日量比 ≥ 1.8x 且最新成交额 ≥ 5亿元，疑似主力集中扫货）
                </span>
              </div>
            }
            description={
              <div className="national-team-sweep-alert__list">
                {abnormalEtfs.map((item) => (
                  <Tag
                    key={item.code}
                    color="orange"
                    className="national-team-sweep-alert__tag"
                    onClick={() => {
                      setSelectedFilterIndex(item.index_name);
                      setSearchKeyword(item.code);
                    }}
                    title={`点击定位筛选 ${item.name}`}
                  >
                    <span className="national-team-sweep-alert__item-name">
                      <strong>{item.name}</strong>
                      <span className="national-team-sweep-alert__item-code">({item.code})</span>
                    </span>
                    <span className="national-team-sweep-alert__item-metrics">
                      成交额 {item.latest_amount_100m?.toFixed(1)}亿 · 量比 {item.volume_ratio}x
                    </span>
                  </Tag>
                ))}
              </div>
            }
          />
        )}

        {error && hasData && (
          <Alert
            className="national-team-partial-alert"
            type="warning"
            showIcon
            title="数据刷新失败，当前展示上次成功结果"
            description={error instanceof Error ? error.message : "请稍后重试刷新。"}
          />
        )}
      </div>

      <SectionDataState
        isLoading={isLoading && !hasData}
        error={hasData ? undefined : error}
        onRetry={() => refetch()}
        isEmpty={!isLoading && !error && !hasData}
        emptyText="暂无国家队 ETF 代理监测数据"
        errorTitle="国家队数据加载失败"
        minHeight={420}
        skeletonRows={8}
      >
        {/* 多维子 Tab 导航切换栏 */}
        <div className="national-team-view-switcher national-team-tab-bar u-mb-12">
          <Segmented
            size="middle"
            value={activeTab}
            options={tabOptions}
            onChange={(val) => handleTabChange(String(val))}
            className="national-team-segmented"
            data-testid="national-team-view-switcher"
          />
        </div>

        {activeTab === "etf" && (
          <div className="national-team-asset-subtabs u-mb-12">
            <Segmented
              size="small"
              value={assetSubView}
              options={[
                { label: "📊 宽基 ETF 监测与走势", value: "etf" },
                { label: "🏛️ 战略底仓画像", value: "portrait" },
              ]}
              onChange={(val) => {
                const next = String(val) as "etf" | "portrait";
                setAssetSubView(next);
                setView(next === "portrait" ? "portrait" : "etf");
              }}
              className="national-team-segmented"
              data-testid="national-team-asset-sub-switcher"
            />
          </div>
        )}

        {(activeTab === "etf" && assetSubView === "portrait") ? (
          <NationalTeamPortraitPanel portrait={data?.portrait} />
        ) : (
          <>
            {/* 数据质量与状态监控控制台 */}
            {(activeTab === "flow" || activeTab === "all") && (
              <NationalTeamDataStatusPanel data={data} />
            )}

            {/* 异动预警横幅：资金极端异动与托底背离预警 */}
            {(activeTab === "flow" || activeTab === "radar" || activeTab === "all") && (
              <NationalTeamAnomalyBanner data={data} />
            )}

            {/* 盘中分钟观测与放量信号对比 (在 intraday 子 Tab 下展示) */}
            {activeTab === "intraday" && (
              <div className="u-mb-12">
                <NationalTeamIntradayMonitor
                  intraday={data?.intraday}
                  asOfDate={data?.as_of_date}
                  onSelectStock={(stock) => setPreviewStock(stock)}
                />
              </div>
            )}

            {/* 托底雷达卡 (在 radar 或 all 下展示) */}
            {(activeTab === "radar" || activeTab === "all") && data?.support_score && (
              <div className="u-mb-12">
                <SupportScoreRadarCard
                  supportScore={data.support_score}
                  history={data.support_score_history}
                  backtest={backtest}
                />
              </div>
            )}

            {/* 托底点位分布与政策标尺 (在 radar 或 all 下展示) */}
            {(activeTab === "radar" || activeTab === "all") && (
              <>
                {data?.support_zones && data.support_zones.length > 0 && (
                  <div className="u-mb-12">
                    <SupportZonesCard supportZones={data.support_zones} />
                  </div>
                )}
                {data?.milestones && data.milestones.length > 0 && (
                  <div className="u-mb-12">
                    <MilestoneTimelineBar milestones={data.milestones} />
                  </div>
                )}
              </>
            )}

            {/* KPI 统计控制台：融合方案附录 A 核心指标卡 (在 flow 或 all 下展示) */}
            {(activeTab === "flow" || activeTab === "all") && (
              <div className="national-team-summary-section">
                <Row gutter={[10, 10]} className="national-team-summary">
                  {/* 核心资产总额卡片 */}
                  <Col xs={24} sm={12} lg={4}>
                    <Card className="national-team-summary__card national-team-summary__card--total">
                      <Statistic
                        title="ETF 总份额"
                        value={formatShares(data?.summary?.total_shares_100m)}
                      />
                      <div className="national-team-summary__hint">
                        覆盖 {data?.covered_etf_count ?? 0}/{data?.total_etf_count ?? 22} 只宽基 ETF · {QUALITY_LABELS[data?.summary?.quality ?? "insufficient"]} · 截至 {data?.as_of_date || "-"}
                      </div>
                    </Card>
                  </Col>

                  {/* 样本 ETF 总成交额 (附录 A 核心指标) */}
                  <Col xs={12} sm={6} lg={4}>
                    <Card
                      className="national-team-summary__card"
                      style={{
                        borderTop: (data?.summary?.total_amount_1d_100m ?? 0) > 0 ? `2px solid ${colors.primary}` : undefined,
                      }}
                    >
                      <Statistic
                        title="样本 ETF 总成交额"
                        value={data?.summary?.total_amount_1d_100m != null ? `${formatNumberWithSeparators(data.summary.total_amount_1d_100m, 1)} 亿元` : "-"}
                        styles={{ content: { color: colors.primary, fontFamily: "var(--c-font-mono)" } }}
                      />
                      <div className="national-team-summary__hint">二级市场成交额合计</div>
                    </Card>
                  </Col>

                  {/* 1 日估算净申购 */}
                  <Col xs={12} sm={6} lg={4}>
                    <Card
                      className="national-team-summary__card national-team-summary__card--flow"
                      style={{
                        borderTop: (data?.summary?.estimated_net_flow_1d_100m ?? 0) !== 0
                          ? `2px solid ${valueColor(data?.summary?.estimated_net_flow_1d_100m, colors.up, colors.down, colors.border)}`
                          : undefined,
                      }}
                    >
                      <Statistic
                        title="1 日估算净申购"
                        value={formatSigned(data?.summary?.estimated_net_flow_1d_100m, "亿元")}
                        prefix={(data?.summary?.estimated_net_flow_1d_100m ?? 0) > 0 ? <RiseOutlined /> : (data?.summary?.estimated_net_flow_1d_100m ?? 0) < 0 ? <FallOutlined /> : undefined}
                        styles={{ content: { color: valueColor(data?.summary?.estimated_net_flow_1d_100m, colors.up, colors.down, colors.textPrimary) } }}
                      />
                      <div className="national-team-summary__hint">较上一交易日资金</div>
                    </Card>
                  </Col>

                  {/* 区间累计净申购 (附录 A 核心指标) */}
                  <Col xs={12} sm={6} lg={4}>
                    <Card
                      className="national-team-summary__card national-team-summary__card--flow"
                      style={{
                        borderTop: (data?.summary?.cumulative_net_flow_100m ?? 0) !== 0
                          ? `2px solid ${valueColor(data?.summary?.cumulative_net_flow_100m, colors.up, colors.down, colors.border)}`
                          : undefined,
                      }}
                    >
                      <Statistic
                        title="区间累计净申购"
                        value={formatSigned(data?.summary?.cumulative_net_flow_100m, "亿元")}
                        prefix={(data?.summary?.cumulative_net_flow_100m ?? 0) > 0 ? <RiseOutlined /> : (data?.summary?.cumulative_net_flow_100m ?? 0) < 0 ? <FallOutlined /> : undefined}
                        styles={{ content: { color: valueColor(data?.summary?.cumulative_net_flow_100m, colors.up, colors.down, colors.textPrimary) } }}
                      />
                      <div className="national-team-summary__hint">
                        近 {days} 日累计
                        {data?.summary?.ytd_net_flow_100m != null && (
                          <span> · 年初至今 {formatSigned(data.summary.ytd_net_flow_100m, "亿")}</span>
                        )}
                      </div>
                    </Card>
                  </Col>

                  {/* 1 日份额变化 */}
                  <Col xs={12} sm={6} lg={4}>
                    <Card
                      className="national-team-summary__card"
                      style={{
                        borderTop: (data?.summary?.change_1d_100m ?? 0) !== 0
                          ? `2px solid ${valueColor(data?.summary?.change_1d_100m, colors.up, colors.down, colors.border)}`
                          : undefined,
                      }}
                    >
                      <Statistic
                        title="1 日份额变化"
                        value={formatSigned(data?.summary?.change_1d_100m)}
                        prefix={(data?.summary?.change_1d_100m ?? 0) > 0 ? <RiseOutlined /> : (data?.summary?.change_1d_100m ?? 0) < 0 ? <FallOutlined /> : undefined}
                        styles={{ content: { color: valueColor(data?.summary?.change_1d_100m, colors.up, colors.down, colors.textPrimary) } }}
                      />
                      <div className="national-team-summary__hint">较上一交易日</div>
                    </Card>
                  </Col>

                  {/* 5 日 / 20 日估算净申购 */}
                  <Col xs={12} sm={6} lg={4}>
                    <Card
                      className="national-team-summary__card national-team-summary__card--flow"
                      style={{
                        borderTop: (data?.summary?.estimated_net_flow_5d_100m ?? 0) !== 0
                          ? `2px solid ${valueColor(data?.summary?.estimated_net_flow_5d_100m, colors.up, colors.down, colors.border)}`
                          : undefined,
                      }}
                    >
                      <Statistic
                        title="5 日估算净申购"
                        value={formatSigned(data?.summary?.estimated_net_flow_5d_100m, "亿元")}
                        prefix={(data?.summary?.estimated_net_flow_5d_100m ?? 0) > 0 ? <RiseOutlined /> : (data?.summary?.estimated_net_flow_5d_100m ?? 0) < 0 ? <FallOutlined /> : undefined}
                        styles={{ content: { color: valueColor(data?.summary?.estimated_net_flow_5d_100m, colors.up, colors.down, colors.textPrimary) } }}
                      />
                      <div className="national-team-summary__hint">
                        近 5 日累计 · 20日 {formatSigned(data?.summary?.estimated_net_flow_20d_100m, "亿元")}
                      </div>
                    </Card>
                  </Col>

                  {/* 保留 5日/20日份额变化以便特定视图/断言读取 */}
                  <Col xs={0} sm={0} lg={0} className="u-hidden">
                    <Statistic title="5 日份额变化" value={formatSigned(data?.summary?.change_5d_100m)} />
                    <Statistic title="20 日份额变化" value={formatSigned(data?.summary?.change_20d_100m)} />
                    <Statistic title="20 日估算净申购" value={formatSigned(data?.summary?.estimated_net_flow_20d_100m, "亿元")} />
                  </Col>
                </Row>
              </div>
            )}

            {/* 宏观双轴走势大图 & 热力矩阵表 (在 flow 或 all 下展示) */}
            {(activeTab === "flow" || activeTab === "all") && data?.daily_flows && data.daily_flows.length > 0 && (
              <>
                <div className="national-team-daily-flow-section u-mb-12">
                  <MacroFlowChart dailyFlows={data.daily_flows} milestones={data?.milestones} />
                </div>
                <div className="u-mb-12">
                  <FlowHeatmapTable dailyFlows={data.daily_flows} asOfDate={data?.as_of_date} />
                </div>
                <div className="u-mb-12">
                  <NationalTeamConcentrationCard
                    etfs={data?.etfs}
                    dailyFlows={data?.daily_flows}
                    asOfDate={data?.as_of_date}
                  />
                </div>
              </>
            )}

            {/* 快速直达锚点与折叠控制条 (在 etf 下展示) */}
            {activeTab === "etf" && (
              <div className="national-team-quick-nav">
                <Space size={6} wrap align="center">
                  <span className="national-team-quick-nav__label">快速直达：</span>
                  <Button
                    size="small"
                    onClick={() => {
                      document.getElementById("national-team-table-section")?.scrollIntoView({ behavior: "smooth" });
                    }}
                  >
                    📋 ETF 监测明细表 ({filteredEtfs.length})
                  </Button>
                  <Button
                    size="small"
                    onClick={() => {
                      setChartsCollapsed(false);
                      setTimeout(() => {
                        document.getElementById("national-team-charts-section")?.scrollIntoView({ behavior: "smooth" });
                      }, 50);
                    }}
                  >
                    📊 宽基双轴走势 ({filteredIndices.length})
                  </Button>
                  <Button
                    size="small"
                    onClick={() => {
                      document.getElementById("national-team-rotation-section")?.scrollIntoView({ behavior: "smooth" });
                    }}
                  >
                    🔄 跨宽基结构轮动
                  </Button>
                </Space>
                <Button
                  size="small"
                  type="link"
                  onClick={() => setChartsCollapsed((prev) => !prev)}
                  className="national-team-quick-nav__toggle"
                >
                  {chartsCollapsed ? (
                    <>展开双轴走势图 <DownOutlined className="national-team-quick-nav__toggle-icon" /></>
                  ) : (
                    <>收起走势图直达大表 <UpOutlined className="national-team-quick-nav__toggle-icon" /></>
                  )}
                </Button>
              </div>
            )}

            {/* 结构轮动卡片 (在 etf 或 all 下展示) */}
            {(activeTab === "etf" || activeTab === "all") && (
              <div id="national-team-rotation-section" className="u-mb-12">
                <Card
                  className="national-team-rotation"
                  title={
                    <div className="national-team-rotation__header-left">
                      <span className="national-team-rotation__title-text">{`结构轮动 · ${rotationWindow} 日份额变化`}</span>
                      <span className="national-team-rotation__subtitle">跨宽基资金动向相对强弱</span>
                    </div>
                  }
                  extra={
                    <Segmented
                      size="small"
                      value={rotationWindow}
                      options={[
                        { label: "20 日", value: 20 },
                        { label: "5 日", value: 5 },
                        { label: "1 日", value: 1 },
                      ]}
                      onChange={(val) => setRotationWindowParam(String(val))}
                      className="national-team-segmented"
                    />
                  }
                >
                  <div className="national-team-rotation__list">
                    {rotation.map((item, index) => {
                      const currentVal = rotationWindow === 1
                        ? item.latest_change_1d_100m
                        : rotationWindow === 5
                        ? item.change_5d_100m
                        : item.change_20d_100m;
                      const hasValue = currentVal != null;
                      const barWidth = Math.max(6, Math.min(100, Math.round((Math.abs(currentVal ?? 0) / maxAbsRotation) * 100)));
                      const isPositive = (currentVal ?? 0) >= 0;
                      const rankClass = hasValue && index < 3 ? `national-team-rotation__rank--${index + 1}` : "";

                      return (
                        <div className="national-team-rotation__item" key={item.index_key}>
                          <span className={`national-team-rotation__rank ${rankClass}`}>{hasValue ? index + 1 : "-"}</span>
                          <div className="national-team-rotation__info">
                            <span className="national-team-rotation__name">{item.index_name}</span>
                            <span className="national-team-rotation__code">{item.index_code}</span>
                          </div>
                          <div className="national-team-rotation__bar" aria-hidden="true">
                            {hasValue && currentVal !== 0 && <span
                              style={{
                                width: `${barWidth}%`,
                                background: isPositive
                                  ? `linear-gradient(90deg, ${colors.up}88, ${colors.up})`
                                  : `linear-gradient(90deg, ${colors.down}88, ${colors.down})`,
                              }}
                            />}
                          </div>
                          <Text className="national-team-rotation__val" style={{ color: valueColor(currentVal, colors.up, colors.down, colors.textSecondary) }}>
                            {hasValue ? formatSigned(currentVal) : "数据不足"}
                          </Text>
                        </div>
                      );
                    })}
                  </div>
                  <div className="national-team-rotation__footer">
                    <Text type="secondary" className="national-team-rotation__note">
                      排名反映纳入 ETF 的份额净变化，不代表真实持仓排名；数据不足时不参与排名。
                    </Text>
                  </div>
                </Card>
              </div>
            )}

            {/* 宽基图表矩阵：整洁紧凑的网格卡片 (在 etf 或 all 下展示) */}
            {(activeTab === "etf" || activeTab === "all") && (
              <div id="national-team-charts-section" className="u-mb-16">
                <div className="national-team-section-heading">
                  <div className="national-team-section-heading__left">
                    <Title level={2} className="national-team-section-heading__title">宽基份额与指数走势</Title>
                    <Text type="secondary" className="national-team-section-heading__desc">
                      左轴为纳入 ETF 合计份额，右轴为指数收盘点位
                    </Text>
                  </div>
                  <div className="national-team-section-heading__controls">
                    <Segmented
                      aria-label="战术板块分类"
                      value={category}
                      options={CATEGORY_OPTIONS}
                      onChange={(val) => handleCategoryChange(String(val))}
                      className="national-team-segmented"
                    />
                    <Tag color="blue" className="national-team-section-heading__tag">双轴 · {days} 天</Tag>
                    {activeTab === "etf" && (
                      <Button
                        size="small"
                        type="link"
                        onClick={() => setChartsCollapsed((prev) => !prev)}
                        className="national-team-chart-btn"
                      >
                        {chartsCollapsed ? "展开" : "收起"}
                      </Button>
                    )}
                  </div>
                </div>

                {!chartsCollapsed || activeTab === "all" ? (
                  <div className="national-team-chart-grid">
                    {filteredIndices.map((item) => (
                      <LazyChart height={340} placeholderClassName="national-team-index-card-placeholder" key={item.index_key}>
                        <IndexDualAxisChart item={item} days={days} />
                      </LazyChart>
                    ))}
                  </div>
                ) : (
                  <Card size="small" className="national-team-empty-card">
                    <Space size={10}>
                      <Text type="secondary">已收起 {filteredIndices.length} 张宽基双轴图表，点击快速展开</Text>
                      <Button size="small" onClick={() => setChartsCollapsed(false)}>展开图表</Button>
                    </Space>
                  </Card>
                )}
              </div>
            )}

            {/* 四大板块概览卡片 (在 etf 或 all 下展示) */}
            {(activeTab === "etf" || activeTab === "all") && (
              <CategoryOverviewCards
                etfs={data?.etfs}
                latestDailyFlow={data?.daily_flows?.[data.daily_flows.length - 1]}
              />
            )}

            {/* ETF 监测明细表格 (在 etf 或 all 下展示) */}
            {(activeTab === "etf" || activeTab === "all") && (
              <div id="national-team-table-section" className="national-team-table-wrapper">
                <div className="national-team-section-heading national-team-section-heading--table">
                  <div className="national-team-section-heading__left">
                    <Title level={2} className="national-team-section-heading__title">ETF 监测明细</Title>
                    <Text type="secondary" className="national-team-section-heading__desc">共 {filteredEtfs.length} 只；份额单位为亿份。</Text>
                  </div>
                  <div className="national-team-table-filters">
                    <Space size={8} wrap>
                      <Segmented
                        size="small"
                        value={tableSortPreset}
                        options={[
                          { label: "默认", value: "default" },
                          { label: "今日净买入", value: "flow1d" },
                          { label: "5日变化", value: "flow5d" },
                          { label: "成交活跃", value: "amount" },
                          { label: "规模份额", value: "shares" },
                          { label: "异动放量", value: "abnormal" },
                        ]}
                        onChange={(val) => setTableSortPreset(val as TableSortPreset)}
                        className="national-team-segmented"
                      />
                      <Input
                        size="small"
                        placeholder="搜索代码 / 名称 / 基金公司"
                        prefix={<SearchOutlined />}
                        value={searchKeyword}
                        onChange={(e) => setSearchKeyword(e.target.value)}
                        allowClear
                      />
                      <Segmented
                        size="small"
                        value={selectedFilterIndex}
                        options={filterOptions}
                        onChange={(val) => setSelectedFilterIndex(String(val))}
                        className="national-team-segmented"
                      />
                      <Button
                        size="small"
                        icon={<DownloadOutlined />}
                        onClick={() => {
                          if (filteredEtfs.length === 0) {
                            message.warning("暂无数据可导出");
                            return;
                          }
                          downloadNationalTeamCsv(filteredEtfs, data?.as_of_date);
                          message.success(`已导出 ${filteredEtfs.length} 只 ETF 监测明细数据`);
                        }}
                        disabled={filteredEtfs.length === 0}
                      >
                        导出 CSV
                      </Button>
                    </Space>
                  </div>
                </div>
                <Card className="national-team-table-card" styles={{ body: { padding: 0 } }}>
                  <Table
                    rowKey="code"
                    columns={columns}
                    dataSource={filteredEtfs}
                    pagination={false}
                    scroll={{ x: isMobile ? 960 : 1160 }}
                    size="small"
                    className="national-team-table"
                  />
                </Card>
              </div>
            )}

            {/* 底部规范化口径与方法提示 (轻量化流线型，去除笨重 Card 边框与冗余 padding) */}
            <div
              className="national-team-methodology"
              data-testid="national-team-methodology"
            >
              <div className="national-team-methodology__content">
                <SafetyCertificateOutlined className="national-team-methodology__icon" />
                <span className="national-team-methodology__header">
                  <Text strong>估算方法与口径规范：</Text>
                  <span>{data?.methodology || "ETF 当日份额变化 × ETF 当日收盘价，逐只计算后按宽基汇总。"}</span>
                </span>
                <span className="national-team-methodology__footer">
                  · 特别提示：ETF 份额变动为全市场一级市场申购赎回代理汇总结果，非中央汇金真实持仓；二级市场成交额严禁误称为真实净流入。
                </span>
              </div>
            </div>

            {activeTab === "all" && (
              <div className="u-mb-16">
                <NationalTeamPortraitPanel portrait={data?.portrait} />
              </div>
            )}
          </>
        )}
  </SectionDataState>

      <NationalTeamReportModal
        open={reportModalOpen}
        onClose={() => setReportModalOpen(false)}
        data={data}
      />

      {previewStock && (
        <StockWorkspaceDrawer
          open={Boolean(previewStock)}
          code={previewStock?.code ?? null}
          name={previewStock?.name}
          onClose={() => setPreviewStock(null)}
        />
      )}
    </section>
  );
}
