# 卡片格式约定（Backlog.md 任务卡 · 交付型可选）

任务卡由 Backlog.md 管理，建卡/改卡一律走 CLI：`backlog task create` / `backlog task edit`。
**只有交付型多任务/多人分工时才用卡**；持续型与办公型的状态在数据文件里，不建卡。
本骨架不设 check.py 执法（那是 03 的重装备），验收闭环靠 self-checker 按 REQ 编号对账，labels 是硬要求。

## frontmatter：Backlog 全权管理，禁自造字段

| 字段 | 本项目约定 |
|---|---|
| `status` | 四列 `todo / doing / review / done`（backlog.config.yml 配置） |
| `labels` | **必须**含对应要求清单条目编号，如 `REQ-1`、`REQ-3`——self-checker 按此对账 |
| `assignee` | 多 harness 分工时填 harness 标识；单人作业可留空 |
| `dependencies` / `priority` / `created_date` / `updated_date` | Backlog 维护 |

## 卡体：固定三节

```markdown
## 需求
对应清单哪几条（引用 REQ-x 编号）+ 做什么。

## 做法与产物
产出落到 deliverables/ 哪个目录、用什么方法、参数怎么设。
涉及数据：文件名 = 实验名_日期，来源必须是真实运行。

## 验收清单
- [ ] 可验证条目，逐条引用 REQ-x（如"REQ-2：程序一键运行出结果"）
```

## 规则

1. 卡的验收清单必须覆盖其 labels 引用的所有 REQ 条目——self-checker 核验时以此对照
2. 状态流转走 `backlog task edit`，不手改文件
3. 其余纪律（可复现性、数据只读、命名）以各角色文件为准，卡片不重复
