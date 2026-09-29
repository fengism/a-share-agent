import { useEffect, useState } from "react";
import {
  Alert,
  Button,
  Card,
  Col,
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
  Switch,
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
  AppstoreOutlined,
  DeleteOutlined,
  DownloadOutlined,
  EditOutlined,
  FileExcelOutlined,
  PlusOutlined,
  ReloadOutlined,
  SearchOutlined,
} from "@ant-design/icons";
import { apiDownload } from "../../api/client";
import {
  useCommitStockConceptImport,
  useConceptTags,
  useCreateStockConceptRecord,
  useDeleteStockConceptRecord,
  usePreviewStockConceptImport,
  useStockConceptRecords,
  useStockConceptStatus,
  useUpdateStockConceptRecord,
} from "../../api/queries";
import type {
  ConceptImportPreviewResponse,
  StockConceptListFilters,
  StockConceptMarketGroup,
  StockConceptRecord,
  StockConceptRecordInput,
} from "../../api/stockConcept";
import { useImportFile } from "./useImportFile";
import SectionDataState from "../../components/SectionDataState";
import { useAuthStore } from "../../store/authStore";
import { useStyles } from "../../styles/ui";
import "./stock-concept.css";

const { Paragraph, Text, Title } = Typography;
const PAGE_SIZE = 50;
const MARKET_OPTIONS = [
  { value: "A", label: "A 股" },
  { value: "HK", label: "港股" },
  { value: "OVERSEAS", label: "海外" },
] satisfies Array<{ value: StockConceptMarketGroup; label: string }>;

const EMPTY_RECORD: StockConceptRecordInput = {
  market_group: "A",
  exchange_suffix: "SZ",
  stock_code: "",
  stock_name: "",
  concepts: [],
  source_version: "manual",
};

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "未知错误";
}

function formatDateTime(value?: string | null): string {
  if (!value) return "—";
  const date = new Date(value.includes("T") ? value : value.replace(" ", "T"));
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString("zh-CN", { hour12: false });
}

function marketColor(market: string): string {
  if (market === "A") return "blue";
  if (market === "HK") return "geekblue";
  return "purple";
}

function marketLabel(market: string): string {
  if (market === "A") return "A 股";
  if (market === "HK") return "港股";
  return "海外";
}

function RecordEditorModal({
  open,
  record,
  saving,
  availableConcepts,
  onClose,
  onSubmit,
}: {
  open: boolean;
  record: StockConceptRecord | null;
  saving: boolean;
  availableConcepts: string[];
  onClose: () => void;
  onSubmit: (value: StockConceptRecordInput) => void;
}) {
  const [form] = Form.useForm<StockConceptRecordInput>();
  const marketGroup = Form.useWatch("market_group", form) ?? "A";

  useEffect(() => {
    if (!open) {
      form.resetFields();
      return;
    }
    form.setFieldsValue(
      record
        ? {
            market_group: record.market_group,
            exchange_suffix: record.exchange_suffix,
            stock_code: record.stock_code,
            stock_name: record.stock_name,
            concepts: record.concepts || [],
            source_version: record.source_version || "manual",
          }
        : EMPTY_RECORD
    );
  }, [form, open, record]);

  const normalizeCode = () => {
    const current = form.getFieldValue("stock_code")?.trim().toUpperCase();
    const suffix = form.getFieldValue("exchange_suffix")?.trim().toUpperCase();
    if (!current || !suffix || current.includes(".") || marketGroup === "OVERSEAS") return;
    form.setFieldValue("stock_code", `${current}.${suffix}`);
  };

  const conceptOptions = Array.from(
    new Set([...(record?.concepts || []), ...availableConcepts])
  ).map((c) => ({ label: c, value: c }));

  return (
    <Modal
      title={record ? "编辑股票概念" : "新增股票概念"}
      open={open}
      okText={record ? "保存修改" : "新增记录"}
      cancelText="取消"
      confirmLoading={saving}
      onCancel={onClose}
      onOk={() =>
        void form.validateFields().then((value) =>
          onSubmit({
            ...value,
            source_version: record?.source_version || "manual",
          })
        )
      }
      destroyOnHidden
      width={720}
    >
      <Alert
        type="info"
        showIcon
        message="手工维护的概念记录会被锁定，CSV 导入仅在开启强制覆盖时可替换。"
        style={{ marginBottom: 16 }}
      />
      <Form form={form} layout="vertical" requiredMark="optional">
        <Row gutter={12}>
          <Col xs={24} md={8}>
            <Form.Item name="market_group" label="市场" rules={[{ required: true }]}>
              <Select options={MARKET_OPTIONS} />
            </Form.Item>
          </Col>
          <Col xs={24} md={8}>
            <Form.Item
              name="exchange_suffix"
              label="交易所后缀"
              rules={[{ required: true, message: "请输入交易所后缀" }]}
            >
              <Input placeholder="SZ / SH / BJ / HK" onBlur={normalizeCode} />
            </Form.Item>
          </Col>
          <Col xs={24} md={8}>
            <Form.Item
              name="stock_code"
              label="股票代码"
              rules={[{ required: true, message: "请输入股票代码" }]}
            >
              <Input placeholder="例如 000001.SZ" onBlur={normalizeCode} />
            </Form.Item>
          </Col>
        </Row>
        <Form.Item name="stock_name" label="公司简称">
          <Input placeholder="例如 平安银行" />
        </Form.Item>
        <Form.Item
          name="concepts"
          label="所属概念（多选，支持输入新建）"
          rules={[{ required: false }]}
        >
          <Select
            mode="tags"
            style={{ width: "100%" }}
            placeholder="请选择或输入概念标签"
            options={conceptOptions}
            tokenSeparators={[",", ";", "；", "，"]}
          />
        </Form.Item>
      </Form>
    </Modal>
  );
}

function ImportDrawer({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const previewImport = usePreviewStockConceptImport();
  const commitImport = useCommitStockConceptImport();
  const upload = useImportFile((text) => { message.error(text); });
  const { file: fileState, reading: readingFile, clear } = upload;
  const [preview, setPreview] = useState<ConceptImportPreviewResponse | null>(null);
  const [forceOverride, setForceOverride] = useState(false);
  const busy = previewImport.isPending || commitImport.isPending;
  useEffect(() => {
    if (!open) {
      clear();
      setPreview(null);
      setForceOverride(false);
    }
  }, [open, clear]);
  const close = () => { if (!busy) onClose(); };

  const resetPreview = () => setPreview(null);
  const request = fileState
    ? {
        filename: fileState.filename,
        content_base64: fileState.content_base64,
        source_version: "",
      }
    : null;

  const uploadProps: UploadProps = {
    accept: ".csv,.xlsx,.xls",
    maxCount: 1,
    fileList: upload.selected ? [upload.selected] : [],
    beforeUpload: (file) => {
      resetPreview();
      return upload.select(file) ? false : Upload.LIST_IGNORE;
    },
    onRemove: () => { clear(); resetPreview(); },
  };

  const handlePreview = () => {
    if (!request || readingFile || busy) return;
    previewImport.mutate(request, {
      onSuccess: (response) => {
        setPreview(response);
        message.success(`预检完成：发现 ${response.valid_rows} 条有效记录`);
      },
      onError: (error) => message.error(`预检失败：${errorMessage(error)}`),
    });
  };

  const handleCommit = () => {
    if (!request || !preview || readingFile || busy) return;
    commitImport.mutate(
      {
        ...request,
        import_token: preview.import_token,
        force_override: forceOverride,
      },
      {
        onSuccess: (result) => {
          message.success(
            `导入成功：新增 ${result.added}，更新 ${result.updated}，跳过 ${result.skipped}`
          );
          onClose();
        },
        onError: (error) => message.error(`导入失败：${errorMessage(error)}`),
      }
    );
  };

  const previewStats = preview
    ? [
        ["新增", preview.added_rows, "green"],
        ["更新", preview.updated_rows, "blue"],
        ["无变化", preview.unchanged_rows, "default"],
        ["跳过（手工）", preview.skipped_rows, "gold"],
        ["无效行", preview.invalid_rows, "error"],
      ]
    : [];

  return (
    <Drawer
      title="导入概念数据 (CSV / Excel)"
      open={open}
      onClose={close}
      closable={!busy}
      mask={{ closable: !busy }}
      keyboard={!busy}
      width={640}
      destroyOnHidden
    >
      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <Alert
          type="info"
          showIcon
          message="文件格式要求"
          description="支持 CSV 或 Excel 格式，必须包含【股票代码】和【所属概念】列（如 i问财导出的表头）。多个概念支持分号或逗号分隔。"
        />
        <Upload.Dragger {...uploadProps} disabled={busy}>
          <p className="ant-upload-drag-icon">
            <FileExcelOutlined />
          </p>
          <p className="ant-upload-text">点击或将 CSV/Excel 文件拖拽到此处</p>
          <p className="ant-upload-hint">支持单个文件导入，最大 50 MB</p>
        </Upload.Dragger>
        <Button
          type="primary"
          icon={<SearchOutlined />}
          block
          disabled={!fileState || readingFile || busy}
          loading={readingFile || previewImport.isPending}
          onClick={handlePreview}
        >
          预检文件
        </Button>
      </div>

      {preview && (
        <div className="concept-preview">
          <div className="concept-preview__title">
            <Title level={5}>预检结果</Title>
            <Text type="secondary">
              有效 {preview.valid_rows} / 共 {preview.total_rows} 行
            </Text>
          </div>
          <Progress
            percent={
              preview.total_rows
                ? Math.round((preview.valid_rows / preview.total_rows) * 100)
                : 0
            }
            showInfo={false}
            status={preview.invalid_rows ? "exception" : "success"}
          />
          <div className="concept-preview__stats">
            {previewStats.map(([label, value, color]) => (
              <Tag key={label as string} color={color as string}>
                {label} {value}
              </Tag>
            ))}
          </div>
          {preview.warnings.length > 0 && (
            <Alert
              type="warning"
              showIcon
              message={`预检提示（${preview.warnings.length}）`}
              description={
                <ul>
                  {preview.warnings.slice(0, 8).map((warning) => (
                    <li key={warning}>{warning}</li>
                  ))}
                </ul>
              }
            />
          )}
          {preview.sample.length > 0 && (
            <Table
              size="small"
              rowKey={(row) => String(row.stock_code)}
              pagination={false}
              scroll={{ x: 500, y: 220 }}
              dataSource={preview.sample}
              columns={[
                { title: "股票代码", dataIndex: "stock_code", width: 120 },
                { title: "简称", dataIndex: "stock_name", width: 100 },
                {
                  title: "概念",
                  dataIndex: "concepts",
                  render: (v: string[]) => (v ? v.slice(0, 3).join("、") + (v.length > 3 ? "..." : "") : "—"),
                },
              ]}
            />
          )}
          <div className="concept-force-override">
            <div>
              <Text strong>强制覆盖手工维护记录</Text>
              <div>
                <Text type="secondary">若未开启，手工维护过的股票将保留原样不被覆盖</Text>
              </div>
            </div>
            <Switch disabled={busy} checked={forceOverride} onChange={setForceOverride} />
          </div>
          <Popconfirm
            title="确认写入概念数据库？"
            description={
              forceOverride
                ? "已开启强制覆盖，可能替换手工修改过的概念。"
                : "手工维护记录将保持不变。"
            }
            okText="确认导入"
            cancelText="取消"
            onConfirm={handleCommit}
          >
            <Button
              type="primary"
              block
              danger={forceOverride}
              loading={commitImport.isPending}
            >
              提交导入
            </Button>
          </Popconfirm>
        </div>
      )}
    </Drawer>
  );
}

export default function StockConceptPage() {
  const { pageContainerStyle, pageDescriptionStyle, pageTitleStyle } = useStyles();
  const isAdmin = Boolean(useAuthStore((state) => state.user?.is_admin));
  const [filters, setFilters] = useState<StockConceptListFilters>({
    page: 1,
    page_size: PAGE_SIZE,
  });
  const [queryDraft, setQueryDraft] = useState("");
  const [editorOpen, setEditorOpen] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const [editingRecord, setEditingRecord] = useState<StockConceptRecord | null>(null);

  const statusQuery = useStockConceptStatus();
  const conceptsQuery = useConceptTags();
  const recordsQuery = useStockConceptRecords(filters);
  const createRecord = useCreateStockConceptRecord();
  const updateRecord = useUpdateStockConceptRecord();
  const deleteRecord = useDeleteStockConceptRecord();

  const updateFilter = (patch: Partial<StockConceptListFilters>) => {
    setFilters((current) => ({ ...current, ...patch, page: patch.page ?? 1 }));
  };

  const openCreate = () => {
    setEditingRecord(null);
    setEditorOpen(true);
  };

  const handleSaveRecord = (value: StockConceptRecordInput) => {
    const callbacks = {
      onSuccess: () => {
        message.success(editingRecord ? "股票概念已更新" : "股票概念已新增");
        setEditorOpen(false);
      },
      onError: (error: Error) => message.error(`保存失败：${errorMessage(error)}`),
    };
    if (editingRecord) {
      updateRecord.mutate({ id: editingRecord.id, record: { ...value, expected_revision: editingRecord.revision } }, callbacks);
      return;
    }
    createRecord.mutate(value, callbacks);
  };

  const handleDelete = (record: StockConceptRecord) => {
    deleteRecord.mutate(record.id, {
      onSuccess: () => message.success(`${record.stock_code} 已删除`),
      onError: (error) => message.error(`删除失败：${errorMessage(error)}`),
    });
  };

  const allConceptNames = (conceptsQuery.data?.items || []).map((c) => c.name);

  const columns: ColumnsType<StockConceptRecord> = [
    {
      title: "股票",
      key: "stock",
      fixed: "left",
      width: 180,
      render: (_, record) => (
        <Space direction="vertical" size={0}>
          <Text strong copyable>
            {record.stock_code}
          </Text>
          <Text type="secondary">{record.stock_name || "—"}</Text>
        </Space>
      ),
    },
    {
      title: "市场",
      dataIndex: "market_group",
      width: 88,
      render: (value: string) => <Tag color={marketColor(value)}>{marketLabel(value)}</Tag>,
    },
    {
      title: "所属概念（多选）",
      dataIndex: "concepts",
      render: (concepts: string[]) => {
        if (!concepts || concepts.length === 0) return <Text type="secondary">—</Text>;
        return (
          <div className="stock-concept-tags-wrap">
            {concepts.slice(0, 10).map((c) => (
              <Tag
                key={c}
                color="blue"
                style={{ cursor: "pointer" }}
                onClick={() => updateFilter({ concept: c })}
              >
                {c}
              </Tag>
            ))}
            {concepts.length > 10 && (
              <Tooltip title={concepts.slice(10).join("、")}>
                <Tag color="default">+{concepts.length - 10}更多</Tag>
              </Tooltip>
            )}
          </div>
        );
      },
    },
    { title: "更新时间", dataIndex: "updated_at", width: 170, render: formatDateTime },
    ...(isAdmin
      ? [
          {
            title: "操作",
            key: "actions",
            fixed: "right" as const,
            width: 104,
            render: (_: unknown, record: StockConceptRecord) => (
              <Space>
                <Tooltip title="编辑概念">
                  <Button
                    type="text"
                    icon={<EditOutlined />}
                    aria-label={`编辑 ${record.stock_code}`}
                    onClick={() => {
                      setEditingRecord(record);
                      setEditorOpen(true);
                    }}
                  />
                </Tooltip>
                <Popconfirm
                  title={`删除 ${record.stock_code}？`}
                  okText="删除"
                  cancelText="取消"
                  onConfirm={() => handleDelete(record)}
                >
                  <Tooltip title="删除">
                    <Button
                      type="text"
                      danger
                      icon={<DeleteOutlined />}
                      aria-label={`删除 ${record.stock_code}`}
                    />
                  </Tooltip>
                </Popconfirm>
              </Space>
            ),
          },
        ]
      : []),
  ];

  const [exporting, setExporting] = useState(false);
  const handleExport = async () => {
    try {
      setExporting(true);
      await apiDownload("/stock-concept/export", "stock_concept_export.csv", {
        query: filters.query,
        market_group: filters.market_group,
        concept: filters.concept,
      });
      message.success("导出完成");
    } catch (err) {
      message.error(`导出失败: ${errorMessage(err)}`);
    } finally {
      setExporting(false);
    }
  };

  const stats = statusQuery.data?.stats;

  return (
    <div style={pageContainerStyle} className="stock-concept-page">
      <header className="stock-concept-header">
        <div>
          <div className="u-page-title u-page-title--compact">
            <Title level={3} style={pageTitleStyle}>
              <AppstoreOutlined /> 概念基础数据
            </Title>
          </div>
          <Paragraph style={pageDescriptionStyle}>
            统一维护个股概念板块（多选），支持 CSV / Excel 批量导入与手工标签修改。
          </Paragraph>
        </div>
        <Space wrap>
          <Button
            icon={<ReloadOutlined />}
            loading={statusQuery.isFetching || recordsQuery.isFetching}
            onClick={() => {
              void statusQuery.refetch();
              void conceptsQuery.refetch();
              void recordsQuery.refetch();
            }}
          >
            刷新数据
          </Button>
          <Button
            icon={<DownloadOutlined />}
            loading={exporting}
            onClick={() => void handleExport()}
          >
            导出 CSV
          </Button>
          {isAdmin && (
            <Button icon={<FileExcelOutlined />} onClick={() => setImportOpen(true)}>
              批量导入
            </Button>
          )}
          {isAdmin && (
            <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
              新增个股
            </Button>
          )}
        </Space>
      </header>

      <SectionDataState
        isLoading={statusQuery.isLoading}
        error={statusQuery.error}
        onRetry={() => statusQuery.refetch()}
        errorTitle="概念数据状态加载失败"
        isEmpty={false}
      >
        <Row gutter={[12, 12]} className="stock-concept-stat-grid">
          <Col xs={12} sm={8} xl={6}>
            <Card>
              <Statistic title="覆盖股票数" value={stats?.total_stocks ?? 0} />
            </Card>
          </Col>
          <Col xs={12} sm={8} xl={6}>
            <Card>
              <Statistic title="概念总数（去重）" value={stats?.total_concepts ?? 0} />
            </Card>
          </Col>
          <Col xs={12} sm={8} xl={6}>
            <Card>
              <Statistic title="A 股股票数" value={stats?.market_counts.A ?? 0} />
            </Card>
          </Col>
          <Col xs={12} sm={8} xl={6}>
            <Card>
              <Statistic
                title="最近更新时间"
                value={formatDateTime(stats?.latest_updated_at)}
                valueStyle={{ fontSize: 15 }}
              />
            </Card>
          </Col>
        </Row>
      </SectionDataState>

      <Card className="stock-concept-table-card">
        <div className="stock-concept-filters">
          <Input.Search
            allowClear
            value={queryDraft}
            placeholder="股票代码或公司简称"
            enterButton="搜索"
            onChange={(event) => setQueryDraft(event.target.value)}
            onSearch={(value) => updateFilter({ query: value.trim() })}
            className="stock-concept-query"
          />
          <Select
            allowClear
            placeholder="全部市场"
            value={filters.market_group || undefined}
            options={MARKET_OPTIONS}
            onChange={(value) => updateFilter({ market_group: value })}
            className="stock-concept-select"
          />
          <Select
            showSearch
            allowClear
            placeholder="按概念筛选"
            value={filters.concept || undefined}
            options={(conceptsQuery.data?.items || []).map((item) => ({
              value: item.name,
              label: `${item.name} (${item.stock_count})`,
            }))}
            onChange={(value) => updateFilter({ concept: value })}
            className="stock-concept-select"
            style={{ width: 260 }}
          />
          <Button
            onClick={() => {
              setQueryDraft("");
              setFilters({ page: 1, page_size: PAGE_SIZE });
            }}
          >
            重置
          </Button>
        </div>

        <SectionDataState isLoading={recordsQuery.isLoading} error={recordsQuery.error}
          onRetry={() => recordsQuery.refetch()} errorTitle="概念记录加载失败"
          isEmpty={!recordsQuery.isLoading && !recordsQuery.error && recordsQuery.data?.total === 0}
          emptyText="没有符合条件的概念记录">
        <Table
          rowKey="id"
          size="middle"
          columns={columns}
          dataSource={recordsQuery.data?.items ?? []}
          loading={recordsQuery.isLoading || recordsQuery.isFetching}
          scroll={{ x: 900 }}
          pagination={{
            current: filters.page,
            pageSize: filters.page_size,
            total: recordsQuery.data?.total ?? 0,
            showSizeChanger: true,
            pageSizeOptions: ["20", "50", "100"],
            onChange: (page, pageSize) => setFilters((curr) => ({ ...curr, page, page_size: pageSize })),
          }}
        />
        </SectionDataState>
      </Card>

      <RecordEditorModal
        open={editorOpen}
        record={editingRecord}
        saving={createRecord.isPending || updateRecord.isPending}
        availableConcepts={allConceptNames}
        onClose={() => setEditorOpen(false)}
        onSubmit={handleSaveRecord}
      />

      <ImportDrawer open={importOpen} onClose={() => setImportOpen(false)} />
    </div>
  );
}
