---
name: coharness
description: CoHarness 一句话调度与自我迭代入口。当用户说「coharness X」或「coharness：X」时使用——无论在项目内干活还是开新项目（X 可带 @路径）；「evolve <项目>」审核骨架改进；也响应 开新项目/建合作区/实例化骨架/跑 check/改进审核 等说法。旧触发词「开工：」「ws」已停用（2026-09-29）。
---

# coharness — CoHarness 一句话调度入口（薄指针）

> 安装：把本目录复制进你的 harness 用户级 skills 目录（如 `~/.agents/skills/`、`~/.qoder/skills/`、`~/.gemini/skills/`），
> 然后把下面这行的 `<LIB>` 改成你的 CoHarness 克隆目录。不装 skill 也能用——项目内 AGENTS.md 本来就生效，本 skill 只是把"创建新区/跨项目操作"变成一句话。

**`<LIB>` = <把这里改成你的 CoHarness 克隆目录>**

调度权威：读 `<LIB>/ROUTER.md` 并**严格执行**其流程（模式判定 → 新建模式/维护模式 → 角色匹配）。

- 触发词：「coharness X」（也接受 `coharness：X`）；X 为任务描述，可带 `@<路径>`，缺省 = 当前目录
- 项目内日常操作命令：`python <LIB>/wsc.py {sync|check|improve|doctor} [项目路径]`
- 想知道全局状态（谁在做哪张卡、做到哪一步、哪里不一致）：`python <LIB>/panel.py --plain [项目路径]`
  —— 只读看板，按角色分组并把"提交了没勾 / 勾了没提交 / 跨工作树分叉"标出来，不写任何文件
- **已经装好骨架的项目**：不必告诉它库在哪。`wsc init` 会把库的绝对路径代进项目自己的
  `AGENTS.md`（含 ROUTER.md 那一行）与 `.agent/` 里的命令，换一个 harness 打开项目读到的就是可执行命令
- 本 skill 不含任何规则本体；一切项目规则以目标项目内 `AGENTS.md` 与 `.agent/` 为准
- 门禁不豁免：plan 批准、清单确认、审查门禁照走

## evolve <项目路径>（骨架改进审核）

1. `python <LIB>/evolve.py <项目> --rubric` 印五条标准；`python <LIB>/evolve.py <项目> --out 记录.json`
   拿机器取证（状态机合法性、同类摩擦跨项目计数、证据能否翻出来、提议落点）
2. 你只填记录里的两个主观维度（有效性、必要性）与结论（晋升 / 继续试点 / 驳回），逐条给理由；
   拿不准就驳回——**驳回是一等公民**
3. 晋升候选：先 `python <LIB>/evolve.py --apply-check 补丁.diff`（临时副本套补丁 + 全套自测 +
   新实例全量 check，红的不许写回），再 `--verify-record 记录.json`（缺主观项或四项证据即红）
4. 向用户展示将改哪些本体文件、改什么 → **等用户批准**；批准后改 `<LIB>` 对应文件 →
   `docs/CHANGELOG.md` 顶部记行（带三证）→ 库内 git commit（一个晋升一个 commit）→
   回写项目登记表状态 → 写回后再跑一次全量自测与 `wsc.py check <项目>`
5. 能力缺口类（类别=能力）：晋升去处是 ROUTER.md 推荐能力节，不写骨架规则；npm/winget 依赖同步对应骨架 NEXT_STEPS
