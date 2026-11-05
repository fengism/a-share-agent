import type { DailyReviewPayload, ReviewHeadline } from "./reviewView";

export interface Sentiment5Factors {
  breadth: number;    // 上涨广度 (0-100)
  momentum: number;   // 动量积聚 (0-100)
  turnover: number;   // 资金量能 (0-100)
  stability: number;  // 结构稳定 (0-100)
  cycle: number;      // 周期定位 (0-100)
}

export type SentimentZoneCode = "ICE_COLD" | "COLD" | "NEUTRAL" | "HOT" | "OVERHEAT";

export interface SentimentAnalysis {
  temperature: number;
  zoneCode: SentimentZoneCode;
  zoneLabel: string;
  zoneIcon: string;
  tactics: string;
  color: string;
  factors: Sentiment5Factors;
}

function clamp(value: number, min = 0, max = 100): number {
  return Math.min(max, Math.max(min, value));
}

export function analyzeSentiment(review: DailyReviewPayload, headline: ReviewHeadline): SentimentAnalysis {
  const snapshot = review.data_snapshot ?? ({} as DailyReviewPayload["data_snapshot"]);
  // 1. 上涨广度 (Breadth)
  const emotion = snapshot?.market_emotion;
  let breadth = 50;
  const upCount = Number(emotion?.up_count ?? emotion?.rise_count);
  const downCount = Number(emotion?.down_count ?? emotion?.fall_count);
  if (Number.isFinite(upCount) && Number.isFinite(downCount) && upCount + downCount > 0) {
    breadth = clamp(Math.round((upCount / (upCount + downCount)) * 100));
  } else {
    const indices = snapshot?.indices ?? [];
    if (indices.length > 0) {
      const positiveCount = indices.filter((item) => Number(item.change_pct ?? 0) > 0).length;
      breadth = clamp(Math.round((positiveCount / indices.length) * 100));
    } else if (headline.indexChangePct !== null) {
      breadth = clamp(Math.round(50 + headline.indexChangePct * 15));
    }
  }

  // 2. 动量积聚 (Momentum)
  const indexPct = headline.indexChangePct ?? 0;
  const momentum = clamp(Math.round(50 + indexPct * 20));

  // 3. 资金量能 (Turnover)
  const volume = snapshot?.market_volume;
  const stats = snapshot?.market_statistics;
  const rawTurnover = Number(
    volume?.total_turnover ??
    volume?.amount ??
    stats?.total_turnover ??
    stats?.turnover
  );
  let turnover = 50;
  if (Number.isFinite(rawTurnover) && rawTurnover > 0) {
    // 若在 2万亿(>=20000亿或>=2e12)左右
    const norm = rawTurnover >= 1e11 ? rawTurnover / 1e8 : rawTurnover; // 统一为亿元
    if (norm >= 20000) turnover = 92;
    else if (norm >= 15000) turnover = 80;
    else if (norm >= 10000) turnover = 60;
    else if (norm >= 8000) turnover = 45;
    else turnover = 30;
  }

  // 4. 结构稳定度 (Stability) - 炸板率越低越稳定
  const breakRate = headline.breakRate;
  let stability = 50;
  if (breakRate !== null && Number.isFinite(breakRate)) {
    // 炸板率 10% -> 85分，20% -> 70分，40% -> 40分
    stability = clamp(Math.round(100 - breakRate * 1.5));
  }

  // 5. 周期定位 (Cycle)
  const stage = headline.stage || "";
  let cycle = 50;
  if (stage.includes("主升") || stage.includes("高潮")) cycle = 85;
  else if (stage.includes("修复") || stage.includes("反弹")) cycle = 65;
  else if (stage.includes("启动") || stage.includes("企稳")) cycle = 55;
  else if (stage.includes("分歧") || stage.includes("震荡")) cycle = 48;
  else if (stage.includes("退潮") || stage.includes("冰点")) cycle = 25;

  // 综合温度 (0-100)
  let computedTemp = Math.round(
    breadth * 0.25 +
    momentum * 0.25 +
    turnover * 0.20 +
    stability * 0.15 +
    cycle * 0.15
  );

  // 如果后端财联社情绪温度存在，进行加权融合
  const backendDegree = Number(emotion?.degree ?? emotion?.temperature);
  if (Number.isFinite(backendDegree) && backendDegree >= 0 && backendDegree <= 100) {
    computedTemp = Math.round(backendDegree * 0.4 + computedTemp * 0.6);
  }

  const temperature = clamp(computedTemp);

  // 划分区间与战术
  let zoneCode: SentimentZoneCode = "NEUTRAL";
  let zoneLabel = "中性震荡区";
  let zoneIcon = "☁️";
  let tactics = "轻指数重结构，聚焦优势主线与个股轮动";
  let color = "#f59e0b";

  if (temperature <= 20) {
    zoneCode = "ICE_COLD";
    zoneLabel = "冰点极寒区";
    zoneIcon = "🥶";
    tactics = "切忌恐慌杀跌，关注左侧超跌与企稳修复信号";
    color = "#38bdf8";
  } else if (temperature <= 40) {
    zoneCode = "COLD";
    zoneLabel = "偏冷探底区";
    zoneIcon = "❄️";
    tactics = "控制仓位防守为主，等待放量企稳与主线确立";
    color = "#60a5fa";
  } else if (temperature <= 65) {
    zoneCode = "NEUTRAL";
    zoneLabel = "中性震荡区";
    zoneIcon = "☁️";
    tactics = "轻指数重结构，聚焦优势主线与个股轮动";
    color = "#f59e0b";
  } else if (temperature <= 85) {
    zoneCode = "HOT";
    zoneLabel = "偏热活跃区";
    zoneIcon = "🔥";
    tactics = "顺势持筹做多，关注高位分歧与均线支撑";
    color = "#ef4444";
  } else {
    zoneCode = "OVERHEAT";
    zoneLabel = "极度亢奋区";
    zoneIcon = "🌋";
    tactics = "严禁追高盲目亢奋，分批止盈防冲高回落";
    color = "#dc2626";
  }

  return {
    temperature,
    zoneCode,
    zoneLabel,
    zoneIcon,
    tactics,
    color,
    factors: {
      breadth,
      momentum,
      turnover,
      stability,
      cycle,
    },
  };
}
