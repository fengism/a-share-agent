import rawData from "./defaultIntradayData.json";
import type { NationalTeamIntradayObservation } from "../../../types/stock";

interface RawDataShape {
  initData?: {
    preClose?: number;
    date?: string;
    times?: string[];
    bars?: number[];
    closes?: number[];
    table?: Array<{
      code?: string;
      name?: string;
      price?: number;
      pct?: number;
      amount?: number;
    }>;
  };
  cumData?: {
    slots?: string[];
    prevDate?: string;
    prev?: number[];
    avgDays?: number;
    avgFrom?: string;
    avgTo?: string;
    avg20?: number[];
    builtAt?: string;
  };
  typData?: {
    slots?: string[];
    supAmt?: number[];
    supCum?: number[];
    norAmt?: number[];
    norCum?: number[];
    supN?: number;
    norN?: number;
    range?: string | string[];
  };
  cmpData?: {
    support?: Array<{
      date?: string;
      amount?: number;
      netflow?: number | null;
    }>;
    recent?: Array<{
      date?: string;
      amount?: number;
      netflow?: number | null;
      pending?: boolean;
    }>;
  };
}

const typedRaw = rawData as RawDataShape;

export const DEFAULT_INTRADAY_OBSERVATION: NationalTeamIntradayObservation = {
  minute: {
    pre_close: typedRaw.initData?.preClose ?? 0,
    date: typedRaw.initData?.date ?? "2026-10-15",
    times: typedRaw.initData?.times ?? [],
    bars: typedRaw.initData?.bars ?? [],
    closes: typedRaw.initData?.closes ?? [],
    table: (typedRaw.initData?.table ?? []).map((item) => ({
      code: item.code ?? "",
      name: item.name ?? "",
      price: item.price ?? 0,
      pct: item.pct ?? 0,
      amount: item.amount ?? 0,
    })),
    built_at: "2026-11-05 09:45",
  },
  cum: {
    slots: typedRaw.cumData?.slots ?? [],
    prev_date: typedRaw.cumData?.prevDate ?? "",
    prev: typedRaw.cumData?.prev ?? [],
    avg_days: typedRaw.cumData?.avgDays ?? 20,
    avg_from: typedRaw.cumData?.avgFrom ?? "",
    avg_to: typedRaw.cumData?.avgTo ?? "",
    avg20: typedRaw.cumData?.avg20 ?? [],
    built_at: typedRaw.cumData?.builtAt ?? "",
  },
  typical_cases: {
    slots: typedRaw.typData?.slots ?? [],
    sup_amt: typedRaw.typData?.supAmt ?? [],
    sup_cum: typedRaw.typData?.supCum ?? [],
    nor_amt: typedRaw.typData?.norAmt ?? [],
    nor_cum: typedRaw.typData?.norCum ?? [],
    sup_n: typedRaw.typData?.supN ?? 0,
    nor_n: typedRaw.typData?.norN ?? 0,
    range: Array.isArray(typedRaw.typData?.range)
      ? typedRaw.typData.range.join(" ~ ")
      : (typedRaw.typData?.range ?? ""),
  },
  volume_signals: {
    support_threshold_100m: 100,
    support_days: (typedRaw.cmpData?.support ?? []).map((item) => ({
      date: item.date ?? "",
      amount: item.amount ?? 0,
      netflow: item.netflow ?? null,
      is_support_day: true,
      is_pending: false,
    })),
    recent_days: (typedRaw.cmpData?.recent ?? []).map((item) => ({
      date: item.date ?? "",
      amount: item.amount ?? 0,
      netflow: item.netflow ?? null,
      is_support_day: false,
      is_pending: Boolean(item.pending),
    })),
  },
};
