import { Alert, Space, Tag, Typography } from "antd";
import type { AnalysisPageData, AnalysisResult } from "../../types/stock";

const { Text } = Typography;

const SECTION_LABELS: Record<string, string> = {
  stock_info: "股票资料",
  kline: "K 线行情",
  intraday: "分时行情",
  valuation: "估值",
  cached_analysis: "历史分析",
};

interface AnalysisDataStatusProps {
  pageData?: AnalysisPageData;
  result?: AnalysisResult | null;
}

export default function AnalysisDataStatus({ pageData, result }: AnalysisDataStatusProps) {
  const unavailable = (pageData?.unavailable_sections ?? []).map((section) => SECTION_LABELS[section] ?? section);
  const adjustmentUnverified = pageData?.kline?.adjustment_verified === false;
  const sourceNames = Array.from(new Set([
    ...(pageData?.stock_info?.data_sources ?? []).map((source) => source.name),
    ...(pageData?.kline?.source ? [pageData.kline.source] : []),
  ]));
  const warnings = [
    ...(unavailable.length ? [`部分数据不可用：${unavailable.join("、")}`] : []),
    ...(adjustmentUnverified ? ["复权校验未通过"] : []),
  ];
  const trace = result?.prompt_trace;

  return (
    <Alert
      type={warnings.length ? "warning" : "info"}
      showIcon
      title={warnings.length ? warnings.join("；") : "分析数据状态正常"}
      description={(
        <Space size={[6, 6]} wrap>
          <Text type="secondary">数据来源</Text>
          {sourceNames.length
            ? sourceNames.map((source) => <Tag key={source}>{source}</Tag>)
            : <Tag>来源未标注</Tag>}
          {trace?.model ? <Text type="secondary">模型 {trace.model}</Text> : null}
          {trace?.generated_at ? <Text type="secondary">生成于 {trace.generated_at}</Text> : null}
        </Space>
      )}
      style={{ marginBottom: 16 }}
    />
  );
}
