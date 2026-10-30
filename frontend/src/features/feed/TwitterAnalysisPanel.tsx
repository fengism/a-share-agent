import { useState } from "react";
import { LinkOutlined, ReloadOutlined, RobotOutlined } from "@ant-design/icons";
import { Button, Empty, message, Select, Skeleton, Tag } from "antd";
import dayjs from "dayjs";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useMarketTwitterAnalysis, useMarketTwitterAnalysisRefresh } from "../../api/queries";
import QueryErrorState from "../../components/QueryErrorState";
import { useColors, semanticTagStyle } from "../../styles/ui";

const markdownPlugins = [remarkGfm];

export interface TwitterAnalysisPanelProps {
  authors: string[];
  selectedAuthor?: string;
  onSelectAuthor?: (author: string) => void;
}

export default function TwitterAnalysisPanel({
  authors,
  selectedAuthor,
  onSelectAuthor,
}: TwitterAnalysisPanelProps) {
  const colors = useColors();
  const [internalAuthor, setInternalAuthor] = useState("");
  const activeAuthor = selectedAuthor !== undefined
    ? (authors.includes(selectedAuthor) ? selectedAuthor : authors[0] || "")
    : (authors.includes(internalAuthor) ? internalAuthor : authors[0] || "");

  const handleAuthorChange = (newAuthor: string) => {
    if (onSelectAuthor) {
      onSelectAuthor(newAuthor);
    } else {
      setInternalAuthor(newAuthor);
    }
  };

  const { data: analysis, isLoading, error, refetch } = useMarketTwitterAnalysis(activeAuthor);
  const regenerateMutation = useMarketTwitterAnalysisRefresh(activeAuthor);
  const coreViews = analysis?.core_views || [];
  const sectors = analysis?.sectors || [];
  const stocks = analysis?.stocks || [];
  const risks = analysis?.risks || [];
  const hasStructuredAnalysis = Boolean(
    analysis?.summary || coreViews.length || sectors.length || stocks.length || risks.length,
  );

  return (
    <div className="twitter-analysis">
      <div className="feed-analysis-header">
        <h2 className="feed-section-heading">
          <RobotOutlined style={{ marginRight: 7, color: colors.primary, fontSize: 15 }} />
          AI 大 V 解读
        </h2>
      </div>

      {authors.length > 0 ? (
        <div className="twitter-analysis-controls">
          <span>选择解读账号</span>
          <Select
            aria-label="选择 Twitter 大 V"
            value={activeAuthor}
            onChange={handleAuthorChange}
            options={authors.map((author) => ({ value: author, label: `@${author}` }))}
            showSearch
            optionFilterProp="label"
            size="small"
          />
          <Button
            icon={<ReloadOutlined />}
            loading={regenerateMutation.isPending}
            disabled={!activeAuthor}
            onClick={() => regenerateMutation.mutate(undefined, {
              onSuccess: () => message.success("AI 大 V 解读已重新生成"),
              onError: (regenerateError) => message.error(regenerateError?.message || "重新生成失败"),
            })}
            size="small"
          >
            重新生成
          </Button>
        </div>
      ) : null}

      {!activeAuthor ? (
        <div className="feed-state">
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无可解读的 Twitter 账号" />
        </div>
      ) : isLoading ? (
        <div className="feed-state">
          <Skeleton active paragraph={{ rows: 8 }} />
        </div>
      ) : error && !analysis ? (
        <div className="feed-state">
          <QueryErrorState error={error} onRetry={() => refetch()} title="AI 大 V 解读加载失败" compact />
        </div>
      ) : analysis ? (
        <div className="twitter-analysis-scroll">
          <div className="twitter-analysis-meta">
            <span>基于 @{analysis.username} 最近 {analysis.content_count} 条推文与文章生成</span>
            <span>
              {analysis.cache_hit ? "缓存结果" : "最新生成"}
              {analysis.generated_at ? ` · ${dayjs(analysis.generated_at).format("MM-DD HH:mm")}` : ""}
            </span>
          </div>
          {hasStructuredAnalysis ? (
            <div className="twitter-analysis-structured">
              <div className="twitter-analysis-overview">
                <div>
                  <Tag style={analysis.stance === "看多" ? semanticTagStyle("up") : analysis.stance === "看空" ? semanticTagStyle("down") : undefined}>
                    {analysis.stance || "中性"}
                  </Tag>
                  <span>置信度 {analysis.confidence || 0}%</span>
                </div>
                <p>{analysis.summary}</p>
              </div>

              {coreViews.length > 0 ? (
                <section className="twitter-analysis-section">
                  <h3>核心研判</h3>
                  {coreViews.map((view, index) => (
                    <article className="twitter-analysis-view" key={`${view.text}-${index}`}>
                      <div className="twitter-analysis-view-meta">
                        <Tag
                          color={view.stance === "看多" ? "red" : view.stance === "看空" ? "green" : "default"}
                          style={{ margin: 0 }}
                        >
                          {view.stance}
                        </Tag>
                        <span>置信度 {view.confidence}%</span>
                      </div>
                      <p>{view.text}</p>
                      {(view.references || []).length > 0 ? (
                        <div className="twitter-analysis-references">
                          <span className="twitter-analysis-references-title">佐证原文：</span>
                          {(view.references || []).map((reference) => (
                            <a
                              key={`${reference.index}-${reference.url}`}
                              href={reference.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="twitter-ref-pill"
                            >
                              <LinkOutlined style={{ marginRight: 4 }} />
                              [{reference.index}] {reference.title || "推文原文"}
                            </a>
                          ))}
                        </div>
                      ) : null}
                    </article>
                  ))}
                </section>
              ) : null}

              {sectors.length > 0 || stocks.length > 0 ? (
                <section className="twitter-analysis-section">
                  <h3>重点关注标的与板块</h3>
                  <div className="twitter-analysis-tags">
                    {sectors.map((sector) => <Tag key={`sector-${sector}`}>{sector}</Tag>)}
                    {stocks.map((stock) => <Tag style={semanticTagStyle("primary")} key={`stock-${stock}`}>{stock}</Tag>)}
                  </div>
                </section>
              ) : null}

              {risks.length > 0 ? (
                <section className="twitter-analysis-section">
                  <h3>风险提示</h3>
                  <ul>{risks.map((risk) => <li key={risk}>{risk}</li>)}</ul>
                </section>
              ) : null}
            </div>
          ) : (
            <div className="twitter-analysis-markdown">
              <ReactMarkdown
                remarkPlugins={markdownPlugins}
                components={{
                  table: ({ children }) => (
                    <div className="twitter-analysis-table-wrap">
                      <table>{children}</table>
                    </div>
                  ),
                }}
              >
                {analysis.analysis}
              </ReactMarkdown>
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
}
