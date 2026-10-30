import { useState } from "react";
import {
  DownOutlined,
  FallOutlined,
  LinkOutlined,
  RiseOutlined,
  RobotOutlined,
  SwapOutlined,
  UpOutlined,
} from "@ant-design/icons";
import { Button, Empty, Skeleton, Tooltip } from "antd";
import { useNewsAnalysis } from "../../api/queries";
import QueryErrorState from "../../components/QueryErrorState";
import { useColors } from "../../styles/ui";
import type { NewsAnalysisItem, NewsAnalysisRef } from "../../types/stock";
import { getSentimentConfig } from "../../features/feed/feedHelpers";

function SummaryItem({ item, index }: { item: NewsAnalysisItem; index: number }) {
  const colors = useColors();
  const references: NewsAnalysisRef[] = item.urls || [];

  return (
    <li className="feed-analysis-item">
      <span className="feed-summary-number">{String(index + 1).padStart(2, "0")}</span>
      <div className="feed-analysis-item-content">
        <div className="feed-analysis-text">{item.text}</div>
        {references.length > 0 ? (
          <div className="feed-analysis-sources">
            {references.map((reference, referenceIndex) => (
              <Tooltip key={`${reference.url}-${referenceIndex}`} title={reference.title || reference.url} placement="bottom">
                <a
                  href={reference.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="feed-srctag"
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 3,
                    maxWidth: 190,
                    padding: "2px 8px",
                    color: colors.primary,
                    borderRadius: 4,
                    fontSize: "var(--c-font-xs)",
                    lineHeight: "16px",
                    textDecoration: "none",
                  }}
                >
                  <LinkOutlined style={{ flexShrink: 0, fontSize: 10 }} />
                  <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {reference.title || "参考来源"}
                  </span>
                </a>
              </Tooltip>
            ))}
          </div>
        ) : null}
      </div>
    </li>
  );
}

export default function NewsAnalysisPanel() {
  const colors = useColors();
  const { data: analysis, isLoading, error, refetch } = useNewsAnalysis();
  const [mobileExpanded, setMobileExpanded] = useState(false);

  if (isLoading) {
    return (
      <div className="feed-analysis">
        <h2 className="feed-section-heading">AI 市场摘要</h2>
        <div className="feed-state">
          <Skeleton active paragraph={{ rows: 7 }} />
        </div>
      </div>
    );
  }

  if (error && !analysis) {
    return (
      <div className="feed-analysis">
        <h2 className="feed-section-heading">AI 市场摘要</h2>
        <div className="feed-state">
          <QueryErrorState error={error} onRetry={() => refetch()} title="AI 资讯摘要加载失败" compact />
        </div>
      </div>
    );
  }

  if (!analysis) {
    return (
      <div className="feed-analysis">
        <h2 className="feed-section-heading">AI 市场摘要</h2>
        <div className="feed-state">
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无 AI 资讯摘要" />
        </div>
      </div>
    );
  }

  const sentiment = analysis.market_sentiment || "中性";
  const sentimentConfig = getSentimentConfig(colors)[sentiment] || getSentimentConfig(colors)["中性"];
  const sentimentScore = sentiment === "偏多" ? 78 : sentiment === "偏空" ? 22 : 50;

  const SentimentIcon =
    sentiment === "偏多"
      ? RiseOutlined
      : sentiment === "偏空"
      ? FallOutlined
      : SwapOutlined;

  const totalPoints = (analysis.sections || []).reduce((acc, s) => acc + (s.items?.length || 0), 0);

  return (
    <div className="feed-analysis">
      <div className="feed-analysis-header">
        <h2 className="feed-section-heading">
          <RobotOutlined style={{ marginRight: 7, color: colors.primary, fontSize: 16 }} />
          AI 市场摘要
        </h2>
        <span
          className="feed-sentiment"
          style={{ color: sentimentConfig.color, background: sentimentConfig.bg }}
        >
          <SentimentIcon style={{ marginRight: 4 }} />
          {sentiment}
        </span>
      </div>

      <div className="feed-sentiment-gauge">
        <div className="feed-sentiment-gauge-info">
          <span className="feed-sentiment-label">盘面多空倾向度</span>
          <span className="feed-sentiment-value financial-num" style={{ color: sentimentConfig.color }}>
            {sentimentScore}%
          </span>
        </div>
        <div className="feed-sentiment-meter" aria-label={`市场情绪：${sentiment} (${sentimentScore}%)`}>
          <span style={{ width: `${sentimentScore}%`, background: sentimentConfig.color }} />
        </div>
      </div>

      <p className="feed-analysis-lead">{analysis.summary}</p>

      {/* 移动端展开/折叠按钮 */}
      {totalPoints > 0 && (
        <div className="feed-analysis-mobile-toggle">
          <Button
            type="link"
            size="small"
            onClick={() => setMobileExpanded((prev) => !prev)}
            icon={mobileExpanded ? <UpOutlined /> : <DownOutlined />}
            style={{ padding: 0, fontSize: "var(--c-font-xs)" }}
          >
            {mobileExpanded ? "收起详细研判" : `展开全部详细研判（共 ${totalPoints} 项）`}
          </Button>
        </div>
      )}

      <div className={`feed-analysis-scroll ${mobileExpanded ? "is-expanded" : ""}`}>
        {(analysis.sections || []).map((section, sectionIndex) => (
          <section className="feed-analysis-section" key={`${section.title}-${sectionIndex}`}>
            <h3 className="feed-analysis-section-title">
              <span aria-hidden="true" style={{ marginRight: 6 }}>{section.icon}</span>
              {section.title}
            </h3>
            <ol className="feed-analysis-list">
              {(section.items || []).map((item, itemIndex) => (
                <SummaryItem key={`${item.text}-${itemIndex}`} item={item} index={itemIndex} />
              ))}
            </ol>
          </section>
        ))}
      </div>
    </div>
  );
}
