import sqlite3
import pytest
import todo_cli


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    todo_cli.init_db(conn)
    yield conn
    conn.close()
