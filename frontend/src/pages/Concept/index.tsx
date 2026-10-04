import { useEffect, useMemo, useState } from "react";
import { AutoComplete, Card, Col, Input, Row, Tag } from "antd";
import { ApartmentOutlined } from "@ant-design/icons";
import {
  useConceptConstituents,
  useConceptIndex,
  useConceptList,
  type ConceptSummary,
} from "../../api/queryHooks/concept";
import { useColors } from "../../styles/ui";
import ConceptConstituentPanel from "./ConceptConstituentPanel";
import ConceptIndexPanel from "./ConceptIndexPanel";
import { DEFAULT_INDEX_DAYS, useConceptParam, useConceptSearch } from "./conceptSelection";

export default function Concept() {
  const c = useColors();
  const [conceptParam, setConceptParam] = useConceptParam();
  const [days, setDays] = useState(DEFAULT_INDEX_DAYS);
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
  const constituentsQuery = useConceptConstituents(concept);
  const indexQuery = useConceptIndex(concept, days);

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

  return (
    <main style={{ display: "flex", flexDirection: "column", gap: 14, minWidth: 0 }}>
      <header style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
        <ApartmentOutlined style={{ fontSize: 20, color: c.primary }} />
        <div>
          <h1 style={{ margin: 0, fontSize: 20, fontWeight: 700, color: c.textPrimary }}>概念板块联动</h1>
          <p style={{ margin: "2px 0 0", fontSize: 12, color: c.textMuted }}>
            左侧是本地合成的等权概念指数，右侧是该概念的成分股与实时行情，两侧共享同一个概念选择。
          </p>
        </div>
      </header>

      <Card size="small" styles={{ body: { padding: 12 } }}>
        <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
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
            style={{ width: 280 }}
            placeholder="搜索并选择概念，例如「固态电池」"
          >
            <Input.Search allowClear onSearch={handleSelectConcept} />
          </AutoComplete>
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
      </Card>

      <Row gutter={[12, 12]} align="stretch">
        <Col xs={24} xl={14}>
          <Card size="small" style={{ height: "100%" }} styles={{ body: { padding: 12 } }}>
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
        <Col xs={24} xl={10}>
          <Card size="small" style={{ height: "100%" }} styles={{ body: { padding: 12 } }}>
            <ConceptConstituentPanel
              concept={concept}
              items={constituentsQuery.data?.items}
              related={related}
              total={constituentsQuery.data?.total ?? 0}
              isLoading={constituentsQuery.isLoading}
              error={constituentsQuery.error}
              onRetry={() => void constituentsQuery.refetch()}
              quoteSource={constituentsQuery.data?.quote_source ?? null}
              onSelectConcept={handleSelectConcept}
            />
          </Card>
        </Col>
      </Row>
    </main>
  );
}