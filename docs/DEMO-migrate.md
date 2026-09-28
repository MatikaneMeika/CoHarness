# DEMO — 把一个 v1 装机的项目升到当前 schema（计划书 W9 的"公开演示项目"）

脚本在仓库里可直接跑：`docs/demo/migrate_demo.py`。它只用本地文件与本地 git，零网络。

```bash
python docs/demo/migrate_demo.py          # 跑完自动清理，并逐条核对结果
python docs/demo/migrate_demo.py --keep   # 保留临时项目目录，自己进去 git diff
```

演示造的"v1 项目"是**本轮改动之前**的真实形态，不是假数据（七项遗留各对应一条升级步骤）：

- 文档里的库路径写作 `<骨架库>`（散文占位符，装机后下游猜不出路径，命令不可执行）
- 认领条款是 `认领 = -a <标识> -s doing`（手工四步，双认领可被静默覆盖）
- 适配指针是 `.cursorrules` 单文件（各家原生格式之后才是 `.cursor/rules/*.mdc`）
- `.gitignore` 里没有 `.agent/telemetry.jsonl`（本地记账会弄脏工作区）
- 没有「降级行为」节（依赖缺失时行为未定义）
- `backlog/tasks/T-000-board.md` 常驻规则卡还挂着（I-001 晋升后它是反模式）
- `backlog/config.yml` 是 `columns: [To Do, In Progress, Done]`（真工具默认英文三列，`-s doing` 会被拒）
- `scripts/check.py` 是 I-001 之前那版，不认识自授权（认领与登记会被自己锁死）
- 项目卡里没有 `| 骨架 schema | N |` 声明行

## 实跑输出（2026-09-28，骨架库 commit 见输出内的 skeleton_commit；临时目录与时间戳已隐去）

```text
=== v1 演示项目：C:\Users\666666\AppData\Local\Temp\<临时目录>\03-multi-harness-project

### 第 1 步：记一次装机指纹（schema 由骨架库当前版本决定）

$ python maintain.py lock C:\Users\666666\AppData\Local\Temp\<临时目录>\03-multi-harness-project
[lock] 已写 C:\Users\666666\AppData\Local\Temp\<临时目录>\03-multi-harness-project\.agent\skeleton.lock（这份指纹可以提交进项目仓库：不含本机路径）
  skeleton = 03-multi-harness-project
  skeleton_commit = 5f85a02
  schema = 3
  check_sha256 = ea91e416249b
### 第 2 步：把指纹改回 schema=1，模拟「这个项目还停在老版本」

$ python maintain.py migrate C:\Users\666666\AppData\Local\Temp\<临时目录>\03-multi-harness-project
== migrate C:\Users\666666\AppData\Local\Temp\<临时目录>\03-multi-harness-project（当前 schema=1←指纹，本体 schema=3）==

v1 -> v2: 本地记账进 .gitignore + 库路径代入绝对值 + 认领首选 wsc claim + 补降级行为节 + 删常驻卡 + 看板列改四列 statuses + 刷新缺自授权的旧 check.py
  - 待追加：.gitignore 里补 '.agent/telemetry.jsonl'
  - 待改写：.agent/workflows/parallel-protocol.md, AGENTS.md（原本写着 <骨架库>/<CoHarness>）
  - 待改：认领条款首选 wsc claim（原句：'- 认领 = `python <骨架库>/task edit -s do…'）
  - 待补：从 03-multi-harness-project 搬「降级行为」节进 AGENTS.md
  - 待删除：backlog/tasks/T-000-board.md（常驻卡作废，见 I-001）
  - 待改写：backlog/config.yml → statuses: [todo, doing, review, done]（真工具默认 To Do/In Progress/Done，不改则 `-s doing` 被拒）
  - 待刷新：scripts/check.py 是 I-001 之前的旧版，缺自授权（会锁死认领与登记）；其余差异不自动覆盖，由 audit 报漂移

v2 -> v3: 适配指针升级为各工具原生目录格式（.cursor/rules、.windsurf/rules），清掉旧单文件
  - 待迁移 .cursorrules → .cursor/rules/coharness.mdc

（dry-run：什么都没写。确认无误再加 --yes，落盘前会自动建备份分支）
（已核对：dry-run 前后 git status 一致，指纹未动）

### 第 3 步：确认后落盘——先自动建备份分支

$ python maintain.py migrate C:\Users\666666\AppData\Local\Temp\<临时目录>\03-multi-harness-project --yes
== migrate C:\Users\666666\AppData\Local\Temp\<临时目录>\03-multi-harness-project（当前 schema=1←指纹，本体 schema=3）==
[migrate] 已建备份分支 coh-backup-<时间戳>（回到旧状态：git reset --hard coh-backup-<时间戳>）

v1 -> v2: 本地记账进 .gitignore + 库路径代入绝对值 + 认领首选 wsc claim + 补降级行为节 + 删常驻卡 + 看板列改四列 statuses + 刷新缺自授权的旧 check.py
  - 已追加：.gitignore 里补 '.agent/telemetry.jsonl'
  - 已改写：.agent/workflows/parallel-protocol.md, AGENTS.md（原本写着 <骨架库>/<CoHarness>）
  - 已改为：认领条款首选 wsc claim（原句：'- 认领 = `python <骨架库>/task edit -s do…'）
  - 已补：从 03-multi-harness-project 搬「降级行为」节进 AGENTS.md
  - 已删除：backlog/tasks/T-000-board.md（常驻卡作废，见 I-001）
  - 已改写：backlog/config.yml → statuses: [todo, doing, review, done]（真工具默认 To Do/In Progress/Done，不改则 `-s doing` 被拒）
  - 已刷新：scripts/check.py 是 I-001 之前的旧版，缺自授权（会锁死认领与登记）；其余差异不自动覆盖，由 audit 报漂移

v2 -> v3: 适配指针升级为各工具原生目录格式（.cursor/rules、.windsurf/rules），清掉旧单文件
  - 已迁移 .cursorrules → .cursor/rules/coharness.mdc
[lock] 已写 C:\Users\666666\AppData\Local\Temp\<临时目录>\03-multi-harness-project\.agent\skeleton.lock（这份指纹可以提交进项目仓库：不含本机路径）
  skeleton = 03-multi-harness-project
  skeleton_commit = 5f85a02
  schema = 3
  check_sha256 = 0206fabaccad

[migrate] 已落盘并把 schema 记到 3；改动都在备份分支 coh-backup-<时间戳> 的对照下，回滚：git reset --hard coh-backup-<时间戳>

### 第 4 步：核对结果

  [OK] 旧单文件适配已删除
  [OK] 原生 Cursor 规则已生成
  [OK] .gitignore 已忽略本地记账
  [OK] AGENTS.md 已有降级行为节
  [OK] 文档里的库路径已代入绝对路径
  [OK] 认领句已升级为 wsc claim
  [OK] 指纹记到当前 schema
  [OK] 常驻规则卡已清掉
  [OK] 看板列已改成本骨架四列
  [OK] 旧版 check.py 已刷新为含自授权的那版
  备份分支：coh-backup-<时间戳>
  回滚办法：git reset --hard coh-backup-<时间戳>

升级带来的未提交改动：
 M .agent/skeleton.lock
 M .agent/workflows/parallel-protocol.md
 D .cursorrules
 M .gitignore
 M AGENTS.md
 M backlog/config.yml
 D backlog/tasks/T-000-board.md
 M scripts/check.py
?? .cursor/

下一步就是常规提交：git add -A && git commit -m 'migrate v1 -> v3'
```

## 这几条设计是要害

- **默认 dry-run**：升级前先看清动什么；脚本当场核对"dry-run 前后 `git status` 一致、指纹未动"
- **落盘前自动建备份分支**：`coh-backup-<时间戳>`，回滚就是一条 `git reset --hard`
- **非 git 仓库拒绝落盘**：没有备份手段就不写（`tests/test_maintain.py::test_migrate_refuses_yes_without_a_repo`）
- **schema 有两个来源**：优先读 `.agent/skeleton.lock`，没有就读项目卡里的 `| 骨架 schema | N |` 声明，
  都没有才按 v1 处理（`migrate` 输出里的 `←指纹` / `←AGENTS.md 声明` 会说是哪个）
- **只补真需要的**：没装过适配指针的项目不会被塞进五个新文件；`check.py` 只在"缺自授权"这一条明确旧版特征时刷新，
  其它差异交给 `audit` 报漂移，不静默覆盖
- **幂等**：升到当前 schema 后再跑一次，答案是"已是最新 schema，无升级步骤"
- **步骤是本轮真实改动**：v1→v2 七步与 v2→v3 一步都对应 CHANGELOG 里已有的行，不是为演示编的

对应的自动化证据：`tests/test_maintain.py` 20 条（含 dry-run 不写盘、备份分支、幂等、拒绝无仓库落盘、
v2→v3 不凭空生成、指纹不含本机路径、七项 v1 遗留各自被处理、schema 可从项目卡读回）。
