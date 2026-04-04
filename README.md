# todo

A TUI todo app. Single file, standard lib only. Navigate items with arrow keys and manage them via vim-style commands prefixed with `:`

- `:a / :add <text>` — Add item
- `:p / :pin <item index>` — Pin item to the top and animate it with amber→red gradient
- `:rm <item index>` — Remove item (requires confirmation)
- `:q` — Quit

All data persists to a SQLite database in `~/.todo/todo.db.`

![alt text](tui-screenshot.png)
