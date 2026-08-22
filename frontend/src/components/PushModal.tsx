import { useId, useRef, useState } from "react";
import { Modal, Radio, Input, Space, Typography } from "antd";
import { SendOutlined } from "@ant-design/icons";
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
  const defaultTarget = isChat ? "feishu" : "notion";
  const [target, setTarget] = useState<"notion" | "feishu">(defaultTarget);
  const [feishuReceiver, setFeishuReceiver] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const isSubmittingRef = useRef(false);
  const receiverInputId = useId();
  const receiverHelpId = useId();

  const handleOk = async () => {
    if (loading || isSubmittingRef.current) return;
    isSubmittingRef.current = true;
    setIsSubmitting(true);
    try {
      const req: PushRequest = {
        target: isChat ? "feishu" : target,
        type,
        date,
        code,
        feishu_receiver: (isChat || target === "feishu") ? feishuReceiver : "",
      };
      const succeeded = await onConfirm(req);
      if (succeeded !== false) {
        setTarget(defaultTarget);
        setFeishuReceiver("");
      }
    } finally {
      isSubmittingRef.current = false;
      setIsSubmitting(false);
    }
  };

  const submitting = Boolean(loading || isSubmitting);

  return (
    <Modal
      title={isChat ? "推送到飞书" : "推送报告"}
      open={open}
      onOk={handleOk}
      onCancel={onCancel}
      okText="推送"
      cancelText="取消"
      okButtonProps={{ loading: submitting, icon: <SendOutlined /> }}
      cancelButtonProps={{ disabled: submitting }}
      destroyOnHidden
    >
      <Space orientation="vertical" style={{ width: "100%" }}>
        {!isChat && (
          <div>
            <Text strong>推送目标</Text>
            <Radio.Group
              aria-label="推送目标"
              value={target}
              onChange={(e) => setTarget(e.target.value)}
              style={{ marginLeft: 16 }}
            >
              <Radio value="notion">Notion</Radio>
              <Radio value="feishu">飞书</Radio>
            </Radio.Group>
          </div>
        )}
        {(isChat || target === "feishu") && (
          <div>
            <label htmlFor={receiverInputId} style={{ display: "block", fontWeight: 600 }}>接收人</label>
            <Text id={receiverHelpId} type="secondary" style={{ display: "block", marginBottom: 4 }}>
              输入群聊 ID（oc_ 开头）或用户 Open ID（ou_ 开头）
            </Text>
            <Input
              id={receiverInputId}
              aria-describedby={receiverHelpId}
              placeholder="oc_xxxxxxxx 或 ou_xxxxxxxx"
              value={feishuReceiver}
              onChange={(e) => setFeishuReceiver(e.target.value)}
            />
          </div>
        )}
      </Space>
    </Modal>
  );
}
