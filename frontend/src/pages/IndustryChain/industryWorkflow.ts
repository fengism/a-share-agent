export const INDUSTRY_CHAIN_STAGES = [
  { code: "research", title: "数据采集与 Agent 调研" },
  { code: "draft", title: "结构化初稿" },
  { code: "verification", title: "引用校验与定向补证" },
  { code: "finalize", title: "图表与质量检查" },
  { code: "archive", title: "存档与历史更新" },
] as const;

export function industryStageIndex(stageCode: string): number {
  return INDUSTRY_CHAIN_STAGES.findIndex((stage) => stage.code === stageCode);
}
