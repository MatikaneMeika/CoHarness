# 卡片格式约定（Backlog.md 任务卡）

任务卡由 Backlog.md 管理，存在 `backlog/tasks/`。建卡/改卡一律走 CLI：
`backlog task create` / `backlog task edit` / `backlog task view`。

## frontmatter：Backlog 全权管理，禁自造字段

| 字段 | 含义 | 本项目约定 |
|---|---|---|
| `id` | 卡号（如 T-001） | `backlog init --task-prefix T` 生成 |
| `status` | 看板列 | 四列 `todo / doing / review / done`（backlog.config.yml 配置） |
| `assignee` | 认领者 | **唯一** harness 标识（如 `zcode-0926a`），一卡一人 |
| `dependencies` | 前置卡 | 无依赖的卡才可并行 |
| `labels` / `priority` / `created_date` / `updated_date` | Backlog 维护 | 02 骨架用 labels 承载 requirement_refs；03 不用 labels 管理引用 |

## 卡体：固定五节（check.py 按"边界"节执法，缺节 = 违规）

```markdown
## 需求
做什么 / 为什么。只写"做什么与为什么"，技术选型留给 architect。

## 技术口径
architect 填：推荐做法 / 禁用做法 / 测试要求。pm 建卡时留空。

## 边界
allowed_paths:
  - code/server/
forbidden_paths:
  - AGENTS.md
  - .agent/
  - backlog/

## 验收清单
- [ ] 可验证条目（禁止"做好"这类不可验证项）

## 交接说明
收工时填，≤5 行：做了什么 / 怎么验证的 / 注意什么。
下一个接手的是另一个 harness，它没有你的会话记忆。
```

## 规则

1. `allowed_paths` 是**唯一**改动授权：diff 超出即越权，pre-commit 拦截
2. `forbidden_paths` 默认含 `AGENTS.md`、`.agent/`、`backlog/`（规则与看板文件不允许随卡改）
3. 两卡的 `allowed_paths` 有交集 → 不能并行，回 pm 切分边界
4. 状态流转只有 `backlog task edit`，**不手改文件**；认领/状态提交直接进 main（见 parallel-protocol）
5. stale 规则：doing/review 超 24h 无新 commit，integrator 可改派（改派也走 `backlog task edit`）
