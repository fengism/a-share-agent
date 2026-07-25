import { Steps } from "antd";
import {
  CloudDownloadOutlined,
  LineChartOutlined,
  FormOutlined,
  RobotOutlined,
} from "@ant-design/icons";
import type { AnalysisStage } from "../../api/sse";
import { useColors } from "../../theme/hooks";

interface Props {
  stages: AnalysisStage[];
  currentStageIndex: number;
}

const STAGE_ICONS = [
  <CloudDownloadOutlined key="1" />,
  <LineChartOutlined key="2" />,
  <FormOutlined key="3" />,
  <RobotOutlined key="4" />,
];

export default function AnalysisProgressSteps({ stages, currentStageIndex }: Props) {
  const c = useColors();

  const items = STAGE_ICONS.map((icon, i) => {
    const stage = stages[i];
    const status =
      !stage || stage.status === "started"
        ? ("process" as const)
        : stage.status === "completed"
          ? ("finish" as const)
          : stage.status === "failed"
            ? ("error" as const)
            : ("wait" as const);

    const description =
      stage?.detail ||
      (stage?.status === "completed" && stage.duration_ms
        ? `${stage.duration_ms}ms`
        : undefined);

    return {
      title: stage?.name || `Stage ${i + 1}`,
      status,
      icon,
      description,
    };
  });

  return (
    <div
      style={{
        padding: "16px 18px",
        borderRadius: 10,
        background: c.elevatedBg,
        border: `1px solid ${c.border}`,
      }}
    >
      <Steps
        current={currentStageIndex}
        items={items}
        size="small"
        style={{ padding: "4px 0" }}
      />
    </div>
  );
}
