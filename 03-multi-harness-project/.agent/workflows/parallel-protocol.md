# 流程：parallel-protocol v2（多 harness 并行规则）

多个 AI 工具（ZCode / Codex / Qoder / Antigravity）同时在一个仓库干活时的防冲突协议。
任务状态存于 Backlog.md（`backlog task` 命令族），工作区隔离用 Worktrunk（Windows 下命令为 `git-wt`）。

## 开工协议（每次会话开始时，顺序固定）

1. `git pull --ff-only`（在主工作树或自己的 worktree 内）——看板可能已被其他 harness 改动
2. `backlog board`（或 `backlog task list`）读看板
3. 选一张 status=todo 且 dependencies 已满足的卡
4. 认领（见下节）
5. `git-wt switch -c feat/T-xxx-<slug>` 开自己的 worktree 干活

**禁止跳过 pull 直接凭上次记忆选卡。**

## 认领（先到先得）

1. 认领动作 = `backlog task edit T-xxx -a <harness标识> -s doing` + **commit + push 到 main**
2. harness 标识 = 工具名 + 会话尾缀，如 `zcode-0926a`；一卡只允许一个 assignee
3. **认领与状态流转的提交必须直接进共享分支 main**——跟功能分支走 = 别人看不见你认领了，先到先得即失效
4. owner 冲突（两工具同时认领同一卡）：以 git 历史时间戳先者为准，后到者换卡

## 看板改动与登记怎么提交（执法现状下的绕行，非设计意图）

`backlog/` 与 `.agent/` 是每张卡 `forbidden_paths` 的默认值，而卡自身的改动、improvements 登记
都需要"挂到某张卡的 allowed_paths 上"才放行 —— 于是**认领/状态流转/登记这三类提交先要认领常驻规则卡**
`backlog/tasks/T-000-board.md`：

1. `backlog task edit T-000-board -a <你的标识> -s doing` + commit + push main（它的 allowed_paths 含 `backlog/` 与 `.agent/improvements.md`）
2. 本轮只动看板与登记表；**持它期间不要再持实现卡**（"一 harness 一张 doing 卡"是硬门禁，两张会撞 `--tasks`）
3. 提交时只 `git add` 看板/登记文件（`--diff` 判的是暂存集）
4. 收工把 T-000-board 退回 todo 并进 main，让给下一轮需要动看板的人

缺口已登记 I-001（状态：登记）。攒够第二次同类摩擦或经 evolve 审核后，把放行规则写进 check.py 本体，本卡随之删除。

## pull 时机（写死，三处）

- 开工时、认领前、push 前，各 pull 一次
- push 被拒（远端有新提交）= 有并行者动了 main，先 pull --rebase 再推

## 工作区隔离（铁律）

- **一个 harness = 一个 worktree**：`git-wt switch -c feat/T-xxx-<slug>`；两个 harness 禁止共居同一 clone
- worktree 里只做卡内的事；发现要改卡外的东西 → 停，回流程开新卡
- 任务结束必须：`git-wt merge`（或手动合并）→ `git-wt remove` 清理——`git-wt list` 只剩在跑的，无孤儿工作树/分支

## 并行前提

- 两张卡同时进行 ⟺ 两卡"## 边界"节的 `allowed_paths` **无交集**
- 有交集 → 串行，或请 pm/integrator 重新切分边界（重叠部分拆成共享前置卡）
- 规则文件（`AGENTS.md`、`.agent/` 全部）永远串行：只允许一张"规则卡"在跑

## stale（僵死卡）处理

- doing/review 卡超过 **24 小时**无新 commit（对照卡 `updated_date` 与 `git log`），即视为 stale
- integrator 有改派权：把 assignee 置空、状态退回 todo，并在卡交接说明记一行改派原因与时间
- 原 owner 回来时以看板现状为准，不恢复现场

## 合并纪律

- 进 main **一次一人**：合并动作本身串行，先到先得
- 后到者 rebase 到最新 main 再合并；冲突以契约文件与 ARCHITECTURE.md 为准裁决，裁决记 ADR
- `python scripts/check.py` 全绿才允许合入（pre-commit 已强制，但合并前主动跑一次）

## 冲突裁决顺序

```
AGENTS.md / .agent/ 规则文件 > spec-kit 产物（constitution/spec/plan）> 任务卡内容 > 会话中的口头约定
```

- 裁决冲突记入 `docs/DECISIONS.md`（谁裁的、依据、结果）
- 禁止用"另写一份说明文档"的方式解决分歧

## 收工汇报（每个 harness 每次结束任务时）

- 卡状态改到位（done / review + 留给谁）：`backlog task edit` + commit + push main
- 功能分支推上或合并；`git-wt remove` 清理本卡工作树
- 卡内"交接说明"节留 ≤5 行（做了什么、验证方式、注意事项）——下一个接手的是另一个工具，它没有你的会话记忆
