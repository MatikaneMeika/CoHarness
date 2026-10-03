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
- Backlog.md 真实 frontmatter 与 check.py 解析的兼容 → **已验（2026-10-02，W21 / T-109 实操）**：在系统临时目录沙盒实装 `backlog.md@1.53.0` 真建卡实测，覆盖基础、引号、含 #、列表、留空、role 标签等多值边界，产物钉入 `tests/fixtures/backlog-real-*`；除单引号内 `''` 转义被 `_strip_comment` 截断暴露既有解析器缺陷外，扁平子集 100% 兼容；口径差已对齐（详见 `docs/audits/T-109-Backlog-frontmatter兼容实测.md` 与末尾补注）。
- `backlog.config.yml` 列配置的精确键名 → **已验（2026-10-02，W22 / T-110 实操）**：在系统临时目录沙盒实装 `backlog.md@1.53.0` 实测，Backlog CLI 真实键名唯一为 `statuses`（`columns` 为早期自研猜测，CLI 报 `Unknown config key` 且完全不认）；真实产物钉入 `tests/fixtures/backlog-real-config-*`；`check.py` 改读真键 `statuses` 并将宽容回落改为未知键/缺键响亮提示（`[配置]` 报警），红绿用例已覆盖（详见末尾补注）。
- `specify init` 四集成（zcode/codex/qodercli/generic）实操、git-wt 双 worktree 并行实操 → **已验（2026-10-02，T-111 实操）**：在系统临时目录沙盒实装 `specify 1.0.13` 与 `wt v0.80.0` 全流程实测；四集成均不修改或注入第二规则源入 `AGENTS.md`，“唯一权威”宪法完好；git-wt 双 worktree 严格对照 `parallel-protocol.md` 四铁律（一卡一树、认领走 main、pull 时机、收工三查）全绿通过；Windows 锁与 dispatch.py 误用 `git-wt add` 等 6 项摩擦已登记 improvements 口径（详见 `docs/audits/T-111-specify四集成与git-wt双worktree实操.md` 与末尾补注）。

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
| 展示面 | `board.py` + `board_render.py` + `panel.py` | 要看全局状态的人（只读，不进下游项目） | 500 / 226 / 238 |

- `check.py` 上限最严：它被复制进**每一个**下游项目，是执法面本体。
- `wsc.py` 允许到 1250 的唯一理由是 README 的 `curl` 单文件承诺——装机与开工命令不许散进多个文件；
  **这是最后一次为 `wsc.py` 上调**，之后的新命令**按面归位**：改已实例化项目的指纹/迁移/体检进
  `maintain.py`，晋升审核进 `evolve.py`，只读呈现进展示面（`board.py` 装配 + `board_render.py` 渲染 +
  `panel.py` 终端，拆开是为了让装配那侧不为行数上限压行、渲染能被 unittest 直接吃；2026-09-30
  board.py 顶到 700/700 时按这条拆的，不是抬上限）。已写进 `CONTRIBUTING.md` 的代码约束同步改过。
- 展示面曾经破例带一次 `exec`（载入项目自己的 `scripts/check.py`，为的是卡片口径只有一套）：
  2026-09-29 被安全门按 CWE-95 判成高危拦截提交后改为 `importlib` 固定路径装载 +
  临时关闭字节码写入（照样不留 `__pycache__`），动态执行口子归零，
  由 `test_panel_loads_check_py_without_dynamic_execution` 钉死"零 exec/eval/compile + 一条路径"。
- `evolve.py` / `maintain.py` 只允许 `import wsc` 复用读表与调用形状，不许引入第三方：
  审核与维护都不该成为下游项目的依赖面。
- 计划书对照表里 ADR-7/8/9 的回绝理由不变（copier 走 git URL 取模板与"零网络 + clone 即用"冲突；
  运行时 frontmatter/jsonschema 破分发面；pre-commit 框架装钩子把执法点交给外部工具）。

### ADR-11 · 2026-10-01：委托在协议层，唤醒是无状态的一次性动作

用户要求“tui 正式加入控制面板 + 一键派发任务”。落地时先把边界钉死，免得长成 orca 那样的编排器：

- **委托在协议层**：谁在做哪张卡 = 卡状态 + `claim` 写的 `branch.<分支>.coharness-card` 绑定 + worktree 在场，全在 git 里，不靠旁路数据库。
- **唤醒是无状态的一次性动作**：`dispatch.launch` 认领 → 建工作树 → 开新终端，然后立刻失联——不持有句柄、不读子进程输出、不记运行时状态、不自动重试、不改派。副作用只在这一个函数里，注入替身后可整条断言。
- **越线判据**：把 CoHarness 进程杀掉重启，状态一条都不丢。哪天这条不成立（例如引入了“需要常驻进程才成立”的调度状态），就是越线，先回头改设计而不是加守护进程。
- 新面归位：`dispatch.py` 不随骨架进下游项目（它是库侧门面），行数上限 300；它按设计要拉起子进程，所以不进“禁 `Popen`”那组分发面钉子，但仍在“只引标准库 + 同目录自带模块”与行数/函数棘轮的守卫内。
- 代价：展示面“只读”这条旧承诺作废，改成“默认只读，派发是唯一写路径”（SECURITY.md 第 12 条同改）。定位变更与代价记在 RFC-0003。

### ADR-12 · 2026-10-02：远端门禁随 03 骨架分发，不做服务端，check.py 预算走先例程序

本地 git 钩子可通过 `--no-verify` 绕过，裸克隆在运行 `wsc sync` 前也缺少钩子。对协作者与第二台机器，唯一共同的执法点是远端。落地远端门禁（W19/W20）时的架构取舍与纪律：

- **不做服务端**（优化计划书-v2 §1.3 新纪律）：远端门禁 = 仓库里的 workflow 文件（`.github/workflows/coharness.yml`）+ GitHub Actions 原生能力，绝非 CoHarness 侧的任何在线服务。坚守宪法第 1、2 条（零服务端、文件即真相）。
- **随 03 骨架分发（01/02/04 不带）**：仅 03 涉及多 harness 并行协作与所有权冲突，需要防范多工具互踩；单 harness 骨架不带。仓库若非 GitHub 托管，该 workflow 文件惰性无害（GitLab CI 等价物按能力缺口登记，不在骨架内预置）。
- **两步落地与判定同源**：CI 跑的是项目自己的 `scripts/check.py`，不写第二套判定。零代码版（W19）先立 `--names --tasks` 门禁拦非法看板与坏文件名；W20 以 `--against`（PR 对照 `origin/main`，push 对照 `event.before`）补齐干净树下的 diff 改动挂卡执法；首推/强推基线缺失时发 notice 显式降级至 names+tasks。
- **CI 一律 `--no-track`**：CI runner 上记录 `.agent/telemetry.jsonl` 既无消费意义（无 `wsc stats` 消费端），又会污染干净工作区。
- **`wsc.py` 不加新命令**（优化计划书-v2 §1.3 新纪律）：坚守 `wsc.py` 不随功能增加膨胀命令集的承诺，远端门禁不引入库侧 CLI 新命令。
- **`check.py` 行数 760→820 走先例程序**：为支持 `--against` 基线判定，`check.py` 行数预算从 760 上调至 820（第三次上调）。严格执行先例程序（独立 commit + 预算注释写明理由 + CHANGELOG 记一条），绝不静默上调。
- **不另立 ADR-13**：按前两次上调只记 `LINE_BUDGET` 注释与 CHANGELOG 的先例，行数预算调整不另立 ADR；远端门禁并未改变“执法面单文件随骨架分发”的架构语义，故直接收录于 ADR-12，若未来架构语义改变再行升格。
- 代价与边界：详见 RFC-0004（私有仓消耗少许 Actions 分钟数、仅限 GitHub Actions 原生环境、极端 rebase 下 baseline 按合并基计算）。

### ADR-12 追记（2026-10-03）：merge_group 预置与门禁两级形态

- **merge_group 与最小权限预置**（W24）：骨架 workflow 加 `merge_group`（`types: [checks_requested]`、`branches: [main]`）与顶层 `permissions: contents: read`，actions 引用改版本注释半钉。未启用 merge queue 的仓库该触发器惰性无害；启用 required check + merge queue 后缺它会让 check 永不报告、PR 卡死。基线表达式加第三支 `github.event.merge_group.base_sha`；schema 仍为 5，不另立迁移步。
- **门禁两级形态与 F-A 边界**（W25）：骨架默认只承诺**检测线**（CI 红=可见信号，未配 required check 时不拦 push/合并）；**硬门禁**（required check 绑 `coharness-gate / check`）是用户仓库侧的装机选项，与“认领直推 main”协议有结构性冲突（required check 会拒绝认领提交）——三条出路（bypass actors / 协议改走 PR / 只对 PR 合流分支开）与修正版 rulesets JSON 见 RFC-0004 追记。默认口径：检测线是与直推协议唯一兼容的形态；bypass actors 默认不配。

### ADR-12 追记（2026-10-03 r2）：required check 的 context 是 job 名

- **修正**：上条追记（W25）写的硬门禁 required check context `coharness-gate / check` 有误。T-108 rulesets 真机 A/B 证实：rulesets 的 `required_status_checks.context` 对齐 **check run 的 `name`**；本骨架 job 未写 `name:`，check run 名 = job key = **`check`**。写 `coharness-gate / check` 时合法 PR 的 check 结论 SUCCESS 却 `mergeStateStatus=BLOCKED`，改裸 `check` 后同 PR `CLEAN`。装机 JSON、RFC-0004 硬门禁节、03 `AGENTS.md`、双语 README 已同步改 `check`。ADR 只增不改，故以本条追记覆盖上条的该字面量（机制结论不变）。

## 2026-10-02 补注（T-109 待验项①实测与口径差对齐）

- **待验项①销账**：2026-10-02 完成 W21 / T-109 实操。在系统临时目录沙盒隔离安装 `backlog.md@1.53.0`，真实建卡覆盖引号标题、含 `#` 值、列表（assignees/labels/dependencies）、留空值、冒号标签（`role:tester`）等边界。
  - **兼容性结论**：Backlog CLI 真实产物的扁平 frontmatter 子集与 `check.py` 解析器高度兼容，空列表 `[]`、块列表 `- 项`、单引号包裹值均能正确读出，脱敏后钉入 `tests/fixtures/backlog-real-*`（含独立夹具组 `tests/fixtures/backlog-real/`）。
  - **缺陷暴露**：单引号内若包含 YAML 标准的成对转义单引号 `''`（例如 `title: 'Fix user''s issue'`），`check.py` 当前的 `_strip_comment`（`:75`）由于直接调用 `v.find(v[0], 1)` 在首个单引号处提前截断，导致解析结果变为 `'Fix user'`，剩余内容被误当做注释抛弃。此项属于“解析结果与语义不符（不报错但值错）”，违反 ADR-10 决定 1，已记录缺陷坐标待后续按先例程序修复。
- **README 与 EVOLUTION-PLAN 口径差对齐**：
  - `README.md:173` 折叠区注明的“2026-09-28 真装真跑”系当时装机试用发现的 3 个外部交互坑（默认看板列、`t-<编号>` 认卡命名、`--agent-instructions` 注入）；而 `:167` 记录的“本机不装 backlog”指骨架库本身未作为常驻依赖安装，且卡片 frontmatter 解析器的深层边界兼容性实测此前一直搁置。
  - 本次（2026-10-02）在隔离临时沙盒中完成真装真跑真建卡，两处口径在此对齐：已知坑仍然有效，frontmatter 兼容实测完成销账。

## 2026-10-02 补注（T-111 待验项③④实测销账）

- **待验项③销账（`specify init` 四集成）**：2026-10-02 完成 T-111 实操。在系统临时目录沙盒隔离安装 `specify 1.0.13`，对 `zcode`、`codex`、`qodercli`、`generic` 4 种集成模式运行完整初始化与 git diff 审计。
  - **规则权威性结论**：4 种集成均未向 `AGENTS.md` 注入第二规则源，未篡改已跟踪的任何规则文件（改动数为 0），完全符合“`AGENTS.md` 唯一权威”宪法。
  - **摩擦与处置**：Codex 生成 `.agents/` 目录与骨架 `.agent/` 存在单复数差异，generic 需显式提供 `--commands-dir` 参数，生成的 `.specify/memory/constitution.md` 占位原则需由项目实例化后自 `docs/CONSTITUTION-SOURCE.md` 灌入，均已登记入审计记录。
- **待验项④销账（`git-wt` 双 worktree 并行实操）**：2026-10-02 完成 T-111 实操。在系统临时目录搭建包含中心裸仓库与多 harness 的隔离演练环境，使用 `wt v0.80.0`（Windows 下命令 `git-wt`）进行双卡（T-001/T-002）两工作树完整生命周期推演。
  - **铁律对照结论**：一卡一树（`git-wt switch -c` 创建独立兄弟目录）、认领提交 main（先到先得原子推送）、pull 时机（开工前、认领前、push 前三处写死）、收工三查（I-004 三项检查全绿，0 孤儿树）全部 100% 严密闭环，`check.py` 成功拦截卡外改动与不存在路径。
  - **缺陷取证与处置**：暴露 `dispatch.py:207` 误调不存在的 `git-wt add` 子命令（CLI 真实为 `switch` 等），以及 Windows 下非 shell 集成终端不自动 cd 与跨树文件锁摩擦；均已立案登记入 `docs/audits/T-111-specify四集成与git-wt双worktree实操.md`，不违规越界改动骨架代码。

## 2026-10-02 补注（T-110 待验项②实测与列配置键名核实）

- **待验项②销账**：2026-10-02 完成 W22 / T-110 实操。在系统临时目录沙盒隔离安装 `backlog.md@1.53.0`，全流程运行 `backlog init`、`backlog config list`、`backlog config get <key>`、`backlog config set <key> <val>` 与不同配置位置（`backlog/config.yml` 与 `backlog.config.yml`）核实真实键名与结构。
  - **真实键名结论**：Backlog CLI 唯一有效列配置键名为 `statuses`（在 `config.yml` 中默认形式为 `statuses: ["To Do", "In Progress", "Done"]`，亦兼容块列表 `- 项`）；`columns` 确系 CoHarness 早期自研推测键名，CLI 执行 `backlog config get columns` 明确报错 `Unknown config key: columns`，若在 `config.yml` 中配置 `columns`，Backlog CLI 完全不予识别并静默回落其内部三列默认值。
  - **check.py 执法口径收紧**：此前 `load_config()` 使用 `cols = _yaml_list_under(t, "statuses") or _yaml_list_under(t, "columns")` 宽容回落，不仅容忍了 Backlog CLI 不支持的 `columns` 伪键，而且在配置错误时静默回落默认四列，掩盖配置缺陷。现重构 `check.py:load_config()`：
    1. 唯一读取真键 `statuses`，彻底废止 `columns` 伪键解析；
    2. 当配置文件存在但缺少有效 `statuses` 定义时，将原“静默宽容回落”改为响亮提示（打印 `[配置]` 警告，若含 `columns` 明确提示未知键并指引改为 `statuses`），再回落默认四列；
    3. 修复自定义 `backlog_directory` 时根配置 `backlog.config.yml` 候选路径遗漏问题。
  - **测试与夹具**：真实生成配置产物已脱敏钉入 `tests/fixtures/backlog-real-config-default.yml`、`tests/fixtures/backlog-real-config-custom.yml`、`tests/fixtures/backlog-real-config-root.yml` 及用于响亮提示红绿对照的 `tests/fixtures/backlog-real-config-unknown-key.yml`；`tests/test_check_current.py` 新增 `TestBacklogConfig` 6 条断言（改前 4 红、改后全绿）。


