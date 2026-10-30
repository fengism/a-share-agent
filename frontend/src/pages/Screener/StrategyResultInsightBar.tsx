import React, { useMemo } from "react";
import { Button, Space, Tag } from "antd";
import { ThunderboltOutlined, ExperimentOutlined, CheckCircleOutlined } from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import ChangeValue from "../../components/ChangeValue";
import * as uiStyles from "../../styles/ui";

const DEFAULT_COLORS = {
  primary: "#1677ff",
  textPrimary: "rgba(0, 0, 0, 0.88)",
  textMuted: "rgba(0, 0, 0, 0.45)",
  up: "#f5222d",
  down: "#52c41a",
};

interface StrategyResultInsightBarProps {
  strategyName: string;
  matchedCodes: string[];
  evaluated: number;
  returnsSinceSignal: ReadonlyMap<string, number | null>;
  signalAges: ReadonlyMap<string, number>;
  onSelectAllMatched?: () => void;
  onBacktestAll?: () => void;
}

export const StrategyResultInsightBar: React.FC<StrategyResultInsightBarProps> = ({
  strategyName,
  matchedCodes,
  evaluated,
  returnsSinceSignal,
  signalAges,
  onSelectAllMatched,
  onBacktestAll,
}) => {
  const c = typeof uiStyles.useColors === "function" ? uiStyles.useColors() : DEFAULT_COLORS;
  const navigate = useNavigate();

  const stats = useMemo(() => {
    if (!matchedCodes || matchedCodes.length === 0) return null;

    const hitRate = evaluated > 0 ? (matchedCodes.length / evaluated) * 100 : 0;

    let winCount = 0;
    let validReturnCount = 0;
    let returnSum = 0;

    matchedCodes.forEach((code) => {
      const ret = returnsSinceSignal.get(code);
      if (ret != null) {
        validReturnCount += 1;
        returnSum += ret;
        if (ret > 0) winCount += 1;
      }
    });

    const winRate = validReturnCount > 0 ? (winCount / validReturnCount) * 100 : 0;
    const avgReturn = validReturnCount > 0 ? returnSum / validReturnCount : null;

    // 统计近期新出信号（年龄 <= 3 根）
    let freshSignalCount = 0;
    matchedCodes.forEach((code) => {
      const age = signalAges.get(code);
      if (age != null && age <= 3) freshSignalCount += 1;
    });

    return {
      hitRate,
      winRate,
      avgReturn,
      freshSignalCount,
      validReturnCount,
    };
  }, [evaluated, matchedCodes, returnsSinceSignal, signalAges]);

  if (!stats || matchedCodes.length === 0) return null;

  const handleAiReview = () => {
    const codesStr = matchedCodes.slice(0, 8).join("、");
    const prompt = `请对策略「${strategyName}」本次命中的标的池（前 8 只：${codesStr}）进行战术复盘：1. 信号触发的有效性与量价配合；2. 胜率与当前市场主线匹配度；3. 最具爆发潜力与需提防假突破的标的。`;
    navigate(`/chat?prompt=${encodeURIComponent(prompt)}`);
  };

  return (
    <div
      style={{
        marginBottom: 16,
        padding: "var(--c-pad-inset, 7px 12px)",
        background: "var(--c-fill-quaternary, rgba(82, 196, 26, 0.04))",
        border: "1px solid var(--c-border, #d9f7be)",
        borderRadius: 8,
        display: "flex",
        flexDirection: "column",
        gap: 8,
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: 8,
        }}
      >
        <Space size={16} wrap style={{ fontSize: 13, color: c.textMuted }}>
          <span>
            扫描命中: <strong style={{ color: c.textPrimary }}>{matchedCodes.length}</strong> / {evaluated} 只 ({stats.hitRate.toFixed(1)}%)
          </span>
          {stats.validReturnCount > 0 && (
            <>
              <span>
                信号胜率:{" "}
                <Tag color={stats.winRate >= 50 ? "success" : "default"} style={{ margin: 0, fontWeight: 600 }}>
                  {stats.winRate.toFixed(0)}%
                </Tag>
              </span>
              <span>
                平均收益:{" "}
                <strong style={{ fontWeight: 600 }}>
                  <ChangeValue value={stats.avgReturn} />
                </strong>
              </span>
            </>
          )}
          <span>
            近3日新信号: <strong style={{ color: c.primary }}>{stats.freshSignalCount}</strong> 只
          </span>
        </Space>

        <Space size={8} wrap>
          {onSelectAllMatched && (
            <Button size="small" icon={<CheckCircleOutlined />} onClick={onSelectAllMatched}>
              勾选前10只
            </Button>
          )}
          <Button size="small" type="primary" ghost icon={<ThunderboltOutlined />} onClick={handleAiReview}>
            AI 策略战术复盘
          </Button>
          {onBacktestAll && (
            <Button size="small" icon={<ExperimentOutlined />} onClick={onBacktestAll}>
              批量回测
            </Button>
          )}
        </Space>
      </div>
    </div>
  );
};

export default StrategyResultInsightBar;
