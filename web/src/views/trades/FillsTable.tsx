// Per-fill table with the full fee breakdown (server-side pagination).

import { useState } from "react";
import type { Fill } from "../../types";
import { datePart, fmtNum } from "../../format";

export function FillsTable({
  fills,
  page,
  pages,
  total,
  onPage,
  loading,
}: {
  fills: Fill[];
  page: number;
  pages: number;
  total: number;
  onPage: (page: number) => void;
  loading: boolean;
}) {
  return (
    <div className="table-wrap" data-view="trades-fills">
      <table className="data-table">
        <thead>
          <tr>
            <th>seq</th>
            <th>时间</th>
            <th>代码</th>
            <th>方向</th>
            <th>价格</th>
            <th>数量</th>
            <th>佣金</th>
            <th>印花税</th>
            <th>过户费</th>
            <th>费用合计</th>
          </tr>
        </thead>
        <tbody>
          {fills.map((fill) => (
            <tr key={fill.seq} data-side={fill.side}>
              <td>{fill.seq}</td>
              <td>{datePart(fill.ts)}</td>
              <td>{fill.symbol}</td>
              <td>
                <span className={`side side-${fill.side}`}>
                  {fill.side === "buy" ? "买入" : "卖出"}
                </span>
              </td>
              <td>{fmtNum(fill.price, 4)}</td>
              <td>{fmtNum(fill.quantity, 0)}</td>
              <td>{fmtNum(fill.commission, 2)}</td>
              <td>{fmtNum(fill.stamp_duty, 2)}</td>
              <td>{fmtNum(fill.transfer_fee, 2)}</td>
              <td>{fmtNum(fill.fees_total, 2)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="pager">
        <button
          type="button"
          className="btn"
          disabled={page <= 1 || loading}
          onClick={() => onPage(page - 1)}
        >
          上一页
        </button>
        <span className="pager-info">
          第 {page} / {Math.max(pages, 1)} 页 · 共 {total} 笔
          {loading ? " · 加载中…" : ""}
        </span>
        <button
          type="button"
          className="btn"
          disabled={page >= pages || loading}
          onClick={() => onPage(page + 1)}
        >
          下一页
        </button>
      </div>
    </div>
  );
}

export function useFillPage(initial = 1): [number, (page: number) => void] {
  return useState(initial);
}
