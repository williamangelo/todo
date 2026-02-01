#!/usr/bin/env python3
"""A simple CLI todo application that stores items in a markdown file."""

import argparse
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

TODO_FILE = Path(os.environ.get("TODO_CLI_FILE", Path.home() / ".todo.md"))
ARCHIVE_FILE = Path(os.environ.get("TODO_CLI_ARCHIVE_FILE", Path.home() / ".todo-archive.md"))


def load_todos():
    """Load todo items from the markdown file."""
    if not TODO_FILE.exists():
        return []

    todos = []
    with open(TODO_FILE, "r") as f:
        for line in f:
            match = re.match(r"^- \[([ x])\] (\d{4}-\d{2}-\d{2}) (.+)$", line.rstrip())
            if match:
                checked = match.group(1) == "x"
                timestamp = match.group(2)
                text = match.group(3)
                todos.append({"checked": checked, "timestamp": timestamp, "text": text})
    return todos


def save_todos(todos):
    """Save todo items to the markdown file."""
    unchecked = sorted([t for t in todos if not t["checked"]], key=lambda t: t["timestamp"])
    checked = [t for t in todos if t["checked"]]  # Keep insertion order
    with open(TODO_FILE, "w") as f:
        for todo in unchecked + checked:
            checkbox = "x" if todo["checked"] else " "
            f.write(f"- [{checkbox}] {todo['timestamp']} {todo['text']}\n")


def add_todo(note):
    """Add a new todo item."""
    todos = load_todos()
    timestamp = datetime.now().strftime("%Y-%m-%d")
    todos.append({"checked": False, "timestamp": timestamp, "text": note})
    save_todos(todos)
    print(f"Added: {note}")


def get_week_start(date_str):
    """Get the Monday of the week for a given date string."""
    date = datetime.strptime(date_str, "%Y-%m-%d")
    monday = date - timedelta(days=date.weekday())
    return monday.strftime("%Y-%m-%d")


def group_by_date(todos):
    """Group todos by date."""
    groups = {}
    for todo in todos:
        key = todo["timestamp"]
        if key not in groups:
            groups[key] = []
        groups[key].append(todo)
    return groups


def group_by_week(todos):
    """Group todos by week (starting Monday)."""
    groups = {}
    for todo in todos:
        key = get_week_start(todo["timestamp"])
        if key not in groups:
            groups[key] = []
        groups[key].append(todo)
    return groups


def list_todos(daily=False, weekly=False, show_archive=False):
    """List all todo items."""
    if show_archive:
        todos = load_archive()
        if not todos:
            print("No archived items.")
            return
        for todo in todos:
            print(f"   [x] {todo['timestamp']} {todo['text']}")
        return

    todos = load_todos()
    if not todos:
        print("No todo items.")
        return

    unchecked = [t for t in todos if not t["checked"]]
    checked = [t for t in todos if t["checked"]]

    if daily or weekly:
        group_fn = group_by_week if weekly else group_by_date
        label = "Week of " if weekly else ""

        # Group unchecked items
        unchecked_groups = group_fn(unchecked)
        idx = 1
        for date_key in sorted(unchecked_groups.keys(), reverse=True):
            print(f"{label}{date_key}")
            for todo in unchecked_groups[date_key]:
                print(f"  {idx}. [ ] {todo['text']}")
                idx += 1
            print()

        # Group checked items under "Completed" header
        if checked:
            print("Completed")
            checked_groups = group_fn(checked)
            for date_key in sorted(checked_groups.keys(), reverse=True):
                print(f"  {label}{date_key}")
                for todo in checked_groups[date_key]:
                    print(f"    [x] {todo['text']}")
            print()
    else:
        # Original flat display
        for i, todo in enumerate(unchecked, 1):
            print(f"{i}. [ ] {todo['timestamp']} {todo['text']}")
        if unchecked and checked:
            print()
        for todo in checked:
            print(f"   [x] {todo['timestamp']} {todo['text']}")


def check_todo(index):
    """Mark a todo item as complete."""
    todos = load_todos()
    unchecked = [t for t in todos if not t["checked"]]
    checked = [t for t in todos if t["checked"]]

    if not unchecked:
        print("No unchecked items.", file=sys.stderr)
        sys.exit(1)

    if index < 1 or index > len(unchecked):
        print(f"Invalid index: {index}. Must be between 1 and {len(unchecked)}.", file=sys.stderr)
        sys.exit(1)

    item = unchecked.pop(index - 1)
    item["checked"] = True
    checked.insert(0, item)  # Push to top of checked stack
    save_todos(unchecked + checked)
    print(f"Checked: {item['text']}")


def rm_todo(index):
    """Remove an unchecked todo item."""
    todos = load_todos()
    unchecked = [t for t in todos if not t["checked"]]
    checked = [t for t in todos if t["checked"]]

    if not unchecked:
        print("No unchecked items.", file=sys.stderr)
        sys.exit(1)

    if index < 1 or index > len(unchecked):
        print(f"Invalid index: {index}. Must be between 1 and {len(unchecked)}.", file=sys.stderr)
        sys.exit(1)

    item = unchecked.pop(index - 1)
    save_todos(unchecked + checked)
    print(f"Removed: {item['text']}")


def uncheck_todo(index):
    """Move a completed item back to unchecked."""
    todos = load_todos()
    unchecked = [t for t in todos if not t["checked"]]
    checked = [t for t in todos if t["checked"]]

    if not checked:
        print("No checked items.", file=sys.stderr)
        sys.exit(1)

    if index < 1 or index > len(checked):
        print(f"Invalid index: {index}. Must be between 1 and {len(checked)}.", file=sys.stderr)
        sys.exit(1)

    item = checked.pop(index - 1)
    item["checked"] = False
    unchecked.append(item)
    save_todos(unchecked + checked)
    print(f"Unchecked: {item['text']}")


def archive_todos():
    """Move all completed items to the archive file."""
    todos = load_todos()
    unchecked = [t for t in todos if not t["checked"]]
    checked = [t for t in todos if t["checked"]]

    if not checked:
        print("No completed items to archive.")
        return

    with open(ARCHIVE_FILE, "a") as f:
        for todo in checked:
            f.write(f"- [x] {todo['timestamp']} {todo['text']}\n")

    save_todos(unchecked)
    print(f"Archived {len(checked)} item{'s' if len(checked) != 1 else ''}.")


def load_archive():
    """Load archived todo items."""
    if not ARCHIVE_FILE.exists():
        return []

    todos = []
    with open(ARCHIVE_FILE, "r") as f:
        for line in f:
            match = re.match(r"^- \[x\] (\d{4}-\d{2}-\d{2}) (.+)$", line.rstrip())
            if match:
                timestamp = match.group(1)
                text = match.group(2)
                todos.append({"checked": True, "timestamp": timestamp, "text": text})
    return todos


def main():
    parser = argparse.ArgumentParser(description="A simple todo CLI application")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # add command
    add_parser = subparsers.add_parser("add", help="Add a new todo item")
    add_parser.add_argument("note", help="The todo item text")

    # list command
    list_parser = subparsers.add_parser("list", help="List all todo items")
    list_parser.add_argument("-d", "--daily", action="store_true", help="Group items by date")
    list_parser.add_argument("-w", "--weekly", action="store_true", help="Group items by week")
    list_parser.add_argument("--archive", action="store_true", help="Show archived items")

    # check command
    check_parser = subparsers.add_parser("check", help="Mark a todo item as complete")
    check_parser.add_argument("index", type=int, help="The index of the item to check (1-based)")

    # rm command
    rm_parser = subparsers.add_parser("rm", help="Remove an unchecked todo item")
    rm_parser.add_argument("index", type=int, help="The index of the item to remove (1-based)")

    # uncheck command
    uncheck_parser = subparsers.add_parser("uncheck", help="Move a completed item back to unchecked")
    uncheck_parser.add_argument("index", type=int, help="The index of the completed item (1-based)")

    # archive command
    subparsers.add_parser("archive", help="Move all completed items to archive")

    args = parser.parse_args()

    if args.command == "add":
        add_todo(args.note)
    elif args.command == "list":
        list_todos(daily=args.daily, weekly=args.weekly, show_archive=args.archive)
    elif args.command == "check":
        check_todo(args.index)
    elif args.command == "rm":
        rm_todo(args.index)
    elif args.command == "uncheck":
        uncheck_todo(args.index)
    elif args.command == "archive":
        archive_todos()


if __name__ == "__main__":
    main()
