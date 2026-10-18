import { useState } from "react";
import { Button, Input, Modal, Switch, Upload } from "antd";
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
  const [content, setContent] = useState("");
  const [overwrite, setOverwrite] = useState(false);

  return (
    <Modal
      title="导入产业链知识库"
      open={open}
      onCancel={onClose}
      onOk={() => onSubmit(content, overwrite)}
      okText="导入"
      okButtonProps={{ disabled: !content.trim() || importing }}
      confirmLoading={importing}
      width="min(720px, calc(100vw - 24px))"
      destroyOnClose
    >
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
