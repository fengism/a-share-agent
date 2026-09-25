import { buildStockValuationUrl } from "./analysisHistoryUrl";
import { ArrowRightOutlined, AuditOutlined, WarningOutlined } from "@ant-design/icons";
import { Alert, Button, Empty, Progress, Segmented, Tag, Typography } from "antd";
import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import type {
  AnalysisResult,
  AssessmentDirection,
  AssessmentLevel,
  InformationGrade,
  InvestorActionPlan,
  RiskLevel,
  ScenarioName,
} from "../../types/stock";
import { semanticTagStyle } from "../../theme/hooks";
import type { SemanticTagColor } from "../../theme/hooks";
import "./stock-research-typography.css";
import "./research-framework.css";

const { Paragraph, Text, Title } = Typography;

const GRADE_LABELS: Record<InformationGrade, string> = {
  A: "A · 资料丰富",
  B: "B · 资料有限",
  C: "C · 资料稀少",
  unknown: "? · 尚未评级",
};

const MOAT_LABELS = {
  brand_pricing: "品牌与定价权",
  switching_cost: "转换成本",
  network_effect: "网络效应",
  scale_advantage: "规模优势",
  technology_ip: "技术与知识产权",
  other: "其他优势",
} as const;

const LEVEL_LABELS: Record<AssessmentLevel, string> = {
  strong: "强",
  moderate: "中",
  weak: "弱",
  unclear: "待核验",
};

const DIRECTION_LABELS: Record<AssessmentDirection, string> = {
  strengthening: "增强",
  stable: "稳定",
  weakening: "减弱",
  unclear: "待核验",
};

const RISK_LABELS: Record<RiskLevel, string> = {
  high: "高",
  medium: "中",
  low: "低",
  unknown: "待核验",
};

const SCENARIO_LABELS: Record<ScenarioName, string> = {
  bull: "乐观情景",
  base: "基准情景",
  bear: "谨慎情景",
};

const NEW_INVESTOR_LABELS: Record<InvestorActionPlan["new_investor_action"], string> = {
  buy: "满足条件后考虑买入",
  watch: "继续观察",
  avoid: "暂时回避",
  insufficient_evidence: "证据不足",
};

const NEW_INVESTOR_TONES: Record<InvestorActionPlan["new_investor_action"], SemanticTagColor> = {
  buy: "up",
  watch: "info",
  avoid: "down",
  insufficient_evidence: "warning",
};

const HOLDER_LABELS: Record<InvestorActionPlan["holder_action"], string> = {
  hold: "继续持有并跟踪",
  add: "满足条件后考虑增持",
  reduce: "考虑降低仓位",
  exit: "考虑退出",
  insufficient_evidence: "证据不足",
};

const HOLDER_TONES: Record<InvestorActionPlan["holder_action"], SemanticTagColor> = {
  hold: "info",
  add: "up",
  reduce: "warning",
  exit: "down",
  insufficient_evidence: "warning",
};

function formatConfidence(value: number | null) {
  return value == null ? null : Math.round(value * 100);
}

function formatRange(value: [number, number] | null) {
  if (!value) return "证据不足，未给出区间";
  return `¥${value[0].toFixed(2)} – ¥${value[1].toFixed(2)}`;
}

function EvidenceMeter({ label, value, description }: { label: string; value: number | null; description: string }) {
  const percent = formatConfidence(value);
  return (
    <div className="research-confidence-meter">
      <div className="research-confidence-meter__label">
        <strong>{label}</strong>
        <span>{percent == null ? "待核验" : `${percent}%`}</span>
      </div>
      <Progress
        percent={percent ?? 0}
        showInfo={false}
        strokeLinecap="butt"
        aria-label={`${label}${percent == null ? "待核验" : `${percent}%`}`}
      />
      <small>{description}</small>
    </div>
  );
}

function TextList({ items, empty = "未覆盖" }: { items: string[]; empty?: string }) {
  if (!items.length) return <Text type="secondary">{empty}</Text>;
  return (
    <ul className="research-text-list">
      {items.map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}
    </ul>
  );
}

function ResearchSection({
  id,
  title,
  eyebrow,
  compact,
  summary,
  children,
}: {
  id: string;
  title: string;
  eyebrow: string;
  compact: boolean;
  summary?: React.ReactNode;
  children: React.ReactNode;
}) {
  const headingId = `${id}-heading`;
  const contentId = `${id}-content`;
  return (
    <section
      id={id}
      className="research-section research-anchor"
      data-pdf-capture
      data-pdf-section
      aria-labelledby={headingId}
    >
      <header className="research-section__header">
        <span>{eyebrow}</span>
        <Title id={headingId} level={4}>{title}</Title>
      </header>
      {compact && summary ? <div className="research-section__compact-summary">{summary}</div> : null}
      <div id={contentId} aria-hidden={compact && Boolean(summary)} className="research-section__content">
        {children}
      </div>
    </section>
  );
}

const RESEARCH_CHAPTERS = [
  ["research-evidence", "证据"],
  ["research-business", "生意"],
  ["research-moat", "护城河"],
  ["research-stewardship", "管理与行业"],
  ["research-inversion", "反向风险"],
  ["research-valuation", "估值"],
  ["research-decision", "行动"],
  ["research-gaps", "数据缺口"],
] as const;

function NamedNarrative({ label, value }: { label: string; value: string }) {
  return (
    <div className="research-narrative">
      <span>{label}</span>
      <p>{value || "证据不足，暂未形成结论"}</p>
    </div>
  );
}

function ActionColumn({
  title,
  action,
  actionTone,
  items,
}: {
  title: string;
  action: string;
  actionTone: SemanticTagColor;
  items: Array<{ label: string; values: string[] }>;
}) {
  return (
    <article className="research-action-column">
      <header className="research-action-column__header">
        <span className="research-action-column__title">{title}</span>
        <Tag style={{ ...semanticTagStyle(actionTone), margin: 0, fontWeight: "var(--c-weight-semibold)" }}>
          {action}
        </Tag>
      </header>
      {items.map(({ label, values }) => (
        <div key={label} className="research-action-column__triggers">
          <h5>{label}</h5>
          <TextList items={values} />
        </div>
      ))}
    </article>
  );
}

interface ResearchFrameworkPanelProps {
  analysis?: AnalysisResult | null;
  onOpenValuation?: () => void;
  forceFullReport?: boolean;
}

export default function ResearchFrameworkPanel({
  analysis,
  onOpenValuation,
  forceFullReport = false,
}: ResearchFrameworkPanelProps) {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [compactPreference, setCompactPreference] = useState(true);
  const compact = forceFullReport ? false : compactPreference;
  const research = analysis?.research_framework;

  if (!analysis) {
    return (
      <div className="research-legacy-state">
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description="完成个股研究后查看结构化研究结论"
        />
        <Text type="secondary">研究结果将覆盖生意、护城河、管理层、风险情景和条件化行动。</Text>
      </div>
    );
  }

  if (!research) {
    return (
      <div className="research-legacy-state">
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description="该研究快照由旧版框架生成，暂无结构化研究结论"
        />
        <Text type="secondary">重新运行分析后，将展示生意、护城河、管理层、风险情景与条件化行动。</Text>
      </div>
    );
  }

  const { information_quality: quality } = research;
  const openValuation = onOpenValuation ?? (() => {
    navigate(buildStockValuationUrl(analysis.stock_code, searchParams.get("date")));
  });

  return (
    <div className={`research-framework${compact ? " is-compact" : ""}`}>
      <div className="research-reading-toolbar pdf-hide">
        <nav aria-label="研究结论章节导航">
          {RESEARCH_CHAPTERS.map(([id, label]) => <a key={id} href={`#${id}`}>{label}</a>)}
        </nav>
        <Segmented
          aria-label="报告阅读模式"
          value={compact ? "compact" : "full"}
          options={[
            { label: "完整报告", value: "full" },
            { label: "精简阅读", value: "compact" },
          ]}
          onChange={(value) => setCompactPreference(value === "compact")}
        />
      </div>
      <section
        id="research-evidence"
        className="research-evidence-ruler research-anchor"
        data-pdf-capture
        data-pdf-section
        aria-labelledby="research-confidence-title"
      >
        <div className="research-evidence-ruler__grade">
          <span className="research-eyebrow"><AuditOutlined /> 信息完备度</span>
          <strong data-grade={quality.grade}>{GRADE_LABELS[quality.grade]}</strong>
          <p>{quality.grade_rationale || "尚无足够证据解释当前等级"}</p>
          <div className="research-grade-scale" aria-label={`信息完备度 ${GRADE_LABELS[quality.grade]}`}>
            {(["C", "B", "A"] as const).map((grade) => (
              <span key={grade} className={quality.grade === grade ? "is-active" : ""}>{grade}</span>
            ))}
          </div>
        </div>
        <div className="research-evidence-ruler__confidence">
          <Title id="research-confidence-title" level={4}>研究证据标尺</Title>
          <EvidenceMeter
            label="证据可信度"
            value={quality.evidence_confidence}
            description="衡量覆盖度、时效性、来源一致性与推断比例"
          />
          <EvidenceMeter
            label="投资确定性"
            value={quality.investment_certainty}
            description="衡量商业模式、护城河与结果区间的可预测性"
          />
          <Paragraph>{quality.coverage_summary || "尚未形成覆盖摘要"}</Paragraph>
        </div>
      </section>

      {quality.limitations.length > 0 ? (
        <Alert
          type="warning"
          showIcon
          title="解读限制"
          description={<TextList items={quality.limitations} />}
        />
      ) : null}

      <ResearchSection id="research-business" eyebrow="01" title="生意与盈利引擎" compact={compact} summary={<strong>{research.business_model.economic_engine || "证据不足，尚不能概括盈利引擎"}</strong>}>
        <div className="research-hero-thesis">
          <span>公司如何赚钱</span>
          <strong>{research.business_model.economic_engine || "证据不足，尚不能概括盈利引擎"}</strong>
        </div>
        <div className="research-two-column">
          <NamedNarrative label="盈利质量" value={research.business_model.earnings_quality} />
          <NamedNarrative label="经营杠杆" value={research.business_model.operating_leverage} />
        </div>
        <div className="research-list-columns">
          <div><h5>收入驱动</h5><TextList items={research.business_model.revenue_drivers} /></div>
          <div><h5>优势证据</h5><TextList items={research.business_model.strengths} /></div>
          <div><h5>待验证隐忧</h5><TextList items={research.business_model.concerns} /></div>
        </div>
        {research.business_model.segment_quality.length ? (
          <div className="research-segment-grid">
            {research.business_model.segment_quality.map((segment, index) => (
              <article key={`${segment.segment}-${index}`}>
                <header><strong>{segment.segment}</strong><span>{segment.evidence_confidence == null ? "证据待核验" : `${formatConfidence(segment.evidence_confidence)}% 证据`}</span></header>
                <p>{segment.role || "分部角色未覆盖"}</p>
                <dl>
                  <div><dt>成长质量</dt><dd>{segment.growth_quality || "待核验"}</dd></div>
                  <div><dt>盈利质量</dt><dd>{segment.profitability_quality || "待核验"}</dd></div>
                  <div><dt>收入持续性</dt><dd>{segment.recurrence || "待核验"}</dd></div>
                </dl>
              </article>
            ))}
          </div>
        ) : null}
      </ResearchSection>

      <ResearchSection id="research-moat" eyebrow="02" title="护城河与反证" compact={compact} summary={research.moat.overall_durability || "尚无足够证据识别可持续护城河"}>
        {research.moat.moats.length ? (
          <div className="research-moat-grid">
            {research.moat.moats.map((moat, index) => (
              <article key={`${moat.moat_type}-${index}`}>
                <header>
                  <strong>{MOAT_LABELS[moat.moat_type]}</strong>
                  <div>
                    <Tag style={semanticTagStyle(moat.strength === "strong" ? "success" : moat.strength === "weak" ? "warning" : "info")}>{LEVEL_LABELS[moat.strength]}</Tag>
                    <Tag>{DIRECTION_LABELS[moat.direction]}</Tag>
                  </div>
                </header>
                <p>{moat.durability || "持续性待核验"}</p>
                <div className="research-evidence-pair">
                  <div><h5>支持证据</h5><TextList items={moat.evidence} /></div>
                  <div><h5>反证与威胁</h5><TextList items={[...moat.counterevidence, ...moat.threats]} /></div>
                </div>
              </article>
            ))}
          </div>
        ) : <Text type="secondary">尚无足够证据识别可持续护城河</Text>}
        {research.moat.overall_durability ? <Paragraph className="research-section__conclusion">持续性判断：{research.moat.overall_durability}</Paragraph> : null}
      </ResearchSection>

      <div id="research-stewardship" className="research-two-column research-section-pair research-anchor" data-pdf-section>
        <ResearchSection id="research-management" eyebrow="03A" title="管理层与资本配置" compact={compact} summary={research.management.capital_allocation || "资本配置待核验"}>
          <NamedNarrative label="经营记录" value={research.management.track_record} />
          <NamedNarrative label="资本配置" value={research.management.capital_allocation} />
          <NamedNarrative label="股东利益一致性" value={research.management.shareholder_alignment} />
          <NamedNarrative label="接班与关键人物风险" value={research.management.succession_or_key_person_risk} />
        </ResearchSection>
        <ResearchSection id="research-industry" eyebrow="03B" title="行业与价值链" compact={compact} summary={research.industry_position.competitive_position || "竞争位置待核验"}>
          <NamedNarrative label="长期行业背景" value={research.industry_position.secular_context} />
          <NamedNarrative label="价值链位置" value={research.industry_position.value_chain_position} />
          <NamedNarrative label="竞争位置" value={research.industry_position.competitive_position} />
          <NamedNarrative label="技术替代风险" value={research.industry_position.technology_or_obsolescence_risk} />
        </ResearchSection>
      </div>

      <ResearchSection id="research-inversion" eyebrow="04" title="反向推演与熊市情景" compact={compact} summary={research.inversion.bear_case || "熊市逻辑待核验"}>
        <Alert
          type="error"
          showIcon
          icon={<WarningOutlined />}
          title="最强熊市逻辑"
          description={research.inversion.bear_case || "证据不足，尚未形成可检验的熊市逻辑"}
        />
        {research.inversion.risks.length ? (
          <div className="research-risk-register" role="list" aria-label="风险登记表">
            {research.inversion.risks.map((risk, index) => (
              <article role="listitem" key={`${risk.risk}-${index}`}>
                <header>
                  <strong>{risk.risk}</strong>
                  <span>概率 {RISK_LABELS[risk.probability]} · 影响 {RISK_LABELS[risk.impact]}</span>
                </header>
                <p>{risk.failure_path || "失败路径待核验"}</p>
                <div><span>观察窗口</span><strong>{risk.time_horizon || "未明确"}</strong></div>
                <div><span>领先指标</span><TextList items={risk.leading_indicators} /></div>
                <div><span>缓释因素</span><TextList items={risk.mitigants} /></div>
              </article>
            ))}
          </div>
        ) : null}
        {research.inversion.bias_checks.length ? <div><h5>认知偏差检查</h5><TextList items={research.inversion.bias_checks} /></div> : null}
      </ResearchSection>

      <ResearchSection
        id="research-valuation"
        eyebrow="05"
        title="估值假设与三情景"
        compact={compact}
        summary={(
          <div className="research-valuation-compact-summary">
            <strong>{research.valuation.current_valuation || "估值证据不足"}</strong>
            <Button type="link" size="small" onClick={openValuation}>
              查看估值明细 <ArrowRightOutlined />
            </Button>
          </div>
        )}
      >
        <div className="research-valuation-heading">
          <div>
            <strong>{research.valuation.current_valuation || "估值证据不足"}</strong>
            <p>{research.valuation.method_summary || "复用估值面已有方法，当前未形成方法摘要"}</p>
          </div>
          <Button type="link" onClick={openValuation}>查看估值明细 <ArrowRightOutlined /></Button>
        </div>
        <div className="research-scenario-grid">
          {(["bull", "base", "bear"] as const).map((name) => {
            const scenario = research.valuation.scenarios?.[name];
            return (
              <article key={name} data-scenario={name}>
                <span>{SCENARIO_LABELS[name]}</span>
                <strong>{formatRange(scenario?.fair_value_range ?? null)}</strong>
                <p>{scenario?.valuation_view || "该情景证据不足"}</p>
                <h5>关键假设</h5>
                <TextList items={scenario?.assumptions ?? []} />
                <h5>失效条件</h5>
                <TextList items={scenario?.invalidating_conditions ?? []} />
              </article>
            );
          })}
        </div>
        <div className="research-list-columns">
          <div><h5>共同假设</h5><TextList items={research.valuation.assumptions} /></div>
          <div>
            <h5>安全边际</h5>
            <p className="research-list-columns__text">
              {research.valuation.margin_of_safety || "证据不足，未形成安全边际判断"}
            </p>
          </div>
          <div><h5>估值限制</h5><TextList items={research.valuation.limitations} /></div>
        </div>
      </ResearchSection>

      <ResearchSection
        id="research-decision"
        eyebrow="06"
        title="行动与持续跟踪"
        compact={compact}
        summary={research.actions.rationale || "暂不形成行动结论"}
      >
        <div className="research-decision-hero">
          <div className="research-decision-hero__body">
            <span className="research-decision-hero__label">行动研判总述</span>
            <p className="research-decision-hero__text">
              {research.actions.rationale || "证据不足，暂不形成行动结论"}
            </p>
          </div>
          {research.actions.buy_or_add_range && (
            <div className="research-decision-hero__range">
              <span>建议关注 / 加仓区间</span>
              <strong>{formatRange(research.actions.buy_or_add_range)}</strong>
            </div>
          )}
        </div>

        <div className="research-action-grid">
          <ActionColumn
            title="新投资者"
            action={NEW_INVESTOR_LABELS[research.actions.new_investor_action]}
            actionTone={NEW_INVESTOR_TONES[research.actions.new_investor_action]}
            items={[{ label: "买入 / 关注触发条件", values: research.actions.add_triggers }]}
          />
          <ActionColumn
            title="已持有者"
            action={HOLDER_LABELS[research.actions.holder_action]}
            actionTone={HOLDER_TONES[research.actions.holder_action]}
            items={[{ label: "减持 / 退出触发条件", values: research.actions.sell_triggers }]}
          />
        </div>

        <div className="research-two-column research-decision-tracking">
          <div className="research-decision-tracking-card research-decision-tracking-card--breakers">
            <h5>核心逻辑失效条件</h5>
            <TextList items={research.actions.thesis_breakers} empty="暂无明确失效条件" />
          </div>
          <div className="research-decision-tracking-card research-decision-tracking-card--metrics">
            <h5>持续跟踪指标</h5>
            <TextList items={research.actions.monitoring_metrics} empty="暂无明确跟踪指标" />
          </div>
        </div>
      </ResearchSection>

      <ResearchSection id="research-gaps" eyebrow="07" title="数据缺口与下一步核验" compact={compact} summary={research.data_gaps.length ? `待核验 ${research.data_gaps.length} 项数据缺口` : "当前未列出额外数据缺口"}>
        {research.data_gaps.length ? (
          <div className="research-gap-list">
            {research.data_gaps.map((gap, index) => (
              <article key={`${gap.topic}-${index}`}>
                <strong>{gap.topic}</strong>
                <p>{gap.missing_data || "缺失内容未说明"}</p>
                <dl>
                  <div><dt>决策影响</dt><dd>{gap.decision_impact || "待评估"}</dd></div>
                  <div><dt>下一步</dt><dd>{gap.follow_up || "待补充核验"}</dd></div>
                </dl>
              </article>
            ))}
          </div>
        ) : <Text type="secondary">当前结果未列出额外数据缺口</Text>}
      </ResearchSection>
    </div>
  );
}
