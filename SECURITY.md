# SECURITY — 安全与数据安全边界

## 这个仓库里有什么、没有什么

- **只有模板与协议文本**：骨架规则、流程文档、两个 Python 工具脚本。不含任何用户数据、凭据或机器特定信息。
- **实例化后的项目是独立仓库**：你在 CoHarness 骨架上创建的项目，其代码与数据归你自己的 git 仓库所有；CoHarness 不收集、不上传任何内容——运行统计与本机登记表都只落在本地文件里（细节见下面"行为边界"第 5、6 条），随时可关可删

## wsc.py、check.py 与 evolve.py 的行为边界（可审计）

1. **零网络**：两个脚本自身都不含任何 HTTP 客户端、不发起网络请求；对外连接只经由用户自己配置的 git 远端（`sync` 的 `pull`、`claim` 的 `fetch`/`push`），推哪个远端由用户的仓库配置决定。下载 CoHarness 本身（curl/git clone）是用户主动行为
2. **subprocess 全字面量 argv、无 shell**：所有子进程调用都以参数列表传（`git` / `backlog` / `<当前解释器> scripts/check.py`，解释器取 `sys.executable` 而非 PATH 上的别名），`shell=False`；用户输入只作为独立 argv 元素（如 `claim` 的卡号与标识会进 commit message 这一参数）或工作目录，绝不拼进命令行字符串；子进程输出一律显式按 utf-8 解码
3. **无动态执行**：不使用 eval / exec / 动态 import
4. **文件操作范围**：`init` 向目标目录写骨架文件与适配指针，并把 pre-commit 钩子复制进 `git rev-parse --git-path hooks` 指向的目录（目标是 linked worktree 时那是主仓库的 `.git/hooks`——多 harness 共享同一执法点，正是并行协议要的）；目标不是仓库根时**不写任何东西**，只打印提示；`sync` 执行 `git pull --ff-only` 并在缺钩子时补装那一个文件；`check` / `improve` 只读项目文件；`doctor` 只探测 PATH；`claim` 只改它认领的那一张卡（写前还原、写坏也还原），其余动作都是 git 子命令
5. **唯一的项目外写入**：`init` 成功后往 `~/.coharness/projects.json` 追加一条本机登记（项目路径 + 骨架名 + 骨架库 commit + 时间），给 `improve --cross` 当扫描清单用。纯本地明文 json，不含文件名之外的内容、不上传、可随时删除；不想写在家目录就设 `COHARNESS_HOME=<你想放的目录>`，写不进去（只读家目录等）只打印提示，不影响装机
6. **本地运行记账**：`check` 每次执行往**项目内** `.agent/telemetry.jsonl` 追加一行（时间、harness 标识、跑了哪几项检查、通过与否、当时在做的卡、耗时）。它是 `wsc stats` 的数据源：只写这一个文件、不联网、不出项目目录，且已在骨架 `.gitignore` 里——不进版本库、不会把工作区弄脏。想关掉：`scripts/check.py --no-track`，或设环境变量 `COHARNESS_NO_TRACK=1`；删掉该文件即回到零持久化痕迹
7. **pre-commit 钩子**：仅执行 `<能用的解释器> scripts/check.py`（本仓库自带、可读、纯标准库；行数上限由 `tests/test_distribution_surface.py` 钉住，超了测试就红，文档不再手写具体数字）。解释器按 `python` / `python3` / `py -3` 顺序探测，每个都真跑一次 `-c "import sys"` 确认可用——因为 Windows 上 `python3` 常是商店占位符；三个都不行就 exit 1 拦住提交，不静默放过
8. **`evolve.py` 在开发面，不在分发面**：它是骨架库维护者的晋升审核工具（读项目登记表、跨本机实例数同类摩擦、在**临时副本**里试装补丁跑自测），因此不随 `wsc init` 进任何下游项目，`curl` 单文件模式也带不动它。它同样只用标准库、不出网；对下游项目只读，唯一的写是你指定的 `--out` 记录文件；`--apply-check` 只在系统临时目录里动，本体一个字不改，临时目录跑完即删
9. **`maintain.py` 在维护面**：管已实例化项目的装机指纹与升级。写盘只有两处——`.agent/skeleton.lock`（`lock` 子命令）和 `migrate --yes` 显式升级；`migrate` 默认 dry-run 且落盘前自动建备份分支，`audit` 全程只读。它不联网、只用标准库
10. **最小模式（`init --minimal`）关掉了什么**：卡片层执法（改动挂卡、认领冲突、边界交集）依赖任务卡，没卡时 `check.py` 显式打印"最小模式关闭"并放行，命名规范与登记管线照常执法。关掉与留下的都在项目 `AGENTS.md` 的「最小模式」节里写着；补一张卡进 `backlog/tasks/` 即恢复执法——执法读文件，不读工具
11. **审计者视角**：想知道这些承诺是不是真的，跑 `python -m unittest discover -s tests`——`tests/test_distribution_surface.py` 会用 AST 检查三个脚本的 import 全在标准库或同目录模块、无网络符号、无 eval/exec、行数在上限内，并检查文档里没留下已经腐烂的手写数字

## 供应链建议

- 引导安装用 `git clone`（全量、可审计）或 `curl` 单文件 `wsc.py`；**建议按 release tag 固定版本**下载，不要盲拉 main
- 实例化后先读一遍项目内 `AGENTS.md` 与 `scripts/check.py` 再开工——整个执法面就这两个文件加一个 pre-commit 钩子

## 实例化项目的数据安全

- 03 骨架自带 `.gitignore` 模板（.env / 密钥 / 依赖目录 / 构建产物），**按项目补充后再提交**
- 纪律已写入骨架：密钥与本机配置不入库、过程产物不进交付树、日志不打印敏感信息（coder 角色约束）
- 多 harness 并行的本质是"多个 AI 工具共享一个 git 仓库"——**给工具的凭据权限请自行最小化**，CoHarness 不代管任何凭据

## 披露

- **普通缺陷与规则缺口**：开 GitHub Issue（用 `.github/ISSUE_TEMPLATE/` 里的两种模板：Bug / 改进提案），
  或按 `CONTRIBUTING.md` 直接在实例化项目里登记 `.agent/improvements.md` 后走晋升管线
- **安全漏洞**：先发私信/邮件给仓库所有者（GitHub 档案页上的邮箱），说明可复现路径与影响面，
  给对方 7 天窗口再公开——本仓库没有私有漏洞报告入口，隐私 Issue 是被接受的方式
- **不接受的"修复"**：另写一份规则文档。安全与协作约束一律进骨架本体（`AGENTS.md`、
  `scripts/check.py`、`ROUTER.md`、`wsc.py`/`maintain.py`），否则就会出现两套口径
- **报告里请附**：操作系统与 Python 版本、`python -m unittest discover -s tests` 的结果、
  以及能不能用 `tests/` 里的形状写出一条红了的最小复现——本仓库的验收方式就是"先能把它写成测试"

