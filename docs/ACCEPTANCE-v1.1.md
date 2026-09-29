# 验收对照 — 优化计划书第 7 节的九项指标（截至 2026-09-29）

口径只有一条：**本地能证的给证据，需要外部条件的写明"未成立"**，不混为已交付。
全套自测：`python -m unittest discover -s tests` → **254 条 OK**（skipped=4 为差分预言机用例，
装了 dev extra 后 skipped=0；expected failures 已清零——I-004 于 2026-09-29 由 pre-push 推送门闭口）。

| # | 阶段 | 指标 | 基线 | 目标 | 现在 | 证据 / 缺什么 |
|---|---|---|---|---|---|---|
| 1 | P1 | CI 协议冒烟 | 无 | 全绿（含标注的 xfail） | **已成立：run #33（`bcddc3a`）五条腿全绿，badge 实测 `passing`** | 剧本 `.github/workflows/ci.yml`（`on: push` + ubuntu/windows × py3.11/3.13 + oracle job）。原先写"本机无 act/docker，结果只有 push 后才存在"，把"我读不到"当成了"没发生"：仓库是公开的，**状态无需登录就能读**——`curl` 取 `actions/workflows/ci.yml/badge.svg` 实测 `badge.svg` 返回 `failing`（当时 17 次运行）。job 级日志确实要登录（未认证 REST 被本机出口 IP 限流），但**失败测试名不用登录也能拿到**：CI 步骤在 `rc≠0` 时发 `::error::` annotation，公开运行页把 annotation 渲染出来，`curl` 就能读——最终定位就是靠它。**2026-09-29 追记**：真因不是 Linux，是测试蹭了开发机的全局 git 配置——`test_claim_without_remote_stays_local` 只设 `user.name` 没设 `user.email`，runner 上没全局配置就 `Please tell me who you are` 退出 1，连带 `--apply-check` 门禁的内层全套也红。取证靠公开页面两条事实：oracle job 绿、stdlib 四条腿全红（含 windows/py3.13，本机同版本却绿）。修法除了补 email，还把 `tests/helpers.py` 改成强制封闭 git 环境（`GIT_CONFIG_GLOBAL`/`GIT_CONFIG_SYSTEM` 指向空文件），以后这类依赖开发机配置的测试**本机就会红**，不用等 CI。封闭环境下全套 OK。本地两条腿此前也全绿（零依赖 + 预言机）。`tests/test_protocol_smoke.py` 9 条硬断言 + `tests/test_parallel_race.py` 3 硬 1 xfail。**第二段红只在 windows 两条腿**（annotation 直接报名：`test_registry_cross` 三条 + `test_hook_install::test_linked_worktree_gets_shared_hook` + 被连带的 `test_evolve::test_apply_check_passes_a_doc_only_patch`）：runner 的 `TEMP` 是 8.3 短名 `C:\Users\RUNNER~1\…`，而 `wsc init` 存 `resolve()` 展开后的长名（本机实测 `Path('C:\PROGRA~1').resolve()` → `C:\Program Files`），测试拿短名比字符串恒假；`--apply-check` 那条是连带——门禁在临时副本里跑全套，内层一红外层就红。修在测试侧（比对一律先 `resolve()`），并补 `H.short_path()`（`GetShortPathNameW`）造出同样条件的新钉子，本机真跑不 skip。**判绿证据**：run #33 的四条测试腿都在 annotation 里出现过、`::error::` 为 0（步骤只在 `rc≠0` 才发），badge 同期返回 `passing` |
| 2 | P1 | 安装渠道 | git clone only | pipx + Release v1.1.0 | **pip 与隔离工具安装均已实测；tag 与 Release 待你登录** | `pyproject.toml` + `tests/test_packaging.py` 7 条；干净 venv 里 `pip install --no-build-isolation ./` → `wsc list` / `wsc init 03` 复制 28 文件 / `wsc check` 全绿。本轮补测等价路径：`uv build --wheel` 出 `coharness-1.1.0-py3-none-any.whl` → `uv tool install --from <wheel> coharness`（`UV_TOOL_DIR`/`UV_TOOL_BIN_DIR` 指到 D 盘，不碰 C）→ 装出来的 `wsc list` 列四套骨架、`wsc init 03` 复制 28 个文件（与上面钉住的数一致）、`wsc check` 全部通过 ✓，跑完已卸载并清痕迹。**新加的展示面走同一条路验过**：wheel 里带 `coharness/board.py` 与 `panel.py`、四个入口齐全，在**仓库外的目录**跑 `coharness-panel --plain --project <项目>` rc=0 且正常渲染（相对导入 `from .board import …` 在装出来的包里成立）。**如实分开**：pipx 本体这台机器没有该命令，字面路径仍未验，这条记的是"pipx 的等价隔离安装实测通过"；tag/Release 属对外动作，约定等 CI 绿再打——**CI 于 run #33/#34 连续判绿，tag 已打：`v1.1.0` → `4374015`（远端 ref 已推，`git ls-remote --tags` 可查）**；GitHub Release 仍要 `gh auth login`（未登录建不了），PyPI 归你（要你的 API token） |
| 3 | P1 | clone → 首次"开工" | 未测 | ≤ 5 分钟（CI 计时） | **runner 实测已回填：ubuntu 2140 ms、windows 2228 ms（上限 300000 ms）** | 本地路径克隆 → `wsc init 03` → 首次 commit → `wsc sync` 合计 2594 ms（含 init 装钩子）。**这是 2026-09-28 本机单次实测，不是统计量**，换机器换盘就会变，所以不进断言。CI 里的计时步骤本轮补上了（`ci.yml` 的 `first-run` job：装机→首次提交→sync 全程计时，>5 分钟判红，实测值发 notice）；本机把抽出来的脚本原样跑过一遍 = 1076 ms、`wsc check` 通过、rc=0。runner 上的数取 run #34（`4374015`，也就是 v1.1.0 指的 commit）的 annotation：ubuntu 2140 ms、windows 2228 ms |
| 4 | P2 | telemetry / stats | 不可用 | 报告稳定生成，反哺登记门槛 | **已成立** | `tests/test_stats.py` 12 条（写入形状、`--no-track`、`COHARNESS_NO_TRACK`、不进版本库、遵循率算法、只读性、返工信号阈值与跨作者标注、stale 转述、坏行不致命）；反哺通道：`wsc improve --cross` + `evolve.py` 的普遍性取证（`tests/test_registry_cross.py` 11 条、`tests/test_evolve.py` 13 条） |
| 5 | P2 | CHANGELOG 真实晋升 ≥1 条带三证 | 0 条 | ≥1 条带三证 | **已成立（第一条 I-005）** | `docs/CHANGELOG.md` 的 `[晋升 I-005@.coh-pilot-03]` 是第一条带满三证的行（run=trial-20260928-190816，存档 `docs/audits/I-005-所有权表优先.md`），同一条里也如实记下了 `a90cf0c` 先写回后审核的偏差。门禁本身：`evolve.py --verify-record` 要求主观两项 + 四项证据（含用户批准）齐，缺任一即红（`tests/test_evolve.py::test_missing_proof_blocks_promotion`）。更早的 I-001/I-002/I-003 发生在门禁之前，CHANGELOG 只增不改所以不回写 |
| 6 | P2 | 并发 claim：一方失败且干净回滚 | 双写可能 | 一方失败且干净回滚 | **已成立（两层证据）** | 本地：`tests/test_claim.py::test_two_processes_claiming_the_same_card_exactly_one_wins`（真双进程）+ `test_parallel_race::test_b`（worktree 拓扑，xfail 已摘）。外部：`.coh-p4` 两个 `qodercli` 真会话抢同一张卡，a 进 main、b 被拒且未提交未推送（`docs/CHANGELOG.md` 演练取证行、`docs/rfcs/RFC-0001-认领原子化.md`） |
| 7 | P2 | migrate 公开演示项目 1 个 | 无 | 公开演示项目 1 个 | **已成立（脚本 + 实跑记录）** | `docs/demo/migrate_demo.py`（clone 后可直接跑，零网络）+ `docs/DEMO-migrate.md` 的实跑输出；v1→v2→v3 每一步都对应本轮真实改动，含 dry-run 不写盘、备份分支、幂等、拒绝无仓库落盘（`tests/test_maintain.py` 20 条） |
| 8 | P3 | adapters verify：五工具 lint 全过 | 一行字 | 五工具 lint 全过 | **已成立** | `tests/test_adapters.py` 11 条：五家原生位置与语法（`.cursor/rules/*.mdc` 的 `alwaysApply`、`.windsurf/rules/*.md` 的 `trigger: always_on`、`CLAUDE.md`/`GEMINI.md` 的 `@AGENTS.md`、Copilot 纯文本）+ `adapters --verify` 对干净装机 rc=0、对"复制规则正文/缺 frontmatter/旧单文件残留"各判红；语法来源写在 `SOURCES` 里 |
| 9 | P3 | 社区：≥50 star、≥1 外部 PR | 1 star | ≥50 star、≥1 外部 PR | **暂缓（2026-09-29 起：当前单用户，目标数字不撤）** | 前置件已就绪：`CONTRIBUTING.md`、Issue/PR 模板、RFC 档案、SECURITY 披露路径。本机登记表当前只有 1 条实例指纹（`.coh-p4/proj`），ADR-3 的"≥50 指纹"重启条件离成立还很远——用户裁定暂缓：这个工具目前只有本机在用，重启条件=对外发布后出现真实协作者 |

## 顺手改掉的两处"承诺与实际不符"（本轮主题的直接产出）

- **单文件安装**：`README`/`SECURITY` 曾写"只下载 `wsc.py` 也能 `init` 装骨架"。骨架文件就在 `wsc.py` 旁边，
  单文件根本没有它们 → 现在文档说清边界，`wsc init` 在无骨架目录时直接给出 `git clone` 或
  `pipx install coharness` 两条可执行替代（`tests/test_packaging.py::test_single_file_mode_says_what_it_cannot_do`）。
- **分发面行数与依赖**：`SECURITY` 曾写死"五百行内/实测 544 行"，实际 `check.py` 已 604 行 →
  数字从文档撤掉，改由 `tests/test_distribution_surface.py` 用 AST + 行数上限钉住
  （分发面只用标准库、无网络符号、无 eval/exec；`wsc.py` ≤1250、`check.py` ≤700、
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

- ~~CI 是红的~~ **已闭口（2026-09-29）**：run #33（`bcddc3a`） ubuntu×2 + windows×2 + oracle 五条腿全绿，
  badge 实测 `passing`。红是分两层露出来的——第一层全局 git 配置（四条 stdlib 腿全红），第二层 8.3 短名
  `TEMP`（只红 windows）。两轮都靠"只在失败时发的 `::error::` annotation"定位，不需要登录
- ~~`I-004` 合并后 main 无自动复查~~ **已闭口（2026-09-29）**：merge/rebase 不跑 pre-commit，两个各自合法的提交合出来的非法看板，由 **pre-push 推送门**在推送前拦下——新骨架钩子 `scripts/hooks/pre-push` 跑 `check.py --tasks`，`wsc init` 直接装、`wsc sync` 顺手补装；`tests/test_parallel_race.py::test_d` 从 expectedFailure 转正，真造"旧基合法认领 → merge 凑出同人两张 doing → 推送被拦"全程；CI 新增 `push-gate` job 在干净 runner 上端到端重演（本地已按"`set -e -o pipefail` 下验"的纪律先行验证）。`maintain.py audit` 仍是事后体检面，`--apply-check` 仍是晋升时复查
- ~~`I-005` 所有权表与卡片边界两源~~ **机械核已落地（2026-09-29）**：`check.py` 在提交时对表里"具体路径 + 具体角色"的行，核对覆盖它的在做卡有没有 `role:<角色>` 标签（角色由卡声明，对应"同一会话可身兼多角"），扩权响亮失败并拦提交；重命名的旧路径也过表，改名逃不掉。模板行与散文写者行判不了，如实报数留给审核人——宁少判，不诬判。钉子：`tests/test_check_diff.py::OwnershipGate` 四条（拦/放行/宽卡不碰辖地/改名旧路）+ `test_protocol_smoke::test_i` 从"钉住未执法"反转为"钉住已执法"，4 条旧夹具（本就在演扩权）补上 `role:architect` 标签
- ~~契约变更的自动通知~~ **已注销（2026-09-29）**：只读报告（`sync --dry-run`）保留；计划书原文要"往他人卡的交接说明写提醒行"，这与"他人卡唯一写者是他自己"直接冲突，否决维持；且当前单用户、无对端可通知——重启条件：本机出现第二个真实协作者
- pipx 真实安装成功率、Actions **长绿**（首跑已成立，见 #1）：发布后的数据，见 `docs/RELEASE-v1.1.0.md` 第三节；社区指标（指标 9）2026-09-29 起暂缓（单用户），重启条件=对外发布后出现真实协作者
