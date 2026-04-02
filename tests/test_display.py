import todo_cli


def _row(text, status="unchecked"):
    # minimal sqlite3.Row stand-in as a dict
    return {"text": text, "status": status, "created_at": "2026-01-01", "id": 1}


def test_col_width_single_item():
    items = [_row("buy milk")]
    assert todo_cli.col_width(items) == len("buy milk")


def test_col_width_longest_wins():
    items = [_row("short"), _row("much longer text")]
    assert todo_cli.col_width(items) == len("much longer text")


def test_col_width_empty():
    assert todo_cli.col_width([]) == 0


def test_navigable_items_excludes_checked_and_scratched():
    items = [
        _row("pinned", "pinned"),
        _row("unchecked", "unchecked"),
        _row("checked", "checked"),
        _row("scratched", "scratched"),
    ]
    nav = todo_cli.navigable_items(items)
    assert len(nav) == 2
    assert all(r["status"] in ("pinned", "unchecked") for r in nav)


def test_navigable_items_pinned_first():
    items = [
        _row("unchecked", "unchecked"),
        _row("pinned", "pinned"),
    ]
    nav = todo_cli.navigable_items(items)
    assert nav[0]["status"] == "pinned"
