import { useState } from "react";
import { LinkOutlined, ReloadOutlined, RobotOutlined } from "@ant-design/icons";
import { Button, Empty, message, Select, Skeleton, Tag } from "antd";
import dayjs from "dayjs";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useMarketTwitterAnalysis, useMarketTwitterAnalysisRefresh } from "../../api/queries";
import QueryErrorState from "../../components/QueryErrorState";
import { useColors } from "../../styles/ui";

const markdownPlugins = [remarkGfm];

export default function TwitterAnalysisPanel({ authors }: { authors: string[] }) {
  const colors = useColors();
  const [preferredAuthor, setPreferredAuthor] = useState("");
  const selectedAuthor = authors.includes(preferredAuthor) ? preferredAuthor : authors[0] || "";
  const { data: analysis, isLoading, error, refetch } = useMarketTwitterAnalysis(selectedAuthor);
  const regenerateMutation = useMarketTwitterAnalysisRefresh(selectedAuthor);
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
            value={selectedAuthor}
            onChange={setPreferredAuthor}
            options={authors.map((author) => ({ value: author, label: `@${author}` }))}
            showSearch
            optionFilterProp="label"
            size="small"
          />
          <Button
            icon={<ReloadOutlined />}
            loading={regenerateMutation.isPending}
            disabled={!selectedAuthor}
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

      {!selectedAuthor ? (
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
        <div className="feed-analysis-scroll">
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
                  <Tag color={analysis.stance === "看多" ? "green" : analysis.stance === "看空" ? "red" : "default"}>
                    {analysis.stance || "中性"}
                  </Tag>
                  <span>置信度 {analysis.confidence || 0}%</span>
                </div>
                <p>{analysis.summary}</p>
              </div>

              {coreViews.length > 0 ? (
                <section className="twitter-analysis-section">
                  <h3>核心观点</h3>
                  {coreViews.map((view, index) => (
                    <article className="twitter-analysis-view" key={`${view.text}-${index}`}>
                      <div className="twitter-analysis-view-meta">
                        <span>{view.stance}</span>
                        <span>置信度 {view.confidence}%</span>
                      </div>
                      <p>{view.text}</p>
                      {(view.references || []).length > 0 ? (
                        <div className="twitter-analysis-references">
                          {(view.references || []).map((reference) => (
                            <a key={`${reference.index}-${reference.url}`} href={reference.url} target="_blank" rel="noopener noreferrer">
                              <LinkOutlined /> [{reference.index}] {reference.title || "原文"}
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
                  <h3>关注方向</h3>
                  <div className="twitter-analysis-tags">
                    {sectors.map((sector) => <Tag key={`sector-${sector}`}>{sector}</Tag>)}
                    {stocks.map((stock) => <Tag color="blue" key={`stock-${stock}`}>{stock}</Tag>)}
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
