# CoHarness

一套让多个 AI 编码工具（harness）共用同一份约定协作干活的文件模板和小工具。

起因很简单：各家 harness 之间没有官方的协作机制，几个人（或几个工具）同时改一个仓库时，靠的是把约定写成文件放进仓库，大家读同一份。这个库就是我们踩坑之后沉淀下来的那套约定，整理成了四套模板，克隆走就能用。它不是框架，没有服务端，也没有配置中心——仓库里只有 Markdown 和两个几百行的 Python 脚本。

它和一般模板库有个不太一样的地方：**模板不是静态的，带一条改进管线**。用的时候发现哪里不合用，登记、试点、审核，通过的改动会写回模板本体——你的使用经验会沉淀进这套约定，而不是烂在你自己的 fork 里。见下文「会自己进化的模板」。

## 快速开始

```bash
git clone https://github.com/MatikaneMeika/CoHarness
python CoHarness/wsc.py init <骨架> <目标路径>    # 骨架: solo / study / multi / doc，或 01-04
```

然后在项目里对 harness 说「开工：<任务描述>」。它会按项目内 AGENTS.md 里的约定干活。这套约定写一次，之后换工具、换会话都不用重讲。

不想 clone 全库的话，也可以只下载 wsc.py 单文件（建议按 release tag 取，别盲拉 main）：

```bash
curl -fsSL https://github.com/MatikaneMeika/CoHarness/raw/main/wsc.py -o wsc.py
python wsc.py init <骨架> <目标路径>
```

## 会自己进化的模板

大多数模板库是静态的：作者按自己的经验写一版，你遇到不合用的地方，要么忍，要么自己改一份——改完就和上游分叉了。CoHarness 把"改"做成了正式流程，一共四步：

1. **登记**：harness 干活时撞上规则缺口（或缺某个 skill/MCP/依赖），往项目里 `.agent/improvements.md` 记一行。门槛写在文件头部：实际返工过、同类摩擦两次以上、或确有能力缺口，才值得记
2. **试点**：改动先落在这个项目自己的 `.agent/` 里试运行，模板本体不动
3. **审核**：对 harness 说「evolve <项目路径>」，它按五条标准逐条评——真实性、普遍性、有效性、兼容性、必要性——结论是晋升或驳回，逐条给理由
4. **写回**：你批准后，改动才进模板本体，CHANGELOG 记一行，一个改进一个 commit

举个这套库里真实发生过的升级：「交付文件名禁带 `-v2` / `-final`」最初只是一条文字纪律，后来发现光靠提醒没用——文件后缀还是越堆越多——于是它变成 check.py 里的一条正则，由 pre-commit 直接拦截。从"文字提醒"升级到"机械执法"，走的就是上面这条管线。

如果你用的是自己的克隆，改进写回你本地的本体；想回馈上游就发 PR——这个库自己的每次升级也都是这么来的。审核那一关，驳回是一等公民，标准与流程见 [docs/EVOLUTION-PROCESS.md](docs/EVOLUTION-PROCESS.md)。

## 骨架怎么选

按交付物选，一共四套：

| 骨架 | 用在 | 依赖 |
|---|---|---|
| `01-solo-code` | 小工具、脚本 | 无 |
| `02-study-office` | 作业/实验报告、备考刷题、周报一类的文档 | backlog 可选 |
| `03-multi-harness-project` | 多组件项目、几个 AI 工具同时干活 | backlog / spec-kit / worktrunk |
| `04-doc-production` | 多章节、多轮改稿的重文档 | 无 |

依赖装不上也能开工，工具链有回落路径，`wsc.py doctor` 会告诉你缺了什么、怎么装。

03 是最完整的一套，我们自己叫它合作区：谁能动哪些路径有所有权表；几个工具并行时认领动作提交到 main 串行化，一个工具一个 worktree；提交前 pre-commit 会跑 check.py，越权的改动直接被拦。其余几套的纪律大多来自真实教训——文件名带 `-v2`/`-final` 会越堆越多，改稿不回源迟早分叉，实验数据手改过一个数字整份报告就不可信了。

## 日常命令

```bash
python wsc.py sync <项目>      # 开工先跑：pull + 看板摘要 + stale 卡报告
python wsc.py claim <项目> T-001 <标识>  # 原子认领：同步+校验+写卡+提交+推 main 绑成一步，被抢就还原
python wsc.py check <项目>     # 全量体检（命名、卡格式、改动挂卡、认领冲突、边界交集）
python wsc.py improve <项目>   # 列出待审的骨架改进
python wsc.py improve --cross  # 扫本机登记过的全部实例，按同类摩擦出机械计数（晋升门槛 ≥2 次的证据源）
python wsc.py stats <项目>     # 本地运行统计：规则遵循率 / 返工信号 / stale 分布（数据只来自项目内文件与 git log）
python wsc.py doctor           # 依赖自检
python wsc.py list             # 骨架列表
```

仓库自带 138 条自测，跑起来不需要装任何东西：

```bash
python -m unittest discover -s tests     # 零依赖；CI 在 ubuntu/windows × py3.11/3.13 上跑同样的命令
```

覆盖的是承诺本身：check.py 的每条执法（命名、卡格式、认领冲突、改动挂卡、stale）、pre-commit 端到端拦与放、`wsc init` 在各种目标目录下的行为、四套骨架的目录地图与占位符是否自洽。另有一条差分测试拿 `python-frontmatter` 当预言机对照自写解析器——那是开发期的事，没装就自动跳过，不影响上面这条命令，也不进任何骨架。

## 工具怎么接

多数主流 harness 会自动读项目根的 AGENTS.md（ZCode、Codex、Qoder、opencode、Copilot CLI 这些都是）。只认自家文件的工具，init 时加 `--adapter claude,gemini,cursor,copilot,windsurf`（或 all），会生成一行指针文件，内容就一句"读 AGENTS.md，以其为准"。支持 skills 的工具可以选装 `skills/collab-zone/`（复制过去、改一行路径），不装也不影响使用。

出现分歧时的裁决顺序：项目规则 > spec-kit 产物 > 任务卡 > 会话里的口头约定。

## 关于安全

仓库里只有模板和两个纯标准库的 Python 脚本：脚本自身不发任何网络请求（对外连接只走你自己配的 git 远端），subprocess 参数全部是字面量 argv。运行统计（`.agent/telemetry.jsonl`）与本机登记表（`~/.coharness/projects.json`）都只落本地文件、可关可删，位置能用 `COHARNESS_HOME` 挪走；你实例化出来的项目归你自己的仓库，这边不收集也不上传任何东西。边界细节写在 [SECURITY.md](SECURITY.md)。

## 文档与来源

- [ROUTER.md](ROUTER.md) —— 「开工：」的调度逻辑与角色匹配
- [docs/EVOLUTION-PROCESS.md](docs/EVOLUTION-PROCESS.md) —— 改进管线；[docs/CHANGELOG.md](docs/CHANGELOG.md) —— 本体变更日志
- [docs/EVOLUTION-PLAN.md](docs/EVOLUTION-PLAN.md) —— 为什么这么设计（从全自研到借力成熟组件的过程）
- [SECURITY.md](SECURITY.md) —— 安全与数据安全边界

任务卡用 [Backlog.md](https://github.com/MrLesk/backlog.md)，规格拆解用 [GitHub Spec Kit](https://github.com/github/spec-kit)，工作树用 [Worktrunk](https://github.com/max-sixty/worktrunk)（Windows 下命令叫 git-wt），版本按 2026-09-26 核实。Backlog.md 1.53.0 在 2026-09-28 真装真跑过：默认看板列是 `To Do / In Progress / Done`，要用本骨架的四列得改 `backlog/config.yml` 的 `statuses`（`backlog config set` 拒绝直改）；它按 `t-<编号> - <标题>.md` 认卡，手工建的 `T-001.md` 工具不列；`backlog init --agent-instructions` 会往 AGENTS.md 注入它自己的说明，本骨架要求写 `none`。Vibe Kanban 试了解过，已宣布 sunset 且看板数据存在应用目录里不进仓库，放弃。

## License

[MIT](LICENSE) © 2026 MatikaneMeika
