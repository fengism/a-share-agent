import { useState } from "react";
import { Input, Modal, Radio, message } from "antd";
import { useMineIndustryChainAtlas } from "../../../api/queryHooks/workflows";
import { useAuthStore } from "../../../store/authStore";
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
  const isAdmin = useAuthStore((s) => s.user?.is_admin ?? false);
  const [industryName, setIndustryName] = useState("");
  const [targetScope, setTargetScope] = useState<"user" | "global">("user");
  const mineMutation = useMineIndustryChainAtlas();

  const handleMine = () => {
    const name = industryName.trim();
    if (!name) return;
    mineMutation.mutate(
      { name, scope: isAdmin ? targetScope : "user" },
      {
        onSuccess: (chain) => {
          const tip = chain?.source === "user"
            ? `已沉淀为个人专属知识库：${name}`
            : `已沉淀为公共知识库：${name}`;
          message.success(tip);
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
      title={isAdmin ? "从历史分析结果挖掘知识库条目" : "沉淀为个人专属知识库"}
      open={open}
      onCancel={onClose}
      onOk={handleMine}
      okText="执行挖掘沉淀"
      confirmLoading={mineMutation.isPending}
      okButtonProps={{ disabled: !industryName.trim() }}
      width="min(520px, calc(100vw - 24px))"
      destroyOnClose
    >
      <div style={{ marginBottom: 12, color: colors.textSecondary, fontSize: "var(--c-font-sm)" }}>
        {isAdmin
          ? "系统将读取该产业最近一份通过质量检验的分析报告，自动解析各环节公司并与 A 股官方名录校验配对，合格后沉淀为知识库条目。"
          : "系统将读取您该产业最近一份通过质量检验的分析报告，自动解析各环节代表公司并校验配对，合格后沉淀为您的个人专属知识库条目。"}
      </div>

      <div style={{ marginBottom: 8, fontSize: "var(--c-font-sm)", color: colors.textPrimary }}>
        产业链名称：
      </div>
      <Input
        placeholder="例如：半导体、低空经济、人形机器人"
        value={industryName}
        onChange={(e) => setIndustryName(e.target.value)}
        onPressEnter={handleMine}
        style={{ marginBottom: isAdmin ? 14 : 0 }}
      />

      {isAdmin && (
        <div>
          <div style={{ marginBottom: 6, fontSize: "var(--c-font-sm)", color: colors.textPrimary }}>
            沉淀归属：
          </div>
          <Radio.Group
            size="small"
            value={targetScope}
            onChange={(e) => setTargetScope(e.target.value)}
          >
            <Radio.Button value="user">个人专属知识库</Radio.Button>
            <Radio.Button value="global">全站公共知识库</Radio.Button>
          </Radio.Group>
        </div>
      )}
    </Modal>
  );
}
