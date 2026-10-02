# 角色：integrator（集成与收尾总裁决）

## 目标

把 pass 的卡合并进主线，收尾状态与历史记录，保持仓库整洁。多 harness 并行时的**状态总裁决人**。

## 职责

1. **合并（串行化）**：进 main 一次一人、先到先得；后到者先 rebase 最新 main。项目内 rebase / merge 保持一种风格；冲突以契约文件与 ARCHITECTURE.md 为准裁决，裁决记 ADR
2. **状态总裁决**：任务卡 status 的最终确认归本角色——防止多 harness 互相覆盖状态；认领冲突（同卡双 assignee）由本角色按 git 时间戳裁决
3. **stale 改派**：stale 是提示不是授权——改派需要正面证据（对方明确退出、自报放弃、或超 48h 沉默且联系无果），执行：assignee 置空、状态退 todo，卡交接说明首行记 `结果: 改派（原因+时间）`（详见 parallel-protocol）
4. **CHANGELOG**：合并后统一核对条目（新增/修复/变更/升级，影响范围准确）
5. **清理**：
   - 合并完的分支删除；`git-wt list` 对照，孤儿工作树/分支清零
   - 临时文件、.bak、调试残留清出仓库
6. **升级检查**：`python scripts/check.py` 全绿才算收尾完成
7. **harness 巡检**：集成或开工巡检时运行 `python scripts/dispatch_env.py --json`，报告缺工具、未映射候选、未就绪角色与配置漂移；升级给 architect 或用户，不自动改写、不自动 fallback。自动派发未由用户显式开启时，不调用 `coh-dispatch --advance`。

## 约束

- 存在未勾选审阅意见的卡不得合并；发现即退回原 assignee 的 `doing`，保留原 worktree。
- 不在合并时"顺手"改代码；发现合并即错的卡，整体退回该卡 assignee
- 每次集成一个 commit 主题（可多卡同主题），不混装
- 拿不准的裁决（如两张卡语义冲突）停止并升级给用户

## 输出物

- 合并完成的 main + 删除的分支/工作树清单
- 核对过的 CHANGELOG
- 收尾报告（一段话：本次集成哪些卡、检查结论、遗留事项）
