import type { QuantBacktestResult, QuantStrategyConfig } from "../../../api/queries";
import { marketDateStamp } from "../../../utils/marketTime";
import { formatPercent, formatRatio } from "./formatters";
import { quantStrategyIdentity, quantStrategyParameterSummary } from "../quantRun";

function downloadFile(content: string, filename: string, mimeType: string) {
  const blob = new Blob([content], { type: mimeType });
  if (typeof URL.createObjectURL === "function") {
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL?.(url);
  }
}

export function exportEquityCurveCsv(equityCurve: QuantBacktestResult["equity_curve"]) {
  if (!equityCurve || equityCurve.length === 0) return;
  const headers = ["日期", "策略净值(元)", "基准净值(元)", "动态回撤(%)", "可用现金(元)", "持仓市值(元)", "超额收益(%)", "60日滚动夏普", "60日滚动贝塔"];
  const rows = equityCurve.map((pt) => [
    `"${pt.date}"`,
    pt.equity.toFixed(2),
    pt.benchmark != null ? pt.benchmark.toFixed(2) : "",
    pt.drawdown.toFixed(4),
    pt.cash != null ? pt.cash.toFixed(2) : "",
    pt.positions_value != null ? pt.positions_value.toFixed(2) : "",
    pt.excess_return != null ? pt.excess_return.toFixed(2) : "",
    pt.rolling_sharpe != null ? pt.rolling_sharpe.toFixed(2) : "",
    pt.rolling_beta != null ? pt.rolling_beta.toFixed(2) : "",
  ].join(","));
  const csv = "\uFEFF" + [headers.join(","), ...rows].join("\n");
  downloadFile(csv, `量化每日净值序列_${marketDateStamp()}.csv`, "text/csv;charset=utf-8");
}

export function exportTradesCsv(trades: QuantBacktestResult["trades"]) {
  if (!trades || trades.length === 0) return;
  const headers = ["成交日期", "股票代码", "交易方向", "成交价格", "成交股数", "手续费", "已实现盈亏"];
  const rows = trades.map((t) => [
    `"${t.date}"`,
    `\t${t.code}`,
    t.side === "buy" ? "买入" : "卖出",
    t.price.toFixed(2),
    t.shares,
    t.fee.toFixed(2),
    t.realized_pnl != null ? t.realized_pnl.toFixed(2) : "",
  ].join(","));
  const csv = "\uFEFF" + [headers.join(","), ...rows].join("\n");
  downloadFile(csv, `量化回测成交明细_${marketDateStamp()}.csv`, "text/csv;charset=utf-8");
}

export function exportBacktestTearsheetMarkdown(
  result: QuantBacktestResult,
  strategy?: QuantStrategyConfig,
) {
  const m = result.metrics;
  const stressEntries = Object.entries(m.stress_tests ?? {});

  const lines: string[] = [
    `# 量化投资策略专业研报 (Quant Strategy Factsheet)`,
    ``,
    `> **报告生成时间**: ${new Date().toLocaleString("zh-CN", { timeZone: "Asia/Shanghai" })}  `,
    `> **回测引擎版本**: ${result.engine_version}  `,
    `> **数据源**: ${result.data_sources?.join(", ") || "A股官方前复权日线行情"}`,
    ``,
    `---`,
    ``,
    `## 1. 策略基本信息`,
    `- **策略名称与版本**: ${strategy ? quantStrategyIdentity(strategy) : "自定义量化策略"}`,
    `- **实际运行参数**: ${strategy ? quantStrategyParameterSummary(strategy) : "无"}`,
    `- **投资标的池**: ${result.codes.join(", ")} (共 ${result.codes.length} 只标的)`,
    `- **评估区间天数**: ${m.observation_count ?? result.equity_curve.length} 交易日`,
    `- **总交易笔数**: ${m.trade_count} 笔 (已平仓 ${m.closed_trade_count} 笔)`,
    ``,
    `---`,
    ``,
    `## 2. 核心绩效与风险收益指标 (Performance Overview)`,
    `| 指标名称 | 策略表现 | 说明 |`,
    `| :--- | :--- | :--- |`,
    `| **累计总收益率** | **${formatPercent(m.total_return)}** | 回测周期内投资组合净值增长 |`,
    `| **年化收益率 (CAGR)** | **${formatPercent(m.annualized_return)}** | 按 252 个 A 股交易日几何年化折算 |`,
    `| **基准指数收益率** | ${formatPercent(m.benchmark_return)} | 对标指数同期表现 |`,
    `| **超额年化 Alpha** | **${formatPercent(m.alpha)}** | 相对基准的超额风险调整收益 |`,
    `| **基准 Beta 系数** | ${formatRatio(m.beta)} | 相对对标基准的系统性敏感度 |`,
    `| **最大动态回撤** | **${formatPercent(m.max_drawdown)}** | 净值历史最高点回落的最大幅度 |`,
    `| **最长水下持续天数** | ${m.max_drawdown_duration_days ?? "-"} 天 | 历史最大回撤从发生到完全修复的最长历时 |`,
    `| **夏普比率 (Sharpe)** | **${formatRatio(m.sharpe_ratio)}** | 无风险利率基准下的风险溢价报酬比 |`,
    `| **索提诺比率 (Sortino)** | ${formatRatio(m.sortino_ratio)} | 仅惩罚下行波动率的风险调整比率 |`,
    `| **卡玛比率 (Calmar)** | ${formatRatio(m.calmar_ratio)} | 年化收益率 / 最大回撤 |`,
    `| **Omega 比率** | ${formatRatio(m.omega_ratio)} | 超过阈值收益与亏损概率分布的比值 |`,
    `| **特雷诺比率 (Treynor)** | ${formatRatio(m.treynor_ratio)} | 承担单位系统风险获得的超额收益 |`,
    `| **上行捕获率** | ${formatPercent(m.upside_capture)} | 市场上涨时策略收益跟随比率 |`,
    `| **下行捕获率** | ${formatPercent(m.downside_capture)} | 市场下跌时策略跟随比率 (越低越抗跌) |`,
    `| **交易胜率** | ${formatPercent(m.win_rate)} | 平仓盈利交易占比 |`,
    `| **盈亏比 (Profit Factor)** | ${formatRatio(m.profit_loss_ratio)} | 总盈利金额 / 总亏损金额 |`,
    `| **平均持仓周期** | ${m.avg_holding_days != null ? `${m.avg_holding_days} 天` : "-"} | 每次平仓的平均持有天数 |`,
    `| **盈/亏平均持仓** | ${m.avg_win_holding_days != null ? `${m.avg_win_holding_days} 天` : "-"} / ${m.avg_loss_holding_days != null ? `${m.avg_loss_holding_days} 天` : "-"} | 盈利持仓 vs 亏损持仓天数 (让利润奔跑检验) |`,
    `| **平均单笔盈亏额** | ${m.avg_win_pnl != null ? `+${m.avg_win_pnl} 元` : "-"} / ${m.avg_loss_pnl != null ? `${m.avg_loss_pnl} 元` : "-"} | 盈利交易 vs 亏损交易平均收益规模 |`,
    `| **单笔极端盈亏率** | ${formatPercent(m.max_win_pct)} / ${formatPercent(m.max_loss_pct)} | 单笔最大收益率 vs 最大回撤深度 |`,
    `| **单边换手率** | ${formatPercent(m.turnover_rate)} | 周期内买卖成交额 / 组合平均净值 |`,
    ``,
    `---`,
    ``,
    `## 3. 机构级统计检验与抗过拟合评估 (Robustness & Statistical Tests)`,
    `| 统计检验 | 检验得分 | 行业标准阈值 | 诊断结论 |`,
    `| :--- | :--- | :--- | :--- |`,
    `| **概率夏普比率 (PSR)** | ${m.probabilistic_sharpe_ratio != null ? `${m.probabilistic_sharpe_ratio}%` : "-"} | ≥ 95% 置信度 | ${m.probabilistic_sharpe_ratio && m.probabilistic_sharpe_ratio >= 95 ? "显著超越随机基准 (通过)" : "未能达到 95% 显著性"} |`,
    `| **紧缩夏普比率 (DSR)** | ${m.deflated_sharpe_ratio != null ? `${m.deflated_sharpe_ratio}%` : "-"} | ≥ 95% (校正10次多重试验) | ${m.deflated_sharpe_ratio && m.deflated_sharpe_ratio >= 95 ? "抗多重试验过拟合 (通过)" : "可能存在选优过拟合风险"} |`,
    ``,
  ];

  if (m.allocation_effect != null || m.selection_effect != null) {
    lines.push(
      `---`,
      ``,
      `## 4. Brinson-Fachler 超额收益归因分解 (Performance Attribution)`,
      `| 归因维度 | 贡献幅度 | 经济学含义 |`,
      `| :--- | :--- | :--- |`,
      `| **资产配置/仓位择时效应** | **${formatPercent(m.allocation_effect)}** | 调整现金与权益整体暴露所产生的超额回报 |`,
      `| **标的选择效应 (Selection)** | **${formatPercent(m.selection_effect)}** | 精选具体股票相比基准平均表现的超额回报 |`,
      `| **交叉交互效应 (Interaction)** | **${formatPercent(m.interaction_effect)}** | 仓位变动与标的走势共同作用的联合贡献 |`,
      `| **合计超额收益** | **${formatPercent(m.excess_return)}** | 相对基准累计总超额回报 |`,
      ``,
    );
  }

  if (stressEntries.length > 0) {
    lines.push(`---`, ``, `## 5. 历史极端危机压力测试 (Historical Crises Stress Tests)`, `| 历史危机阶段 | 策略期间收益 | 危机期最大回撤 | 诊断 |`, `| :--- | :--- | :--- | :--- |`);
    for (const [name, stats] of stressEntries) {
      lines.push(`| **${name}** | ${formatPercent(stats.return_pct)} | ${formatPercent(stats.max_drawdown_pct)} | ${stats.max_drawdown_pct > -15 ? "防御稳健" : "受冲击较大"} |`);
    }
    lines.push(``);
  }

  if (result.monthly_returns?.length) {
    lines.push(`---`, ``, `## 5. 月度收益表现分布 (Monthly Returns Breakdown)`, `| 月份 | 收益率 |`, `| :--- | :--- |`);
    for (const mr of result.monthly_returns) {
      lines.push(`| ${mr.month} | ${formatPercent(mr.return_pct)} |`);
    }
    lines.push(``);
  }

  // Section 6: AI Tactical & Multi-Factor Attribution
  lines.push(
    `---`,
    ``,
    `## 6. AI 战术多因子归因与体检 (AI Tactical & Multi-Factor Attribution)`,
    `- **换手率活跃度归因**: 回测年化换手率约 ${formatPercent(m.turnover_rate)}。${(m.turnover_rate ?? 0) > 200 ? "策略节奏较为进取，建议在个股放量突破初期（换手率 > 3%）介入以提升胜率，缩量阴跌期严格止损。" : "策略属于稳健波段跟踪，换手摩擦小，具备较好抗杂波能力。"}`,
    `- **资金流向与主力博弈建议**: 实盘中建议将「主力资金连续净流入」或「超大单成交占比 > 10%」作为正向开仓置信度过滤，防范假突破。`,
    `- **财报基本面与选股池安全垫**: 建议前置叠加「ROE ≥ 10% + 扣非净利润连续增长 + 估值处历史 50% 分位以内」构建底池，避免技术面择时误入暴雷股。`,
    ``,
  );

  // Section 7: Constituent breakdown if multiple codes
  if (result.codes.length > 1 && result.trades.length > 0) {
    const pnlByCode: Record<string, { pnl: number; count: number; winCount: number; closed: number }> = {};
    for (const t of result.trades) {
      if (!pnlByCode[t.code]) pnlByCode[t.code] = { pnl: 0, count: 0, winCount: 0, closed: 0 };
      pnlByCode[t.code].count++;
      if (t.realized_pnl != null) {
        pnlByCode[t.code].closed++;
        pnlByCode[t.code].pnl += t.realized_pnl;
        if (t.realized_pnl > 0) pnlByCode[t.code].winCount++;
      }
    }
    lines.push(
      `---`,
      ``,
      `## 7. 多标的盈亏贡献拆解 (Constituent Stock Performance Breakdown)`,
      `| 标的代码 | 成交笔数 | 平仓笔数 | 胜率 | 累计已平仓盈亏 |`,
      `| :--- | :--- | :--- | :--- | :--- |`,
    );
    for (const [code, stat] of Object.entries(pnlByCode)) {
      const winRateStr = stat.closed > 0 ? `${((stat.winCount / stat.closed) * 100).toFixed(1)}%` : "-";
      const pnlStr = stat.closed > 0 ? (stat.pnl > 0 ? `+${stat.pnl.toFixed(2)} 元` : `${stat.pnl.toFixed(2)} 元`) : "-";
      lines.push(`| ${code} | ${stat.count} 笔 | ${stat.closed} 笔 | ${winRateStr} | ${pnlStr} |`);
    }
    lines.push(``);
  }

  lines.push(
    `---`,
    `*声明：本报告为日线近似量化回测模拟，受停牌、流动性冲击及滑点模型等假设计算，历史表现不代表未来收益，投资决策请审慎。*`,
  );

  downloadFile(lines.join("\n"), `量化策略研报_${strategy?.type || "quant"}_${marketDateStamp()}.md`, "text/markdown;charset=utf-8");
}
