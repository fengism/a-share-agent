export const pageLoaders = {
  appLayout: () => import("../components/AppLayout"),
  earthscope: () => import("../pages/EarthScope"),
  dashboard: () => import("../pages/Dashboard"),
  watchlist: () => import("../pages/Watchlist"),
  market: () => import("../pages/Market"),
  concept: () => import("../pages/Concept"),
  nationalTeam: () => import("../pages/NationalTeam"),
  hkMarket: () => import("../pages/HKMarket"),
  tradingCalendar: () => import("../pages/TradingCalendar"),
  screener: () => import("../pages/Screener"),
  analysis: () => import("../pages/Analysis"),
  stock: () => import("../pages/Stock"),
  analysisEntry: () => import("../pages/Analysis/Entry"),
  dailyReview: () => import("../pages/DailyReview"),
  potential: () => import("../pages/Potential"),
  chat: () => import("../pages/Chat"),
  settings: () => import("../pages/Settings"),
  feed: () => import("../pages/Feed"),
  industryChain: () => import("../pages/IndustryChain"),
  macro: () => import("../pages/Macro"),
  portfolio: () => import("../pages/Portfolio"),
  quant: () => import("../pages/Quant"),
  capabilities: () => import("../pages/Capabilities"),
  industryClassification: () => import("../pages/IndustryClassification"),
  stockConcept: () => import("../pages/StockConcept"),
  masterData: () => import("../pages/MasterData"),
  login: () => import("../pages/Login"),
  register: () => import("../pages/Register"),
  resetPassword: () => import("../pages/ResetPassword"),
  forceChangePassword: () => import("../pages/ForceChangePassword"),
} as const;

type PageLoader = () => Promise<unknown>;

const routeLoaders: Record<string, PageLoader> = {
  "/earthscope": pageLoaders.earthscope,
  "/": pageLoaders.dashboard,
  "/watchlist": pageLoaders.watchlist,
  "/market": pageLoaders.market,
  "/national-team": pageLoaders.nationalTeam,
  "/hk-market": () => pageLoaders.hkMarket(),
  "/trading-calendar": () => pageLoaders.tradingCalendar(),
  "/screener": pageLoaders.screener,
  "/analysis": pageLoaders.analysisEntry,
  "/investment-research": pageLoaders.analysisEntry,
  "/daily-review": pageLoaders.dailyReview,
  "/chat": pageLoaders.chat,
  "/settings": pageLoaders.settings,
  "/feed": pageLoaders.feed,
  "/twitter": () => pageLoaders.feed(),
  "/industry-chain": pageLoaders.industryChain,
  "/macro": pageLoaders.macro,
  "/portfolio": pageLoaders.portfolio,
  "/quant": pageLoaders.quant,
  "/capabilities": pageLoaders.capabilities,
  "/industry-classification": () => pageLoaders.industryClassification(),
  "/stock-concept": () => pageLoaders.stockConcept(),
  "/master-data": () => pageLoaders.masterData(),
};

const routeIntentLoaders: Partial<Record<string, PageLoader>> = {
  "/": () => Promise.all([
    pageLoaders.dashboard(),
    import("../pages/Market/prefetch").then(({ prefetchMarketOverview }) => prefetchMarketOverview()),
  ]),
  "/market": () => pageLoaders.market(),
};

const preloadCache = new Map<string, Promise<void>>();

export function preloadAppRoute(pathnameWithSearch: string): Promise<void> | undefined {
  const pathname = pathnameWithSearch.split("?")[0];
  const routeKey = pathname.startsWith("/stock/")
    ? "/stock/:code"
    : pathname.startsWith("/analysis/")
      ? "/analysis/:code"
      : pathname.startsWith("/investment-research/")
        ? "/investment-research/:code"
        : pathname.startsWith("/industry-chain/")
          ? "/industry-chain/:name"
          : pathname;
  const loader = routeKey === "/stock/:code"
    ? pageLoaders.stock
    : routeKey === "/analysis/:code" || routeKey === "/investment-research/:code"
      ? pageLoaders.analysis
      : routeKey === "/industry-chain/:name"
        ? pageLoaders.industryChain
        : routeIntentLoaders[routeKey] ?? routeLoaders[routeKey];
  if (!loader) return undefined;
  const cached = preloadCache.get(routeKey);
  if (cached) return cached;

  const preload = loader()
    .then(() => undefined)
    .catch(() => {
      preloadCache.delete(routeKey);
    });
  preloadCache.set(routeKey, preload);
  return preload;
}
