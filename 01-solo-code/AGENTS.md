# {{PROJECT_NAME}} — 单人代码项目骨架

> 触发约定：用户说「coharness X」（可带 @路径）= 按本文件与 `.agent/` 规程执行 X；调度细则见 `{{COHARNESS_LIB}}/ROUTER.md`（装机时代成绝对路径，所以换一个 harness 打开本项目也不用问库在哪）；门禁照走不豁免。

一句话目标：{{GOAL}}

## 项目卡

| 项 | 内容 |
|---|---|
| 骨架 schema | 4 |
| 技术栈 | {{STACK}} |
| 运行命令 | `{{RUN_CMD}}` |
| 测试命令 | `{{TEST_CMD}}` |
| 入口 | `{{ENTRY}}` |

## 目录地图

```
src/          业务代码（唯一交付代码目录）
tests/        测试
docs/         CHANGELOG 等长期文档
.agent/       协作规则：角色、流程、任务卡（规则本体，勿随任务乱改）
```

## 全局约束

1. **先 plan 后改**：任何非琐碎改动，先列方案（改哪些文件、怎么验证）待确认，再动手。
2. **最小改动**：只改与当前任务卡相关的代码。顺手重构、顺手美化一律禁止，想要就开新任务卡。
3. **一任务一卡**：每个任务先在 `.agent/tasks/` 建卡（从 TEMPLATE.md 复制），状态流转 = 改 frontmatter 字段。
4. **版本进 git**：交付文件名不带 `-v2` / `-final` / `-副本` 等后缀；每次交付在 `docs/CHANGELOG.md` 追加一条。
5. **过程产物不进交付树**：调试截图、临时脚本、日志放系统临时目录，确属测试资产的再放进 `tests/fixtures/`（用到时自己建该目录），用完即删。
6. **发现骨架问题就登记**：规则缺失/冲突造成返工、同类摩擦 ≥2 次、或缺 skill/MCP 时，在 `.agent/improvements.md` 登记一行（门槛见该文件头部）；试点改动只落本项目，晋升本体走 evolve 审核。

## 工作方式

接到任务后按顺序执行：

1. 判断类型：新功能 → `.agent/workflows/new-feature.md`；修 bug → `.agent/workflows/bugfix.md`
2. 按流程建任务卡，**门禁处停下来等确认**
3. 实现阶段以 `.agent/roles/coder.md` 的约束行事；自审阶段切换到 `.agent/roles/reviewer.md` 的清单
4. 收尾：更新任务卡状态 + 追加 CHANGELOG

规则本身要改时（如命令变了、目录变了），直接改本文件并在 CHANGELOG 记一行，**不要**新建任何"规则补充说明"文档。
## 降级行为（依赖没装时）

本骨架刻意零外部依赖：唯一必需的是 `git`（没有它 pre-commit 与改动挂卡自动跳过，只剩命名规范）。
不需要 `backlog` / `specify` / `git-wt` / `node`——一个人一个仓库，看板与并行都不是这一档要解决的问题。
想升级：改用 `03` 骨架（`python {{COHARNESS_LIB}}/wsc.py init 03 <空目录>`），或装 backlog CLI 给本仓库加看板。
