import todo_cli


def test_parse_quit():
    assert todo_cli.parse_command("q") == {"action": "quit"}


def test_parse_add_short():
    assert todo_cli.parse_command("a buy milk") == {"action": "add", "text": "buy milk"}


def test_parse_add_long():
    assert todo_cli.parse_command("add buy milk") == {"action": "add", "text": "buy milk"}


def test_parse_check_short():
    assert todo_cli.parse_command("c 3") == {"action": "check", "index": 3}


def test_parse_check_long():
    assert todo_cli.parse_command("check 3") == {"action": "check", "index": 3}


def test_parse_scratch_short():
    assert todo_cli.parse_command("s 2") == {"action": "scratch", "index": 2}


def test_parse_scratch_long():
    assert todo_cli.parse_command("scratch 2") == {"action": "scratch", "index": 2}


def test_parse_pin_short():
    assert todo_cli.parse_command("p 1") == {"action": "pin", "index": 1}


def test_parse_pin_long():
    assert todo_cli.parse_command("pin 1") == {"action": "pin", "index": 1}


def test_parse_unknown():
    assert todo_cli.parse_command("foo") == {"action": "error", "message": "unknown command"}


def test_parse_check_missing_index():
    assert todo_cli.parse_command("c") == {"action": "error", "message": "usage: c <id>"}


def test_parse_check_non_integer():
    assert todo_cli.parse_command("c abc") == {"action": "error", "message": "usage: c <id>"}


def test_parse_add_missing_text():
    assert todo_cli.parse_command("a") == {"action": "error", "message": "usage: a <text>"}
