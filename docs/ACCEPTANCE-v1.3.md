# 验收对照 — 优化计划书 v2（W15–W23，截至 2026-10-02）

> **状态：未发布。本地验收中，等待用户批准推送与发布。**

口径只有一条：**本地能证的给证据，需要外部条件的写明"未成立"**，不混为已交付。
全套自测：`python -m unittest discover -s tests` → **全绿**（实跑记录见 §5）。

## §0 基线

- **分支**：`codex/harness-discovery`
- **主干基线**：`main` / `origin/main` = `4ab6d750e6ae6ffe45ecffe2a4cdc90eecc94e92`（`4ab6d75`）
- **本地领先提交数**：`24` 个提交（实跑 `git rev-list --count origin/main..HEAD` 取值）
- **版本号**：`pyproject.toml` 实读为 `1.2.3`（未 bump，保持发布冻结）
- **本地 HEAD**：`ca13acec58db48e2f22ef2af05705b827436e7e7`（`ca13ace`）

## §1 阶段一 W15–W18：发布收口与定位

| 工作项 | 目标 | 状态 | 证据 / 现状 |
|---|---|---|---|
| W15 CI 偶发红取证与闭口 | 连续 10 轮全绿或覆盖 ≥2 周；环境问题成文豁免 | **OPEN（未闭口）** | 取证记录见 `docs/audits/T-101-CI偶发红取证.md`。最近 50 轮 `gh run list` 归因：`success` 28 / `failure` 22，全部 failure 均能对应具名修复提交（无未归因偶发红），但从最新向前连续 success = **1**（机械事实），未达 10 轮判据；本地 24 个提交未推送，CI 从未跑过本批代码，依规保持 open 不予静默豁免。 |
| W16 派发失败路径测试钉子 | 建树失败与认领成功建树失败钉子，行为诚实 | **已闭（本地）** | 提交 `9bcdc98`（建树失败用例注入失败前后红绿可证）+ 提交 `9f8c386`（T-113 废除 `git-wt add` 误调，坚守原生 `git worktree add` 路径契约；`_worktree` 失败 detail 补 `argv` 与 `returncode`，`tests/test_dispatch.py` 40 条全绿，`dispatch.py` 299/300 行未抬上限）。 |
| W17 README 双语定位章节 | 补齐定位层与 Vibe Kanban 迁移注记 | **已闭（本地）** | 提交 `802030a` + `ca13ace`。`README.en.md` 补入 "How CoHarness relates to other tools" 四行详表，`README.md` 中文简版口径一致并双向互链；按机制对比、无星标数字；"Coming from Vibe Kanban?" 迁移注记在位；`tests/test_packaging.py` 钉子通过。 |
| W18 v1.3.0 发布 | PyPI 1.3.0 上线、Release 双资产、CHANGELOG 归档 | **未开始（已冻结）** | 用户明确指令冻结发布（不 push、不 merge、不 bump 版本、不打 tag、不发 Release、不发 PyPI）；`pyproject.toml` 版本保持 `1.2.3`；`docs/CHANGELOG.md` 8 条 `[未发布]` 条目保持不变。 |

### 未闭项与阻塞
- **W15 阻塞**：CI 连续 10 轮绿未满足（当前连续绿=1），受分支尚未推送所限，需等用户批准推送后于远端持续累积运行记录。
- **W18 阻塞**：发布流程处于用户明确冻结状态，等待用户后续发布决策。

## §2 阶段二 W19–W20：远端门禁（两步走）

| 工作项 | 目标 | 状态 | 证据 / 现状 |
|---|---|---|---|
| W19 零改动执法面版 | workflow 进 03 骨架，老项目 migrate 升级 | **已闭（本地）/ 待真机** | 提交 `51d9a08`（新增 `03-multi-harness-project/.github/workflows/coharness.yml`，`pyproject.toml` package-data 逐条写死，`test_packaging.py::test_remote_gate_workflow_is_shipped` 钉住，`test_skeleton_integrity.py` 钉住仅 03 携带）+ 提交 `368af10`（`maintain.py` schema 4→5，`up_remote_gate` 迁移步，四套骨架声明行升至 5，dry-run / `--yes` 迁移演练通过）+ `RFC-0004` 成文 + `ADR-12` 架构决定。真机 run 待推送。 |
| W20 `--against <ref>` 基线 diff 执法 | 干净树下 diff 改动挂卡远端执法，可见降级 | **已闭（本地）/ 待真机** | 提交 `61e655a`（`check.py` 行数预算 760→820 独立 commit 走先例程序）+ 提交 `93f7c98`（`check.py` 新增 `--against <ref>`，判定核心复用，基线缺失响亮失败；03 workflow 升级 PR 用 `origin/main`、push 用 `event.before`，全零/不可达可见降级发 notice；`tests/test_check_current.py::AgainstBaseline` 三类用例：卡外改动被拦、挂卡放行、基线缺失响亮失败；既有用例零改动全绿；`check.py` 现 815/820 行 ≤820）+ 提交 `e1c92b2`（`docs/audits/T-108-远端门禁本地等价验证.md` 本地 bash 等价演练，证明分支选路与真实 check.py 拦截行为成立）。真机 run 待推送。 |

### 未闭项与阻塞
- **W19 / W20 真机 run 阻塞**：GitHub Actions 真实环境的三类用例（非法看板 push 拦、卡外改动 PR 拦、合法 push 绿）需要创建临时 GitHub 仓库并推送测试，当前在本地分支受冻结限制未推远端，等用户批准后在临时仓验证并回填 run 链接。

## §3 阶段三 W21–W23：集成验证清欠

| 工作项 | 目标 | 状态 | 证据 / 现状 |
|---|---|---|---|
| W21 Backlog.md 真实 frontmatter 兼容实测 | 真实 CLI 产物子集边界实测，夹具落地，待验项①销账 | **已闭（本地）** | 提交 `fb610ba` + `0df4c55`。在临时沙盒实装 `backlog.md@1.53.0`，真实建卡覆盖引号标题、含 #、列表、留空、role 标签等多值边界，夹具钉入 `tests/fixtures/backlog-real-*`；发现单引号内 `''` 转义截断缺陷并在 `0df4c55` 修复 `_strip_comment` 与 `_unquote`（`check.py` 807/820）；`docs/audits/T-109-Backlog-frontmatter兼容实测.md` 在位；`docs/EVOLUTION-PLAN.md:118` 待验项①销账；README 折叠区与 EVOLUTION-PLAN 口径差对齐。 |
| W22 backlog.config.yml 列配置键名核实 | 真实键名核实，改读真键，宽容回落改响亮警告 | **已闭（本地）** | 提交 `554b5a7`。在临时沙盒实装 `backlog.md@1.53.0` 实测，Backlog CLI 唯一有效键名为 `statuses`（`columns` 伪键被 CLI 报错且不识别）；`check.py` `load_config` 改读真键 `statuses`，未知键/缺少 statuses 从静默回落改为响亮警告（`[配置]`）；修复自定义 `backlog_directory` 时根配置路径候选；真实配置夹具进 `tests/fixtures/backlog-real-config-*`；`test_check_current.py` 6 条新断言；`check.py` 815/820 行 ≤820；`docs/EVOLUTION-PLAN.md:119` 待验项②销账。 |
| W23 specify init 四集成与 git-wt 双 worktree 实操 | 四集成规格产物审计与双树四铁律实测，待验项③④销账 | **已闭（本地）** | 提交 `42cf62a` + `ca13ace`。在临时沙盒实装 `specify-cli 1.0.13` 与 `wt v0.80.0`（`git-wt`）；specify 四集成（zcode/codex/qodercli/generic）均未篡改或注入第二规则源，宪法唯一权威完好；git-wt 双 worktree 对照 `parallel-protocol.md` 四铁律（一卡一树、认领走 main、pull 时机、收工三查）全绿通过；Windows 锁与 `dispatch.py` 误调 `git-wt add` 等 6 项摩擦记录登记入 improvements 口径；`docs/audits/T-111-specify四集成与git-wt双worktree实操.md` 在位；`docs/EVOLUTION-PLAN.md:120` 待验项③④销账；三个工具版本（`backlog.md@1.53.0`、`specify 1.0.13`、`wt v0.80.0`）同步钉在 `README.md` 与 `README.en.md`。 |

### 未闭项与阻塞
- 本阶段三项全部完成本地闭环与销账，无未闭项与阻塞。

## §4 运营轨：来源项目登记现状

依据自迭代管线（登记 → 试点 → evolve 晋升），对来源项目的 `.agent/improvements.md` 进行只读引用（不改动源项目）：

- **ClassObserver**（`D:\job\ClassObserver\.agent\improvements.md`）：
  - `I-001`（装机布局物理分离：work/ 与 project/ 分离）：状态为「试点中」，尚需在后续项目积累第 2 个独立数据点；
  - `I-002`~`I-005`：状态为「已晋升」（已写回本体并打通测试）；
  - `I-006`（禁止分支反向并 main）与 `I-007`（文本哈希行尾归一 + 钉 LF）：源项目表内为「登记」，本体已于 2026-10-01 吸收晋升。
- **PoseWise**（`D:\job\PoseWise_Health\.agent\improvements.md`）：
  - `I-001`（建 worktree 开工时 `scripts/check.py` 边界路径校验空目录 demo/）：状态为「试点中」；
  - `I-002`（Mimosa 安全门禁全项目扫描误拦提交）：状态为「登记」；
  - `I-003`（卡收尾 `git-wt merge` + `remove` 时 gitignored 交付物丢失）：状态为「登记」。
- **本轮演练摩擦沉淀**：
  - T-111 审计报告沉淀了 6 项改进备忘（`IMP-111-1` 至 `IMP-111-6`），其中 `IMP-111-1`（`dispatch.py` 误调 `git-wt add`）已在 T-113 闭环修复，其余（如 Windows 跨树清理锁、specify generic 参数说明等）作为储备改进项。

### 未闭项与阻塞
- **总控角色数据点不足**：ClassObserver 与 PoseWise 均处于试点/单点阶段，尚未完整跑完 architect 完整总控形态，单点证据不足以触发晋升。
- **I-001 第二数据点**：目前仍仅有 ClassObserver 单一实例，需在下一个真实项目中复验同类需求。

## §5 全量自测

实跑命令：
```bash
python -m unittest discover -s tests
```

实跑结果：
```text
Ran 412 tests in 1118.443s

OK (skipped=6)
```

- **测试总数**：412 条全绿通过，`skipped=6`（差分预言机与环境依赖用例，安装 dev 依赖后不 skip）；
- **耗时**：1118.443s（约 18.6 分钟，包含 `test_evolve.py` 中 `--apply-check` 在临时副本内全套端到端递归自测验证）。
