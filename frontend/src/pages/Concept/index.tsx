import { useCallback, useEffect, useMemo, useState } from "react";
import { AutoComplete, Button, Card, Col, Input, Row, Segmented, Tag, Tooltip, Typography } from "antd";
import {
  ApartmentOutlined,
  ClockCircleOutlined,
  FireOutlined,
  RiseOutlined,
  StarFilled,
  StarOutlined,
} from "@ant-design/icons";
import { ApiError } from "../../api/client";
import {
  useConceptConstituents,
  useConceptIndex,
  useConceptList,
  type ConceptSummary,
} from "../../api/queryHooks/concept";
import { useMarketMainline, useThsHotConcept } from "../../api/queries";
import type { MarketMainline, ThsHotPlate } from "../../types/stock/market";
import { useMediaQuery } from "../../hooks/useMediaQuery";
import { useColors, useStyles } from "../../styles/ui";
import ConceptComparePanel from "./ConceptComparePanel";
import ConceptConstituentPanel from "./ConceptConstituentPanel";
import ConceptIndexPanel from "./ConceptIndexPanel";
import ConceptSidePanel from "./ConceptSidePanel";
import {
  COMPARE_CONCEPT_LIMIT,
  CONCEPT_INDEX_RANGES,
  useConceptPageParams,
  useConceptSearch,
  useFavoriteConcepts,
  useRecentConcepts,
} from "./conceptSelection";
import "./concept-page.css";

/** 指数卡片视图切换：单概念 K 线 / 多概念对比 */
const INDEX_VIEW_OPTIONS = [
  { label: "走势", value: "single" },
  { label: "对比", value: "compare" },
];

/** 首屏按需加载的行情窗口（约两屏），够用户看清前几十行 */
const INITIAL_QUOTE_WINDOW = 80;

/** 行情自动补齐的每批窗口：滚动/后台渐进加载，直到全量 */
const QUOTE_WINDOW_STEP = 120;

function HotChips({
  hot,
  activeConcept,
  onSelect,
}: {
  hot: ThsHotPlate[] | undefined;
  activeConcept: string;
  onSelect: (name: string) => void;
}) {
  const c = useColors();
  if (!hot?.length) return null;
  return (
    <div className="concept-picker__chips">
      <span className="concept-picker__label">
        <FireOutlined style={{ color: c.warning }} /> 热门
      </span>
      {hot.slice(0, 10).map((item, index) => {
        const active = item.name === activeConcept;
        const chip = (
          <button
            key={`${item.code}-${item.name}`}
            type="button"
            className={`concept-chip${active ? " concept-chip--active" : ""}`}
            onClick={() => onSelect(item.name)}
          >
            <span className="concept-chip__rank financial-num">{index + 1}</span>
            <span className="concept-chip__name">{item.name}</span>
            {item.change_pct != null ? (
              <span
                className="concept-chip__pct financial-num"
                style={{ color: item.change_pct > 0 ? c.up : item.change_pct < 0 ? c.down : c.textMuted }}
              >
                {item.change_pct > 0 ? "+" : ""}
                {item.change_pct.toFixed(2)}%
              </span>
            ) : null}
          </button>
        );
        const hint = [
          item.hot_value != null ? `热度 ${item.hot_value.toFixed(1)}` : null,
          item.hot_tag || null,
        ]
          .filter(Boolean)
          .join(" · ");
        return hint ? (
          <Tooltip key={`${item.code}-${item.name}`} title={`${item.name}：${hint}，点击查看概念详情`}>
            {chip}
          </Tooltip>
        ) : (
          chip
        );
      })}
    </div>
  );
}

function RecentChips({
  recent,
  activeConcept,
  onSelect,
}: {
  recent: string[];
  activeConcept: string;
  onSelect: (name: string) => void;
}) {
  if (!recent.length) return null;
  return (
    <div className="concept-picker__chips">
      <span className="concept-picker__label">
        <ClockCircleOutlined /> 最近
      </span>
      {recent.map((name) => (
        <button
          key={name}
          type="button"
          className={`concept-chip concept-chip--plain${name === activeConcept ? " concept-chip--active" : ""}`}
          onClick={() => onSelect(name)}
        >
          <span className="concept-chip__name">{name}</span>
        </button>
      ))}
    </div>
  );
}

function FavoriteChips({
  favorites,
  activeConcept,
  onSelect,
}: {
  favorites: string[];
  activeConcept: string;
  onSelect: (name: string) => void;
}) {
  const c = useColors();
  if (!favorites.length) return null;
  return (
    <div className="concept-picker__chips">
      <span className="concept-picker__label">
        <StarFilled style={{ color: c.warning }} /> 关注
      </span>
      {favorites.map((name) => (
        <button
          key={name}
          type="button"
          className={`concept-chip${name === activeConcept ? " concept-chip--active" : ""}`}
          onClick={() => onSelect(name)}
        >
          <StarFilled style={{ color: c.warning, fontSize: 11 }} />
          <span className="concept-chip__name">{name}</span>
        </button>
      ))}
    </div>
  );
}

function MainlineChips({ mainline, activeConcept, onSelect }: {
  mainline: MarketMainline | undefined;
  activeConcept: string;
  onSelect: (name: string) => void;
}) {
  const c = useColors();
  const plates = useMemo(() => {
    const seen = new Set<string>();
    const flat = [];
    for (const chance of mainline?.items ?? []) {
      for (const plate of chance.plates ?? []) {
        if (!plate.name || seen.has(plate.name)) continue;
        seen.add(plate.name);
        flat.push({
          name: plate.name,
          change_pct: plate.change_pct,
          reason: chance.title || plate.reason,
          faucets: (plate.faucets ?? []).slice(0, 3).map((f) => f.name),
        });
      }
    }
    return flat.sort((a, b) => (b.change_pct ?? -999) - (a.change_pct ?? -999)).slice(0, 8);
  }, [mainline]);

  if (!plates.length) return null;
  return (
    <div className="concept-picker__chips">
      <span className="concept-picker__label">
        <RiseOutlined style={{ color: c.up }} /> 今日主线
      </span>
      {plates.map((plate) => {
        const active = plate.name === activeConcept;
        const hint = [
          plate.reason || null,
          plate.faucets.length ? `龙头：${plate.faucets.join("、")}` : null,
        ]
          .filter(Boolean)
          .join(" · ");
        const chip = (
          <button
            key={plate.name}
            type="button"
            className={`concept-chip${active ? " concept-chip--active" : ""}`}
            onClick={() => onSelect(plate.name)}
          >
            <span className="concept-chip__name">{plate.name}</span>
            {plate.change_pct != null ? (
              <span
                className="concept-chip__pct financial-num"
                style={{ color: plate.change_pct > 0 ? c.up : plate.change_pct < 0 ? c.down : c.textMuted }}
              >
                {plate.change_pct > 0 ? "+" : ""}
                {plate.change_pct.toFixed(2)}%
              </span>
            ) : null}
          </button>
        );
        return hint ? (
          <Tooltip key={plate.name} title={`${plate.name}：${hint}`}>
            {chip}
          </Tooltip>
        ) : (
          chip
        );
      })}
    </div>
  );
}

export default function Concept() {
  const c = useColors();
  const { pageContainerStyle } = useStyles();
  const { Title } = Typography;
  const isNarrow = useMediaQuery("(max-width: 768px)");
  const [{ concept: conceptParam, days, compare }, patchParams] = useConceptPageParams();
  const [mobileView, setMobileView] = useState<"index" | "constituents">("index");
  // 搜索词与输入框显示值必须分开：受控AutoComplete 若直接把 value 绑到
  // 已选概念，用户输入时框内文字不会变化，下拉也就没法跟着过滤。
  const [keyword, setKeyword] = useState("");
  const [inputValue, setInputValue] = useState("");

  // 概念列表排序：按规模（默认）/按最近交易日涨幅；涨幅数据由后端聚合，零上游调用
  const [listOrder, setListOrder] = useState<"size" | "change">("size");
  const listQuery = useConceptList(1200, listOrder);
  const concepts = useMemo(() => (listQuery.data?.items ?? []) as ConceptSummary[], [listQuery.data]);
  const filtered = useConceptSearch(concepts, keyword);
  const [recentConcepts, rememberRecentConcept] = useRecentConcepts();
  const { favorites, has: hasFavorite, toggle: toggleFavorite } = useFavoriteConcepts();
  const hotQuery = useThsHotConcept();
  const mainlineQuery = useMarketMainline();
  // 指数卡片视图：单概念 K 线 / 多概念对比
  const [indexView, setIndexView] = useState<"single" | "compare">("single");

  // URL 没带概念时默认选成分股最多的那个，保证首屏就有内容
  useEffect(() => {
    if (conceptParam || !concepts.length) return;
    patchParams({ concept: concepts[0].name });
  }, [conceptParam, concepts, patchParams]);

  // 外部换概念（如点关联概念/热门概念）时同步输入框
  useEffect(() => {
    setInputValue(conceptParam);
  }, [conceptParam]);

  const concept = conceptParam;
  // 行情按需加载：undefined = 只取本地身份列表（零上游调用），
  // 之后由自动补齐 effect 逐批扩大代码集，后端仍返回完整成分股，行情逐段补齐。
  const [quoteCodes, setQuoteCodes] = useState<string[] | undefined>(undefined);

  // 换概念时回到「不拉行情」，让新概念的身份列表先秒出
  useEffect(() => {
    setQuoteCodes(undefined);
  }, [concept]);

  const constituentsQuery = useConceptConstituents(concept, quoteCodes);
  const indexQuery = useConceptIndex(concept, days);

  const items = constituentsQuery.data?.items;
  const total = constituentsQuery.data?.total ?? 0;
  const allCodes = useMemo(() => (items ?? []).map((item) => item.code), [items]);
  const quoteRequested = quoteCodes?.length ?? 0;
  const quoteComplete = allCodes.length > 0 && quoteRequested >= allCodes.length;

  /**
   * 行情自动补齐：首屏取一小窗保证秒出，然后后台逐批扩大直至全量。
   * - placeholderData 会把上一个概念的数据短暂带回，用 concept 字段守卫；
   * - 一批行情全部落空（上游不可用且无本地兜底）时停止续拉，避免空转。
   */
  useEffect(() => {
    const data = constituentsQuery.data;
    if (!data || data.concept !== concept || constituentsQuery.isFetching) return;
    if (!allCodes.length) return;
    if (!quoteCodes) {
      setQuoteCodes(allCodes.slice(0, INITIAL_QUOTE_WINDOW));
      return;
    }
    if (quoteCodes.length >= allCodes.length) return;
    if (quoteCodes.length > 0 && (data.quote_covered ?? 0) === 0) return;
    setQuoteCodes(allCodes.slice(0, Math.min(quoteCodes.length + QUOTE_WINDOW_STEP, allCodes.length)));
  }, [concept, allCodes, quoteCodes, constituentsQuery.data, constituentsQuery.isFetching]);

  const quoteUnavailable =
    !constituentsQuery.isFetching &&
    quoteCodes != null &&
    quoteCodes.length > 0 &&
    !quoteComplete &&
    (constituentsQuery.data?.quote_covered ?? 0) === 0;

  const handleSelectConcept = useCallback(
    (next: string) => {
      patchParams({
        concept: next,
        // 主概念换到某个对比概念时，把它从对比列表里移除，避免重复曲线
        compare: compare.filter((name) => name !== next),
      });
      setInputValue(next);
      setKeyword("");
      rememberRecentConcept(next);
    },
    [patchParams, rememberRecentConcept, compare],
  );

  const toggleCompareConcept = useCallback(
    (name: string) => {
      const next = compare.includes(name)
        ? compare.filter((item) => item !== name)
        : [...compare, name].slice(0, COMPARE_CONCEPT_LIMIT);
      patchParams({ compare: next });
    },
    [compare, patchParams],
  );

  /** 概念不存在（未收录/已更名）：给出行动引导而不是三个报错面板 */
  const conceptNotFound = useMemo(() => {
    const error = constituentsQuery.error;
    return error instanceof ApiError && error.code === "concept.not_found";
  }, [constituentsQuery.error]);

  // 概念名 → 最近交易日等权涨跌（列表已附带，零额外请求）
  const changeByName = useMemo(() => {
    const map = new Map<string, number>();
    for (const item of concepts) {
      if (item.change_pct != null) map.set(item.name, item.change_pct);
    }
    return map;
  }, [concepts]);

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
      { label: "指数走势", value: "index" },
      { label: `成分股${total ? ` (${total})` : ""}`, value: "constituents" },
    ],
    [total],
  );

  const showIndex = !isNarrow || mobileView === "index";
  const showConstituents = !isNarrow || mobileView === "constituents";

  if (conceptNotFound) {
    return (
      <main className="concept-page" style={pageContainerStyle}>
        <header>
          <div className="u-page-title u-page-title--compact">
            <Title level={3} style={{ margin: 0, color: c.textPrimary }}>
              <ApartmentOutlined /> 概念
            </Title>
          </div>
        </header>
        <Card size="small">
          <div className="concept-missing">
            <p className="concept-missing__title" style={{ color: c.textPrimary }}>
              「{concept}」暂未收录或已更名
            </p>
            <p className="concept-missing__desc" style={{ color: c.textMuted }}>
              概念名单来自本地维护的同花顺映射，热门概念榜中的名称一般都可直接打开。
            </p>
            <div className="concept-missing__actions">
              {(hotQuery.data?.length ?? 0) > 0 ? (
                <Button type="primary" size="small" onClick={() => handleSelectConcept(hotQuery.data![0].name)}>
                  看热门概念
                </Button>
              ) : null}
              <Button size="small" onClick={() => patchParams({ concept: "" })}>重新搜索</Button>
            </div>
          </div>
        </Card>
      </main>
    );
  }

  return (
    <main className="concept-page" style={pageContainerStyle}>
      <header>
        <div className="u-page-title u-page-title--compact">
          <Title level={3} style={{ margin: 0, color: c.textPrimary }}>
            <ApartmentOutlined /> 概念
          </Title>
        </div>
        <p className="concept-page__desc" style={{ color: c.textMuted }}>
          把一个概念当作一个组合：看板块整体走势、谁在领涨，以及与哪些概念联动。
        </p>
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
                  <span style={{ display: "inline-flex", gap: 10, alignItems: "baseline" }}>
                    {item.change_pct != null ? (
                      <span
                        className="financial-num"
                        style={{
                          fontSize: 12,
                          color: item.change_pct > 0 ? c.up : item.change_pct < 0 ? c.down : c.textMuted,
                        }}
                      >
                        {item.change_pct > 0 ? "+" : ""}
                        {item.change_pct.toFixed(2)}%
                      </span>
                    ) : null}
                    <span style={{ color: c.textMuted, fontSize: 12 }}>{item.stock_count} 只</span>
                  </span>
                </span>
              ),
            }))}
            className="concept-search-input"
            style={{ width: "100%", maxWidth: isNarrow ? "100%" : 320 }}
            placeholder="搜索概念，例如「固态电池」"
          >
            <Input.Search allowClear onSearch={handleSelectConcept} />
          </AutoComplete>
          <div className="concept-search-meta">
            {concept ? (
              <Tooltip title={hasFavorite(concept) ? "取消收藏" : "收藏概念，展示在「关注」一栏"}>
                <Button
                  type="text"
                  size="small"
                  aria-label={`${hasFavorite(concept) ? "取消收藏" : "收藏"}-${concept}`}
                  icon={
                    hasFavorite(concept) ? (
                      <StarFilled style={{ color: c.warning }} />
                    ) : (
                      <StarOutlined style={{ color: c.textMuted }} />
                    )
                  }
                  onClick={() => toggleFavorite(concept)}
                />
              </Tooltip>
            ) : null}
            {concept ? (
              <Tag style={{ marginInlineEnd: 0 }} color="blue">
                {concept} · {total || concepts.find((i) => i.name === concept)?.stock_count || 0} 只
              </Tag>
            ) : null}
            <span style={{ fontSize: 12, color: c.textMuted }}>
              共 {concepts.length} 个概念{keyword.trim() ? ` · 匹配 ${filtered.length}` : ""}
            </span>
            <Tooltip title="涨幅为概念成分股最近交易日等权平均（与合成指数同口径）">
              <Segmented
                size="small"
                value={listOrder}
                options={[
                  { label: "按规模", value: "size" },
                  { label: "按涨幅", value: "change" },
                ]}
                onChange={(value) => setListOrder(value as "size" | "change")}
              />
            </Tooltip>
          </div>
        </div>
        <FavoriteChips favorites={favorites} activeConcept={concept} onSelect={handleSelectConcept} />
        <MainlineChips mainline={mainlineQuery.data} activeConcept={concept} onSelect={handleSelectConcept} />
        <HotChips hot={hotQuery.data} activeConcept={concept} onSelect={handleSelectConcept} />
        <RecentChips recent={recentConcepts} activeConcept={concept} onSelect={handleSelectConcept} />
      </Card>

      {isNarrow && (
        <div className="concept-mobile-view-tabs">
          <Segmented
            block
            size="middle"
            value={mobileView}
            options={mobileViewOptions}
            onChange={(val) => setMobileView(val as "index" | "constituents")}
          />
        </div>
      )}

      {showIndex && (
        <Row gutter={[12, 12]} align="stretch">
          <Col xs={24} xl={16}>
            {indexView === "single" ? (
              <Card size="small" style={{ height: "100%" }} styles={{ body: { padding: isNarrow ? 10 : 12 } }}>
                <ConceptIndexPanel
                  concept={concept}
                  points={indexQuery.data?.items}
                  days={days}
                  onDaysChange={(nextDays) => patchParams({ days: nextDays })}
                  isLoading={indexQuery.isLoading}
                  error={indexQuery.error}
                  onRetry={() => void indexQuery.refetch()}
                  constituentTotal={indexQuery.data?.constituent_total ?? 0}
                  constituentUsed={indexQuery.data?.constituent_used ?? 0}
                  truncated={indexQuery.data?.truncated ?? false}
                  toolbarExtra={
                    <Segmented
                      size="small"
                      value="single"
                      options={INDEX_VIEW_OPTIONS}
                      onChange={(value) => setIndexView(value as "single" | "compare")}
                    />
                  }
                />
              </Card>
            ) : (
              <Card size="small" style={{ height: "100%" }} styles={{ body: { padding: isNarrow ? 10 : 12 } }}>
                <div className="concept-index-toolbar">
                  <span className="concept-kpi__name" style={{ color: c.textPrimary }}>{concept} 对比</span>
                  <div className="concept-index-toolbar__controls">
                    <Segmented
                      size="small"
                      value={days}
                      options={CONCEPT_INDEX_RANGES.map((range) => ({ label: range.label, value: range.days }))}
                      onChange={(value) => patchParams({ days: Number(value) })}
                    />
                    <Segmented
                      size="small"
                      value="compare"
                      options={INDEX_VIEW_OPTIONS}
                      onChange={(value) => setIndexView(value as "single" | "compare")}
                    />
                  </div>
                </div>
                <ConceptComparePanel
                  mainConcept={concept}
                  compareConcepts={compare}
                  days={days}
                  onAdd={toggleCompareConcept}
                  onRemove={toggleCompareConcept}
                  onSelectMain={handleSelectConcept}
                />
              </Card>
            )}
          </Col>
          <Col xs={24} xl={8}>
            <ConceptSidePanel
              concept={concept}
              items={items}
              related={related}
              changeByName={changeByName}
              isLoading={constituentsQuery.isLoading}
              error={constituentsQuery.error}
              onRetry={() => void constituentsQuery.refetch()}
              onSelectConcept={handleSelectConcept}
            />
          </Col>
        </Row>
      )}

      {showConstituents && (
        <Card size="small" styles={{ body: { padding: isNarrow ? 10 : 12 } }}>
          {/* key=concept：换概念时重置表格滚动位置与临时排序，从默认「按涨幅」重新开始 */}
          <ConceptConstituentPanel
            key={concept}
            concept={concept}
            items={items}
            total={total}
            isLoading={constituentsQuery.isLoading}
            error={constituentsQuery.error}
            onRetry={() => void constituentsQuery.refetch()}
            quoteRequested={quoteRequested}
            quotePending={constituentsQuery.isFetching}
            quoteUnavailable={quoteUnavailable}
            quotedAt={quoteComplete ? constituentsQuery.data?.quoted_at ?? null : null}
            onSelectConcept={handleSelectConcept}
          />
        </Card>
      )}
    </main>
  );
}
