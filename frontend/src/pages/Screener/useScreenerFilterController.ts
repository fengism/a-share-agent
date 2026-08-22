import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  DEFAULT_SCREENER_FILTERS,
  parseScreenerUrlState,
  serializeScreenerUrlState,
  type ScreenerUrlState,
} from "../../features/screener/screenerUrlState";
import type { ScreenerFilter } from "../../types/stock";

export function useScreenerFilterController() {
  const [searchParams, setSearchParams] = useSearchParams();
  const appliedState = useMemo(() => parseScreenerUrlState(searchParams), [searchParams]);
  const [filters, setFilters] = useState<ScreenerFilter>(appliedState.filters);
  const { showPercentile, pePercentileMax, pbPercentileMax } = appliedState;

  const commitUrlState = useCallback((nextState: ScreenerUrlState) => {
    const nextParams = serializeScreenerUrlState(nextState);
    if (nextParams.toString() !== searchParams.toString()) {
      setSearchParams(nextParams, { replace: true });
    }
  }, [searchParams, setSearchParams]);

  useEffect(() => {
    setFilters(appliedState.filters);
  }, [appliedState.filters]);

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      commitUrlState({ ...appliedState, filters: { ...filters } });
    }, 300);
    return () => window.clearTimeout(timeoutId);
  }, [appliedState, commitUrlState, filters]);

  const handleSearch = useCallback(() => {
    commitUrlState({ ...appliedState, filters: { ...filters } });
  }, [appliedState, commitUrlState, filters]);

  const handleReset = useCallback(() => {
    setFilters(DEFAULT_SCREENER_FILTERS);
    commitUrlState({
      filters: DEFAULT_SCREENER_FILTERS,
      showPercentile: false,
      pePercentileMax: 50,
      pbPercentileMax: 50,
    });
  }, [commitUrlState]);

  const handlePageChange = useCallback((page: number, pageSize: number) => {
    const newFilters = { ...filters, page, page_size: pageSize };
    setFilters(newFilters);
    commitUrlState({ ...appliedState, filters: newFilters });
  }, [appliedState, commitUrlState, filters]);

  const handleSortChange = useCallback((
    sortBy: ScreenerFilter["sort_by"],
    sortOrder: ScreenerFilter["sort_order"],
  ) => {
    const newFilters = { ...filters, sort_by: sortBy, sort_order: sortOrder, page: 1 };
    setFilters(newFilters);
    commitUrlState({ ...appliedState, filters: newFilters });
  }, [appliedState, commitUrlState, filters]);

  const handleShowPercentileChange = useCallback((value: boolean) => {
    commitUrlState({ ...appliedState, filters: { ...filters }, showPercentile: value });
  }, [appliedState, commitUrlState, filters]);

  const handlePePercentileMaxChange = useCallback((value: number) => {
    commitUrlState({ ...appliedState, filters: { ...filters }, pePercentileMax: value });
  }, [appliedState, commitUrlState, filters]);

  const handlePbPercentileMaxChange = useCallback((value: number) => {
    commitUrlState({ ...appliedState, filters: { ...filters }, pbPercentileMax: value });
  }, [appliedState, commitUrlState, filters]);

  const applySavedFilter = useCallback((state: ScreenerUrlState) => {
    setFilters(state.filters);
    commitUrlState(state);
  }, [commitUrlState]);

  const applyPreset = useCallback((preset: Partial<ScreenerFilter>) => {
    const newFilters = { ...DEFAULT_SCREENER_FILTERS, ...preset, page: 1 };
    setFilters(newFilters);
    commitUrlState({ ...appliedState, filters: newFilters, showPercentile: false });
  }, [appliedState, commitUrlState]);

  return {
    appliedState,
    applyPreset,
    applySavedFilter,
    filters,
    handlePageChange,
    handlePbPercentileMaxChange,
    handlePePercentileMaxChange,
    handleReset,
    handleSearch,
    handleShowPercentileChange,
    handleSortChange,
    pbPercentileMax,
    pePercentileMax,
    setFilters,
    showPercentile,
  };
}
