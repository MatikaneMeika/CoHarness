# {{PROJECT_NAME}} — 多组件/多 harness 协作骨架 v2

> 触发约定：用户说「开工：X」（可带 @路径）= 按本文件与 `.agent/` 规程执行 X；调度细则见骨架库 `ROUTER.md`；门禁照走不豁免。

## 项目卡

| 项 | 内容 |
|---|---|
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
| `backlog/` 状态流转 | 各 harness 认领后改自己的卡，总裁决归 integrator | 只读他人卡 |
| 其余共享契约（接口定义等） | architect | 只读，变更走 ADR |

并行工作的前提是**路径不重叠**：两卡 `allowed_paths` 有交集时必须串行，或由 pm 先切分边界。
本表与卡片 `allowed_paths` 都是授权来源且**以本表为准**：卡可以把本表里属于你的路径收窄，不能把标"只读"的路径扩成可写——要扩先改本表（走规则卡 + ADR）。

## 全局禁令（违反 = 直接返工；本节为 constitution 底稿来源，见 docs/CONSTITUTION-SOURCE.md）

1. **交付文件名禁版本后缀**：`-v2` / `-final` / `-副本` / `-新` / `-修正版` 一律禁止，版本进 git + CHANGELOG
2. **禁平行规则文档**：一切协作规则只在本文件和 `.agent/` 中演进；改规则 = 改文件 + git commit + CHANGELOG 记一行
3. **过程产物不进交付树**：草稿、截图、日志、备份不进 `code/` 和 `docs/`；临时调试文件用完即删
4. **禁孤儿分支/工作树**：harness 收工必须 `git-wt merge` + `git-wt remove`，不留残骸
5. **禁绕过任务卡直接改代码**：所有改动必须挂卡（pre-commit 强制）
6. **事实唯一**：版本号、接口契约、结构描述只在一处记录，其他地方引用之
7. **发现骨架问题就登记**：规则缺失/冲突造成返工、同类摩擦 ≥2 次、或缺 skill/MCP 时，在 `.agent/improvements.md` 登记一行（门槛见该文件头部）；试点改动只落本项目，晋升本体走 evolve 审核。规则卡与改进登记都走共享分支 main

## 规格与拆卡（Spec Kit 流程）

需求 → `/speckit-specify` → `/speckit-clarify`（歧义清零）→ `/speckit-plan`【门禁 1：用户确认】→ `/speckit-tasks` → pm 转成 Backlog 卡 → 并行实现 → reviewer 门禁 → tester 回归【门禁 2：清单全过 + 回归全绿 + check.py 全绿】→ integrator 收尾。
桥接规则见 `.agent/roles/pm.md`；技术方案纪律见 `.agent/roles/architect.md`；完整流程图见 `.agent/workflows/new-feature.md`。

## 任务看板（Backlog.md）

- 看板与卡片：`backlog board` / `backlog task list` / `backlog task view T-xxx`
- 建卡 / 改卡：`backlog task create` / `backlog task edit`（卡片格式约定见 `.agent/tasks/CARD-CONVENTION.md`）
- 状态四列：`todo → doing → review → done`（写在 `backlog/config.yml` 的 `statuses`；真工具默认是 `To Do / In Progress / Done`，装机时按 wsc init 的提示改成这四列）
- 认领 = `python {{COHARNESS_LIB}}/wsc.py claim <项目> T-xxx <harness标识>`（同步+校验+提交+推送绑成一步，被抢就还原并列出可认领的卡）；手工路径为 `backlog task edit -a <标识> -s doing` 且**提交直接进 main**；一卡一 assignee；卡片与 `.agent/improvements.md` 属自授权改动（不再要求挂卡），细则见 parallel-protocol

## 角色一览

| 角色 | 文件 | 职责 |
|---|---|---|
| pm | `.agent/roles/pm.md` | spec-kit 规格流程 + 转卡拆分（allowed_paths 互斥） |
| architect | `.agent/roles/architect.md` | /speckit-plan 技术方案、接口契约、ADR |
| coder-<组件> | `.agent/roles/coder-frontend.md` 等 | 按卡实现，路径白名单（卡"边界"节） |
| doc-writer | `.agent/roles/doc-writer.md` | 文档/企划书生产 |
| reviewer | `.agent/roles/reviewer.md` | 合入前审查门禁 |
| tester | `.agent/roles/tester.md` | 集成回归 |
| integrator | `.agent/roles/integrator.md` | 合并串行化、stale 改派、状态总裁决 |

同一会话可身兼多角，但**实现与审查必须分开两轮**；多 harness 并行规则见 `.agent/workflows/parallel-protocol.md`。

## 执法

`python scripts/check.py`（命名规范 / 卡格式与边界节 / 改动挂卡 / stale / assignee 冲突），已由 pre-commit 钩子强制（`scripts/hooks/pre-commit`，wsc init 自动安装）。**所有工具的提交都过这一个钩子。**

`check.py` 每次执行会在项目内 `.agent/telemetry.jsonl` 追加一行本地运行记账（时间、harness 标识、跑了哪几项、通过与否、当时在做的卡）。它已在 `.gitignore` 里——不进版本库、不联网、不弄脏工作区，只给 `python <库>/wsc.py stats <项目>` 当数据源（遵循率 / 返工信号 / stale 分布）。不想留：`--no-track` 或环境变量 `COHARNESS_NO_TRACK=1`。

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
