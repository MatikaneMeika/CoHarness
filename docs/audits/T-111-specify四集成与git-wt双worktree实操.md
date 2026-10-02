# T-111 specify init 四集成与 git-wt 双 worktree 实操记录

> 实施日期：2026-10-02  
> 责任角色：tester（agy / Antigravity CLI 独立实现 harness）  
> 对应计划：`docs/优化计划书-v2.md` T-111 / `docs/EVOLUTION-PLAN.md` 待验项③④  

---

## 1. 实操背景与目标

`docs/EVOLUTION-PLAN.md` 规划的成熟开源组件借力体系中，以下两项待验项自立项以来一直保留未真装真跑：
1. **待验项③**：`specify init` 四个集成（`zcode` / `codex` / `qodercli` / `generic`）真实初始化产物与规则权威性；
2. **待验项④**：`worktrunk`（Windows 环境命令名为 `git-wt`）双 worktree 并行实操与四大铁律（一卡一树、认领走 main、pull 时机、收工三查）全流程闭环验证。

本次实操在系统外部临时隔离目录（`%TEMP%\coharness-t111-sandbox`）中完成真装、真跑、真建树、双 harness 并行全流程推演，真实产物不进仓库，验证后完全清理。

---

## 2. 工具版本钉住

- **specify-cli**：`specify 1.0.13`（通过 `uv tool install specify-cli` 安装与核验）
- **worktrunk**：`wt v0.80.0`（Windows 可执行文件 `git-wt.exe` / `wt.exe`）
- **Git**：`git version 2.47.1.windows.1`
- **Python / 宿主**：Python 3.12 / Windows 11 Pro

---

## 3. specify init 四集成实操记录

在实例化后的标准 `03-multi-harness-project` 骨架项目中，分别对 4 种集成模式运行真实初始化，逐项核对产物、与 `AGENTS.md` 的交互及潜在冲突。

### 3.1 集成 1：`zcode`

- **执行命令**：
  ```powershell
  specify init . --force --integration zcode --non-interactive --ignore-agent-tools
  ```
- **真实产物**：
  - `.specify/`：基础脚手架，包括 `.specify/memory/constitution.md`、`.specify/templates/`（checklist/constitution/plan/spec/tasks 模板）、`.specify/scripts/powershell/`（7 个自动化辅助脚本）、`.specify/integrations/zcode.manifest.json`、`speckit.manifest.json` 等共 17 个文件；
  - `.zcode/skills/`：安装 10 个 Spec Kit 专属技能（`speckit-analyze`、`speckit-checklist`、`speckit-clarify`、`speckit-constitution`、`speckit-converge`、`speckit-implement`、`speckit-plan`、`speckit-specify`、`speckit-tasks`、`speckit-taskstoissues`）。
- **规则源与 AGENTS.md 交互验证**：
  - **已跟踪文件改动为 0**：`git diff` 结果为空，原有 `AGENTS.md`、`.agent/`、`backlog/` 均未被篡改或追加注入；
  - **宪法权威保持**：`specify init` 严格将自身资产收敛在 `.specify/` 与 `.zcode/` 内，未违反“`AGENTS.md` 唯一权威”宪法。
- **冲突点与摩擦**：
  - `.specify/memory/constitution.md` 默认包含 Spec Kit 的通用占位原则（如 `[PRINCIPLE_1_NAME]`），与 CoHarness 项目底稿 `docs/CONSTITUTION-SOURCE.md` 分离。
- **处置方案**：
  - 项目实例化后需由 pm/architect 将 `docs/CONSTITUTION-SOURCE.md` 内容灌入 `/speckit-constitution`（或覆盖 `.specify/memory/constitution.md`），维持裁决顺序：`AGENTS.md / .agent/ > spec-kit constitution > 任务卡 > 口头约定`。

### 3.2 集成 2：`codex`

- **执行命令**：
  ```powershell
  specify init . --force --integration codex --non-interactive --ignore-agent-tools
  ```
- **真实产物**：
  - `.specify/`：同上基础脚手架；
  - `.agents/skills/`：安装 10 个 Spec Kit 技能目录（与 zcode 相同功能集）。
- **规则源与 AGENTS.md 交互验证**：
  - 原有 `AGENTS.md` 完全无改动（`git status --porcelain` 中原有文件无 M 状态）。
- **冲突点与摩擦**：
  - **目录单复数不一致**：Codex 集成默认生成的技能目录为 `.agents/`（复数），而 CoHarness 骨架规范为 `.agent/`（单数）；
  - **所有权表未覆盖**：`AGENTS.md` 单写者所有权表覆盖了 `AGENTS.md`、`.agent/`、`scripts/`，但未显式声明 `.agents/` 或 `.specify/` 的唯一写者归属。
- **处置方案**：
  - 维持架构层级隔离，登记为改进事项；在不改动骨架本体的前提下，Codex harness 读取 `.agents/skills/` 执行规格拆解，而 CoHarness 调度与角色规则依然以 `.agent/` 为唯一准绳。

### 3.3 集成 3：`qodercli`

- **执行命令**：
  ```powershell
  specify init . --force --integration qodercli --non-interactive --ignore-agent-tools
  ```
- **真实产物**：
  - `.specify/`：同上基础脚手架；
  - `.qoder/skills/`：安装 10 个 Spec Kit 技能目录。
- **规则源与 AGENTS.md 交互验证**：
  - 原有 `AGENTS.md` 零修改；所有技能资产位于 `.qoder/skills/`。
- **冲突点与摩擦**：
  - 无规则源冲突；`.qoder/` 目录属于工具专用容器，符合“工具专属容器只放指针与扩展”原则。
- **处置方案**：
  - 放行，登记纳入 `.gitignore` 推荐配置。

### 3.4 集成 4：`generic`（通用 / 自定义 harness，如 Antigravity）

- **执行命令**：
  ```powershell
  specify init . --force --integration generic --integration-options="--commands-dir .myagent/commands/" --non-interactive --ignore-agent-tools
  ```
- **真实产物**：
  - `.specify/`：同上基础脚手架；
  - `.myagent/commands/`：生成 10 个 `.md` 命令提示文件（`speckit.analyze.md`、`speckit.constitution.md`、`speckit.plan.md`、`speckit.specify.md`、`speckit.tasks.md` 等）。
- **规则源与 AGENTS.md 交互验证**：
  - 原有 `AGENTS.md` 零修改。
- **冲突点与摩擦**：
  - `generic` 模式必须通过 `--integration-options` 显式提供 `--commands-dir <路径>`，否则 CLI 在非交互模式下因缺少安全默认值而直接报错中断；
  - 生成物为 Markdown 提示词文件而非可执行脚本，依赖宿主 harness 的 prompt 挂载能力。
- **处置方案**：
  - 在文档与接入指南中固定标注 `--integration-options="--commands-dir <dir>"` 必填项。

---

## 4. worktrunk (git-wt) 双 worktree 并行实操记录

### 4.1 演练架构与环境

- **中心远端**：`%TEMP%\coharness-t111-sandbox\parallel-wt-simulation\origin.git`（裸仓库）
- **本地工作树**：`%TEMP%\coharness-t111-sandbox\parallel-wt-simulation\repo`（main 分支）
- **模拟 Harness A**：`zcode-0926a`，认领任务 `T-001`（Auth 模块，`allowed_paths: [code/auth/]`）
- **模拟 Harness B**：`codex-0926b`，认领任务 `T-002`（Billing 模块，`allowed_paths: [code/billing/]`）
- **并行前提检查**：两卡 `allowed_paths` 完全正交无交集，满足 `.agent/workflows/parallel-protocol.md` 并行前提。

### 4.2 铁律逐条对照核验

| 铁律条目 | 协议要求（parallel-protocol.md） | 实跑动作与命令 | 真实输出/检验结果 | 判定 |
|---|---|---|---|---|
| **1. 一卡一树** | 一个 harness = 一个 worktree，禁止共居同一 clone | `git-wt switch -c feat/T-001-auth`<br>`git-wt switch -c feat/T-002-billing` | 成功创建独立工作树：<br>1) `../repo.feat-T-001-auth`<br>2) `../repo.feat-T-002-billing`<br>`git-wt list` 清晰呈现 3 个工作树共存 | **通过** |
| **2. 认领提交 main** | 认领与状态流转提交必须直接进共享分支 main，先推入为准 | A 认领 T-001 后 `git commit -m "claim T-001"` 并 push main；<br>B 随后 pull main 认领 T-002 并 push main | A 推送后，B 在 pull main 时立即可见 T-001 已处于 doing 状态，B 自觉认领 T-002，避免 owner 碰撞 | **通过** |
| **3. pull 时机** | 开工时、认领前、push 前各 pull 一次（写死三处） | 演练中严格执行开工 pull、认领前 pull、push 前 pull | B 在认领前成功拉取 A 的最新 commit，本地变基无冲突顺利合流 | **通过** |
| **4. 边界执法拦截** | 严禁越权修改 forbidden 路径或卡外路径 | 在 `feat/T-001-auth` 树中尝试改动 `code/billing/hack.py` | `check.py --diff` 当场拦截：`[改动挂卡] code/billing/hack.py 只被未认领的卡覆盖（T-002.md 仍为 todo）` | **通过** |
| **5. 串行合并与 rebase** | 进 main 一次一人，先到先得；后到者 rebase 到最新 main 再合并；**禁止在分支侧反向 merge main** | A 先完成：更新 T-001 为 done，合并并 push main；<br>B 后完成：在 `feat/T-002-billing` 树执行 `git fetch origin` + `git rebase origin/main`，回 main 树合并后 push | B rebase 顺利应用变更，未进行分支侧反向 merge，保持干净线性提交历史并通过 check.py | **通过** |
| **6. 收工三查 (I-004)** | ① `git status --short` 为空<br>② `git rev-parse HEAD == origin/main`<br>③ `git-wt list` 无本卡孤儿树 | 1) A 收工运行 `git-wt remove feat/T-001-auth -y`<br>2) B 收工运行 `git-wt remove feat/T-002-billing -y` | A 收工时：三查全绿，仅剩 main 与 B 树；<br>B 收工时：三查全绿，`git-wt list` 仅剩 `@ main`，0 孤儿树 | **通过** |

### 4.3 实测发现的关键摩擦点（UX / Windows 特性 / 代码缺陷）

1. **摩擦 1：无 shell 集成时 `git-wt switch -c` 不改变终端当前工作目录**
   - **现象**：执行 `git-wt switch -c feat/xxx` 时打印提示：
     `▲ Cannot change directory — shell integration not installed. ↳ To enable automatic cd, run wt config shell install`
   - **影响**：当前 PowerShell/终端会话的当前目录仍留在主项目目录！如果调用者未加察觉直接写代码，改动会直接写进主工作树而非新工作树。
   - **处置**：脚本或 harness 必须显式通过路径（如 `../<repo>.<slug>` 或解析 `git-wt list` 路径）切换工作目录。

2. **摩擦 2：Windows 下进程句柄占用导致工作树延迟清理与后台锁**
   - **现象**：当命令行当前目录位于某 worktree 内部时，在该目录内执行 `git-wt merge` 虽然能合并，但因 Windows 对当前工作目录持有句柄锁，导致底层 worktree 目录删除被转入后台/延迟，`git-wt list` 仍可能显示该树带有 `⊂` 符号。
   - **处置**：收工合并必须遵照协议“回到主工作树目录”，再运行 `git-wt remove <branch> -y`，即可一次性彻底删除。

3. **摩擦 3：库侧 `dispatch.py:207` 误调不存在的 `git-wt add` 命令**
   - **现象**：审查 `dispatch.py` 发现第 207 行写为：
     `argv = (["git-wt", "add", "-b", f"coh/{card}", str(path)] if which("git-wt") else ...)`
     而在终端真实执行 `git-wt add` 响亮报错：`error: unrecognized subcommand 'add'`。`worktrunk` 0.80.0 的子命令只有 `switch`、`list`、`remove`、`merge`、`step`、`hook`、`config`，没有 `add`。
   - **处置**：由于本任务 Brief 严格禁止修改 `dispatch.py`（属于硬约束），本报告记录此缺陷坐标与现场证据，登记入 improvements 口径，待后续规则/代码通道修复。

4. **摩擦 4：`check.py` 强制要求卡片边界路径物理存在**
   - **现象**：在新建卡片声明 `allowed_paths: [code/auth/]` 时，若该目录未被 git 跟踪或在新检出分支上未被创建，`check.py` 会直接报错拦截：`边界路径不存在: code/auth/`。
   - **处置**：建卡规划路径后，应在基线提交中放置 `.gitkeep` 或由脚手架统一创建占位目录，防止空目录在不同 worktree 间丢失。

---

## 5. improvements 口径登记汇总

依据任务要求，将实操中发现的非阻断性摩擦统一沉淀为 improvements 备忘（不直接修改骨架）：

| 编号 | 模块 | 现象与成因 | 建议处置方向 |
|---|---|---|---|
| **IMP-111-1** | `dispatch.py` | `:207` 使用了 `git-wt add`，真实 worktrunk 0.80.0 无此子命令导致 rc=1 | 后续通道将 `git-wt add` 修正为原生 `git worktree add` 或适配 `git-wt switch -c` |
| **IMP-111-2** | `worktrunk` | `git-wt switch -c` 在缺少 shell integration 时不切换终端 CWD | 在 `parallel-protocol.md` 中增加显式 `cd` 提示，或由 `wsc` 包装层代执行目录切换 |
| **IMP-111-3** | `worktrunk` | Windows 下工作树内部执行清理受目录文件句柄锁定影响 | 强化“收工一律切回 main 主工作树执行 remove”的操作铁律 |
| **IMP-111-4** | `specify-cli` | `codex` 模式生成 `.agents/` 目录，与骨架 `.agent/` 单复数差异 | 所有权表或 `.gitignore` 补充 `.agents/` 与 `.specify/` 推荐规则 |
| **IMP-111-5** | `specify-cli` | `generic` 模式非交互下缺少 `--commands-dir` 会报错中断 | 在接入说明与文档中明确标注通用集成参数样例 |
| **IMP-111-6** | `check.py` | 任务卡边界路径若在 worktree 中因空目录未跟踪而不存在，会导致 `边界路径不存在` 拦截 | 建议在 `wsc init` 或建卡指引中强调使用 `.gitkeep` 保持边界目录存在 |

---

## 6. 验收清单与销账结论

- [x] **EVOLUTION-PLAN 待验项③销账**：`specify init` 四集成（`zcode` / `codex` / `qodercli` / `generic`）实操完成，确认不篡改、不注入 `AGENTS.md`，宪法唯一权威完好；
- [x] **EVOLUTION-PLAN 待验项④销账**：`worktrunk`（`wt v0.80.0`）双 worktree 实操完成，一卡一树、认领走 main、pull 时机、收工三查 100% 闭环通过；
- [x] **实操记录落地**：已详细记入本审计文档 `docs/audits/T-111-specify四集成与git-wt双worktree实操.md`；
- [x] **README 版本注记同步**：同步更新 `README.md` 版本说明，自测条数行 398 严格保持不变；
- [x] **系统临时沙盒清理**：`%TEMP%\coharness-t111-sandbox` 已彻底删除，工作区与宿主环境零污染。
