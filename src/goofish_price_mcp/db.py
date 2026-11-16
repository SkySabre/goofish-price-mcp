"""SQLite connection helpers for the ai-goofish-monitor database (read-only)."""

import os
import sqlite3
from pathlib import Path
from urllib.parse import quote

ENV_VAR = "GOOFISH_DB_PATH"
DEFAULT_CANDIDATES = (
    "data/app.sqlite3",
    "/app/data/app.sqlite3",
    "~/.ai-goofish/data/app.sqlite3",
)


def resolve_db_path() -> str:
    explicit = os.environ.get(ENV_VAR, "").strip()
    if explicit:
        path = Path(explicit).expanduser()
        if not path.is_file():
            raise FileNotFoundError(
                f"{ENV_VAR}={explicit} 指定的数据库不存在。"
                " 请指向 ai-goofish-monitor 项目的 data/app.sqlite3。"
            )
        return str(path.resolve())
    for candidate in DEFAULT_CANDIDATES:
        path = Path(candidate).expanduser()
        if path.is_file():
            return str(path.resolve())
    tried = " / ".join(DEFAULT_CANDIDATES)
    raise FileNotFoundError(
        f"未找到闲鱼监控数据库。已尝试: {tried}；"
        f"或设置环境变量 {ENV_VAR} 指向 ai-goofish-monitor 的 data/app.sqlite3。"
    )


def open_readonly(db_path: str | None = None) -> sqlite3.Connection:
    path = db_path or resolve_db_path()
    uri = "file://" + quote(str(Path(path).absolute())) + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=2.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=2000")
    return conn
