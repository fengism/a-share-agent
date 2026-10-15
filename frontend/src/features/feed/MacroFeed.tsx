import { useMemo, useState } from "react";
import { LinkOutlined } from "@ant-design/icons";
import { Card, Segmented, Tag, Typography } from "antd";
import { useMacroAnalysis, useMacroFeed } from "../../api/queries";
import SectionDataState from "../../components/SectionDataState";
import { useColors, useTokens } from "../../styles/ui";
import type {
  MacroAnalysisEvent,
  MacroFeedItem,
  MacroRateItem,
} from "../../types/stock";
import "./macro-feed.css";

const { Text } = Typography;

type PolicyView = "news" | "readings";

const LIST_PREVIEW = 8;
const TIMELINE_PREVIEW = 8;

function impactClass(impact: string): string {
  if (impact === "偏多") return "up";
  if (impact === "偏空") return "down";
  return "flat";
}

function matches(query: string, ...values: string[]): boolean {
  if (!query) return true;
  const keyword = query.trim().toLocaleLowerCase("zh-CN");
  if (!keyword) return true;
  return values.some((value) => value.toLocaleLowerCase("zh-CN").includes(keyword));
}

function RatesCard({ rates }: { rates: MacroRateItem[] }) {
  const t = useTokens();
  return (
    <Card
      className="macro-card"
      size="small"
      title="利率"
      extra={<Text type="secondary" style={{ fontSize: t.font.xs }}>LPR / SHIBOR</Text>}
    >
      <div className="macro-rates">
        {rates.map((rate) => (
          <div key={rate.key} className="macro-rate">
            <span className="macro-rate__label">{rate.label}</span>
            <strong className="macro-rate__value financial-num">
              {rate.value != null ? rate.value.toFixed(rate.value < 10 ? 2 : 2) : "-"}
              <small>{rate.unit}</small>
            </strong>
            <span className="macro-rate__meta">
              {rate.change_bp != null && rate.change_bp !== 0 ? (
                <span className={`macro-rate__change is-${rate.change_bp > 0 ? "up" : "down"}`}>
                  {rate.change_bp > 0 ? "+" : ""}
                  {rate.change_bp}bp
                </span>
              ) : null}
              {rate.period ? <span className="macro-rate__period">{rate.period}</span> : null}
            </span>
          </div>
        ))}
      </div>
    </Card>
  );
}

function FeedList({ items, emptyText, preview = LIST_PREVIEW }: { items: MacroFeedItem[]; emptyText: string; preview?: number }) {
  const [expanded, setExpanded] = useState(false);
  if (items.length === 0) {
    return <div className="macro-empty">{emptyText}</div>;
  }
  const visible = expanded ? items : items.slice(0, preview);
  return (
    <>
      <ul className="macro-list">
        {visible.map((item) => (
          <li key={item.id} className="macro-list__item">
            <a className="macro-list__title" href={item.url} target="_blank" rel="noreferrer">
              {item.title}
              <LinkOutlined className="macro-list__icon" />
            </a>
            <span className="macro-list__date financial-num">{item.published_at}</span>
          </li>
        ))}
      </ul>
      {items.length > preview ? (
        <button type="button" className="macro-more" onClick={() => setExpanded((value) => !value)}>
          {expanded ? "收起" : `展开全部（${items.length}）`}
        </button>
      ) : null}
    </>
  );
}

function EventTimeline({ events, preview = TIMELINE_PREVIEW }: { events: MacroAnalysisEvent[]; preview?: number }) {
  const [expanded, setExpanded] = useState(false);
  if (events.length === 0) {
    return <div className="macro-empty">暂无宏观事件</div>;
  }
  const visible = expanded ? events : events.slice(0, preview);
  return (
    <>
      <ol className="macro-timeline">
        {visible.map((event, index) => {
        const ref = event.refs[0];
        const showInterpretation = Boolean(event.interpretation) && event.interpretation !== event.title;
        return (
          <li key={`${event.date}-${event.title}-${index}`} className="macro-timeline__item">
            <span className="macro-timeline__date financial-num">{event.date.slice(5)}</span>
            <div className="macro-timeline__body">
              <div className="macro-timeline__head">
                {event.category ? <Tag className="macro-timeline__tag">{event.category}</Tag> : null}
                <span className={`macro-impact is-${impactClass(event.impact)}`}>{event.impact}</span>
              </div>
              {ref?.url ? (
                <a className="macro-timeline__title" href={ref.url} target="_blank" rel="noreferrer">
                  {event.title}
                  <LinkOutlined className="macro-list__icon" />
                </a>
              ) : (
                <span className="macro-timeline__title">{event.title}</span>
              )}
              {showInterpretation ? (
                <p className="macro-timeline__interpretation">{event.interpretation}</p>
              ) : null}
            </div>
          </li>
        );
        })}
      </ol>
      {events.length > preview ? (
        <button type="button" className="macro-more" onClick={() => setExpanded((value) => !value)}>
          {expanded ? "收起" : `展开全部（${events.length}）`}
        </button>
      ) : null}
    </>
  );
}

export default function MacroFeed({ searchQuery = "" }: { searchQuery?: string }) {
  const colors = useColors();
  const t = useTokens();
  const feed = useMacroFeed();
  const analysis = useMacroAnalysis();
  const [policyView, setPolicyView] = useState<PolicyView>("news");

  const feedData = feed.data;
  const analysisData = analysis.data;

  const events = useMemo(
    () =>
      (analysisData?.events ?? []).filter((event) =>
        matches(searchQuery, event.title, event.interpretation, event.category),
      ),
    [analysisData?.events, searchQuery],
  );

  const releases = useMemo(
    () => (feedData?.releases ?? []).filter((item) => matches(searchQuery, item.title)),
    [feedData?.releases, searchQuery],
  );

  const policyItems = useMemo(() => {
    const source = policyView === "news" ? feedData?.policy_news ?? [] : feedData?.policy_readings ?? [];
    return source.filter((item) => matches(searchQuery, item.title));
  }, [feedData?.policy_news, feedData?.policy_readings, policyView, searchQuery]);

  const hasFeed = Boolean(
    feedData &&
      (feedData.releases.length ||
        feedData.policy_news.length ||
        feedData.policy_readings.length ||
        feedData.rates.length),
  );

  return (
    <div className="macro-feed">
      <SectionDataState
        isLoading={analysis.isLoading}
        error={analysis.error}
        onRetry={() => analysis.refetch()}
        isEmpty={!analysis.isLoading && !analysis.error && !analysisData}
        emptyText="暂无宏观解读"
        errorTitle="宏观解读加载失败"
        skeletonRows={6}
        minHeight={220}
      >
        <Card
          className="macro-card macro-analysis"
          size="small"
          title="宏观解读（AI）"
          extra={
            <Text type="secondary" style={{ fontSize: t.font.xs }}>
              {analysisData?.period ?? ""}
            </Text>
          }
        >
          {analysisData?.summary ? (
            <div className="macro-analysis__summary">
              <span className={`macro-impact is-${impactClass(analysisData.sentiment)}`}>
                {analysisData.sentiment}
              </span>
              <p>{analysisData.summary}</p>
            </div>
          ) : null}
          {analysisData?.warning ? (
            <div className="macro-analysis__warning" style={{ color: colors.warning }}>
              {analysisData.warning}
            </div>
          ) : null}
          {analysisData?.policy_signals?.length ? (
            <div className="macro-analysis__signals">
              {analysisData.policy_signals.map((signal) => (
                <Tag key={signal} className="macro-signal">
                  {signal}
                </Tag>
              ))}
            </div>
          ) : null}
          <EventTimeline events={events} />
        </Card>
      </SectionDataState>

      <SectionDataState
        isLoading={feed.isLoading}
        error={feed.error}
        onRetry={() => feed.refetch()}
        isEmpty={!feed.isLoading && !feed.error && !hasFeed}
        emptyText="暂无宏观数据"
        errorTitle="宏观数据加载失败"
        skeletonRows={5}
        minHeight={200}
      >
        <RatesCard rates={feedData?.rates ?? []} />
        <div className="macro-lists">
          <Card className="macro-card" size="small" title={`国家统计局发布数据（${releases.length}）`}>
            <FeedList items={releases} emptyText="近一个月暂无发布数据" />
          </Card>
          <Card
            className="macro-card"
            size="small"
            title="金融政策"
            extra={
              <Segmented
                size="small"
                aria-label="金融政策分类"
                value={policyView}
                onChange={(value) => setPolicyView(value as PolicyView)}
                options={[
                  { label: "新闻发布", value: "news" },
                  { label: "政策解读", value: "readings" },
                ]}
              />
            }
          >
            <FeedList items={policyItems} emptyText="暂无金融政策" />
          </Card>
        </div>
        {feedData?.status === "partial" && feedData.failed_sources.length > 0 ? (
          <Text type="secondary" style={{ fontSize: t.font.xs }}>
            部分数据源暂不可用：{feedData.failed_sources.join("、")}
          </Text>
        ) : null}
      </SectionDataState>
    </div>
  );
}
