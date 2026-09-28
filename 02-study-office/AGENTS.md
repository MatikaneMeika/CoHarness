# {{PROJECT_NAME}} — 学习办公骨架

> 触发约定：用户说「开工：X」（可带 @路径）= 按本文件与 `.agent/` 规程执行 X；调度细则见骨架库 `ROUTER.md`；门禁照走不豁免。

## 学习办公卡

| 项 | 内容 |
|---|---|
| 骨架 schema | 3 |
| 名称 | {{PROJECT_NAME}}（课程/考试/事项名） |
| 类型 | {{TYPE}}（交付型 / 持续型 / 办公型，可多选） |
| 截止/考试日期 | {{DUE_DATE}} |
| 每次投入 | {{DAILY_HOURS}} |
| 教材/大纲 | {{TEXTBOOKS}}（如：课程教材、官方考试大纲） |
| 格式模板 | {{FORMAT_TEMPLATE}}（学校/单位给的模板：实验报告模板、周报格式等；无则填"无"） |
| 运行命令 | `{{RUN_CMD}}`（涉及代码时） |
| 交付命名 | {{NAMING_RULE}} |

## 目录地图

```
deliverables/          交付物目录（code 可运行代码 / data 原始数据 / report 报告导出物）
syllabus.md            持续型唯一进度源：章节 × 掌握度 × 复习到期日
error-log.md           持续型唯一错题源
quiz-bank/             持续型题库
docs/                  要求清单等长期文档
.agent/                协作规则：角色、流程、任务卡
```

## 模式判定（接活先判模式）

| 模式 | 判断 | 入口流程 | 角色 |
|---|---|---|---|
| 交付型 | 有明确交付物与截止：作业 / 实验 / 报告 | `.agent/workflows/assignment.md` | requirement-analyst → coder / report-writer → self-checker |
| 持续型 | 无交付物、长期练习：备考 / 考证 / 语言 / 技能 | `.agent/workflows/daily-session.md` | quizmaster / tutor / error-auditor |
| 办公型 | 一次性文档：周报 / 日志 / 申请材料 | `.agent/workflows/office-task.md` | report-writer + self-checker |

同一项目可混合（如"备考为主 + 周日交实验报告"），按当次任务选模式。多章节、多轮改稿、多写手的**重度**文档生产分流到 04-doc-production 骨架。

## 诚信纪律（最高优先级，作业与办公材料通用）

1. AI 参与产出的内容，必须能向验收方**复述原理与依据**——写完每个核心模块/关键论断，用一段话讲清"为什么这么写"
2. **禁止伪造数据**：data/ 或材料中每个数字都必须来自真实运行、真实来源；产出不来就如实报告，不编结果
3. 引用外部资料一律标注来源；报告数据与 data/ 文件一一对应
4. **不发明事实**：所有事实、数字、经历只允许来自用户提供的资料或已确认内容；拿不准 → 标 ⚠ 提问，禁止编造或"合理推测"填空

## 全局纪律

1. 交付型开工第一步永远是**提取要求清单**（assignment.md 步骤 1），清单未确认不动手
2. 持续型每次会话**先读 syllabus.md 与 error-log.md**——数据文件即状态，会话记忆不作数
3. 交付物命名按 {{NAMING_RULE}}，禁 `-v2` / `-final` / `-副本` 后缀，版本进 git
4. 交付前必须过 self-checker 逐项核验，全 ✅（⚠ 项经确认）才能交
5. 跑不通的代码不进 `deliverables/code/`——先走 debug 流程
6. 任务卡（可选，交付型多任务/多人分工时用）：Backlog CLI，格式见 `.agent/tasks/CARD-CONVENTION.md`；持续型/办公型不用卡
7. **发现骨架问题就登记**：规则缺失/冲突造成返工、同类摩擦 ≥2 次、或缺 skill/MCP 时，在 `.agent/improvements.md` 登记一行（门槛见该文件头部）；试点改动只落本项目，晋升本体走 evolve 审核
## 降级行为（依赖没装时）

- **`backlog` 没装**（本骨架把它列为可选）：交付任务清单照 `docs/` 与 `error-log.md` 走，
  不建看板也不影响执法——这一档没有卡片层执法。要多人/多任务并行时再 `npm i -g backlog.md && backlog init`
- **`node` 没装**：装不了 backlog，同上；交付物生成不依赖 npm
- 没有 `specify` / `git-wt` 的需求：本骨架不做规格流水线，也不假设多 harness 并行
