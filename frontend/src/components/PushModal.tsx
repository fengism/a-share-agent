import { useState } from "react";
import { Modal, Radio, Input, Space, Typography } from "antd";
import { SendOutlined } from "@ant-design/icons";
import type { PushRequest } from "../types/stock";

const { Text } = Typography;

interface PushModalProps {
  open: boolean;
  type: "daily_review" | "analysis" | "chat";
  date?: string;
  code?: string;
  onConfirm: (req: PushRequest) => Promise<void>;
  onCancel: () => void;
  loading?: boolean;
}

export default function PushModal({ open, type, date, code, onConfirm, onCancel, loading }: PushModalProps) {
  const isChat = type === "chat";
  const [target, setTarget] = useState<"notion" | "feishu">(isChat ? "feishu" : "notion");
  const [feishuReceiver, setFeishuReceiver] = useState("");

  const handleOk = async () => {
    const req: PushRequest = {
      target: isChat ? "feishu" : target,
      type,
      date,
      code,
      feishu_receiver: (isChat || target === "feishu") ? feishuReceiver : "",
    };
    await onConfirm(req);
    setFeishuReceiver("");
  };

  return (
    <Modal
      title="推送到飞书"
      open={open}
      onOk={handleOk}
      onCancel={onCancel}
      okText="推送"
      okButtonProps={{ loading, icon: <SendOutlined /> }}
      destroyOnClose
    >
      <Space direction="vertical" style={{ width: "100%" }}>
        {!isChat && (
          <div>
            <Text strong>推送目标</Text>
            <Radio.Group
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
            <Text strong>接收人</Text>
            <Text type="secondary" style={{ display: "block", marginBottom: 4 }}>
              输入群聊 ID（oc_ 开头）或用户 Open ID（ou_ 开头）
            </Text>
            <Input
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
