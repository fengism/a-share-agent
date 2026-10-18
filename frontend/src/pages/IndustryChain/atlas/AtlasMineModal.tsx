import { useState } from "react";
import { Input, Modal, message } from "antd";
import { useMineIndustryChainAtlas } from "../../../api/queryHooks/workflows";
import { useColors } from "../../../styles/ui";

export function AtlasMineModal({
  open,
  onClose,
  onSuccess,
}: {
  open: boolean;
  onClose: () => void;
  onSuccess: (name: string) => void;
}) {
  const colors = useColors();
  const [industryName, setIndustryName] = useState("");
  const mineMutation = useMineIndustryChainAtlas();

  const handleMine = () => {
    const name = industryName.trim();
    if (!name) return;
    mineMutation.mutate(
      { name },
      {
        onSuccess: () => {
          onSuccess(name);
        },
        onError: (err: Error) => {
          message.error({
            content: err.message || "挖掘失败，请确保该产业已有合格的完整深度分析存档",
            duration: 6,
          });
        },
      },
    );
  };

  return (
    <Modal
      title="从历史分析结果挖掘知识库条目"
      open={open}
      onCancel={onClose}
      onOk={handleMine}
      okText="执行挖掘"
      confirmLoading={mineMutation.isPending}
      okButtonProps={{ disabled: !industryName.trim() }}
      width="min(520px, calc(100vw - 24px))"
      destroyOnClose
    >
      <div style={{ marginBottom: 12, color: colors.textSecondary, fontSize: "var(--c-font-sm)" }}>
        系统将读取该产业最近一份通过质量检验的分析报告，自动解析各环节公司并与 A 股官方名录校验配对，合格后自动沉淀为知识库条目。
      </div>

      <div style={{ marginBottom: 8, fontSize: "var(--c-font-sm)", color: colors.textPrimary }}>
        产业链名称：
      </div>
      <Input
        placeholder="例如：半导体、低空经济、人形机器人"
        value={industryName}
        onChange={(e) => setIndustryName(e.target.value)}
        onPressEnter={handleMine}
      />
    </Modal>
  );
}
