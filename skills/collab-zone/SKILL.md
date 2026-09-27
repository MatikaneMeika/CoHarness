---
name: collab-zone
description: CoHarness 一句话调度与自我迭代入口。当用户说「开工：X」或「ws X」时使用——无论在项目内干活还是开新项目（X 可带 @路径）；「evolve <项目>」审核骨架改进；也响应 开新项目/建合作区/实例化骨架/开工/跑 check/改进审核 等说法。
---

# collab-zone — CoHarness 一句话调度入口（薄指针）

> 安装：把本目录复制进你的 harness 用户级 skills 目录（如 `~/.agents/skills/`、`~/.qoder/skills/`、`~/.gemini/skills/`），
> 然后把下面这行的 `<WS>` 改成你的 CoHarness 克隆目录。不装 skill 也能用——项目内 AGENTS.md 本来就生效，本 skill 只是把"创建新区/跨项目操作"变成一句话。

**`<WS>` = <把这里改成你的 CoHarness 克隆目录>**

调度权威：读 `<WS>/ROUTER.md` 并**严格执行**其流程（模式判定 → 新建模式/维护模式 → 角色匹配）。

- 触发词：「开工：X」/「ws X」；X 为任务描述，可带 `@<路径>`，缺省 = 当前目录
- 项目内日常操作命令：`python <WS>/wsc.py {sync|check|improve|doctor} [项目路径]`
- 本 skill 不含任何规则本体；一切项目规则以目标项目内 `AGENTS.md` 与 `.agent/` 为准
- 门禁不豁免：plan 批准、清单确认、审查门禁照走

## evolve <项目路径>（骨架改进审核）

1. 读 `<项目>/.agent/improvements.md`，筛状态 ∈ {登记, 试点中, 待审} 的条目（或先跑 `python <WS>/wsc.py improve <项目>`）
2. 逐条按 `<WS>/docs/EVOLUTION-PROCESS.md` 的五条标准评估：晋升 / 继续试点 / 驳回，逐条给理由；拿不准就驳回
3. 晋升候选：向用户展示将改动哪些本体文件、改什么 → **等用户批准**
4. 批准后：改 `<WS>` 对应文件 → `docs/CHANGELOG.md` 顶部记行 → 库内 git commit（一个晋升一个 commit）→ 回写项目登记表状态
5. 能力缺口类（类别=能力）：晋升去处是 ROUTER.md 推荐能力节，不写骨架规则；npm/winget 依赖同步对应骨架 NEXT_STEPS
