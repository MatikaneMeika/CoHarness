# CHANGELOG — 骨架本体变更日志

> 格式：`- YYYY-MM-DD [晋升 I-xxx@来源项目] 摘要`；非晋升的本体演进用 `[演进]` 标签，缺陷修复用 `[缺陷修复]` 并附复现方式。只增不改。

- 2026-09-28 [演进] 新增骨架库自测 `tests/`（36 条，纯标准库 unittest，`python -m unittest discover -s tests` 零安装可跑）：EVOLUTION-PLAN.md 附录里 2026-09-26 手工跑过、从未落盘的 check.py 断言全部钉成可重复执行的测试；覆盖命名规范、卡格式与认领冲突、stale advisory、pre-commit 端到端拦截、wsc init 三种目标与适配指针
- 2026-09-26 [演进] 建立自我迭代管线（登记→试点→审核→晋升）：新增 EVOLUTION-PROCESS 与本日志；4 套骨架加 improvements 登记模板与纪律行；wsc.py 加 improve 子命令；collab-zone skill 加 evolve 指令；ROUTER.md 加推荐能力节
