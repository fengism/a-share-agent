"""Deterministic research questions, not a source of industry facts."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ResearchTemplate:
    key: str
    name: str
    aliases: tuple[str, ...]
    metrics: tuple[str, ...]
    tiers: tuple[str, str, str]

    def render(self) -> str:
        return (
            f"研究模板：{self.name}。优先核查指标：{'、'.join(self.metrics)}。\n"
            f"上游调查方向：{self.tiers[0]}；中游：{self.tiers[1]}；下游：{self.tiers[2]}。\n"
            "以上是正文提取问题，不是事实或逐项搜索清单。同份资料可覆盖多个指标；先说明产品与地域边界，不适用的环节不要套用。"
        )


TEMPLATES = (
    ResearchTemplate("baijiu", "白酒", ("白酒", "酿酒", "酿造"),
                     ("核心单品批价", "渠道库存", "终端动销", "回款", "直营占比"),
                     ("原粮、包装与酿造设备", "酿造、品牌与产品价格带", "经销商、直营渠道与消费场景")),
    ResearchTemplate("solar", "光伏", ("光伏", "硅料", "硅片", "太阳能"),
                     ("环节价格与成本", "有效产能", "开工率", "库存", "单位盈利"),
                     ("硅料、设备与辅材", "硅片、电池片与组件", "电站开发、装机与电力消纳")),
    ResearchTemplate("semiconductor", "半导体", ("半导体", "芯片", "晶圆", "集成电路"),
                     ("库存周期", "产能利用率", "制程与良率", "资本开支", "国产化进展"),
                     ("设备、材料与设计工具", "芯片设计、晶圆制造与封装测试", "终端应用与客户需求")),
    ResearchTemplate("pharma", "医药", ("创新药", "医药", "制药", "cxo", "生物药"),
                     ("管线阶段", "临床结果", "获批与商业化", "授权交易", "研发投入与现金储备"),
                     ("原料、研发工具与研究服务", "研发、临床与生产", "准入、医院、药房与患者需求")),
    ResearchTemplate("ai_computing", "AI 算力", ("算力", "服务器", "ai计算", "数据中心"),
                     ("资本开支", "订单与交付", "供给瓶颈", "单位价值量", "能耗与利用率"),
                     ("计算芯片、存储与关键器件", "服务器、网络、散热与电源", "云厂商、数据中心与应用需求")),
    ResearchTemplate("robot", "机器人", ("机器人", "具身智能"),
                     ("量产阶段", "订单与交付", "单机成本", "核心部件价值量", "应用验证"),
                     ("执行器、传感器与控制器", "整机制造与系统集成", "工业、商业与人形应用场景")),
)
GENERIC = ResearchTemplate("generic", "通用产业研究", (),
                           ("需求与供给", "价格与成本", "库存", "盈利能力", "竞争与商业化"),
                           ("关键投入、资源或服务", "核心产品、生产或服务交付", "渠道、客户与最终需求"))


def select_research_template(name: str) -> ResearchTemplate:
    normalized = name.lower().replace(" ", "")
    matches = [template for template in TEMPLATES if any(alias in normalized for alias in template.aliases)]
    # Mixed themes must not silently inherit the first matching industry.
    return matches[0] if len(matches) == 1 else GENERIC


# Research questions only: units and equations are conceptual, not measured estimates.
ECONOMIC_QUESTIONS = {
    "baijiu": (
        "终端动销与经销商打款是否同步？区分出厂价、批价、零售价和渠道库存，不能用压货当终端需求。",
        "渠道库存去化如何改变酒厂补库订单、价格折扣与现金回款？观察直营占比变化和销售费用，不只看毛利率。",
        "反证：批价下跌、回款弱于收入、库存上升是否推翻改善判断？原粮成本变化不能自动解释品牌定价。",
    ),
    "solar": (
        "按硅料→硅片→电池→组件分别比较同期间价格、单位成本、有效产能与开工率；名义规划产能不是有效供给。",
        "组件价格下降如何传到各环节价差与库存减值？下游装机需求能否消化投产，电站收益率是否改善？",
        "反证：下游数量增长是否被单价下降抵消？不得跨单位/技术路线合并价差，不把出货增长直接当利润增长。",
    ),
    "semiconductor": (
        "终端销量、客户库存与晶圆订单是否一致？区分设计、制造、封测的库存和资本开支周期。",
        "先进制程/封装的良率、产能利用率与认证周期如何影响实际交付及单位成本？不能用扩产公告代替可用产能。",
        "反证：库存天数、降价与客户取消订单是否说明补库只是短期？国产替代需要产品验证和收入而非概念名单。",
    ),
    "pharma": (
        "沿临床→获批→准入→处方/销售回款逐级核查；研发进展不等于收入，交易总额不等于已收首付款。",
        "准入和销量变化如何传到药企净销售额、现金消耗及CXO订单？区分授权收入、商业销售及里程碑的持续性。",
        "反证：临床失败、准入降价、订单取消及现金储备是否改变商业化路径？不同适应症与临床阶段不能合并胜率。",
    ),
    "ai_computing": (
        "从云厂商资本开支到服务器采购，区分已批准预算、订单、机柜交付、验收和计费利用率；不能把所有CapEx当AI设备采购。",
        "逐项核查芯片/存储→服务器/光互连/散热供电→算力客户的瓶颈，单位配置×出货量仅作框架，参数须同代际同口径。",
        "反证：电力受限、交付延期、闲置率或回款问题是否抵消扩张？比较量、价、结构与毛利，不只列高增长赛道。",
    ),
    "robot": (
        "从真实任务需求→整机付费订单→关键部件用量，分清展示/试点、框架协议、正式订单、交付与复购，不把产能当销量。",
        "关节/灵巧手等部件的单机用量、单价、良率与认证怎样影响整机成本和供应商收入？不能混用人形/轮式/工业机器人口径。",
        "反证：客户任务成功率、人工接管、维护成本和投资回收是否支持复制采购？没有BOM与份额依据不得量化供应商弹性。",
    ),
}

def research_guidance(name: str) -> str:
    template = select_research_template(name)
    guidance = template.render()
    questions = ECONOMIC_QUESTIONS.get(template.key, (
        "区分数量、价格与产品结构；下游需求经由订单、交付、验收和回款传导，不能从行业增长直接推导公司利润。",
        "寻找供给替代、价格传递、营运资金和反向证据；缺少参数时只作条件推断，不编造利润分配。",
    ))
    guidance += "\n经营研究问题（非事实/预测）：\n" + "\n".join(f"- {question}" for question in questions)
    if "机器人" in name and not any(word in name for word in ("人形", "工业", "服务")):
        guidance += "\n主题包含多种口径：工业机器人、人形机器人、服务机器人。分别列示，禁止合并规模与渗透率。"
    return guidance
