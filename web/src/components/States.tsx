// Explicit outcome states: the design's rule is "工件缺失显示明确空态
// 而非报错", so unavailable data renders as a named, explained panel.

import type { ReactNode } from "react";

export function EmptyState({
  title,
  reason,
  sources,
  pending,
  hint,
}: {
  title: string;
  reason?: string | null;
  sources?: string[];
  pending?: string | null;
  hint?: ReactNode;
}) {
  return (
    <div className="state state-empty" data-state="empty">
      <div className="state-glyph">○</div>
      <div className="state-title">{title}</div>
      {reason ? <div className="state-reason">{reason}</div> : null}
      {sources && sources.length > 0 ? (
        <div className="state-meta">已检查的数据源：{sources.join("；")}</div>
      ) : null}
      {pending ? <div className="state-meta">待补齐：{pending}</div> : null}
      {hint ? <div className="state-hint">{hint}</div> : null}
    </div>
  );
}

export function ErrorState({ message }: { message: string }) {
  return (
    <div className="state state-error" data-state="error">
      <div className="state-glyph">✕</div>
      <div className="state-title">请求失败</div>
      <div className="state-reason">{message}</div>
    </div>
  );
}

export function LoadingState({ label = "加载中…" }: { label?: string }) {
  return (
    <div className="state state-loading" data-state="loading">
      <div className="state-glyph spin">◠</div>
      <div className="state-title">{label}</div>
    </div>
  );
}
