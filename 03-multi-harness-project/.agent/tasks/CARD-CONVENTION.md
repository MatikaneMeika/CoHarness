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

## 支持的写法子集（check.py 只认这些，超出去就报错给行号，绝不静默按空值处理）

- `key: 值`——值里含 `: ` 或 `#` 时，整个值用引号包住：`title: "方案: A"`
- `key: [a, b]` 与 `key: []`
- `key:` 留空，下一行起缩进写 `  - 项`（一行一项）
- 整行注释 `# ...`、行尾注释 `值  # 注释`
- 不支持：键下套键（嵌套 map）、块标量 `|` / `>`、行内 map `{}`、锚点别名 `&` `*`、
  多行续值、制表符缩进、重复键、`---` 不闭合、文件带 BOM
- 撞上不支持的写法：`[卡格式] backlog/tasks/T-001.md:13 列表项里又开了键（嵌套结构）…`，
  提交被 pre-commit 拦下。留空和写错是两回事——`title:` 留空报"title 为空"，
  `title: 值: 值` 这种歧义写法直接报错，而不是猜一个值。

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

1. `allowed_paths` 是**代码与文档改动**的唯一授权：进入本次提交的改动超出即越权，pre-commit 拦截（判暂存集，没 `git add` 的不算；仓库的首个提交不执法）
2. **卡片文件（`backlog/tasks/*.md`）与 `.agent/improvements.md` 属自授权改动**：认领、状态流转、改进登记直接 commit + push main，不再要求被某张卡覆盖；`forbidden_paths` 默认含 `AGENTS.md` 与 `.agent/`（规则文件不许随实现卡改），看板目录不在其列
3. 两卡的 `allowed_paths` 有交集 → 不能并行，回 pm 切分边界（目前只有文字纪律，check.py 不查交集）
4. 状态流转优先走 `backlog task edit`（要先把 `backlog/config.yml` 的 `statuses` 改成上面四列，真工具默认是 `To Do/In Progress/Done`）；没装 CLI 时手改卡片文件同样合法
5. stale 规则：doing/review 超 24h 无新 commit，integrator 可改派（改派也走 `backlog task edit`）
