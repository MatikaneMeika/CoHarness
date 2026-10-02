# {{PROJECT_NAME}} — 多组件/多 harness 协作骨架 v2

> 触发约定：用户说「coharness X」（可带 @路径）= 按本文件与 `.agent/` 规程执行 X；调度细则见 `{{COHARNESS_LIB}}/ROUTER.md`（装机时代成绝对路径，所以换一个 harness 打开本项目也不用问库在哪）；门禁照走不豁免。

## 项目卡

| 项 | 内容 |
|---|---|
| 骨架 schema | 4 |
| 一句话 | {{GOAL}} |
| 运行方式 | `{{RUN_CMD}}` |
| 测试方式 | `{{TEST_CMD}}` |
| 任务层 | Backlog.md（`backlog/` 目录，git 原生卡片） |
| 规格层 | GitHub Spec Kit（`.specify/`，/speckit-* 命令族） |
| 工作树隔离 | Worktrunk（Windows 下 `git-wt`） |

依赖安装（一次性）：`npm i -g backlog.md`；`uv tool install specify-cli`；`winget install max-sixty.worktrunk`。自检：`python {{COHARNESS_LIB}}/wsc.py doctor`。

## 组件地图（新增组件必须登记于此）

| 组件 | 技术 | 目录 | 端口 | 入口 |
|---|---|---|---|---|
| {{COMPONENT_1}} | {{STACK_1}} | code/{{COMPONENT_1}}/ | {{PORT_1}} | {{ENTRY_1}} |
| {{COMPONENT_2}} | {{STACK_2}} | code/{{COMPONENT_2}}/ | {{PORT_2}} | {{ENTRY_2}} |

## 单写者所有权表（路径前缀 → 唯一写者）

| 路径 | 唯一写者 | 其他人 |
|---|---|---|
| `code/<组件>/` | 该组件的 coder | 只读 |
| `docs/ARCHITECTURE.md` | architect | 只读 |
| `docs/DECISIONS.md` | architect（ADR 只增不改） | 只读 |
| `AGENTS.md`、`.agent/`、`scripts/` | architect（规则层，走规则卡 + ADR） | 只读 |
| `backlog/` 状态流转 | 各 harness 认领后改自己的卡，总裁决归 integrator | 只读他人卡 |
| 其余共享契约（接口定义等） | architect | 只读，变更走 ADR |

并行工作的前提是**路径不重叠**：两卡 `allowed_paths` 有交集时必须串行，或由 pm 先切分边界。
本表与卡片 `allowed_paths` 都是授权来源且**以本表为准**：卡可以把本表里属于你的路径收窄，不能把标"只读"的路径扩成可写——要扩先改本表（走规则卡 + ADR）。这条已有机械核对（I-005，2026-09-29 起）：`check.py` 在提交时对表里"具体路径 + 具体角色"的行，核对该路径覆盖它的在做卡有没有 `role:<角色>` 标签（"同一会话可身兼多角"，角色由卡声明），没有就拦下提交；模板行与散文写者行判不了，留给审核人。

## 接口契约（路径前缀 → 契约定义 → 变更要通知谁）

所有权表管"谁能写"，这张表管"改了会波及谁"。`wsc sync --dry-run` 会拿它对照即将进来的改动，
开工时就知道这次同步会不会动到你的接口。（通知落在自己的交接说明里；**不往别人的卡上写行**——
他人卡的唯一写者是他自己，见所有权表。）

| 路径前缀 | 契约/接口定义在哪 | 变更要通知 |
|---|---|---|
| `code/api/` | `docs/ARCHITECTURE.md` 的接口节 | 所有 doing 卡里含 `code/` 的 harness |
| `code/shared/` | 模块自身 README | 在场全部 harness |
| `docs/ARCHITECTURE.md`、`docs/DECISIONS.md` | 本身即契约 | integrator + 受影响组件 coder |
| `backlog/config.yml` | 状态词表与列定义 | 在场全部 harness |

## 全局禁令（违反 = 直接返工；本节为 constitution 底稿来源，见 docs/CONSTITUTION-SOURCE.md）

1. **交付文件名禁版本后缀**：`-v2` / `-final` / `-副本` / `-新` / `-修正版` 一律禁止，版本进 git + CHANGELOG
2. **禁平行规则文档**：一切协作规则只在本文件和 `.agent/` 中演进；改规则 = 改文件 + git commit + CHANGELOG 记一行
3. **过程产物不进交付树**：草稿、截图、日志、备份不进 `code/` 和 `docs/`；临时调试文件用完即删。**测试产物一律写临时目录**（如 pytest 的 `tmp_path`），禁止写入任何 tracked 路径——尤其已入库的证据目录：跑一次全量测试就把证据改脏，会连带卡住所有人的 rebase 与提交（I-002，2026-09-30 晋升）
4. **禁孤儿分支/工作树**：harness 收工必须 `git-wt merge` + `git-wt remove`，不留残骸
5. **禁绕过任务卡直接改代码**：所有改动必须挂卡（pre-commit 强制）
6. **事实唯一**：版本号、接口契约、结构描述只在一处记录，其他地方引用之；拿文件哈希当指纹/血缘凭证时，文本先做 `\r\n -> \n` 归一，二进制保持原始字节（行尾由 `.gitattributes` 钉 LF）
7. **发现骨架问题就登记**：规则缺失/冲突造成返工、同类摩擦 ≥2 次、或缺 skill/MCP 时，在 `.agent/improvements.md` 登记一行（门槛见该文件头部）；试点改动只落本项目，晋升本体走 evolve 审核。规则卡与改进登记都走共享分支 main

## 规格与拆卡（Spec Kit 流程）

需求 → `/speckit-specify` → `/speckit-clarify`（歧义清零）→ `/speckit-plan`【门禁 1：用户确认】→ `/speckit-tasks` → pm 转成 Backlog 卡 → 并行实现 → reviewer 门禁 → tester 回归【门禁 2：清单全过 + 回归全绿 + check.py 全绿】→ integrator 收尾。
桥接规则见 `.agent/roles/pm.md`；技术方案纪律见 `.agent/roles/architect.md`；完整流程图见 `.agent/workflows/new-feature.md`。

## 任务看板（Backlog.md）

- 看板与卡片：`backlog board` / `backlog task list` / `backlog task view T-xxx`
- 建卡 / 改卡：`backlog task create` / `backlog task edit`（卡片格式约定见 `.agent/tasks/CARD-CONVENTION.md`）
- 状态四列：`todo → doing → review → done`（写在 `backlog/config.yml` 的 `statuses`；真工具默认是 `To Do / In Progress / Done`，装机时按 wsc init 的提示改成这四列）
- 认领 = `python {{COHARNESS_LIB}}/wsc.py claim <项目> T-xxx <harness标识>`（同步+校验+提交+推送绑成一步，被抢就还原并列出可认领的卡）；手工路径为 `backlog task edit -a <标识> -s doing` 且**提交直接进 main**；一卡一 assignee；卡片与 `.agent/improvements.md` 属自授权改动（不再要求挂卡），细则见 parallel-protocol
- 收工唤醒下一个：`coh-dispatch --advance <项目>`（按候选/预选拉起下一个 harness：认领 + 建工作树 + 开新终端，拉起后立刻失联；启动命令表在 `.agent/dispatch.md`，缺表只列候选不执行）
- 自动派发默认关闭；只有用户明确要求 architect 或 integrator“开启自动派发”后，收工协议才可自动调用 `coh-dispatch --advance`。候选 harness 由 architect 用 `python scripts/dispatch_env.py --json` 只读探测（或按用户指定）后登记，骨架不预置本机 CLI 或路径；候选可用不等于自动改派。
- **收工留痕三查**（I-004，2026-09-30 晋升）：卡状态改到位后必须确认 ① `git status --short` 为空；② `git rev-parse HEAD` 与 `origin/main` 相同；③ 本卡 worktree 已 remove。**看板与卡片读磁盘，显示 done 不等于已入册**——曾发生 289 个文件（含整版交付物）只存在于工作区、git 历史无记录的事故。

## 角色一览

| 角色 | 文件 | 职责 |
|---|---|---|
| pm | `.agent/roles/pm.md` | spec-kit 规格流程 + 转卡拆分（allowed_paths 互斥） |
| architect | `.agent/roles/architect.md` | /speckit-plan 技术方案、接口契约、ADR；维护候选 harness 清单与角色→CLI 映射 |
| coder-<组件> | `.agent/roles/coder-frontend.md` 等 | 按卡实现，路径白名单（卡"边界"节） |
| doc-writer | `.agent/roles/doc-writer.md` | 文档/企划书生产 |
| reviewer | `.agent/roles/reviewer.md` | 合入前审查门禁 |
| tester | `.agent/roles/tester.md` | 集成回归 |
| integrator | `.agent/roles/integrator.md` | 合并串行化、stale 改派、状态总裁决；只读巡检 harness 就绪度 |

同一会话可身兼多角，但**实现与审查必须分开两轮**；多 harness 并行规则见 `.agent/workflows/parallel-protocol.md`。

## 执法

`python scripts/check.py`（命名规范 / 卡格式与边界节 / 改动挂卡 / stale / assignee 冲突），已由 pre-commit 钩子强制（`scripts/hooks/pre-commit`，wsc init 自动安装）。**所有工具的提交都过这一个钩子。**

`check.py` 每次执行会在项目内 `.agent/telemetry.jsonl` 追加一行本地运行记账（时间、harness 标识、跑了哪几项、通过与否、当时在做的卡）。它已在 `.gitignore` 里——不进版本库、不联网、不弄脏工作区，只给 `python <库>/wsc.py stats <项目>` 当数据源（遵循率 / 返工信号 / stale 分布）。不想留：`--no-track` 或环境变量 `COHARNESS_NO_TRACK=1`。

### 远端门禁（CI，第二道门）

`.github/workflows/coharness.yml`（随骨架带入的 GitHub Actions workflow）：push 到 main 与指向 main 的 PR 会在 runner 上跑 `python scripts/check.py --names --tasks --against <基线> --no-track`。PR 基线为 `origin/main`，push 基线为 `event.before`；基线全零或 force-push 后不可达时发 `::notice::` 后只跑 names+tasks，降级可见。口径：**本地钩子是第一道门，CI 是第二道**——`--no-verify` 逃得过本地、逃不过远端；裸克隆没装钩子也躲不开这道门。CI 红了先修卡 / 改派（按所有权表），不是原样重推。仓库不在 GitHub 托管时该文件惰性无害；等价门禁（GitLab CI 等）按 `.agent/improvements.md` 登记为能力缺口，不私改执法面。

## 冲突裁决顺序

```
AGENTS.md / .agent/ 规则文件 > spec-kit 产物 > 任务卡内容 > 会话中的口头约定
```

## 工具接入

- **ZCode / Codex**：原生读本文件；可选 `backlog mcp start` 接入任务工具
- **Qoder**：项目 Rules 加一行 `一切约定以根目录 AGENTS.md 为准`；specify 用 `--integration qodercli`
- **Antigravity**：读本文件（必要时加一行式 `GEMINI.md` 指针）；specify 用 `--integration generic`
- **specify 初始化**：对每个在场工具各跑一次 `specify init --integration <名>`

原则：`AGENTS.md` 是唯一权威，任何工具专属文件只放一行指针，**不写第二份规则**。
## 共享解释器（venv）约定

多 harness 共用同一个解释器（如 `code/.venv`）时：

1. **重建前先探测**：先确认已有环境是否可用（跑一次最小自检脚本，或看 `pip list` 与上次的 `env_report.json`），不要凭"大概没装"就重建；
2. **只用同一套安装器**：本项目统一用一个安装器（`uv` 或 `python -m venv`，二者混用会静默清空 site-packages）；
3. **重建后必须复验并广播**：重跑自检脚本，把解释器路径与关键依赖版本写进当次交接说明；重建期间在场 harness 的测试结果一律视为无效。

（I-003，2026-09-30 晋升：某项目 venv 两次被清空，CUDA torch 与 mediapipe 全丢，多路测试在"以为装好了"的环境上失败。）

## 降级行为（依赖没装时）

装机顺序无所谓，缺一项就照这一节走回落路径；`python {{COHARNESS_LIB}}/wsc.py doctor --explain backlog,specify,worktrunk,node`
会把同样的话打给你看，`--simulate-missing=<项> <项目>` 还能核对回落产物在不在位。

- **`backlog` 没装**：卡片仍是 md 文件。`wsc sync` 回落读 `backlog/tasks/*.md`；手工建卡照样被
  `scripts/check.py` 执法（认领唯一、边界交集、卡格式都在文件层）。零依赖起步可
  `wsc init 03 <空目录> --minimal`——任务清单换 `TODO.md`，代价是卡片层执法随之关闭（AGENTS.md 会写明关闭了哪几条）
- **`specify` 没装**：规格流程手工五步——需求 → 技术口径 → 边界（allowed/forbidden） → 验收清单 → 交接说明，
  产物与转卡由 pm 角色手写；执法不变，只是没人替你校验规格格式
- **`git-wt`（Worktrunk）没装**：用原生 `git worktree add`。**一个 harness 一个工作目录**这条不许破，
  两个 harness 禁止共居同一 clone；pre-commit 装在共享的 `.git/hooks` 里，工作树照样过钩子
- **`node` 没装**：npm 系工具（backlog.md）装不上，走上一条 backlog 的回落路径

组件版本按实测钉住：Backlog.md 1.53.0（`statuses` 键、默认英文三列需手改、卡文件名 `t-<n> - <标题>.md`、
`--agent-instructions` 会往 AGENTS.md 注入 24 行——本骨架要求填 `none`）。

## 深读指引（遇到什么读什么）

本文件只保留高频规则；下表这些文档**在对应情境下必须先读再动**（指向不存在的文档是缺陷，由 test_skeleton_integrity 钉住）：

| 遇到什么 | 读哪份 | 为什么 |
|---|---|---|
| 写卡、改卡、填交接说明 | `.agent/tasks/CARD-CONVENTION.md` | 卡是唯一协调面，格式错会被 check.py 响亮拒绝 |
| 认领、并行、stale 改派 | `.agent/workflows/parallel-protocol.md` | 先到先得与合并纪律的权威版本 |
| 担任某个角色 | `.agent/roles/`（pm / architect / integrator / reviewer / tester / doc-writer / coder-） | 角色职责与动作清单 |
| 谁能写哪个路径 | 本文件「单写者所有权表」 | 授权总裁决，扩权先改表（check.py 机械核对 role: 标签） |
| 依赖没装、命令失败 | 本文件「降级行为」 | 每个依赖的降级路径与 probe |
| 改架构、动接口 | `docs/ARCHITECTURE.md` | 架构唯一事实源，变更走 ADR |
| 为什么这么做 | `docs/DECISIONS.md` | ADR 只增不改 |
| 查交付历史 | `docs/CHANGELOG.md` | 合并收尾核对条目 |
