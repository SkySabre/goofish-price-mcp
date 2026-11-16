"""MCP server exposing read-only Xianyu price tools over ai-goofish-monitor's DB."""

import sys
from typing import Any

try:  # mcp >= 2.x
    from mcp.server.mcpserver import MCPServer as _Server
except ModuleNotFoundError:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP as _Server

from . import queries
from .db import ENV_VAR, open_readonly, resolve_db_path

mcp = _Server(
    "goofish-price",
    instructions=(
        "闲鱼(Xianyu/Goofish) 二手行情查询。数据来自本机 ai-goofish-monitor "
        "监控任务持续抓取的挂牌样本（只读，不触碰网站）。查价用 get_price_stats，"
        "看具体在售商品用 latest_items，看蹲守全景用 market_overview / list_watch_tasks。"
    ),
)


def _run(fn, **kwargs: Any) -> dict[str, Any]:
    try:
        conn = open_readonly()
    except Exception as exc:
        return {"error": str(exc), "hint": f"请设置环境变量 {ENV_VAR} 指向 data/app.sqlite3"}
    try:
        return fn(conn, **kwargs)
    finally:
        conn.close()


@mcp.tool()
def get_price_stats(keyword: str, days: int = 30) -> dict[str, Any]:
    """查询某关键词的闲鱼二手行情：均价/中位/最低价、按天价格趋势、最便宜的商品链接。

    keyword 支持模糊匹配（如 "DDR4"）；days 为回看天数(1-365)。
    样本 = 监控任务在搜索条件下每次运行实际看到的挂牌价。
    """
    return _run(queries.price_stats, keyword=keyword, days=days)


@mcp.tool()
def latest_items(
    keyword: str | None = None,
    max_price: float | None = None,
    min_price: float | None = None,
    recommended_only: bool = False,
    limit: int = 20,
) -> dict[str, Any]:
    """列出最近蹲到的在售商品明细（标题/价格/链接/卖家/发布时间），按抓取时间倒序。

    可按关键词、价格区间过滤；recommended_only=True 只看判定为推荐的商品。
    """
    return _run(
        queries.latest_items,
        keyword=keyword,
        max_price=max_price,
        min_price=min_price,
        recommended_only=recommended_only,
        limit=limit,
    )


@mcp.tool()
def market_overview() -> dict[str, Any]:
    """所有已监控关键词的行情速览：最近一天均价/最低价、累计样本量、运行时间。"""
    return _run(queries.market_overview)


@mcp.tool()
def list_watch_tasks() -> dict[str, Any]:
    """列出监控端的蹲守任务（关键词、价格区间、cron、判定模式、已入库数量）。"""
    return _run(queries.watch_tasks)


def main() -> None:
    try:
        print(f"goofish-price-mcp: using db {resolve_db_path()}", file=sys.stderr)
    except FileNotFoundError as exc:
        print(f"goofish-price-mcp: WARN {exc}", file=sys.stderr)
    mcp.run()


if __name__ == "__main__":
    main()
