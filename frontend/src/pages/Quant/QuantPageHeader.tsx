import { ExperimentOutlined } from "@ant-design/icons";
import { Typography } from "antd";
import { useStyles } from "../../styles/ui";

const { Paragraph, Title } = Typography;

export default function QuantPageHeader() {
  const { pageDescriptionStyle, pageHeaderStyle, pageTitleStyle } = useStyles();

  return (
    <header className="quant-page-header" style={pageHeaderStyle}>
      <div className="quant-page-header__kicker"><ExperimentOutlined />策略实验室</div>
      <div className="u-page-title u-page-title--compact">
        <Title level={3} style={pageTitleStyle}>量化研究</Title>
      </div>
      <Paragraph style={{ ...pageDescriptionStyle, marginBottom: 0 }}>
        配置策略、跟踪任务，再单独查看收益与风险分析。
      </Paragraph>
    </header>
  );
}
