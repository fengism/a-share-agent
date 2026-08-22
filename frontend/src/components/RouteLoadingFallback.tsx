import LoadingSpinner from "./LoadingSpinner";

export default function RouteLoadingFallback() {
  return (
    <div className="route-loading" role="status" aria-live="polite">
      <span className="route-loading__indicator"><LoadingSpinner size="large" /></span>
      <strong>正在加载页面</strong>
      <span>首次打开后，后续切换会更快</span>
    </div>
  );
}
