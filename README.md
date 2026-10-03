# CoHarness

[![CI](https://github.com/MatikaneMeika/CoHarness/actions/workflows/ci.yml/badge.svg)](https://github.com/MatikaneMeika/CoHarness/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/coharness?label=PyPI)](https://pypi.org/project/coharness/)
[![Python](https://img.shields.io/pypi/pyversions/coharness)](https://pypi.org/project/coharness/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

[English](README.en.md) · 中文

一套让多个 AI 编码工具（harness）共用同一份约定协作干活的文件模板和小工具。各家 harness 之间没有官方协作机制——几个人（或几个工具）同时改一个仓库时，靠的是把约定写成文件放进仓库，大家读同一份。这个库就是踩坑之后沉淀下来的那套约定，整理成四套模板，克隆走就能用。

它和一般模板库有四个不太一样的地方：

- **约定就是仓库里的文件**：只有 Markdown 和几个几百行的纯标准库 Python 脚本——没有服务端，没有配置中心，没有运行时依赖
- **纪律是机械执法**：文件命名、卡格式、认领冲突、改动挂卡，由 pre-commit / pre-push 跑 `check.py` 直接拦，不靠提醒
- **模板带改进管线**：用着不顺的地方登记、试点、审核，通过的改动写回模板本体——你的使用经验沉淀进约定，而不是烂在自己的 fork 里
- **有只读看板**：多工具并行时，谁在做什么、做到哪一步、哪张卡报了警，一屏看完

## 快速开始

**方式一：克隆即用**（第一次接触推荐）

```bash
git clone https://github.com/MatikaneMeika/CoHarness
python CoHarness/wsc.py init <骨架> <目标路径>    # 骨架: solo / study / multi / doc，或 01-04
```

然后在项目里对 harness 说「**coharness** <任务描述>」——它会按项目内 AGENTS.md 里的约定干活。这套约定写一次，之后换工具、换会话都不用重讲。

**方式二：装成命令**（想要能直接敲的 `wsc` 和 `coh-panel`）

```bash
pipx install coharness      # 或 pip install coharness；运行期仍零第三方依赖
wsc init 03 ./my-project
```

> **只下载 `wsc.py` 一个文件是不够的**：装机要复制骨架本体，而骨架文件就在 `wsc.py` 旁边。
> 单文件模式能跑的是已在用的项目里的日常命令（sync / check / claim / stats / improve / doctor）；
> `init` 会当场把这条边界说清楚（`git clone` 整库，或 `pipx install coharness`，二选一）。
> 本仓库不联网取模板——那条路会把"clone 即用"换成"运行时依赖远端"（理由见 ADR-10）。

## 骨架怎么选

按交付物选，一共四套：

| 骨架 | 用在 | 依赖 |
|---|---|---|
| `01-solo-code` | 小工具、脚本 | 无 |
| `02-study-office` | 作业/实验报告、备考刷题、周报一类的文档 | backlog 可选 |
| `03-multi-harness-project` | 多组件项目、几个 AI 工具同时干活 | backlog / spec-kit / worktrunk |
| `04-doc-production` | 多章节、多轮改稿的重文档 | 无 |

依赖装不上也能开工，工具链有回落路径：`wsc.py doctor` 会告诉你缺了什么、怎么装、缺着时降级成什么。

03 是最完整的一套，我们自己叫它**合作区**：谁能动哪些路径有所有权表；几个工具并行时认领动作提交到 main 串行化，一个工具一个 worktree；提交前 pre-commit 会跑 check.py，越权的改动直接被拦；03 骨架随带 `.github/workflows/coharness.yml` 远端门禁：本地钩子第一道，CI 检测线第二道——未配 required check 时红是可见信号不是拦截，在仓库 rulesets 里把 `coharness-gate / check` 绑成 required check 才是硬门禁；硬门禁与认领直推有冲突、默认不推荐（详见 [RFC-0004-远端门禁](docs/rfcs/RFC-0004-远端门禁.md)）。其余几套的纪律大多来自真实教训——文件名带 `-v2`/`-final` 会越堆越多，改稿不回源迟早分叉，实验数据手改过一个数字整份报告就不可信了。

## 它和相邻工具怎么摆位

"多个异构 harness 在同一个仓库里不打架" 这一层——路径所有权、认领串行化、改动挂卡、卡边界互斥——目前没有高星项目的成形态实现。CoHarness 占的是个小而空的位：

| 类别 | 状态存哪 | 管什么 | 不管什么 |
|---|---|---|---|
| 编排器（[claude-squad](https://github.com/smtg-ai/claude-squad)、[cmux](https://github.com/mafialink-ai/cmux)、[orca](https://github.com/stablyai/orca) 等） | 各自应用 / 进程侧 | 把多个代理进程隔离并行 | 仓库里的约定：谁能动哪些路径、改动挂不挂卡 |
| 看板工具（Vibe Kanban，见下） | 服务端 + 本地应用库 | 给代理派卡 | 状态不进 git；项目已停止维护 |
| 规范层（[spec-kit](https://github.com/github/spec-kit)、[OpenSpec](https://github.com/Fission-AI/OpenSpec)、[ECC](https://github.com/affaan-m/ECC)、[agents.md](https://github.com/agentsmd/agents.md) 等） | 仓库文件 | 单个代理怎么干活（规格 / 技能 / 规则） | 多个代理之间的边界与冲突 |
| **CoHarness** | 仓库文件 + git | 多个异构 harness 同仓的边界 / 认领 / 执法 | 进程隔离与拉起（留给编排器——共生，非竞争） |

对比表按机制写、不按星数写（星数会腐烂，机制不会）。每个被点名的项目都在用自己的方式描述自己，本节不排名。

### 从 Vibe Kanban 迁来？

[Vibe Kanban](https://github.com/BloopAI/vibe-kanban) 已宣布停止维护（README 横幅原话，末次提交 2026-09-19），未推荐迁移目标。两边的对位人群也重合：要"卡驱动派发"，不要服务端与本地应用库。如果你正符合这种形态，四列语义（`todo / doing / review / done`）可以直接沿用。本仓库的运行统计全部本地、可关可删（`--no-track` / `COHARNESS_NO_TRACK=1`）；状态在 git 里，不在你仓库旁边的某个应用目录里。


## 日常命令

**装机与开工**

```bash
python wsc.py init <骨架> <目标路径> [--minimal]  # 装机；--minimal = 零外部依赖起步（清单走 TODO.md）
python wsc.py list                                # 骨架列表
python wsc.py sync <项目>                         # 开工先跑：pull + 看板摘要 + stale 卡报告
python wsc.py sync <项目> --dry-run               # 不 pull、不出网：报告即将进来的改动碰到哪些契约与在做卡的边界
python wsc.py claim <项目> T-001 <标识>           # 原子认领：同步+校验+写卡+提交+推 main 绑成一步，被抢就还原
python wsc.py check <项目>                        # 全量体检（命名、卡格式、改动挂卡、认领冲突、边界交集）
```

**统计、体检与诊断**

```bash
python wsc.py stats <项目>                # 本地运行统计：遵循率 / 返工信号 / stale 分布（数据只来自项目内文件与 git log）
python wsc.py doctor                      # 依赖自检
python wsc.py doctor --explain backlog,specify           # 这些依赖没装时降级成什么、执法怎么变
python wsc.py doctor --simulate-missing backlog <项目>   # 核对回落产物真在不在位
```

**骨架改进与工具适配**

```bash
python wsc.py improve <项目>              # 列出待审的骨架改进
python wsc.py improve --cross             # 扫本机登记过的全部实例，按同类摩擦出机械计数（晋升门槛 ≥2 次的证据源）
python wsc.py adapters                    # 列出各家工具的适配指针该写在哪
python wsc.py adapters <项目> --verify    # 自检指针还是不是薄指针（有没有变成第二权威）
python wsc.py adapters <项目> --install cursor  # 装机后又来一家工具时补指针
```

**维护与审核**（另两个入口，都不随骨架进下游项目）

```bash
python maintain.py lock    <项目>   # 记装机指纹（骨架名 + 本体 commit + schema + check.py 哈希）
python maintain.py migrate <项目>   # 按 schema 差值升级：默认 dry-run，加 --yes 先建备份分支再落盘
python maintain.py audit   <项目>   # 只读体检：钩子在否/被没被改、指纹漂移、merge 这类不跑钩子的入口、main 合成态合不合法
python evolve.py  <项目> --out 记录.json   # 晋升审核：机器取客观证据，人填有效性与必要性
```

**看板 + 控制台**——谁在做什么、做到哪一步；默认只读，唯一的写路径是派发页（一键把下一个 harness 拉起来）。`pipx install coharness` 之后直接敲 `coh-panel`（`coharness-panel` 是同一个入口的长名字）：

```bash
coh-panel --plain                            # 一次性纯文本：本机装出来的项目 + 在做/待办/报警数
coh-panel --plain --project <项目>            # 直接看某个项目的任务列表（按角色分组，核心角色置顶）
coh-panel                                    # 全屏四页：项目 → 任务 → 卡详情 → 派发（↑↓/Enter/Backspace/d/q）
python panel.py                              # 在克隆里跑同一个入口，不必装机
coh-dispatch --advance <项目>                # 不面板也能派发：认领 + 建工作树 + 开新终端，拉起后失联
                                            # 自动派发默认关闭；用户明确要求开启后收工协议才会自动唤醒
```

- 完成度读卡片里本来就有的 `## 验收清单` 勾选项，佐证读 git 与本地运行记账；两边对不上会直接标出来：`提交了没勾`、`勾了没提交`、`done 但清单未满`、`跨工作树分叉`（同一张卡在不同工作树里状态不一致，`.coh-p2` 演练真出现过）
- 角色从 `AGENTS.md` 的单写者所有权表推，推不到就写"边界没落进所有权表"，不猜
- 终端默认全屏，本机 conhost 花屏就用 `--plain`；要全屏就换给得了 TTY 的终端——Git 自带的 mintty 两条都真机验过：`mintty -e coh-panel`，没装机的克隆里 `mintty -e python <库>\panel.py`
- 设计与否决记录在 [docs/rfcs/RFC-0002-面板展示面.md](docs/rfcs/RFC-0002-面板展示面.md)
- 派发页（任务页按 `d`）：候选 = 依赖就绪、边界不与在做卡冲突的 todo 卡；系统按确定性规则预选（卡号最小），↑↓ 改选，Enter 派发，`m` 只印命令不执行，`r` 原地重试。派发 = 认领 + 建工作树 + 开新终端，拉起后立刻失联（不持有句柄、不读输出、不记运行时状态）。启动命令表在项目侧 `.agent/dispatch.md`（角色 → 命令，支持 `{worktree}`/`{card}` 占位符），缺表只列候选不执行
- 主机 harness 发现：项目侧 `python scripts/dispatch_env.py --json` 只读探测候选与角色命令是否就绪；骨架不预置本机 CLI 名称或路径，由 architect 按本机环境或用户指定登记。自动派发默认关闭，只有用户明确对 architect/integrator 说“开启自动派发/关闭自动派发”后才切换；候选可用不等于自动改派
- 委托与唤醒的边界、被否决的常驻调度器方案、以及“展示面只读”承诺的代价： [docs/rfcs/RFC-0003-委托与唤醒.md](docs/rfcs/RFC-0003-委托与唤醒.md)
- 多 harness 派发从零上手与排错速查（登记候选 / 填命令表 / 只读体检 / 开关自动派发）： [docs/USAGE-多harness派发.md](docs/USAGE-多harness派发.md)

## 会自己进化的模板

大多数模板库是静态的：作者按自己的经验写一版，你遇到不合用的地方，要么忍，要么自己改一份——改完就和上游分叉了。CoHarness 把"改"做成了正式流程，一共四步：

1. **登记**：harness 干活时撞上规则缺口（或缺某个 skill/MCP/依赖），往项目里 `.agent/improvements.md` 记一行。门槛写在文件头部：实际返工过、同类摩擦两次以上、或确有能力缺口，才值得记
2. **试点**：改动先落在这个项目自己的 `.agent/` 里试运行，模板本体不动
3. **审核**：对 harness 说「evolve <项目路径>」，它跑 `python CoHarness/evolve.py <项目> --out 记录.json`——客观那一半（状态机合法性、同类摩擦跨项目计数、证据能不能翻出来、提议落点）由机器取证，有效性与必要性两栏必须有人（或 LLM）填进记录；结论是晋升 / 继续试点 / 驳回，逐条给理由
4. **写回**：晋升候选先 `evolve.py --apply-check 补丁.diff`（临时副本套补丁 + 全套自测 + 新实例复查，红的不许写回），再 `evolve.py --verify-record 记录.json`（主观两栏与四项证据缺一即红）；你批准后改动才进模板本体，CHANGELOG 记一行，一个改进一个 commit

举个这套库里真实发生过的升级：「交付文件名禁带 `-v2` / `-final`」最初只是一条文字纪律，后来发现光靠提醒没用——文件后缀还是越堆越多——于是它变成 check.py 里的一条正则，由 pre-commit 直接拦截。从"文字提醒"升级到"机械执法"，走的就是上面这条管线。

如果你用的是自己的克隆，改进写回你本地的本体；想回馈上游就发 PR——这个库自己的每次升级也都是这么来的。审核那一关，驳回是一等公民，标准与流程见 [docs/EVOLUTION-PROCESS.md](docs/EVOLUTION-PROCESS.md)。

## 工具怎么接

多数主流 harness 会自动读项目根的 `AGENTS.md`，装完即用；只认自家文件的工具，init 时加 `--adapter` 生成**原生格式**的薄指针（内容只有指针与工具元数据，不复制第二份规则，`wsc adapters --verify` 当场查）：

| 工具 | 指针 |
|---|---|
| ZCode、Codex、Qoder、opencode、Copilot CLI 等 | 自动读项目根的 `AGENTS.md`，无需生成 |
| Claude | `CLAUDE.md`（`@AGENTS.md` 导入） |
| Gemini | `GEMINI.md`（`@AGENTS.md` 导入） |
| Cursor | `.cursor/rules/coharness.mdc`（frontmatter 带 `alwaysApply`） |
| Windsurf | `.windsurf/rules/coharness.md`（`trigger: always_on`） |
| Copilot（IDE） | 全局 `.github/copilot-instructions.md` + 路径特定 `.github/instructions/coharness.instructions.md`（YAML 头 `applyTo`） |

装机后又来一家工具时用 `wsc adapters <项目> --install <工具>` 补指针。支持 skills 的工具可以选装 `skills/coharness/`（复制过去、改一行路径），不装也不影响使用。

出现分歧时的裁决顺序：**项目规则 > spec-kit 产物 > 任务卡 > 会话里的口头约定**。

## 自测与质量

仓库自带 417 条自测，跑起来不需要装任何东西：

```bash
python -m unittest discover -s tests     # 零依赖；CI 在 ubuntu/windows/macos × py3.11/3.12/3.13 上跑同样的命令
```

覆盖的是承诺本身：check.py 的每条执法（命名、卡格式、认领冲突、改动挂卡、stale）、面板只读与分叉报警、pre-commit 端到端拦与放、`wsc init` 在各种目标目录下的行为、四套骨架的目录地图与占位符是否自洽。另有一条差分测试拿 `python-frontmatter` 当预言机对照自写解析器——那是开发期的事，没装就自动跳过，不影响上面这条命令，也不进任何骨架。

## 关于安全

仓库里只有模板和几个纯标准库的 Python 脚本：脚本自身不发任何网络请求（对外连接只走你自己配的 git 远端），subprocess 参数全部是字面量 argv。运行统计（`.agent/telemetry.jsonl`）与本机登记表（`~/.coharness/projects.json`）都只落本地文件、可关可删，位置能用 `COHARNESS_HOME` 挪走；你实例化出来的项目归你自己的仓库，这边不收集也不上传任何东西。边界细节写在 [SECURITY.md](SECURITY.md)。

## 文档与来源

- [ROUTER.md](ROUTER.md) —— 「coharness」的调度逻辑与角色匹配
- [CONTRIBUTING.md](CONTRIBUTING.md) —— 三条通道（缺陷 / 规则 / 能力）、登记门槛、晋升门禁、PR 检查清单
- [docs/rfcs/](docs/rfcs/README.md) —— 设计取舍的论证档案（RFC-0001 认领原子化、RFC-0002 面板展示面、RFC-0003 委托与唤醒，均已采纳）
- [docs/EVOLUTION-PROCESS.md](docs/EVOLUTION-PROCESS.md) —— 改进管线；[docs/CHANGELOG.md](docs/CHANGELOG.md) —— 本体变更日志
- [docs/EVOLUTION-PLAN.md](docs/EVOLUTION-PLAN.md) —— 为什么这么设计（从全自研到借力成熟组件的过程）
- [SECURITY.md](SECURITY.md) —— 安全与数据安全边界

任务卡用 [Backlog.md](https://github.com/MrLesk/backlog.md)（1.53.0），规格拆解用 [GitHub Spec Kit](https://github.com/github/spec-kit)（1.0.13），工作树用 [Worktrunk](https://github.com/max-sixty/worktrunk)（0.80.0，Windows 下命令叫 git-wt），三者均经 2026-10-02 隔离沙盒全流程真装真跑核验。

<details>
<summary>第三方工具的已知坑与实测经验（Backlog 1.53.0 / Spec Kit 1.0.13 / Worktrunk 0.80.0，2026-10-02 真装真跑）</summary>

- **Backlog.md**：
  - 默认看板列是 `To Do / In Progress / Done`，要用本骨架的四列得改 `backlog/config.yml` 的 `statuses`（`backlog config set` 拒绝直改）
  - 它按 `t-<编号> - <标题>.md` 认卡，手工建的 `T-001.md` 工具不列
  - `backlog init --agent-instructions` 会往 AGENTS.md 注入它自己的说明，本骨架要求写 `none`
- **Spec Kit**：
  - `specify init` 不篡改 `AGENTS.md`（四集成均 0 篡改已跟踪文件），但会建 `.specify/memory/constitution.md` 骨架；项目实例化后需将 `docs/CONSTITUTION-SOURCE.md` 灌入，维持全局纪律单一源
  - Codex 集成将技能装至 `.agents/skills`（复数），generic 需显式指定 `--commands-dir`
- **Worktrunk**（`git-wt`）：
  - `git-wt switch -c` 开新树位于兄弟目录 `../<repo>.<branch>`；无 shell 挂钩环境下不自动改变终端当前目录，需显式切入
  - Windows 下进程持有工作树句柄时后台清理会延迟，收工合并后需回主工作树执行 `git-wt remove <branch> -y`
  - 命令为 `switch` / `list` / `merge` / `remove`，无 `add` 子命令
- **排除工具**：Vibe Kanban 试了解过：已宣布 sunset 且看板数据存在应用目录里不进仓库，放弃

</details>

## License

[MIT](LICENSE) © 2026 MatikaneMeika
