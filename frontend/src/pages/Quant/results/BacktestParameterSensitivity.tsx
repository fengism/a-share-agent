import { useMemo, useState } from "react";
import {
  Alert,
  Button,
  Card,
  Col,
  Empty,
  Form,
  Input,
  Row,
  Select,
  Space,
  Spin,
  Switch,
  Table,
  Tag,
  Tooltip,
  Typography,
  message,
} from "antd";
import {
  CheckCircleOutlined,
  CompassOutlined,
  ExperimentOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";
import {
  useScanQuantParameterSensitivity,
  type QuantParameterScanPoint,
  type QuantParameterScanResult,
  type QuantStrategyConfig,
} from "../../../api/queries";
import { useColors, useStyles } from "../../../styles/ui";
import { formatPercent, formatRatio } from "./formatters";

const { Text } = Typography;

interface BacktestParameterSensitivityProps {
  runId?: string;
  strategy?: QuantStrategyConfig;
  onApplyOptimal?: (
    param1Name: string,
    param1Val: number | string | boolean,
    param2Name?: string,
    param2Val?: number | string | boolean,
  ) => void;
}

function parseValues(input: string): (number | string)[] {
  return input
    .split(/[,，\s]+/)
    .map((s) => s.trim())
    .filter(Boolean)
    .map((s) => {
      const num = Number(s);
      return Number.isFinite(num) ? num : s;
    });
}

function generateDefaultSteps(defaultValue: unknown): string {
  if (typeof defaultValue === "number") {
    if (defaultValue <= 1 && defaultValue > 0) {
      // 比例型参数（如止损 0.05）
      return [0.03, 0.05, 0.08, 0.1, 0.15].join(", ");
    }
    const step = Math.max(1, Math.round(defaultValue * 0.25));
    const vals = [
      Math.max(2, defaultValue - 2 * step),
      Math.max(2, defaultValue - step),
      defaultValue,
      defaultValue + step,
      defaultValue + 2 * step,
    ];
    return Array.from(new Set(vals)).join(", ");
  }
  return "5, 10, 15, 20, 25, 30";
}

export default function BacktestParameterSensitivity({
  runId,
  strategy,
  onApplyOptimal,
}: BacktestParameterSensitivityProps) {
  const colors = useColors();
  const { cardStyle } = useStyles();
  const scanMutation = useScanQuantParameterSensitivity();

  const availableParams = useMemo(() => {
    const keys = Object.keys(strategy?.parameters ?? {});
    return keys.length > 0 ? keys : ["fast_period", "slow_period"];
  }, [strategy]);

  const [param1Name, setParam1Name] = useState<string>(() => availableParams[0] || "fast_period");
  const [param1Input, setParam1Input] = useState<string>(() =>
    generateDefaultSteps(strategy?.parameters?.[availableParams[0]] ?? 10),
  );

  const [enableParam2, setEnableParam2] = useState<boolean>(() => availableParams.length > 1);
  const [param2Name, setParam2Name] = useState<string>(
    () => availableParams[1] || "slow_period",
  );
  const [param2Input, setParam2Input] = useState<string>(() =>
    generateDefaultSteps(strategy?.parameters?.[availableParams[1]] ?? 20),
  );

  const [scanResult, setScanResult] = useState<QuantParameterScanResult | null>(null);

  const handleParam1Change = (name: string) => {
    setParam1Name(name);
    setParam1Input(generateDefaultSteps(strategy?.parameters?.[name] ?? 10));
  };

  const handleParam2Change = (name: string) => {
    setParam2Name(name);
    setParam2Input(generateDefaultSteps(strategy?.parameters?.[name] ?? 20));
  };

  const handleRunScan = async () => {
    if (!runId) {
      message.error("请先选中已完成的回测任务");
      return;
    }
    const p1Values = parseValues(param1Input);
    if (p1Values.length === 0) {
      message.warning("请输入参数 1 的扫描取值");
      return;
    }
    const p2Values = enableParam2 ? parseValues(param2Input) : null;
    if (enableParam2 && (!p2Values || p2Values.length === 0)) {
      message.warning("请输入参数 2 的扫描取值");
      return;
    }

    try {
      const res = await scanMutation.mutateAsync({
        runId,
        request: {
          param1_name: param1Name,
          param1_values: p1Values,
          param2_name: enableParam2 ? param2Name : null,
          param2_values: enableParam2 ? p2Values : null,
        },
      });
      setScanResult(res);
      message.success(`敏感性分析完成，已评估 ${res.points.length} 组参数组合`);
    } catch (err: unknown) {
      const errMessage = err instanceof Error ? err.message : "参数敏感性扫描失败";
      message.error(errMessage);
    }
  };

  const handleApply = (optimal: QuantParameterScanPoint) => {
    if (onApplyOptimal) {
      onApplyOptimal(
        param1Name,
        optimal.param1_value as string | number | boolean,
        enableParam2 ? param2Name : undefined,
        enableParam2 ? ((optimal.param2_value as string | number | boolean | null | undefined) ?? undefined) : undefined,
      );
      message.success("已将最优参数填入回测配置");
    }
  };

  // 构造热力网格表格数据
  const matrixData = useMemo(() => {
    if (!scanResult) return null;
    const { param1_values, param2_values, points } = scanResult;
    const pointMap = new Map<string, QuantParameterScanPoint>();
    for (const pt of points) {
      pointMap.set(`${pt.param1_value}__${pt.param2_value ?? "none"}`, pt);
    }

    if (!param2_values || param2_values.length === 0) {
      // 1D 网格
      const rows = param1_values.map((v1) => {
        const pt = pointMap.get(`${v1}__none`);
        return {
          key: String(v1),
          param1: v1,
          point: pt,
        };
      });
      return { is2D: false, rows };
    }

    // 2D 网格
    const rows = param1_values.map((v1) => {
      const rowObj: Record<string, unknown> = { key: String(v1), param1: v1 };
      for (const v2 of param2_values) {
        rowObj[String(v2)] = pointMap.get(`${v1}__${v2}`);
      }
      return rowObj;
    });
    return { is2D: true, cols: param2_values, rows };
  }, [scanResult]);

  return (
    <Card
      title={(
        <Space size={8}>
          <ExperimentOutlined style={{ color: colors.primary }} />
          <span>策略参数敏感性与稳健度分析 (Parameter Robustness Scan)</span>
        </Space>
      )}
      size="small"
      style={cardStyle}
      className="quant-result-card"
    >
      <div style={{ marginBottom: 16 }}>
        <p style={{ color: "var(--color-text-secondary, #8c8c8c)", fontSize: 13, margin: "0 0 12px" }}>
          基于当前回测的纯内存高速复算引擎，扫描策略参数空间网格。可识别策略是否处于「稳健高原」还是面临「参数过拟合悬崖」。
        </p>

        <Form layout="vertical" size="small">
          <Row gutter={[16, 12]}>
            <Col xs={24} md={10}>
              <Form.Item label="主要参数 1" style={{ marginBottom: 8 }}>
                <Space.Compact block>
                  <Select
                    style={{ width: "40%" }}
                    value={param1Name}
                    onChange={handleParam1Change}
                    options={availableParams.map((p) => ({ value: p, label: p }))}
                  />
                  <Input
                    style={{ width: "60%" }}
                    value={param1Input}
                    onChange={(e) => setParam1Input(e.target.value)}
                    placeholder="逗号分隔，如 5, 10, 15, 20"
                  />
                </Space.Compact>
              </Form.Item>
            </Col>

            <Col xs={24} md={10}>
              <Form.Item
                label={(
                  <Space size={6}>
                    <span>联合参数 2 (可选)</span>
                    <Switch
                      size="small"
                      checked={enableParam2}
                      onChange={setEnableParam2}
                    />
                  </Space>
                )}
                style={{ marginBottom: 8 }}
              >
                <Space.Compact block>
                  <Select
                    style={{ width: "40%" }}
                    disabled={!enableParam2}
                    value={param2Name}
                    onChange={handleParam2Change}
                    options={availableParams.map((p) => ({ value: p, label: p }))}
                  />
                  <Input
                    style={{ width: "60%" }}
                    disabled={!enableParam2}
                    value={param2Input}
                    onChange={(e) => setParam2Input(e.target.value)}
                    placeholder="逗号分隔，如 15, 20, 25, 30"
                  />
                </Space.Compact>
              </Form.Item>
            </Col>

            <Col xs={24} md={4} style={{ display: "flex", alignItems: "flex-end" }}>
              <Button
                type="primary"
                icon={<CompassOutlined />}
                loading={scanMutation.isPending}
                disabled={!runId}
                onClick={handleRunScan}
                style={{ width: "100%", marginBottom: 8 }}
              >
                开始网格扫描
              </Button>
            </Col>
          </Row>
        </Form>
      </div>

      {scanMutation.isPending && (
        <div style={{ padding: "32px 0", textAlign: "center" }}>
          <Spin tip="正在进行高速内存网格并行复算..." />
        </div>
      )}

      {scanResult && (
        <div>
          <Alert
            style={{ marginBottom: 16 }}
            type={scanResult.robustness_score >= 70 ? "success" : scanResult.robustness_score >= 45 ? "info" : "warning"}
            showIcon
            icon={<CheckCircleOutlined />}
            description={(
              <Space wrap size={16} align="center">
                <span>
                  <strong>参数稳健度评分：</strong>
                  <Tag color={scanResult.robustness_score >= 70 ? "success" : "warning"} style={{ fontSize: 13, fontWeight: "bold" }}>
                    {scanResult.robustness_score} 分 ({scanResult.robustness_score >= 70 ? "稳健高原" : scanResult.robustness_score >= 45 ? "中等稳健" : "较敏感"})
                  </Tag>
                </span>
                <span>
                  <strong>参数盈利比例：</strong>
                  <Text style={{ color: scanResult.profitable_ratio >= 60 ? colors.up : colors.down, fontWeight: "bold" }}>
                    {scanResult.profitable_ratio}%
                  </Text>
                </span>
                {scanResult.optimal_point && (
                  <span>
                    <strong>最优参数组合：</strong>
                    <Tag color="cyan">
                      {scanResult.param1_name}={String(scanResult.optimal_point.param1_value)}
                      {scanResult.param2_name && scanResult.optimal_point.param2_value != null ? `, ${scanResult.param2_name}=${String(scanResult.optimal_point.param2_value)}` : ""}
                      {" "}(夏普: {scanResult.optimal_point.sharpe_ratio ?? "-"}, 收益: {formatPercent(scanResult.optimal_point.total_return)})
                    </Tag>
                    {onApplyOptimal && (
                      <Button
                        size="small"
                        type="link"
                        icon={<ThunderboltOutlined />}
                        onClick={() => handleApply(scanResult.optimal_point!)}
                      >
                        一键应用
                      </Button>
                    )}
                  </span>
                )}
              </Space>
            )}
          />

          {matrixData && (
            <div style={{ overflowX: "auto" }}>
              <div style={{ marginBottom: 8, fontSize: 12, color: "var(--color-text-secondary, #8c8c8c)" }}>
                表格单元格数值为 <strong>夏普比率 (Sharpe)</strong>，悬停查看收益率与回撤。绿色代表高风险报酬，红色代表弱势或亏损。
              </div>

              {!matrixData.is2D ? (
                <Table
                  size="small"
                  pagination={false}
                  dataSource={matrixData.rows}
                  columns={[
                    { title: `${scanResult.param1_name}`, dataIndex: "param1", width: 120 },
                    {
                      title: "夏普比率",
                      render: (_, row: { point?: QuantParameterScanPoint }) => {
                        const pt = row.point;
                        if (!pt) return "-";
                        const isOptimal = scanResult.optimal_point && scanResult.optimal_point.param1_value === pt.param1_value;
                        const bg = (pt.sharpe_ratio ?? 0) >= 1.0 ? "rgba(46, 204, 113, 0.18)" : (pt.sharpe_ratio ?? 0) > 0 ? "rgba(46, 204, 113, 0.08)" : "rgba(231, 76, 60, 0.1)";
                        return (
                          <Tooltip title={`累计收益: ${formatPercent(pt.total_return)} | 最大回撤: ${formatPercent(pt.max_drawdown)}`}>
                            <span style={{ padding: "4px 8px", borderRadius: 4, background: bg, fontWeight: isOptimal ? "bold" : "normal" }}>
                              {formatRatio(pt.sharpe_ratio)} {isOptimal ? "★" : ""}
                            </span>
                          </Tooltip>
                        );
                      },
                    },
                    {
                      title: "累计收益",
                      render: (_, row: { point?: QuantParameterScanPoint }) => (
                        <Text style={{ color: (row.point?.total_return ?? 0) >= 0 ? colors.up : colors.down }}>
                          {formatPercent(row.point?.total_return)}
                        </Text>
                      ),
                    },
                    {
                      title: "最大回撤",
                      render: (_, row: { point?: QuantParameterScanPoint }) => formatPercent(row.point?.max_drawdown),
                    },
                    {
                      title: "胜率",
                      render: (_, row: { point?: QuantParameterScanPoint }) => formatPercent(row.point?.win_rate),
                    },
                  ]}
                />
              ) : (
                <Table
                  size="small"
                  pagination={false}
                  dataSource={matrixData.rows}
                  columns={[
                    {
                      title: `${scanResult.param1_name} \\ ${scanResult.param2_name}`,
                      dataIndex: "param1",
                      fixed: "left",
                      width: 140,
                      render: (val) => <strong>{String(val)}</strong>,
                    },
                    ...(matrixData.cols?.map((colVal) => ({
                      title: `${String(colVal)}`,
                      dataIndex: String(colVal),
                      align: "center" as const,
                      render: (pt?: QuantParameterScanPoint) => {
                        if (!pt) return "-";
                        const isOptimal =
                          scanResult.optimal_point &&
                          scanResult.optimal_point.param1_value === pt.param1_value &&
                          scanResult.optimal_point.param2_value === pt.param2_value;
                        const sr = pt.sharpe_ratio ?? 0;
                        const bg = sr >= 1.2
                          ? "rgba(46, 204, 113, 0.28)"
                          : sr >= 0.6
                          ? "rgba(46, 204, 113, 0.16)"
                          : sr > 0
                          ? "rgba(46, 204, 113, 0.08)"
                          : "rgba(231, 76, 60, 0.12)";

                        return (
                          <Tooltip title={`收益: ${formatPercent(pt.total_return)} | 回撤: ${formatPercent(pt.max_drawdown)} | 胜率: ${formatPercent(pt.win_rate)}`}>
                            <div style={{ padding: "4px 6px", borderRadius: 4, background: bg, border: isOptimal ? `2px solid ${colors.primary}` : "none" }}>
                              <span style={{ fontWeight: isOptimal ? "bold" : "normal" }}>
                                {formatRatio(pt.sharpe_ratio)} {isOptimal ? "★" : ""}
                              </span>
                            </div>
                          </Tooltip>
                        );
                      },
                    })) ?? []),
                  ]}
                />
              )}
            </div>
          )}
        </div>
      )}

      {!scanResult && !scanMutation.isPending && (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description="点击「开始网格扫描」对当前策略进行多维参数高原稳定性测试"
        />
      )}
    </Card>
  );
}
