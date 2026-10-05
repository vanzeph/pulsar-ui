# pulsar-ui

Pulsar 的本地可视化看板：一个只读查询服务（`pulsar_ui.server`）+ 内嵌托管的
React+ECharts 前端（`web/`），读取 run 工件与本地数据湖，服务端预聚合后供
前端消费。

## 设计基线

- **只读**：所有 API 端点均为 GET；DuckDB 以只读方式（内存连接 + 单条
  SELECT/WITH 守卫）扫描 Parquet；服务不写入数据湖与工件。
- **本机边界**：服务仅监听 `127.0.0.1`（硬约束，端口可配，主机不可
  配）；本机单用户前提下不做鉴权。
- **不出网**：服务只读本机文件，自身不发起任何外部请求；前端依赖全部
  打包进构建产物，无 CDN 运行时依赖。
- **空态而非报错**：工件缺失、schema 版本不支持、湖内无数据等一律
  返回结构化空态，前端如实呈现原因；未知 run id 才是 404。
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

## 看板（四视图）

浏览器访问 `http://127.0.0.1:7800/`：

| 路由 | 视图 | 能力 |
|-|-|-|
| `/` | 回测对比 | run 清单（experiment 分组）→ 勾选 ≥2 个 run：净值叠加 + 回撤、指标对比表、月度收益热图、RunManifest 差异对照 |
| `/factors` | 因子分析 | 因子名查询：IC/IR 时序、分位分层收益、多因子相关矩阵（当前为明确空态，如实展示原因） |
| `/trades` | 交易分析 | K 线叠加买卖点（湖内行情 × 逐笔成交）、逐笔明细含费用（服务端分页）、FIFO 持仓周期 |
| `/lake` | 数据可视化 | 湖覆盖热图（symbol × year，按质量着色）、同步水位 |

## 运行

```bash
pip install .            # 或 pip install -e ".[test]" 后运行 pytest
pulsar-ui --port 7800 --runs-dir ./runs --lake-dir ./lake
# 或: python -m pulsar_ui
# 环境变量: PULSAR_UI_RUNS_DIR / PULSAR_UI_LAKE_DIR / PULSAR_UI_PORT
```

浏览器访问 `http://127.0.0.1:7800/`（看板）或 `/docs`（交互式 API 文档）。

## 前端构建（可复现交付方式）

前端源码在 `web/`（Vite + React + TS + ECharts，组件按视图分文件）。
**交付形态**：构建产物提交在 `src/pulsar_ui/static/` 作为包资源，
`pulsar_ui.server` 启动即在 `/` 托管（含 SPA fallback），安装与运行都
不需要 Node。工具链由 `web/package-lock.json` 锁定，重建方式：

```bash
tools/build_web.sh        # cd web && npm ci && npm run build（零 TS 错误才通过）
```

CI 的 `web` job 对源码重新执行同一脚本作为可构建性闸门；`tests` job
断言提交的产物确由服务托管（`tests/test_web_hosting.py`）。修改前端后
请重新运行该脚本并提交 `src/pulsar_ui/static/` 下的变更。

## 静态报告（`pulsar_ui.report`）

run 结束后可为该 run 生成一份自包含的静态 HTML 报告：数据与图表全部
内嵌（纯 HTML + CSS + 内联 SVG，无脚本、无外部 CDN、零外部请求），
双击即看、可离线分享；与看板读取同一套 run 工件，不依赖服务运行，
零 pulsar 包依赖。

```bash
python -m pulsar_ui.report <run_dir>            # 产出 <run_dir>/report.html
python -m pulsar_ui.report <run_dir> -o r.html  # 自定义输出路径
```

报告内容：工件状态、RunManifest 摘要（含实验分组与数据水位）、关键
指标表、净值/回撤内嵌图、费用归因、逐笔成交表（含
journal_digest）。契约语义与 `pulsar_ui.artifacts` 一致：工件
schema_version 与生成器不匹配时输出明确的错误页（不做半解析），工件
缺失时对应章节渲染明确空态。

### pulsar-app 挂接（run 结束回调）

pulsar-app 不需要 import 本包，也不需要改动代码结构：在 run 结束、
三工件（`run_manifest.json` / `events.parquet` / `metrics_report.json`）
落盘之后追加一行命令即可，报告写入 run 目录、随 RunManifest 一并归档：

```bash
python -m pulsar_ui.report "<该次 run 的 run 目录>"
```

（若本包以 `pip install pulsar-ui` 安装在 pulsar-app 同一环境，直接
调用 `pulsar_ui.report.generate_report(run_dir)` 亦可。）

## 仓库状态

- `pulsar_ui.server` — 只读查询服务（U1）
- `web/` React+ECharts 前端 + `pulsar_ui.webapp` 静态托管 — U2
- `pulsar_ui.report` — 静态报告生成器（U3：`python -m pulsar_ui.report <run_dir>`）

测试包含真实工件样本（由 pulsar-core 的 `write_run_artifacts` 产出，
见 `tests/fixtures/runs/`）与按湖布局契约合成的数据湖；四视图冒烟
（`tests/test_web_smoke.py`）在合成湖上补齐 run 时段分区后断言 K 线与
买卖点可对齐。
