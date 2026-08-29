export const QUERY_CACHE_POLICIES = {
  marketIndices: { staleMs: 30_000, pollMs: 30_000 },
  marketMainline: { staleMs: 60_000, activePollMs: 60_000, idlePollMs: 5 * 60_000 },
  indexIntraday: { staleMs: 30_000, pollMs: 30_000 },
  stockIntraday: { staleMs: 30_000, pollMs: 30_000 },
  thsHotRank: { staleMs: 5 * 60_000, pollMs: 5 * 60_000 },
  marketLimitHistory: { staleMs: 24 * 60 * 60_000 },
  marketSectorStocksHistory: { staleMs: 24 * 60 * 60_000 },
  industryRankings: { liveStaleMs: 60_000, stableStaleMs: 24 * 60 * 60_000, pollMs: 60_000 },
} as const;
