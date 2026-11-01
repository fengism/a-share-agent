import type { ScreenerFilter } from "../../types/stock";

export interface ParsedFilterResult {
  patch: Partial<ScreenerFilter>;
  matchedExplanations: string[];
}

export function parseNaturalLanguageToFilters(
  text: string,
  availableIndustries: string[] = [],
  availableConcepts: string[] = [],
): ParsedFilterResult {
  const patch: Partial<ScreenerFilter> = {};
  const matchedExplanations: string[] = [];
  const lower = text.toLowerCase();

  // 1. 市值
  const capMinMatch = text.match(/(?:市值|流通市值)(?:大于|超过|>|高于)(\d+)(?:亿)?/);
  if (capMinMatch) {
    patch.market_cap_min = Number(capMinMatch[1]);
    matchedExplanations.push(`市值 ≥ ${capMinMatch[1]}亿`);
  }
  const capMaxMatch = text.match(/(?:市值|流通市值)(?:小于|低于|<)(\d+)(?:亿)?/);
  if (capMaxMatch) {
    patch.market_cap_max = Number(capMaxMatch[1]);
    matchedExplanations.push(`市值 ≤ ${capMaxMatch[1]}亿`);
  }

  // 2. PE
  const peMaxMatch = text.match(/(?:pe|市盈率|pe_ttm)(?:低于|小于|<|不超过)(\d+)/i);
  if (peMaxMatch) {
    patch.pe_max = Number(peMaxMatch[1]);
    matchedExplanations.push(`PE(TTM) ≤ ${peMaxMatch[1]}`);
  }
  const peMinMatch = text.match(/(?:pe|市盈率|pe_ttm)(?:高于|大于|>|超过)(\d+)/i);
  if (peMinMatch) {
    patch.pe_min = Number(peMinMatch[1]);
    matchedExplanations.push(`PE(TTM) ≥ ${peMinMatch[1]}`);
  }

  // 3. PB / 破净
  if (lower.includes("破净")) {
    patch.is_broken_net = true;
    patch.pb_max = 1.0;
    matchedExplanations.push("破净股 (PB ≤ 1.0)");
  } else {
    const pbMaxMatch = text.match(/(?:pb|市净率)(?:低于|小于|<|不超过)(\d+(?:\.\d+)?)/i);
    if (pbMaxMatch) {
      patch.pb_max = Number(pbMaxMatch[1]);
      matchedExplanations.push(`PB ≤ ${pbMaxMatch[1]}`);
    }
  }

  // 4. 换手率
  const turnoverMatch = text.match(/(?:换手率|换手)(?:大于|高于|>|超过)(\d+(?:\.\d+)?)(?:%)?/);
  if (turnoverMatch) {
    patch.turnover_pct_min = Number(turnoverMatch[1]);
    matchedExplanations.push(`换手率 ≥ ${turnoverMatch[1]}%`);
  }

  // 5. 涨跌幅
  const changeMatch = text.match(/(?:涨跌幅|涨幅)(?:大于|超过|>|高于)(\d+(?:\.\d+)?)(?:%)?/);
  if (changeMatch) {
    patch.change_pct_min = Number(changeMatch[1]);
    matchedExplanations.push(`涨幅 ≥ ${changeMatch[1]}%`);
  }

  // 6. 60日涨幅
  const change60Match = text.match(/(?:60日涨幅|两月涨幅|中期涨幅)(?:大于|超过|>|高于)(\d+(?:\.\d+)?)(?:%)?/);
  if (change60Match) {
    patch.change_pct_60d_min = Number(change60Match[1]);
    matchedExplanations.push(`60日涨幅 ≥ ${change60Match[1]}%`);
  }

  // 7. 量比
  const volumeRatioMatch = text.match(/(?:量比)(?:大于|超过|>|高于)(\d+(?:\.\d+)?)/);
  if (volumeRatioMatch) {
    patch.volume_ratio_min = Number(volumeRatioMatch[1]);
    matchedExplanations.push(`量比 ≥ ${volumeRatioMatch[1]}`);
  }

  // 8. 剔除ST
  if (/(?:剔除st|不含st|非st|无st)/i.test(text)) {
    patch.exclude_st = true;
    matchedExplanations.push("剔除ST风险股");
  }

  // 9. 匹配行业
  const matchedIndustries: string[] = [];
  availableIndustries.forEach((ind) => {
    if (ind && ind.length >= 2 && text.includes(ind)) {
      matchedIndustries.push(ind);
    }
  });
  if (matchedIndustries.length > 0) {
    patch.industries = matchedIndustries;
    matchedExplanations.push(`行业: ${matchedIndustries.join("、")}`);
  }

  // 10. 匹配概念
  const matchedConcepts: string[] = [];
  availableConcepts.forEach((c) => {
    if (c && c.length >= 2 && text.includes(c)) {
      matchedConcepts.push(c);
    }
  });
  if (matchedConcepts.length > 0) {
    patch.concepts = matchedConcepts;
    matchedExplanations.push(`概念: ${matchedConcepts.join("、")}`);
  }

  return { patch, matchedExplanations };
}
