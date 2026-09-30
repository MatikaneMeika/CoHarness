# 流程：parallel-protocol v2（多 harness 并行规则）

多个 AI 工具（ZCode / Codex / Qoder / Antigravity）同时在一个仓库干活时的防冲突协议。
任务状态存于 Backlog.md（`backlog task` 命令族），工作区隔离用 Worktrunk（Windows 下命令为 `git-wt`）。

## 开工协议（每次会话开始时，顺序固定）

1. `git pull --ff-only`（在主工作树或自己的 worktree 内）——看板可能已被其他 harness 改动
   - worktree 里的 harness 分支一般没有 upstream，裸 `git pull --ff-only` 会 rc=1：改用 `wsc sync <项目>`（它会自动回退到 `git pull --ff-only origin main`），或显式指名
2. `backlog board`（或 `backlog task list`）读看板
3. 选一张 status=todo 且 dependencies 已满足的卡
4. 认领（见下节）
5. `git-wt switch -c feat/T-xxx-<slug>` 开自己的 worktree 干活

**禁止跳过 pull 直接凭上次记忆选卡。**

## 认领（先到先得）

1. **首选一条命令**：`python {{COHARNESS_LIB}}/wsc.py claim <项目> T-xxx <harness标识>`
   —— 它把"fetch + 变基 + 读卡校验 + 写卡 + 过项目 check.py + commit + push main"绑成一步，
   任何一步不成都还原，不会留下半截认领；被抢则退出并列出此刻可认领的卡
2. 手工路径（用 backlog CLI 或不带 wsc 时）：`backlog task edit T-xxx -a <harness标识> -s doing`
   + **commit + push 到 main**；先 pull 再改，改完立刻推
3. harness 标识 = 工具名 + 会话尾缀，如 `zcode-0926a`；一卡只允许一个 assignee
4. **认领与状态流转的提交必须直接进共享分支 main**——跟功能分支走 = 别人看不见你认领了，先到先得即失效
5. owner 冲突（两工具同时认领同一卡）：以 git 先推入 main 者为准，后到者换卡；
   手工路径靠 pull 时机兜，`wsc claim` 靠推送被拒后重新同步再判一次

## 看板改动与登记怎么提交

卡片文件（`backlog/tasks/*.md`）与 `.agent/improvements.md` 是**自授权改动**：认领、状态流转、
改进登记这三类提交不需要再被某张卡的 `allowed_paths` 覆盖，直接 commit + push main。
它们仍受同一套全局纪律约束——一卡一 assignee、一 harness 一张 doing 卡、卡体缺"## 边界"节即违规。

规则文件（`AGENTS.md`、`.agent/roles|workflows|tasks`）不在自授权之列：永远串行，只允许一张"规则卡"在跑。

**为什么这样定**：2026-09-28 并发演练实测，要求这三类改动也挂卡会让认领彻底无路可走——
唯一的授权来源是常驻规则卡，而持它再领实现卡会撞"一 harness 一张 doing 卡"，
退回它又卡在"该卡仍为 todo"上，四条路全部 rc=1。缺口登记为 I-001，本条是它的晋升产物。

## pull 时机（写死，三处）

- 开工时、认领前、push 前，各 pull 一次
- 开工时想知道这次同步会碰到谁：`python {{COHARNESS_LIB}}/wsc.py sync <项目> --dry-run`——不 pull、不 fetch、不写盘，只按 `AGENTS.md` 的「接口契约」表与在看板的卡边界报告命中；**通知写在自己的交接说明里，不改他人的卡**
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

- doing/review 卡超过 **24 小时**无新 commit（对照卡 `updated_date` 与 `git log`），即打上 stale 标记
- **stale 是提示，不是改派授权**：无更新、联系不上本身不构成改派依据——缺席 ≠ 死亡，卡可能只是慢
- 改派需要**正面证据**：对方明确退出、自己报告放弃、或超过两倍阈值（48h）的沉默且联系无果；
  由 integrator 执行——assignee 置空、状态退回 todo，并在卡交接说明**首行**记 `结果: 改派（原因+时间）`
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
