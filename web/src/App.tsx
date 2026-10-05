// Dashboard shell: header, four-view navigation, history routing.

import { ROUTES, navigate, routeTitle, useRoute, type Route } from "./router";
import { BacktestView } from "./views/backtest/BacktestView";
import { FactorsView } from "./views/factors/FactorsView";
import { TradesView } from "./views/trades/TradesView";
import { LakeView } from "./views/lake/LakeView";

function viewFor(route: Route) {
  switch (route) {
    case "/factors":
      return <FactorsView />;
    case "/trades":
      return <TradesView />;
    case "/lake":
      return <LakeView />;
    default:
      return <BacktestView />;
  }
}

export default function App() {
  const route = useRoute();
  return (
    <div className="app" data-view-root>
      <header className="app-head">
        <div className="app-brand">
          <span className="app-logo">✦</span>
          <span className="app-title">Pulsar Dashboard</span>
          <span className="app-sub">本机只读看板 · 127.0.0.1</span>
        </div>
        <nav className="app-nav" data-role="main-nav">
          {ROUTES.map((path) => (
            <button
              key={path}
              type="button"
              className={`nav-item${route === path ? " is-active" : ""}`}
              data-nav={path}
              onClick={() => navigate(path)}
            >
              {routeTitle(path)}
            </button>
          ))}
        </nav>
      </header>
      <main className="app-main">{viewFor(route)}</main>
      <footer className="app-foot">
        只读消费 run 工件与本地数据湖 · 工件缺失显示明确空态 · 不发起任何外部请求
      </footer>
    </div>
  );
}
