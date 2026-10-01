# dispatch — 启动命令表（角色 → 启动命令）

`coh-dispatch` 按候选卡的 `allowed_paths` 推出角色，再来这里取启动命令；拉起后立刻失联
（不读子进程输出、不记运行时状态）。命令里的 `{worktree}` / `{card}` 在拉起前替换成工作树
绝对路径与卡号。**缺这张表时 dispatch 只列候选、不执行**，并响亮提示缺表。

装机后把下面的命令换成你实际用的 CLI（工具不在 PATH 时面板标灰、强行派发响亮失败）。
一个角色一行；同一角色写重复时后写的生效。

| 角色 | 启动命令 |
|---|---|
| pm | `codex --cd {worktree}` |
| architect | `codex --cd {worktree}` |
| coder | `codex --cd {worktree}` |
| doc-writer | `codex --cd {worktree}` |
| reviewer | `codex --cd {worktree}` |
| tester | `codex --cd {worktree}` |
| integrator | `codex --cd {worktree}` |
