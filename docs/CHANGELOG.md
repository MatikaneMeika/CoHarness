# CHANGELOG — 骨架本体变更日志

> 格式：`- YYYY-MM-DD [晋升 I-xxx@来源项目] 摘要`；非晋升的本体演进用 `[演进]` 标签，缺陷修复用 `[缺陷修复]` 并附复现方式。只增不改。

- 2026-09-28 [缺陷修复] `check.py --diff` 判错了对象：用 `git status --porcelain`（整个工作区，含没 add 的文件与被折叠成目录的未跟踪项），导致全新实例化的项目**连第一个提交都被自己的钩子拦死**（骨架本体每个文件都"未挂任何任务卡"），只能 `--no-verify`。复现：`cp -r 03-multi-harness-project p && cd p && git init && cp scripts/hooks/pre-commit .git/hooks/ && git add -A && git commit`。修：改判本次提交的暂存集（`git diff --cached --name-only`，含删除、重命名取新路径、`core.quotepath=false`），仓库尚无提交时跳过执法并明确提示；`CARD-CONVENTION.md` 规则 1 同步写明"判暂存集、首个提交不执法"。证据：`tests/test_check_diff.py` 8 条（改动前 4 红）
- 2026-09-28 [缺陷修复] 简体中文 Windows（默认 cp936 控制台）上 `wsc check` / `wsc sync` 崩溃、`wsc init`/`improve` 的中文报错经管道后乱码：wsc.py 的子进程调用未写 encoding，把 check.py 的 utf-8 输出按 GBK 解码抛 UnicodeDecodeError；两个脚本又只重配置 stdout 不管 stderr。修法：新增 `_run()` 统一显式 utf-8 解码、子进程解释器由 PATH 别名 `python` 改为 `sys.executable`、stdout+stderr 一并 utf-8。复现与验证：`tests/test_console_encoding.py`（改动前 4 条红，改动后 43 条全绿）
- 2026-09-28 [演进] 新增骨架库自测 `tests/`（36 条，纯标准库 unittest，`python -m unittest discover -s tests` 零安装可跑）：EVOLUTION-PLAN.md 附录里 2026-09-26 手工跑过、从未落盘的 check.py 断言全部钉成可重复执行的测试；覆盖命名规范、卡格式与认领冲突、stale advisory、pre-commit 端到端拦截、wsc init 三种目标与适配指针
- 2026-09-26 [演进] 建立自我迭代管线（登记→试点→审核→晋升）：新增 EVOLUTION-PROCESS 与本日志；4 套骨架加 improvements 登记模板与纪律行；wsc.py 加 improve 子命令；collab-zone skill 加 evolve 指令；ROUTER.md 加推荐能力节
