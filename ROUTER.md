# ROUTER — 一句话调度（所有 harness 通用的唯一调度权威）

> 触发词约定：用户说 **「开工：X」**（等价别名 `ws X`）即进入本流程，X 为任务描述，可带 `@<路径>`（缺省 = 当前目录）。
> 本文件只负责路由与选型；一切项目规则以目标项目内的 `AGENTS.md` 和 `.agent/` 为准。
> **触发词不豁免任何门禁**——plan 批准、清单确认、审查门禁照走。

## 第一步：判定模式

看 `@路径`（或当前目录）下有没有 `AGENTS.md` + `.agent/`：

- **有** → 已是合作区/骨架项目，直接进【维护模式】
- **没有** → 走【新建模式】，完成后接【维护模式】

## 新建模式（选骨架 → 实例化 → 就绪）

1. **选骨架**（按交付物判断，向用户说明理由）：

   | 交付物 | 骨架 | 依赖 |
   |---|---|---|
   | 作业/实验/报告类交付、备考学习、办公文档（周报/日志/申请材料） | 02-study-office | backlog（可选，交付型用） |
   | 多组件 / 多 harness 并行 | 03-multi-harness-project | backlog / specify / git-wt |
   | 纯文档（企划书/报告/论文，多章多轮） | 04-doc-production | 无 |
   | 小脚本 / 小游戏 / 单组件工具 | 01-solo-code | 无 |

2. `python <CoHarness 克隆目录>\wsc.py init <骨架> <路径>`
3. 02/03：按 init 输出的依赖提示安装（`wsc.py doctor` 自检）→ `backlog init`（看板列改 todo/doing/review/done）→ 03 再对每个在场工具跑 `specify init --integration zcode|codex|qodercli|generic`
4. 填占位符：机械项（项目名/路径）可代填，事实项（技术栈/考试名/截止日）问用户
5. 读取项目 `AGENTS.md` 与相关 workflow → 进入维护模式

## 维护模式（匹配角色干活）

1. 每次**先跑** `python <库>\wsc.py sync <路径>`（pull + 看板摘要 + stale 报告；01/04 无看板则跳过）
2. 读项目 `AGENTS.md`，按其"工作方式"节定位 workflow；03 多 harness 另按 `.agent/workflows/parallel-protocol.md` 认领开工
3. **按任务性质套角色**（同一会话可身兼多角，但实现与审查必须分开两轮）：

   | 任务性质 | 角色（按所选骨架取用） |
   |---|---|
   | 提需求 / 提要求清单 / 拆卡 | pm、requirement-analyst |
   | 技术方案 / 大纲 / 架构 | architect、outline-writer |
   | 写代码 / 写章节 / 写报告 / 办公文档（周报·日志·申请材料） | coder-*、content-writer、report-writer |
   | 审查 / 自检 / 核验 | reviewer、self-checker、checker |
   | 集成回归 | tester |
   | 合并收尾 / 交付打包 | integrator |
   | 文档生产 | doc-writer |
   | 学习（02 持续型）：出题 / 讲解 / 错题 | quizmaster、tutor、error-auditor |

4. 干活全程遵守项目 AGENTS.md 的全局禁令与角色约束；收工按 parallel-protocol 汇报（03）或项目 workflow 的收尾节（其余骨架）

## 自我迭代

骨架用着不顺手（规则缺口 / 能力缺口）→ 项目内 `.agent/improvements.md` 登记 → 本项目试点 → **「evolve <项目路径>」**：按 `docs/EVOLUTION-PROCESS.md` 五条标准审核，用户批准后写回本体并记入 `docs/CHANGELOG.md`。`wsc.py improve <项目>` 可机械列出待审条目。

## 推荐能力（晋升产物，按需取用）

> 工作中任务暴露能力缺口 → 项目登记 → evolve 晋升后记入本节。用到才装，不预装。

| 适用骨架 | 能力 | 载体 | 用途 |
|---|---|---|---|
| 02 交付型 | 作业要求扫描件 OCR / 要求模板解析 | skill: doc-intake | requirement-analyst 的输入 |
| 02/04 | 报告与文档配图 | skill: agnes-free-image | 配图生成 |

## 边界情况

- 用户在**任意目录**说「开工：」没带 @路径且当前目录不是项目 → 先问项目放哪，再走新建模式
- 目标路径非空且非项目 → 停下报告，禁止混入
- 多 harness 同时在场 → 各自走 parallel-protocol，认领先进 main
- 项目规则与本文件冲突 → 项目规则优先（本文件只管路由）
