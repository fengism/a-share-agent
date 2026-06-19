import { Space, Segmented, Typography, Button } from "antd";
import { DownloadOutlined, ThunderboltOutlined } from "@ant-design/icons";
import { useColors, useStyles } from "../../theme/hooks";
import { formatMarketCap } from "../../utils/format";
import type { StockBasicInfo } from "../../types/stock";

const { Title, Text } = Typography;

interface AnalysisHeaderProps {
  info: StockBasicInfo | null | undefined;
  isLoading: boolean;
  latestPrice: number | null;
  latestChangePct: number | null;
  period: string;
  adjust: string;
  onPeriodChange: (val: string) => void;
  onAdjustChange: (val: string) => void;
  isAnalyzing: boolean;
  onStartAnalysis: () => void;
  onExportPdf: () => void;
  isExportingPdf: boolean;
}

export default function AnalysisHeader({
  info, isLoading, latestPrice, latestChangePct,
  period, adjust, onPeriodChange, onAdjustChange,
  isAnalyzing, onStartAnalysis, onExportPdf, isExportingPdf,
}: AnalysisHeaderProps) {
  const c = useColors();
  const { gradientHeaderStyle } = useStyles();

  const changeColor = latestChangePct != null
    ? (latestChangePct >= 0 ? "#e74c3c" : "#27ae60")
    : c.textSecondary;

  return (
    <div style={{ ...gradientHeaderStyle, padding: "16px 24px", borderRadius: 12, marginBottom: 16 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 12 }}>
        <div>
          <Space align="baseline" size={12}>
            <Title level={2} style={{ margin: 0, color: c.text }}>
              {isLoading ? "加载中..." : (info?.name || info?.code || "未知")}
            </Title>
            {info?.code && <Text style={{ color: c.textSecondary, fontSize: 14 }}>{info.code}</Text>}
          </Space>
          {latestPrice != null && (
            <div style={{ marginTop: 4 }}>
              <Text style={{ fontSize: 24, fontWeight: 600, color: changeColor }}>
                {latestPrice.toFixed(2)}
              </Text>
              <Text style={{ marginLeft: 8, fontSize: 14, color: changeColor }}>
                {latestChangePct != null ? `${latestChangePct >= 0 ? "+" : ""}${latestChangePct.toFixed(2)}%` : ""}
              </Text>
            </div>
          )}
          {info?.market_cap != null && (
            <div style={{ marginTop: 4 }}>
              <Text style={{ color: c.textSecondary, fontSize: 12 }}>总市值: {formatMarketCap(info.market_cap)}</Text>
            </div>
          )}
        </div>

        <Space wrap>
          <Segmented
            value={period}
            onChange={(v) => onPeriodChange(v as string)}
            options={[
              { label: "日K", value: "daily" },
              { label: "周K", value: "weekly" },
              { label: "月K", value: "monthly" },
            ]}
            style={{ background: c.surface }}
          />
          <Segmented
            value={adjust}
            onChange={(v) => onAdjustChange(v as string)}
            options={[
              { label: "前复权", value: "qfq" },
              { label: "后复权", value: "hfq" },
              { label: "不复权", value: "" },
            ]}
            style={{ background: c.surface }}
          />
          <Button
            type="primary"
            icon={<ThunderboltOutlined />}
            onClick={onStartAnalysis}
            loading={isAnalyzing}
          >
            {isAnalyzing ? "分析中..." : "AI 分析"}
          </Button>
          <Button
            icon={<DownloadOutlined />}
            onClick={onExportPdf}
            loading={isExportingPdf}
          >
            导出 PDF
          </Button>
        </Space>
      </div>
    </div>
  );
}
