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


def test_navigable_items_returns_all_items():
    items = [
        _row("pinned", "pinned"),
        _row("unchecked", "unchecked"),
        _row("checked", "checked"),
        _row("scratched", "scratched"),
    ]
    nav = todo_cli.navigable_items(items)
    assert len(nav) == 4


def test_navigable_items_preserves_order():
    items = [
        _row("pinned", "pinned"),
        _row("unchecked", "unchecked"),
        _row("checked", "checked"),
    ]
    nav = todo_cli.navigable_items(items)
    assert [r["status"] for r in nav] == ["pinned", "unchecked", "checked"]
