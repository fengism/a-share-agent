import { useId, useRef, useState } from "react";
import { Input, Modal, Segmented, Space, Typography } from "antd";
import { CloudUploadOutlined, FileTextOutlined, SendOutlined } from "@ant-design/icons";
import type { PushRequest } from "../types/stock";

const { Text } = Typography;

interface PushModalProps {
  open: boolean;
  type: "daily_review" | "analysis" | "chat";
  date?: string;
  code?: string;
  onConfirm: (req: PushRequest) => Promise<boolean | void>;
  onCancel: () => void;
  loading?: boolean;
}

export default function PushModal({ open, type, date, code, onConfirm, onCancel, loading }: PushModalProps) {
  const isChat = type === "chat";
  const defaultTarget = "feishu";
  const [target, setTarget] = useState<"notion" | "feishu">(defaultTarget);
  const [feishuReceiver, setFeishuReceiver] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const isSubmittingRef = useRef(false);
  const receiverInputId = useId();
  const receiverHelpId = useId();
  const normalizedReceiver = feishuReceiver.trim();
  const receiverInvalid = normalizedReceiver.length > 0
    && !/^(?:oc_|ou_)[A-Za-z0-9_-]+$/.test(normalizedReceiver);
  const receiverDescription = normalizedReceiver
    ? `使用自定义${normalizedReceiver.startsWith("oc_") ? "群聊" : "用户"}接收人`
    : "使用系统默认接收人";

  const resetForm = () => {
    setTarget(defaultTarget);
    setFeishuReceiver("");
  };

  const handleOk = async () => {
    if (loading || isSubmittingRef.current || receiverInvalid) return;
    isSubmittingRef.current = true;
    setIsSubmitting(true);
    try {
      const req: PushRequest = {
        target: isChat ? "feishu" : target,
        type,
        date,
        code,
        feishu_receiver: (isChat || target === "feishu") ? normalizedReceiver : "",
      };
      const succeeded = await onConfirm(req);
      if (succeeded !== false) {
        resetForm();
      }
    } finally {
      isSubmittingRef.current = false;
      setIsSubmitting(false);
    }
  };

  const submitting = Boolean(loading || isSubmitting);
  const handleCancel = () => {
    if (submitting) return;
    resetForm();
    onCancel();
  };

  return (
    <Modal
      title={isChat ? "推送到飞书" : "推送报告"}
      open={open}
      onOk={handleOk}
      onCancel={handleCancel}
      okText={target === "feishu" ? "推送到飞书" : "转存到 Notion"}
      cancelText="取消"
      okButtonProps={{ loading: submitting, disabled: receiverInvalid, icon: <SendOutlined /> }}
      cancelButtonProps={{ disabled: submitting }}
      destroyOnHidden
    >
      <Space orientation="vertical" style={{ width: "100%" }}>
        {!isChat && (
          <div>
            <label htmlFor={`${receiverInputId}-target`} style={{ display: "block", fontWeight: 600, marginBottom: 8 }}>
              推送目标
            </label>
            <Segmented
              id={`${receiverInputId}-target`}
              aria-label="推送目标"
              block
              value={target}
              onChange={(value) => setTarget(value as "notion" | "feishu")}
              options={[
                { label: "飞书", value: "feishu", icon: <CloudUploadOutlined /> },
                { label: "Notion", value: "notion", icon: <FileTextOutlined /> },
              ]}
            />
          </div>
        )}
        {(isChat || target === "feishu") && (
          <div>
            <label htmlFor={receiverInputId} style={{ display: "block", fontWeight: 600 }}>接收人</label>
            <Text id={receiverHelpId} type="secondary" style={{ display: "block", marginBottom: 4 }}>
              群聊 ID（oc_）或用户 Open ID（ou_）；留空使用系统默认接收人
            </Text>
            <Input
              id={receiverInputId}
              aria-describedby={receiverHelpId}
              aria-invalid={receiverInvalid}
              status={receiverInvalid ? "error" : undefined}
              placeholder="使用默认接收人"
              value={feishuReceiver}
              onChange={(e) => setFeishuReceiver(e.target.value)}
              allowClear
            />
            <Text type={receiverInvalid ? "danger" : "secondary"} style={{ display: "block", marginTop: 6 }}>
              {receiverInvalid ? "接收人 ID 必须以 oc_ 或 ou_ 开头" : receiverDescription}
            </Text>
          </div>
        )}
      </Space>
    </Modal>
  );
}
