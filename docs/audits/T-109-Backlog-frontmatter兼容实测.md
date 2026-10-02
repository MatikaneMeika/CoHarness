# T-109 Backlog.md 真实 frontmatter 兼容实测记录

> 实施日期：2026-10-02  
> 责任角色：tester（agy / Antigravity CLI 独立实现 harness）  
> 对应计划：`docs/优化计划书-v2.md` W21 / `docs/EVOLUTION-PLAN.md` 待验项①  

---

## 1. 口径差对齐结论

### 历史记录
- `README.md:173`：折叠区注明“第三方工具的已知坑（Backlog.md 1.53.0，2026-09-28 真装真跑）”，记录了 3 个坑（默认看板列不是四列、认卡格式为 `t-<编号> - <标题>.md`、`--agent-instructions` 侵入）。
- `docs/EVOLUTION-PLAN.md:167`：2026-09-28 补注记录“三条待验项仍未验（本机不装 backlog / specify / git-wt，也不为此装）”。

### 差异成因分析
1. **两次事件性质不同**：
   - 2026-09-28 是快速装机试用 CLI 交互与初始化逻辑，重点在用户界面与工作流，由此发现了默认看板列、认卡文件名前缀、指令注入等 3 个 UX 坑，并沉淀入 README。
   - 但当时并未对 Backlog CLI 真实生成的各种 frontmatter/Markdown 语法子集与 `check.py` 内部手写的自研扁平 YAML 解析器做系统的边界兼容性验证，也为了保持环境干净未在开发机常驻保留 Backlog 工具，故 EVOLUTION-PLAN 待验项①一直处于“留给首次真实使用”的待验状态。
2. **本次对齐结论**：
   - 2026-10-02 在系统隔离临时目录（`%TEMP%/backlog-sandbox-t109`）中完成真正的 `backlog.md@1.53.0` 隔离安装、真实建卡、全边界用例测试。
   - README 所载的 3 个已知坑在本次实操中全部 100% 再次复现属实（例如 `backlog config set statuses` 明确报错拒绝直改、`t-<编号>` 命名规则、默认 To Do/In Progress/Done 三列等）。
   - EVOLUTION-PLAN 待验项①正式在此完成验证并销账。两者口径完全统一，不存在逻辑冲突。

---

## 2. 实操环境与命令

- **系统环境**：Windows 11 / Node.js `v22.13.1` / npm `10.9.2` / Python 3.12 (with PyYAML 6.0.3)
- **隔离沙盒路径**：`%TEMP%\backlog-sandbox-t109`（仓库外部系统临时目录，零文件污染）
- **工具安装与版本确认**：
  ```powershell
  cd $env:TEMP\backlog-sandbox-t109
  npm init -y
  npm install backlog.md@1.53.0
  node ./node_modules/backlog.md/cli.js --version
  # 输出: 1.53.0
  ```
- **项目初始化**：
  ```powershell
  git init
  node ./node_modules/backlog.md/cli.js init "CoHarness Real Sandbox" --defaults --agent-instructions none --task-prefix T
  ```
- **配置看板四列**：
  手动编辑 `backlog/config.yml`：
  ```yaml
  statuses: ["todo", "doing", "review", "done"]
  task_prefix: "T"
  ```
  *(注：实测验证 `node ./node_modules/backlog.md/cli.js config set statuses ...`，CLI 响亮报错拒绝直改，必须编辑配置文件，复现 README 记录)*。

---

## 3. 逐张实测清单与结论

实测覆盖了 CARD-CONVENTION 与 W21 规定的全部子集边界用例：

| 卡号 | 测试边界 | 执行建卡/改卡命令 | 真实生成文件名 | check.py 解析结果 | PyYAML 预言机对比 | 最终处置与判定 |
|---|---|---|---|---|---|---|
| **T-1** | 基础卡 (简单标题、单标签、单认领) | `task create "Basic Task: CLI Real Verification" -s todo -a @zcode-0926a -l core` | `t-1 - Basic-Task-CLI-Real-Verification.md` | `id='T-1', title='Basic Task: CLI Real Verification', status='todo', assignee=['@zcode-0926a'], labels=['core']` | 100% 一致 | **通过** (钉入 fixtures) |
| **T-2** | 引号标题 (含冒号空格 `: `) | `task create "Plan: Evaluation of A and B" -s todo -a @zcode-0926a` | `t-2 - Plan-Evaluation-of-A-and-B.md` | `title='Plan: Evaluation of A and B'` (CLI 自动加单引号 `'Plan: Evaluation of A and B'`) | 100% 一致 | **通过** (钉入 fixtures) |
| **T-3** | 标量含 `#` 字符 | `task create "Fix issue #42 and #99" -s todo -a @zcode-0926a -l bug` | `t-3 - Fix-issue-42-and-99.md` | `title='Fix issue #42 and #99'` (CLI 自动单引号包裹，去注释逻辑未误杀) | 100% 一致 | **通过** (钉入 fixtures) |
| **T-4** | 标题含双引号 `"` 与中括号 `[]` | `task create 'Refactor "parser" and [tokenizer]' -s todo -a @zcode-0926a` | `t-4 - Refactor-parser-and-tokenizer.md` | `title='Refactor "parser" and [tokenizer]'` | 100% 一致 | **通过** (钉入 fixtures) |
| **T-5** | 多值列表 (多 assignees、多 labels) | `task create "Multi Assignees and Labels" -s todo -a @alice,@bob -l frontend,backend,urgent` | `t-5 - Multi-Assignees-and-Labels.md` | `assignee=['@alice', '@bob'], labels=['frontend', 'backend', 'urgent']` (缩进 `- 项` 块列表) | 100% 一致 | **通过** (钉入 fixtures；check.py 业务层正确报错拦下一卡多 assignee) |
| **T-6** | 留空值 (空列表、未认领) | `task create "Empty Fields Task" -s todo` (缺省 assignee) | `t-6 - Empty-Fields-Task.md` | `assignee=[], labels=[], dependencies=[]` | 100% 一致 | **通过** (钉入 fixtures；非 doing/review 允许未认领) |
| **T-7** | 含冒号标签 (`role:tester`) | `task create "Role Labeled Task" -s todo -a @tester-01 -l role:tester,scope:cli` | `t-7 - Role-Labeled-Task.md` | `labels=['role:tester', 'scope:cli']` (CLI 自动为列表项加单引号 `'- \'role:tester\''`) | 100% 一致 | **通过** (钉入 fixtures；未误判为嵌套键值) |
| **T-8** | 依赖前置卡 (多 dependencies) | `task create "Dependent Task" -s todo -a @zcode-0926a --dep T-1,T-2` | `t-8 - Dependent-Task.md` | `dependencies=['T-1', 'T-2']` (块列表形式) | 100% 一致 | **通过** (钉入 fixtures) |
| **T-9** | 状态流转与更新时间戳 | `task create "Task with Updated Date" -s todo -a @zcode-0926a` 随后 `task edit T-9 -s doing` | `t-9 - Task-with-Updated-Date.md` | `status='doing', updated_date='2026-10-02 09:44'` | 100% 一致 | **通过** (钉入 fixtures；`_parse_updated` 秒级通过) |
| **T-10** | 标题含单引号/撇号 `'` | `task create "Fix user's issue #123" -s todo -a @zcode-0926a` | `t-10 - Fix-users-issue-123.md` | `title='Fix user'` (严重截断！) | 预言机为 `"Fix user's issue #123"` | **发现真实缺陷** (违反 ADR-10 决定 1，钉入专用夹具) |

---

## 4. 关键缺陷发现与取证（T-10）

### 缺陷现象
在 `T-10` 中，Backlog.md 生成的原始 YAML frontmatter 行为：
```yaml
title: 'Fix user''s issue #123'
```
这是标准 YAML 规范：在单引号标量中，单引号通过两个连续单引号 `''` 进行转义。

然而，`check.py` 运行时解析结果为：
```python
meta["title"] == "Fix user"  # 后半截 "'s issue #123" 丢失！
```

### 缺陷代码坐标
位于 `03-multi-harness-project/scripts/check.py:71-78`：
```python
def _strip_comment(value: str):
    """去行尾注释；引号里的 # 不算注释。"""
    v = value.strip()
    if v[:1] in ("\"", "'"):
        close = v.find(v[0], 1)
        if close != -1:
            return v[: close + 1]
    return re.split(r"\s+#", v)[0].strip()
```

### 机制成因
`close = v.find(v[0], 1)` 简单查找索引 1 之后出现的第一个单引号。在 `'Fix user''s...'` 中，它找到了 `user` 后的第一个 `'`，并将索引截止到该处，直接切断返回了 `'Fix user'`。随后的 `_unquote` 将其处理为 `Fix user`，导致后面的内容被当作注释静默截断！

### 处置裁决（遵循 W21 决策树）
- **判定等级**：属于决策树第 3 支——`解析结果与语义不符（不报错但值错）`。
- **违背宪法**：直接违反了 ADR-10 决定 1“宁可不解析（响亮失败），也不静默给出错的值”。
- **当前边界处理**：由于当前任务 T-109 严禁修改 `check.py`，本任务**不跨界修改代码**，而是：
  1. 将真实产物钉入 `tests/fixtures/backlog-real-escaped-quote.md` 作为红用例夹具；
  2. 提供可复现的聚焦测试代码与红绿测试证据；
  3. 立案登记此缺陷坐标与修复建议，留待后续迭代修补。

---

## 5. 夹具落地清单

夹具已写入 `tests/fixtures/`，包含独立文件及 `tests/fixtures/backlog-real/` 目录：

1. `tests/fixtures/backlog-real-basic.md` (`backlog-real/basic.md`)：基础真实卡
2. `tests/fixtures/backlog-real-quotes.md` (`backlog-real/quotes.md`)：含冒号与双引号标题
3. `tests/fixtures/backlog-real-hash.md` (`backlog-real/hash.md`)：含 `#` 标题
4. `tests/fixtures/backlog-real-lists.md` (`backlog-real/lists.md`)：多 assignee、多 label、多 dep 块列表
5. `tests/fixtures/backlog-real-empty.md` (`backlog-real/empty.md`)：CLI 缺省空列表
6. `tests/fixtures/backlog-real-labels.md` (`backlog-real/labels.md`)：带冒号 `role:tester` 标签
7. `tests/fixtures/backlog-real-updated.md` (`backlog-real/updated.md`)：流转后带 `updated_date` 卡
8. `tests/fixtures/backlog-real-escaped-quote.md` (`backlog-real/escaped-quote.md`)：单引号转义截断缺陷夹具

---

## 6. 验收清单闭环

- [x] `tests/fixtures/backlog-real-*` 夹具在位，相关聚焦用例红绿可证
- [x] `docs/EVOLUTION-PLAN.md` 待验项①销账（标注 2026-10-02 实操日期与结论，文末补注）
- [x] 口径差对齐结论已完整写入本审核报告
- [x] 系统临时沙盒产物与缓存已清理，未污染工作区仓库
