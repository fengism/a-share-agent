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
  CloudSyncOutlined,
  DatabaseOutlined,
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
  useCommitIndustryImport,
  useCreateIndustryRecord,
  useDeleteIndustryRecord,
  useIndustryHierarchy,
  useIndustryRecords,
  useIndustryStatus,
  usePreviewIndustryImport,
  useRefreshIndustries,
  useUpdateIndustryRecord,
  useUpdateIndustryRefreshPolicy,
} from "../../api/queries";
import type {
  IndustryImportPreviewResponse,
  IndustryListFilters,
  IndustryMarketGroup,
  IndustryRecord,
  IndustryRecordInput,
} from "../../api/industryClassification";
import { useImportFile } from "./useImportFile";
import SectionDataState from "../../components/SectionDataState";
import { useAuthStore } from "../../store/authStore";
import { useStyles } from "../../styles/ui";
import { formatMarketDateTime } from "../../utils/marketTime";
import "./industry-classification.css";

const { Paragraph, Text, Title } = Typography;
const PAGE_SIZE = 50;
const MARKET_OPTIONS = [
  { value: "A", label: "A 股" },
  { value: "HK", label: "港股" },
  { value: "OVERSEAS", label: "海外" },
] satisfies Array<{ value: IndustryMarketGroup; label: string }>;
const REFRESH_INTERVAL_OPTIONS = [
  { value: 24 * 60 * 60, label: "每天" },
  { value: 3 * 24 * 60 * 60, label: "每 3 天" },
  { value: 7 * 24 * 60 * 60, label: "每周" },
  { value: 30 * 24 * 60 * 60, label: "每 30 天" },
];

const EMPTY_RECORD: IndustryRecordInput = {
  market_group: "A",
  exchange_suffix: "SZ",
  stock_code: "",
  stock_name: "",
  sw_level1_name: "",
  sw_level2_name: "",
  sw_level3_name: "",
  sw_industry_code: "",
  source_version: "manual",
  effective_date: null,
};

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "未知错误";
}

function formatDateTime(value?: string | null): string {
  if (!value) return "—";
  return formatMarketDateTime(value, value);
}

function marketLabel(value: string): string {
  return MARKET_OPTIONS.find((item) => item.value === value)?.label ?? value;
}

function marketColor(value: string): string {
  return value === "A" ? "red" : value === "HK" ? "blue" : "purple";
}

function RecordEditor({
  open,
  record,
  saving,
  onClose,
  onSubmit,
}: {
  open: boolean;
  record: IndustryRecord | null;
  saving: boolean;
  onClose: () => void;
  onSubmit: (value: IndustryRecordInput) => void;
}) {
  const [form] = Form.useForm<IndustryRecordInput>();
  const marketGroup = Form.useWatch("market_group", form);

  useEffect(() => {
    if (!open) return;
    form.setFieldsValue(record ? {
      market_group: record.market_group,
      exchange_suffix: record.exchange_suffix,
      stock_code: record.stock_code,
      stock_name: record.stock_name,
      sw_level1_name: record.sw_level1_name,
      sw_level2_name: record.sw_level2_name,
      sw_level3_name: record.sw_level3_name,
      sw_industry_code: record.sw_industry_code,
      source_version: record.source_version || "manual",
      effective_date: record.effective_date,
    } : EMPTY_RECORD);
  }, [form, open, record]);

  const normalizeCode = () => {
    const current = form.getFieldValue("stock_code")?.trim().toUpperCase();
    const suffix = form.getFieldValue("exchange_suffix")?.trim().toUpperCase();
    if (!current || !suffix || current.includes(".") || marketGroup === "OVERSEAS") return;
    form.setFieldValue("stock_code", `${current}.${suffix}`);
  };

  return (
    <Modal
      title={record ? "编辑行业记录" : "新增行业记录"}
      open={open}
      okText={record ? "保存修改" : "新增记录"}
      cancelText="取消"
      confirmLoading={saving}
      onCancel={onClose}
      onOk={() => void form.validateFields().then((value) => onSubmit({
        ...value,
        source_version: record?.source_version || "manual",
      }))}
      destroyOnHidden
      width="min(720px, calc(100vw - 24px))"
    >
      <Alert
        type="info"
        showIcon
        message="手工维护的记录会被锁定，自动更新不会覆盖。Excel 导入仅在开启强制覆盖时可替换。"
        className="industry-editor-alert"
      />
      <Form form={form} layout="vertical" requiredMark="optional">
        <Row gutter={12}>
          <Col xs={24} md={8}>
            <Form.Item name="market_group" label="市场" rules={[{ required: true }]}>
              <Select options={MARKET_OPTIONS} />
            </Form.Item>
          </Col>
          <Col xs={24} md={8}>
            <Form.Item name="exchange_suffix" label="交易所后缀" rules={[{ required: true, message: "请输入交易所后缀" }]}>
              <Input placeholder="SZ / SH / HK / US" onBlur={normalizeCode} />
            </Form.Item>
          </Col>
          <Col xs={24} md={8}>
            <Form.Item name="stock_code" label="股票代码" rules={[{ required: true, message: "请输入股票代码" }]}>
              <Input placeholder="例如 300957.SZ" onBlur={normalizeCode} />
            </Form.Item>
          </Col>
        </Row>
        <Row gutter={12}>
          <Col xs={24} md={12}>
            <Form.Item name="stock_name" label="公司简称"><Input placeholder="可留空" /></Form.Item>
          </Col>
          <Col xs={24} md={12}>
            <Form.Item name="sw_industry_code" label="申万行业代码"><Input /></Form.Item>
          </Col>
        </Row>
        <Row gutter={12}>
          <Col xs={24} md={8}>
            <Form.Item name="sw_level1_name" label="一级行业"><Input /></Form.Item>
          </Col>
          <Col xs={24} md={8}>
            <Form.Item name="sw_level2_name" label="二级行业"><Input /></Form.Item>
          </Col>
          <Col xs={24} md={8}>
            <Form.Item name="sw_level3_name" label="三级行业"><Input /></Form.Item>
          </Col>
        </Row>
        <Form.Item name="effective_date" label="生效日期">
          <Input type="date" />
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
  const previewImport = usePreviewIndustryImport();
  const commitImport = useCommitIndustryImport();
  const upload = useImportFile((text) => { message.error(text); });
  const { file: fileState, reading: readingFile, clear } = upload;
  const [preview, setPreview] = useState<IndustryImportPreviewResponse | null>(null);
  const [effectiveDate, setEffectiveDate] = useState("");
  const [forceOverride, setForceOverride] = useState(false);
  const busy = previewImport.isPending || commitImport.isPending;
  useEffect(() => {
    if (!open) {
      clear();
      setPreview(null);
      setForceOverride(false);
      setEffectiveDate("");
    }
  }, [open, clear]);
  const close = () => { if (!busy) onClose(); };

  const resetPreview = () => setPreview(null);
  const request = fileState ? {
    filename: fileState.filename,
    content_base64: fileState.content_base64,
    source_version: fileState.filename.replace(/\.xlsx$/i, ""),
    effective_date: effectiveDate || null,
  } : null;

  const beforeUpload: UploadProps["beforeUpload"] = (file) => {
    resetPreview();
    return upload.select(file) ? false : Upload.LIST_IGNORE;
  };

  const handlePreview = () => {
    if (!request || readingFile || busy) return;
    previewImport.mutate(request, {
      onSuccess: (result) => setPreview(result),
      onError: (error) => message.error(`预检失败：${errorMessage(error)}`),
    });
  };

  const handleCommit = () => {
    if (!request || !preview || readingFile || busy) return;
    commitImport.mutate({ ...request, import_token: preview.import_token, force_override: forceOverride }, {
      onSuccess: (result) => {
        message.success(`导入完成：新增 ${result.added}、更新 ${result.updated}、跳过 ${result.skipped}`);
        setPreview(null);
        clear();
        onClose();
      },
      onError: (error) => message.error(`导入失败：${errorMessage(error)}`),
    });
  };

  const previewStats = preview ? [
    ["新增", preview.added_rows, "success"],
    ["更新", preview.updated_rows, "processing"],
    ["不变", preview.unchanged_rows, "default"],
    ["跳过", preview.skipped_rows, "warning"],
    ["冲突", preview.conflict_rows, "error"],
    ["无效", preview.invalid_rows, "error"],
  ] as const : [];

  return (
    <Drawer
      title={<Space><FileExcelOutlined />导入行业数据 (CSV / Excel)</Space>}
      open={open}
      onClose={close}
      closable={!busy}
      mask={{ closable: !busy }}
      keyboard={!busy}
      width="min(640px, 100vw)"
      destroyOnHidden
      extra={<Button disabled={busy} onClick={close}>关闭</Button>}
    >
      <Alert
        showIcon
        type="info"
        message="文件格式要求"
        description="支持 CSV 或 Excel 格式。必须包含【股票代码】和【一级行业】/【所属行业】列（如申万发布表格或同花顺行情表）。"
      />
      <div className="industry-import-fields">
        <Upload.Dragger
          accept=".csv,.xlsx,.xls"
          maxCount={1}
          showUploadList={false}
          beforeUpload={beforeUpload}
          disabled={busy}
        >
          <p className="ant-upload-drag-icon"><FileExcelOutlined /></p>
          <p className="ant-upload-text">点击或拖拽 CSV / Excel 文件到这里</p>
          <p className="ant-upload-hint">支持 CSV 或 Excel (.xlsx/.xls)，最大 50 MB</p>
        </Upload.Dragger>
        {fileState && (
          <Card size="small" className="industry-selected-file">
            <Space direction="vertical" size={2}>
              <Text strong>{fileState.filename}</Text>
              <Text type="secondary">{((upload.selected?.size ?? 0) / 1024 / 1024).toFixed(2)} MB</Text>
            </Space>
          </Card>
        )}
        <div>
          <label className="industry-field-label" htmlFor="industry-effective-date">生效日期</label>
          <Input
            id="industry-effective-date"
            type="date"
            disabled={busy}
            value={effectiveDate}
            onChange={(event) => { setEffectiveDate(event.target.value); resetPreview(); }}
          />
        </div>
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
        <div className="industry-preview" aria-label="导入预检结果">
          <div className="industry-preview__title">
            <Title level={5}>预检结果</Title>
            <Text type="secondary">有效 {preview.valid_rows} / 共 {preview.total_rows} 行</Text>
          </div>
          <Progress
            percent={preview.total_rows ? Math.round((preview.valid_rows / preview.total_rows) * 100) : 0}
            showInfo={false}
            status={preview.invalid_rows ? "exception" : "success"}
          />
          <div className="industry-preview__stats">
            {previewStats.map(([label, value, color]) => (
              <Tag key={label} color={color}>{label} {value}</Tag>
            ))}
          </div>
          {preview.warnings.length > 0 && (
            <Alert
              type="warning"
              showIcon
              message={`预检提示（${preview.warnings.length}）`}
              description={<ul>{preview.warnings.slice(0, 8).map((warning) => <li key={warning}>{warning}</li>)}</ul>}
            />
          )}
          {preview.sample.length > 0 && (
            <Table
              size="small"
              rowKey={(row) => String(row.stock_code)}
              pagination={false}
              scroll={{ x: 560, y: 260 }}
              dataSource={preview.sample}
              columns={[
                { title: "股票代码", dataIndex: "stock_code", width: 120 },
                { title: "简称", dataIndex: "stock_name", width: 100 },
                { title: "一级", dataIndex: "sw_level1_name", width: 110 },
                { title: "二级", dataIndex: "sw_level2_name", width: 110 },
                { title: "三级", dataIndex: "sw_level3_name", width: 110 },
              ]}
            />
          )}
          <div className="industry-force-override">
            <div>
              <Text strong>强制覆盖手工记录</Text>
              <div><Text type="secondary">仅在确认 Excel 数据优先时开启</Text></div>
            </div>
            <Switch disabled={busy} checked={forceOverride} onChange={setForceOverride} />
          </div>
          <Popconfirm
            title="确认写入行业数据库？"
            description={forceOverride ? "已开启强制覆盖，可能替换手工维护记录。" : "手工维护记录会保持不变。"}
            okText="确认导入"
            cancelText="取消"
            onConfirm={handleCommit}
          >
            <Button type="primary" block danger={forceOverride} loading={commitImport.isPending}>
              提交导入
            </Button>
          </Popconfirm>
        </div>
      )}
    </Drawer>
  );
}

export default function IndustryClassificationPage() {
  const { pageContainerStyle, pageDescriptionStyle, pageTitleStyle } = useStyles();
  const isAdmin = Boolean(useAuthStore((state) => state.user?.is_admin));
  const [filters, setFilters] = useState<IndustryListFilters>({ page: 1, page_size: PAGE_SIZE });
  const [queryDraft, setQueryDraft] = useState("");
  const [editorOpen, setEditorOpen] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const [editingRecord, setEditingRecord] = useState<IndustryRecord | null>(null);
  const statusQuery = useIndustryStatus();
  const hierarchyQuery = useIndustryHierarchy(filters);
  const recordsQuery = useIndustryRecords(filters);
  const createRecord = useCreateIndustryRecord();
  const updateRecord = useUpdateIndustryRecord();
  const deleteRecord = useDeleteIndustryRecord();
  const refreshIndustries = useRefreshIndustries();
  const updateRefreshPolicy = useUpdateIndustryRefreshPolicy();

  const updateFilter = (patch: Partial<IndustryListFilters>) => {
    setFilters((current) => ({ ...current, ...patch, page: patch.page ?? 1 }));
  };

  const openCreate = () => {
    setEditingRecord(null);
    setEditorOpen(true);
  };

  const handleSaveRecord = (value: IndustryRecordInput) => {
    const callbacks = {
      onSuccess: () => {
        message.success(editingRecord ? "行业记录已更新" : "行业记录已新增");
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

  const handleDelete = (record: IndustryRecord) => {
    deleteRecord.mutate(record.id, {
      onSuccess: () => message.success(`${record.stock_code} 已删除`),
      onError: (error) => message.error(`删除失败：${errorMessage(error)}`),
    });
  };

  const handleRefresh = () => {
    refreshIndustries.mutate(undefined, {
      onSuccess: (result) => message.success(`自动更新完成：新增 ${result.added}、更新 ${result.updated}`),
      onError: (error) => message.error(`自动更新失败：${errorMessage(error)}`),
    });
  };

  const handlePolicyChange = (enabled: boolean, intervalSeconds?: number) => {
    const refresh = statusQuery.data?.refresh;
    updateRefreshPolicy.mutate({
      enabled,
      interval_seconds: intervalSeconds ?? refresh?.interval_seconds ?? 7 * 24 * 60 * 60,
    }, {
      onSuccess: () => message.success("自动更新策略已保存"),
      onError: (error) => message.error(`保存失败：${errorMessage(error)}`),
    });
  };

  const columns: ColumnsType<IndustryRecord> = [
    {
      title: "股票",
      key: "stock",
      fixed: "left",
      width: 140,
      render: (_, record) => (
        <Space direction="vertical" size={0}>
          <Text strong copyable>{record.stock_code}</Text>
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
    { title: "一级行业", dataIndex: "sw_level1_name", width: 130, render: (value: string) => value || "—" },
    { title: "二级行业", dataIndex: "sw_level2_name", width: 150, render: (value: string) => value || "—" },
    { title: "三级行业", dataIndex: "sw_level3_name", width: 150, render: (value: string) => value || "—" },
    { title: "行业代码", dataIndex: "sw_industry_code", width: 110, render: (value: string) => value || "—" },
    { title: "更新时间", dataIndex: "updated_at", width: 170, render: formatDateTime },
    ...(isAdmin ? [{
      title: "操作",
      key: "actions",
      fixed: "right" as const,
      width: 104,
      render: (_: unknown, record: IndustryRecord) => (
        <Space>
          <Tooltip title="编辑">
            <Button type="text" icon={<EditOutlined />} aria-label={`编辑 ${record.stock_code}`} onClick={() => { setEditingRecord(record); setEditorOpen(true); }} />
          </Tooltip>
          <Popconfirm title={`删除 ${record.stock_code}？`} okText="删除" cancelText="取消" onConfirm={() => handleDelete(record)}>
            <Tooltip title="删除"><Button type="text" danger icon={<DeleteOutlined />} aria-label={`删除 ${record.stock_code}`} /></Tooltip>
          </Popconfirm>
        </Space>
      ),
    }] : []),
  ];

  const [exporting, setExporting] = useState(false);
  const handleExport = async () => {
    try {
      setExporting(true);
      await apiDownload("/industry-classification/export", "industry_classification_export.csv", {
        query: filters.query,
        market_group: filters.market_group,
        level1: filters.level1,
        level2: filters.level2,
        level3: filters.level3,
      });
      message.success("导出完成");
    } catch (err) {
      message.error(`导出失败: ${errorMessage(err)}`);
    } finally {
      setExporting(false);
    }
  };

  const status = statusQuery.data;
  const refresh = status?.refresh;
  const total = status?.stats.total ?? 0;

  return (
    <div style={pageContainerStyle} className="industry-classification-page">
      <header className="industry-page-header">
        <div>
          <div className="u-page-title u-page-title--compact">
            <Title level={3} style={pageTitleStyle}><DatabaseOutlined /> 申万行业基础数据</Title>
          </div>
          <Paragraph style={pageDescriptionStyle}>
            统一维护 A 股、港股和海外股票的申万行业归属，为搜索、选股和个股页面提供基础数据。
          </Paragraph>
        </div>
        <Space wrap>
          <Button icon={<ReloadOutlined />} loading={statusQuery.isFetching || recordsQuery.isFetching} onClick={() => { void statusQuery.refetch(); void recordsQuery.refetch(); }}>
            刷新页面
          </Button>
          <Button icon={<DownloadOutlined />} loading={exporting} onClick={() => void handleExport()}>
            导出 CSV
          </Button>
          {isAdmin && <Button icon={<FileExcelOutlined />} onClick={() => setImportOpen(true)}>批量导入</Button>}
          {isAdmin && <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>新增记录</Button>}
        </Space>
      </header>

      <SectionDataState
        isLoading={statusQuery.isLoading}
        error={statusQuery.error}
        onRetry={() => statusQuery.refetch()}
        errorTitle="行业数据状态加载失败"
        isEmpty={false}
      >
        <Row gutter={[12, 12]} className="industry-stat-grid">
          <Col xs={12} sm={8} xl={4}><Card><Statistic title="股票总数" value={total} /></Card></Col>
          <Col xs={12} sm={8} xl={4}><Card><Statistic title="A 股" value={status?.stats.market_counts.A ?? 0} /></Card></Col>
          <Col xs={12} sm={8} xl={4}><Card><Statistic title="港股" value={status?.stats.market_counts.HK ?? 0} /></Card></Col>
          <Col xs={12} sm={8} xl={4}><Card><Statistic title="海外" value={status?.stats.market_counts.OVERSEAS ?? 0} /></Card></Col>
          <Col xs={12} sm={8} xl={4}><Card><Statistic title="行业层级" value={`${status?.stats.level1_count ?? 0} / ${status?.stats.level2_count ?? 0} / ${status?.stats.level3_count ?? 0}`} suffix={<span className="industry-stat-suffix">一/二/三级</span>} /></Card></Col>
          <Col xs={12} sm={8} xl={4}><Card><Statistic title="最近更新时间" value={formatDateTime(status?.stats.latest_updated_at)} valueStyle={{ fontSize: 15 }} /></Card></Col>
        </Row>
      </SectionDataState>

      <Card className="industry-refresh-card">
        <div className="industry-refresh-card__main">
          <div className="industry-refresh-card__icon"><CloudSyncOutlined /></div>
          <div className="industry-refresh-card__copy">
            <Space wrap>
              <Text strong>自动更新 A 股一级、二级、三级行业</Text>
              <Tag color={refresh?.enabled ? "success" : "default"}>{refresh?.enabled ? "已启用" : "已停用"}</Tag>
            </Space>
            <Text type="secondary">
              最近成功：{formatDateTime(refresh?.last_succeeded_at)}
              {refresh?.last_error ? ` · 最近错误：${refresh.last_error}` : ""}
            </Text>
          </div>
          {isAdmin && (
            <Space wrap className="industry-refresh-card__actions">
              <Select
                aria-label="自动更新间隔"
                value={refresh?.interval_seconds ?? 7 * 24 * 60 * 60}
                options={REFRESH_INTERVAL_OPTIONS}
                disabled={updateRefreshPolicy.isPending}
                onChange={(value) => handlePolicyChange(refresh?.enabled ?? false, value)}
                style={{ width: 112 }}
              />
              <Switch
                checked={refresh?.enabled ?? false}
                checkedChildren="自动"
                unCheckedChildren="手动"
                loading={updateRefreshPolicy.isPending}
                onChange={(enabled) => handlePolicyChange(enabled)}
              />
              <Button icon={<CloudSyncOutlined />} loading={refreshIndustries.isPending} onClick={handleRefresh}>立即更新</Button>
            </Space>
          )}
        </div>
        {refresh?.last_error && <Alert className="industry-refresh-error" type="warning" showIcon message={refresh.last_error} />}
      </Card>

      <Card className="industry-table-card">
        <div className="industry-filters">
          <Input.Search
            allowClear
            value={queryDraft}
            placeholder="股票代码或公司简称"
            enterButton="搜索"
            onChange={(event) => setQueryDraft(event.target.value)}
            onSearch={(value) => updateFilter({ query: value.trim() })}
            className="industry-query"
          />
          <Select
            allowClear
            placeholder="全部市场"
            value={filters.market_group || undefined}
            options={MARKET_OPTIONS}
            onChange={(value) => updateFilter({ market_group: value, level1: undefined, level2: undefined, level3: undefined })}
          />
          <Select
            showSearch
            allowClear
            placeholder="一级行业"
            value={filters.level1 || undefined}
            options={(hierarchyQuery.data?.level1 ?? []).map((value) => ({ value, label: value }))}
            onChange={(value) => updateFilter({ level1: value, level2: undefined, level3: undefined })}
          />
          <Select
            showSearch
            allowClear
            placeholder="二级行业"
            value={filters.level2 || undefined}
            options={(hierarchyQuery.data?.level2 ?? []).map((value) => ({ value, label: value }))}
            onChange={(value) => updateFilter({ level2: value, level3: undefined })}
          />
          <Select
            showSearch
            allowClear
            placeholder="三级行业"
            value={filters.level3 || undefined}
            options={(hierarchyQuery.data?.level3 ?? []).map((value) => ({ value, label: value }))}
            onChange={(value) => updateFilter({ level3: value })}
          />
          <Button
            onClick={() => { setQueryDraft(""); setFilters({ page: 1, page_size: PAGE_SIZE }); }}
          >
            重置
          </Button>
        </div>

        <SectionDataState
          isLoading={recordsQuery.isLoading}
          error={recordsQuery.error}
          onRetry={() => recordsQuery.refetch()}
          errorTitle="行业记录加载失败"
          isEmpty={!recordsQuery.isLoading && !recordsQuery.error && (recordsQuery.data?.total ?? 0) === 0}
          emptyText="没有符合条件的行业记录"
        >
          <Table
            rowKey="id"
            size="middle"
            columns={columns}
            dataSource={recordsQuery.data?.items ?? []}
            loading={recordsQuery.isFetching && !recordsQuery.isLoading}
            scroll={{ x: 1080 }}
            pagination={{
              current: filters.page,
              pageSize: filters.page_size,
              total: recordsQuery.data?.total ?? 0,
              showSizeChanger: true,
              pageSizeOptions: [20, 50, 100],
              showTotal: (count) => `共 ${count} 条`,
              onChange: (page, pageSize) => setFilters((current) => ({ ...current, page: pageSize === current.page_size ? page : 1, page_size: pageSize })),
            }}
          />
        </SectionDataState>
      </Card>

      <RecordEditor
        open={editorOpen}
        record={editingRecord}
        saving={createRecord.isPending || updateRecord.isPending}
        onClose={() => setEditorOpen(false)}
        onSubmit={handleSaveRecord}
      />
      {isAdmin && <ImportDrawer open={importOpen} onClose={() => setImportOpen(false)} />}
    </div>
  );
}
