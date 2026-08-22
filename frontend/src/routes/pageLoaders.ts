export const pageLoaders = {
  appLayout: () => import("../components/AppLayout"),
  dashboard: () => import("../pages/Dashboard"),
  market: () => import("../pages/Market"),
  screener: () => import("../pages/Screener"),
  analysis: () => import("../pages/Analysis"),
  analysisEntry: () => import("../pages/Analysis/Entry"),
  dailyReview: () => import("../pages/DailyReview"),
  chat: () => import("../pages/Chat"),
  settings: () => import("../pages/Settings"),
  feed: () => import("../pages/Feed"),
  twitter: () => import("../pages/Twitter"),
  industryChain: () => import("../pages/IndustryChain"),
  compare: () => import("../pages/Compare"),
  macro: () => import("../pages/Macro"),
  portfolio: () => import("../pages/Portfolio"),
  quant: () => import("../pages/Quant"),
  capabilities: () => import("../pages/Capabilities"),
  login: () => import("../pages/Login"),
  register: () => import("../pages/Register"),
  resetPassword: () => import("../pages/ResetPassword"),
  forceChangePassword: () => import("../pages/ForceChangePassword"),
} as const;

type PageLoader = () => Promise<unknown>;

const routeLoaders: Record<string, PageLoader> = {
  "/": pageLoaders.dashboard,
  "/market": pageLoaders.market,
  "/screener": pageLoaders.screener,
  "/analysis": pageLoaders.analysisEntry,
  "/daily-review": pageLoaders.dailyReview,
  "/chat": pageLoaders.chat,
  "/settings": pageLoaders.settings,
  "/feed": pageLoaders.feed,
  "/twitter": pageLoaders.twitter,
  "/industry-chain": pageLoaders.industryChain,
  "/compare": pageLoaders.compare,
  "/macro": pageLoaders.macro,
  "/portfolio": pageLoaders.portfolio,
  "/quant": pageLoaders.quant,
  "/capabilities": pageLoaders.capabilities,
};

const routeIntentLoaders: Partial<Record<string, PageLoader>> = {
  "/market": () => Promise.all([
    pageLoaders.market(),
    import("../pages/Market/prefetch").then(({ prefetchMarketOverview }) => prefetchMarketOverview()),
  ]),
};

const preloadCache = new Map<string, Promise<void>>();

export function preloadAppRoute(pathname: string): Promise<void> | undefined {
  const routeKey = pathname.startsWith("/analysis/")
    ? "/analysis/:code"
    : pathname.startsWith("/industry-chain/")
      ? "/industry-chain/:name"
      : pathname;
  const loader = routeKey === "/analysis/:code"
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
