# dispatch — 启动命令表（角色 → 启动命令）

`coh-dispatch` 按候选卡的 `allowed_paths` 推出角色，再来这里取启动命令；拉起后立刻失联
（不读子进程输出、不记运行时状态）。命令里的 `{worktree}` / `{card}` 在拉起前替换成工作树
绝对路径与卡号。**缺这张表时 dispatch 只列候选、不执行**，并响亮提示缺表。

自动派发：关闭（默认；用户明确要求 architect 或 integrator “开启自动派发/关闭自动派发”后，
由该角色更新本行。候选可用不等于自动派发已开启，角色不得自行推断。）

**骨架不预置任何 harness 名称、可执行文件路径或本机环境位置。** 装机后由 architect 按本机
PATH 探测，或按用户明确指定的工具名填写下表；新 harness 是否承担某角色必须走规则卡/ADR，
不自动映射。工具不在 PATH 时面板标灰、强行派发响亮失败。一个角色一行；同一角色写重复时
后写的生效。

| 角色 | 启动命令 |
|---|---|
| pm | `<harness-cli> --cd {worktree}` |
| architect | `<harness-cli> --cd {worktree}` |
| coder | `<harness-cli> --cd {worktree}` |
| doc-writer | `<harness-cli> --cd {worktree}` |
| reviewer | `<harness-cli> --cd {worktree}` |
| tester | `<harness-cli> --cd {worktree}` |
| integrator | `<harness-cli> --cd {worktree}` |

## 候选 harness（只读探测）

候选清单是项目侧的环境事实，不是骨架默认值。architect 在本机探测后或用户明确指定后填写；
`scripts/dispatch_env.py` 只读检查 PATH 上的命令名，不执行候选 CLI、不联网、不自动改映射。
未填写时脚本明确报“未配置”，不会静默 fallback。

```json
{"harnesses": []}
```
