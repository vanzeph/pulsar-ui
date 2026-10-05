// 水位展示：_meta/watermarks.parquet 的同步位置。

import type { WatermarkEntry } from "../../types";
import { datePart } from "../../format";

export function WatermarksTable({ entries }: { entries: WatermarkEntry[] }) {
  return (
    <div className="table-wrap" data-view="lake-watermarks">
      <table className="data-table">
        <thead>
          <tr>
            <th>来源</th>
            <th>数据集</th>
            <th>分区</th>
            <th>行数</th>
            <th>同步至</th>
            <th>更新时间</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((entry) => (
            <tr key={`${entry.source}-${entry.dataset}-${entry.partition}`}>
              <td>{entry.source}</td>
              <td>{entry.dataset}</td>
              <td>{entry.partition}</td>
              <td>{entry.rows?.toLocaleString("zh-CN") ?? "—"}</td>
              <td>{datePart(entry.synced_through)}</td>
              <td>{datePart(entry.updated_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
