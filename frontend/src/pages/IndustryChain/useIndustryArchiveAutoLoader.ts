import { useEffect, useRef } from "react";

import type { IndustryChainResult } from "../../types/stock";

interface IndustryArchiveRequest {
  name: string;
  archiveId: string;
}

interface IndustryArchiveAutoLoaderOptions {
  activeName: string;
  latestArchiveId: string;
  isLatestLoading: boolean;
  isAnalyzing: boolean;
  hasDisplayedResult: boolean;
  hasCurrentRouteError: boolean;
  hasCurrentRouteStopped?: boolean;
  loadArchive: (request: IndustryArchiveRequest) => Promise<IndustryChainResult>;
  loadResult: (name: string, result: IndustryChainResult, archiveId: string) => void;
}

export function useIndustryArchiveAutoLoader({
  activeName,
  latestArchiveId,
  isLatestLoading,
  isAnalyzing,
  hasDisplayedResult,
  hasCurrentRouteError,
  hasCurrentRouteStopped = false,
  loadArchive,
  loadResult,
}: IndustryArchiveAutoLoaderOptions): void {
  const mountedRef = useRef(false);
  const requestedKeyRef = useRef("");
  const activeRequestKeyRef = useRef("");
  const loadArchiveRef = useRef(loadArchive);
  const loadResultRef = useRef(loadResult);

  loadArchiveRef.current = loadArchive;
  loadResultRef.current = loadResult;

  const shouldLoad = Boolean(
    activeName
    && latestArchiveId
    && !isLatestLoading
    && !isAnalyzing
    && !hasDisplayedResult
    && !hasCurrentRouteError
    && !hasCurrentRouteStopped,
  );
  const requestKey = shouldLoad
    ? JSON.stringify([activeName, latestArchiveId])
    : "";
  activeRequestKeyRef.current = requestKey;

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    if (!requestKey) {
      requestedKeyRef.current = "";
      return;
    }
    if (requestedKeyRef.current === requestKey) return;
    requestedKeyRef.current = requestKey;

    void loadArchiveRef.current({ name: activeName, archiveId: latestArchiveId })
      .then((data) => {
        if (!mountedRef.current || activeRequestKeyRef.current !== requestKey) return;
        loadResultRef.current(activeName, data, latestArchiveId);
      })
      .catch(() => undefined);
  }, [activeName, latestArchiveId, requestKey]);
}
