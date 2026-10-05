// RunManifest diff: flattened dotted-path comparison against the base run.

import type { ManifestResponse } from "../../types";
import { diffManifests, flattenJson, type ManifestRow } from "../../lib/metrics";

function isUnavailable(doc: ManifestResponse | null): doc is null | { available: false; reason: string } {
  if (doc === null) return true;
  if (doc && typeof doc === "object" && "available" in doc && (doc as { available: unknown }).available === false) {
    return true;
  }
  return false;
}

export function ManifestDiff({
  runIds,
  manifests,
  baseId,
}: {
  runIds: string[];
  manifests: Record<string, ManifestResponse | null>;
  baseId: string | null;
}) {
  const missing = runIds.filter((id) => isUnavailable(manifests[id]));
  if (missing.length > 0) {
    return (
      <div className="state state-empty" data-state="empty">
        <div className="state-glyph">○</div>
        <div className="state-title">部分 run 的 RunManifest 不可用</div>
        <div className="state-reason">
          {missing
            .map((id) => {
              const doc = manifests[id];
              const reason =
                doc && typeof doc === "object" && "reason" in doc
                  ? String((doc as { reason?: string }).reason)
                  : "未知原因";
              return `${id}：${reason}`;
            })
            .join("；")}
        </div>
      </div>
    );
  }
  const rows: ManifestRow[] = diffManifests(
    runIds.map((id) => flattenJson(manifests[id] as Record<string, unknown>)),
  );
  const changed = rows.filter((row) => row.changed);
  return (
    <div className="table-wrap" data-view="backtest-manifest-diff">
      <div className="diff-summary">
        共 {rows.length} 个配置字段，
        <span className={changed.length > 0 ? "hl-changed" : "hl-same"}>
          {changed.length} 个与基准（{baseId ?? "—"}）不同
        </span>
        ——差异字段即参数扫描的对比维度。
      </div>
      <table className="data-table diff-table">
        <thead>
          <tr>
            <th>字段</th>
            {runIds.map((id) => (
              <th key={id}>
                <span className="run-id" title={id}>{id}</span>
                {id === baseId ? <span className="tag">基准</span> : null}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.path} className={row.changed ? "row-changed" : undefined}>
              <th title={row.path}>{row.path}</th>
              {row.values.map((value, index) => (
                <td key={index} title={value}>
                  {value === "" ? "（缺失）" : value}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
