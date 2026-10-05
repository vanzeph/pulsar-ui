// 回测对比：run 列表（experiment 分组）→ 选 ≥2 个 run 叠加净值曲线、
// 指标对比表、回撤曲线、月度收益热图、RunManifest 差异对照。

import { useEffect, useMemo, useState } from "react";
import { getEquity, getManifest, listRuns } from "../../api";
import type { EquityResponse, ManifestResponse, RunSummary } from "../../types";
import { useAsync } from "../../hooks/useAsync";
import { Card } from "../../components/Card";
import { EmptyState, ErrorState, LoadingState } from "../../components/States";
import { MAX_COMPARE, RunList } from "./RunList";
import { MetricsTable } from "./MetricsTable";
import { EquityChart, type EquitySeries } from "./EquityChart";
import { MonthlyHeatmap } from "./MonthlyHeatmap";
import { ManifestDiff } from "./ManifestDiff";

export function BacktestView() {
  const runsQuery = useAsync(() => listRuns(), []);
  const [selected, setSelected] = useState<string[]>([]);
  const [equities, setEquities] = useState<Record<string, EquityResponse>>({});
  const [manifests, setManifests] = useState<Record<string, ManifestResponse | null>>({});

  const runs = runsQuery.data?.runs ?? [];
  useEffect(() => {
    setSelected((current) => {
      const alive = current.filter((id) => runs.some((run) => run.run_id === id));
      if (alive.length === 0 && runs.length > 0) {
        return runs.slice(0, Math.min(2, runs.length)).map((run) => run.run_id);
      }
      return alive;
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runsQuery.data]);

  useEffect(() => {
    let alive = true;
    for (const runId of selected) {
      if (equities[runId] === undefined) {
        getEquity(runId)
          .then((payload) => {
            if (alive) setEquities((prev) => ({ ...prev, [runId]: payload }));
          })
          .catch(() => {
            if (alive)
              setEquities((prev) => ({
                ...prev,
                [runId]: { run_id: runId, available: false, reason: "净值曲线请求失败" },
              }));
          });
      }
      if (manifests[runId] === undefined) {
        getManifest(runId)
          .then((payload) => {
            if (alive) setManifests((prev) => ({ ...prev, [runId]: payload }));
          })
          .catch(() => {
            if (alive) setManifests((prev) => ({ ...prev, [runId]: null }));
          });
      }
    }
    return () => {
      alive = false;
    };
  }, [selected, equities, manifests]);

  const toggle = (runId: string) => {
    setSelected((current) =>
      current.includes(runId)
        ? current.filter((id) => id !== runId)
        : current.length >= MAX_COMPARE
          ? current
          : [...current, runId],
    );
  };

  const selectedRuns: RunSummary[] = useMemo(
    () => selected.map((id) => runs.find((run) => run.run_id === id)).filter((r): r is RunSummary => !!r),
    [selected, runs],
  );
  const series: EquitySeries[] = selected
    .map((id) => equities[id])
    .filter((payload): payload is EquityResponse => !!payload)
    .map((payload) => ({
      runId: payload.run_id,
      nav: (payload.points ?? []).map((p) => ({ ts: p.ts, value: p.nav })),
    }))
    .filter((item) => item.nav.length > 0);
  const unavailableEquity = selected
    .map((id) => equities[id])
    .filter((payload): payload is EquityResponse => !!payload && !payload.available);

  if (runsQuery.loading) return <LoadingState label="加载 run 清单…" />;
  if (runsQuery.error) return <ErrorState message={runsQuery.error} />;

  return (
    <div className="view view-backtest" data-view="backtest">
      <div className="view-grid">
        <Card title="Run 清单" note={`勾选 2-${MAX_COMPARE} 个 run 进行对比`} className="card-runs">
          <RunList runs={runs} selected={selected} onToggle={toggle} />
        </Card>
        <div className="view-main">
          <Card
            title="指标对比"
            note={`基准：${selected[0] ?? "—"}`}
            className="card-metrics"
          >
            {selectedRuns.length === 0 ? (
              <EmptyState title="尚未选择 run" reason="在左侧勾选至少一个 run 后展示指标对比。" />
            ) : (
              <MetricsTable runs={selectedRuns} baseId={selected[0] ?? null} />
            )}
          </Card>
          <Card
            title="净值曲线与回撤"
            note={series.length > 0 ? "上：净值叠加；下：回撤（共享缩放）" : undefined}
          >
            {series.length === 0 ? (
              selected.length === 0 ? (
                <EmptyState title="尚未选择 run" reason="勾选 run 后叠加其净值曲线与回撤。" />
              ) : (
                <EmptyState title="所选 run 无净值数据" reason={unavailableEquity.map((e) => `${e.run_id}：${e.reason ?? "未知原因"}`).join("；") || "净值数据加载中…"} />
              )
            ) : (
              <EquityChart series={series} />
            )}
          </Card>
          <Card title="月度收益热图" note="按月收益着色（红涨绿跌）">
            {series.length === 0 ? (
              <EmptyState title="无月度收益可展示" reason="需要至少一个带净值曲线的 run。" />
            ) : (
              <MonthlyHeatmap series={series} />
            )}
          </Card>
          <Card title="RunManifest 差异对照" note="以第一个所选 run 为基准">
            {selected.length === 0 ? (
              <EmptyState title="尚未选择 run" reason="勾选 run 后对照其 RunManifest 配置差异。" />
            ) : (
              <ManifestDiff runIds={selected} manifests={manifests} baseId={selected[0] ?? null} />
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
