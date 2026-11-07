import type { ReactNode } from "react";
import {
  ApartmentOutlined,
  AuditOutlined,
  BankOutlined,
  BulbOutlined,
  CalendarOutlined,
  ClockCircleOutlined,
  CompassOutlined,
  DashboardOutlined,
  DatabaseOutlined,
  ExperimentOutlined,
  FileSearchOutlined,
  FileTextOutlined,
  FilterOutlined,
  FundOutlined,
  GlobalOutlined,
  HomeOutlined,
  MessageOutlined,
  PieChartOutlined,
  RadarChartOutlined,
  StarOutlined,
} from "@ant-design/icons";

export interface NavItemConfig {
  key: string;
  icon: ReactNode;
  label: string;
  match?: (pathname: string) => boolean;
}

export interface NavGroupConfig {
  key: string;
  label: string;
  icon?: ReactNode;
  items: NavItemConfig[];
}

/**
 * 侧边栏按「投研交易生命周期」收敛为 4 个工作区，而不是按数据来源平铺。
 * 判定依据是用户此刻在做什么，而不是数据来自哪个接口：
 *
 * - 盯盘中心：盘中实时看盘与自选监控（高频、秒级刷新）
 * - 市场洞察：回答「谁在买、钱流向哪」，偏宏观与资金面
 * - 深度投研：以个股/题材为单位的挖掘与研究
 * - 策略与复盘：把判断落成仓位、回测与事后复盘
 *
 * 新增入口前先回答：它属于哪个工作区？四个都不属于，说明它是运维类工具，
 * 应放进 NAV_UTILITY_ITEMS，不要再开第五个分组。
 */
export const NAV_GROUPS: NavGroupConfig[] = [
  {
    key: "market_center",
    label: "盯盘中心",
    icon: <DashboardOutlined />,
    items: [
      { key: "/", icon: <HomeOutlined />, label: "首页", match: (p) => p === "/" },
      { key: "/watchlist", icon: <StarOutlined />, label: "自选", match: (p) => p.startsWith("/watchlist") },
      {
        key: "/market",
        icon: <FundOutlined />,
        label: "市场",
        match: (p) => p.startsWith("/market") || p.startsWith("/hk-market"),
      },
      { key: "/concept", icon: <ApartmentOutlined />, label: "概念", match: (p) => p.startsWith("/concept") },
    ],
  },
  {
    key: "insights",
    label: "市场洞察",
    icon: <CompassOutlined />,
    items: [
      { key: "/national-team", icon: <BankOutlined />, label: "国家队", match: (p) => p.startsWith("/national-team") },
      { key: "/macro", icon: <GlobalOutlined />, label: "宏观", match: (p) => p.startsWith("/macro") },
      {
        key: "/industry-chain",
        icon: <ApartmentOutlined />,
        label: "产业链",
        match: (p) => p.startsWith("/industry-chain"),
      },
      {
        key: "/feed",
        icon: <ClockCircleOutlined />,
        label: "资讯",
        match: (p) => p.startsWith("/feed") || p.startsWith("/twitter"),
      },
    ],
  },
  {
    key: "research",
    label: "深度投研",
    icon: <BulbOutlined />,
    items: [
      { key: "/chat", icon: <MessageOutlined />, label: "对话", match: (p) => p.startsWith("/chat") },
      {
        key: "/analysis",
        icon: <FileSearchOutlined />,
        label: "个股",
        match: (p) =>
          p.startsWith("/analysis") ||
          p.startsWith("/investment-research") ||
          p === "/stock" ||
          p.startsWith("/stock/"),
      },
      { key: "/screener", icon: <FilterOutlined />, label: "选股", match: (p) => p.startsWith("/screener") },
      { key: "/potential", icon: <RadarChartOutlined />, label: "潜力股", match: (p) => p.startsWith("/potential") },
    ],
  },
  {
    key: "trading",
    label: "策略与复盘",
    icon: <AuditOutlined />,
    items: [
      { key: "/portfolio", icon: <PieChartOutlined />, label: "仓位", match: (p) => p.startsWith("/portfolio") },
      { key: "/quant", icon: <ExperimentOutlined />, label: "量化", match: (p) => p.startsWith("/quant") },
      { key: "/daily-review", icon: <FileTextOutlined />, label: "复盘", match: (p) => p.startsWith("/daily-review") },
      {
        key: "/trading-calendar",
        icon: <CalendarOutlined />,
        label: "交易日历",
        match: (p) => p.startsWith("/trading-calendar"),
      },
    ],
  },
];

/**
 * 运维/数据维护类入口：不属于任一投研工作区，渲染在侧边栏底部的独立工具区
 * （无分组标题，仅一条分隔线），避免与业务工作区争夺注意力。
 *
 * 注意：`getActiveNavKey` 会一并检索这里，因此这些页面仍有正确的激活态。
 */
export const NAV_UTILITY_ITEMS: NavItemConfig[] = [
  {
    key: "/master-data",
    icon: <DatabaseOutlined />,
    label: "主数据管理",
    match: (p) =>
      p.startsWith("/master-data") ||
      p.startsWith("/stock-concept") ||
      p.startsWith("/industry-classification"),
  },
];

/**
 * 根据路径获取当前激活的导航项 key。
 *
 * 先查 4 个工作区，再查工具区：工具区的 match 更宽（含历史别名路径），
 * 放在后面可确保具体业务路由优先命中，不会被兜底规则抢走。
 */
export function getActiveNavKey(pathname: string): string {
  if (pathname === "/") return "/";
  const candidates = [...NAV_GROUPS.flatMap((group) => group.items), ...NAV_UTILITY_ITEMS];
  for (const item of candidates) {
    if (item.match) {
      if (item.match(pathname)) {
        return item.key;
      }
    } else if (item.key !== "/" && pathname.startsWith(item.key)) {
      return item.key;
    }
  }
  return "/";
}
