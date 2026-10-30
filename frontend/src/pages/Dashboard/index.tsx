import { useMemo, useState } from "react";
import {
  AimOutlined,
  ApartmentOutlined,
  AppstoreOutlined,
  AuditOutlined,
  CalendarOutlined,
  CompassOutlined,
  DashboardOutlined,
  DownloadOutlined,
  FireOutlined,
  LineChartOutlined,
  ReloadOutlined,
  RobotOutlined,
  StarOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";
import { Button, Card, FloatButton, Segmented, Table, Tag, Typography } from "antd";
import PageShell from "../../components/page/PageShell";
import type { ColumnsType } from "antd/es/table";
import { useNavigate } from "react-router-dom";
import { useMarketMainline } from "../../api/queries";
import ChangeValue from "../../components/ChangeValue";
import PreloadLink from "../../components/PreloadLink";
import RefreshBadge from "../../components/RefreshBadge";
import SectionDataState from "../../components/SectionDataState";
import StockExternalLink from "../../components/StockExternalLink";
import { useAStockTradingSession } from "../../hooks/useAStockTradingSession";
import { useColors, useTokens, semanticTagStyle } from "../../styles/ui";
import type {
  MarketMainlineChance,
  MarketMainlineStyle,
  MarketMainlineStyleIndex,
} from "../../types/stock";
import { HotRankContent as HotRankBoard } from "../../components/HotRankBoard";
import MarketOverviewBoard from "../../components/MarketOverviewBoard";
import MarketWindBoard from "../../components/MarketWindBoard";
import { marketDateStamp } from "../../utils/marketTime";
import WatchlistPanel from "./WatchlistPanel";
import "./dashboard.css";

const { Text } = Typography;

type MobileDashboardView = "all" | "market" | "mainline" | "watchlist" | "hotrank";

const MOBILE_VIEW_OPTIONS = [
  { label: "全景", value: "all", icon: <AppstoreOutlined /> },
  { label: "大盘", value: "market", icon: <DashboardOutlined /> },
  { label: "主线", value: "mainline", icon: <CompassOutlined /> },
  { label: "自选", value: "watchlist", icon: <StarOutlined /> },
  { label: "热榜", value: "hotrank", icon: <FireOutlined /> },
];

interface MainlineFaucetRow {
  key: string;
  code: string;
  name: string;
  change_pct: number | null;
  reason: string;
  origin: string;
}

interface MainlineStyleStockRow {
  key: string;
  code: string;
  name: string;
  change_30d: number | null;
  indexName: string;
}

function collectFaucetRows(chances: MarketMainlineChance[]): MainlineFaucetRow[] {
  const rows: MainlineFaucetRow[] = [];
  const seen = new Set<string>();
  for (const chance of chances) {
    for (const plate of chance.plates) {
      for (const faucet of plate.faucets) {
        if (seen.has(faucet.code)) continue;
        seen.add(faucet.code);
        rows.push({
          key: faucet.code,
          code: faucet.code,
          name: faucet.name,
          change_pct: faucet.change_pct,
          reason: faucet.reason,
          origin: plate.name === chance.title ? chance.title : `${chance.title} · ${plate.name}`,
        });
      }
    }
  }
  return rows;
}

function collectStyleStockRows(style: MarketMainlineStyle): MainlineStyleStockRow[] {
  const rows: MainlineStyleStockRow[] = [];
  const seen = new Set<string>();
  for (const index of style.indexes) {
    for (const stock of index.stocks) {
      if (seen.has(stock.code)) continue;
      seen.add(stock.code);
      rows.push({
        key: stock.code,
        code: stock.code,
        name: stock.name,
        change_30d: stock.change_30d,
        indexName: index.name || "指数",
      });
    }
  }
  return rows;
}

function MainlineChanceCard({ chance }: { chance: MarketMainlineChance }) {
  const t = useTokens();
  return (
    <Card
      className="dashboard-mainline-card"
      size="small"
      title={chance.title}
      extra={
        <span style={{ display: "inline-flex", gap: t.space[1] }}>
          {chance.continued_days != null && chance.continued_days > 0 ? (
            <Tag className="financial-num" style={{ marginInlineEnd: 0 }}>持续 {chance.continued_days} 天</Tag>
          ) : null}
          {chance.hot != null && chance.hot > 0 ? (
            <Tag className="financial-num" color="volcano" style={{ marginInlineEnd: 0 }}>热度 {chance.hot}</Tag>
          ) : null}
        </span>
      }
      style={{
        borderRadius: t.radius.md,
        boxShadow: t.shadow.xs,
        height: "100%",
        display: "flex",
        flexDirection: "column",
      }}
      styles={{ body: { flex: 1, minHeight: 0 } }}
    >
      {chance.description ? (
        <Text type="secondary" style={{ fontSize: t.font.sm }}>{chance.description}</Text>
      ) : null}
      <div style={{ marginTop: chance.description ? t.space[2] : 0, display: "grid", gap: t.space[2] }}>
        {chance.plates.map((plate) => (
          <div
            key={`${plate.code}-${plate.name}`}
            className="dashboard-mainline-plate"
          >
            <div style={{ display: "flex", alignItems: "baseline", gap: t.space[2], flexWrap: "wrap" }}>
              <Text strong>{plate.name}</Text>
              <ChangeValue value={plate.change_pct} />
              {plate.rise_count != null && plate.rise_count > 0 ? (
                <Text type="secondary" className="financial-num" style={{ fontSize: t.font.xs }}>{plate.rise_count} 家上涨</Text>
              ) : null}
            </div>
            {plate.reason ? (
              <Text type="secondary" style={{ fontSize: t.font.xs }} ellipsis>{plate.reason}</Text>
            ) : null}
          </div>
        ))}
      </div>
    </Card>
  );
}

function MainlineFaucetTableCard({ rows }: { rows: MainlineFaucetRow[] }) {
  const c = useColors();
  const t = useTokens();

  const handleExportCsv = () => {
    const headers = ["股票代码", "股票名称", "所属主线", "涨跌幅(%)", "上涨逻辑"];
    const lines = rows.map((r) => [
      `\t${r.code}`,
      `"${r.name.replace(/"/g, '""')}"`,
      `"${r.origin.replace(/"/g, '""')}"`,
      r.change_pct != null ? r.change_pct.toFixed(2) : "",
      `"${(r.reason || "").replace(/"/g, '""')}"`,
    ].join(","));
    const blob = new Blob(["\uFEFF" + [headers.join(","), ...lines].join("\n")], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `今日主线龙头_${marketDateStamp()}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const columns: ColumnsType<MainlineFaucetRow> = useMemo(() => [
    {
      title: "龙头股",
      key: "stock",
      width: 150,
      render: (_value, row) => (
        <span style={{ display: "inline-flex", alignItems: "baseline", gap: t.space[2] }}>
          <StockExternalLink code={row.code} name={row.name}><strong>{row.name}</strong></StockExternalLink>
          <span className="financial-num" style={{ color: c.textSecondary, fontSize: t.font.xs }}>{row.code}</span>
        </span>
      ),
    },
    { title: "所属主线", dataIndex: "origin", key: "origin", width: 130, ellipsis: true },
    {
      title: "涨跌幅",
      dataIndex: "change_pct",
      key: "change_pct",
      width: 95,
      align: "right",
      sorter: (a, b) => (a.change_pct ?? -Infinity) - (b.change_pct ?? -Infinity),
      render: (value: number | null) => <ChangeValue value={value} />,
    },
    {
      title: "上涨逻辑",
      dataIndex: "reason",
      key: "reason",
      ellipsis: true,
      render: (value: string) => value || "-",
    },
    {
      title: "快速下钻",
      key: "actions",
      width: 135,
      render: (_value, row) => (
        <span style={{ display: "inline-flex", gap: 4 }}>
          <PreloadLink to={`/chat?prompt=${encodeURIComponent(`分析 ${row.name}(${row.code}) 的主线逻辑、资金流向与近期估值`)}`}>
            <Button size="small" type="link" style={{ padding: "0 2px", fontSize: 12 }}>
              问AI
            </Button>
          </PreloadLink>
          <PreloadLink to={`/analysis?code=${row.code}`}>
            <Button size="small" type="link" style={{ padding: "0 2px", fontSize: 12 }}>
              研报
            </Button>
          </PreloadLink>
          <PreloadLink to={`/quant?codes=${row.code}`}>
            <Button size="small" type="link" style={{ padding: "0 2px", fontSize: 12 }}>
              回测
            </Button>
          </PreloadLink>
        </span>
      ),
    },
  ], [c.textSecondary, t.font.xs, t.space]);

  return (
    <Card
      className="dashboard-mainline-card"
      size="small"
      title={`主线龙头股（${rows.length}）`}
      extra={
        rows.length > 0 ? (
          <Button size="small" icon={<DownloadOutlined />} onClick={handleExportCsv}>
            导出 CSV
          </Button>
        ) : null
      }
      style={{ borderRadius: t.radius.md, boxShadow: t.shadow.xs }}
    >
      <div className="dashboard-faucet-desktop-table">
        <Table<MainlineFaucetRow>
          size="small"
          rowKey="key"
          columns={columns}
          dataSource={rows}
          pagination={{ pageSize: 10, size: "small", showSizeChanger: false, hideOnSinglePage: true }}
          scroll={{ x: 500 }}
        />
      </div>
      <div className="dashboard-faucet-mobile-cards">
        {rows.map((row) => (
          <div key={row.key} className="dashboard-faucet-card-item">
            <div className="dashboard-faucet-card-item__top">
              <span className="dashboard-faucet-card-item__name">
                <StockExternalLink code={row.code} name={row.name}>
                  <strong>{row.name}</strong>
                </StockExternalLink>
                <span className="dashboard-faucet-card-item__code financial-num">{row.code}</span>
              </span>
              <ChangeValue value={row.change_pct} />
            </div>
            <div className="dashboard-faucet-card-item__meta">
              <Tag color="blue" style={{ marginInlineEnd: 0, fontSize: 11 }}>{row.origin}</Tag>
            </div>
            {row.reason ? (
              <div className="dashboard-faucet-card-item__reason">
                {row.reason}
              </div>
            ) : null}
            <div className="dashboard-faucet-card-item__actions">
              <PreloadLink to={`/analysis?code=${row.code}`}>
                <Button size="small" type="link" style={{ padding: "0 4px", fontSize: 12 }}>
                  研报
                </Button>
              </PreloadLink>
              <PreloadLink to={`/quant?codes=${row.code}`}>
                <Button size="small" type="link" style={{ padding: "0 4px", fontSize: 12 }}>
                  回测
                </Button>
              </PreloadLink>
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}

function MainlineStyleTableCard({ style }: { style: MarketMainlineStyle }) {
  const c = useColors();
  const t = useTokens();
  const stockRows = useMemo(() => collectStyleStockRows(style), [style]);

  const indexColumns: ColumnsType<MarketMainlineStyleIndex> = useMemo(() => [
    {
      title: "指数",
      key: "name",
      render: (_value, index) => <strong>{index.name || "指数"}</strong>,
    },
    {
      title: "近30日涨跌幅",
      dataIndex: "change_30d",
      key: "change_30d",
      width: 120,
      align: "right",
      sorter: (a, b) => (a.change_30d ?? -Infinity) - (b.change_30d ?? -Infinity),
      render: (value: number | null) => <ChangeValue value={value} />,
    },
  ], []);

  const stockColumns: ColumnsType<MainlineStyleStockRow> = useMemo(() => [
    {
      title: "个股",
      key: "stock",
      width: 150,
      render: (_value, row) => (
        <span style={{ display: "inline-flex", alignItems: "baseline", gap: t.space[2] }}>
          <StockExternalLink code={row.code} name={row.name}><strong>{row.name}</strong></StockExternalLink>
          <span className="financial-num" style={{ color: c.textSecondary, fontSize: t.font.xs }}>{row.code}</span>
        </span>
      ),
    },
    { title: "所属指数", dataIndex: "indexName", key: "indexName", width: 130, ellipsis: true },
    {
      title: "近30日涨跌幅",
      dataIndex: "change_30d",
      key: "change_30d",
      width: 100,
      align: "right",
      sorter: (a, b) => (a.change_30d ?? -Infinity) - (b.change_30d ?? -Infinity),
      render: (value: number | null) => <ChangeValue value={value} />,
    },
    {
      title: "操作",
      key: "actions",
      width: 65,
      render: (_value, row) => (
        <PreloadLink to={`/analysis?code=${row.code}`}>
          <Button size="small" type="link" style={{ padding: "0 2px", fontSize: 12 }}>
            研报
          </Button>
        </PreloadLink>
      ),
    },
  ], [c.textSecondary, t.font.xs, t.space]);

  return (
    <Card
      className="dashboard-mainline-card"
      size="small"
      title="风格判断"
      style={{ borderRadius: t.radius.md, boxShadow: t.shadow.xs }}
      styles={{ body: { display: "grid", gap: t.space[3] } }}
    >
      {style.title || style.interpret ? (
        <div style={{ display: "grid", gap: 2 }}>
          {style.title ? <Text strong style={{ fontSize: t.font.sm }}>{style.title}</Text> : null}
          {style.interpret ? (
            <Text type="secondary" style={{ fontSize: t.font.sm }}>{style.interpret}</Text>
          ) : null}
        </div>
      ) : null}
      {style.indexes.length > 0 ? (
        <div style={{ display: "grid", gap: t.space[2], minWidth: 0 }}>
          <Text strong style={{ fontSize: t.font.sm }}>指数表现</Text>
          <Table<MarketMainlineStyleIndex>
            size="small"
            rowKey="code"
            columns={indexColumns}
            dataSource={style.indexes}
            pagination={false}
            scroll={{ x: 280 }}
          />
        </div>
      ) : null}
      {stockRows.length > 0 ? (
        <div style={{ display: "grid", gap: t.space[2], minWidth: 0 }}>
          <Text strong style={{ fontSize: t.font.sm }}>代表个股</Text>
          <Table<MainlineStyleStockRow>
            size="small"
            rowKey="key"
            columns={stockColumns}
            dataSource={stockRows}
            pagination={{ pageSize: 10, size: "small", showSizeChanger: false, hideOnSinglePage: true }}
            scroll={{ x: 445 }}
          />
        </div>
      ) : null}
    </Card>
  );
}

function DashboardMainlineSection() {
  const t = useTokens();
  const query = useMarketMainline();
  const isTradingSession = useAStockTradingSession();
  const chances = useMemo(() => query.data?.items ?? [], [query.data?.items]);
  const faucetRows = useMemo(() => collectFaucetRows(chances), [chances]);
  const style = query.data?.style ?? null;
  const hasContent = chances.length > 0 || style != null;

  return (
    <section aria-label="今日主线">
      <header className="dashboard-section-heading" style={{ marginBottom: 16 }}>
        <span className="dashboard-section-heading__icon"><AimOutlined /></span>
        <span className="dashboard-section-heading__text">
          <strong>今日主线</strong>
          <small>主线题材机会与市场风格判断</small>
        </span>
        <span className="dashboard-section-heading__actions">
          <Tag style={{ ...semanticTagStyle("primary"), marginInlineEnd: 0 }}>{chances.length} 条主线</Tag>
          <RefreshBadge label={isTradingSession ? "每分钟自动更新" : "每 5 分钟更新"} />
          <Button
            type="text"
            size="small"
            icon={<ReloadOutlined />}
            loading={query.isFetching}
            aria-label="刷新今日主线"
            title="刷新今日主线"
            onClick={() => void query.refetch()}
          />
        </span>
      </header>
      <SectionDataState
        isLoading={query.isLoading}
        error={query.error}
        onRetry={() => query.refetch()}
        isEmpty={!query.isLoading && !query.error && !hasContent}
        emptyText="暂无今日主线数据"
        errorTitle="今日主线加载失败"
        skeletonRows={4}
        minHeight={160}
      >
        <div style={{ display: "grid", gap: t.space[3] }}>
          {chances.length > 0 ? (
            <div className="dashboard-mainline-grid">
              {chances.map((chance) => (
                <MainlineChanceCard key={chance.title} chance={chance} />
              ))}
            </div>
          ) : null}
          {faucetRows.length > 0 ? <MainlineFaucetTableCard rows={faucetRows} /> : null}
          {style ? <MainlineStyleTableCard style={style} /> : null}
        </div>
      </SectionDataState>
    </section>
  );
}

export default function Dashboard() {

  const navigate = useNavigate();
  const [mobileView, setMobileView] = useState<MobileDashboardView>("all");

  const today = new Date();
  const dateStr = `${today.getFullYear()}年${today.getMonth() + 1}月${today.getDate()}日`;

  return (
    <PageShell width="full" className="dashboard-page">
      <header className="dashboard-hero">
        <div className="dashboard-hero__copy">
          <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
            <span className="dashboard-hero__eyebrow">今日市场</span>
            <span style={{ fontSize: "var(--c-font-xs)", color: "var(--c-text-muted)" }}>·</span>
            <span className="dashboard-hero__terminal-badge">
              <span className="dashboard-hero__pulse-dot" />
              A股实时态势
            </span>
            <span style={{ fontSize: "var(--c-font-xs)", color: "var(--c-text-muted)" }}>·</span>
            <span style={{ fontSize: "var(--c-font-xs)", color: "var(--c-text-secondary)", fontFamily: "var(--c-font-mono)" }}>{dateStr}</span>
          </div>
          <h1 className="dashboard-hero__title">市场总览</h1>
        </div>
        <div className="dashboard-hero__shortcuts">
          <Button
            size="small"
            shape="round"
            type="primary"
            className="dashboard-hero__shortcut-btn"
            icon={<RobotOutlined />}
            onClick={() => navigate("/chat?prompt=" + encodeURIComponent("总结今日A股市场全景、领涨主线题材与资金攻击方向"))}
          >
            AI 盘面诊断
          </Button>
          <Button
            size="small"
            shape="round"
            className="dashboard-hero__shortcut-btn"
            icon={<RobotOutlined style={{ color: "var(--c-primary)" }} />}
            onClick={() => navigate("/analysis")}
          >
            个股研报
          </Button>
          <Button
            size="small"
            shape="round"
            className="dashboard-hero__shortcut-btn"
            icon={<ThunderboltOutlined style={{ color: "var(--c-warning, #faad14)" }} />}
            onClick={() => navigate("/screener")}
          >
            智能选股
          </Button>
          <Button
            size="small"
            shape="round"
            className="dashboard-hero__shortcut-btn"
            icon={<LineChartOutlined style={{ color: "var(--c-primary)" }} />}
            onClick={() => navigate("/quant")}
          >
            量化回测
          </Button>
          <Button
            size="small"
            shape="round"
            className="dashboard-hero__shortcut-btn"
            aria-label="产业链图谱"
            icon={<ApartmentOutlined style={{ color: "var(--c-primary)" }} />}
            onClick={() => navigate("/industry-chain")}
          >
            产业链图谱
          </Button>
          <Button
            size="small"
            shape="round"
            className="dashboard-hero__shortcut-btn"
            aria-label="国家队监测"
            icon={<AuditOutlined style={{ color: "var(--c-primary)" }} />}
            onClick={() => navigate("/national-team")}
          >
            国家队监测
          </Button>
          <Button
            size="small"
            shape="round"
            className="dashboard-hero__shortcut-btn"
            aria-label="每日复盘"
            icon={<CalendarOutlined style={{ color: "var(--c-primary)" }} />}
            onClick={() => navigate("/daily-review")}
          >
            每日复盘
          </Button>
        </div>
      </header>
      <div className="dashboard-mobile-nav">
        <Segmented
          block
          value={mobileView}
          onChange={(val) => {
            setMobileView(val as MobileDashboardView);
            if (
              typeof window !== "undefined" &&
              typeof window.scrollTo === "function" &&
              import.meta.env.MODE !== "test"
            ) {
              window.scrollTo({ top: 0, behavior: "smooth" });
            }
          }}
          options={MOBILE_VIEW_OPTIONS}
        />
      </div>
      <div className="dashboard-layout" data-mobile-view={mobileView}>
        <section className="dashboard-main" aria-label="首页中间内容">
          <section className="dashboard-market-board" aria-label="首页市场看板">
            <MarketOverviewBoard showRankings={false} onNavigate={(tab) => navigate(`/market?tab=${tab}`)} />
          </section>
          <section aria-label="市场风向">
            <MarketWindBoard embedded />
          </section>
          <DashboardMainlineSection />
        </section>
        <aside className="dashboard-sidebar" aria-label="首页热榜与自选栏">
          <section aria-label="热榜"><HotRankBoard embedded /></section>
          <WatchlistPanel />
        </aside>
      </div>
      <FloatButton.BackTop tooltip="回到顶部" />
    </PageShell>
  );
}
