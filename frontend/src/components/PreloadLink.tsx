import { Link, type LinkProps } from "react-router-dom";
import { useRoutePreload } from "../routes/RoutePreloadContext";

function routePath(to: LinkProps["to"]): string | undefined {
  if (typeof to === "string") return to.split(/[?#]/, 1)[0];
  return to.pathname;
}

export default function PreloadLink({ onFocus, onPointerEnter, to, ...props }: LinkProps) {
  const preloadAppRoute = useRoutePreload();
  const preload = () => {
    const pathname = routePath(to);
    if (pathname) void preloadAppRoute(pathname);
  };

  return (
    <Link
      {...props}
      to={to}
      onFocus={(event) => {
        onFocus?.(event);
        preload();
      }}
      onPointerEnter={(event) => {
        onPointerEnter?.(event);
        preload();
      }}
    />
  );
}
