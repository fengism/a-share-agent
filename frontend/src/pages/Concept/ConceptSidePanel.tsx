import { useMemo } from "react";
import { Card, Tag, Tooltip } from "antd";
import { FallOutlined, RiseOutlined } from "@ant-design/icons";
import ChangeValue from "../../components/ChangeValue";
import SectionDataState from "../../components/SectionDataState";
import StockExternalLink from "../../components/StockExternalLink";
import { useMediaQuery } from "../../hooks/useMediaQuery";
import { useColors, semanticTagStyle } from "../../styles/ui";
import type { ConceptConstituent, RelatedConcept } from "../../api/queryHooks/concept";

interface Props {
  concept: string;
  items: ConceptConstituent[] | undefined;
  related: RelatedConcept[];
  /** 关联概念的最近交易日等权涨跌（来自概念列表的日度聚合，缺失为 undefined） */
  changeByName: Map<string, number>;
  isLoading: boolean;
  error: unknown;
  onRetry: () => void;
  /** 点击关联概念 → 切换当前概念（浏览器后退可返回） */
  onSelectConcept: (concept: string) => void;
}

const LEADER_COUNT = 5;
const LAGGARD_COUNT = 3;

/**
 * 右侧栏：领涨/领跌个股 + 关联概念，回答"这个概念里谁在带动、和谁联动"。
 * 行情未补齐时按已加载数据计算——成分股表的行情加载进度在表格头部展示。
 */
export default function ConceptSidePanel({
  concept,
  items,
  related,
  changeByName,
  isLoading,
  error,
  onRetry,
  onSelectConcept,
}: Props) {
  const c = useColors();
  const isNarrow = useMediaQuery("(max-width: 768px)");

  const { leaders, laggards } = useMemo(() => {
    const quoted = (items ?? []).filter((item) => item.change_pct != null);
    const byDesc = [...quoted].sort((a, b) => (b.change_pct ?? 0) - (a.change_pct ?? 0));
    return {
      leaders: byDesc.slice(0, LEADER_COUNT),
      laggards: byDesc.slice(-LAGGARD_COUNT).reverse(),
    };
  }, [items]);

  const renderStockRow = (item: ConceptConstituent) => (
    <div key={item.code} className="concept-leader-row">
      <StockExternalLink code={item.code} name={item.name} className="concept-leader-row__name">
        {item.name || item.code}
      </StockExternalLink>
      <ChangeValue value={item.change_pct} digits={2} />
    </div>
  );

  return (
    <div className="concept-side" style={{ display: "flex", flexDirection: "column", gap: isNarrow ? 10 : 12, minWidth: 0 }}>
      <Card
        size="small"
        title={<span className="concept-side__title"><RiseOutlined style={{ color: c.up }} /> 领涨 / 领跌</span>}
        styles={{ body: { padding: isNarrow ? 10 : 12 } }}
      >
        <SectionDataState
          isLoading={isLoading && !items?.length}
          error={items?.length ? undefined : error}
          onRetry={onRetry}
          isEmpty={!isLoading && !error && !items?.length}
          emptyText={`暂无「${concept}」的成分股数据`}
          errorTitle="成分股加载失败"
          minHeight={120}
        >
          <div className="concept-leaders" style={{ display: "flex", gap: isNarrow ? 12 : 16, minWidth: 0 }}>
            <div className="concept-leaders__col" style={{ flex: 3, minWidth: 0 }}>
              {leaders.length ? (
                leaders.map(renderStockRow)
              ) : (
                <span style={{ fontSize: 12, color: c.textMuted }}>行情加载中…</span>
              )}
            </div>
            {laggards.length ? (
              <div className="concept-leaders__col" style={{ flex: 2, minWidth: 0 }}>
                <div className="concept-leaders__col-label" style={{ color: c.textMuted }}>
                  <FallOutlined /> 领跌
                </div>
                {laggards.map(renderStockRow)}
              </div>
            ) : null}
          </div>
        </SectionDataState>
      </Card>

      {related.length ? (
        <Card
          size="small"
          title={<span className="concept-side__title">关联概念</span>}
          styles={{ body: { padding: isNarrow ? 10 : 12 } }}
        >
          <div className="concept-related">
            {related.map((item) => (
              <Tooltip key={item.name} title={`${item.overlap} 只成分股同时属于「${item.name}」，点击查看`}>
                <Tag
                  className="concept-related__tag"
                  style={{ ...semanticTagStyle("primary"), cursor: "pointer", marginInlineEnd: 0 }}
                  onClick={() => onSelectConcept(item.name)}
                >
                  <span className="concept-related__name">{item.name}</span>
                  {changeByName.get(item.name) != null ? (
                    <ChangeValue value={changeByName.get(item.name) ?? null} digits={2} />
                  ) : null}
                  <span className="concept-related__overlap financial-num">{item.overlap} 只重叠</span>
                </Tag>
              </Tooltip>
            ))}
          </div>
        </Card>
      ) : null}
    </div>
  );
}
