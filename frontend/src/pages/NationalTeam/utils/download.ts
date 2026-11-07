import type {
  NationalTeamEtfSeries,
  NationalTeamPortrait,
} from "../../../types/stock";
import { marketDateStamp } from "../../../utils/marketTime";
import { CATEGORY_TAG_LABELS } from "../constants";
import { downloadCsv } from "./csv";

export function downloadNationalTeamCsv(etfs: NationalTeamEtfSeries[], asOfDate?: string | null) {
  const headers = [
    "战术分类",
    "宽基板块",
    "ETF代码",
    "ETF名称",
    "基金公司",
    "市场",
    "最新日期",
    "最新份额(亿份)",
    "1日变化(亿份)",
    "5日变化(亿份)",
    "20日变化(亿份)",
    "1日估算净申购(亿元)",
    "成交额(亿元)",
    "量比",
    "放量异动",
  ];

  const rows = etfs.map((item) => {
    const flow1d = item.latest_estimated_net_flow_100m;
    const catLabel = CATEGORY_TAG_LABELS[item.category || "core_broad"]?.label || "核心大盘";
    return [
      catLabel,
      item.index_name,
      item.code,
      item.name,
      item.fund_manager || "",
      item.exchange === "SH" ? "上海" : "深圳",
      item.latest_date || "",
      item.latest_shares_100m != null ? item.latest_shares_100m.toFixed(2) : "",
      item.latest_change_1d_100m != null ? item.latest_change_1d_100m.toFixed(2) : "",
      item.change_5d_100m != null ? item.change_5d_100m.toFixed(2) : "",
      item.change_20d_100m != null ? item.change_20d_100m.toFixed(2) : "",
      flow1d != null ? flow1d.toFixed(2) : "",
      item.latest_amount_100m != null ? item.latest_amount_100m.toFixed(2) : "",
      item.volume_ratio != null ? item.volume_ratio.toFixed(2) : "",
      item.is_abnormal_volume ? "显著放量" : "正常",
    ];
  });

  downloadCsv(`国家队ETF监测_${asOfDate || marketDateStamp()}.csv`, [headers, ...rows]);
}

export function downloadPortraitCsv(portrait: NationalTeamPortrait) {
  const rows: unknown[][] = [];
  rows.push(["国家队战略机构底仓全景数据"]);
  rows.push(["披露口径", portrait.reporting_period || ""]);
  rows.push(["静态参考截至", portrait.as_of || ""]);
  rows.push(["数据来源", portrait.source || ""]);
  rows.push(["预估战略总持股市值(万亿元)", portrait.total_market_value_trillion || ""]);
  rows.push([]);

  // 1. 机构主体
  rows.push(["机构主体", "机构简称", "职能定位", "预估规模(万亿元)", "配置核心"]);
  for (const entity of portrait.entities ?? []) {
    rows.push([entity.name, entity.short_name, entity.role, entity.estimated_aum_trillion, entity.focus]);
  }
  rows.push([]);

  // 2. 行业配置
  rows.push(["行业板块", "配置权重(%)", "持股市值(亿元)", "代表性标的"]);
  for (const allocation of portrait.industry_allocations ?? []) {
    rows.push([
      allocation.industry,
      allocation.weight_pct,
      allocation.market_value_100m,
      (allocation.representative_stocks ?? []).join(" / "),
    ]);
  }
  rows.push([]);

  // 3. 前十大重仓
  rows.push(["排名", "标的代码", "标的名称", "持股主体", "所属行业", "占总股本比(%)", "持股市值(亿元)"]);
  (portrait.top_holdings ?? []).forEach((holding, idx) => {
    rows.push([
      idx + 1,
      holding.code,
      holding.name,
      holding.holder_name,
      holding.industry,
      holding.shareholding_ratio_pct,
      holding.market_value_100m,
    ]);
  });

  downloadCsv(`国家队战略底仓画像_${marketDateStamp()}.csv`, rows);
}
