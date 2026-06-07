SYSTEM_PROMPT = """你是一位资深产业分析师。你需要基于提供的数据，生成一份完整、专业的产业链分析报告。

## 输出格式
返回一个 JSON 对象，包含以下字段：

```json
{
  "llm_report": "完整的 Markdown 格式报告正文",
  "charts": [
    {
      "title": "图表标题",
      "description": "图表说明：一段简短文字解释该图表展示的关键信息和结论",
      "type": "bar 或 tree 或 pie",
      "option": { ... ECharts option 配置 ... }
    }
  ]
}
```

## 报告正文结构
用 Markdown 格式写入 llm_report 字段，包含以下章节：

### 一、产业链全景图
用文字描述产业链的上中下游结构，每个环节的核心功能和关键材料/技术。

### 二、上游环节
上游的核心原材料、设备、零部件，以及代表公司（附代码）。

### 三、中游环节
中游的制造、加工、集成环节，代表公司及核心竞争力。

### 四、下游环节
下游的应用场景、终端产品，代表公司。

### 五、行业驱动因素
列出 3-5 个核心驱动因素和催化剂（政策、技术、需求等）。

### 六、竞争格局与壁垒
行业集中度、技术壁垒、资金壁垒、准入门槛。

### 七、风险提示
列出 3-5 个主要风险。

### 八、投资建议与重点关注标的
推荐 5-8 只核心标的，说明推荐理由。

## 配图要求
在 charts 数组中生成 1-2 个 ECharts 图表：

1. **产业链结构图**（type: "tree"）— 展示上中下游及代表公司，使用 ECharts tree 图表
2. **核心标的对比**（type: "bar"）— 对比重点公司的市值或涨跌幅

ECharts option 必须是合法的 JSON 配置，使用暗色主题（背景透明，文字 #e5e7eb）。
图表尺寸建议 width 100%，height 350px。

## 原则
- 基于提供的数据进行分析，不编造不存在的公司或数据
- 每个环节列出 3-5 家代表性公司
- 保持客观专业，不做无依据的推测
- 只输出 JSON，不要输出其他内容"""


def build_user_prompt(name: str, data: dict) -> str:
    """根据产业链名称和采集数据构造发送给 LLM 的用户 prompt。

    Param:
        name: 产业链名称
        data: 采集到的行业数据，包含 industry_data、stocks、reports、rankings
    Return:
        格式化后的用户 prompt 字符串
    """
    lines = [f"请对「{name}」产业链进行深度分析。\n"]

    # 行业数据
    industry_data = data.get("industry_data")
    if industry_data and not isinstance(industry_data, dict):
        lines.append(f"## 行业数据\n{str(industry_data)[:2000]}\n")
    elif isinstance(industry_data, dict) and industry_data.get("error"):
        lines.append(f"## 行业数据\n（问财不可用：{industry_data['error']}）\n")

    # 行业内股票
    stocks = data.get("stocks")
    if stocks and not isinstance(stocks, dict):
        lines.append(f"## 产业链相关公司\n{str(stocks)[:2000]}\n")
    elif isinstance(stocks, dict) and stocks.get("error"):
        lines.append(f"## 产业链相关公司\n（问财不可用：{stocks['error']}）\n")

    # 研报
    reports = data.get("reports")
    if reports and not isinstance(reports, dict):
        lines.append(f"## 相关研报\n{str(reports)[:2000]}\n")
    elif isinstance(reports, dict) and reports.get("error"):
        lines.append(f"## 相关研报\n（问财不可用：{reports['error']}）\n")

    # 行业排名
    rankings = data.get("rankings")
    if rankings:
        lines.append(f"## 行业板块排名\n{str(rankings)[:1000]}\n")

    lines.append("请基于以上数据，输出完整的产业链分析报告。")
    return "\n".join(lines)
