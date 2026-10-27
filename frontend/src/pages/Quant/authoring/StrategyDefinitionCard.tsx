import { CheckCircleOutlined, CodeOutlined, RocketOutlined, SaveOutlined } from "@ant-design/icons";
import { Button, Card, Input, Popconfirm, Space, Typography } from "antd";
import type { QuantStrategyRegistryStatus } from "../../../api/queries";

const { Text } = Typography;

interface StrategyDefinitionCardProps {
  canPublish: boolean;
  /** 是否能发布到全局策略注册表（仅管理员） */
  canManagePublish: boolean;
  definitionText: string;
  isDefinitionDirty: boolean;
  isDefinitionLocked: boolean;
  isPublishing: boolean;
  isSaving: boolean;
  isValidating: boolean;
  registry?: QuantStrategyRegistryStatus;
  onDefinitionChange: (value: string) => void;
  onPublish: () => Promise<void>;
  onSave: () => Promise<void>;
  onValidate: () => Promise<void>;
}

export default function StrategyDefinitionCard({
  canPublish,
  canManagePublish,
  definitionText,
  isDefinitionDirty,
  isDefinitionLocked,
  isPublishing,
  isSaving,
  isValidating,
  registry,
  onDefinitionChange,
  onPublish,
  onSave,
  onValidate,
}: StrategyDefinitionCardProps) {
  return (
    <Card className="quant-authoring-card" title={<Space><CodeOutlined />定义编辑器</Space>}>
      <Input.TextArea
        className="quant-definition-editor"
        value={definitionText}
        onChange={(event) => onDefinitionChange(event.target.value)}
        rows={20}
        spellCheck={false}
        disabled={isDefinitionLocked}
        placeholder="生成草稿后可在这里编辑完整 StrategyDefinition JSON"
      />
      <Space wrap>
        <Button
          icon={<SaveOutlined />}
          disabled={isDefinitionLocked || !isDefinitionDirty}
          loading={isSaving}
          onClick={() => void onSave()}
        >
          保存定义
        </Button>
        <Button
          icon={<CheckCircleOutlined />}
          disabled={isDefinitionLocked || isDefinitionDirty}
          loading={isValidating}
          onClick={() => void onValidate()}
        >
          编译校验
        </Button>
        {canManagePublish && (
          <Popconfirm
            title="确认发布当前策略？"
            description="系统将校验定义哈希与质量门禁并原子发布；请求中断后可安全重试。"
            okText="确认发布"
            cancelText="取消"
            onConfirm={() => void onPublish()}
          >
            <Button
              type="primary"
              icon={<RocketOutlined />}
              disabled={!canPublish}
              loading={isPublishing}
            >
              发布策略
            </Button>
          </Popconfirm>
        )}
      </Space>
      {canManagePublish && (
        <Text type="secondary">
          Registry generation：{registry?.generation ?? "-"}，发布目录：{registry?.published_directory ?? "未配置"}
        </Text>
      )}
    </Card>
  );
}
