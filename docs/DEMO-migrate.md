# DEMO — 把一个 v1 装机的项目升到当前 schema（计划书 W9 的"公开演示项目"）

脚本在仓库里可直接跑：`docs/demo/migrate_demo.py`。它只用本地文件与本地 git，零网络。

```bash
python docs/demo/migrate_demo.py          # 跑完自动清理
python docs/demo/migrate_demo.py --keep   # 保留临时项目，自己进去 git diff
```

演示造的"v1 项目"是**本轮改动之前**的真实形态，不是假数据：

- 文档里的库路径写作 `<骨架库>`（散文占位符，下游猜不出路径 → 命令不可执行）
- 认领条款是 `认领 = -a <标识> -s doing`（手工四步，双认领可被静默覆盖）
- 适配指针是 `.cursorrules` 单文件（各家原生格式之后才是 `.cursor/rules/*.mdc`）
- `.gitignore` 里没有 `.agent/telemetry.jsonl`（本地记账会弄脏工作区）
- 没有「降级行为」节（依赖缺失时行为未定义）

## 实跑输出（2026-09-28，骨架库 commit `431792e`；临时目录路径已省略）

```text
=== v1 演示项目：<临时目录>/03-multi-harness-project

### 第 1 步：记一次装机指纹（schema 由骨架库当前版本决定）

$ python maintain.py lock <临时目录>/03-multi-harness-project
[lock] 已写 <临时目录>/03-multi-harness-project/.agent/skeleton.lock（这份指纹可以提交进项目仓库：不含本机路径）
  skeleton = 03-multi-harness-project
  skeleton_commit = 431792e
  schema = 3
  check_sha256 = 0206fabaccad
### 第 2 步：把指纹改回 schema=1，模拟「这个项目还停在老版本」

$ python maintain.py migrate <临时目录>/03-multi-harness-project
== migrate <临时目录>/03-multi-harness-project（当前 schema=1，本体 schema=3）==

v1 -> v2: 补 .gitignore 的本地记账项 + 代入骨架库绝对路径 + 认领首选 wsc claim + 补降级行为节
  - 待追加：.gitignore 里补 '.agent/telemetry.jsonl'
  - 待改写：.agent/workflows/parallel-protocol.md, AGENTS.md（原本写着 <骨架库>/<CoHarness>）
  - 待改：认领条款首选 wsc claim（原句：'- 认领 = `python <骨架库>/task edit -s do…'）
  - 待补：从 03-multi-harness-project 搬「降级行为」节进 AGENTS.md

v2 -> v3: 适配指针升级为各工具原生目录格式（.cursor/rules、.windsurf/rules），清掉旧单文件
  - 待迁移 .cursorrules → .cursor/rules/coharness.mdc

（dry-run：什么都没写。确认无误再加 --yes，落盘前会自动建备份分支）
（已核对：dry-run 前后 git status 一致，指纹未动）

### 第 3 步：确认后落盘——先自动建备份分支

$ python maintain.py migrate <临时目录>/03-multi-harness-project --yes
== migrate <临时目录>/03-multi-harness-project（当前 schema=1，本体 schema=3）==
[migrate] 已建备份分支 coh-backup-20260928-180536（回到旧状态：git reset --hard coh-backup-20260928-180536）

v1 -> v2: 补 .gitignore 的本地记账项 + 代入骨架库绝对路径 + 认领首选 wsc claim + 补降级行为节
  - 已追加：.gitignore 里补 '.agent/telemetry.jsonl'
  - 已改写：.agent/workflows/parallel-protocol.md, AGENTS.md（原本写着 <骨架库>/<CoHarness>）
  - 已改为：认领条款首选 wsc claim（原句：'- 认领 = `python <骨架库>/task edit -s do…'）
  - 已补：从 03-multi-harness-project 搬「降级行为」节进 AGENTS.md

v2 -> v3: 适配指针升级为各工具原生目录格式（.cursor/rules、.windsurf/rules），清掉旧单文件
  - 已迁移 .cursorrules → .cursor/rules/coharness.mdc
[lock] 已写 <临时目录>/03-multi-harness-project/.agent/skeleton.lock（这份指纹可以提交进项目仓库：不含本机路径）
  skeleton = 03-multi-harness-project
  skeleton_commit = 431792e
  schema = 3
  check_sha256 = 0206fabaccad

[migrate] 已落盘并把 schema 记到 3；改动都在备份分支 coh-backup-20260928-180536 的对照下，回滚：git reset --hard coh-backup-20260928-180536

### 第 4 步：核对结果

  [OK] 旧单文件适配已删除
  [OK] 原生 Cursor 规则已生成
  [OK] .gitignore 已忽略本地记账
  [OK] AGENTS.md 已有降级行为节
  [OK] 文档里的库路径已代入绝对路径
  [OK] 认领句已升级为 wsc claim
  [OK] 指纹记到当前 schema
  备份分支：coh-backup-20260928-180536
  回滚办法：git reset --hard coh-backup-20260928-180536

升级带来的未提交改动：
 M .agent/skeleton.lock
 M .agent/workflows/parallel-protocol.md
 D .cursorrules
 M .gitignore
 M AGENTS.md
?? .cursor/

下一步就是常规提交：git add -A && git commit -m 'migrate v1 -> v3'
```

## 这几条设计是要害

- **默认 dry-run**：升级前先看清动什么；脚本当场核对"dry-run 前后 `git status` 一致、指纹未动"
- **落盘前自动建备份分支**：`coh-backup-<时间戳>`，回滚就是一条 `git reset --hard`
- **非 git 仓库拒绝落盘**：没有备份手段就不写（`tests/test_maintain.py::test_migrate_refuses_yes_without_a_repo`）
- **升级步骤只补真需要的**：没装过适配指针的项目不会被塞进五个新文件
- **幂等**：升到当前 schema 后再跑一次，答案是"已是最新 schema，无升级步骤"
- **步骤是本轮真实改动**：v1→v2 四步与 v2→v3 一步都对应 CHANGELOG 里已有的行，不是为演示编的

对应的自动化证据：`tests/test_maintain.py` 15 条（含 dry-run 不写盘、备份分支、幂等、
无仓库拒绝落盘、v2→v3 不凭空生成、指纹不含本机路径）。
