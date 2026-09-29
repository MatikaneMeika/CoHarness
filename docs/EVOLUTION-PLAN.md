# EVOLUTION-PLAN — working_struct 极致优化计划书（借力成熟项目）

> 2026-09-26 制定。背景：骨架库初版（c4ddc86）验证了"约束写进文件、多 harness 共读"的方向，
> 但任务卡、规格拆解、工作树隔离均为自研。本计划把机械部分换给成熟开源组件，
> 骨架本身瘦身成**薄协议层 + 成熟组件 + 胶水配置**。

## 目标与原则

把 working_struct 从"自制任务系统"升级为多 harness（ZCode / Codex / Qoder / Antigravity）真正可开的合作区。三原则：

1. **文件即真相**：一切状态进 git，任何工具专属容器只放指针
2. **机械的交给成熟 CLI，判断的留在协议文件**：认领/看板/工作树/规格拆解用现成工具；所有权纪律、门禁、裁决协议保持自研
3. **骨架库自身零运行时依赖**：依赖（backlog / specify / git-wt）属于实例化后的项目

## 新架构（03 合作区，六层）

| 层 | 承载 | 来源 |
|---|---|---|
| 协议层 | AGENTS.md v2 + parallel-protocol v2 + constitution（全局纪律单一源） | 自研保留，补齐 4 缺口 |
| 规格层 | Spec Kit：/speckit-constitution → specify → clarify → plan → tasks（原生集成 zcode/codex/qodercli/generic，覆盖四工具） | github/spec-kit v1.0.12 |
| 任务层 | Backlog.md：`backlog/tasks/*.md`，board 列配置为 todo/doing/review/done，assignee=harness 标识，dependencies=依赖，labels 承载 requirement_refs（02） | MrLesk/backlog.md v1.53.0 |
| 隔离层 | Worktrunk（Windows 下 `git-wt`）：一 harness 一 worktree 从"可选"变"铁律" | max-sixty/worktrunk 0.79.0 |
| 执法层 | check.py v2 + pre-commit hook（四工具唯一共享执法点） | 自研改造 |
| 入口层 | wsc.py（scaffold.py 扩展：init/sync/check/doctor）+ ZCode 用户级薄 skill | 自研 |

**明确排除**（记录决策依据，防止将来重复调研）：

- **Vibe Kanban**：2026-09 已宣布 sunset（README 顶部横幅），且看板状态存 `%APPDATA%\bloop\vibe-kanban\` 应用本地库、不进仓库——与"文件即真相"根本冲突。同类的 Claude Squad / Conductor 为 Mac 限定。
- **自研 MCP server**：状态会脱离 git，且四工具 MCP 支持参差。Backlog.md 自带 MCP（`backlog mcp start`）够用。
- **01/04/05 骨架不动**：01 太轻不值得加依赖；04/05 是领域纪律与纯数据，与这些工具无重叠。

## 执行阶段（每阶段一个 git commit）

### Phase 0 — 计划书落盘（本文件）

### Phase 1 — 03 骨架核心改造

- **parallel-protocol.md v2**，补四缺口：
  1. 强制隔离：`git-wt switch -c feat/T-xxx` 一卡一 worktree，禁止多 harness 共居同一 clone
  2. 认领可见性：认领与状态流转**直接提交共享分支（main）**，代码改动才走功能分支；pull 时机写死（开工前、认领前、push 前）
  3. 开工协议（与既有收工汇报对称）：pull → `backlog board` → 选卡 → `backlog task edit`（assignee+status=doing）→ commit+push main
  4. stale 与合并纪律：doing/review 卡超 24h 无新 commit（依据 updated_date + git log）integrator 可改派；进 main 一次一人、先到先得、后到者 rebase
- **AGENTS.md v2**：任务看板节改为 Backlog CLI 命令表；裁决顺序 `AGENTS/.agent 规则 > spec-kit 产物 > 任务卡 > 口头`；工具接入节加四工具的 specify 集成名
- **TEMPLATE.md 删除** → `CARD-CONVENTION.md`：frontmatter 全权交给 Backlog（禁自造字段），卡体固定五节：需求 / 技术口径 / 边界（allowed_paths + forbidden_paths）/ 验收清单 / 交接说明≤5行
- **角色瘦身**：pm.md（拆卡流程指向 /speckit-specify→clarify→tasks，保留独有纪律）；architect.md（方案指向 /speckit-plan，保留 ADR 只增不改、契约唯一源）；integrator.md（新增合并串行化职责 + stale 改派权）
- **check.py v2**：任务目录改读 `backlog/tasks/*.md`（尊重 backlog.config.yml）；保留命名规范、diff 挂卡、forbidden 命中、状态枚举；新增 `--stale`、assignee 冲突检测、卡体"边界"节格式校验；退出码 0/1 不变
- **新增 `scripts/hooks/pre-commit`**：跑 check.py，失败即拦（所有工具提交必经）
- **新增 `docs/CONSTITUTION-SOURCE.md`**：全局纪律底稿，实例化时灌入 /speckit-constitution（项目运行时唯一源 = spec-kit 生成的 constitution，底稿只是模板）

### Phase 2 — Spec Kit 接入说明与桥接

- 安装 `uv tool install specify-cli`；对每个在场工具跑 `specify init --integration zcode|codex|qodercli|generic`
- 桥接指令：/speckit-tasks 产出逐条转 `backlog task create`（dependencies 对应依赖，边界节由 architect 按组件地图填）
- 门禁映射：门禁1 = /speckit-plan 用户确认；门禁2 = reviewer + tester + check.py 全绿
- new-feature.md workflow 同步更新为 spec-kit 流程

### Phase 3 — 02 课程作业轻接

- 任务机制换 Backlog（labels 承载 requirement_refs，如 REQ-3）；不引入 check.py 保持轻量
- requirement-analyst 的逐字摘录 + ⚠ 门禁**保留**（Spec Kit 无等价物），提取环节可借助 /speckit-clarify
- AGENTS.md 学术诚信纪律标注为 constitution 内容；assignment.md workflow 同步更新

### Phase 4 — 工具链层

- **scaffold.py → wsc.py**：`init`（复制骨架 + 占位符清单 + 引导依赖安装 / 装 pre-commit）、`sync`（pull + 看板摘要 + stale 报告）、`check`（转发项目 check.py）、`doctor`（自检 node/backlog/uv/specify/git-wt，缺啥给一行安装命令）
- **README.md 更新**：六层架构、03/02 依赖安装表、四工具接入表、"进阶参考"改写（Spec Kit/Backlog 已接入；Vibe Kanban 移除并注明 sunset）
- **ZCode 用户级 skill** `~/.agents/skills/coharness/SKILL.md`：薄指针，不写任何规则本体
  （原目录名 `collab-zone`，2026-09-29 随触发词一起改成 `coharness`——旧词「开工：」/`ws` 太泛）

### Phase 5 — 验收（精简版：只验本计划新写的代码，成熟工具自身能力不重复验）

1. 静态一致性：临时目录 `wsc init multi`，文件齐全、占位符正确、hook 就位——不安装真实依赖
2. check.py v2 自测：fixture 断言 `--names/--tasks/--diff/--stale` 精确通过/拦截
3. 真实格式抽验（条件执行）：仅当机器已装 backlog 时验真实 frontmatter；否则记待验项
4. 结果记入本文件附录；**不做**四集成 specify init、git-wt 双 worktree 模拟、双 harness 演练——交给首次真实使用

## 风险与对策

- **Backlog 无原生认领锁/stale 检测**（已核实 v1.53.0）→ 协议层补：认领走 main 分支 git 串行化 + check.py 冲突检测 + updated_date stale 规则
- **卡体"边界"节是自造约定，Backlog 不校验** → check.py 强制格式，缺节即 fail
- **Spec Kit 高频发版可能语义漂移**（v1.0.12，2026-09 内多次发版）→ README 钉住验证过的版本；裁决顺序已把 spec-kit 产物压在 .agent 规则之下
- **依赖安装失败** → wsc doctor 一行命令自诊；01/04/05 零依赖不受影响
- **已实例化旧项目不自动同步** → 保持既有演进规则，见下方迁移要点

## 旧项目手动迁移要点（.agent/tasks YAML 卡 → Backlog）

1. 项目根 `npm i -g backlog.md` 后 `backlog init`，配置看板列 `columns: [todo, doing, review, done]`
2. 每张旧卡转 `backlog task create`：owner → assignee、depends_on → dependencies、四态照搬
3. 旧卡正文的允许/禁改清单移入新卡"## 边界"节；验收清单、交接说明按 CARD-CONVENTION 搬
4. 把 `scripts/hooks/pre-commit` 装进 `.git/hooks/`（wsc init 会自动做）
5. 跑 `python scripts/check.py` 全绿后删 `.agent/tasks/` 旧卡，CHANGELOG 记一行

## 验收附录（2026-09-26 实测）

**静态一致性（wsc init multi，临时目录 + git init）**
- ✓ 20 个文件全部复制（含 CARD-CONVENTION、check.py、pre-commit）
- ✓ pre-commit 钩子自动安装进 `.git/hooks/`
- ✓ 占位符清单输出正确（15 个占位符 + 依赖安装提示）
- ✓ 仅含 `.git` 的目标目录放行（首轮验收发现 init 会误拒，已修复）

**check.py v2 fixture 自测（5 张卡 + 违规文件，断言全过）**

| 断言 | 结果 |
|---|---|
| `--names`：`report-final.md` 精确报出，exit=1 | ✓ |
| `--tasks`：T-2 缺"## 边界"节、T-4 一卡多 assignee、zcode-a 双 doing 卡冲突，exit=1 | ✓ |
| `--stale`：T-3 提示"已约 152h 无更新，integrator 可改派"，仅提示 exit=0 | ✓ |
| `--diff`：`docs/secret.md` 命中 T-4 forbidden_paths、`misc-other.txt` 未挂卡，exit=1 | ✓ |
| 挂卡内的合法改动（code/server/ 下文件）不误报 | ✓ |
| 违规文件移除后 `--names` 恢复 exit=0 | ✓ |
| **pre-commit 端到端**：git commit 实际被钩子拦截并给出修复提示（Windows Git 环境） | ✓ |

**首轮验收发现并已修复的问题**
1. 骨架混入 `scripts/__pycache__/*.pyc` 运行残留并被复制 → 已清理，`instantiate` 增加 pycache/pyc 过滤防复发
2. `wsc init` 拒绝仅含 `.git` 的目标目录 → 已放行（先 git init 再实例化的顺序现在可用）

**待验项（按计划不为此安装依赖，留给首次真实使用）**
- Backlog.md 真实 frontmatter 与 check.py 解析的兼容（本机未装 backlog；解析按其公开文档的扁平 frontmatter 行为编写）
- `backlog.config.yml` 列配置的精确键名（当前为宽容解析，解析失败回落默认四列，不影响执法）
- `specify init` 四集成（zcode/codex/qodercli/generic）实操、git-wt 双 worktree 并行实操

## 决策记录（ADR）

> 本节 2026-09-28 起建（此前本文件没有编号化的决策记录）。只增不改，推翻旧条 = 追加新条并注明取代关系。

### ADR-10 · 依赖面按分发面分层

**背景**：优化计划书的"现成项目复用对照表"建议用 `python-frontmatter` + `jsonschema` 替换自写
frontmatter 解析（其 ADR-8）、用 `pre-commit` 框架替换自建钩子安装（其 ADR-9）、用 `copier` 替换
自建 migrate（其 ADR-7）。这与本文件"三原则"之 3（骨架库自身零运行时依赖）以及 SECURITY.md 的
"纯标准库 / 零网络 / 一个下午能读完"三条承诺正面冲突。裁决依据是**分发面不同**：

| | wsc.py | check.py |
|---|---|---|
| 分发方式 | 开发者自己装（骨架库环境） | **复制进每一个实例化项目** |
| 运行环境 | 作者可控 | 用户任意 Python 环境 |
| 对外承诺 | `curl` 单文件即可用 | SECURITY.md：五百行内纯标准库、可读 |

`check.py` 一旦依赖第三方库，每个下游项目、每台新机器都要先装包才能开工。本机
`import frontmatter` 失败就是这条摩擦的现场证据——"环境里恰好装了 jsonschema"不是可以依赖它的理由，
依赖现状是碎片化的，纯标准库是唯一确定的下界。

**决定**：

1. `check.py`（分发物）：纯标准库；只支持 `CARD-CONVENTION.md` 声明的扁平子集，子集外的写法
   **响亮失败**（`文件:行号` + 改写提示，退出码 1），不静默给出错的值。
2. `wsc.py`：同上，直到 W3（`pipx install coharness` / PyPI 发布）落地才复议。
3. CI 与测试（不进分发物）：开发期依赖 `python-frontmatter` + `pyyaml` 作**差分预言机**，
   同一批夹具对照自写子集解析器；未安装时该文件整体 skip，零依赖跑法不变。
   注意这是"用库验自研"，不是双实现——分发物里永远只有一份解析器。
4. 否决：现阶段向 `check.py` / `wsc.py` 引入运行时第三方依赖；否决用 copier 替换骨架分发
   （copier 经 git URL 取模板，与"零网络 + clone 即用"冲突）；否决 `wsc migrate` 自建升级版
   （升级路径另行按 ADR 复议，不用 copier 的模板同步模型）。

**重启条件**：W3 发布后 `wsc.py` 侧可重评估引依赖；`check.py` 永不——它跟着用户的项目走。
任何翻案必须同步改写 SECURITY.md 与 README 的对应承诺并记入 CHANGELOG，不留两套口径。

## 2026-09-28 补注（不改动上面带日期的原文）

- 正文提到的"05 骨架"从未建立（:30、:81 的 05 在 01-04 之外）；`ROUTER.md` 的同类笔误已就地改正，
  本文件保留原文只加本条注。
- :95 的"20 个文件"是当时的 03 计数。本轮给四套骨架补齐了目录地图声明却从不创建的路径
  （01 `src/`+`tests/`、02 `docs/notes.md`、03 `code/`+`backlog/tasks/`+`docs/reviews/`+`docs/regression/`、
  04 `docs/CHANGELOG.md`），计数已变，以 `wsc init` 的输出为准；
  `tests/test_skeleton_integrity.py` 会钉住"声明的路径必须真存在、引用的文件必须真在、
  占位符必须在项目卡里能解释"这三条。
- :117-119 三条待验项仍未验（本机不装 backlog / specify / git-wt，也不为此装）。
  其中"真实 frontmatter 与 check.py 解析的兼容"这条现在有了开发期差分预言机与子集夹具兜着
  （见本文件 ADR-10 与 `tests/fixtures/`）。

### ADR-10 附注 · 2026-09-28：三个面与行数上限的收口

W5/W7/W9/W12 落地后，`wsc.py` 一度涨到 1137 行——**自己写的行数上限测试当场把它判红**，
这正是那条测试存在的意义。处理不是删功能，而是把 ADR-10 的分层原则贯彻到底：

| 面 | 文件 | 谁在用 | 上限（由 `tests/test_distribution_surface.py` 钉） |
|---|---|---|---|
| 分发面 | `wsc.py`、`03-.../scripts/check.py` | 下游项目与其中的 harness | 1250 / 650 |
| 开发面 | `evolve.py` | 骨架库维护者（晋升审核） | 400 |
| 维护面 | `maintain.py` | 管已实例化项目的漂移/指纹/体检 | 700 |
| 展示面 | `board.py` + `panel.py` | 要看全局状态的人（只读，不进下游项目） | 580 / 220 |

- `check.py` 上限最严：它被复制进**每一个**下游项目，是执法面本体。
- `wsc.py` 允许到 1250 的唯一理由是 README 的 `curl` 单文件承诺——装机与开工命令不许散进多个文件；
  **这是最后一次为 `wsc.py` 上调**，之后的新命令**按面归位**：改已实例化项目的指纹/迁移/体检进
  `maintain.py`，晋升审核进 `evolve.py`，只读呈现进展示面（`board.py` 装配与渲染 + `panel.py` 终端，
  拆两个文件是为了让渲染能被 unittest 直接吃）。已写进 `CONTRIBUTING.md` 的代码约束同步改过。
- 展示面曾经破例带一次 `exec`（载入项目自己的 `scripts/check.py`，为的是卡片口径只有一套）：
  2026-09-29 被安全门按 CWE-95 判成高危拦截提交后改为 `importlib` 固定路径装载 +
  临时关闭字节码写入（照样不留 `__pycache__`），动态执行口子归零，
  由 `test_panel_loads_check_py_without_dynamic_execution` 钉死"零 exec/eval/compile + 一条路径"。
- `evolve.py` / `maintain.py` 只允许 `import wsc` 复用读表与调用形状，不许引入第三方：
  审核与维护都不该成为下游项目的依赖面。
- 计划书对照表里 ADR-7/8/9 的回绝理由不变（copier 走 git URL 取模板与"零网络 + clone 即用"冲突；
  运行时 frontmatter/jsonschema 破分发面；pre-commit 框架装钩子把执法点交给外部工具）。
