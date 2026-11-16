# goofish-price-mcp

把 [ai-goofish-monitor](https://github.com/Usagi-org/ai-goofish-monitor) 积累的闲鱼行情数据暴露成 MCP（Model Context Protocol）工具，让任意 AI Agent（Claude Desktop / Cursor / Cline / 本地 harness…）直接查询二手价格、历史趋势和蹲守结果。

Read-only MCP server that exposes Xianyu (Goofish) second-hand market prices collected by [ai-goofish-monitor](https://github.com/Usagi-org/ai-goofish-monitor) watch tasks.

## 它解决什么问题

ai-goofish-monitor 在浏览器里 7×24 蹲守关键词，把每次搜索页看到的挂牌价存进本地 SQLite。
本项目**只读这份数据库**（不碰网站、零风控风险、毫秒级响应），把它翻译成 Agent 友好的工具：

> 你：“DDR4 16G 现在什么行情？有没有低于 300 的单条？”
> Agent 调 `get_price_stats("DDR4")` + `latest_items("DDR4", max_price=300)` → 直接给出均价、趋势和具体商品链接。

## Tools

| Tool | 说明 |
|---|---|
| `get_price_stats(keyword, days=30)` | 行情统计：均价/中位/最低/最高、按天趋势、最便宜的 5 条商品（含链接）。关键词模糊匹配 |
| `latest_items(keyword?, max_price?, min_price?, recommended_only?, limit)` | 最近蹲到的在售商品明细（标题/价格/链接/卖家/发布时间） |
| `market_overview()` | 所有已监控关键词的行情速览 |
| `list_watch_tasks()` | 蹲守任务清单（关键词、价格区间、cron、判定模式、已入库数量） |

> 样本口径：`get_price_stats` 的数据 = 监控任务在其搜索条件（价格区间/个人闲置等筛选）下每次运行**实际看到的挂牌价**，会受任务筛选条件影响，不等于全网成交均价。

## Quick start

前置：本机已部署 ai-goofish-monitor 且至少跑过一个蹲守任务（产生 `data/app.sqlite3`）。

```bash
pip install -e .            # 或 uv pip install -e .
export GOOFISH_DB_PATH=/path/to/ai-goofish-monitor/data/app.sqlite3
goofish-price-mcp           # stdio MCP server，打印 DB 路径到 stderr 后等待连接
```

接入 MCP 客户端（以 Claude Desktop / 通用 `mcpServers` 配置为例）：

```json
{
  "mcpServers": {
    "goofish-price": {
      "command": "/path/to/venv/bin/goofish-price-mcp",
      "env": { "GOOFISH_DB_PATH": "/path/to/ai-goofish-monitor/data/app.sqlite3" }
    }
  }
}
```

DB 路径解析顺序：`GOOFISH_DB_PATH` → `./data/app.sqlite3` → `/app/data/app.sqlite3` → `~/.ai-goofish/data/app.sqlite3`。

## Development

```bash
python tests/test_queries.py   # 内存库单元测试，无外部依赖
```

只读连接（`file:...?mode=ro`）与监控进程的 WAL 写入共存，不会阻塞爬虫。

## Roadmap (v0.2+)

- `refresh_price(keyword)`：按需现抓一屏实时价（复用登录态 + 进程锁排队）
- `add_watch_task(keyword, max_price)`：Agent 一句话建立新蹲守任务
- PyPI 发布（`uvx goofish-price-mcp`）

## License

MIT · 数据归属其来源（闲鱼页面公开展示信息），本项目仅供学习研究。
