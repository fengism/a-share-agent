import { lazy, Suspense, useEffect, useState } from "react";
import { SearchOutlined } from "@ant-design/icons";
import { loadAppHeaderSearch } from "./appHeaderSearchLoader";

const AppHeaderSearch = lazy(loadAppHeaderSearch);

interface DeferredAppHeaderSearchProps {
  isMobile: boolean;
}

function SearchTrigger({
  isMobile,
  isBusy = false,
  onActivate,
  onIntent,
}: {
  isMobile: boolean;
  isBusy?: boolean;
  onActivate?: () => void;
  onIntent?: () => void;
}) {
  return (
    <button
      type="button"
      className={`app-header-search-trigger${isMobile ? " app-header-search-trigger--mobile" : ""}`}
      aria-label="打开股票搜索"
      aria-busy={isBusy}
      onPointerEnter={onIntent}
      onTouchStart={onIntent}
      onFocus={onIntent}
      onClick={onActivate}
    >
      {!isMobile && <SearchOutlined className="app-header-search-trigger__prefix" />}
      <span className="app-header-search-trigger__label">
        {isMobile ? "代码 / 名称" : "输入代码或名称，如 600519、贵州茅台、AAPL"}
      </span>
      {!isMobile && <kbd className="app-search-kbd">⌘K</kbd>}
      <span className="app-header-search-trigger__action" aria-hidden="true">
        <SearchOutlined />
      </span>
    </button>
  );
}

export default function DeferredAppHeaderSearch({ isMobile }: DeferredAppHeaderSearchProps) {
  const [active, setActive] = useState(false);
  const preload = () => {
    void loadAppHeaderSearch().catch(() => undefined);
  };

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        preload();
        setActive(true);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  if (!active) {
    return (
      <SearchTrigger
        isMobile={isMobile}
        onIntent={preload}
        onActivate={() => setActive(true)}
      />
    );
  }

  return (
    <Suspense fallback={<SearchTrigger isMobile={isMobile} isBusy />}>
      <AppHeaderSearch isMobile={isMobile} autoFocus />
    </Suspense>
  );
}
