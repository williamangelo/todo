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


def test_get_todos_order(db):
    todo_cli.add_todo(db, "normal")
    todo_cli.add_todo(db, "pinned")
    db.execute("UPDATE todos SET status='pinned' WHERE text='pinned'")
    rows = todo_cli.get_todos(db)
    assert rows[0]["text"] == "pinned"
    assert rows[1]["text"] == "normal"


def test_delete_todo(db):
    todo_cli.add_todo(db, "to remove")
    row = db.execute("SELECT id FROM todos").fetchone()
    todo_cli.delete_todo(db, row["id"])
    assert db.execute("SELECT count(*) FROM todos").fetchone()[0] == 0


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
