# 验收对照 — 优化计划书第 7 节的九项指标（截至 2026-09-28）

口径只有一条：**本地能证的给证据，需要外部条件的写明"未成立"**，不混为已交付。
全套自测：`python -m unittest discover -s tests` → **244 条 OK**（skipped=4 为差分预言机用例，
装了 dev extra 后 skipped=0；expected failures=1 是 `I-004`）。

| # | 阶段 | 指标 | 基线 | 目标 | 现在 | 证据 / 缺什么 |
|---|---|---|---|---|---|---|
| 1 | P1 | CI 协议冒烟 | 无 | 全绿（含标注的 xfail） | **根因已定位并修好，转绿待这次 push 的 badge 确认** | 剧本 `.github/workflows/ci.yml`（`on: push` + ubuntu/windows × py3.11/3.13 + oracle job）。原先写"本机无 act/docker，结果只有 push 后才存在"，把"我读不到"当成了"没发生"：仓库是公开的，**状态无需登录就能读**——`curl` 取 `actions/workflows/ci.yml/badge.svg` 实测返回 `failing`，Actions 页共 17 次运行，最新一次对应 `1885195`。差的是 job 级日志：未认证 REST API 被本机出口 IP 限流（403 rate limit），`gh` 又未登录，所以定位根因要先 `gh auth login` 一次。**2026-09-29 追记**：真因不是 Linux，是测试蹭了开发机的全局 git 配置——`test_claim_without_remote_stays_local` 只设 `user.name` 没设 `user.email`，runner 上没全局配置就 `Please tell me who you are` 退出 1，连带 `--apply-check` 门禁的内层全套也红。取证靠公开页面两条事实：oracle job 绿、stdlib 四条腿全红（含 windows/py3.13，本机同版本却绿）。修法除了补 email，还把 `tests/helpers.py` 改成强制封闭 git 环境（`GIT_CONFIG_GLOBAL`/`GIT_CONFIG_SYSTEM` 指向空文件），以后这类依赖开发机配置的测试**本机就会红**，不用等 CI。封闭环境下 244 条 OK。本地两条腿此前也全绿（244 条，零依赖 + 预言机）。`tests/test_protocol_smoke.py` 9 条硬断言 + `tests/test_parallel_race.py` 3 硬 1 xfail |
| 2 | P1 | 安装渠道 | git clone only | pipx + Release v1.1.0 | **pip 与隔离工具安装均已实测；tag 与 Release 待你登录** | `pyproject.toml` + `tests/test_packaging.py` 7 条；干净 venv 里 `pip install --no-build-isolation ./` → `wsc list` / `wsc init 03` 复制 27 文件 / `wsc check` 全绿。本轮补测等价路径：`uv build --wheel` 出 `coharness-1.1.0-py3-none-any.whl` → `uv tool install --from <wheel> coharness`（`UV_TOOL_DIR`/`UV_TOOL_BIN_DIR` 指到 D 盘，不碰 C）→ 装出来的 `wsc list` 列四套骨架、`wsc init 03` 复制 27 个文件（与上面钉住的数一致）、`wsc check` 全部通过 ✓，跑完已卸载并清痕迹。**新加的展示面走同一条路验过**：wheel 里带 `coharness/board.py` 与 `panel.py`、四个入口齐全，在**仓库外的目录**跑 `coharness-panel --plain --project <项目>` rc=0 且正常渲染（相对导入 `from .board import …` 在装出来的包里成立）。**如实分开**：pipx 本体这台机器没有该命令，字面路径仍未验，这条记的是"pipx 的等价隔离安装实测通过"；tag/Release 属对外动作，等 CI 绿再打（红的 commit 上打 tag 等于给发布物挂个已知坏的状态） |
| 3 | P1 | clone → 首次"开工" | 未测 | ≤ 5 分钟（CI 计时） | **本地实测 2.6 秒；CI 计时未做** | 本地路径克隆 → `wsc init 03` → 首次 commit → `wsc sync` 合计 2594 ms（含 init 装钩子）。**这是 2026-09-28 本机单次实测，不是统计量**，换机器换盘就会变，所以不进断言。CI 里的计时步骤没加——要它成立得先有 #1 的 Actions 首跑 |
| 4 | P2 | telemetry / stats | 不可用 | 报告稳定生成，反哺登记门槛 | **已成立** | `tests/test_stats.py` 12 条（写入形状、`--no-track`、`COHARNESS_NO_TRACK`、不进版本库、遵循率算法、只读性、返工信号阈值与跨作者标注、stale 转述、坏行不致命）；反哺通道：`wsc improve --cross` + `evolve.py` 的普遍性取证（`tests/test_registry_cross.py` 10 条、`tests/test_evolve.py` 13 条） |
| 5 | P2 | CHANGELOG 真实晋升 ≥1 条带三证 | 0 条 | ≥1 条带三证 | **已成立（第一条 I-005）** | `docs/CHANGELOG.md` 的 `[晋升 I-005@.coh-pilot-03]` 是第一条带满三证的行（run=trial-20260928-190816，存档 `docs/audits/I-005-所有权表优先.md`），同一条里也如实记下了 `a90cf0c` 先写回后审核的偏差。门禁本身：`evolve.py --verify-record` 要求主观两项 + 四项证据（含用户批准）齐，缺任一即红（`tests/test_evolve.py::test_missing_proof_blocks_promotion`）。更早的 I-001/I-002/I-003 发生在门禁之前，CHANGELOG 只增不改所以不回写 |
| 6 | P2 | 并发 claim：一方失败且干净回滚 | 双写可能 | 一方失败且干净回滚 | **已成立（两层证据）** | 本地：`tests/test_claim.py::test_two_processes_claiming_the_same_card_exactly_one_wins`（真双进程）+ `test_parallel_race::test_b`（worktree 拓扑，xfail 已摘）。外部：`.coh-p4` 两个 `qodercli` 真会话抢同一张卡，a 进 main、b 被拒且未提交未推送（`docs/CHANGELOG.md` 演练取证行、`docs/rfcs/RFC-0001-认领原子化.md`） |
| 7 | P2 | migrate 公开演示项目 1 个 | 无 | 公开演示项目 1 个 | **已成立（脚本 + 实跑记录）** | `docs/demo/migrate_demo.py`（clone 后可直接跑，零网络）+ `docs/DEMO-migrate.md` 的实跑输出；v1→v2→v3 每一步都对应本轮真实改动，含 dry-run 不写盘、备份分支、幂等、拒绝无仓库落盘（`tests/test_maintain.py` 20 条） |
| 8 | P3 | adapters verify：五工具 lint 全过 | 一行字 | 五工具 lint 全过 | **已成立** | `tests/test_adapters.py` 11 条：五家原生位置与语法（`.cursor/rules/*.mdc` 的 `alwaysApply`、`.windsurf/rules/*.md` 的 `trigger: always_on`、`CLAUDE.md`/`GEMINI.md` 的 `@AGENTS.md`、Copilot 纯文本）+ `adapters --verify` 对干净装机 rc=0、对"复制规则正文/缺 frontmatter/旧单文件残留"各判红；语法来源写在 `SOURCES` 里 |
| 9 | P3 | 社区：≥50 star、≥1 外部 PR | 1 star | ≥50 star、≥1 外部 PR | **未成立（需要发布与时间）** | 前置件已就绪：`CONTRIBUTING.md`、Issue/PR 模板、RFC 档案、SECURITY 披露路径。本机登记表当前只有 1 条实例指纹（`.coh-p4/proj`），ADR-3 的"≥50 指纹"重启条件离成立还很远——这一格我不粉饰 |

## 顺手改掉的两处"承诺与实际不符"（本轮主题的直接产出）

- **单文件安装**：`README`/`SECURITY` 曾写"只下载 `wsc.py` 也能 `init` 装骨架"。骨架文件就在 `wsc.py` 旁边，
  单文件根本没有它们 → 现在文档说清边界，`wsc init` 在无骨架目录时直接给出 `git clone` 或
  `pipx install coharness` 两条可执行替代（`tests/test_packaging.py::test_single_file_mode_says_what_it_cannot_do`）。
- **分发面行数与依赖**：`SECURITY` 曾写死"五百行内/实测 544 行"，实际 `check.py` 已 604 行 →
  数字从文档撤掉，改由 `tests/test_distribution_surface.py` 用 AST + 行数上限钉住
  （分发面只用标准库、无网络符号、无 eval/exec；`wsc.py` ≤1250、`check.py` ≤650、
  `evolve.py` ≤400、`maintain.py` ≤700），并断言文档里不许再出现写死的行数。

## 自查后仍存的两处口径差（不粉饰）

计划书某些句子的实现形状与原话不完全一致，记录在此：

- **W6 遥测字段**：原文写 `{ts, harness_id, checks_run, violations, card}`。实现是
  `{ts, harness, checks{names/tasks/diff/stale 各自布尔}, rc, card, ms}`——没记"违规条数"而记"哪几项过没过"，
  因为遵循率按检查项算比按条数算更稳（一条违规可能刷出多行输出）。字段名与 `SECURITY.md` 第 6 条一致。
- **W5 的"与 ROUTER/骨架文件的机械冲突检测"**：实现到的是"提议落点预判 + 落点文件里已有多少行提到同一批路径"
  这一层（`evolve.py` 的 `兼容性提示`），**不是**语义级矛盾判定——真正判断"新条款是否与既有条款打架"仍归五条标准里的
  兼容性一条，由审核人判。要做成语义级检测需要先把规则文本结构化，那是另一件事。

## 仍未闭口的（下一轮候选）

- **CI 是红的**：`ci.yml` 的 badge 实测 `failing`（17 次运行，最新一次是 `1885195`）。本地两条腿全绿而 CI 红，
  差在矩阵环境（ubuntu / py3.11 / 干净 runner 的 git 配置），job 级日志要 `gh auth login` 才读得到——
  这一条排在所有新能力前面：红的 CI 会让上面所有"已证"都带一句存疑
- `I-004` 合并后 main 无自动复查：`maintain.py audit` 给了可查面，`evolve.py --apply-check` 覆盖晋升时机；
  **常态提交路径仍靠 integrator 自觉**，服务端钩子或 CI 门禁待议
- `I-005` 所有权表与卡片边界两源：已加裁决句（以表为准、扩权先改表），但**没有执法**，`test_d` 之外仍无人拦
- 契约变更的自动通知：本轮只做只读报告（`sync --dry-run`）。计划书原文要"往他人卡的交接说明写提醒行"，
  这与"他人卡唯一写者是他自己"直接冲突 → 按规则通道登记待议，没有顺手改执法
- pipx 真实安装成功率、Actions 长绿、社区指标：都依赖发布动作，见 `docs/RELEASE-v1.1.0.md` 第三节
