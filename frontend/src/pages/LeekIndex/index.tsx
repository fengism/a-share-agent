import { useState, useMemo, useEffect } from "react";
import {
  Button,
  Card,
  Drawer,
  Empty,
  Input,
  Progress,
  Radio,
  Space,
  Table,
  Tag,
  Tooltip,
  message,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import {
  FireOutlined,
  ReloadOutlined,
  SearchOutlined,
  InfoCircleOutlined,
  WarningOutlined,
  DownloadOutlined,
  DotChartOutlined,
  DownOutlined,
  UpOutlined,
} from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import StockWorkspaceDrawer from "../../components/StockWorkspaceDrawer";
import {
  useLeekIndexOverview,
  useIndustryLeekHistory,
  useRefreshLeekIndex,
  type IndustryLeekItem,
} from "../../api/queryHooks/sentiment";
import { useUrlSearchParam } from "../../hooks/useUrlSearchParam";
import { useMediaQuery } from "../../hooks/useMediaQuery";
import { downloadCsv } from "../NationalTeam/utils/csv";
import { LeekQuadrantChart } from "./LeekQuadrantChart";
import "./leek-index.css";
import "./leek-drawer.css";
import "./leek-mobile.css";

const RISK_BADGES = {
  extreme: { color: "red", label: "🔥 极度接盘", desc: "散户高位狂热追高，主力坚决出货，极易见顶" },
  fever: { color: "orange", label: "⚠️ 散户过热", desc: "跟风炒作加速，筹码趋向分散" },
  normal: { color: "blue", label: "⚖️ 筹码均衡", desc: "多空博弈平稳，主力散户参与度正常" },
  safe: { color: "green", label: "💎 筹码出清", desc: "散户割肉离场、无人问津，常为左侧黄金坑" },
};

function formatAmount(val: number): string {
  const abs = Math.abs(val);
  if (abs >= 1e8) {
    return `${(val / 1e8).toFixed(1)} 亿`;
  }
  if (abs >= 1e4) {
    return `${(val / 1e4).toFixed(0)} 万`;
  }
  return `${val.toFixed(0)} 元`;
}

function getScoreColorClass(score: number): string {
  if (score >= 75) return "leek-score-num--extreme";
  if (score >= 60) return "leek-score-num--fever";
  if (score >= 35) return "leek-score-num--normal";
  return "leek-score-num--safe";
}

export default function LeekIndexPage() {
  const navigate = useNavigate();
  const isMobile = useMediaQuery("(max-width: 768px)");

  const [filterLevel, setFilterLevel] = useUrlSearchParam<string>("level", "all", {
    allowedValues: ["all", "extreme", "fever", "normal", "safe"],
  });
  const [quickPreset, setQuickPreset] = useUrlSearchParam<string>("preset", "all", {
    allowedValues: ["all", "top_risk", "bargain", "smart_inflow"],
  });
  const [searchKw, setSearchKw] = useUrlSearchParam<string>("q", "", { replace: true });
  const [industryParam, setIndustryParam] = useUrlSearchParam<string>("industry", "", { replace: true });
  const [showQuadrant, setShowQuadrant] = useState<boolean>(!isMobile);

  const [selectedIndustry, setSelectedIndustry] = useState<IndustryLeekItem | null>(null);
  const [previewStock, setPreviewStock] = useState<{ code: string; name: string } | null>(null);

  const { data, isLoading, isFetching } = useLeekIndexOverview();
  const refreshMutation = useRefreshLeekIndex();

  const historyQuery = useIndustryLeekHistory(
    selectedIndustry?.industry_name ?? "",
    30
  );

  // URL 深度直达：根据 industry 参数自动打开对应行业抽屉
  useEffect(() => {
    if (industryParam && data?.industries) {
      const match = data.industries.find((i) => i.industry_name === industryParam);
      if (match && selectedIndustry?.industry_name !== industryParam) {
        setSelectedIndustry(match);
      }
    }
  }, [industryParam, data?.industries, selectedIndustry?.industry_name]);

  const handleSelectIndustry = (record: IndustryLeekItem | null) => {
    setSelectedIndustry(record);
    setIndustryParam(record ? record.industry_name : "");
  };

  const filteredIndustries = useMemo(() => {
    if (!data?.industries) return [];
    return data.industries.filter((item) => {
      // 快捷预设过滤器
      if (quickPreset === "top_risk" && !(item.leek_score >= 70 && item.change_pct >= 0)) {
        return false;
      }
      if (quickPreset === "bargain" && !(item.leek_score <= 40 && item.change_pct <= 0)) {
        return false;
      }
      if (quickPreset === "smart_inflow" && !(item.main_net > 0 && item.retail_net < 0)) {
        return false;
      }

      const matchLevel = filterLevel === "all" || item.risk_level === filterLevel;
      const matchKw =
        !searchKw.trim() ||
        item.industry_name.includes(searchKw.trim()) ||
        item.crowded_stocks.some((s) => s.name.includes(searchKw.trim()) || s.code.includes(searchKw.trim())) ||
        (item.sub_industries && item.sub_industries.some((sub) => sub.name.includes(searchKw.trim())));
      return matchLevel && matchKw;
    });
  }, [data?.industries, filterLevel, searchKw, quickPreset]);

  const handleExportCsv = () => {
    if (!filteredIndustries || filteredIndustries.length === 0) {
      message.warning("当前无数据可导出");
      return;
    }
    const headers = [
      "排名",
      "申万一级行业",
      "韭菜指数",
      "风险等级",
      "当日涨跌幅(%)",
      "主力净流入(元)",
      "散户净买入(元)",
      "主力净流入(描述)",
      "散户净买入(描述)",
      "资金流背离分",
      "东财股吧舆论分",
      "成交拥挤度分",
      "滞涨套牢分",
      "跟风热门标的",
      "预警信号",
    ];
    const rows = filteredIndustries.map((item, idx) => [
      idx + 1,
      item.industry_name,
      item.leek_score.toFixed(1),
      RISK_BADGES[item.risk_level as keyof typeof RISK_BADGES]?.label || item.risk_level,
      item.change_pct.toFixed(2),
      item.main_net,
      item.retail_net,
      formatAmount(item.main_net),
      formatAmount(item.retail_net),
      item.sub_scores.flow.toFixed(1),
      item.sub_scores.guba.toFixed(1),
      item.sub_scores.crowd.toFixed(1),
      item.sub_scores.trap.toFixed(1),
      item.crowded_stocks.map((s) => `${s.name}(${s.code})`).join("; "),
      item.warning_signals.join("; "),
    ]);
    const filename = `A股行业韭菜指数_${data?.trade_date || "today"}.csv`;
    downloadCsv(filename, [headers, ...rows]);
    message.success(`已导出 ${filteredIndustries.length} 条行业韭菜指数数据`);
  };

  const columns: ColumnsType<IndustryLeekItem> = [
    {
      title: "排名",
      key: "rank",
      width: 65,
      align: "center",
      render: (_, __, idx) => <span className="font-mono text-secondary">{idx + 1}</span>,
    },
    {
      title: "申万一级行业",
      dataIndex: "industry_name",
      key: "industry_name",
      render: (name: string, record) => (
        <Button
          type="link"
          className="leek-industry-btn"
          onClick={() => handleSelectIndustry(record)}
        >
          {name}
        </Button>
      ),
    },
    {
      title: "韭菜指数 (0-100)",
      dataIndex: "leek_score",
      key: "leek_score",
      sorter: (a, b) => a.leek_score - b.leek_score,
      width: 200,
      render: (score: number) => {
        let strokeColor = "#10b981";
        if (score >= 75) strokeColor = "#ef4444";
        else if (score >= 60) strokeColor = "#f59e0b";
        else if (score >= 35) strokeColor = "#3b82f6";
        return (
          <div className="leek-score-cell">
            <span className={`leek-score-num ${getScoreColorClass(score)}`}>
              {score.toFixed(1)}
            </span>
            <Progress
              percent={score}
              strokeColor={strokeColor}
              showInfo={false}
              size="small"
              className="leek-score-progress"
            />
          </div>
        );
      },
    },
    {
      title: "四维因子透视",
      key: "factors",
      width: 175,
      render: (_, record) => (
        <Tooltip
          title={
            <div className="leek-factor-tooltip">
              <div>资金剪刀差: <strong>{record.sub_scores.flow.toFixed(1)}</strong></div>
              <div>东财股吧热度: <strong>{record.sub_scores.guba.toFixed(1)}</strong></div>
              <div>成交拥挤度: <strong>{record.sub_scores.crowd.toFixed(1)}</strong></div>
              <div>滞涨套牢盘: <strong>{record.sub_scores.trap.toFixed(1)}</strong></div>
            </div>
          }
        >
          <div className="leek-factor-pills">
            <span className="leek-pill leek-pill--flow">流 {record.sub_scores.flow.toFixed(0)}</span>
            <span className="leek-pill leek-pill--guba">吧 {record.sub_scores.guba.toFixed(0)}</span>
            <span className="leek-pill leek-pill--crowd">挤 {record.sub_scores.crowd.toFixed(0)}</span>
            <span className="leek-pill leek-pill--trap">套 {record.sub_scores.trap.toFixed(0)}</span>
          </div>
        </Tooltip>
      ),
    },
    {
      title: "风险状态",
      dataIndex: "risk_level",
      key: "risk_level",
      render: (level: keyof typeof RISK_BADGES) => {
        const badge = RISK_BADGES[level] || RISK_BADGES.normal;
        return (
          <Tooltip title={badge.desc}>
            <Tag color={badge.color}>{badge.label}</Tag>
          </Tooltip>
        );
      },
    },
    {
      title: "当日涨跌",
      dataIndex: "change_pct",
      key: "change_pct",
      sorter: (a, b) => a.change_pct - b.change_pct,
      render: (pct: number) => (
        <span
          className={`leek-change-val ${
            pct > 0 ? "leek-change-val--up" : pct < 0 ? "leek-change-val--down" : ""
          }`}
        >
          {pct > 0 ? `+${pct.toFixed(2)}%` : `${pct.toFixed(2)}%`}
        </span>
      ),
    },
    {
      title: "主力净流入",
      dataIndex: "main_net",
      key: "main_net",
      sorter: (a, b) => a.main_net - b.main_net,
      render: (v: number) => (
        <span className={`leek-diff-val ${v >= 0 ? "leek-diff-val--inflow" : "leek-diff-val--outflow"}`}>
          {formatAmount(v)}
        </span>
      ),
    },
    {
      title: "散户小单净买入",
      dataIndex: "retail_net",
      key: "retail_net",
      sorter: (a, b) => a.retail_net - b.retail_net,
      render: (v: number) => (
        <span className={`leek-diff-val ${v >= 0 ? "leek-diff-val--inflow" : "leek-diff-val--outflow"}`}>
          {formatAmount(v)}
        </span>
      ),
    },
    {
      title: "散户跟风/人气龙头",
      key: "crowded_stocks",
      render: (_, record) => {
        if (!record.crowded_stocks || record.crowded_stocks.length === 0) {
          return <span className="leek-empty-cell">-</span>;
        }
        return (
          <div>
            {record.crowded_stocks.map((stock) => (
              <Tooltip key={stock.code} title={`${stock.name} (${stock.code}) · 点击快速查看行情 · ${stock.reason || ""}`}>
                <Tag
                  className="leek-crowded-tag"
                  onClick={() => setPreviewStock({ code: stock.code, name: stock.name })}
                >
                  {stock.name}
                </Tag>
              </Tooltip>
            ))}
          </div>
        );
      },
    },
  ];

  return (
    <div className="leek-index-page">
      {/* 顶部标题区 */}
      <div className="leek-index-header">
        <div className="leek-index-header__title-group">
          <h2 className="leek-index-header__title">
            <FireOutlined className="leek-index-header__fire-icon" />
            A股行业韭菜指数看板
          </h2>
          <Tooltip title="通过资金剪刀差（主力出逃vs散户接盘）、东财股吧人气聚集、交易拥挤度及高位套牢盘四维合成的0-100逆向情绪与见顶风险指标。">
            <InfoCircleOutlined className="leek-index-header__info-icon" />
          </Tooltip>
        </div>

        <Space>
          <span className="leek-index-header__meta-time">
            截至交易日：{data?.trade_date || "-"} (更新于 {data?.updated_at || "-"})
          </span>
          <Button
            icon={<ReloadOutlined spin={isFetching || refreshMutation.isPending} />}
            onClick={() => refreshMutation.mutate()}
            loading={refreshMutation.isPending}
          >
            强制刷新
          </Button>
        </Space>
      </div>

      {/* 市场散户整体情绪诊断横幅 */}
      <div className="leek-summary-banner">
        <div className="leek-summary-metric">
          <div className="leek-summary-metric__label">全市场韭菜指数中位数</div>
          <div className="leek-summary-metric__val leek-summary-metric__val--blue">
            {data?.summary.median_score?.toFixed(1) || "-"}
            <span className="leek-summary-metric__unit">/ 100</span>
          </div>
        </div>

        <div className="leek-summary-metric">
          <div className="leek-summary-metric__label">🔥 极度接盘区行业</div>
          <div className="leek-summary-metric__val leek-summary-metric__val--red">
            {data?.summary.extreme_count ?? 0}
            <span className="leek-summary-metric__unit">个</span>
          </div>
        </div>

        <div className="leek-summary-metric">
          <div className="leek-summary-metric__label">⚠️ 散户过热追高行业</div>
          <div className="leek-summary-metric__val leek-summary-metric__val--orange">
            {data?.summary.fever_count ?? 0}
            <span className="leek-summary-metric__unit">个</span>
          </div>
        </div>

        <div className="leek-summary-metric">
          <div className="leek-summary-metric__label">💎 筹码出清/冷门行业</div>
          <div className="leek-summary-metric__val leek-summary-metric__val--green">
            {data?.summary.safe_count ?? 0}
            <span className="leek-summary-metric__unit">个</span>
          </div>
        </div>

        <div className="leek-summary-sentiment-text">
          <strong>情绪诊断：</strong> {data?.summary.market_sentiment_label || "正在计算全市场散户情绪特征..."}
        </div>
      </div>

      {/* 四象限矩阵可视化板块 */}
      <div className="leek-quadrant-section">
        <div className="leek-quadrant-header">
          <div className="leek-quadrant-title">
            <DotChartOutlined />
            <span>行业博弈四象限矩阵</span>
            <span className="leek-quadrant-desc">
              （涨跌幅 vs 资金剪刀差 · 气泡大小与颜色反映韭菜指数）
            </span>
          </div>
          <Button
            size="small"
            type="text"
            icon={showQuadrant ? <UpOutlined /> : <DownOutlined />}
            onClick={() => setShowQuadrant((prev) => !prev)}
          >
            {showQuadrant ? "收起矩阵" : "展开矩阵"}
          </Button>
        </div>
        {showQuadrant && (
          <LeekQuadrantChart
            industries={filteredIndustries}
            onSelectIndustry={(ind) => handleSelectIndustry(ind)}
          />
        )}
      </div>

      {/* 行业表格或移动端卡片流 */}
      <div className="leek-table-card">
        <div className="leek-table-toolbar">
          <div className="leek-table-filters-row">
            <Radio.Group
              value={filterLevel}
              onChange={(e) => setFilterLevel(e.target.value)}
              size="small"
            >
              <Radio.Button value="all">全部 (31)</Radio.Button>
              <Radio.Button value="extreme">🔥 极度接盘</Radio.Button>
              <Radio.Button value="fever">⚠️ 过热追高</Radio.Button>
              <Radio.Button value="normal">⚖️ 筹码均衡</Radio.Button>
              <Radio.Button value="safe">💎 筹码出清</Radio.Button>
            </Radio.Group>

            <Space size={6} className="leek-quick-presets">
              <span className="leek-preset-label">快捷预设:</span>
              <Tag.CheckableTag
                checked={quickPreset === "all"}
                onChange={() => setQuickPreset("all")}
              >
                默认全部
              </Tag.CheckableTag>
              <Tag.CheckableTag
                checked={quickPreset === "top_risk"}
                onChange={(checked) => setQuickPreset(checked ? "top_risk" : "all")}
              >
                🔥 见顶预警(&gt;70且上涨)
              </Tag.CheckableTag>
              <Tag.CheckableTag
                checked={quickPreset === "bargain"}
                onChange={(checked) => setQuickPreset(checked ? "bargain" : "all")}
              >
                💎 黄金坑探底(&lt;40且下跌)
              </Tag.CheckableTag>
              <Tag.CheckableTag
                checked={quickPreset === "smart_inflow"}
                onChange={(checked) => setQuickPreset(checked ? "smart_inflow" : "all")}
              >
                🚀 主力拉升散户下车
              </Tag.CheckableTag>
            </Space>
          </div>

          <Space className="leek-table-actions">
            <Input
              placeholder="搜索一级/二级行业或热门股票..."
              prefix={<SearchOutlined />}
              className="leek-table-search-input"
              size="small"
              value={searchKw}
              onChange={(e) => setSearchKw(e.target.value)}
              allowClear
            />
            <Button
              icon={<DownloadOutlined />}
              size="small"
              onClick={handleExportCsv}
            >
              导出 CSV
            </Button>
          </Space>
        </div>

        {isMobile ? (
          <div className="leek-mobile-card-list">
            {filteredIndustries.length === 0 ? (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无符合条件的行业数据" />
            ) : (
              filteredIndustries.map((item, idx) => (
                <div
                  key={item.industry_name}
                  className="leek-mobile-card"
                  onClick={() => handleSelectIndustry(item)}
                >
                  <div className="leek-mobile-card-header">
                    <div className="leek-mobile-card-title">
                      <span className="leek-mobile-rank">#{idx + 1}</span>
                      <span className="leek-mobile-name">{item.industry_name}</span>
                      <Tag color={RISK_BADGES[item.risk_level as keyof typeof RISK_BADGES]?.color}>
                        {RISK_BADGES[item.risk_level as keyof typeof RISK_BADGES]?.label}
                      </Tag>
                    </div>
                    <span
                      className={`leek-change-val ${
                        item.change_pct > 0
                          ? "leek-change-val--up"
                          : item.change_pct < 0
                          ? "leek-change-val--down"
                          : ""
                      }`}
                    >
                      {item.change_pct > 0 ? `+${item.change_pct.toFixed(2)}%` : `${item.change_pct.toFixed(2)}%`}
                    </span>
                  </div>

                  <div className="leek-mobile-card-body">
                    <div className="leek-mobile-score-wrap">
                      <span className="leek-mobile-label">韭菜指数:</span>
                      <span className={`leek-score-num ${getScoreColorClass(item.leek_score)}`}>
                        {item.leek_score.toFixed(1)}
                      </span>
                      <Progress
                        percent={item.leek_score}
                        strokeColor={
                          item.leek_score >= 75
                            ? "#ef4444"
                            : item.leek_score >= 60
                            ? "#f59e0b"
                            : item.leek_score >= 35
                            ? "#3b82f6"
                            : "#10b981"
                        }
                        showInfo={false}
                        size="small"
                        className="leek-score-progress"
                      />
                    </div>

                    <div className="leek-mobile-flow-row">
                      <span>
                        主力:{" "}
                        <strong className={item.main_net >= 0 ? "leek-diff-val--inflow" : "leek-diff-val--outflow"}>
                          {formatAmount(item.main_net)}
                        </strong>
                      </span>
                      <span>
                        散户:{" "}
                        <strong className={item.retail_net >= 0 ? "leek-diff-val--inflow" : "leek-diff-val--outflow"}>
                          {formatAmount(item.retail_net)}
                        </strong>
                      </span>
                    </div>

                    {item.crowded_stocks.length > 0 && (
                      <div className="leek-mobile-stocks">
                        {item.crowded_stocks.map((stock) => (
                          <span key={stock.code} className="leek-mobile-stock-badge">
                            {stock.name}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        ) : (
          <Table
            dataSource={filteredIndustries}
            columns={columns}
            rowKey="industry_name"
            loading={isLoading}
            pagination={false}
            size="middle"
            expandable={{
              expandedRowRender: (record) => {
                if (!record.sub_industries || record.sub_industries.length === 0) {
                  return <div className="leek-sub-table-empty">暂无二级行业资金明细</div>;
                }
                return (
                  <div className="leek-sub-table-wrap">
                    <div className="leek-sub-table-header">
                      <span>申万二级行业 ({record.sub_industries.length}个)</span>
                      <span className="leek-sub-table-header-tip">点击一级行业行即可在右侧查看历史曲线与详细分析</span>
                    </div>
                    <div className="leek-sub-grid">
                      {record.sub_industries.map((sub) => (
                        <div key={sub.name} className="leek-sub-card">
                          <div className="leek-sub-card-top">
                            <strong className="leek-sub-card-name">{sub.name}</strong>
                            <span className={`leek-diff-val ${sub.change_pct >= 0 ? "leek-diff-val--inflow" : "leek-diff-val--outflow"}`}>
                              {sub.change_pct >= 0 ? "+" : ""}{sub.change_pct.toFixed(2)}%
                            </span>
                          </div>
                          <div className="leek-sub-card-bottom">
                            <span className="leek-sub-card-score">
                              指数: <strong>{sub.leek_score.toFixed(1)}</strong>
                            </span>
                            <span className="leek-sub-card-flow">
                              主力: {formatAmount(sub.main_net)} / 散户: {formatAmount(sub.retail_net)}
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                );
              },
              rowExpandable: (record) => Boolean(record.sub_industries && record.sub_industries.length > 0),
            }}
          />
        )}
      </div>

      {/* 选中行业详情与历史时序抽屉 */}
      <Drawer
        title={
          selectedIndustry ? (
            <span>
              <strong>{selectedIndustry.industry_name}</strong> · 散户博弈与韭菜指数详情
            </span>
          ) : (
            "行业详情"
          )
        }
        open={Boolean(selectedIndustry)}
        onClose={() => handleSelectIndustry(null)}
        size="large"
      >
        {selectedIndustry && (
          <div className="leek-drawer-body">
            <Card size="small" title="四维度因子得分分解">
              <div className="leek-factor-list">
                <div>
                  <div className="leek-factor-row">
                    <span>资金流背离（主力跑/散户买剪刀差）</span>
                    <strong>{selectedIndustry.sub_scores.flow.toFixed(1)}</strong>
                  </div>
                  <Progress percent={selectedIndustry.sub_scores.flow} strokeColor="#ef4444" size="small" />
                </div>

                <div>
                  <div className="leek-factor-row">
                    <span>东财股吧舆论与新粉丝聚集度</span>
                    <strong>{selectedIndustry.sub_scores.guba.toFixed(1)}</strong>
                  </div>
                  <Progress percent={selectedIndustry.sub_scores.guba} strokeColor="#f59e0b" size="small" />
                </div>

                <div>
                  <div className="leek-factor-row">
                    <span>成交拥挤度与投机集中度</span>
                    <strong>{selectedIndustry.sub_scores.crowd.toFixed(1)}</strong>
                  </div>
                  <Progress percent={selectedIndustry.sub_scores.crowd} strokeColor="#3b82f6" size="small" />
                </div>

                <div>
                  <div className="leek-factor-row">
                    <span>高位滞涨与套牢盘沉重度</span>
                    <strong>{selectedIndustry.sub_scores.trap.toFixed(1)}</strong>
                  </div>
                  <Progress percent={selectedIndustry.sub_scores.trap} strokeColor="#8b5cf6" size="small" />
                </div>
              </div>
            </Card>

            {selectedIndustry.warning_signals.length > 0 && (
              <Card size="small" title="异动与预警特征">
                <div className="leek-warning-list">
                  {selectedIndustry.warning_signals.map((sig, i) => (
                    <div key={i} className="leek-warning-item">
                      <WarningOutlined />
                      <span>{sig}</span>
                    </div>
                  ))}
                </div>
              </Card>
            )}

            {selectedIndustry.sub_industries && selectedIndustry.sub_industries.length > 0 && (
              <Card size="small" title="申万二级细分行业分布与风险">
                <div className="leek-sub-ind-list">
                  {selectedIndustry.sub_industries.map((sub) => (
                    <div key={sub.name} className="leek-sub-ind-item">
                      <div className="leek-sub-ind-meta">
                        <strong className="leek-sub-ind-name">{sub.name}</strong>
                        <span className="leek-sub-ind-pct">
                          {sub.change_pct >= 0 ? "+" : ""}{sub.change_pct.toFixed(2)}%
                        </span>
                      </div>
                      <div className="leek-sub-ind-scores">
                        <span className="leek-sub-ind-score">
                          指数: <strong>{sub.leek_score.toFixed(1)}</strong>
                        </span>
                        <span className="leek-sub-ind-flow">
                          主力: {formatAmount(sub.main_net)} / 散户: {formatAmount(sub.retail_net)}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </Card>
            )}

            <Card size="small" title="散户集中跟风标的">
              {selectedIndustry.crowded_stocks.length === 0 ? (
                <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无显著散户聚焦标的" />
              ) : (
                <div className="leek-crowded-list">
                  {selectedIndustry.crowded_stocks.map((stock) => (
                    <div key={stock.code} className="leek-crowded-item">
                      <div>
                        <strong>{stock.name}</strong> ({stock.code})
                        {stock.reason && (
                          <span className="leek-crowded-reason">
                            {stock.reason}
                          </span>
                        )}
                      </div>
                      <Space size="small">
                        <Button
                          type="link"
                          size="small"
                          onClick={() => setPreviewStock({ code: stock.code, name: stock.name })}
                        >
                          看盘 &gt;
                        </Button>
                        <Button
                          type="link"
                          size="small"
                          onClick={() => navigate(`/analysis/${stock.code}`)}
                        >
                          深度分析 &gt;
                        </Button>
                      </Space>
                    </div>
                  ))}
                </div>
              )}
            </Card>

            <Card size="small" title="历史归档走势记录">
              {historyQuery.isLoading ? (
                <div className="leek-history-loading">加载历史时序中...</div>
              ) : !historyQuery.data?.history.length ? (
                <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无历史归档数据" />
              ) : (
                <div className="leek-history-list">
                  {historyQuery.data.history.map((pt) => (
                    <div key={pt.date} className="leek-history-item">
                      <span className="font-mono">{pt.date}</span>
                      <span className="leek-history-score">韭菜指数: {pt.score.toFixed(1)}</span>
                      <span>涨跌: {pt.industry_change_pct != null ? `${pt.industry_change_pct}%` : "-"}</span>
                    </div>
                  ))}
                </div>
              )}
            </Card>
          </div>
        )}
      </Drawer>

      {previewStock ? (
        <StockWorkspaceDrawer
          open={Boolean(previewStock)}
          code={previewStock.code}
          name={previewStock.name}
          onClose={() => setPreviewStock(null)}
        />
      ) : null}
    </div>
  );
}
