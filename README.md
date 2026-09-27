# CoHarness

> **Co**llaboration across **Harness**es——让任意 AI coding harness（CLI/IDE 智能体）按同一套文件协议组队干活：一个 git 仓库当消息总线，任务卡当邮箱，谁来都能接。

## 30 秒上手

**开一个新合作区**（人跑、或丢给任何 harness 跑都行）：

```bash
git clone https://github.com/MatikaneMeika/CoHarness
python CoHarness/wsc.py init <骨架> <目标路径>      # 骨架: solo / study / multi / doc 或 01-04
```

**之后在项目里对任何 harness 只说一句话：**

```
开工：<任务描述>
```

它就会自动选模式、匹配角色、按流程干活。不想 clone 全库也可以只取工具脚本（建议按 release tag 校验）：

```bash
curl -fsSL https://github.com/MatikaneMeika/CoHarness/raw/main/wsc.py -o wsc.py
python wsc.py init <骨架> <目标路径>
```

## 解决什么问题

跨工具协调没有哪家 harness 厂商会替你做——唯一务实的方案是**文件即真相、git 即总线**。CoHarness 就是这一层"纪律 + 胶水"：

- 项目内 **AGENTS.md 是唯一权威**（绝大多数 harness 原生读取），其他一切只放指针
- 机械环节交给成熟组件：任务卡看板用 **Backlog.md**，规格拆解用 **GitHub Spec Kit**，工作树隔离用 **Worktrunk**
- 自研的只剩成熟工具没有的部分：**单写者所有权**、**路径边界白名单**、**认领冲突与 stale 执法**（check.py + pre-commit，四工具唯一共享执法点）、**自我迭代管线**（用出来的改进经审核写回本体）

## 4 套骨架（选型只看交付物）

| 骨架 | 场景 | 依赖 |
|---|---|---|
| `01-solo-code` | 小游戏、脚本、单组件小工具 | 无 |
| `02-study-office` | 作业/实验/报告交付、备考学习、办公文档（周报/日志/申请材料） | backlog 可选 |
| `03-multi-harness-project` | 多组件全栈项目、多个 AI 并行的大活 | backlog / spec-kit / worktrunk |
| `04-doc-production` | 企划书、报告、论文类**重度**文档生产 | 无 |

03 是完整的"合作区"：单写者所有权表、并行协议（认领进 main 串行化、一 harness 一 worktree、stale 改派、合并纪律）、双门禁、spec-kit 全流程。02/03 的依赖装不上也能开工——工具链都有回落路径（`wsc.py doctor` 自检）。

## 命令速查

```bash
python wsc.py init <骨架> <路径> [--adapter all]  # 实例化；--adapter 生成各工具指针文件
python wsc.py sync <项目>      # 每次开工第一步：pull + 看板摘要 + stale 报告
python wsc.py check <项目>     # 全量体检（命名/卡格式/挂卡/认领冲突）
python wsc.py improve <项目>   # 列出待审的骨架改进
python wsc.py doctor           # 依赖自检，缺啥给安装命令
python wsc.py list             # 骨架列表
```

## 接入任意 harness

| 你的工具 | 接法 |
|---|---|
| 读 AGENTS.md 的（ZCode、Codex、Qoder、opencode、Copilot CLI、Kilo、Trae 等绝大多数） | 项目内**零配置**，开工即生效 |
| 只认自家文件（Claude Code / Gemini-Antigravity / Cursor / Copilot IDE / Windsurf） | `init --adapter claude,gemini,cursor,copilot,windsurf`（或 all）一键生成一行式指针 |
| 支持 skills 的（ZCode / Qoder / Gemini 系） | 可选：把 `skills/collab-zone/` 复制进用户级 skills 目录，改一行 `<WS>` 指向克隆目录——获得跨项目一句话操作 |
| 其他 | 把工具的全局指令文件一行指向本库 `ROUTER.md` 即可 |

原则不变：**AGENTS.md 是唯一权威，指针只指路，不写第二份规则**。冲突裁决顺序：`AGENTS.md / .agent/ > spec-kit 产物 > 任务卡 > 口头约定`。

## 自我迭代（用出来的改进写回本体）

骨架用着不顺手（规则缺口/能力缺口）→ 项目内 `.agent/improvements.md` 登记 → 本项目副本试点 → 对任意 harness 说 **「evolve <项目路径>」**：AI 按 5 条标准（真实性/普遍性/有效性/兼容性/必要性）审核 → **你批准后**写回本体并记入 CHANGELOG。管线与标准见 [docs/EVOLUTION-PROCESS.md](docs/EVOLUTION-PROCESS.md)。

## 安全与数据安全

仓库里只有模板与协议文本，没有用户数据、没有网络请求、没有遥测；wsc.py 的 subprocess 调用全部是字面量参数、文件操作限于项目内。实例化项目的代码与数据归你自己的 git 仓库。详见 [SECURITY.md](SECURITY.md)。

## 文档索引

| 文档 | 内容 |
|---|---|
| [ROUTER.md](ROUTER.md) | 「开工：」调度权威：模式判定 / 骨架选型 / 角色匹配 / 推荐能力 |
| [docs/EVOLUTION-PROCESS.md](docs/EVOLUTION-PROCESS.md) | 自我迭代管线：登记 → 试点 → 审核 → 晋升 |
| [docs/CHANGELOG.md](docs/CHANGELOG.md) | 本体变更日志 |
| [docs/EVOLUTION-PLAN.md](docs/EVOLUTION-PLAN.md) | 设计史：从自研骨架到薄协议层的演进依据 |
| [SECURITY.md](SECURITY.md) | 安全与数据安全边界 |

## 组件选型记录（2026-09-26 核实）

- **Backlog.md** v1.53.0（git 原生 Markdown 任务卡）：无认领锁/stale 检测——由协议层（认领进 main 串行化）+ check.py 补齐
- **GitHub Spec Kit** v1.0.12：/speckit-* 命令族，集成注册表含 40+ agent
- **Worktrunk** 0.79.0（Windows 下 `git-wt`）：worktree 生命周期一条龙
- **排除 Vibe Kanban**：已宣布 sunset，且看板状态存应用本地目录不进仓库，与"文件即真相"冲突

## License

[MIT](LICENSE) © 2026 MatikaneMeika
