// 因子分析：输入因子名（可多个）→ IC/IR 时序、分位分层收益、相关矩阵。
// 当端点返回结构化空态（当前工件契约尚无因子数据）时，如实展示原因，
// 绝不伪造序列。

import { useState } from "react";
import { getFactorIc } from "../../api";
import type { FactorIcResponse } from "../../types";
import { useAsync } from "../../hooks/useAsync";
import { Card } from "../../components/Card";
import { ErrorState, LoadingState } from "../../components/States";
import { IcSeriesChart } from "./IcSeriesChart";
import { QuantileChart } from "./QuantileChart";
import { CorrelationMatrix } from "./CorrelationMatrix";
import { normalizeIcSeries, normalizeQuantileReturns } from "./normalize";

function parseNames(input: string): string[] {
  return input
    .split(/[,，\s]+/)
    .map((name) => name.trim())
    .filter((name) => name.length > 0)
    .slice(0, 6);
}

function FactorResult({ payload }: { payload: FactorIcResponse }) {
  if (!payload.available) {
    return (
      <div className="state state-empty" data-state="empty">
        <div className="state-glyph">○</div>
        <div className="state-title">因子「{payload.factor}」暂无 IC 数据（明确空态）</div>
        <div className="state-reason">{payload.reason ?? "未知原因"}</div>
        {payload.checked_sources && payload.checked_sources.length > 0 ? (
          <div className="state-meta">已检查的数据源：{payload.checked_sources.join("；")}</div>
        ) : null}
        {payload.pending ? <div className="state-meta">待补齐：{payload.pending}</div> : null}
      </div>
    );
  }
  const ic = normalizeIcSeries(payload.ic_series ?? []);
  const quantiles = normalizeQuantileReturns(payload.quantile_returns ?? []);
  if (!ic.recognized) {
    return (
      <div className="state state-empty" data-state="empty">
        <div className="state-glyph">○</div>
        <div className="state-title">因子「{payload.factor}」的 IC 序列结构无法识别</div>
        <div className="state-reason">
          端点标记数据可用，但序列字段结构与本前端实现的读取器不匹配；
          为避免误读，不渲染图表。请核对 C3 工件扩展的序列 schema。
        </div>
      </div>
    );
  }
  return (
    <div className="factor-result">
      <IcSeriesChart factor={payload.factor} points={ic.points} ir={payload.ir} />
      {quantiles.recognized && quantiles.points.length > 0 ? (
        <div className="chart-block">
          <div className="chart-block-title">分位分层收益</div>
          <QuantileChart points={quantiles.points} />
        </div>
      ) : (
        <div className="state state-empty" data-state="empty">
          <div className="state-glyph">○</div>
          <div className="state-title">分位分层收益暂缺</div>
          <div className="state-reason">
            {payload.quantile_returns && payload.quantile_returns.length > 0
              ? "序列结构与本前端实现的读取器不匹配，不渲染图表。"
              : "该因子的 quantile_returns 为空。"}
          </div>
        </div>
      )}
    </div>
  );
}

export function FactorsView() {
  const [input, setInput] = useState("momentum_20");
  const [names, setNames] = useState<string[]>([]);
  const query = useAsync(
    () => Promise.all(names.map((name) => getFactorIc(name))),
    [names.join("|")],
  );
  const submit = () => setNames(parseNames(input));

  const usable: Record<string, import("./normalize").IcPoint[]> = {};
  const usableFactors: string[] = [];
  const payloads = query.data;
  if (payloads) {
    names.forEach((name, index) => {
      const payload = payloads[index];
      if (payload?.available) {
        const ic = normalizeIcSeries(payload.ic_series ?? []);
        if (ic.recognized && ic.points.length > 0) {
          usable[name] = ic.points;
          usableFactors.push(name);
        }
      }
    });
  }

  return (
    <div className="view view-factors" data-view="factors">
      <Card
        title="因子健康诊断"
        note="IC/IR 时序 · 分位分层收益 · 相关矩阵（数据来自 /api/factors/{name}/ic）"
      >
        <div className="factor-input-row">
          <input
            className="factor-input"
            data-role="factor-input"
            value={input}
            placeholder="因子名，如 momentum_20；多个用逗号分隔"
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") submit();
            }}
          />
          <button type="button" className="btn" data-role="factor-submit" onClick={submit}>
            查询
          </button>
        </div>
        {names.length === 0 ? (
          <div className="state state-empty" data-state="empty">
            <div className="state-glyph">○</div>
            <div className="state-title">输入因子名开始分析</div>
            <div className="state-reason">
              因子名为注册标识符（如 momentum_20）；多个因子用逗号分隔可查看相关矩阵。
            </div>
          </div>
        ) : query.loading ? (
          <LoadingState label="查询因子 IC…" />
        ) : query.error ? (
          <ErrorState message={query.error} />
        ) : (
          <div className="factor-results">
            {query.data?.map((payload, index) => (
              <div key={names[index]} className="factor-result-block">
                <h3 className="factor-name">{names[index]}</h3>
                {payload ? <FactorResult payload={payload} /> : null}
              </div>
            ))}
          </div>
        )}
      </Card>
      <Card
        title="相关矩阵"
        note={usableFactors.length >= 2 ? "基于对齐后的 IC 序列" : "需要 ≥2 个有 IC 数据的因子"}
      >
        {usableFactors.length >= 2 ? (
          <CorrelationMatrix factors={usableFactors} series={usable} />
        ) : (
          <div className="state state-empty" data-state="empty">
            <div className="state-glyph">○</div>
            <div className="state-title">相关矩阵暂不可用</div>
            <div className="state-reason">
              当前有 IC 数据的因子不足两个（{usableFactors.length} 个）。查询多个因子后自动计算。
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}
