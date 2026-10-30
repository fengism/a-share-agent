import {
  ExperimentOutlined,
  EyeOutlined,
  RobotOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";
import { Button, Space, Tag, Typography } from "antd";
import { semanticTagStyle } from "../../styles/ui";

const { Text } = Typography;

interface ScreenerBatchActionsProps {
  selectedCodes: string[];
  isAddingWatchlist: boolean;
  isAnalyzing: boolean;
  analysisProgress: string;
  onAddWatchlist: () => void;
  onAnalyze: () => void;
  onBacktest: () => void;
  onClear: () => void;
  onAiDiagnose?: () => void;
}

export default function ScreenerBatchActions({
  selectedCodes,
  isAddingWatchlist,
  isAnalyzing,
  analysisProgress,
  onAddWatchlist,
  onAnalyze,
  onBacktest,
  onClear,
  onAiDiagnose,
}: ScreenerBatchActionsProps) {
  const count = selectedCodes.length;
  if (count === 0) return null;

  return (
    <Space size={[8, 8]} wrap style={{ marginBottom: 12 }}>
      <Tag style={semanticTagStyle("primary")}>已选 {count} 只</Tag>
      <Button
        size="small"
        icon={<EyeOutlined />}
        loading={isAddingWatchlist}
        onClick={onAddWatchlist}
      >
        加入自选
      </Button>
      {onAiDiagnose ? (
        <Button
          size="small"
          type="primary"
          ghost
          icon={<ThunderboltOutlined />}
          disabled={count > 8}
          title={count > 8 ? "AI 诊断最多支持 8 只" : undefined}
          onClick={onAiDiagnose}
        >
          AI 诊断
        </Button>
      ) : null}
      <Button
        size="small"
        icon={<RobotOutlined />}
        loading={isAnalyzing}
        disabled={count > 5}
        title={count > 5 ? "批量分析最多支持 5 只" : undefined}
        onClick={onAnalyze}
      >
        批量分析
      </Button>
      <Button size="small" icon={<ExperimentOutlined />} onClick={onBacktest}>批量回测</Button>
      {analysisProgress ? <Text type="secondary">{analysisProgress}</Text> : null}
      <Button size="small" type="link" onClick={onClear}>清空选择</Button>
    </Space>
  );
}
