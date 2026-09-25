import type { ReactNode } from "react";
import { FundOutlined, LineChartOutlined, MessageOutlined, PieChartOutlined } from "@ant-design/icons";
import ThemeSelector from "./ThemeSelector";
import "./auth.css";

export default function AuthShell({ children }: { children: ReactNode }) {
  return (
    <div className="auth-shell">
      <div className="auth-shell__theme-selector">
        <ThemeSelector />
      </div>

      <main className="auth-shell__layout">
        <section className="auth-hero" aria-label="产品简介">
          <div className="auth-hero__brand">
            <span className="auth-hero__brand-mark" aria-hidden="true">
              <LineChartOutlined />
            </span>
            <span>
              <strong>智能投研平台</strong>
              <small>INTELLIGENT INVESTMENT PLATFORM</small>
            </span>
          </div>

          <div className="auth-hero__copy">
            <span className="auth-hero__eyebrow">智能投研工作台</span>
            <h2>让市场信息，更快转化为投资判断</h2>
            <p>聚合行情、资讯、产业链与持仓数据，在一个工作台完成跟踪、分析和复盘。</p>
          </div>

          <div className="auth-hero__chart" aria-hidden="true">
            <div className="auth-hero__chart-label">
              <span>MARKET INSIGHT</span>
              <i />
            </div>
            <svg viewBox="0 0 560 150" preserveAspectRatio="none">
              <path
                className="auth-hero__chart-area"
                d="M0 132 C58 118 78 126 124 101 S204 111 252 72 S332 89 384 48 S468 68 560 18 L560 150 L0 150 Z"
              />
              <path
                className="auth-hero__chart-line"
                d="M0 132 C58 118 78 126 124 101 S204 111 252 72 S332 89 384 48 S468 68 560 18"
              />
            </svg>
          </div>

          <div className="auth-hero__features">
            <span><FundOutlined />行情聚合</span>
            <span><MessageOutlined />智能研判</span>
            <span><PieChartOutlined />仓位管理</span>
          </div>
        </section>

        <section className="auth-card" aria-label="账户访问">
          {children}
        </section>
      </main>
    </div>
  );
}
