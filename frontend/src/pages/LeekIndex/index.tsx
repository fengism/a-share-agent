import { useState, useMemo } from "react";
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
} from "antd";
import type { ColumnsType } from "antd/es/table";
import {
  FireOutlined,
  ReloadOutlined,
  SearchOutlined,
  InfoCircleOutlined,
  WarningOutlined,
} from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import {
  useLeekIndexOverview,
  useIndustryLeekHistory,
  useRefreshLeekIndex,
  type IndustryLeekItem,
} from "../../api/queryHooks/sentiment";
import "./leek-index.css";

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

export default function LeekIndexPage() {
  const navigate = useNavigate();
  const [filterLevel, setFilterLevel] = useState<string>("all");
  const [searchKw, setSearchKw] = useState<string>("");
  const [selectedIndustry, setSelectedIndustry] = useState<IndustryLeekItem | null>(null);

  const { data, isLoading, isFetching } = useLeekIndexOverview();
  const refreshMutation = useRefreshLeekIndex();

  const historyQuery = useIndustryLeekHistory(
    selectedIndustry?.industry_name ?? "",
    30
  );

  const filteredIndustries = useMemo(() => {
    if (!data?.industries) return [];
    return data.industries.filter((item) => {
      const matchLevel = filterLevel === "all" || item.risk_level === filterLevel;
      const matchKw =
        !searchKw.trim() ||
        item.industry_name.includes(searchKw.trim()) ||
        item.crowded_stocks.some((s) => s.name.includes(searchKw.trim()) || s.code.includes(searchKw.trim()));
      return matchLevel && matchKw;
    });
  }, [data?.industries, filterLevel, searchKw]);

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
          onClick={() => setSelectedIndustry(record)}
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
      width: 220,
      render: (score: number) => {
        let strokeColor = "#10b981";
        if (score >= 75) strokeColor = "#ef4444";
        else if (score >= 60) strokeColor = "#f59e0b";
        else if (score >= 35) strokeColor = "#3b82f6";
        return (
          <div className="leek-score-cell">
            <span className="leek-score-num" style={{ color: strokeColor }}>
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
              <Tooltip key={stock.code} title={`${stock.name} (${stock.code}) · ${stock.reason || ""}`}>
                <Tag
                  className="leek-crowded-tag"
                  onClick={() => navigate(`/analysis/${stock.code}`)}
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

      {/* 行业表格 */}
      <div className="leek-table-card">
        <div className="leek-table-toolbar">
          <Radio.Group
            value={filterLevel}
            onChange={(e) => setFilterLevel(e.target.value)}
            size="small"
          >
            <Radio.Button value="all">全部行业 (31)</Radio.Button>
            <Radio.Button value="extreme">🔥 极度接盘</Radio.Button>
            <Radio.Button value="fever">⚠️ 过热追高</Radio.Button>
            <Radio.Button value="normal">⚖️ 筹码均衡</Radio.Button>
            <Radio.Button value="safe">💎 筹码出清</Radio.Button>
          </Radio.Group>

          <Input
            placeholder="搜索行业或热门跟风股票..."
            prefix={<SearchOutlined />}
            className="leek-table-search-input"
            size="small"
            value={searchKw}
            onChange={(e) => setSearchKw(e.target.value)}
            allowClear
          />
        </div>

        <Table
          dataSource={filteredIndustries}
          columns={columns}
          rowKey="industry_name"
          loading={isLoading}
          pagination={false}
          size="middle"
        />
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
        onClose={() => setSelectedIndustry(null)}
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
                      <Button
                        type="link"
                        size="small"
                        onClick={() => navigate(`/analysis/${stock.code}`)}
                      >
                        深度分析 &gt;
                      </Button>
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
    </div>
  );
}
