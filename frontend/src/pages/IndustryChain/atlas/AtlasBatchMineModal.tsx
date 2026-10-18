import { useState } from "react";
import { RobotOutlined } from "@ant-design/icons";
import { Button, Modal, Spin, Table, Tag, message } from "antd";
import { useBatchMineIndustryChainAtlas } from "../../../api/queryHooks/workflows";
import { useColors } from "../../../styles/ui";
import type { AtlasBatchMineResponse } from "../../../types/stock";

export function AtlasBatchMineModal({
  open,
  onClose,
  onSuccess,
}: {
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const colors = useColors();
  const [result, setResult] = useState<AtlasBatchMineResponse | null>(null);
  const batchMineMutation = useBatchMineIndustryChainAtlas();

  const handleStart = async () => {
    try {
      const res = await batchMineMutation.mutateAsync();
      setResult(res);
      message.success(`批量挖掘完成！扫描 ${res.scanned} 份研报，成功挖掘/更新 ${res.succeeded} 条产业链`);
      onSuccess();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "批量挖掘失败";
      message.error(msg);
    }
  };

  const handleModalClose = () => {
    setResult(null);
    onClose();
  };

  return (
    <Modal
      title="批量挖掘历史产业链研报"
      open={open}
      onCancel={handleModalClose}
      footer={[
        <Button key="close" onClick={handleModalClose}>
          {result ? "完成并关闭" : "取消"}
        </Button>,
        !result && (
          <Button
            key="start"
            type="primary"
            loading={batchMineMutation.isPending}
            icon={<RobotOutlined />}
            onClick={handleStart}
          >
            开始扫描历史研报
          </Button>
        ),
      ]}
      width="min(680px, calc(100vw - 24px))"
      destroyOnClose
    >
      <div style={{ color: colors.textSecondary, marginBottom: 16, fontSize: "var(--c-font-sm)", lineHeight: "var(--c-leading-relaxed)" }}>
        系统将自动遍历所有已完成且通过质量门禁的产业链深度研究研报，按时间先后顺序智能增量提取上/中/下游代表公司与业务定位，经 A 股官方名录校验防幻觉后，智能增量合并沉淀到知识库图谱中。
      </div>

      {batchMineMutation.isPending && (
        <div style={{ textAlign: "center", padding: "36px 0" }}>
          <Spin />
          <div style={{ marginTop: 12, color: colors.textMuted }}>
            正在扫描历史研报并智能增量合并产业链…请稍候
          </div>
        </div>
      )}

      {result && (
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(80px, 1fr))",
              gap: 12,
              padding: 14,
              background: `${colors.primary}10`,
              borderRadius: 8,
              border: `1px solid ${colors.primary}30`,
              textAlign: "center",
            }}
          >
            <div>
              <div style={{ fontSize: 22, fontWeight: 700, color: colors.textPrimary }}>
                {result.scanned}
              </div>
              <div style={{ fontSize: 12, color: colors.textMuted }}>扫描历史研报</div>
            </div>
            <div>
              <div style={{ fontSize: 22, fontWeight: 700, color: colors.success }}>
                {result.succeeded}
              </div>
              <div style={{ fontSize: 12, color: colors.textMuted }}>成功入库/更新</div>
            </div>
            <div>
              <div style={{ fontSize: 22, fontWeight: 700, color: colors.textMuted }}>
                {result.skipped}
              </div>
              <div style={{ fontSize: 12, color: colors.textMuted }}>跳过/无需更新</div>
            </div>
          </div>

          {result.chains.length > 0 ? (
            <div style={{ maxHeight: 280, overflowY: "auto", border: `1px solid ${colors.border}`, borderRadius: 8 }}>
              <Table
                size="small"
                scroll={{ x: 380 }}
                pagination={false}
                dataSource={result.chains.map((c, i) => ({ ...c, key: i }))}
                columns={[
                  { title: "产业链名称", dataIndex: "name", key: "name", render: (name) => <b>{name}</b> },
                  {
                    title: "动作",
                    dataIndex: "action",
                    key: "action",
                    render: (action) => (
                      <Tag color={action === "created" ? "success" : "processing"}>
                        {action === "created" ? "新增入库" : "增量合并"}
                      </Tag>
                    ),
                  },
                  { title: "细分环节", dataIndex: "segment_count", key: "segment_count", align: "right" },
                  { title: "公司数", dataIndex: "company_count", key: "company_count", align: "right" },
                ]}
              />
            </div>
          ) : (
            <div style={{ textAlign: "center", padding: 24, color: colors.textMuted }}>
              暂无可挖掘的有效历史研报（需要完成状态且通过质量检验）
            </div>
          )}
        </div>
      )}
    </Modal>
  );
}
