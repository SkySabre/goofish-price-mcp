"""Self-contained unit tests: python tests/test_queries.py (also pytest-compatible)."""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from goofish_price_mcp import queries

SCHEMA = """
CREATE TABLE price_snapshots (
    keyword TEXT, task_name TEXT, snapshot_time TEXT, snapshot_day TEXT,
    run_id TEXT, item_id TEXT, title TEXT, price REAL, price_display TEXT, link TEXT
);
CREATE TABLE result_items (
    task_name TEXT, keyword TEXT, title TEXT, price REAL, price_display TEXT,
    link TEXT, seller_nickname TEXT, publish_time TEXT, crawl_time TEXT,
    is_recommended INTEGER, status TEXT DEFAULT 'active'
);
CREATE TABLE tasks (
    id INTEGER PRIMARY KEY, task_name TEXT, enabled INTEGER, keyword TEXT,
    cron TEXT, min_price TEXT, max_price TEXT, decision_mode TEXT,
    keyword_rules_json TEXT, is_running INTEGER
);
"""

SEED = [
    ("INSERT INTO price_snapshots VALUES (?,?,?,?,?,?,?,?,?,?)",
     [
      ("DDR4 16G", "蹲DDR4内存", "2026-11-16T10:00:00", "2026-11-16", "r1", "i1", "三星 16G", 300, "¥300", "l1"),
      ("DDR4 16G", "蹲DDR4内存", "2026-11-16T10:00:00", "2026-11-16", "r1", "i2", "光威 16G", 350, "¥350", "l2"),
      ("DDR4 16G", "蹲DDR4内存", "2026-11-17T10:00:00", "2026-11-17", "r2", "i1", "三星 16G", 280, "¥280", "l1"),
      ("半高显卡", "蹲刀卡", "2026-11-16T09:00:00", "2026-11-16", "r1", "k1", "GT620", 66, "¥66", "l3"),
     ]),
    ("INSERT INTO result_items (task_name,keyword,title,price,price_display,link,seller_nickname,publish_time,crawl_time,is_recommended) VALUES (?,?,?,?,?,?,?,?,?,?)",
     [
      ("蹲DDR4内存", "DDR4 16G", "三星 16G DDR4", 280, "¥280", "l1", "卖家A", "2026-11-15 10:00", "2026-11-17T10:00:00", 1),
      ("蹲DDR4内存", "DDR4 16G", "杂牌拆机条", 90, "¥90", "l9", "卖家B", "2026-11-15 12:00", "2026-11-17T10:00:05", 0),
      ("蹲刀卡", "半高显卡", "GT620 亮机", 66, "¥66", "l3", "卖家C", "2026-11-14 08:00", "2026-11-16T09:00:00", 1),
     ]),
    ("INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?,?,?)",
     [
      (0, "蹲刀卡", 1, "半高显卡", None, "50", "600", "keyword", '["半高","刀卡"]', 0),
      (1, "蹲DDR4内存", 1, "DDR4 16G", None, "50", "400", "keyword", '["ddr4 16g"]', 0),
     ]),
]


def make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    for sql, rows in SEED:
        conn.executemany(sql, rows)
    conn.commit()
    return conn


def test_price_stats_fuzzy_and_trend():
    conn = make_conn()
    stats = queries.price_stats(conn, "ddr4", days=365)
    assert stats["sample_count"] == 3, stats
    assert stats["matched_keyword"] == "DDR4 16G"
    assert stats["min_price"] == 280.0 and stats["max_price"] == 350.0
    assert stats["median_price"] == 300.0
    assert len(stats["daily_trend"]) == 2
    assert stats["cheapest_items"][0]["price_display"] == "¥280"
    missing = queries.price_stats(conn, "不存在词", days=30)
    assert missing["sample_count"] == 0 and "DDR4 16G" in missing["available_keywords"]


def test_latest_items_filters():
    conn = make_conn()
    capped = queries.latest_items(conn, keyword="DDR4", max_price=290)
    assert capped["returned"] == 2
    rec_only = queries.latest_items(conn, keyword="DDR4", recommended_only=True)
    assert rec_only["returned"] == 1 and rec_only["items"][0]["recommended"]


def test_watch_tasks_and_overview():
    conn = make_conn()
    tasks = queries.watch_tasks(conn)["tasks"]
    by_name = {t["task_name"]: t for t in tasks}
    assert by_name["蹲DDR4内存"]["saved_items"] == 2
    assert by_name["蹲刀卡"]["keyword_rules"] == ["半高", "刀卡"]
    overview = queries.market_overview(conn)["keywords"]
    assert len(overview) == 2
    ddr = next(o for o in overview if o["keyword"] == "DDR4 16G")
    assert ddr["total_samples"] == 3 and ddr["last_day_summary"]["min_price"] == 280.0
    assert ddr["recommended_items_saved"] == 1


def test_known_keywords_union():
    conn = make_conn()
    assert sorted(queries.known_keywords(conn)) == ["DDR4 16G", "半高显卡"]


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"ALL {len(fns)} TESTS PASSED")
