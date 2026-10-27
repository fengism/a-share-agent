import { useState } from "react";
import { Button, Input, Modal, Switch, Upload } from "antd";
import { useAuthStore } from "../../../store/authStore";
import { useColors } from "../../../styles/ui";
import { IMPORT_PLACEHOLDER } from "./constants";

export function AtlasImportModal({
  open,
  onClose,
  importing,
  onSubmit,
}: {
  open: boolean;
  onClose: () => void;
  importing: boolean;
  onSubmit: (content: string, overwrite: boolean) => void;
}) {
  const colors = useColors();
  const isAdmin = useAuthStore((s) => s.user?.is_admin ?? false);
  const [content, setContent] = useState("");
  const [overwrite, setOverwrite] = useState(false);

  return (
    <Modal
      title={isAdmin ? "导入产业链知识库" : "导入个人专属产业链"}
      open={open}
      onCancel={onClose}
      onOk={() => onSubmit(content, overwrite)}
      okText={isAdmin ? "导入公共知识库" : "导入个人知识库"}
      okButtonProps={{ disabled: !content.trim() || importing }}
      confirmLoading={importing}
      width="min(720px, calc(100vw - 24px))"
      destroyOnClose
    >
      <div style={{ marginBottom: 12, color: colors.textSecondary, fontSize: "var(--c-font-sm)" }}>
        {isAdmin
          ? "导入的产业链定义将存入全站公共知识库，供所有用户查看与分析先验参考。"
          : "导入的产业链定义将存入您的个人专属知识库，仅您可见，并在您执行该主题分析时作为专属先验知识。"}
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8, flexWrap: "wrap" }}>
        <Upload
          accept=".yaml,.yml,.json,.txt"
          maxCount={1}
          showUploadList={false}
          beforeUpload={(file) => {
            void file.text().then((text) => setContent(text));
            return false;
          }}
        >
          <Button size="small">选择文件（.yaml / .json）</Button>
        </Upload>
        <span style={{ color: colors.textMuted, fontSize: "var(--c-font-sm)" }}>
          或直接粘贴内容
        </span>
        <label
          style={{
            marginLeft: "auto",
            fontSize: "var(--c-font-md)",
            color: colors.textSecondary,
            cursor: "pointer",
          }}
        >
          覆盖同名产业链
          <Switch
            size="small"
            checked={overwrite}
            onChange={setOverwrite}
            style={{ marginLeft: 8 }}
          />
        </label>
      </div>
      <Input.TextArea
        value={content}
        onChange={(event) => setContent(event.target.value)}
        placeholder={IMPORT_PLACEHOLDER}
        rows={14}
        style={{ fontFamily: "var(--c-font-mono)", fontSize: "var(--c-font-sm)" }}
      />
    </Modal>
  );
}
