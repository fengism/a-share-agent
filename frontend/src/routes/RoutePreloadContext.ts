import { createContext, useContext } from "react";

export type RoutePreloader = (pathname: string) => Promise<void> | undefined;

const noopRoutePreloader: RoutePreloader = () => undefined;
export const RoutePreloadContext = createContext<RoutePreloader>(noopRoutePreloader);

export function useRoutePreload(): RoutePreloader {
  return useContext(RoutePreloadContext);
}
