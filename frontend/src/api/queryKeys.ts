export const queryKeys = {
  market: {
    indices: ["marketIndices"] as const,
    indexKline: (symbol: string, period: string, startDate: string) =>
      ["marketIndexKline", symbol, period, startDate] as const,
    hsgtFlow: ["hsgtFlow"] as const,
    thsHotRank: ["thsHotRank"] as const,
    thsHotConcept: ["thsHotConcept"] as const,
    thsHotIndustry: ["thsHotIndustry"] as const,
    industryRankings: ["industryRankings"] as const,
    dragonTiger: (reportDate: string) => ["dragonTiger", reportDate] as const,
    dragonTigerDetail: (code: string, reportDate: string) =>
      ["dragonTigerDetail", code, reportDate] as const,
    kuaixun: ["marketKuaixun"] as const,
    otherNews: ["marketOtherNews"] as const,
    twitterFeed: ["marketTwitterFeed"] as const,
    twitterAnalysisRoot: ["marketTwitterAnalysis"] as const,
    twitterAnalysis: (username: string) => ["marketTwitterAnalysis", username] as const,
    newsAnalysis: ["newsAnalysis"] as const,
    macroAll: ["macroAllData"] as const,
  },
  stock: {
    search: (query: string) => ["stockSearch", query] as const,
    kline: (code: string, period: string, adjust: string, startDate: string) =>
      ["kline", code, period, adjust, startDate] as const,
    financial: (code: string, type: string) => ["financial", code, type] as const,
    valuationDetail: (code: string) => ["valuationDetail", code] as const,
    indicators: (code: string) => ["indicators", code] as const,
    categorizedNews: (code: string) => ["categorizedNews", code] as const,
    sentiment: (code: string) => ["sentiment", code] as const,
    retailSentiment: (code: string) => ["retailSentiment", code] as const,
    compare: (codes: string) => ["stockCompare", codes] as const,
    fundFlow: (code: string) => ["stockFundFlow", code] as const,
    analysisPage: (code: string) => ["analysisPage", code] as const,
  },
  screener: {
    screen: (filters: unknown) => ["screener", filters] as const,
    industries: ["industries"] as const,
  },
  settings: {
    config: ["config"] as const,
    failedBotJobs: ["bot-jobs", "failed"] as const,
    invites: ["invites"] as const,
  },
  portfolio: ["portfolio"] as const,
  quant: {
    presets: ["quant", "strategy-presets"] as const,
    strategies: ["quant", "strategies"] as const,
    runs: ["quant", "backtests"] as const,
    run: (runId: string) => ["quant", "backtests", runId] as const,
  },
  workflows: {
    dailyReviewHistoryRoot: ["dailyReviewHistory"] as const,
    dailyReviewHistory: (pageSize: number) => ["dailyReviewHistory", "infinite", pageSize] as const,
    dailyReview: (date: string) => ["dailyReview", date] as const,
    analysisHistory: (pageSize: number) => ["allAnalysisHistory", "infinite", pageSize] as const,
    industryChainHistoryRoot: ["industryChainHistory"] as const,
    industryChainHistory: (name: string, pageSize: number) =>
      ["industryChainHistory", "infinite", name, pageSize] as const,
    industryChainLatest: (name: string) => ["industryChainLatest", name] as const,
  },
  capabilities: {
    catalog: ["chat-capabilities"] as const,
    availability: ["chat-capability-availability"] as const,
  },
} as const;
