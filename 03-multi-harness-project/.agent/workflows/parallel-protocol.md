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

## harness 发现与自动派发开关（默认关闭）

- 集成或开工巡检时运行 `python scripts/dispatch_env.py --json`：只读检查候选 harness 与角色启动命令是否就绪，报告缺工具、未映射候选、未就绪角色与配置漂移。
- 候选 harness 是本机环境事实，不写进骨架默认值。architect 按本机 PATH 探测或按用户明确指定的工具名登记；新 harness 是否承担角色必须走规则卡/ADR，不自动映射。
- 自动派发默认关闭。只有用户明确对 architect 或 integrator 说“开启自动派发/关闭自动派发”后，才更新 `.agent/dispatch.md` 的开关；候选可用不等于自动改派，不得自行推断。
- 开关关闭时，收工不自动调用 `coh-dispatch --advance`；需要派发由用户显式发起。开关开启后仍只按既有确定性预选和失败不重试规则动作。

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

## 派发失败处理（发起会话负责，重试上限 1 次）

| 失败 | 归属 | 动作 | 上限 |
|---|---|---|---|
| 认领失败（卡被抢） | 发起派发的会话 | 重新 `plan` 拿新候选，重试一次 | 1 次 |
| 建 worktree 失败 | 发起派发的会话 | 修正现场后重试一次 | 1 次 |
| 开窗/拉起失败 | 发起派发的会话 | 修正命令或终端后重试一次 | 1 次 |
| 缺表 / 角色无命令 / 工具不在 PATH | 发起会话 | 当场补配置；补不了登记改进并升级给人 | 1 次 |
| 重试到顶 | 发起会话 | 登记 + 升级给人，**不静默改派** | — |
| 派发成功但长期无动静 | integrator（总控帽子） | 走本文件既有 stale 条款 | — |

## 总控边界（试点口径，不新增角色）

- 派发保持去中心：**谁收工谁唤醒**；总控不独占派发按钮，也不成为链条的单点在场依赖。
- 总控由既有 `architect` / `integrator` 帽子承担，不写进角色一览，不改变“同一会话可身兼多角”。
- 总控负责失败处置、巡检、stale 改派与规则裁决；库侧 `dispatch` 只管认领、工作树、拉起与执法，不知道“总控”这个概念。
- 总控不在场就停在原地，靠下一次 `wsc sync` 巡检恢复；不引入常驻进程，不把调度状态挪出 git。

## 合并纪律

- 进 main **一次一人**：合并动作本身串行，先到先得
- 后到者 rebase 到最新 main 再合并；冲突以契约文件与 ARCHITECTURE.md 为准裁决，裁决记 ADR
- `python scripts/check.py` 全绿才允许合入（pre-commit 已强制，但合并前主动跑一次）
- **禁止在实现分支上反向 `git merge main`**：收工统一回 main 工作树执行 `git merge <实现分支>`；分支侧反向合并会把 main 上 done 卡的历史改动重新挂到本次暂存集，既过不了钩子也会把历史责任混在一起
- 若反向合并已经被拦住：不要 `--no-verify` 绕过，改用 main 侧合并并重放本卡产物；`check.py` 报错会打印卡片真实 status 供诊断

## 冲突裁决顺序

```
AGENTS.md / .agent/ 规则文件 > spec-kit 产物（constitution/spec/plan）> 任务卡内容 > 会话中的口头约定
```

- 裁决冲突记入 `docs/DECISIONS.md`（谁裁的、依据、结果）
- 禁止用"另写一份说明文档"的方式解决分歧

## 收工汇报（每个 harness 每次结束任务时）

- 卡状态改到位（done / review + 留给谁）：`backlog task edit` + commit + push main
- reviewer fail：先写审阅意见并把卡退回 `doing`；返工后追加新 commit、勾完审阅意见，再退回 `review`；存在未勾选项不得合并。
- **入册三查**（I-004，2026-09-30 晋升，缺一不可）：① `git status --short` 输出为空；② `git rev-parse HEAD` 与 `git rev-parse origin/main` 相同；③ `git-wt list` 里本卡工作树已清理。任何一项不满足就是"没干完"——看板读磁盘，显示 done 不等于已入册
- 功能分支推上或合并；`git-wt remove` 清理本卡工作树
- 跑过全量测试后先 `git status --short` 看一眼：测试产物（尤其证据目录里的 json/csv/png）可能被被动改写，用 `git restore --source=HEAD --staged --worktree <路径>` 还原，别把它们当成果提交（I-002 晋升）
- 卡内"交接说明"节留 ≤5 行（做了什么、验证方式、注意事项）——下一个接手的是另一个工具，它没有你的会话记忆
- 唤醒下一张卡：`coh-dispatch --advance <项目>`——按候选与确定性预选拉起下一个 harness（认领 + 建工作树 + 开新终端），拉起后立刻失联（不持有句柄、不读输出、不自动重试）；启动命令表在项目侧 `.agent/dispatch.md`
- 唤醒前先看 `.agent/dispatch.md` 的自动派发开关：关闭时由用户显式发起；开启时按本节协议执行。无论开关状态，先跑 `python scripts/dispatch_env.py --json`，未就绪只报告并升级，不自动 fallback。
