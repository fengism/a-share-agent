import { ExperimentOutlined, FundOutlined } from "@ant-design/icons";
import { Typography } from "antd";

const { Paragraph, Title } = Typography;

export default function QuantPageHeader() {
  return (
    <header className="quant-page-header">
      <div className="quant-page-header__identity">
        <span className="quant-page-header__mark"><FundOutlined /></span>
        <div>
          <div className="quant-page-header__kicker"><ExperimentOutlined />策略实验室</div>
          <div className="u-page-title u-page-title--compact">
            <Title level={3}>量化研究</Title>
          </div>
        </div>
      </div>
      <Paragraph className="quant-page-header__description">
        配置策略、跟踪任务，再单独查看收益与风险分析。
      </Paragraph>
      <div className="quant-page-header__status" aria-label="回测类型">
        <ExperimentOutlined aria-hidden="true" />
        <span>研究模式</span>
        <strong>日线回测</strong>
      </div>
    </header>
  );
}
