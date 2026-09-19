import { useState } from "react";
import {
  Button,
  Card,
  Checkbox,
  Col,
  Descriptions,
  Drawer,
  Form,
  Input,
  Modal,
  Popconfirm,
  Progress,
  Row,
  Select,
  Space,
  Statistic,
  Table,
  Tag,
  Tooltip,
  Typography,
  Upload,
  message,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import type { UploadProps } from "antd";
import {
  BankOutlined,
  CalendarOutlined,
  DeleteOutlined,
  DownloadOutlined,
  EditOutlined,
  EyeOutlined,
  GlobalOutlined,
  ImportOutlined,
  PlusOutlined,
  ReloadOutlined,
  SearchOutlined,
  SyncOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";
import { Link } from "react-router-dom";
import { apiDownload } from "../../api/client";
import {
  useCreateStockProfileRecord,
  useDeleteStockProfileRecord,
  useEnrichStockProfileRecord,
  useImportStockProfiles,
  useStockProfileRecords,
  useStockProfileSummary,
  useSyncMasterStockProfiles,
  useUpdateStockProfileRecord,
} from "../../api/queries";
import type {
  StockBasicProfileInput,
  StockBasicProfileRecord,
  StockProfileImportFileRequest,
  StockProfileListFilters,
} from "../../api/stockProfile";
import "./stock-profile.css";

const { Paragraph, Text } = Typography;
const { TextArea } = Input;
const PAGE_SIZE = 50;
const MAX_IMPORT_FILE_SIZE = 50 * 1024 * 1024;

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "未知错误";
}

const BOARD_OPTIONS = [
  { value: "", label: "全部板块" },
  { value: "主板", label: "主板 (沪深)" },
  { value: "创业板", label: "创业板" },
  { value: "科创板", label: "科创板" },
  { value: "北交所", label: "北交所" },
  { value: "港股主板", label: "港股主板" },
];

const MARKET_OPTIONS = [
  { value: "", label: "全部市场" },
  { value: "A", label: "A 股" },
  { value: "HK", label: "港股" },
];

const BUSINESS_OPTIONS = [
  { value: "", label: "全部主营状态" },
  { value: "true", label: "已录入主营" },
  { value: "false", label: "待补充主营" },
];

const EMPTY_INPUT: StockBasicProfileInput = {
  market_group: "A",
  exchange: "SH",
  board: "主板",
  stock_code: "",
  stock_name: "",
  listing_date: "",
  main_business: "",
  business_scope: "",
  products: "",
  industry: "",
  sw_level1_name: "",
  sw_level2_name: "",
  sw_level3_name: "",
  city: "",
  province: "",
  legal_repr: "",
  registered_capital: "",
  setup_date: "",
  website: "",
  company_intro: "",
  source_version: "manual",
};

function boardTagColor(board?: string | null): string {
  switch (board) {
    case "科创板":
      return "cyan";
    case "创业板":
      return "orange";
    case "北交所":
      return "purple";
    case "港股主板":
      return "magenta";
    default:
      return "blue";
  }
}

export default function StockProfileTab() {
  const [filters, setFilters] = useState<StockProfileListFilters>({
    q: "",
    market_group: "",
    board: "",
    has_business: undefined,
    page: 1,
    page_size: PAGE_SIZE,
    sort_by: "stock_code",
    sort_order: "asc",
  });
  const [searchInput, setSearchInput] = useState("");
  const [activeRecord, setActiveRecord] = useState<StockBasicProfileRecord | null>(null);
  const [detailVisible, setDetailVisible] = useState(false);
  const [editModalVisible, setEditModalVisible] = useState(false);
  const [editingRecord, setEditingRecord] = useState<StockBasicProfileRecord | null>(null);
  const [form] = Form.useForm<StockBasicProfileInput>();
  const [importOpen, setImportOpen] = useState(false);
  const [importFile, setImportFile] = useState<Pick<StockProfileImportFileRequest, "filename" | "content_base64"> | null>(null);
  const [updateManual, setUpdateManual] = useState(false);
  const [readingFile, setReadingFile] = useState(false);
  const [exporting, setExporting] = useState(false);

  const { data: summary, isLoading: isSummaryLoading, refetch: refetchSummary } = useStockProfileSummary();
  const { data: recordsData, isLoading: isRecordsLoading, isFetching, refetch: refetchRecords } = useStockProfileRecords(filters);

  const createMutation = useCreateStockProfileRecord();
  const updateMutation = useUpdateStockProfileRecord();
  const deleteMutation = useDeleteStockProfileRecord();
  const enrichMutation = useEnrichStockProfileRecord();
  const syncMasterMutation = useSyncMasterStockProfiles();
  const importMutation = useImportStockProfiles();

  const handleExport = async () => {
    setExporting(true);
    try {
      await apiDownload("/stock-profile/records/export", "stock_profile_export.csv", {
        q: filters.q,
        market_group: filters.market_group,
        exchange: filters.exchange,
        board: filters.board,
      });
      message.success("导出完成");
    } catch (err) {
      message.error(`导出失败: ${errorMessage(err)}`);
    } finally {
      setExporting(false);
    }
  };

  const importUploadProps: UploadProps = {
    accept: ".csv,.xlsx,.xls",
    maxCount: 1,
    showUploadList: true,
    beforeUpload: (file) => {
      if (file.size > MAX_IMPORT_FILE_SIZE) {
        message.error("文件不能超过 50 MB");
        return Upload.LIST_IGNORE;
      }
      setReadingFile(true);
      const reader = new FileReader();
      reader.onload = () => {
        const result = String(reader.result || "");
        const base64 = result.includes(",") ? result.split(",")[1] : result;
        setImportFile({ filename: file.name, content_base64: base64 });
        setReadingFile(false);
      };
      reader.onerror = () => {
        setReadingFile(false);
        message.error("读取文件失败");
      };
      reader.readAsDataURL(file);
      return false;
    },
    onRemove: () => setImportFile(null),
  };

  const handleImportSubmit = () => {
    if (!importFile) return;
    importMutation.mutate(
      { ...importFile, update_manual: updateManual },
      {
        onSuccess: (result) => {
          message.success(
            `导入完成：新增 ${result.added}，更新 ${result.updated}，无变化 ${result.unchanged}，跳过 ${result.skipped}`,
          );
          setImportOpen(false);
          setImportFile(null);
        },
        onError: (error) => message.error(`导入失败：${errorMessage(error)}`),
      },
    );
  };

  const handleSearch = () => {
    setFilters((prev) => ({ ...prev, q: searchInput.trim(), page: 1 }));
  };

  const handleOpenDetail = (record: StockBasicProfileRecord) => {
    setActiveRecord(record);
    setDetailVisible(true);
  };

  const handleOpenCreate = () => {
    setEditingRecord(null);
    form.resetFields();
    form.setFieldsValue(EMPTY_INPUT);
    setEditModalVisible(true);
  };

  const handleOpenEdit = (record: StockBasicProfileRecord) => {
    setEditingRecord(record);
    form.resetFields();
    form.setFieldsValue({
      market_group: record.market_group,
      exchange: record.exchange,
      board: record.board,
      stock_code: record.stock_code,
      stock_name: record.stock_name,
      listing_date: record.listing_date || "",
      main_business: record.main_business,
      business_scope: record.business_scope,
      products: record.products,
      industry: record.industry,
      sw_level1_name: record.sw_level1_name,
      sw_level2_name: record.sw_level2_name,
      sw_level3_name: record.sw_level3_name,
      city: record.city,
      province: record.province,
      legal_repr: record.legal_repr,
      registered_capital: record.registered_capital,
      setup_date: record.setup_date || "",
      website: record.website,
      company_intro: record.company_intro,
      source_version: record.source_version || "manual",
    });
    setEditModalVisible(true);
  };

  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      if (editingRecord) {
        await updateMutation.mutateAsync({ id: editingRecord.id, record: values });
        message.success(`已保存 ${values.stock_name || values.stock_code}`);
      } else {
        await createMutation.mutateAsync(values);
        message.success(`已创建 ${values.stock_name || values.stock_code}`);
      }
      setEditModalVisible(false);
      refetchRecords();
      refetchSummary();
    } catch (error: unknown) {
      if ((error as { errorFields?: unknown })?.errorFields) return;
      message.error((error as Error)?.message || "保存失败");
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await deleteMutation.mutateAsync(id);
      message.success("已删除该股票记录");
      refetchRecords();
      refetchSummary();
    } catch (error: unknown) {
      message.error((error as Error)?.message || "删除失败");
    }
  };

  const handleEnrich = async (stockCode: string) => {
    try {
      const res = await enrichMutation.mutateAsync({ code: stockCode });
      message.success(res.message || "补充成功");
      refetchRecords();
      refetchSummary();
      if (activeRecord && (activeRecord.stock_code === stockCode || activeRecord.stock_code.startsWith(stockCode))) {
        // refresh active record in drawer if open
        const updated = recordsData?.items.find((r) => r.stock_code === stockCode);
        if (updated) setActiveRecord(updated);
      }
    } catch (error: unknown) {
      message.error((error as Error)?.message || "补充数据失败");
    }
  };

  const handleSyncMaster = async () => {
    try {
      const res = await syncMasterMutation.mutateAsync();
      message.success(`同步完成: 新增 ${res.added ?? 0} 条，更新 ${res.updated ?? 0} 条`);
      refetchRecords();
      refetchSummary();
    } catch (error: unknown) {
      message.error((error as Error)?.message || "同步失败");
    }
  };

  const columns: ColumnsType<StockBasicProfileRecord> = [
    {
      title: "代码",
      dataIndex: "stock_code",
      key: "stock_code",
      width: 110,
      render: (code: string) => {
        const raw = code.split(".")[0];
        return (
          <Link to={`/stock/${raw}`} style={{ fontWeight: 600, fontFamily: "var(--c-font-mono)" }}>
            {code}
          </Link>
        );
      },
    },
    {
      title: "名称",
      dataIndex: "stock_name",
      key: "stock_name",
      width: 120,
      render: (name: string, record) => {
        const raw = record.stock_code.split(".")[0];
        return (
          <Link to={`/stock/${raw}`} style={{ color: "inherit", fontWeight: 500 }}>
            {name || "—"}
          </Link>
        );
      },
    },
    {
      title: "板块 / 交易所",
      key: "board",
      width: 140,
      render: (_, r) => (
        <Space size={4}>
          <Tag color={boardTagColor(r.board)}>{r.board || r.exchange || "—"}</Tag>
          {r.market_group === "HK" && <Tag color="magenta">HK</Tag>}
        </Space>
      ),
    },
    {
      title: "上市时间",
      dataIndex: "listing_date",
      key: "listing_date",
      width: 110,
      sorter: true,
      render: (date?: string | null) => (
        <span style={{ fontSize: 13, color: date ? "inherit" : "var(--c-text-muted)" }}>
          {date || "—"}
        </span>
      ),
    },
    {
      title: "所属行业",
      key: "industry",
      width: 140,
      render: (_, r) => {
        const label = r.sw_level1_name || r.industry;
        return label ? <Tag>{label}</Tag> : <Text type="secondary">—</Text>;
      },
    },
    {
      title: "主营业务",
      dataIndex: "main_business",
      key: "main_business",
      ellipsis: true,
      render: (business: string) => {
        if (!business) {
          return <Tag color="default" style={{ color: "var(--c-text-muted)" }}>待补充</Tag>;
        }
        return (
          <Tooltip title={business} placement="topLeft">
            <div className="stock-profile-business-text">{business}</div>
          </Tooltip>
        );
      },
    },
    {
      title: "地区 / 法人",
      key: "corp",
      width: 130,
      ellipsis: true,
      render: (_, r) => {
        const parts = [r.province || r.city, r.legal_repr].filter(Boolean);
        return parts.length > 0 ? (
          <Text style={{ fontSize: 12 }}>{parts.join(" · ")}</Text>
        ) : (
          <Text type="secondary">—</Text>
        );
      },
    },
    {
      title: "操作",
      key: "actions",
      width: 160,
      align: "right",
      render: (_, record) => (
        <Space size={2}>
          <Tooltip title="查看完整资料">
            <Button
              type="text"
              size="small"
              icon={<EyeOutlined />}
              onClick={() => handleOpenDetail(record)}
            />
          </Tooltip>
          <Tooltip title="补充主营与简介（库中已有则跳过联网）">
            <Button
              type="text"
              size="small"
              icon={<ThunderboltOutlined />}
              loading={enrichMutation.isPending && enrichMutation.variables?.code === record.stock_code}
              onClick={() => handleEnrich(record.stock_code)}
            />
          </Tooltip>
          <Tooltip title="编辑资料">
            <Button
              type="text"
              size="small"
              icon={<EditOutlined />}
              onClick={() => handleOpenEdit(record)}
            />
          </Tooltip>
          <Popconfirm
            title="确认删除该股票资料？"
            okText="删除"
            cancelText="取消"
            okButtonProps={{ danger: true }}
            onConfirm={() => handleDelete(record.id)}
          >
            <Button type="text" danger size="small" icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const totalStocks = summary?.total || 0;
  const businessCount = summary?.has_business_count || 0;
  const listingDateCount = summary?.has_listing_date_count || 0;
  const businessPercent = totalStocks ? Math.round((businessCount / totalStocks) * 100) : 0;
  const listingPercent = totalStocks ? Math.round((listingDateCount / totalStocks) * 100) : 0;

  return (
    <div className="stock-profile-tab">
      {/* Summary Cards */}
      <div className="stock-profile-stat-grid">
        <Row gutter={[12, 12]}>
          <Col xs={24} sm={12} md={6}>
            <Card size="small">
              <Statistic
                title="全市场股票数"
                value={totalStocks}
                prefix={<BankOutlined />}
                suffix="只"
                loading={isSummaryLoading}
              />
              <div style={{ marginTop: 6, fontSize: 12, color: "var(--c-text-muted)" }}>
                A股 {summary?.market_group_counts?.A || 0} · 港股 {summary?.market_group_counts?.HK || 0}
              </div>
            </Card>
          </Col>
          <Col xs={24} sm={12} md={6}>
            <Card size="small">
              <Statistic
                title="主营业务已录入"
                value={businessCount}
                prefix={<ThunderboltOutlined />}
                suffix={`/ ${totalStocks}`}
                loading={isSummaryLoading}
              />
              <Progress percent={businessPercent} size="small" strokeColor="#52c41a" style={{ marginTop: 6 }} />
            </Card>
          </Col>
          <Col xs={24} sm={12} md={6}>
            <Card size="small">
              <Statistic
                title="上市时间已建档"
                value={listingDateCount}
                prefix={<CalendarOutlined />}
                suffix={`/ ${totalStocks}`}
                loading={isSummaryLoading}
              />
              <Progress percent={listingPercent} size="small" strokeColor="#1890ff" style={{ marginTop: 6 }} />
            </Card>
          </Col>
          <Col xs={24} sm={12} md={6}>
            <Card size="small">
              <div style={{ fontSize: 13, color: "var(--c-text-muted)", marginBottom: 6 }}>主要板块分布</div>
              <Space wrap size={[4, 4]}>
                {Object.entries(summary?.board_counts || {}).slice(0, 5).map(([board, cnt]) => (
                  <Tag key={board} color={boardTagColor(board)} style={{ margin: 0 }}>
                    {board}: {cnt}
                  </Tag>
                ))}
              </Space>
            </Card>
          </Col>
        </Row>
      </div>

      {/* Filter and Action Toolbar */}
      <div className="stock-profile-filters">
        <div className="stock-profile-filters__left">
          <Input
            placeholder="搜索股票代码或名称..."
            prefix={<SearchOutlined />}
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            onPressEnter={handleSearch}
            allowClear
            style={{ width: 220 }}
          />
          <Button onClick={handleSearch}>搜索</Button>

          <Select
            value={filters.market_group}
            onChange={(val) => setFilters((prev) => ({ ...prev, market_group: val, page: 1 }))}
            options={MARKET_OPTIONS}
            style={{ width: 110 }}
          />

          <Select
            value={filters.board}
            onChange={(val) => setFilters((prev) => ({ ...prev, board: val, page: 1 }))}
            options={BOARD_OPTIONS}
            style={{ width: 130 }}
          />

          <Select
            value={filters.has_business === undefined ? "" : String(filters.has_business)}
            onChange={(val) =>
              setFilters((prev) => ({
                ...prev,
                has_business: val === "" ? undefined : val === "true",
                page: 1,
              }))
            }
            options={BUSINESS_OPTIONS}
            style={{ width: 130 }}
          />
        </div>

        <div className="stock-profile-filters__right">
          <Button
            icon={<ReloadOutlined />}
            loading={isFetching}
            onClick={() => {
              refetchRecords();
              refetchSummary();
            }}
          >
            刷新
          </Button>
          <Popconfirm
            title="同步交易所官方股票名录？"
            description="将重新扫描交易所官方名录与申万分类并补齐数据库缺失项。"
            onConfirm={handleSyncMaster}
          >
            <Button icon={<SyncOutlined />} loading={syncMasterMutation.isPending}>
              同步交易所名录
            </Button>
          </Popconfirm>
          <Button icon={<DownloadOutlined />} loading={exporting} onClick={() => void handleExport()}>
            导出 CSV
          </Button>
          <Button icon={<ImportOutlined />} onClick={() => setImportOpen(true)}>
            批量导入
          </Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={handleOpenCreate}>
            新增资料
          </Button>
        </div>
      </div>

      {/* Main Table */}
      <Table<StockBasicProfileRecord>
        rowKey="id"
        columns={columns}
        dataSource={recordsData?.items || []}
        loading={isRecordsLoading}
        size="middle"
        pagination={{
          current: filters.page,
          pageSize: filters.page_size,
          total: recordsData?.total || 0,
          showSizeChanger: true,
          pageSizeOptions: ["20", "50", "100", "200"],
          showTotal: (total) => `共 ${total} 只个股资料`,
          onChange: (page, pageSize) => {
            setFilters((prev) => ({ ...prev, page, page_size: pageSize }));
          },
        }}
        onChange={(_pagination, _filters, sorter) => {
          if (sorter && !Array.isArray(sorter) && sorter.field) {
            setFilters((prev) => ({
              ...prev,
              sort_by: String(sorter.field),
              sort_order: sorter.order === "descend" ? "desc" : "asc",
              page: 1,
            }));
          }
        }}
      />

      {/* Detail Drawer */}
      <Drawer
        title={
          activeRecord ? (
            <Space>
              <span>{activeRecord.stock_name}</span>
              <span style={{ fontFamily: "var(--c-font-mono)", color: "var(--c-text-muted)" }}>
                ({activeRecord.stock_code})
              </span>
              <Tag color={boardTagColor(activeRecord.board)}>{activeRecord.board || "主板"}</Tag>
            </Space>
          ) : (
            "个股资料详情"
          )
        }
        size="large"
        open={detailVisible}
        onClose={() => setDetailVisible(false)}
        extra={
          activeRecord && (
            <Button
              type="primary"
              size="small"
              icon={<ThunderboltOutlined />}
              loading={enrichMutation.isPending}
              onClick={() => handleEnrich(activeRecord.stock_code)}
            >
              在线补充资料
            </Button>
          )
        }
      >
        {activeRecord && (
          <div className="stock-profile-drawer">
            {/* Section 1: 上市基本信息 */}
            <div className="stock-profile-drawer__section">
              <div className="stock-profile-drawer__title">
                <BankOutlined /> 上市基础资料
              </div>
              <Descriptions size="small" column={2} className="stock-profile-detail-desc" bordered>
                <Descriptions.Item label="股票代码">{activeRecord.stock_code}</Descriptions.Item>
                <Descriptions.Item label="股票名称">{activeRecord.stock_name}</Descriptions.Item>
                <Descriptions.Item label="上市板块">{activeRecord.board || "—"}</Descriptions.Item>
                <Descriptions.Item label="交易所">{activeRecord.exchange || "—"}</Descriptions.Item>
                <Descriptions.Item label="上市时间">{activeRecord.listing_date || "—"}</Descriptions.Item>
                <Descriptions.Item label="成立时间">{activeRecord.setup_date || "—"}</Descriptions.Item>
              </Descriptions>
            </div>

            {/* Section 2: 核心业务信息 */}
            <div className="stock-profile-drawer__section">
              <div className="stock-profile-drawer__title">
                <ThunderboltOutlined /> 主营业务与范围
              </div>
              <Descriptions size="small" column={1} className="stock-profile-detail-desc" bordered>
                <Descriptions.Item label="主营业务">
                  <Paragraph style={{ margin: 0, whiteSpace: "pre-wrap" }}>
                    {activeRecord.main_business || "待补充"}
                  </Paragraph>
                </Descriptions.Item>
                <Descriptions.Item label="主要产品">
                  <Paragraph style={{ margin: 0 }}>{activeRecord.products || "—"}</Paragraph>
                </Descriptions.Item>
                <Descriptions.Item label="经营范围">
                  <Paragraph style={{ margin: 0, whiteSpace: "pre-wrap", fontSize: 12 }}>
                    {activeRecord.business_scope || "—"}
                  </Paragraph>
                </Descriptions.Item>
              </Descriptions>
            </div>

            {/* Section 3: 公司与工商资料 */}
            <div className="stock-profile-drawer__section">
              <div className="stock-profile-drawer__title">
                <GlobalOutlined /> 公司工商概况
              </div>
              <Descriptions size="small" column={2} className="stock-profile-detail-desc" bordered>
                <Descriptions.Item label="所属行业">
                  {activeRecord.sw_level1_name || activeRecord.industry || "—"}
                </Descriptions.Item>
                <Descriptions.Item label="申万二级">
                  {activeRecord.sw_level2_name || "—"}
                </Descriptions.Item>
                <Descriptions.Item label="法定代表人">{activeRecord.legal_repr || "—"}</Descriptions.Item>
                <Descriptions.Item label="注册资本">{activeRecord.registered_capital || "—"}</Descriptions.Item>
                <Descriptions.Item label="省份 / 地区">
                  {[activeRecord.province, activeRecord.city].filter(Boolean).join(" ") || "—"}
                </Descriptions.Item>
                <Descriptions.Item label="官方网址">
                  {activeRecord.website ? (
                    <a
                      href={activeRecord.website.startsWith("http") ? activeRecord.website : `https://${activeRecord.website}`}
                      target="_blank"
                      rel="noreferrer"
                    >
                      {activeRecord.website}
                    </a>
                  ) : (
                    "—"
                  )}
                </Descriptions.Item>
              </Descriptions>
            </div>

            {/* Section 4: 公司简介 */}
            {activeRecord.company_intro && (
              <div className="stock-profile-drawer__section">
                <div className="stock-profile-drawer__title">公司简介</div>
                <Card size="small" style={{ background: "var(--c-nested-bg)" }}>
                  <Paragraph style={{ margin: 0, fontSize: 13, lineHeight: 1.6 }}>
                    {activeRecord.company_intro}
                  </Paragraph>
                </Card>
              </div>
            )}

            {/* Section 5: 元数据 */}
            <div className="stock-profile-drawer__section">
              <div style={{ fontSize: 12, color: "var(--c-text-muted)", marginTop: 12 }}>
                数据来源: {activeRecord.source} · 更新时间: {activeRecord.updated_at}
                {activeRecord.is_manual_override && <Tag color="warning" style={{ marginLeft: 8 }}>手工修改</Tag>}
              </div>
            </div>
          </div>
        )}
      </Drawer>

      {/* Create / Edit Modal */}
      <Modal
        title={editingRecord ? `编辑个股资料: ${editingRecord.stock_code}` : "新增个股资料"}
        open={editModalVisible}
        onOk={handleSave}
        onCancel={() => setEditModalVisible(false)}
        width={680}
        confirmLoading={createMutation.isPending || updateMutation.isPending}
        destroyOnHidden
      >
        <Form form={form} layout="vertical" initialValues={EMPTY_INPUT}>
          <Row gutter={16}>
            <Col span={8}>
              <Form.Item
                name="stock_code"
                label="股票代码"
                rules={[{ required: true, message: "请输入股票代码" }]}
              >
                <Input placeholder="如 600519 或 600519.SH" disabled={Boolean(editingRecord)} />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item
                name="stock_name"
                label="股票名称"
                rules={[{ required: true, message: "请输入股票名称" }]}
              >
                <Input placeholder="如 贵州茅台" />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="board" label="上市板块">
                <Input placeholder="主板 / 科创板 / 创业板 / 北交所" />
              </Form.Item>
            </Col>
          </Row>

          <Row gutter={16}>
            <Col span={8}>
              <Form.Item name="market_group" label="市场">
                <Select options={MARKET_OPTIONS.filter((o) => o.value)} />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="listing_date" label="上市时间">
                <Input placeholder="YYYY-MM-DD" />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="setup_date" label="成立时间">
                <Input placeholder="YYYY-MM-DD" />
              </Form.Item>
            </Col>
          </Row>

          <Form.Item name="main_business" label="主营业务">
            <TextArea rows={2} placeholder="核心主营业务说明" />
          </Form.Item>

          <Form.Item name="products" label="主要产品">
            <Input placeholder="核心产品系列" />
          </Form.Item>

          <Form.Item name="business_scope" label="经营范围">
            <TextArea rows={2} placeholder="公司工商登记经营范围" />
          </Form.Item>

          <Row gutter={16}>
            <Col span={8}>
              <Form.Item name="sw_level1_name" label="申万一级行业">
                <Input placeholder="如 食品饮料" />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="sw_level2_name" label="申万二级行业">
                <Input placeholder="如 白酒Ⅱ" />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="legal_repr" label="法定代表人">
                <Input placeholder="法人代表" />
              </Form.Item>
            </Col>
          </Row>

          <Row gutter={16}>
            <Col span={8}>
              <Form.Item name="registered_capital" label="注册资本">
                <Input placeholder="如 12.50亿" />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="province" label="省份/地区">
                <Input placeholder="如 贵州" />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="website" label="官方网址">
                <Input placeholder="www.example.com" />
              </Form.Item>
            </Col>
          </Row>

          <Form.Item name="company_intro" label="公司简介">
            <TextArea rows={3} placeholder="公司发展历程与介绍" />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="批量导入个股资料"
        open={importOpen}
        onCancel={() => {
          setImportOpen(false);
          setImportFile(null);
        }}
        footer={[
          <Button key="cancel" onClick={() => setImportOpen(false)}>
            取消
          </Button>,
          <Button
            key="submit"
            type="primary"
            disabled={!importFile}
            loading={importMutation.isPending || readingFile}
            onClick={handleImportSubmit}
          >
            开始导入
          </Button>,
        ]}
      >
        <Space direction="vertical" style={{ width: "100%" }} size="middle">
          <Upload {...importUploadProps}>
            <Button icon={<ImportOutlined />}>选择 CSV / Excel 文件</Button>
          </Upload>
          <Typography.Text type="secondary">
            必须包含【股票代码】列；可选列：股票简称、板块、上市日期、所属行业、申万一/二/三级行业、
            主营业务、经营范围、主要产品、省份、城市、法定代表人、注册资本、成立日期、网址、公司简介。
            港股代码支持 5 位数字或 .HK 后缀。内容与现有记录一致的行会自动跳过。
          </Typography.Text>
          <Checkbox
            checked={updateManual}
            onChange={(e) => setUpdateManual(e.target.checked)}
          >
            覆盖手动维护的记录（默认跳过）
          </Checkbox>
        </Space>
      </Modal>
    </div>
  );
}
