#!/usr/bin/env python3

import curses
import re
import sqlite3
from datetime import date
from pathlib import Path
from typing import Optional

# commands that take an integer index argument
_INDEX_COMMANDS = {
    "rm": "rm",
    "p": "pin", "pin": "pin",
}

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


def get_todos(conn: sqlite3.Connection) -> list:
    return conn.execute(
        "SELECT * FROM todos ORDER BY CASE status WHEN 'pinned' THEN 0 WHEN 'unchecked' THEN 1 ELSE 2 END, id"
    ).fetchall()


def set_status(conn: sqlite3.Connection, todo_id: int, status: str) -> None:
    conn.execute("UPDATE todos SET status=? WHERE id=?", (status, todo_id))
    conn.commit()


def delete_todo(conn: sqlite3.Connection, todo_id: int) -> None:
    conn.execute("DELETE FROM todos WHERE id=?", (todo_id,))
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

    # allow :p1, :rm2, etc. (no space between command and index)
    if not arg:
        m = re.match(r'^([a-z]+)(\d+)$', cmd)
        if m and m.group(1) in _INDEX_COMMANDS:
            cmd, arg = m.group(1), m.group(2)

    if cmd == "q":
        return {"action": "quit"}

    if cmd in ("a", "add"):
        if not arg:
            return {"action": "error", "message": f"usage: {cmd} <text>"}
        return {"action": "add", "text": arg}

    if cmd in _INDEX_COMMANDS:
        try:
            return {"action": _INDEX_COMMANDS[cmd], "index": int(arg)}
        except ValueError:
            return {"action": "error", "message": f"usage: {cmd} <id>"}

    return {"action": "error", "message": "unknown command"}


class App:
    def __init__(self, stdscr: "curses.window") -> None:
        self.stdscr = stdscr
        self.db = open_db()
        self.cursor = 0
        self.mode = "normal"
        self.command_buf = ""
        self.error = ""
        self._frame = 0
        self._confirm_delete: Optional[tuple] = None  # (todo_id, text)

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
        phase = (self._frame // 2 + char_pos * 2) % (len(wave_colors) * 3)
        color_idx = wave_colors[phase % len(wave_colors)]
        pair_num = 20 + (phase % len(wave_colors))
        curses.init_pair(pair_num, color_idx, -1)
        return curses.color_pair(pair_num)

    def _draw_separator(self, row: int, char: str = "─") -> None:
        _, w = self.stdscr.getmaxyx()
        self.stdscr.addstr(row, 0, char * (w - 1), curses.A_DIM)

    def _draw_item(self, screen_row: int, index: int, item: dict, selected: bool) -> None:
        h, w = self.stdscr.getmaxyx()
        if screen_row >= h - 1:
            return

        status = item["status"]
        text = item["text"]
        date_str = item["created_at"]

        # index column (3 chars wide, right-aligned)
        idx_str = f"{index:>3}"
        if status == "pinned":
            for i, ch in enumerate(idx_str):
                self.stdscr.addstr(screen_row, i, ch, self._wave_color(i))
        else:
            self.stdscr.addstr(screen_row, 0, idx_str, curses.A_DIM)

        # spaces before bracket drawn separately so cursor highlight covers only [ ] / [X]
        self.stdscr.addstr(screen_row, 4, "  ", curses.A_NORMAL)
        bracket = "[X]" if status == "checked" else "[ ]"
        color = {
            "pinned": curses.color_pair(2),
            "checked": curses.color_pair(1),
        }.get(status, curses.A_DIM)
        bracket_attr = color | curses.A_REVERSE if selected else color
        self.stdscr.addstr(screen_row, 6, bracket, bracket_attr)
        self.stdscr.addstr(screen_row, 9, "  ", curses.A_NORMAL)

        # text column starts at col 11
        text_col = 11
        max_text = w - text_col - 14
        if status == "pinned":
            for i, ch in enumerate(text):
                if text_col + i >= w - 1:
                    break
                self.stdscr.addstr(screen_row, text_col + i, ch, self._wave_color(i))
        elif status == "checked":
            self.stdscr.addstr(screen_row, text_col, text[:max_text], curses.color_pair(1) | curses.A_DIM)
        else:
            self.stdscr.addstr(screen_row, text_col, text[:max_text], curses.A_NORMAL)

        date_str_formatted = f"│  {date_str}"
        date_col = w - len(date_str_formatted) - 1
        if date_col > text_col + len(text):
            self.stdscr.addstr(screen_row, date_col, date_str_formatted, curses.A_DIM)

    def draw(self) -> None:
        self.stdscr.erase()
        h, _ = self.stdscr.getmaxyx()

        items = self._load_items()
        pinned = [r for r in items if r["status"] == "pinned"]
        unchecked = [r for r in items if r["status"] == "unchecked"]
        checked = [r for r in items if r["status"] == "checked"]

        row = 0
        self.stdscr.addstr(row, 2, "TODO", curses.A_DIM)
        row += 2

        nav_index = 1

        for item in pinned:
            self._draw_item(row, nav_index, item, (nav_index - 1) == self.cursor)
            row += 1
            nav_index += 1

        if pinned and unchecked:
            self._draw_separator(row, "╌")
            row += 1

        for item in unchecked:
            self._draw_item(row, nav_index, item, (nav_index - 1) == self.cursor)
            row += 1
            nav_index += 1

        if checked:
            row += 1
            self._draw_separator(row)
            row += 1
            for item in checked:
                self._draw_item(row, nav_index, item, (nav_index - 1) == self.cursor)
                row += 1
                nav_index += 1

        self._draw_statusbar()
        self.stdscr.refresh()

    def _draw_statusbar(self) -> None:
        h, _ = self.stdscr.getmaxyx()
        if self._confirm_delete:
            _, text = self._confirm_delete
            msg = f"delete '{text}'? [y/N]"
            self.stdscr.addstr(h - 1, 0, msg, curses.color_pair(3))
        elif self.mode == "command":
            self.stdscr.addstr(h - 1, 0, ":" + self.command_buf, curses.A_REVERSE)
        elif self.error:
            self.stdscr.addstr(h - 1, 0, self.error, curses.color_pair(3))

    def handle_key(self, key: int) -> bool:
        """Return False to quit."""
        if self._confirm_delete:
            if key == ord("y"):
                delete_todo(self.db, self._confirm_delete[0])
                self.cursor = max(0, self.cursor - 1)
            self._confirm_delete = None
            return True

        if self.error:
            self.error = ""

        if self.mode == "command":
            return self._handle_command_key(key)

        if key == ord(":"):
            self.mode = "command"
            self.command_buf = ""
        elif key in (curses.KEY_ENTER, 10, 13):
            items = self._load_items()
            if items:
                item = items[self.cursor]
                new_status = "unchecked" if item["status"] == "checked" else "checked"
                set_status(self.db, item["id"], new_status)
                self._move_cursor_to_next_unchecked(self._load_items())
        elif key == curses.KEY_UP:
            self.cursor = max(0, self.cursor - 1)
        elif key == curses.KEY_DOWN:
            items = self._load_items()
            self.cursor = max(0, min(len(items) - 1, self.cursor + 1))

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

        if cmd["action"] == "quit":
            return False

        if cmd["action"] == "error":
            self.error = cmd["message"]
            return True

        if cmd["action"] == "add":
            add_todo(self.db, cmd["text"])
            items = self._load_items()
            self.cursor = len(items) - 1
            return True

        items = self._load_items()

        if cmd["action"] in ("pin", "rm"):
            idx = cmd["index"] - 1
            if idx < 0 or idx >= len(items):
                self.error = f"no item {cmd['index']}"
                return True
            todo = items[idx]
            if cmd["action"] == "pin":
                pin_todo(self.db, todo["id"])
                self.cursor = 0
            else:
                self._confirm_delete = (todo["id"], todo["text"])

        return True

    def _move_cursor_to_next_unchecked(self, items: list) -> None:
        active = [i for i, it in enumerate(items) if it["status"] in ("unchecked", "pinned")]
        if not active:
            self.cursor = 0
            return
        self.cursor = next((i for i in active if i >= self.cursor), active[-1])

    def _load_items(self) -> list:
        return get_todos(self.db)

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
