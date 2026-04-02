import todo_cli
from datetime import date


def test_init_db_creates_table(db):
    cur = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='todos'")
    assert cur.fetchone() is not None


def test_add_todo(db):
    todo_cli.add_todo(db, "buy milk")
    rows = db.execute("SELECT * FROM todos").fetchall()
    assert len(rows) == 1
    assert rows[0]["text"] == "buy milk"
    assert rows[0]["status"] == "unchecked"
    assert rows[0]["created_at"] == date.today().strftime("%Y-%m-%d")


def test_get_todos_excludes_scratched_by_default(db):
    todo_cli.add_todo(db, "visible")
    todo_cli.add_todo(db, "hidden")
    db.execute("UPDATE todos SET status='scratched' WHERE text='hidden'")
    rows = todo_cli.get_todos(db, include_scratched=False)
    assert len(rows) == 1
    assert rows[0]["text"] == "visible"


def test_get_todos_includes_scratched_when_requested(db):
    todo_cli.add_todo(db, "visible")
    todo_cli.add_todo(db, "hidden")
    db.execute("UPDATE todos SET status='scratched' WHERE text='hidden'")
    rows = todo_cli.get_todos(db, include_scratched=True)
    assert len(rows) == 2


def test_set_status(db):
    todo_cli.add_todo(db, "task")
    row = db.execute("SELECT id FROM todos").fetchone()
    todo_cli.set_status(db, row["id"], "checked")
    updated = db.execute("SELECT status FROM todos WHERE id=?", (row["id"],)).fetchone()
    assert updated["status"] == "checked"


def test_pin_unpins_previous(db):
    todo_cli.add_todo(db, "first")
    todo_cli.add_todo(db, "second")
    ids = [r["id"] for r in db.execute("SELECT id FROM todos ORDER BY id").fetchall()]
    todo_cli.pin_todo(db, ids[0])
    todo_cli.pin_todo(db, ids[1])
    statuses = {r["id"]: r["status"] for r in db.execute("SELECT id, status FROM todos").fetchall()}
    assert statuses[ids[0]] == "unchecked"
    assert statuses[ids[1]] == "pinned"
