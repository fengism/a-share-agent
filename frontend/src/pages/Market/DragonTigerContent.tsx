import { useCallback, useMemo, useState } from "react";
import { Button, Card, Col, DatePicker, Empty, Modal, Row, Statistic, Table, Tag } from "antd";
import { SwapRightOutlined, ArrowUpOutlined, ArrowDownOutlined } from "@ant-design/icons";
import dayjs, { type Dayjs } from "dayjs";
import type { ColumnsType } from "antd/es/table";
import { useDragonTigerDetail, useDragonTigerList } from "../../api/queries";
import ChangeValue from "../../components/ChangeValue";
import ResponsiveMetricGrid from "../../components/ResponsiveMetricGrid";
import SectionDataState from "../../components/SectionDataState";
import StockExternalLink from "../../components/StockExternalLink";
import { useMediaQuery } from "../../hooks/useMediaQuery";
import type { DragonTigerDetail, DragonTigerItem } from "../../types/stock";
import {
  changeColor,
  formatNumber,
  formatRatioPercent,
  formatSignedPercent,
  formatWanAmount,
} from "../../utils/format";
import { useColors, useTokens, semanticTagStyle } from "../../styles/ui";

function DetailModal({
  code,
  name,
  reportDate,
  open,
  onClose,
}: {
  code: string;
  name: string;
  reportDate: string;
  open: boolean;
  onClose: () => void;
  }) {
  const c = useColors();
  const t = useTokens();
  const { data, isLoading, error, refetch } = useDragonTigerDetail(code, reportDate);
  const hasData = (data?.length ?? 0) > 0;
  const buyItems = useMemo(() => (data || []).filter((item) => item.side === "buy").slice(0, 5), [data]);
  const sellItems = useMemo(() => (data || []).filter((item) => item.side === "sell").slice(0, 5), [data]);

  const buyColumns: ColumnsType<DragonTigerDetail> = useMemo(() => [
    { title: "买入营业部", dataIndex: "operate_name", ellipsis: true, width: 240 },
    {
      title: "买入(万)",
      dataIndex: "buy_amount",
      width: 110,
      align: "right",
      render: (value: number | null) => (
        <span style={{ color: c.up, fontWeight: Number(t.weight.semibold), fontFamily: "monospace" }}>
          {formatNumber(value)}
        </span>
      ),
    },
    {
      title: "占总额比",
      dataIndex: "buy_ratio",
      width: 90,
      align: "right",
      render: (value: number | null) => (
        <span style={{ fontFamily: "monospace" }}>{formatRatioPercent(value, 2)}</span>
      ),
    },
  ], [c.up, t.weight.semibold]);

  const sellColumns: ColumnsType<DragonTigerDetail> = useMemo(() => [
    { title: "卖出营业部", dataIndex: "operate_name", ellipsis: true, width: 240 },
    {
      title: "卖出(万)",
      dataIndex: "sell_amount",
      width: 110,
      align: "right",
      render: (value: number | null) => (
        <span style={{ color: c.down, fontWeight: Number(t.weight.semibold), fontFamily: "monospace" }}>
          {formatNumber(value)}
        </span>
      ),
    },
    {
      title: "占总额比",
      dataIndex: "sell_ratio",
      width: 90,
      align: "right",
      render: (value: number | null) => (
        <span style={{ fontFamily: "monospace" }}>{formatRatioPercent(value, 2)}</span>
      ),
    },
  ], [c.down, t.weight.semibold]);

  return (
    <Modal
      title={
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <SwapRightOutlined style={{ transform: "rotate(90deg)", color: c.primary }} />
          <span>
            龙虎榜席位明细 — <StockExternalLink code={code} name={name}>{name}</StockExternalLink> ({code})
          </span>
          <Tag style={{ marginLeft: "auto", fontSize: t.font.xs }}>{reportDate}</Tag>
        </div>
      }
      open={open}
      onCancel={onClose}
      footer={null}
      width={780}
    >
      <SectionDataState
        isLoading={isLoading && !hasData}
        error={hasData ? undefined : error}
        onRetry={() => refetch()}
        isEmpty={!isLoading && !error && !hasData}
        emptyText="暂无营业部明细"
        errorTitle="龙虎榜明细加载失败"
        minHeight={240}
      >
        <Row gutter={[16, 20]}>
          <Col span={24}>
            <div style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              fontWeight: Number(t.weight.semibold),
              marginBottom: t.space[2],
              color: c.up,
            }}>
              <ArrowUpOutlined /> 买入前 5 席位
            </div>
            <Table
              columns={buyColumns}
              dataSource={buyItems}
              rowKey="operate_name"
              size="small"
              pagination={false}
              scroll={{ x: 400 }}
              locale={{
                emptyText: <Empty description="无数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />,
              }}
            />
          </Col>
          <Col span={24}>
            <div style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              fontWeight: Number(t.weight.semibold),
              marginBottom: t.space[2],
              color: c.down,
            }}>
              <ArrowDownOutlined /> 卖出前 5 席位
            </div>
            <Table
              columns={sellColumns}
              dataSource={sellItems}
              rowKey="operate_name"
              size="small"
              pagination={false}
              scroll={{ x: 400 }}
              locale={{
                emptyText: <Empty description="无数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />,
              }}
            />
          </Col>
        </Row>
      </SectionDataState>
    </Modal>
  );
}

export function DragonTigerContent({ embedded = false }: { embedded?: boolean }) {
  const c = useColors();
  const t = useTokens();
  const isNarrow = useMediaQuery("(max-width: 768px)");
  const [date, setDate] = useState<Dayjs>(dayjs().subtract(1, "day"));
  const reportDate = date.format("YYYY-MM-DD");
  const [detailCode, setDetailCode] = useState<string | null>(null);
  const [detailName, setDetailName] = useState("");
  const [detailReportDate, setDetailReportDate] = useState("");
  const { data, isLoading, error, refetch } = useDragonTigerList(reportDate);
  const hasData = (data?.length ?? 0) > 0;
  const actualReportDate = data?.find((item) => item.trade_date)?.trade_date || reportDate;
  const dateWasResolved = hasData && actualReportDate !== reportDate;

  const totalBuy = useMemo(() => (data || []).reduce((acc, cur) => acc + (cur.buy_amount || 0), 0), [data]);
  const totalSell = useMemo(() => (data || []).reduce((acc, cur) => acc + (cur.sell_amount || 0), 0), [data]);
  const totalNet = totalBuy - totalSell;

  const openDetail = useCallback((record: DragonTigerItem) => {
    setDetailCode(record.code);
    setDetailName(record.name);
    setDetailReportDate(record.trade_date || reportDate);
  }, [reportDate]);

  const columns: ColumnsType<DragonTigerItem> = useMemo(() => {
    if (isNarrow) {
      return [
        {
          title: "股票",
          key: "stock",
          width: 132,
          render: (_: unknown, record: DragonTigerItem) => (
            <StockExternalLink code={record.code} name={record.name} style={{ display: "block", color: c.primary }}>
              <span style={{ display: "block", color: c.textPrimary, fontWeight: Number(t.weight.semibold) }}>{record.name}</span>
              <span style={{ display: "block", color: c.textMuted, fontSize: t.font.xs, fontFamily: "monospace" }}>{record.code}</span>
            </StockExternalLink>
          ),
        },
        {
          title: "涨跌幅",
          dataIndex: "change_pct",
          width: 82,
          align: "right",
          render: (value: number | null) => <ChangeValue value={value} fontWeight={Number(t.weight.medium)} />,
        },
        {
          title: "净额(万)",
          dataIndex: "net_amount",
          width: 88,
          align: "right",
          render: (value: number | null) => value == null ? "-" : (
            <span style={{ color: changeColor(value, c), fontWeight: Number(t.weight.semibold), fontFamily: "monospace" }}>
              {value > 0 ? "+" : ""}{value.toFixed(0)}
            </span>
          ),
        },
      ];
    }

    return [
      {
        title: "代码",
        dataIndex: "code",
        width: 90,
        render: (code: string) => (
          <StockExternalLink code={code} style={{ color: c.primary, fontWeight: Number(t.weight.medium), fontFamily: "monospace" }}>
            {code}
          </StockExternalLink>
        ),
      },
      {
        title: "名称",
        dataIndex: "name",
        width: 110,
        ellipsis: true,
        render: (name: string, record) => (
          <StockExternalLink code={record.code} name={name} style={{ color: c.textPrimary, fontWeight: Number(t.weight.medium) }}>
            {name}
          </StockExternalLink>
        ),
      },
      {
        title: "收盘价",
        dataIndex: "close",
        width: 85,
        align: "right",
        render: (value: number | null) => <span style={{ fontFamily: "monospace" }}>{formatNumber(value)}</span>,
      },
      {
        title: "涨跌幅",
        dataIndex: "change_pct",
        width: 90,
        align: "right",
        sorter: (a, b) => (a.change_pct ?? 0) - (b.change_pct ?? 0),
        render: (value: number | null) => <ChangeValue value={value} fontWeight={Number(t.weight.medium)} />,
      },
      {
        title: "上榜原因",
        dataIndex: "reason",
        width: 180,
        ellipsis: true,
        render: (value: string) => value ? <Tag style={{ fontSize: t.font.xs, maxWidth: "100%", overflow: "hidden", textOverflow: "ellipsis" }}>{value}</Tag> : "-",
      },
      {
        title: "买入额(万)",
        dataIndex: "buy_amount",
        width: 105,
        align: "right",
        sorter: (a, b) => (a.buy_amount ?? 0) - (b.buy_amount ?? 0),
        render: (value: number | null) => (
          <span style={{ color: c.up, fontFamily: "monospace" }}>{value?.toFixed(0) ?? "-"}</span>
        ),
      },
      {
        title: "卖出额(万)",
        dataIndex: "sell_amount",
        width: 105,
        align: "right",
        sorter: (a, b) => (a.sell_amount ?? 0) - (b.sell_amount ?? 0),
        render: (value: number | null) => (
          <span style={{ color: c.down, fontFamily: "monospace" }}>{value?.toFixed(0) ?? "-"}</span>
        ),
      },
      {
        title: "净额(万)",
        dataIndex: "net_amount",
        width: 105,
        align: "right",
        defaultSortOrder: "descend",
        sorter: (a, b) => (a.net_amount ?? 0) - (b.net_amount ?? 0),
        render: (value: number | null) =>
          value == null ? (
            "-"
          ) : (
            <span style={{ color: changeColor(value, c), fontWeight: Number(t.weight.semibold), fontFamily: "monospace" }}>
              {value > 0 ? "+" : ""}{value.toFixed(0)}
            </span>
          ),
      },
      {
        title: "成交额",
        dataIndex: "deal_amount",
        width: 100,
        align: "right",
        render: (value: number | null) => <span style={{ fontFamily: "monospace" }}>{formatWanAmount(value)}</span>,
      },
      {
        title: "占成交比",
        dataIndex: "deal_amount_rate",
        width: 85,
        align: "right",
        render: (value: number | null) => <span style={{ fontFamily: "monospace" }}>{formatRatioPercent(value)}</span>,
      },
      {
        title: "换手率",
        dataIndex: "turnover_pct",
        width: 80,
        align: "right",
        render: (value: number | null) => <span style={{ fontFamily: "monospace" }}>{formatSignedPercent(value).replace("+", "")}</span>,
      },
      {
        title: "次日后",
        dataIndex: "d1_chg",
        width: 75,
        align: "right",
        render: (value: number | null) => <ChangeValue value={value} fontWeight={Number(t.weight.normal)} />,
      },
      {
        title: "2日后",
        dataIndex: "d2_chg",
        width: 75,
        align: "right",
        render: (value: number | null) => <ChangeValue value={value} fontWeight={Number(t.weight.normal)} />,
      },
      {
        title: "5日后",
        dataIndex: "d5_chg",
        width: 75,
        align: "right",
        render: (value: number | null) => <ChangeValue value={value} fontWeight={Number(t.weight.normal)} />,
      },
      {
        title: "明细",
        key: "detail",
        width: 70,
        align: "center",
        fixed: "right",
        render: (_: unknown, record: DragonTigerItem) => (
          <Button
            type="link"
            size="small"
            onClick={() => openDetail(record)}
          >
            席位
          </Button>
        ),
      },
    ];
  }, [c, t, isNarrow, openDetail]);

  const renderExpandedRow = useCallback((record: DragonTigerItem) => (
    <ResponsiveMetricGrid
      items={[
        { key: "reason", label: "上榜原因", value: record.reason || "-" },
        { key: "close", label: "收盘价", value: formatNumber(record.close) },
        { key: "buy", label: "买入额(万)", value: record.buy_amount?.toFixed(0) ?? "-" },
        { key: "sell", label: "卖出额(万)", value: record.sell_amount?.toFixed(0) ?? "-" },
        { key: "deal", label: "成交额", value: formatWanAmount(record.deal_amount) },
        { key: "deal-rate", label: "占成交比", value: formatRatioPercent(record.deal_amount_rate) },
        { key: "turnover", label: "换手率", value: formatSignedPercent(record.turnover_pct).replace("+", "") },
        { key: "d1", label: "次日后", value: <ChangeValue value={record.d1_chg} fontWeight={Number(t.weight.normal)} /> },
        { key: "d2", label: "2日后", value: <ChangeValue value={record.d2_chg} fontWeight={Number(t.weight.normal)} /> },
        { key: "d5", label: "5日后", value: <ChangeValue value={record.d5_chg} fontWeight={Number(t.weight.normal)} /> },
        {
          key: "detail",
          label: "营业部明细",
          value: <Button type="link" size="small" onClick={() => openDetail(record)}>查看</Button>,
        },
      ]}
    />
  ), [t, openDetail]);

  return (
    <>
      <div style={{ marginBottom: t.space[4] }}>
        <Row gutter={[16, 16]}>
          <Col xs={12} sm={6}>
            <Card size="small" style={{ borderRadius: t.radius.md, boxShadow: t.shadow.xs }}>
              <Statistic
                title={<span style={{ fontSize: t.font.sm, color: c.textSecondary }}>上榜股票数</span>}
                value={data?.length ?? 0}
                suffix="只"
                styles={{ content: { color: c.primary, fontWeight: Number(t.weight.bold) } }}
              />
            </Card>
          </Col>
          <Col xs={12} sm={6}>
            <Card size="small" style={{ borderRadius: t.radius.md, boxShadow: t.shadow.xs }}>
              <Statistic
                title={<span style={{ fontSize: t.font.sm, color: c.textSecondary }}>净买入总额 (万)</span>}
                value={totalNet >= 0 ? `+${(totalNet / 1).toFixed(0)}` : (totalNet / 1).toFixed(0)}
                styles={{ content: { color: totalNet >= 0 ? c.up : c.down, fontWeight: Number(t.weight.bold) } }}
              />
            </Card>
          </Col>
          <Col xs={12} sm={6}>
            <Card size="small" style={{ borderRadius: t.radius.md, boxShadow: t.shadow.xs }}>
              <Statistic
                title={<span style={{ fontSize: t.font.sm, color: c.textSecondary }}>总买入额 (万)</span>}
                value={(totalBuy / 1).toFixed(0)}
                styles={{ content: { color: c.up, fontWeight: Number(t.weight.bold) } }}
              />
            </Card>
          </Col>
          <Col xs={12} sm={6}>
            <Card size="small" style={{ borderRadius: t.radius.md, boxShadow: t.shadow.xs }}>
              <Statistic
                title={<span style={{ fontSize: t.font.sm, color: c.textSecondary }}>总卖出额 (万)</span>}
                value={(totalSell / 1).toFixed(0)}
                styles={{ content: { color: c.down, fontWeight: Number(t.weight.bold) } }}
              />
            </Card>
          </Col>
        </Row>
      </div>

      <Card
        size="small"
        style={{
          marginBottom: embedded ? t.space[3] : t.space[4],
          borderRadius: t.radius.md,
          border: `1px solid ${c.border}`,
          boxShadow: t.shadow.xs,
        }}
        styles={{ body: { padding: isNarrow ? t.space[3] : `${t.space[3]} ${t.space[4]}` } }}
      >
        <Row justify="space-between" align="middle" gutter={[12, 8]}>
          <Col xs={24} sm={12}>
            <div style={{ display: "flex", alignItems: "center", gap: t.space[2] }}>
              <span style={{ fontWeight: Number(t.weight.medium), whiteSpace: "nowrap" }}>报告日期：</span>
              <DatePicker
                value={date}
                onChange={(value) => value && setDate(value)}
                allowClear={false}
                format="YYYY-MM-DD"
                style={{ width: isNarrow ? "100%" : undefined }}
              />
              {dateWasResolved ? (
                <Tag color="warning">实际数据日期：{actualReportDate}</Tag>
              ) : null}
            </div>
          </Col>
          <Col xs={24} sm={12} style={{ textAlign: isNarrow ? "left" : "right" }}>
            {embedded && <Tag style={semanticTagStyle("primary")}>东方财富</Tag>}
            <span style={{ color: c.textSecondary, fontSize: t.font.sm, marginLeft: embedded ? t.space[2] : 0 }}>
              {data ? `共 ${data.length} 只股票上榜` : "等待榜单数据"}
            </span>
          </Col>
        </Row>
      </Card>

      <Card
        size="small"
        style={{
          borderRadius: t.radius.md,
          border: `1px solid ${c.border}`,
          boxShadow: t.shadow.xs,
        }}
        styles={{ body: { padding: t.space[3] } }}
      >
        <SectionDataState
          isLoading={isLoading && !hasData}
          error={hasData ? undefined : error}
          onRetry={() => refetch()}
          isEmpty={!isLoading && !error && !hasData}
          emptyText="当日无龙虎榜数据，请选择交易日"
          errorTitle="龙虎榜数据加载失败"
          minHeight={320}
        >
          <Table
            columns={columns}
            dataSource={data || []}
            rowKey={(record) => `${record.code}-${record.trade_date}-${record.reason}`}
            size="middle"
            pagination={{ pageSize: 20, showSizeChanger: false }}
            expandable={isNarrow ? {
              expandedRowRender: renderExpandedRow,
              columnWidth: 38,
            } : undefined}
            scroll={isNarrow ? undefined : { x: 1280 }}
          />
        </SectionDataState>
      </Card>

      {detailCode && (
        <DetailModal
          code={detailCode}
          name={detailName}
          reportDate={detailReportDate || actualReportDate}
          open={!!detailCode}
          onClose={() => setDetailCode(null)}
        />
      )}
    </>
  );
}
