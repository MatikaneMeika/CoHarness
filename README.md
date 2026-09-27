# CoHarness

一套让多个 AI 编码工具（harness）共用同一份约定协作干活的文件模板和小工具。

起因很简单：各家 harness 之间没有官方的协作机制，几个人（或几个工具）同时改一个仓库时，靠的是把约定写成文件放进仓库，大家读同一份。这个库就是我们踩坑之后沉淀下来的那套约定，整理成了四套模板，克隆走就能用。它不是框架，没有服务端，也没有配置中心——仓库里只有 Markdown 和两个几百行的 Python 脚本。

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
python wsc.py check <项目>     # 全量体检（命名、卡格式、改动挂卡、认领冲突）
python wsc.py improve <项目>   # 列出待审的骨架改进
python wsc.py doctor           # 依赖自检
python wsc.py list             # 骨架列表
```

## 工具怎么接

多数主流 harness 会自动读项目根的 AGENTS.md（ZCode、Codex、Qoder、opencode、Copilot CLI 这些都是）。只认自家文件的工具，init 时加 `--adapter claude,gemini,cursor,copilot,windsurf`（或 all），会生成一行指针文件，内容就一句"读 AGENTS.md，以其为准"。支持 skills 的工具可以选装 `skills/collab-zone/`（复制过去、改一行路径），不装也不影响使用。

出现分歧时的裁决顺序：项目规则 > spec-kit 产物 > 任务卡 > 会话里的口头约定。

## 规则会自己进化

模板是死的，用的时候一定会遇到不顺手的地方。约定是：在项目里 `.agent/improvements.md` 记一笔 → 在这个项目里先试点 → 对 harness 说「evolve <项目>」，它会按五条标准（真实性、普遍性、有效性、兼容性、必要性）逐条审，你同意了才把改动写回这套模板本体。驳回很常见，不用勉强凑理由。细节在 [docs/EVOLUTION-PROCESS.md](docs/EVOLUTION-PROCESS.md)。

## 关于安全

仓库里只有模板和两个纯标准库的 Python 脚本：没有网络请求，没有遥测，subprocess 参数全部是写死的字面量，文件操作不出项目目录。你实例化出来的项目归你自己的仓库，这边不收集任何东西。边界细节写在 [SECURITY.md](SECURITY.md)。

## 文档与来源

- [ROUTER.md](ROUTER.md) —— 「开工：」的调度逻辑与角色匹配
- [docs/EVOLUTION-PROCESS.md](docs/EVOLUTION-PROCESS.md) —— 改进管线；[docs/CHANGELOG.md](docs/CHANGELOG.md) —— 本体变更日志
- [docs/EVOLUTION-PLAN.md](docs/EVOLUTION-PLAN.md) —— 为什么这么设计（从全自研到借力成熟组件的过程）
- [SECURITY.md](SECURITY.md) —— 安全与数据安全边界

任务卡用 [Backlog.md](https://github.com/MrLesk/backlog.md)，规格拆解用 [GitHub Spec Kit](https://github.com/github/spec-kit)，工作树用 [Worktrunk](https://github.com/max-sixty/worktrunk)（Windows 下命令叫 git-wt），版本按 2026-09-26 核实。Vibe Kanban 试了解过，已宣布 sunset 且看板数据存在应用目录里不进仓库，放弃。

## License

[MIT](LICENSE) © 2026 MatikaneMeika
