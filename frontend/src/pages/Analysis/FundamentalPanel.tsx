import { Card, Table, Tabs, Spin, Row, Col, Tag, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useFinancial } from "../../api/queries";
import type { AnalysisResult } from "../../types/stock";
import RatingBadge from "../../components/RatingBadge";
import { cardStyle, sectionHeaderStyle, tagStyle } from "../../styles/ui";
import { financialFieldLabels } from "../../utils/financialFieldLabels";

interface Props {
  code: string;
  analysis?: AnalysisResult | null;
}

const { Paragraph, Text } = Typography;

const financialFieldTokenLabels: Record<string, string> = {
  NOTE: "票据",
  ACCOUNTS: "账款",
  RECE: "应收",
  PAYABLE: "应付",
  RECEIVABLES: "应收款项",
  ADVANCE: "预收",
  INVENTORY: "存货",
  CASH: "现金",
  CCE: "现金及现金等价物",
  NETCASH: "现金流净额",
  OPERATE: "经营",
  INVEST: "投资",
  FINANCE: "筹资",
  INCOME: "收入",
  PROFIT: "利润",
  ASSET: "资产",
  ASSETS: "资产",
  LIAB: "负债",
  EQUITY: "权益",
  MONETARYFUNDS: "货币资金",
  PARENT: "归母",
  TOTAL: "总",
  BEGIN: "期初",
  END: "期末",
  RATE: "汇率",
  CHANGE: "变动",
  EFFECT: "影响",
  TAX: "税费",
  STAFF: "职工",
  SERVICES: "商品劳务",
  BOND: "债券",
  LOAN: "借款",
  LONG: "长期",
  SHORT: "短期",
  FIXED: "固定",
  INTANGIBLE: "无形",
  GOODWILL: "商誉",
  CONTRACT: "合同",
  LEASE: "租赁",
  CAPITAL: "资本",
  RESERVE: "公积",
  EPS: "每股收益",
  YOY: "同比",
  ADD: "增加额",
  REDUCE: "减少额",
  BALANCE: "平衡项",
  OTHER: "其他",
  NOTE_SUFFIX: "说明",
};

function formatFinancialFieldLabel(key: string) {
  if (financialFieldLabels[key]) {
    return financialFieldLabels[key];
  }
  if (!/^[A-Z0-9_]+$/.test(key)) {
    return key;
  }

  const suffixes = [
    [/_YOY$/, "同比"],
    [/_ADD$/, "增加额"],
    [/_REDUCE$/, "减少额"],
    [/_BALANCE$/, "平衡项"],
    [/_OTHER$/, "其他"],
    [/_NOTE$/, "说明"],
  ] as const;

  let baseKey = key;
  const suffixLabels: string[] = [];

  for (const [pattern, label] of suffixes) {
    if (pattern.test(baseKey)) {
      baseKey = baseKey.replace(pattern, "");
      suffixLabels.unshift(label);
    }
  }

  const tokens = baseKey.split("_").filter(Boolean);
  const translated = tokens.map((token) => financialFieldTokenLabels[token] || token);
  return [...translated, ...suffixLabels].join("");
}

function renderTags(items: string[] | undefined, color: string) {
  if (!items || items.length === 0) {
    return <Text type="secondary">暂无</Text>;
  }

  return items.map((item) => (
    <Tag key={item} color={color} style={tagStyle}>
      {item}
    </Tag>
  ));
}


export default function FundamentalPanel({ code, analysis }: Props) {
  const { data: balance, isLoading: l1 } = useFinancial(code, "balance");
  const { data: profit, isLoading: l2 } = useFinancial(code, "profit");
  const { data: cashflow, isLoading: l3 } = useFinancial(code, "cashflow");

  if (l1 || l2 || l3) return <Spin />;

  const renderTable = (data: Record<string, unknown>[] | undefined) => {
    if (!data || data.length === 0) return <div style={{ color: "#9ca3af", padding: 16 }}>暂无数据</div>;

    const filteredRecords = data.map((record) => {
      const entries = Object.entries(record)
        .map(([key, value]) => [formatFinancialFieldLabel(key), value] as const)
        .filter(([key]) => Boolean(key));
      return Object.fromEntries(entries);
    });

    const nonEmptyRows = filteredRecords.filter((record) =>
      Object.values(record).some((value) => value !== null && value !== undefined && value !== "" && value !== "N/A"),
    );

    if (nonEmptyRows.length === 0) {
      return <div style={{ color: "#9ca3af", padding: 16 }}>暂无数据</div>;
    }

    const visibleKeys = Object.keys(nonEmptyRows[0]).filter((key) =>
      nonEmptyRows.some((record) => {
        const value = record[key];
        return value !== null && value !== undefined && value !== "" && value !== "N/A";
      }),
    );

    const localizedData = nonEmptyRows.map((record) =>
      Object.fromEntries(visibleKeys.map((key) => [key, record[key]])),
    );

    const columns: ColumnsType<Record<string, unknown>> = visibleKeys.map((key) => {
      const align = key.includes("同比") || key.includes("率") || key.includes("金额") || key.includes("收入") || key.includes("利润") || key.includes("现金流") ? "right" : "left";
      return {
        title: <span style={{ fontSize: 12, fontWeight: 700, color: "#9ca3af", whiteSpace: "nowrap" }}>{key}</span>,
        dataIndex: key,
        key,
        width: 150,
        ellipsis: true,
        align,
        render: (v: unknown) => <span style={{ fontSize: 12, color: "#9ca3af", whiteSpace: "nowrap" }}>{v === "N/A" || v === null || v === undefined || v === "" ? "-" : String(v)}</span>,
      };
    });
    return (
      <div style={{ width: "100%", overflowX: "auto" }}>
        <Table
          dataSource={localizedData}
          columns={columns}
          rowKey={(record) => String(record.报告日期 ?? record.报告期名称 ?? record.报告期 ?? JSON.stringify(record))}
          size="small"
          scroll={{ x: "max-content" }}
          pagination={false}
          bordered={false}
          rowClassName={() => "terminal-table-row"}
        />
      </div>
    );
  };

  const items = [
    { key: "balance", label: "资产负债表", children: renderTable(balance) },
    { key: "profit", label: "利润表", children: renderTable(profit) },
    { key: "cashflow", label: "现金流量表", children: renderTable(cashflow) },
  ];


  return (
    <div style={{ display: "grid", gap: 16, width: "100%", minWidth: 0, overflowX: "hidden" }}>
      {analysis?.fundamental && (
        <Card
          size="small"
          style={{ ...cardStyle, marginBottom: 16, borderTop: "3px solid #1f3a5f" }}
          styles={{ body: { padding: 16 } }}
        >
          <Row gutter={[16, 16]} align="middle">
            <Col xs={24} sm={6} style={{ textAlign: "center" }}>
              <RatingBadge score={analysis.fundamental.score} size={64} />
              <div style={{ marginTop: 8, fontWeight: 600, color: "#e5e7eb" }}>基本面评分</div>
            </Col>
            <Col xs={24} sm={18}>
              <Paragraph style={{ marginBottom: 12, color: "#9ca3af", lineHeight: 1.8 }}>
                {analysis.fundamental.summary}
              </Paragraph>
              <div style={tagStyle}>
                <Text strong style={{ color: "#3b82f6" }}>核心优势：</Text>
              </div>
              <div style={{ marginBottom: 12 }}>
                {renderTags(analysis.fundamental.strengths, "blue")}
              </div>
              <div style={tagStyle}>
                <Text strong style={{ color: "#ff4d4f" }}>主要风险：</Text>
              </div>
              <div>
                {renderTags(analysis.fundamental.risks, "red")}
              </div>
            </Col>
          </Row>
        </Card>
      )}

      <div style={sectionHeaderStyle}>
        <Text strong style={{ color: "#e5e7eb", fontSize: 13 }}>三张报表</Text>
        <Text type="secondary" style={{ fontSize: 12 }}>按报告期查看明细</Text>
      </div>
      <div style={{ width: "100%", minWidth: 0, overflowX: "hidden" }}>
        <Tabs items={items} size="small" />
      </div>
    </div>
  );
}
