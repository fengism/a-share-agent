import { useState, useCallback, useEffect, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Input, Steps, Typography, Spin, Tag, Button, message, Empty, Tooltip, Popover, Modal } from "antd";
import { SearchOutlined, ApartmentOutlined, CheckCircleOutlined, LoadingOutlined, CloseCircleOutlined, SendOutlined, HistoryOutlined, CloudUploadOutlined, FullscreenOutlined } from "@ant-design/icons";
import ReactECharts from "echarts-for-react/lib/core";
import DOMPurify from "dompurify";
import echarts from "../../charts/echarts-setup";
import { streamIndustryChain, type IndustryChainProgress } from "../../api/sse";
import { useConfig, usePush, useIndustryChainHistory, useIndustryChainArchive, useIndustryChainLatest } from "../../api/queries";
import { useColors, useStyles } from "../../styles/ui";
import type { IndustryChainResult, IndustryChainHistoryItem, IndustryChainChart } from "../../types/stock";

const { Title, Paragraph, Text } = Typography;
const { Search } = Input;

const STAGE_MAP: Record<string, number> = {
  "搜索产业链相关公司": 0,
  "获取行业数据与研报": 1,
  "AI 生成分析报告": 2,
};

/** Extract readable text from a JSON string, trying multiple parsing approaches. */
function tryExtractFromJson(raw: string): string {
  const tryParse = (s: string) => {
    try { return JSON.parse(s); } catch { return null; }
  };

  // Try 1: Standard parse
  let obj = tryParse(raw);

  // Try 2: Fix literal newlines inside string values
  if (!obj) {
    const cleaned = raw.replace(/:\s*"((?:[^"\\]|\\.)*?)"/gs, (m) =>
      m.replace(/\n/g, "\\n").replace(/\r/g, "\\r")
    );
    obj = tryParse(cleaned);
  }

  // Try 3: Extract JSON portion from surrounding text
  if (!obj) {
    const start = raw.indexOf("{");
    const end = raw.lastIndexOf("}");
    if (start !== -1 && end > start) {
      const portion = raw.slice(start, end + 1);
      obj = tryParse(portion);
      if (!obj) {
        const cleaned = portion.replace(/:\s*"((?:[^"\\]|\\.)*?)"/gs, (m) =>
          m.replace(/\n/g, "\\n").replace(/\r/g, "\\r")
        );
        obj = tryParse(cleaned);
      }
    }
  }

  if (obj && typeof obj === "object") {
    return extractBestString(obj);
  }
  return raw;
}

/** Recursively extract the best readable string from a parsed JSON value. */
function extractBestString(obj: unknown, depth = 0): string {
  if (depth > 5) return "";
  if (typeof obj === "string" && obj.length > 10) return obj;
  if (Array.isArray(obj)) {
    for (const item of obj) {
      const r = extractBestString(item, depth + 1);
      if (r) return r;
    }
    return obj.filter(v => typeof v === "string" && v.length > 4).join("\n\n").slice(0, 50000);
  }
  if (obj && typeof obj === "object") {
    const entries = obj as Record<string, unknown>;
    // Priority keys
    for (const key of ["llm_report", "content", "text", "review", "llm_review", "markdown", "summary", "analysis", "report"]) {
      if (typeof entries[key] === "string" && entries[key].length > 10) return entries[key];
    }
    // Fallback: collect all string values
    const parts: string[] = [];
    const collect = (v: unknown, d: number) => {
      if (d > 10) return;
      if (typeof v === "string" && v.length > 4) parts.push(v);
      else if (Array.isArray(v)) v.forEach(item => collect(item, d + 1));
      else if (v && typeof v === "object") Object.values(v as Record<string, unknown>).forEach(item => collect(item, d + 1));
    };
    collect(obj, 0);
    if (parts.length > 0) return parts.join("\n\n").slice(0, 50000);
  }
  return "";
}

function MarkdownReport({ content }: { content: string }) {
  const c = useColors();

  let text = content?.trim() || "";

  // If content looks like JSON, try to extract readable text
  if (text.startsWith("{") || text.startsWith("[")) {
    text = tryExtractFromJson(text);
  }

  // 去除 markdown 代码块包裹
  const codeBlockMatch = text.match(/^```(?:markdown|md)?\s*([\s\S]*?)```$/);
  if (codeBlockMatch) text = codeBlockMatch[1].trim();

  // 提取代码块，用占位符替换，markdown→HTML 转换完成后还原为格式化 <pre><code>
  const codeBlocks: { lang: string; pretty: string }[] = [];
  text = text.replace(/```(\w*)\s*\n?([\s\S]*?)```/g, (_match, lang, code) => {
    const idx = codeBlocks.length;
    let display = code.trim();
    if (lang === "json") {
      try { display = JSON.stringify(JSON.parse(display), null, 2); } catch { /* keep raw */ }
    }
    codeBlocks.push({ lang: lang || "", pretty: display });
    return `\x00CB${idx}\x00`;
  });

  const tp = c.textPrimary;
  const ts = c.textSecondary;
  const border = c.border;

  const bg = c.elevatedBg;
  let html = text
    .replace(/^### (.+)$/gm, `<h3 style="color:${tp};margin:20px 0 8px;font-size:15px;">$1</h3>`)
    .replace(/^## (.+)$/gm, `<h2 style="color:${tp};margin:24px 0 10px;font-size:17px;border-bottom:1px solid ${border};padding-bottom:6px;">$1</h2>`)
    .replace(/^# (.+)$/gm, `<h1 style="color:${tp};margin:0 0 16px;font-size:20px;">$1</h1>`)
    .replace(/\*\*(.+?)\*\*/g, `<strong style="color:${tp}">$1</strong>`)
    .replace(/^- (.+)$/gm, `<li style="color:${ts};margin:4px 0;line-height:1.7;">$1</li>`)
    .replace(/(<li[^>]*>.*<\/li>\n?)+/gs, (match) => `<ul style="padding-left:20px;margin:8px 0;">${match}</ul>`)
    .replace(/\n\n/g, "<br/>")
    .replace(/\n/g, "<br/>");

  // 还原代码块为格式化 <pre><code>（\x00 为占位符分隔，故意使用控制字符）
  // eslint-disable-next-line no-control-regex
  html = html.replace(/\x00CB(\d+)\x00/g, (_match, idx) => {
    const b = codeBlocks[parseInt(idx, 10)];
    if (!b) return _match;
    const escaped = b.pretty.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    return `<pre style="background:${bg};border:1px solid ${border};border-radius:6px;padding:12px 16px;overflow-x:auto;font-size:12px;line-height:1.6;margin:12px 0;"><code style="color:${ts};font-family:monospace;white-space:pre;">${escaped}</code></pre>`;
  });

  return (
    <div
      style={{ color: ts, fontSize: 14, lineHeight: 1.8 }}
      dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(html, { ADD_TAGS: ["pre", "code"], ADD_ATTR: ["style"] }) }}
    />
  );
}

export default function IndustryChain() {
  const c = useColors();
  const { pageContainerStyle, pageHeaderStyle, pageTitleStyle, pageDescriptionStyle, cardStyle } = useStyles();
  const { name: urlName } = useParams();
  const navigate = useNavigate();
  const [inputValue, setInputValue] = useState(urlName ? decodeURIComponent(urlName) : "");
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [currentStage, setCurrentStage] = useState(-1);
  const [stageMessage, setStageMessage] = useState("");
  const [result, setResult] = useState<IndustryChainResult | null>(null);
  const [archiveId, setArchiveId] = useState<string>("");
  const [error, setError] = useState("");
  const [historyFilter, setHistoryFilter] = useState("");
 const [pushResult, setPushResult] = useState<{ url?: string; message?: string; target?: string } | null>(null);
  const [expandedChart, setExpandedChart] = useState<{ chart: IndustryChainChart; idx: number } | null>(null);
  const cancelStreamRef = useRef<(() => void) | null>(null);

  const activeName = urlName ? decodeURIComponent(urlName) : "";

  // 组件卸载时关闭未结束的 SSE 连接，避免连接泄漏
  useEffect(() => {
    return () => {
      cancelStreamRef.current?.();
      cancelStreamRef.current = null;
    };
  }, []);

  const { data: config } = useConfig();
  const pushMutation = usePush();
  const { data: history = [], refetch: refetchHistory } = useIndustryChainHistory(historyFilter);
  const archiveMutation = useIndustryChainArchive();
  const { data: latest, refetch: refetchLatest } = useIndustryChainLatest(activeName);

  useEffect(() => {
    if (activeName) setHistoryFilter(activeName);
  }, [activeName]);

  useEffect(() => {
    if (latest?.archive_id && !archiveId && result) {
      setArchiveId(latest.archive_id);
    }
  }, [latest, archiveId, result]);

  const handleAnalyze = useCallback((value: string) => {
    const name = value.trim();
    if (!name) return;

    navigate(`/industry-chain/${encodeURIComponent(name)}`, { replace: true });
    // 重新发起分析前先取消上一次的 SSE 连接
    cancelStreamRef.current?.();
    setIsAnalyzing(true);
    setCurrentStage(-1);
    setStageMessage("");
    setResult(null);
    setArchiveId("");
    setError("");
    setPushResult(null);

    const { promise, cancel } = streamIndustryChain(name, (event: IndustryChainProgress) => {
      if (event.type === "stage_started" && event.stage) {
        const idx = STAGE_MAP[event.stage] ?? 0;
        setCurrentStage(idx);
        setStageMessage(event.message || "");
      } else if (event.type === "stage_completed" && event.stage) {
        setStageMessage(event.message || "完成");
      } else if (event.type === "complete" && event.result) {
        // 后端存档 ID 暴露在 result 上不必要；前端在下一次拉取历史时刷新
        refetchHistory();
      }
    });
    cancelStreamRef.current = cancel;

    promise
      .then((data) => {
        setResult(data);
        setCurrentStage(3);
        setIsAnalyzing(false);
        refetchHistory();
        refetchLatest();
      })
      .catch((err) => {
        setError(err.message || "分析失败");
        setIsAnalyzing(false);
        message.error(err.message || "分析失败");
      })
      .finally(() => {
        cancelStreamRef.current = null;
      });
  }, [navigate, refetchHistory, refetchLatest]);

  const handleLoadArchive = useCallback(async (item: IndustryChainHistoryItem) => {
    try {
      const data = await archiveMutation.mutateAsync({ name: item.name, archiveId: item.archive_id });
      setResult(data);
      setArchiveId(item.archive_id);
      setError("");
      setPushResult(null);
      navigate(`/industry-chain/${encodeURIComponent(item.name)}`, { replace: true });
    } catch (err) {
      const detail = err instanceof Error ? err.message : "加载历史存档失败";
      message.error(detail);
    }
  }, [archiveMutation, navigate]);

  const handlePush = useCallback(async (target: "feishu" | "notion") => {
    if (!result || !activeName) {
      message.warning("请先完成一次产业链分析");
      return;
    }
    if (!archiveId) {
      message.warning("当前报告未关联存档，无法推送");
      return;
    }
    try {
      const res = await pushMutation.mutateAsync({
        target,
        type: "industry_chain",
        industry_name: activeName,
        archive_id: archiveId,
      });
      setPushResult({ url: res.url, message: res.message, target });
      message.success(res.message || `已推送到 ${target}`);
    } catch (err) {
      const e = err as { response?: { data?: { detail?: string } }; message?: string };
      const detail = e?.response?.data?.detail || e?.message || "推送失败";
      message.error(detail);
    }
  }, [result, activeName, archiveId, pushMutation]);

  return (
    <div style={pageContainerStyle}>
      <div style={pageHeaderStyle}>
        <Title level={3} style={pageTitleStyle}>
          <ApartmentOutlined style={{ marginRight: 8 }} />
          产业链分析
        </Title>
        <Paragraph style={pageDescriptionStyle}>
          输入产业关键词，AI 自动搜索数据并生成完整产业链分析报告
        </Paragraph>
      </div>

      {/* 输入区域 */}
      <div style={{ ...cardStyle, padding: "16px 20px", marginBottom: 20 }}>
        <Search
          placeholder="输入产业链名称，如：锂电池、AI芯片、光伏..."
          enterButton={
            <span>
              <SearchOutlined /> 开始分析
            </span>
          }
          size="large"
          loading={isAnalyzing}
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onSearch={handleAnalyze}
          disabled={isAnalyzing}
        />
      </div>

      {/* 进度条 */}
      {isAnalyzing && (
        <div style={{ ...cardStyle, padding: "20px 24px", marginBottom: 20 }}>
          <Steps
            current={currentStage}
            items={[
              { title: "数据采集", icon: currentStage === 0 ? <LoadingOutlined /> : currentStage > 0 ? <CheckCircleOutlined /> : undefined },
              { title: "数据整理", icon: currentStage === 1 ? <LoadingOutlined /> : currentStage > 1 ? <CheckCircleOutlined /> : undefined },
              { title: "AI 分析", icon: currentStage === 2 ? <LoadingOutlined /> : undefined },
            ]}
          />
          {stageMessage && (
            <div style={{ marginTop: 12, color: c.textSecondary, fontSize: 13 }}>
              <Spin size="small" style={{ marginRight: 8 }} />{stageMessage}
            </div>
          )}
        </div>
      )}

      {/* 错误状态 */}
      {error && !isAnalyzing && (
        <div style={{ ...cardStyle, padding: 40, textAlign: "center" }}>
          <CloseCircleOutlined style={{ fontSize: 40, color: c.up, marginBottom: 12 }} />
          <div style={{ color: c.up }}>{error}</div>
        </div>
      )}

      {/* 两栏布局：左报告 · 右历史（始终显示） */}
      <div style={{ display: "flex", gap: 16, alignItems: "flex-start" }}>
          {/* 左侧：报告区 */}
          <div style={{ flex: 1, minWidth: 0 }}>
            {result && (
              <>
                {/* 摘要卡片：上中下游 + 驱动风险 */}
                <div style={{ ...cardStyle, padding: "16px 20px", marginBottom: 16 }}>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8, gap: 12 }}>
                    <Text strong style={{ color: c.textPrimary, fontSize: 15 }}>
                      <ApartmentOutlined style={{ marginRight: 6 }} />
                      {result.name || activeName} 产业链
                    </Text>
                    <Popover
                      trigger="click"
                      placement="bottomRight"
                      content={(
                        <div style={{ width: 280 }}>
                          <Text style={{ color: c.textSecondary, fontSize: 12, display: "block", marginBottom: 8 }}>
                            飞书接收人 open_id
                          </Text>
                          <Input
                            size="small"
                            placeholder={config?.feishu_default_receiver || "ou_xxx..."}
                            defaultValue={config?.feishu_default_receiver || ""}
                            id="feishu-receiver-input"
                            style={{ marginBottom: 12 }}
                          />
                          <Button
                            type="primary"
                            icon={<SendOutlined />}
                            size="small"
                            block
                            loading={pushMutation.isPending}
                            disabled={!result || !archiveId}
                            onClick={() => handlePush("feishu")}
                            style={{ marginBottom: 8 }}
                          >
                            推送到飞书
                          </Button>
                          <Button
                            icon={<SendOutlined />}
                            size="small"
                            block
                            loading={pushMutation.isPending}
                            disabled={!result || !archiveId}
                            onClick={() => handlePush("notion")}
                          >
                            推送到 Notion
                          </Button>
                          {!archiveId && result && (
                            <div style={{ color: c.textSecondary, fontSize: 12, marginTop: 8 }}>
                              提示：从右侧历史打开的报告可直接推送。
                            </div>
                          )}
                          {pushResult && (
                            <div style={{ marginTop: 12, padding: 10, background: `${c.down}1a`, borderRadius: 6 }}>
                              <div style={{ color: c.down, fontSize: 12, marginBottom: 4 }}>
                                ✓ 已推送到 {pushResult.target === "feishu" ? "飞书" : "Notion"}
                              </div>
                              {pushResult.url && (
                                <a href={pushResult.url} target="_blank" rel="noreferrer" style={{ color: c.primary, fontSize: 12, wordBreak: "break-all" }}>
                                  {pushResult.url}
                                </a>
                              )}
                              {pushResult.message && (
                                <div style={{ color: c.textSecondary, fontSize: 11, marginTop: 4 }}>
                                  {pushResult.message}
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      )}
                    >
                      <Button
                        type="primary"
                        icon={<CloudUploadOutlined />}
                        size="small"
                        loading={pushMutation.isPending}
                        disabled={!result || !archiveId}
                      >
                        推送
                      </Button>
                    </Popover>
                  </div>
                  {result.summary && (
                    <Paragraph style={{ color: c.textSecondary, fontSize: 13, marginBottom: 12 }}>
                      {result.summary}
                    </Paragraph>
                  )}
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 12 }}>
                    {result.drivers.length > 0 && (
                      <div>
                        <Text style={{ color: c.textSecondary, fontSize: 12, fontWeight: 600 }}>驱动因素</Text>
                        <ul style={{ margin: "6px 0 0", paddingLeft: 16 }}>
                          {result.drivers.map((d, i) => (
                            <li key={i}><Text style={{ color: c.textSecondary, fontSize: 13 }}>{d}</Text></li>
                          ))}
                        </ul>
                      </div>
                    )}
                    {result.risks.length > 0 && (
                      <div>
                        <Text style={{ color: c.textSecondary, fontSize: 12, fontWeight: 600 }}>风险提示</Text>
                        <ul style={{ margin: "6px 0 0", paddingLeft: 16 }}>
                          {result.risks.map((r, i) => (
                            <li key={i}><Text style={{ color: c.accent, fontSize: 13 }}>{r}</Text></li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                  {result.key_stocks.length > 0 && (
                    <div style={{ marginTop: 10 }}>
                      <Text style={{ color: c.textSecondary, fontSize: 12, fontWeight: 600 }}>重点关注 </Text>
                      <div style={{ marginTop: 6, display: "flex", flexWrap: "wrap", gap: 6 }}>
                        {result.key_stocks.map((s, i) => (
                          <Tag key={i} color="blue" style={{ margin: 0 }}>{String(s.name || s.code || "")}</Tag>
                        ))}
                      </div>
                    </div>
                  )}
                  {(result.upstream?.length > 0 || result.midstream?.length > 0 || result.downstream?.length > 0) && (
                    <div style={{ marginTop: 16, display: "flex", flexDirection: "column", gap: 10 }}>
                      {result.upstream?.length > 0 && (
                        <div>
                          <Text style={{ color: c.textSecondary, fontSize: 12, fontWeight: 600 }}>上游 </Text>
                          <div style={{ marginTop: 4, display: "flex", flexWrap: "wrap", gap: 4 }}>
                            {result.upstream.map((item, i) => (
                              <Tag key={i} style={{ margin: 0, fontSize: 11 }} color="orange">{String(item.name || item.company || item.code || "")}</Tag>
                            ))}
                          </div>
                        </div>
                      )}
                      {result.midstream?.length > 0 && (
                        <div>
                          <Text style={{ color: c.textSecondary, fontSize: 12, fontWeight: 600 }}>中游 </Text>
                          <div style={{ marginTop: 4, display: "flex", flexWrap: "wrap", gap: 4 }}>
                            {result.midstream.map((item, i) => (
                              <Tag key={i} style={{ margin: 0, fontSize: 11 }} color="blue">{String(item.name || item.company || item.code || "")}</Tag>
                            ))}
                          </div>
                        </div>
                      )}
                      {result.downstream?.length > 0 && (
                        <div>
                          <Text style={{ color: c.textSecondary, fontSize: 12, fontWeight: 600 }}>下游 </Text>
                          <div style={{ marginTop: 4, display: "flex", flexWrap: "wrap", gap: 4 }}>
                            {result.downstream.map((item, i) => (
                              <Tag key={i} style={{ margin: 0, fontSize: 11 }} color="green">{String(item.name || item.company || item.code || "")}</Tag>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>

                {result.charts && result.charts.length > 0 && (
                  <div style={{ marginBottom: 16 }}>
                    {result.charts.map((chart, idx) => {
                      const chartHeight = chart.type === "tree" ? Math.min(900, Math.max(400, Math.round(window.innerHeight * 0.55))) : Math.min(550, Math.max(300, Math.round(window.innerHeight * 0.4)));
                      const hasValidOption = Boolean(chart.option && typeof chart.option === "object");
                      return (
                        <div key={idx} style={{ ...cardStyle, padding: "16px 20px", marginBottom: 16 }}>
                          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                            <Text strong style={{ color: c.textPrimary, fontSize: 14 }}>
                              {chart.title}
                            </Text>
                            {hasValidOption && (
                              <Button
                                type="text"
                                size="small"
                                icon={<FullscreenOutlined />}
                                onClick={() => setExpandedChart({ chart, idx })}
                                style={{ color: c.textMuted }}
                              />
                            )}
                          </div>
                          {chart.description && (
                            <Text style={{ color: c.textSecondary, fontSize: 13, marginBottom: 12, display: "block", lineHeight: 1.6 }}>
                              {chart.description}
                            </Text>
                          )}
                          {hasValidOption ? (
                            <div style={{ width: "100%", overflow: "auto" }}><ReactECharts echarts={echarts} option={chart.option} style={{ height: chartHeight, width: "100%" }} notMerge /></div>
                          ) : (
                            <div style={{ height: chartHeight, display: "flex", alignItems: "center", justifyContent: "center", color: c.textMuted, fontSize: 13 }}>
                              图表配置不可用
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}

                <div style={{ ...cardStyle, padding: "20px 24px" }}>
                  <MarkdownReport content={result.llm_review} />
                </div>
              </>
            )}
            {/* 空状态 */}
            {!result && !isAnalyzing && !error && (
              <div style={{ ...cardStyle, padding: 60, textAlign: "center" }}>
                <ApartmentOutlined style={{ fontSize: 48, color: c.textMuted, marginBottom: 16 }} />
                <div style={{ color: c.textMuted, fontSize: 14 }}>
                  输入产业关键词，开始 AI 产业链分析
                </div>
              </div>
            )}
          </div>

          {/* 右侧：历史记录 */}
          <div style={{ width: 280, flexShrink: 0 }}>
            <div style={{ ...cardStyle, padding: 0, position: "sticky", top: 24 }}>
              <div style={{ padding: "14px 16px", borderBottom: `1px solid ${c.border}` }}>
                <Text strong style={{ color: c.textPrimary, fontSize: 14 }}>
                  <HistoryOutlined style={{ marginRight: 6 }} />
                  历史记录
                </Text>
              </div>

              <div style={{ padding: "10px 12px", borderBottom: `1px solid ${c.border}` }}>
                <Input
                  size="small"
                  placeholder="按名称过滤"
                  value={historyFilter}
                  onChange={(e) => setHistoryFilter(e.target.value)}
                  allowClear
                />
              </div>

              <div style={{ maxHeight: "calc(100vh - 220px)", overflowY: "auto" }}>
                {history.length === 0 ? (
                  <div style={{ padding: 24 }}>
                    <Empty
                      image={Empty.PRESENTED_IMAGE_SIMPLE}
                      description={<span style={{ color: c.textMuted, fontSize: 12 }}>暂无历史记录</span>}
                    />
                  </div>
                ) : (
                  history.map((item) => {
                    const isActive = item.name === activeName && item.archive_id === archiveId;
                    return (
                      <Tooltip key={`${item.name}-${item.archive_id}`} title={item.summary || item.title} placement="left">
                        <div
                          onClick={() => handleLoadArchive(item)}
                          className={isActive ? undefined : "hover-mutedrow"}
                          style={{
                            padding: "10px 12px",
                            borderBottom: `1px solid ${c.border}`,
                            cursor: "pointer",
                            background: isActive ? `${c.primary}26` : undefined,
                            transition: "background 0.15s",
                          }}
                        >
                          <div style={{ color: c.textPrimary, fontSize: 13, fontWeight: 500, marginBottom: 4 }}>
                            {item.title || `${item.name} 产业链`}
                          </div>
                          <div style={{ color: c.textSecondary, fontSize: 11, display: "flex", justifyContent: "space-between" }}>
                            <span>{item.saved_at || item.archive_id}</span>
                            {isActive && <span style={{ color: c.primary }}>当前</span>}
                          </div>
                        </div>
                      </Tooltip>
                    );
                  })
                )}
              </div>
            </div>
          </div>
      </div>
      <Modal
        title={expandedChart?.chart?.title || ""}
        open={!!expandedChart}
        onCancel={() => setExpandedChart(null)}
        footer={null}
        width={Math.min(1200, Math.round(window.innerWidth * 0.92))}
        style={{ top: 20 }}
        destroyOnClose
      >
        {expandedChart && (
          <ReactECharts
            echarts={echarts}
            option={expandedChart.chart.option}
            style={{ height: expandedChart.chart.type === "tree" ? Math.min(1600, Math.round(window.innerHeight * 0.85)) : Math.min(800, Math.round(window.innerHeight * 0.7)), width: "100%" }}
            notMerge
          />
        )}
      </Modal>
    </div>
  );
}
