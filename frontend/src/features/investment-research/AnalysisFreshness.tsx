import { Alert, Collapse, Descriptions, Tag, Typography } from "antd";
import type { AnalysisResult } from "../../types/stock";
import { toolDisplayName } from "../agent-process/toolPresentation";

const CACHE_LABELS: Record<string, string> = {
  cached: "来源标记为缓存", live: "来源标记为非缓存", stale: "来源标记为旧数据", mixed: "混合缓存状态", unknown: "缓存状态未披露",
};

export default function AnalysisFreshness({ analysis }: { analysis: Pick<AnalysisResult, "generated_at" | "report_id" | "provenance"> }) {
  const data = analysis.provenance;
  return (
    <div data-pdf-section style={{ marginBottom: 16 }}>
      <Descriptions size="small" column={1}>
        <Descriptions.Item label="报告生成时间">{analysis.generated_at || "旧报告未记录"}</Descriptions.Item>
        {analysis.report_id && <Descriptions.Item label="报告版本">{analysis.report_id}</Descriptions.Item>}
      </Descriptions>
      <Alert type="info" showIcon title="数据时效与缓存说明"
        description={data?.freshness_note || "旧报告未记录数据时效与缓存来源；分析日期不代表全部数据截至日期。"} />
      {data && <>
        <Typography.Paragraph type="secondary" style={{ marginTop: 8 }}>
          调研时间：{data.research_started_at} — {data.research_completed_at}。调研时间不等于行情日期、财报报告期或资料发布日期。
        </Typography.Paragraph>
        <Collapse className="pdf-hide" items={[{ key: "sources", label: `查看 ${data.evidence.length} 项证据的日期与来源`, children: (
          <div style={{ display: "grid", gap: 12 }}>{data.evidence.map((item) => (
            <div key={item.evidence_id} style={{ paddingBlock: 8, borderBottom: "1px solid var(--c-border)" }}>
                <Typography.Text strong>{toolDisplayName(item.tool_name)}</Typography.Text>{" "}
                <Tag>{CACHE_LABELS[item.cache_status] || CACHE_LABELS.unknown}</Tag>
                <div>数据/来源日期：{item.data_dates.join("；") || "未披露"}</div>
                <div>报告期：{item.report_periods.join("；") || "未披露"}</div>
                <div style={{ overflowWrap: "anywhere" }}>来源：{item.sources.join("；") || "未披露"}</div>
            </div>
          ))}</div>
        ) }]} />
      </>}
    </div>
  );
}
