## 这是什么通道？（删掉不适用的两行）

- **缺陷通道**：代码/执法与文档承诺不符，已附红了的最小复现 → 当场修
- **规则/能力通道**：本 PR 是**晋升审核通过之后**的写回（不是第一次提出；提出走 Issue 或项目登记表）

关联：Issue #____ ／ 登记条目 `I-___` @ `<来源项目>` ／ RFC-____（若是设计取舍）

## 改了什么、为什么

（两三句。写"为什么"和"被牺牲掉的东西"，不要只写文件名。）

## 证据（三证，缺一不得写回本体）

- **diff 位置**：____（文件或 `commit --short` + 行段）
- **来源项目**：____（哪个实例化项目撞到的，`.agent/improvements.md` 的哪一行）
- **测试/CI 运行标识**：____（`evolve.py --apply-check` 打出的 `run=trial-YYYYMMDD-HHMMSS`，或 Actions run id）
- **用户批准**：____（谁在什么时候批的；口头批准要落进 CHANGELOG 行）

## 自测

- [ ] `python -m unittest discover -s tests` 全绿
- [ ] `expected failures` 只减不增（变红=真问题，变绿=该摘 xfail）
- [ ] 带预言机再跑一遍（装了 `python-frontmatter` 的环境，skip 数应为 0）
- [ ] 新命令都补了用例：正常路径 + 拒绝路径 + `--dry-run` 不写盘
- [ ] `python evolve.py --apply-check 本 PR 的补丁.diff` 在临时副本里过（本体没动）

## 口径同步

- [ ] README / SECURITY / 骨架 `AGENTS.md` 里相关说法改成真（不留两套口径）
- [ ] `docs/CHANGELOG.md` 顶部加了一行（`[演进]` / `[缺陷修复]` / `[晋升 I-xxx@来源]`）
- [ ] 来源项目的登记表状态已回写（已晋升 / 已驳回 + 理由）

## 我确认没有

- [ ] 新增第三方依赖，或给 `wsc.py` / `scripts/check.py` 加了网络调用
- [ ] 把卡片 frontmatter 的子集悄悄放宽（要放宽先扩 `tests/test_card_subset.py` 与差分用例）
- [ ] 改动 `docs/CHANGELOG.md` 的历史行
- [ ] 用 `--no-verify` 绕过钩子（绕过就在 reflog 里留痕，audit 会盯）
- [ ] 往 `wsc.py` 加新命令（新命令一律进 `maintain.py`）
