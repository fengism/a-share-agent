import type { ReactNode } from "react";
import {
  ApartmentOutlined,
  AuditOutlined,
  BankOutlined,
  BulbOutlined,
  CalendarOutlined,
  ClockCircleOutlined,
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

export const NAV_GROUPS: NavGroupConfig[] = [
  {
    key: "market",
    label: "行情资讯",
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
      { key: "/national-team", icon: <BankOutlined />, label: "国家队", match: (p) => p.startsWith("/national-team") },
      {
        key: "/feed",
        icon: <ClockCircleOutlined />,
        label: "资讯",
        match: (p) => p.startsWith("/feed") || p.startsWith("/twitter"),
      },
    ],
  },
  {
    key: "macro_industry",
    label: "宏观产业",
    icon: <GlobalOutlined />,
    items: [
      { key: "/macro", icon: <GlobalOutlined />, label: "宏观", match: (p) => p.startsWith("/macro") },
      {
        key: "/industry-chain",
        icon: <ApartmentOutlined />,
        label: "产业链",
        match: (p) => p.startsWith("/industry-chain"),
      },
    ],
  },
  {
    key: "research",
    label: "个股投研",
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
    label: "交易策略",
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
  {
    key: "master_data",
    label: "基础数据",
    icon: <DatabaseOutlined />,
    items: [
      {
        key: "/master-data",
        icon: <DatabaseOutlined />,
        label: "主数据管理",
        match: (p) =>
          p.startsWith("/master-data") ||
          p.startsWith("/stock-concept") ||
          p.startsWith("/industry-classification"),
      },
    ],
  },
];

/**
 * 根据路径获取当前激活的导航项 key
 */
export function getActiveNavKey(pathname: string): string {
  if (pathname === "/") return "/";
  for (const group of NAV_GROUPS) {
    for (const item of group.items) {
      if (item.match) {
        if (item.match(pathname)) {
          return item.key;
        }
      } else if (item.key !== "/" && pathname.startsWith(item.key)) {
        return item.key;
      }
    }
  }
  return "/";
}
