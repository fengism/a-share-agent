import { useState, useMemo } from "react";
import { Table, Tag, Input, Radio, Card, Space } from "antd";
import { SearchOutlined, FireOutlined } from "@ant-design/icons";
import { useCommoditySpotPrices } from "../../api/queries";
import SectionDataState from "../../components/SectionDataState";
import { useColors } from "../../styles/ui";
import type { CommodityItem } from "../../types/stock";

export default function CommoditiesTab() {
  const c = useColors();
  const [keyword, setKeyword] = useState("");
  const [selectedCategory, setSelectedCategory] = useState("all");
  const { data, isLoading, error, refetch } = useCommoditySpotPrices();

  const items = useMemo(() => data?.items ?? [], [data?.items]);

  const categories = useMemo(() => {
    const set = new Set<string>();
    items.forEach((item) => {
      if (item.category) set.add(item.category);
    });
    return Array.from(set);
  }, [items]);

  const filteredItems = useMemo(() => {
    return items.filter((item) => {
      const matchCat = selectedCategory === "all" || item.category === selectedCategory;
      const matchKw =
        !keyword ||
        item.name.toLowerCase().includes(keyword.toLowerCase()) ||
        item.symbol.toLowerCase().includes(keyword.toLowerCase()) ||
        item.contract.toLowerCase().includes(keyword.toLowerCase()) ||
        item.related_chains.some((ch) => ch.toLowerCase().includes(keyword.toLowerCase()));
      return matchCat && matchKw;
    });
  }, [items, selectedCategory, keyword]);

  const columns = [
    {
      title: "品种 / 合约",
      key: "symbol",
      render: (_: unknown, record: CommodityItem) => (
        <div>
          <div style={{ fontWeight: 600 }}>{record.name}</div>
          <div style={{ fontSize: 12, color: c.textSecondary }}>
            {record.symbol} · <Tag style={{ fontSize: 11 }}>{record.contract}</Tag>
          </div>
        </div>
      ),
    },
    {
      title: "分类",
      dataIndex: "category",
      key: "category",
      render: (cat: string) => {
        let color = "default";
        if (cat.includes("新能源")) color = "green";
        else if (cat.includes("有色")) color = "orange";
        else if (cat.includes("贵金属")) color = "gold";
        else if (cat.includes("黑色")) color = "volcano";
        else if (cat.includes("能化") || cat.includes("化工")) color = "blue";
        else if (cat.includes("农产品") || cat.includes("养殖")) color = "cyan";
        return <Tag color={color}>{cat}</Tag>;
      },
    },
    {
      title: "最新价",
      dataIndex: "latest_price",
      key: "latest_price",
      align: "right" as const,
      render: (val: number | null, record: CommodityItem) => (
        <div>
          <span className="financial-num" style={{ fontWeight: 600, fontSize: 14 }}>
            {val != null ? val.toLocaleString() : "-"}
          </span>
          <span style={{ fontSize: 11, color: c.textSecondary, marginLeft: 4 }}>{record.unit}</span>
        </div>
      ),
    },
    {
      title: "涨跌幅",
      dataIndex: "change_pct",
      key: "change_pct",
      align: "right" as const,
      sorter: (a: CommodityItem, b: CommodityItem) => (a.change_pct ?? 0) - (b.change_pct ?? 0),
      render: (pct: number | null) => {
        if (pct == null) return "-";
        const isUp = pct > 0;
        const isDown = pct < 0;
        const color = isUp ? c.up : isDown ? c.down : c.textSecondary;
        return (
          <span className="financial-num" style={{ color, fontWeight: 600 }}>
            {isUp ? `+${pct.toFixed(2)}` : pct.toFixed(2)}%
          </span>
        );
      },
    },
    {
      title: "日内区间 (低 - 高)",
      key: "range",
      align: "right" as const,
      render: (_: unknown, record: CommodityItem) => (
        <span className="financial-num" style={{ fontSize: 12, color: c.textSecondary }}>
          {record.low != null ? record.low.toLocaleString() : "-"} ~ {record.high != null ? record.high.toLocaleString() : "-"}
        </span>
      ),
    },
    {
      title: "关联产业链 / 映射赛道",
      dataIndex: "related_chains",
      key: "related_chains",
      render: (chains: string[]) => (
        <Space size={[0, 4]} wrap>
          {chains.map((chain) => (
            <Tag key={chain} style={{ fontSize: 12, borderRadius: 3 }}>
              {chain}
            </Tag>
          ))}
        </Space>
      ),
    },
    {
      title: "商品简介与传导逻辑",
      dataIndex: "description",
      key: "description",
      ellipsis: true,
      render: (desc: string) => <span style={{ fontSize: 12, color: c.textSecondary }}>{desc}</span>,
    },
  ];

  return (
    <SectionDataState
      isLoading={isLoading && !data}
      error={data ? undefined : error}
      onRetry={() => refetch()}
      isEmpty={!data || items.length === 0}
      emptyText="暂无大宗商品现货行情数据"
      errorTitle="大宗商品数据加载失败"
      minHeight={320}
    >
      <div className="macro-insight-banner">
        <div className="macro-insight-banner__title">
          <span><FireOutlined /> 核心大宗商品与工业原材料现货基差看板</span>
          <Tag color="geekblue">覆盖 {items.length} 大工业与民生基准品种</Tag>
        </div>
        <div className="macro-insight-banner__body">
          实时跟踪碳酸锂、工业硅、电解铜、铝、原油、生猪等大宗商品主力合约价格。上游原材料价格波动直接影响中下游制造产业链（电池电芯、光伏组件、电网特缆、养殖屠宰）的毛利率与盈利弹性。
        </div>
      </div>

      <Card size="small" variant="borderless" style={{ marginBottom: 16 }}>
        <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "space-between", gap: 12, alignItems: "center" }}>
          <Radio.Group
            value={selectedCategory}
            onChange={(e) => setSelectedCategory(e.target.value)}
            optionType="button"
            buttonStyle="solid"
            size="small"
          >
            <Radio.Button value="all">全部品种 ({items.length})</Radio.Button>
            {categories.map((cat) => (
              <Radio.Button key={cat} value={cat}>
                {cat}
              </Radio.Button>
            ))}
          </Radio.Group>

          <Input
            prefix={<SearchOutlined style={{ color: c.textSecondary }} />}
            placeholder="搜索品种名称、代码或产业链 (如: 碳酸锂、铜、储能)"
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            style={{ width: 300 }}
            size="small"
            allowClear
          />
        </div>
      </Card>

      <Table
        rowKey="contract"
        dataSource={filteredItems}
        columns={columns}
        pagination={{ pageSize: 12, showSizeChanger: true, showTotal: (t) => `共 ${t} 个品种` }}
        size="middle"
      />
    </SectionDataState>
  );
}
