import { useState } from "react";
import { Card, Col, DatePicker, Empty, Modal, Row, Table, Tag } from "antd";
import dayjs, { type Dayjs } from "dayjs";
import { useNavigate } from "react-router-dom";
import type { ColumnsType } from "antd/es/table";
import { useDragonTigerDetail, useDragonTigerList } from "../../api/queries";
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
  const { data, isLoading } = useDragonTigerDetail(code, reportDate);
  const buyItems = (data || []).filter((item) => item.side === "buy").slice(0, 5);
  const sellItems = (data || []).filter((item) => item.side === "sell").slice(0, 5);

  const buyColumns: ColumnsType<DragonTigerDetail> = [
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
  ];
  const sellColumns: ColumnsType<DragonTigerDetail> = [
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
  ];

  return (
    <Modal
      title={<span>龙虎榜明细 — <a>{name}</a> ({code}) {reportDate}</span>}
      open={open}
      onCancel={onClose}
      footer={null}
      width={700}
    >
      {isLoading ? (
        <div style={{ textAlign: "center", padding: 40 }}>加载中...</div>
      ) : (
        <Row gutter={16}>
          <Col xs={24} lg={12}>
            <div style={{ fontWeight: 600, marginBottom: 8, color: c.up }}>
              买入前5
            </div>
            <Table
              columns={buyColumns}
              dataSource={buyItems}
              rowKey="operate_name"
              size="small"
              pagination={false}
              locale={{
                emptyText: <Empty description="无数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />,
              }}
            />
          </Col>
          <Col xs={24} lg={12}>
            <div style={{ fontWeight: 600, marginBottom: 8, color: c.down }}>
              卖出前5
            </div>
            <Table
              columns={sellColumns}
              dataSource={sellItems}
              rowKey="operate_name"
              size="small"
              pagination={false}
              locale={{
                emptyText: <Empty description="无数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />,
              }}
            />
          </Col>
        </Row>
      )}
    </Modal>
  );
}

export function DragonTigerContent({ embedded = false }: { embedded?: boolean }) {
  const c = useColors();
  const navigate = useNavigate();
  const [date, setDate] = useState<Dayjs>(dayjs().subtract(1, "day"));
  const reportDate = date.format("YYYY-MM-DD");
  const [detailCode, setDetailCode] = useState<string | null>(null);
  const [detailName, setDetailName] = useState("");
  const { data, isLoading } = useDragonTigerList(reportDate);

  const columns: ColumnsType<DragonTigerItem> = [
    {
      title: "代码",
      dataIndex: "code",
      width: 85,
      render: (code: string) => (
        <a
          onClick={() => navigate(`/analysis/${code}`)}
          style={{ color: c.primary, fontWeight: 500 }}
        >
          {code}
        </a>
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
      render: (value: number | null) => (
        <span style={{ color: changeColor(value, c), fontWeight: 500 }}>
          {formatSignedPercent(value)}
        </span>
      ),
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
      render: (value: number | null) => (
        <span style={{ color: changeColor(value, c) }}>{formatSignedPercent(value)}</span>
      ),
    },
    {
      title: "2日后",
      dataIndex: "d2_chg",
      width: 70,
      align: "right",
      render: (value: number | null) => (
        <span style={{ color: changeColor(value, c) }}>{formatSignedPercent(value)}</span>
      ),
    },
    {
      title: "5日后",
      dataIndex: "d5_chg",
      width: 70,
      align: "right",
      render: (value: number | null) => (
        <span style={{ color: changeColor(value, c) }}>{formatSignedPercent(value)}</span>
      ),
    },
    {
      title: "明细",
      key: "detail",
      width: 60,
      align: "center",
      render: (_: unknown, record: DragonTigerItem) => (
        <a
          onClick={() => {
            setDetailCode(record.code);
            setDetailName(record.name);
          }}
        >
          查看
        </a>
      ),
    },
  ];

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
        styles={{ body: { padding: embedded ? undefined : "16px 24px" } }}
      >
        <Row justify="space-between" align="middle">
          <Col>
            <span style={{ marginRight: 12, fontWeight: 500 }}>报告日期：</span>
            <DatePicker
              value={date}
              onChange={(value) => value && setDate(value)}
              allowClear={false}
              format="YYYY-MM-DD"
            />
          </Col>
          <Col>
            {embedded && <Tag color="orange">东方财富</Tag>}
            <span style={{ color: c.textSecondary, fontSize: 12, marginLeft: embedded ? 8 : 0 }}>
              共 {data?.length ?? 0} 只股票上榜
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
        <Table
          columns={columns}
          dataSource={data || []}
          rowKey={(record) => `${record.code}-${record.trade_date}-${record.reason}`}
          loading={isLoading}
          size="small"
          pagination={false}
          locale={{ emptyText: <Empty description="当日无龙虎榜数据，请选择交易日" /> }}
          scroll={{ x: "max-content" }}
        />
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
