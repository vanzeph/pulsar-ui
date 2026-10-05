# pulsar-ui

Pulsar 的本地可视化看板：一个只读查询服务（`pulsar_ui.server`），读取
run 工件与本地数据湖，服务端预聚合后供前端消费。

## 设计基线

- **只读**：所有端点均为 GET；DuckDB 以只读方式（内存连接 + 单条
  SELECT/WITH 守卫）扫描 Parquet；服务不写入数据湖与工件。
- **本机边界**：服务仅监听 `127.0.0.1`（硬约束，端口可配，主机不可
  配）；本机单用户前提下不做鉴权。
- **不出网**：服务只读本机文件，自身不发起任何外部请求。
- **空态而非报错**：工件缺失、schema 版本不支持、湖内无数据等一律
  返回结构化空态；未知 run id 才是 404。
- **零 pulsar 包依赖**：本仓只依赖三个数据格式契约（`run_manifest.json`
  / `events.parquet` / `metrics_report.json`，pulsar-core 工件契约）与
  数据湖目录布局（`bars_1d/symbol=.../year=.../part.parquet` +
  `_meta/watermarks.parquet`）。

## API

```text
GET /api/runs                    run 清单与指标摘要
GET /api/runs/{id}/equity        净值曲线（服务端预聚合降采样）
GET /api/runs/{id}/trades        逐笔明细（分页）
GET /api/runs/{id}/manifest      RunManifest 原文
GET /api/factors/{name}/ic       因子 IC/IR（工件尚无因子数据：明确空态，待 C3 工件扩展）
GET /api/lake/coverage           数据湖覆盖与质量热图数据
GET /api/lake/bars/{symbol}      个股行情（K 线，可降采样）
```

## 运行

```bash
pip install .            # 或 pip install -e ".[test]" 后运行 pytest
pulsar-ui --port 7800 --runs-dir ./runs --lake-dir ./lake
# 或: python -m pulsar_ui
# 环境变量: PULSAR_UI_RUNS_DIR / PULSAR_UI_LAKE_DIR / PULSAR_UI_PORT
```

浏览器访问 `http://127.0.0.1:7800/docs` 查看交互式 API 文档。

## 仓库状态

- `pulsar_ui.server` — 只读查询服务（本任务 U1）
- `web/` React+ECharts 前端 — U2
- `pulsar_ui.report` 静态报告生成器 — U3

测试包含真实工件样本（由 pulsar-core 的 `write_run_artifacts` 产出，
见 `tests/fixtures/runs/`）与按湖布局契约合成的数据湖。
