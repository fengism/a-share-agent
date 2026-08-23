import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { AimOutlined } from "@ant-design/icons";
import { Card, Col, Row, Tag, Typography } from "antd";
import { useMarketIndices, useMarketMainline } from "../../api/queries";
import ChangeValue from "../../components/ChangeValue";
import IndexIntradayCard from "../../components/IndexIntradayCard";
import SectionDataState from "../../components/SectionDataState";
import StockExternalLink from "../../components/StockExternalLink";
import { useColors, useStyles, useTokens } from "../../styles/ui";
import type { MarketMainlineChance, MarketMainlineStyle } from "../../types/stock";
import { formatAmount } from "../../utils/format";
import { HotRankContent as HotRankBoard } from "../../components/HotRankBoard";
import MarketWindBoard from "../../components/MarketWindBoard";
import WatchlistPanel from "./WatchlistPanel";

const { Text } = Typography;

const INDEX_NAMES = ["上证指数", "深证成指", "创业板指", "科创50", "沪深300", "中证500"];

function formatIndexPrice(value: number | string | null | undefined) {
  const numericValue = typeof value === "number" ? value : Number(value);
  return Number.isFinite(numericValue) ? numericValue.toFixed(2) : "-";
}

function SectionHeading({ icon, title }: { icon: ReactNode; title: string }) {
  const c = useColors();
  const t = useTokens();
  return (
    <div style={{ display: "flex", alignItems: "center", gap: t.space[2] }}>
      <span style={{ color: c.primary, fontSize: t.font.lg, display: "inline-flex" }}>{icon}</span>
      <Text strong style={{ fontSize: t.font.lg, color: c.textPrimary }}>{title}</Text>
    </div>
  );
}

function MainlineChanceCard({ chance }: { chance: MarketMainlineChance }) {
  const c = useColors();
  const t = useTokens();
  return (
    <Card
      size="small"
      title={chance.title}
      extra={
        <span style={{ display: "inline-flex", gap: t.space[1] }}>
          {chance.continued_days != null && chance.continued_days > 0 ? (
            <Tag style={{ marginInlineEnd: 0 }}>持续 {chance.continued_days} 天</Tag>
          ) : null}
          {chance.hot != null && chance.hot > 0 ? (
            <Tag color="volcano" style={{ marginInlineEnd: 0 }}>热度 {chance.hot}</Tag>
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
            style={{
              background: c.nestedBg,
              borderRadius: t.radius.sm,
              padding: `${t.space[2]} ${t.space[3]}`,
              display: "grid",
              gap: t.space[1],
            }}
          >
            <div style={{ display: "flex", alignItems: "baseline", gap: t.space[2], flexWrap: "wrap" }}>
              <Text strong>{plate.name}</Text>
              <ChangeValue value={plate.change_pct} />
              {plate.rise_count != null && plate.rise_count > 0 ? (
                <Text type="secondary" style={{ fontSize: t.font.xs }}>{plate.rise_count} 家上涨</Text>
              ) : null}
            </div>
            {plate.reason ? (
              <Text type="secondary" style={{ fontSize: t.font.xs }} ellipsis>{plate.reason}</Text>
            ) : null}
            {plate.faucets.length > 0 ? (
              <div style={{ display: "flex", flexWrap: "wrap", gap: t.space[3] }}>
                {plate.faucets.map((faucet) => (
                  <span key={faucet.code} style={{ display: "inline-flex", alignItems: "baseline", gap: t.space[1] }}>
                    <StockExternalLink code={faucet.code} name={faucet.name}>
                      {faucet.name}
                    </StockExternalLink>
                    <ChangeValue value={faucet.change_pct} />
                    {faucet.reason ? (
                      <Text type="secondary" style={{ fontSize: t.font.xs }}>{faucet.reason}</Text>
                    ) : null}
                  </span>
                ))}
              </div>
            ) : null}
          </div>
        ))}
      </div>
    </Card>
  );
}

function MainlineStyleCard({ style }: { style: MarketMainlineStyle }) {
  const c = useColors();
  const t = useTokens();
  return (
    <Card
      size="small"
      title="风格判断"
      style={{
        borderRadius: t.radius.md,
        boxShadow: t.shadow.xs,
        height: "100%",
        display: "flex",
        flexDirection: "column",
      }}
      styles={{ body: { flex: 1, minHeight: 0 } }}
    >
      <div style={{ display: "grid", gap: t.space[2] }}>
        <div style={{ display: "grid", gap: 2 }}>
          {style.title ? (
            <Text strong style={{ fontSize: t.font.sm }}>{style.title}</Text>
          ) : null}
          {style.interpret ? (
            <Text type="secondary" style={{ fontSize: t.font.xs }}>{style.interpret}</Text>
          ) : null}
        </div>
        {style.indexes.map((index) => (
          <div
            key={`${index.code}-${index.name}`}
            style={{
              background: c.nestedBg,
              borderRadius: t.radius.sm,
              padding: `${t.space[2]} ${t.space[3]}`,
              display: "grid",
              gap: 2,
            }}
          >
            <div style={{ display: "flex", alignItems: "baseline", gap: t.space[2], flexWrap: "wrap" }}>
              <Text strong style={{ fontSize: t.font.sm }}>{index.name || "指数"}</Text>
              <ChangeValue value={index.change_30d} />
              <Text type="secondary" style={{ fontSize: t.font.xs }}>近30日</Text>
            </div>
            {index.stocks.length > 0 ? (
              <div style={{ display: "grid", gap: 2 }}>
                {index.stocks.slice(0, 5).map((stock) => (
                  <span key={stock.code} style={{ display: "inline-flex", alignItems: "baseline", gap: t.space[1] }}>
                    <StockExternalLink code={stock.code} name={stock.name}>
                      {stock.name}
                    </StockExternalLink>
                    <ChangeValue value={stock.change_30d} />
                  </span>
                ))}
              </div>
            ) : null}
          </div>
        ))}
      </div>
    </Card>
  );
}

function DashboardMainlineSection() {
  const t = useTokens();
  const query = useMarketMainline();
  const chances = useMemo(() => query.data?.items ?? [], [query.data?.items]);

  return (
    <section aria-label="今日主线" style={{ marginTop: t.space[4] }}>
      <SectionHeading icon={<AimOutlined />} title="今日主线" />
      <SectionDataState
        isLoading={query.isLoading}
        error={query.error}
        onRetry={() => query.refetch()}
        isEmpty={!query.isLoading && !query.error && chances.length === 0}
        emptyText="暂无今日主线数据"
        errorTitle="今日主线加载失败"
        skeletonRows={4}
        minHeight={160}
      >
        <div className="dashboard-mainline-grid" style={{ marginTop: t.space[2] }}>
          {chances.map((chance) => (
            <MainlineChanceCard key={chance.title} chance={chance} />
          ))}
          {query.data?.style ? <MainlineStyleCard style={query.data.style} /> : null}
        </div>
      </SectionDataState>
    </section>
  );
}

export default function Dashboard() {
  const { data: marketData, isLoading, error, refetch } = useMarketIndices();
  const c = useColors();
  const t = useTokens();
  const { pageContainerStyle, rowGutter } = useStyles();
  const [activeIndexCode, setActiveIndexCode] = useState("000001");

  const mainIndices = useMemo(
    () => INDEX_NAMES.map(
      (name) => (marketData?.indices || []).find((item) => item.name === name),
    ).filter((item) => item != null),
    [marketData],
  );
  const activeIndex = mainIndices.find((item) => item.code === activeIndexCode) ?? mainIndices[0];

  useEffect(() => {
    if (mainIndices.length > 0 && !mainIndices.some((item) => item.code === activeIndexCode)) {
      setActiveIndexCode(mainIndices[0].code);
    }
  }, [activeIndexCode, mainIndices]);

  const today = new Date();
  const dateStr = `${today.getFullYear()}年${today.getMonth() + 1}月${today.getDate()}日`;

  return (
    <div className="dashboard-page" style={pageContainerStyle}>
      <header className="dashboard-hero">
        <div className="dashboard-hero__copy">
          <span className="dashboard-hero__eyebrow">今日市场</span>
          <h1>市场总览</h1>
          <p>{dateStr}</p>
        </div>
        <div className="dashboard-hero__meta" aria-label="市场概览元数据">
          <span>当前查看 {activeIndex?.name || "等待行情"} · {activeIndex?.code || "-"}</span>
        </div>
      </header>
      <div className="dashboard-layout">
        <section className="dashboard-main" aria-label="市场概览">
          <SectionDataState
            isLoading={isLoading}
            error={error}
            onRetry={() => refetch()}
            isEmpty={mainIndices.length === 0}
            emptyText="暂无市场指数数据"
            errorTitle="市场指数加载失败"
            skeletonRows={3}
            minHeight={180}
          >
            <Row gutter={[rowGutter, rowGutter]}>
              {mainIndices.map((idx) => {
                const isUp = idx.change_pct != null && idx.change_pct > 0;
                const isDown = idx.change_pct != null && idx.change_pct < 0;
                const color = isUp ? c.up : isDown ? c.down : c.textSecondary;
                return (
                  <Col xs={24} sm={12} md={8} key={idx.code}>
                    <button
                      type="button"
                      aria-label={`选择${idx.name}分时图`}
                      aria-pressed={idx.code === activeIndex?.code}
                      onClick={() => setActiveIndexCode(idx.code)}
                      className={`dashboard-index-button${idx.code === activeIndex?.code ? " is-active" : ""}`}
                    >
                      <div className={`dashboard-index-tile${idx.code === activeIndex?.code ? " is-active" : ""}`} style={{
                        display: "flex", flexDirection: "column", gap: t.space[1],
                        background: idx.code === activeIndex?.code ? c.activeBg : c.hoverBg,
                        borderStyle: "solid", borderWidth: "1px 1px 1px 3px",
                        borderColor: `${idx.code === activeIndex?.code ? c.primary : c.border} ${idx.code === activeIndex?.code ? c.primary : c.border} ${idx.code === activeIndex?.code ? c.primary : c.border} ${color}`,
                        borderRadius: t.radius.md, height: "100%", boxSizing: "border-box",
                      }}>
                        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: t.space[2] }}>
                          <span className="dashboard-index-tile__identity">
                            <Text style={{ color: c.textSecondary, fontSize: t.font.md, fontWeight: Number(t.weight.medium) }}>{idx.name}</Text>
                            <Text type="secondary" style={{ fontSize: t.font.xs }}>{idx.code}</Text>
                          </span>
                          <Text style={{ color: c.textMuted, fontSize: t.font.sm }}>额 {formatAmount(idx.amount)}</Text>
                        </div>
                        <div style={{ display: "flex", alignItems: "baseline", gap: t.space[2] }}>
                          <Text style={{ color, fontSize: t.font["2xl"], fontWeight: Number(t.weight.bold), lineHeight: t.leading.tight }}>{formatIndexPrice(idx.price)}</Text>
                          <ChangeValue value={idx.change_pct} showIcon style={{ fontSize: t.font.base }} />
                        </div>
                      </div>
                    </button>
                  </Col>
                );
              })}
            </Row>
            {activeIndex && (
              <div style={{ marginTop: t.space[4] }}>
                <IndexIntradayCard
                  symbol={activeIndex.code}
                  name={activeIndex.name}
                  price={activeIndex.price}
                  changePct={activeIndex.change_pct}
                  preClose={activeIndex.pre_close}
                  height={300}
                />
              </div>
            )}
          </SectionDataState>
          <DashboardMainlineSection />
          <section aria-label="今日风口" style={{ marginTop: t.space[4] }}>
            <MarketWindBoard embedded />
          </section>
        </section>
        <aside className="dashboard-sidebar" aria-label="首页榜单与自选栏">
          <HotRankBoard embedded />
          <WatchlistPanel />
        </aside>
      </div>
    </div>
  );
}
