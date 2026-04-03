#!/usr/bin/env python3
"""TUI todo application backed by SQLite."""

import curses
import sqlite3
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
    # all visible items are navigable; get_todos already orders and filters them
    return list(items)


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
        # all pairs use -1 (terminal default bg) so the theme adapts to the user's terminal
        curses.init_pair(1, curses.COLOR_GREEN, -1)   # checked
        curses.init_pair(2, curses.COLOR_YELLOW, -1)  # pinned bracket
        curses.init_pair(3, curses.COLOR_RED, -1)     # error

    def _wave_color(self, char_pos: int) -> int:
        # 256-color amber→red→amber wave. returns a curses color pair.
        # pairs 20+ reserved for wave colors to avoid clashing with pairs 1-8
        wave_colors = [214, 208, 202, 196, 202, 208]  # amber→red→amber
        phase = (self._frame + char_pos * 2) % (len(wave_colors) * 3)
        color_idx = wave_colors[phase % len(wave_colors)]
        pair_num = 20 + (phase % len(wave_colors))
        curses.init_pair(pair_num, color_idx, -1)
        return curses.color_pair(pair_num)

    def _draw_separator(self, row: int) -> None:
        _, w = self.stdscr.getmaxyx()
        self.stdscr.addstr(row, 0, "─" * (w - 1), curses.A_DIM)

    def _draw_item(self, screen_row: int, index: Optional[int], item: dict, width: int, selected: bool) -> None:
        h, w = self.stdscr.getmaxyx()
        if screen_row >= h - 1:
            return

        status = item["status"]
        text = item["text"]
        date_str = item["created_at"]

        # index column (3 chars wide, right-aligned)
        idx_str = f"{index:>3}" if index is not None else "   "
        self.stdscr.addstr(screen_row, 0, idx_str, curses.A_DIM)

        # spaces before bracket drawn separately so cursor highlight covers only [ ] / [X]
        self.stdscr.addstr(screen_row, 4, "  ", curses.A_NORMAL)
        if status == "pinned":
            bracket = "[ ]"
            bracket_attr = curses.color_pair(2) | curses.A_REVERSE if selected else curses.color_pair(2)
        elif status == "checked":
            bracket = "[X]"
            bracket_attr = curses.color_pair(1) | curses.A_REVERSE if selected else curses.color_pair(1)
        else:
            bracket = "[ ]"
            bracket_attr = curses.A_REVERSE if selected else curses.A_DIM
        self.stdscr.addstr(screen_row, 6, bracket, bracket_attr)
        self.stdscr.addstr(screen_row, 9, "  ", curses.A_NORMAL)

        # text column starts at col 11
        text_col = 11
        max_text = w - text_col - 14
        if status == "pinned":
            for i, ch in enumerate(text):
                if text_col + i >= w - 1:
                    break
                wave = self._wave_color(i) | (curses.A_DIM if selected else curses.A_NORMAL)
                self.stdscr.addstr(screen_row, text_col + i, ch, wave)
        elif status == "checked":
            self.stdscr.addstr(screen_row, text_col, text[:max_text], curses.color_pair(1) | curses.A_DIM)
        elif status == "scratched":
            # curses has no strikethrough — render dim
            self.stdscr.addstr(screen_row, text_col, text[:max_text], curses.A_DIM)
        else:
            self.stdscr.addstr(screen_row, text_col, text[:max_text], curses.A_NORMAL)

        # date pinned immediately after the item's own text
        date_col = text_col + len(text) + 2
        date_str_formatted = f"│  {date_str}"
        if date_col + len(date_str_formatted) < w:
            self.stdscr.addstr(screen_row, date_col, date_str_formatted, curses.A_DIM)

    def draw(self) -> None:
        self.stdscr.erase()
        h, _ = self.stdscr.getmaxyx()

        items = self._load_items()
        nav = navigable_items(items)
        pinned = [r for r in items if r["status"] == "pinned"]
        unchecked = [r for r in items if r["status"] == "unchecked"]
        checked = [r for r in items if r["status"] == "checked"]
        scratched = [r for r in items if r["status"] == "scratched"]

        width = col_width(items)

        row = 0
        self.stdscr.addstr(row, 2, "TODO", curses.A_DIM)
        row += 2

        # display index counter (1-based, covers pinned + unchecked)
        nav_index = 1

        # pinned section
        for item in pinned:
            selected = (nav_index - 1) == self.cursor
            self._draw_item(row, nav_index, item, width, selected)
            row += 1
            nav_index += 1

        if pinned and unchecked:
            self._draw_separator(row)
            row += 1

        # unchecked section
        for item in unchecked:
            selected = (nav_index - 1) == self.cursor
            self._draw_item(row, nav_index, item, width, selected)
            row += 1
            nav_index += 1

        # checked section
        if checked:
            self._draw_separator(row)
            row += 1
            for item in checked:
                selected = (nav_index - 1) == self.cursor
                self._draw_item(row, nav_index, item, width, selected)
                row += 1
                nav_index += 1

        # scratched section (only when show_scratched is True)
        if self.show_scratched and scratched:
            self._draw_separator(row)
            row += 1
            for item in scratched:
                selected = (nav_index - 1) == self.cursor
                self._draw_item(row, nav_index, item, width, selected)
                row += 1
                nav_index += 1

        self._draw_statusbar()
        self.stdscr.refresh()

    def _draw_statusbar(self) -> None:
        h, w = self.stdscr.getmaxyx()
        if self.mode == "command":
            bar = ":" + self.command_buf
            self.stdscr.addstr(h - 1, 0, bar, curses.A_NORMAL)
        elif self.error:
            self.stdscr.addstr(h - 1, 0, self.error, curses.color_pair(3))
        else:
            status = "NORMAL"
            if self.show_scratched:
                status += "  s"
            self.stdscr.addstr(h - 1, 0, status, curses.A_DIM)

    def handle_key(self, key: int) -> bool:
        """Return False to quit."""
        if self.error:
            self.error = ""

        if self.mode == "command":
            return self._handle_command_key(key)

        if key == ord(":"):
            self.mode = "command"
            self.command_buf = ""
        elif key in (curses.KEY_ENTER, 10, 13):
            items = self._load_items()
            nav = navigable_items(items)
            if nav:
                item = nav[self.cursor]
                new_status = "unchecked" if item["status"] == "checked" else "checked"
                set_status(self.db, item["id"], new_status)
                self.cursor = min(self.cursor, max(0, len(nav) - 2))
        elif key == ord("s"):
            self.show_scratched = not self.show_scratched
            self.cursor = 0
        elif key == curses.KEY_UP:
            self.cursor = max(0, self.cursor - 1)
        elif key == curses.KEY_DOWN:
            items = self._load_items()
            nav = navigable_items(items)
            self.cursor = max(0, min(len(nav) - 1, self.cursor + 1))

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
                new_status = "unchecked" if nav[idx]["status"] == "checked" else "checked"
                set_status(self.db, todo_id, new_status)
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
