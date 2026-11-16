"""Pure query functions over the ai-goofish-monitor SQLite schema."""

import json
import sqlite3
from statistics import median
from typing import Any

_PRICE_ROUND = 2


def _round(value: float | None) -> float | None:
    return round(value, _PRICE_ROUND) if value is not None else None


def _summary(prices: list[float]) -> dict[str, Any]:
    if not prices:
        return {"sample_count": 0}
    return {
        "sample_count": len(prices),
        "avg_price": _round(sum(prices) / len(prices)),
        "median_price": _round(median(prices)),
        "min_price": _round(min(prices)),
        "max_price": _round(max(prices)),
    }


def known_keywords(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "SELECT DISTINCT keyword FROM price_snapshots "
        "UNION SELECT DISTINCT keyword FROM result_items "
        "ORDER BY keyword"
    ).fetchall()
    return [row["keyword"] for row in rows if row["keyword"]]


def _no_keyword_result(keyword: str, conn: sqlite3.Connection) -> dict[str, Any]:
    return {
        "keyword": keyword,
        "sample_count": 0,
        "message": f"最近没有 '{keyword}' 的监控样本。数据库中已有的关键词见 available_keywords；"
        "若确无此关键词，需要先在监控端创建蹲守任务。",
        "available_keywords": known_keywords(conn),
    }


def price_stats(
    conn: sqlite3.Connection, keyword: str, days: int = 30
) -> dict[str, Any]:
    days = max(1, min(int(days), 365))
    like = f"%{keyword.strip()}%"
    rows = conn.execute(
        "SELECT snapshot_day, keyword, price, price_display, item_id, title, link "
        "FROM price_snapshots "
        "WHERE keyword LIKE ? COLLATE NOCASE "
        "AND snapshot_day >= date('now', 'localtime', ?) "
        "ORDER BY snapshot_day",
        (like, f"-{days} days"),
    ).fetchall()
    if not rows:
        return _no_keyword_result(keyword, conn)

    by_day: dict[str, list[float]] = {}
    for row in rows:
        by_day.setdefault(row["snapshot_day"], []).append(float(row["price"]))

    all_prices = [float(row["price"]) for row in rows]
    best_by_item: dict[str, sqlite3.Row] = {}
    for row in rows:
        key = row["item_id"] or row["link"] or f"noid-{len(best_by_item)}"
        current = best_by_item.get(key)
        if current is None or float(row["price"]) < float(current["price"]):
            best_by_item[key] = row
    cheapest = [
        {
            "title": (row["title"] or "")[:60],
            "price_display": row["price_display"] or f"¥{row['price']}",
            "link": row["link"],
            "seen_day": row["snapshot_day"],
        }
        for row in sorted(best_by_item.values(), key=lambda r: float(r["price"]))[:5]
    ]

    return {
        "keyword": keyword,
        "matched_keyword": rows[0]["keyword"],
        "days_window": days,
        **_summary(all_prices),
        "unique_items": len(best_by_item),
        "first_day": min(by_day),
        "last_day": max(by_day),
        "daily_trend": [
            {**{"date": day}, **_summary(day_prices)}
            for day, day_prices in sorted(by_day.items())
        ],
        "cheapest_items": cheapest,
    }


def latest_items(
    conn: sqlite3.Connection,
    keyword: str | None = None,
    max_price: float | None = None,
    min_price: float | None = None,
    recommended_only: bool = False,
    limit: int = 20,
) -> dict[str, Any]:
    limit = max(1, min(int(limit), 100))
    sql = (
        "SELECT task_name, keyword, title, price, price_display, link, "
        "seller_nickname, publish_time, crawl_time, is_recommended "
        "FROM result_items WHERE status = 'active'"
    )
    params: list[Any] = []
    if keyword:
        sql += " AND keyword LIKE ? COLLATE NOCASE"
        params.append(f"%{keyword.strip()}%")
    if max_price is not None:
        sql += " AND price <= ?"
        params.append(float(max_price))
    if min_price is not None:
        sql += " AND price >= ?"
        params.append(float(min_price))
    if recommended_only:
        sql += " AND is_recommended = 1"
    sql += " ORDER BY crawl_time DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(sql, params).fetchall()
    return {
        "returned": len(rows),
        "items": [
            {
                "task_name": row["task_name"],
                "keyword": row["keyword"],
                "title": (row["title"] or "")[:80],
                "price_display": row["price_display"] or f"¥{row['price']}",
                "link": row["link"],
                "seller": row["seller_nickname"],
                "publish_time": row["publish_time"],
                "crawl_time": row["crawl_time"],
                "recommended": bool(row["is_recommended"]),
            }
            for row in rows
        ],
    }


def watch_tasks(conn: sqlite3.Connection) -> dict[str, Any]:
    rows = conn.execute(
        "SELECT t.*, "
        "(SELECT COUNT(*) FROM result_items r WHERE r.task_name = t.task_name) AS item_count, "
        "(SELECT MAX(snapshot_time) FROM price_snapshots p WHERE p.task_name = t.task_name) AS last_seen "
        "FROM tasks t ORDER BY t.id"
    ).fetchall()
    tasks = []
    for row in rows:
        try:
            rules = json.loads(row["keyword_rules_json"])
        except (TypeError, ValueError):
            rules = []
        tasks.append(
            {
                "id": row["id"],
                "task_name": row["task_name"],
                "keyword": row["keyword"],
                "enabled": bool(row["enabled"]),
                "is_running": bool(row["is_running"]),
                "decision_mode": row["decision_mode"],
                "cron": row["cron"],
                "price_min": row["min_price"],
                "price_max": row["max_price"],
                "keyword_rules": rules,
                "saved_items": row["item_count"],
                "last_seen": row["last_seen"],
            }
        )
    return {"task_count": len(tasks), "tasks": tasks}


def market_overview(conn: sqlite3.Connection) -> dict[str, Any]:
    rows = conn.execute(
        "SELECT keyword, task_name, COUNT(*) AS total_samples, "
        "MAX(snapshot_time) AS last_run_at, MAX(snapshot_day) AS last_day, "
        "COUNT(DISTINCT snapshot_day) AS active_days "
        "FROM price_snapshots GROUP BY keyword, task_name ORDER BY keyword"
    ).fetchall()
    keywords = []
    for row in rows:
        day_row = conn.execute(
            "SELECT AVG(price) AS avg_price, MIN(price) AS min_price, "
            "COUNT(*) AS n FROM price_snapshots WHERE keyword = ? AND snapshot_day = ?",
            (row["keyword"], row["last_day"]),
        ).fetchone()
        rec_row = conn.execute(
            "SELECT COUNT(*) AS n FROM result_items WHERE keyword = ? "
            "AND is_recommended = 1 AND status = 'active'",
            (row["keyword"],),
        ).fetchone()
        keywords.append(
            {
                "keyword": row["keyword"],
                "task_name": row["task_name"],
                "total_samples": row["total_samples"],
                "active_days": row["active_days"],
                "last_run_at": row["last_run_at"],
                "last_day_summary": {
                    "samples": day_row["n"],
                    "avg_price": _round(day_row["avg_price"]),
                    "min_price": _round(day_row["min_price"]),
                },
                "recommended_items_saved": rec_row["n"],
            }
        )
    return {"keywords": keywords}
