// 数据可视化：湖覆盖热图（symbol×year，按质量着色）+ 水位展示。

import { getLakeCoverage } from "../../api";
import { useAsync } from "../../hooks/useAsync";
import { Card } from "../../components/Card";
import { EmptyState, ErrorState, LoadingState } from "../../components/States";
import { fmtNum } from "../../format";
import { CoverageHeatmap } from "./CoverageHeatmap";
import { WatermarksTable } from "./WatermarksTable";

export function LakeView() {
  const query = useAsync(() => getLakeCoverage(), []);
  if (query.loading) return <LoadingState label="扫描数据湖覆盖…" />;
  if (query.error) return <ErrorState message={query.error} />;
  const payload = query.data;
  if (!payload) return null;

  return (
    <div className="view view-lake" data-view="lake">
      <Card
        title="数据湖覆盖"
        note={
          payload.available && payload.totals
            ? `${payload.totals.symbols} 个代码 · ${fmtNum(payload.totals.rows, 0)} 行`
            : undefined
        }
      >
        {!payload.available ? (
          <EmptyState title="数据湖不可用" reason={payload.reason ?? "未知原因"} />
        ) : payload.symbols.length === 0 ? (
          <EmptyState title="湖内无 bars_1d 分区" reason="配置的 lake 目录下没有 symbol=*/year=*/part.parquet。" />
        ) : (
          <>
            {payload.totals ? (
              <div className="stat-row">
                <span className="stat"><span className="stat-label">代码数</span><span className="stat-value">{payload.totals.symbols}</span></span>
                <span className="stat"><span className="stat-label">总行数</span><span className="stat-value">{fmtNum(payload.totals.rows, 0)}</span></span>
                <span className="stat stat-ok"><span className="stat-label">ok</span><span className="stat-value">{fmtNum(payload.totals.ok, 0)}</span></span>
                <span className="stat stat-warn"><span className="stat-label">backfilled</span><span className="stat-value">{fmtNum(payload.totals.backfilled, 0)}</span></span>
                <span className="stat stat-bad"><span className="stat-label">suspect</span><span className="stat-value">{fmtNum(payload.totals.suspect, 0)}</span></span>
                <span className="stat"><span className="stat-label">other</span><span className="stat-value">{fmtNum(payload.totals.other, 0)}</span></span>
              </div>
            ) : null}
            <CoverageHeatmap symbols={payload.symbols} />
          </>
        )}
      </Card>
      <Card title="同步水位" note="_meta/watermarks.parquet">
        {!payload.watermarks.available ? (
          <EmptyState title="水位信息不可用" reason={payload.watermarks.reason ?? "未知原因"} />
        ) : (
          <WatermarksTable entries={payload.watermarks.entries ?? []} />
        )}
      </Card>
    </div>
  );
}
