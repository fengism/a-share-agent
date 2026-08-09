import { useCallback, useMemo, useState } from "react";
import { Button, Card, Col, DatePicker, Empty, Modal, Row, Table, Tag } from "antd";
import dayjs, { type Dayjs } from "dayjs";
import { Link } from "react-router-dom";
import type { ColumnsType } from "antd/es/table";
import { useDragonTigerDetail, useDragonTigerList } from "../../api/queries";
import ChangeValue from "../../components/ChangeValue";
import ResponsiveMetricGrid from "../../components/ResponsiveMetricGrid";
import SectionDataState from "../../components/SectionDataState";
import { useMediaQuery } from "../../hooks/useMediaQuery";
import type { DragonTigerDetail, DragonTigerItem } from "../../types/stock";
import {
  changeColor,
  formatNumber,
  formatRatioPercent,
  formatSignedPercent,
  formatWanAmount,
} from "../../utils/format";
import { useColors } from "../../styles/ui";

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
  const { data, isLoading, error, refetch } = useDragonTigerDetail(code, reportDate);
  const hasData = (data?.length ?? 0) > 0;
  const buyItems = useMemo(() => (data || []).filter((item) => item.side === "buy").slice(0, 5), [data]);
  const sellItems = useMemo(() => (data || []).filter((item) => item.side === "sell").slice(0, 5), [data]);

  const buyColumns: ColumnsType<DragonTigerDetail> = useMemo(() => [
    { title: "买入营业部", dataIndex: "operate_name", ellipsis: true, width: 220 },
    {
      title: "买入(万)",
      dataIndex: "buy_amount",
      width: 100,
      align: "right",
      render: (value: number | null) => formatNumber(value),
    },
    {
      title: "占总额比",
      dataIndex: "buy_ratio",
      width: 80,
      align: "right",
      render: (value: number | null) => formatRatioPercent(value, 2),
    },
  ], []);
  const sellColumns: ColumnsType<DragonTigerDetail> = useMemo(() => [
    { title: "卖出营业部", dataIndex: "operate_name", ellipsis: true, width: 220 },
    {
      title: "卖出(万)",
      dataIndex: "sell_amount",
      width: 100,
      align: "right",
      render: (value: number | null) => formatNumber(value),
    },
    {
      title: "占总额比",
      dataIndex: "sell_ratio",
      width: 80,
      align: "right",
      render: (value: number | null) => formatRatioPercent(value, 2),
    },
  ], []);

  return (
    <Modal
      title={<span>龙虎榜明细 — <Link to={`/analysis/${code}`}>{name}</Link> ({code}) {reportDate}</span>}
      open={open}
      onCancel={onClose}
      footer={null}
      width={760}
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
            <div style={{ fontWeight: 600, marginBottom: 8, color: c.up }}>
              买入前5
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
            <div style={{ fontWeight: 600, marginBottom: 8, color: c.down }}>
              卖出前5
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
  const isNarrow = useMediaQuery("(max-width: 768px)");
  const [date, setDate] = useState<Dayjs>(dayjs().subtract(1, "day"));
  const reportDate = date.format("YYYY-MM-DD");
  const [detailCode, setDetailCode] = useState<string | null>(null);
  const [detailName, setDetailName] = useState("");
  const { data, isLoading, error, refetch } = useDragonTigerList(reportDate);
  const hasData = (data?.length ?? 0) > 0;

  const openDetail = useCallback((record: DragonTigerItem) => {
    setDetailCode(record.code);
    setDetailName(record.name);
  }, []);

  const columns: ColumnsType<DragonTigerItem> = useMemo(() => {
    if (isNarrow) {
      return [
        {
          title: "股票",
          key: "stock",
          width: 132,
          render: (_: unknown, record: DragonTigerItem) => (
            <Link to={`/analysis/${record.code}`} style={{ display: "block", color: c.primary }}>
              <span style={{ display: "block", color: c.textPrimary, fontWeight: 600 }}>{record.name}</span>
              <span style={{ display: "block", color: c.textMuted, fontSize: 11 }}>{record.code}</span>
            </Link>
          ),
        },
        {
          title: "涨跌幅",
          dataIndex: "change_pct",
          width: 82,
          align: "right",
          render: (value: number | null) => <ChangeValue value={value} fontWeight={500} />,
        },
        {
          title: "净额(万)",
          dataIndex: "net_amount",
          width: 88,
          align: "right",
          render: (value: number | null) => value == null ? "-" : (
            <span style={{ color: changeColor(value, c), fontWeight: 600 }}>
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
      width: 85,
      render: (code: string) => (
        <Link to={`/analysis/${code}`} style={{ color: c.primary, fontWeight: 500 }}>
          {code}
        </Link>
      ),
    },
    { title: "名称", dataIndex: "name", width: 90, ellipsis: true },
    {
      title: "收盘价",
      dataIndex: "close",
      width: 75,
      align: "right",
      render: (value: number | null) => formatNumber(value),
    },
    {
      title: "涨跌幅",
      dataIndex: "change_pct",
      width: 80,
      align: "right",
      render: (value: number | null) => <ChangeValue value={value} fontWeight={500} />,
    },
    {
      title: "上榜原因",
      dataIndex: "reason",
      width: 160,
      ellipsis: true,
      render: (value: string) => value ? <Tag style={{ fontSize: 11 }}>{value}</Tag> : "-",
    },
    {
      title: "买入额(万)",
      dataIndex: "buy_amount",
      width: 95,
      align: "right",
      render: (value: number | null) => (
        <span style={{ color: c.up }}>{value?.toFixed(0) ?? "-"}</span>
      ),
    },
    {
      title: "卖出额(万)",
      dataIndex: "sell_amount",
      width: 95,
      align: "right",
      render: (value: number | null) => (
        <span style={{ color: c.down }}>{value?.toFixed(0) ?? "-"}</span>
      ),
    },
    {
      title: "净额(万)",
      dataIndex: "net_amount",
      width: 95,
      align: "right",
      render: (value: number | null) =>
        value == null ? (
          "-"
        ) : (
          <span style={{ color: changeColor(value, c), fontWeight: 600 }}>
            {value > 0 ? "+" : ""}{value.toFixed(0)}
          </span>
        ),
    },
    {
      title: "成交额",
      dataIndex: "deal_amount",
      width: 90,
      align: "right",
      render: (value: number | null) => formatWanAmount(value),
    },
    {
      title: "占成交比",
      dataIndex: "deal_amount_rate",
      width: 80,
      align: "right",
      render: (value: number | null) => formatRatioPercent(value),
    },
    {
      title: "换手率",
      dataIndex: "turnover_pct",
      width: 70,
      align: "right",
      render: (value: number | null) => formatSignedPercent(value).replace("+", ""),
    },
    {
      title: "次日后",
      dataIndex: "d1_chg",
      width: 70,
      align: "right",
      render: (value: number | null) => <ChangeValue value={value} fontWeight={400} />,
    },
    {
      title: "2日后",
      dataIndex: "d2_chg",
      width: 70,
      align: "right",
      render: (value: number | null) => <ChangeValue value={value} fontWeight={400} />,
    },
    {
      title: "5日后",
      dataIndex: "d5_chg",
      width: 70,
      align: "right",
      render: (value: number | null) => <ChangeValue value={value} fontWeight={400} />,
    },
    {
      title: "明细",
      key: "detail",
      width: 60,
      align: "center",
      render: (_: unknown, record: DragonTigerItem) => (
        <Button
          type="link"
          size="small"
          onClick={() => openDetail(record)}
        >
          查看
        </Button>
      ),
    },
    ];
  }, [c, isNarrow, openDetail]);

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
        { key: "d1", label: "次日后", value: <ChangeValue value={record.d1_chg} fontWeight={400} /> },
        { key: "d2", label: "2日后", value: <ChangeValue value={record.d2_chg} fontWeight={400} /> },
        { key: "d5", label: "5日后", value: <ChangeValue value={record.d5_chg} fontWeight={400} /> },
        {
          key: "detail",
          label: "营业部明细",
          value: <Button type="link" size="small" onClick={() => openDetail(record)}>查看</Button>,
        },
      ]}
    />
  ), [openDetail]);

  return (
    <>
      <Card
        size="small"
        style={{
          marginBottom: embedded ? 12 : 16,
          borderRadius: 10,
          border: "none",
          boxShadow: "0 1px 4px rgba(0,0,0,0.04)",
        }}
        styles={{ body: { padding: embedded ? undefined : isNarrow ? "12px" : "16px 24px" } }}
      >
        <Row justify="space-between" align="middle" gutter={[12, 8]}>
          <Col xs={24} sm={12}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontWeight: 500, whiteSpace: "nowrap" }}>报告日期：</span>
            <DatePicker
              value={date}
              onChange={(value) => value && setDate(value)}
              allowClear={false}
              format="YYYY-MM-DD"
              style={{ width: isNarrow ? "100%" : undefined }}
            />
            </div>
          </Col>
          <Col xs={24} sm={12} style={{ textAlign: isNarrow ? "left" : "right" }}>
            {embedded && <Tag color="orange">东方财富</Tag>}
            <span style={{ color: c.textSecondary, fontSize: 12, marginLeft: embedded ? 8 : 0 }}>
              {data ? `共 ${data.length} 只股票上榜` : "等待榜单数据"}
            </span>
          </Col>
        </Row>
      </Card>
      <Card
        size="small"
        style={{
          borderRadius: 10,
          border: "none",
          boxShadow: "0 1px 4px rgba(0,0,0,0.04)",
        }}
        styles={{ body: { padding: "8px 16px" } }}
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
            size="small"
            pagination={false}
            expandable={isNarrow ? {
              expandedRowRender: renderExpandedRow,
              columnWidth: 38,
            } : undefined}
            scroll={isNarrow ? undefined : { x: "max-content" }}
          />
        </SectionDataState>
      </Card>

      {detailCode && (
        <DetailModal
          code={detailCode}
          name={detailName}
          reportDate={reportDate}
          open={!!detailCode}
          onClose={() => setDetailCode(null)}
        />
      )}
    </>
  );
}
