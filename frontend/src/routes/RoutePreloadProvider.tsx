import type { PropsWithChildren } from "react";
import { RoutePreloadContext, type RoutePreloader } from "./RoutePreloadContext";

export default function RoutePreloadProvider({
  children,
  preload,
}: PropsWithChildren<{ preload: RoutePreloader }>) {
  return (
    <RoutePreloadContext.Provider value={preload}>
      {children}
    </RoutePreloadContext.Provider>
  );
}
