export const INDUSTRY_CHAIN_STAGES = [
  { code: "research", title: "数据采集与证据校验" },
  { code: "synthesis", title: "AI 生成分析报告" },
] as const;

export function industryStageIndex(stageCode: string): number {
  return INDUSTRY_CHAIN_STAGES.findIndex((stage) => stage.code === stageCode);
}
