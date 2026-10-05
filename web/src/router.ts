// Minimal history-API router for the four client-side views. The server
// hosts the SPA and falls back to index.html for these paths, so direct
// navigation and refresh both work.

import { useEffect, useState } from "react";

export const ROUTES = ["/", "/factors", "/trades", "/lake"] as const;
export type Route = (typeof ROUTES)[number];

const TITLES: Record<Route, string> = {
  "/": "回测对比",
  "/factors": "因子分析",
  "/trades": "交易分析",
  "/lake": "数据可视化",
};

export function routeTitle(route: Route): string {
  return TITLES[route];
}

function normalize(pathname: string): Route {
  const path = pathname.replace(/\/+$/, "") || "/";
  return (ROUTES as readonly string[]).includes(path) ? (path as Route) : "/";
}

export function useRoute(): Route {
  const [route, setRoute] = useState<Route>(() => normalize(window.location.pathname));
  useEffect(() => {
    const onPop = () => setRoute(normalize(window.location.pathname));
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);
  return route;
}

export function navigate(route: Route): void {
  if (window.location.pathname !== route) {
    window.history.pushState({}, "", route);
  }
  window.dispatchEvent(new PopStateEvent("popstate"));
}
