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
| `labels` / `priority` / `created_date` / `updated_date` | Backlog 维护 | 02 骨架用 labels 承载 requirement_refs；03 用 labels 承载 `role:<角色>` 声明（所有权表执法要用，见下） |

## 边界与所有权表的关系（I-005，2026-09-29 起有机械核对）

卡片边界节以 `AGENTS.md` 的单写者所有权表为准：表里"具体路径 + 具体角色"的行所管辖的文件，
只有当覆盖它的在做卡带着 `role:<角色>` 标签（如 `role:architect`——"同一会话可身兼多角"，
角色由卡声明）时才可写，`check.py` 在提交时核对并拦下扩权；表的模板行与散文写者行判不了，
仍归审核人判。要改"谁拥有什么"，先改所有权表，不是绕开它。

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

## 卡体：固定五节 + 可选审阅节（check.py 按"边界"节执法，缺节 = 违规）

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
- [ ] `命令` 或 `路径` 或 `测试名`——每项必须指向可观察的证据（禁止"做好"这类不可验证项）

## 交接说明
收工时填，≤5 行：**首行 `结果: 成功|失败|部分`**，然后做了什么 / 怎么验证的 / 注意什么。
下一个接手的是另一个 harness，它没有你的会话记忆。
```

### 可选节：`## 审阅意见`（人给 agent 提意见的队列）

审阅者（人或另一 harness）把意见挂在卡上，agent 逐条消化后勾掉——勾选 = 已传达并处理。
三行结构是**渲染契约**（借鉴 orca 的 diff 批注格式）：确定性、可机器定位，面板会数未读条目。

```markdown
## 审阅意见
- [ ] File: docs/ARCHITECTURE.md
  Lines: 12-18
  Comment: "接口这里要写清幂等性"
- [x] File: code/api/
  Lines: all
  Comment: "整卡意见写 all；这条已传达并改掉"
```

格式由 `check.py` 响亮执法：条目必须 `File: ` 开头，续行只允许 `Lines:`（行号或 `all`）与
`Comment:`（引号包住的原文，`\` 与 `"` 要转义）。没有这一节的卡完全不受影响。

状态不变量：`doing` 可以带未勾选审阅意见；`review` / `done` 不得带未勾选审阅意见。

## 规则

1. `allowed_paths` 是**代码与文档改动**的唯一授权：进入本次提交的改动超出即越权，pre-commit 拦截（判暂存集，没 `git add` 的不算；仓库的首个提交不执法）
   - **两个授权来源冲突时，以 `AGENTS.md` 的单写者所有权表为准**：卡可以把你自己的路径收窄，不能把表里标"只读"的路径扩成可写；要扩权先改表（走规则卡 + ADR）。
     这条已有机械核对（2026-09-29 起）：`check.py` 在提交时对表里"具体路径 + 具体角色"的行核对在做卡的 `role:<角色>` 标签，扩权当场拦；表里判不了的模板/散文行留给审核人
2. **卡片文件（`backlog/tasks/*.md`）与 `.agent/improvements.md` 属自授权改动**：认领、状态流转、改进登记直接 commit + push main，不再要求被某张卡覆盖；`forbidden_paths` 默认含 `AGENTS.md` 与 `.agent/`（规则文件不许随实现卡改），看板目录不在其列
3. 两卡的 `allowed_paths` 有交集 → 不能并行，回 pm 切分边界（`check.py` 当场拦：两张 doing/review 卡交集 = `[任务卡] 边界交集不得并行`）
4. 状态流转优先走 `backlog task edit`（要先把 `backlog/config.yml` 的 `statuses` 改成上面四列，真工具默认是 `To Do/In Progress/Done`）；没装 CLI 时手改卡片文件同样合法
5. stale 规则：doing/review 超 24h 无新 commit 会打 stale 标记——**stale 是提示，不是改派授权**；integrator 改派需要正面证据（对方明确退出、自报放弃、或超 48h 沉默且联系无果），并在交接说明首行记 `结果: 改派（原因+时间）`（改派也走 `backlog task edit`）
6. 验收清单每项必须指向**可观察的证据**（反引号包住的命令、文件路径或测试名）；不含证据的项会被 `check.py` 提示（advisory，不拦截提交）
