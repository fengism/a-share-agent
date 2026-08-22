import { InputNumber, Modal, Select, Space } from "antd";
import PushModal from "../../../components/PushModal";
import type { WatchlistAlertCondition } from "../../../types/watchlist";
import type { ChatResultActionController } from "../useChatResultActionController";

const ALERT_CONDITIONS: Array<{ value: WatchlistAlertCondition; label: string }> = [
  { value: "price_above", label: "价格高于" },
  { value: "price_below", label: "价格低于" },
  { value: "change_pct_above", label: "涨跌幅高于" },
  { value: "change_pct_below", label: "涨跌幅低于" },
];

export function ChatActionDialogs({ controller }: { controller: ChatResultActionController }) {
  return (
    <>
      <PushModal
        open={controller.pushModalOpen}
        type="chat"
        onConfirm={controller.handlePushConfirm}
        onCancel={controller.closePush}
        loading={controller.isPushPending}
      />
      <Modal
        title="将对话结果设置为提醒"
        open={controller.alertCodes.length > 0}
        onCancel={controller.closeAlert}
        onOk={() => void controller.handleCreateResultAlert()}
        okText="创建提醒"
        okButtonProps={{
          disabled: !controller.alertStockCode || controller.alertThreshold == null,
          loading: controller.isAlertSaving,
        }}
      >
        <Space orientation="vertical" style={{ width: "100%" }}>
          <Select
            aria-label="提醒股票"
            value={controller.alertStockCode}
            onChange={controller.setAlertStockCode}
            options={controller.alertCodes.map((stockCode) => ({ value: stockCode, label: stockCode }))}
            style={{ width: "100%" }}
          />
          <Select
            aria-label="提醒条件"
            value={controller.alertCondition}
            onChange={controller.setAlertCondition}
            options={ALERT_CONDITIONS}
            style={{ width: "100%" }}
          />
          <InputNumber
            aria-label="提醒阈值"
            value={controller.alertThreshold}
            onChange={controller.setAlertThreshold}
            placeholder={controller.alertCondition.startsWith("change_pct") ? "阈值（%）" : "价格阈值"}
            style={{ width: "100%" }}
          />
        </Space>
      </Modal>
    </>
  );
}
