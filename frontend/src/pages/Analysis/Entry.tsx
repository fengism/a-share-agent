import { Card, Typography } from "antd";
import { FileSearchOutlined } from "@ant-design/icons";
import { Navigate, useSearchParams } from "react-router-dom";
import SearchBar from "../../features/stock-search/SearchBar";
import AnalysisHistoryManager from "../../features/investment-research/AnalysisHistoryManager";
import { buildAnalysisHistoryUrl } from "../../features/investment-research/analysisHistoryUrl";
import WorkflowPageHeader from "../../components/workflows/WorkflowPageHeader";
import WorkflowWorkspace from "../../components/workflows/WorkflowWorkspace";
import { useColors, useStyles, useTokens } from "../../styles/ui";
import { buildStockAnalysisUrl, buildStockProfileUrl } from "../../utils/stockLinks";

const { Paragraph } = Typography;

export default function AnalysisEntry() {
  const [searchParams] = useSearchParams();
  const codeParam = searchParams.get("code")?.trim();

  const colors = useColors();
  const t = useTokens();
  const { pageContainerStyle, cardStyle } = useStyles();

  if (codeParam) {
    return <Navigate to={buildStockAnalysisUrl(codeParam)} replace />;
  }

  return (
    <div style={pageContainerStyle}>
      <WorkflowPageHeader
        title="个股"
        description="查看行情、财务、估值与资讯等个股资料，支持进入 AI 独立分析"
        icon={<FileSearchOutlined />}
      />
      <WorkflowWorkspace
        historyTitle="研究历史"
        historyButtonLabel="研究历史"
        history={(
          <AnalysisHistoryManager buildHistoryUrl={buildAnalysisHistoryUrl} />
        )}
      >
        <div style={{ minHeight: "calc(100vh - 260px)", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: `${t.space[8]} ${t.space[6]}` }}>
          <div style={{ textAlign: "center", marginBottom: t.space[7] }}>
            <div style={{ fontSize: t.font.display, marginBottom: t.space[2] }}>
              <FileSearchOutlined style={{ color: colors.accent }} />
            </div>
            <Paragraph style={{ fontSize: t.font.lg, margin: 0, color: colors.textSecondary }}>
              选择一只股票，进入个股资料页
            </Paragraph>
          </div>
          <Card
            style={{ ...cardStyle, padding: `${t.space[2]} 0`, width: "100%", maxWidth: 560 }}
            styles={{ body: { padding: `${t.space[6]} ${t.space[6]} ${t.space[4]}`, display: "flex", justifyContent: "center" } }}
          >
            {/* 个股入口默认带用户去个股资料页（/stock/:code）；AI 分析（/analysis/:code）
                由分析历史等明确的研究入口进入，不作为选股后的默认落点。 */}
            <SearchBar buildTarget={buildStockProfileUrl} />
          </Card>
        </div>
      </WorkflowWorkspace>
    </div>
  );
}
