# 验收对照 — 优化计划书第 7 节的九项指标（截至 2026-09-28）

口径只有一条：**本地能证的给证据，需要外部条件的写明"未成立"**，不混为已交付。
全套自测：`python -m unittest discover -s tests` → **207 条 OK**（skipped=4 为差分预言机用例，
装了 dev extra 后 skipped=0；expected failures=1 是 `I-004`）。

| # | 阶段 | 指标 | 基线 | 目标 | 现在 | 证据 / 缺什么 |
|---|---|---|---|---|---|---|
| 1 | P1 | CI 协议冒烟 | 无 | 全绿（含标注的 xfail） | **本地已绿，Actions 未首跑** | 剧本 `.github/workflows/ci.yml`；本机无 `act`/`docker`，Actions 结果只有 push 后才存在。`tests/test_protocol_smoke.py` 8 条硬断言 + `tests/test_parallel_race.py` 3 硬 1 xfail |
| 2 | P1 | 安装渠道 | git clone only | pipx + Release v1.1.0 | **pip 已实测；pipx 与 Release 待你执行** | `pyproject.toml` + `tests/test_packaging.py` 6 条；干净 venv 里 `pip install --no-build-isolation ./` → `wsc list` / `wsc init 03` 复制 26 文件 / `wsc check` 全绿。pipx 本机未装，未实测；tag 与 Release 属对外动作，我不代办（清单见 `docs/RELEASE-v1.1.0.md`） |
| 3 | P1 | clone → 首次"开工" | 未测 | ≤ 5 分钟（CI 计时） | **本地实测 2.6 秒；CI 计时未做** | 本地路径克隆 → `wsc init 03` → 首次 commit → `wsc sync` 合计 2594 ms（含 init 装钩子）。CI 里的计时步骤没加——要它成立得先有 #1 的 Actions 首跑 |
| 4 | P2 | telemetry / stats | 不可用 | 报告稳定生成，反哺登记门槛 | **已成立** | `tests/test_stats.py` 12 条（写入形状、`--no-track`、`COHARNESS_NO_TRACK`、不进版本库、遵循率算法、只读性、返工信号阈值与跨作者标注、stale 转述、坏行不致命）；反哺通道：`wsc improve --cross` + `evolve.py` 的普遍性取证（`tests/test_registry_cross.py` 10 条、`tests/test_evolve.py` 12 条） |
| 5 | P2 | CHANGELOG 真实晋升 ≥1 条带三证 | 0 条 | ≥1 条带三证 | **已成立（第一条 I-005）** | `docs/CHANGELOG.md` 的 `[晋升 I-005@.coh-pilot-03]` 是第一条带满三证的行（run=trial-20260928-190816，存档 `docs/audits/I-005-所有权表优先.md`），同一条里也如实记下了 `a90cf0c` 先写回后审核的偏差。门禁本身：`evolve.py --verify-record` 要求主观两项 + 四项证据（含用户批准）齐，缺任一即红（`tests/test_evolve.py::test_missing_proof_blocks_promotion`）。更早的 I-001/I-002/I-003 发生在门禁之前，CHANGELOG 只增不改所以不回写 |
| 6 | P2 | 并发 claim：一方失败且干净回滚 | 双写可能 | 一方失败且干净回滚 | **已成立（两层证据）** | 本地：`tests/test_claim.py::test_two_processes_claiming_the_same_card_exactly_one_wins`（真双进程）+ `test_parallel_race::test_b`（worktree 拓扑，xfail 已摘）。外部：`.coh-p4` 两个 `qodercli` 真会话抢同一张卡，a 进 main、b 被拒且未提交未推送（`docs/CHANGELOG.md` 演练取证行、`docs/rfcs/RFC-0001-认领原子化.md`） |
| 7 | P2 | migrate 公开演示项目 1 个 | 无 | 公开演示项目 1 个 | **已成立（脚本 + 实跑记录）** | `docs/demo/migrate_demo.py`（clone 后可直接跑，零网络）+ `docs/DEMO-migrate.md` 的实跑输出；v1→v2→v3 每一步都对应本轮真实改动，含 dry-run 不写盘、备份分支、幂等、拒绝无仓库落盘（`tests/test_maintain.py` 15 条） |
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

## 仍未闭口的（下一轮候选）

- `I-004` 合并后 main 无自动复查：`maintain.py audit` 给了可查面，`evolve.py --apply-check` 覆盖晋升时机；
  **常态提交路径仍靠 integrator 自觉**，服务端钩子或 CI 门禁待议
- `I-005` 所有权表与卡片边界两源：已加裁决句（以表为准、扩权先改表），但**没有执法**，`test_d` 之外仍无人拦
- 契约变更的自动通知：本轮只做只读报告（`sync --dry-run`）。计划书原文要"往他人卡的交接说明写提醒行"，
  这与"他人卡唯一写者是他自己"直接冲突 → 按规则通道登记待议，没有顺手改执法
- pipx 真实安装成功率、Actions 长绿、社区指标：都依赖发布动作，见 `docs/RELEASE-v1.1.0.md` 第三节
