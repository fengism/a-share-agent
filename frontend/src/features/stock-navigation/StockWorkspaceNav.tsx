import { NavLink } from "react-router-dom";
import { buildStockAnalysisUrl, buildStockProfileUrl } from "../../utils/stockLinks";
import "./stock-workspace-nav.css";

export default function StockWorkspaceNav({ code }: { code: string }) {
  return (
    <nav className="stock-workspace-nav pdf-hide" aria-label="个股页面">
      <NavLink className="stock-workspace-nav__link" end to={buildStockProfileUrl(code)}>
        个股资料
      </NavLink>
      <NavLink className="stock-workspace-nav__link" end to={buildStockAnalysisUrl(code)}>
        AI 分析
      </NavLink>
    </nav>
  );
}
