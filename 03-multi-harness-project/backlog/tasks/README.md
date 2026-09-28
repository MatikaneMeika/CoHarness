# backlog/tasks — 任务卡目录

卡片由 Backlog.md 管理，格式与写法子集见 `.agent/tasks/CARD-CONVENTION.md`。
认领与状态流转的提交直接进 main，卡片文件属**自授权改动**（不需要被某张卡的 allowed_paths 覆盖）。

## 命名约定（真工具按这个认卡）

Backlog.md 1.53.0 读写的是 `t-<编号> - <标题>.md`（如 `t-1 - 登录接口.md`），
`backlog task list` 只认这种文件名。**手工建的 `T-001.md` 工具看不见**——
执法（`scripts/check.py`）读得到它，看板 CLI 不会列它。两条路都合法，但别混着用：

- 装了 backlog：一律 `backlog task create "标题"`，卡片名交给工具
- 没装 backlog：手工按 CARD-CONVENTION 建 `T-<编号>.md`，`check.py` 照常执法

新增卡：`backlog task create "标题" -s todo`；改状态/认领：`backlog task edit T-1 -a <标识> -s doing`
（前提：`backlog/config.yml` 的 `statuses` 已改成 `todo/doing/review/done`，工具默认是英文三列）。
