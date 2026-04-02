#!/usr/bin/env python3
"""TUI todo application backed by SQLite."""

import sqlite3
from datetime import date
from pathlib import Path

DB_DIR = Path.home() / ".todo"
DB_PATH = DB_DIR / "todo.db"


def open_db() -> sqlite3.Connection:
    DB_DIR.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS todos (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            text       TEXT NOT NULL,
            status     TEXT NOT NULL DEFAULT 'unchecked',
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()


def add_todo(conn: sqlite3.Connection, text: str) -> int:
    cur = conn.execute(
        "INSERT INTO todos (text, status, created_at) VALUES (?, 'unchecked', ?)",
        (text, date.today().strftime("%Y-%m-%d")),
    )
    conn.commit()
    return cur.lastrowid


def get_todos(conn: sqlite3.Connection, include_scratched: bool = False) -> list:
    if include_scratched:
        return conn.execute(
            "SELECT * FROM todos ORDER BY CASE status WHEN 'pinned' THEN 0 WHEN 'unchecked' THEN 1 WHEN 'checked' THEN 2 ELSE 3 END, id"
        ).fetchall()
    return conn.execute(
        "SELECT * FROM todos WHERE status != 'scratched' ORDER BY CASE status WHEN 'pinned' THEN 0 WHEN 'unchecked' THEN 1 ELSE 2 END, id"
    ).fetchall()


def set_status(conn: sqlite3.Connection, todo_id: int, status: str) -> None:
    conn.execute("UPDATE todos SET status=? WHERE id=?", (status, todo_id))
    conn.commit()


def pin_todo(conn: sqlite3.Connection, todo_id: int) -> None:
    conn.execute("UPDATE todos SET status='unchecked' WHERE status='pinned'")
    conn.execute("UPDATE todos SET status='pinned' WHERE id=?", (todo_id,))
    conn.commit()


def parse_command(buf: str) -> dict:
    parts = buf.strip().split(None, 1)
    if not parts:
        return {"action": "error", "message": "empty command"}
    cmd = parts[0]
    arg = parts[1] if len(parts) > 1 else ""

    if cmd == "q":
        return {"action": "quit"}

    if cmd in ("a", "add"):
        if not arg:
            return {"action": "error", "message": f"usage: {cmd} <text>"}
        return {"action": "add", "text": arg}

    if cmd in ("c", "check"):
        try:
            return {"action": "check", "index": int(arg)}
        except ValueError:
            return {"action": "error", "message": f"usage: {cmd} <id>"}

    if cmd in ("s", "scratch"):
        try:
            return {"action": "scratch", "index": int(arg)}
        except ValueError:
            return {"action": "error", "message": f"usage: {cmd} <id>"}

    if cmd in ("p", "pin"):
        try:
            return {"action": "pin", "index": int(arg)}
        except ValueError:
            return {"action": "error", "message": f"usage: {cmd} <id>"}

    return {"action": "error", "message": "unknown command"}


def col_width(items: list) -> int:
    if not items:
        return 0
    return max(len(row["text"]) for row in items)


def navigable_items(items: list) -> list:
    pinned = [r for r in items if r["status"] == "pinned"]
    unchecked = [r for r in items if r["status"] == "unchecked"]
    return pinned + unchecked


def main() -> None:
    pass


if __name__ == "__main__":
    main()
