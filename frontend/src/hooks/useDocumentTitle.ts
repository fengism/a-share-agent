import { useEffect } from "react";

const APP_NAME = "A-Share Agent";

export const ROUTE_DEFAULT_TITLES: Record<string, string> = {
  "/": "大盘看板",
  "/watchlist": "自选股监控",
  "/market": "大盘全景行情",
  "/national-team": "国家队持仓分析",
  "/screener": "智能多因子选股",
  "/trading-calendar": "交易日历",
  "/daily-review": "大盘每日复盘",
  "/potential": "黑马潜伏挖掘",
  "/feed": "全网舆情监控",
  "/macro": "宏观数据看板",
  "/portfolio": "投资组合管理",
  "/quant": "量化策略回测",
  "/industry-chain": "产业链图谱",
  "/chat": "AI 投研助手",
  "/capabilities": "Agent 技能目录",
  "/master-data": "基础主数据",
  "/settings": "系统配置与偏好",
  "/login": "用户登录",
  "/register": "用户注册",
  "/reset-password": "重置密码",
  "/earthscope": "EarthScope 全球视野",
};

export function formatPageTitle(title?: string | null): string {
  const trimmed = title?.trim();
  if (!trimmed) {
    return APP_NAME;
  }
  return `${trimmed} - ${APP_NAME}`;
}

export function resolveRouteTitle(pathname: string): string | undefined {
  if (ROUTE_DEFAULT_TITLES[pathname]) {
    return ROUTE_DEFAULT_TITLES[pathname];
  }
  if (pathname.startsWith("/stock/") || pathname.startsWith("/analysis/")) {
    const code = pathname.split("/")[2];
    return code ? `标的详情 (${code})` : "标的投研分析";
  }
  if (pathname.startsWith("/industry-chain/")) {
    const name = decodeURIComponent(pathname.split("/")[2] || "");
    return name ? `${name}产业链` : "产业链图谱";
  }
  return undefined;
}

export interface UseDocumentTitleOptions {
  restoreOnUnmount?: boolean;
}

export function useDocumentTitle(
  title?: string | null,
  options: UseDocumentTitleOptions = {},
): void {
  const { restoreOnUnmount = false } = options;

  useEffect(() => {
    if (typeof document === "undefined") return;
    const previousTitle = document.title;
    if (title !== undefined) {
      document.title = formatPageTitle(title);
    }
    return () => {
      if (restoreOnUnmount) {
        document.title = previousTitle;
      }
    };
  }, [title, restoreOnUnmount]);
}
