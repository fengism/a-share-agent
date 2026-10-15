import { useCallback, useEffect, useMemo, useState } from "react";
import { AutoComplete, Card, Col, Input, Row, Segmented, Tag } from "antd";
import { ApartmentOutlined } from "@ant-design/icons";
import {
  useConceptConstituents,
  useConceptIndex,
  useConceptList,
  type ConceptSummary,
} from "../../api/queryHooks/concept";
import { useMediaQuery } from "../../hooks/useMediaQuery";
import { useColors } from "../../styles/ui";
import ConceptConstituentPanel from "./ConceptConstituentPanel";
import ConceptIndexPanel from "./ConceptIndexPanel";
import { DEFAULT_INDEX_DAYS, useConceptParam, useConceptSearch } from "./conceptSelection";
import "./concept-page.css";

export default function Concept() {
  const c = useColors();
  const isNarrow = useMediaQuery("(max-width: 768px)");
  const [conceptParam, setConceptParam] = useConceptParam();
  const [days, setDays] = useState(DEFAULT_INDEX_DAYS);
  const [mobileView, setMobileView] = useState<"all" | "index" | "constituents">("all");
  // 搜索词与输入框显示值必须分开：受控AutoComplete 若直接把 value 绑到
  // 已选概念，用户输入时框内文字不会变化，下拉也就没法跟着过滤。
  const [keyword, setKeyword] = useState("");
  const [inputValue, setInputValue] = useState("");

  const listQuery = useConceptList();
  const concepts = useMemo(() => (listQuery.data?.items ?? []) as ConceptSummary[], [listQuery.data]);
  const filtered = useConceptSearch(concepts, keyword);

  // URL 没带概念时默认选成分股最多的那个（融资融券），保证首屏就有内容
  useEffect(() => {
    if (conceptParam || !concepts.length) return;
    setConceptParam(concepts[0].name);
  }, [conceptParam, concepts, setConceptParam]);

  // 外部换概念（如点重叠概念）时同步输入框
  useEffect(() => {
    setInputValue(conceptParam);
  }, [conceptParam]);

  const concept = conceptParam;
  // 行情按需加载：undefined = 只取本地身份列表（零上游调用），
  // 之后每次传入更大的代码集，后端仍返回完整成分股，只是行情逐段补齐。
  const [quoteCodes, setQuoteCodes] = useState<string[] | undefined>(undefined);

  // 换概念时回到「不拉行情」，让新概念的身份列表先秒出
  useEffect(() => {
    setQuoteCodes(undefined);
  }, [concept]);

  const constituentsQuery = useConceptConstituents(concept, quoteCodes);
  const indexQuery = useConceptIndex(concept, days);

  const handleRequestQuotes = useCallback((codes: string[]) => {
    setQuoteCodes(codes);
  }, []);

  const handleSelectConcept = (next: string) => {
    setConceptParam(next);
    setInputValue(next);
    setKeyword("");
  };

  const related = useMemo(
    () => (constituentsQuery.data?.related_concepts ?? []) as Array<{
      name: string;
      overlap: number;
      ratio: number;
    }>,
    [constituentsQuery.data],
  );

  const mobileViewOptions = useMemo(
    () => [
      { label: "综合双屏", value: "all" },
      { label: "指数走势", value: "index" },
      {
        label: `成分股${constituentsQuery.data?.total ? ` (${constituentsQuery.data.total})` : ""}`,
        value: "constituents",
      },
    ],
    [constituentsQuery.data?.total],
  );

  const showIndex = !isNarrow || mobileView === "all" || mobileView === "index";
  const showConstituents = !isNarrow || mobileView === "all" || mobileView === "constituents";

  return (
    <main className="concept-page">
      <header className="concept-header">
        <ApartmentOutlined className="concept-header__icon" style={{ fontSize: isNarrow ? 18 : 20, color: c.primary }} />
        <div>
          <h1 className="concept-header__title" style={{ color: c.textPrimary }}>
            概念板块联动
          </h1>
          <p className="concept-header__desc" style={{ color: c.textMuted }}>
            左侧是本地合成的等权概念指数，右侧是该概念的成分股与实时行情，两侧共享同一个概念选择。
          </p>
        </div>
      </header>

      <Card size="small" styles={{ body: { padding: isNarrow ? 10 : 12 } }}>
        <div className="concept-search-bar">
          <AutoComplete
            value={inputValue}
            // 我们自己按 concepts 过滤；option 的 label 是 JSX，默认过滤会匹配失败
            filterOption={false}
            onSearch={(text) => {
              setKeyword(text);
              setInputValue(text);
            }}
            onSelect={(value) => handleSelectConcept(String(value))}
            options={filtered.slice(0, 30).map((item) => ({
              value: item.name,
              label: (
                <span style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
                  <span>{item.name}</span>
                  <span style={{ color: c.textMuted, fontSize: 12 }}>{item.stock_count} 只</span>
                </span>
              ),
            }))}
            className="concept-search-input"
            style={{ width: "100%", maxWidth: isNarrow ? "100%" : 320 }}
            placeholder="搜索并选择概念，例如「固态电池」"
          >
            <Input.Search allowClear onSearch={handleSelectConcept} />
          </AutoComplete>
          <div className="concept-search-meta">
            {concept ? (
              <Tag style={{ marginInlineEnd: 0 }} color="blue">
                {concept} ·{" "}
                {constituentsQuery.data?.total ?? concepts.find((i) => i.name === concept)?.stock_count ?? 0} 只
              </Tag>
            ) : null}
            <span style={{ fontSize: 12, color: c.textMuted }}>
              共 {concepts.length} 个概念{keyword.trim() ? ` · 匹配 ${filtered.length}` : ""}
            </span>
          </div>
        </div>
      </Card>

      {isNarrow && (
        <div className="concept-mobile-view-tabs">
          <Segmented
            block
            size="middle"
            value={mobileView}
            options={mobileViewOptions}
            onChange={(val) => setMobileView(val as "all" | "index" | "constituents")}
          />
        </div>
      )}

      <Row gutter={[12, 12]} align="stretch">
        {showIndex && (
          <Col xs={24} xl={14}>
            <Card size="small" style={{ height: "100%" }} styles={{ body: { padding: isNarrow ? 10 : 12 } }}>
              <ConceptIndexPanel
                concept={concept}
                points={indexQuery.data?.items}
                days={days}
                onDaysChange={setDays}
                isLoading={indexQuery.isLoading}
                error={indexQuery.error}
                onRetry={() => void indexQuery.refetch()}
                constituentTotal={indexQuery.data?.constituent_total ?? 0}
                constituentUsed={indexQuery.data?.constituent_used ?? 0}
                truncated={indexQuery.data?.truncated ?? false}
              />
            </Card>
          </Col>
        )}
        {showConstituents && (
          <Col xs={24} xl={showIndex ? 10 : 24}>
            <Card size="small" style={{ height: "100%" }} styles={{ body: { padding: isNarrow ? 10 : 12 } }}>
              <ConceptConstituentPanel
                concept={concept}
                items={constituentsQuery.data?.items}
                related={related}
                total={constituentsQuery.data?.total ?? 0}
                isLoading={constituentsQuery.isLoading}
                error={constituentsQuery.error}
                onRetry={() => void constituentsQuery.refetch()}
                quoteSource={constituentsQuery.data?.quote_source ?? null}
                quoteRequested={quoteCodes?.length ?? 0}
                quotePending={constituentsQuery.isFetching}
                onRequestQuotes={handleRequestQuotes}
                onSelectConcept={handleSelectConcept}
              />
            </Card>
          </Col>
        )}
      </Row>
    </main>
  );
}