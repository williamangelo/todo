#!/usr/bin/env python3
"""TUI todo application backed by SQLite."""

import curses
import sqlite3
import time
from datetime import date
from pathlib import Path
from typing import Optional

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


class App:
    def __init__(self, stdscr: "curses.window") -> None:
        self.stdscr = stdscr
        self.db = open_db()
        self.cursor = 0
        self.show_scratched = False
        self.mode = "normal"
        self.command_buf = ""
        self.error = ""
        self._frame = 0

        curses.start_color()
        curses.use_default_colors()
        curses.curs_set(0)
        self._init_colors()

    def _init_colors(self) -> None:
        # color pair indices
        # 1: dim (gray)      2: normal text     3: selected bg
        # 4: checked bracket 5: checked text    6: pinned bracket
        # 7: error           8: scratched
        curses.init_pair(1, 240, -1)   # dark gray
        curses.init_pair(2, 252, -1)   # light gray
        curses.init_pair(3, 252, 22)   # light text, dark green bg
        curses.init_pair(4, 71, -1)    # muted green (checked bracket)
        curses.init_pair(5, 65, -1)    # darker green (checked text)
        curses.init_pair(6, 214, -1)   # amber (pinned bracket)
        curses.init_pair(7, 196, -1)   # red (error)
        curses.init_pair(8, 236, -1)   # very dark gray (scratched)

    def draw(self) -> None:
        self.stdscr.erase()
        self.stdscr.addstr(0, 2, "TODO", curses.color_pair(1))
        self._draw_statusbar()
        self.stdscr.refresh()

    def _draw_statusbar(self) -> None:
        h, w = self.stdscr.getmaxyx()
        if self.mode == "command":
            bar = ":" + self.command_buf
            self.stdscr.addstr(h - 1, 0, bar, curses.color_pair(2))
        elif self.error:
            self.stdscr.addstr(h - 1, 0, self.error, curses.color_pair(7))
        else:
            status = "NORMAL"
            if self.show_scratched:
                status += "  s"
            self.stdscr.addstr(h - 1, 0, status, curses.color_pair(1))

    def handle_key(self, key: int) -> bool:
        """Return False to quit."""
        if self.error:
            self.error = ""

        if self.mode == "command":
            return self._handle_command_key(key)

        if key == ord(":"):
            self.mode = "command"
            self.command_buf = ""
        elif key == ord("s"):
            self.show_scratched = not self.show_scratched
            self.cursor = 0
        elif key == curses.KEY_UP:
            self.cursor = max(0, self.cursor - 1)
        elif key == curses.KEY_DOWN:
            items = self._load_items()
            nav = navigable_items(items)
            self.cursor = min(len(nav) - 1, self.cursor + 1)

        return True

    def _handle_command_key(self, key: int) -> bool:
        if key == 27:  # Esc
            self.mode = "normal"
            self.command_buf = ""
        elif key in (curses.KEY_ENTER, 10, 13):
            result = self._execute_command(self.command_buf)
            self.mode = "normal"
            self.command_buf = ""
            if not result:
                return False
        elif key in (curses.KEY_BACKSPACE, 127):
            self.command_buf = self.command_buf[:-1]
        elif 32 <= key <= 126:
            self.command_buf += chr(key)
        return True

    def _execute_command(self, buf: str) -> bool:
        """Return False to quit."""
        cmd = parse_command(buf)
        items = self._load_items()
        nav = navigable_items(items)

        if cmd["action"] == "quit":
            return False

        if cmd["action"] == "error":
            self.error = cmd["message"]
            return True

        if cmd["action"] == "add":
            add_todo(self.db, cmd["text"])
            items = self._load_items()
            nav = navigable_items(items)
            self.cursor = len(nav) - 1
            return True

        if cmd["action"] in ("check", "scratch", "pin"):
            idx = cmd["index"] - 1
            if idx < 0 or idx >= len(nav):
                self.error = f"no item {cmd['index']}"
                return True
            todo_id = nav[idx]["id"]
            if cmd["action"] == "check":
                set_status(self.db, todo_id, "checked")
                self.cursor = min(self.cursor, max(0, len(nav) - 2))
            elif cmd["action"] == "scratch":
                set_status(self.db, todo_id, "scratched")
                self.cursor = min(self.cursor, max(0, len(nav) - 2))
            elif cmd["action"] == "pin":
                pin_todo(self.db, todo_id)
                self.cursor = 0
            return True

        return True

    def _load_items(self) -> list:
        return get_todos(self.db, include_scratched=self.show_scratched)

    def run(self) -> None:
        self.stdscr.timeout(100)
        while True:
            self._frame += 1
            self.draw()
            key = self.stdscr.getch()
            if key == -1:
                continue
            if not self.handle_key(key):
                break


def main() -> None:
    curses.wrapper(lambda stdscr: App(stdscr).run())


if __name__ == "__main__":
    main()
