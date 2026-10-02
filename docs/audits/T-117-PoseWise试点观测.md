# T-117 PoseWise 试点观测记录（返工闭环与执法面漂移）

> 日期：2026-10-02 20:50 ｜ 执行：root（控制器）｜ 方式：只读观测
> 观测对象：`D:\job\PoseWise_Health`（只读，未改动其任何文件）
> 关联：`docs/优化计划书-v2.md` §5 运营轨；前序本地提交 `5820b44`（审阅返工闭环）

## 水位线

- HEAD：`60bb32cf3686de716e932beb7b4438ac2bb5e2c2`（`60bb32c`）
- 分支：`main`；工作区：干净（`git status --porcelain` 无输出）
- 装机 schema：`AGENTS.md` 声明 `| 骨架 schema | 3 |`；`.agent/skeleton.lock` 不存在
- 本地 `scripts/check.py`：758 行

## 机械事实

### 1. 返工闭环在人肉流程里真在跑

`backlog/tasks/T-019.md`（status: `done`）的「交接说明」含连续三轮复审返工记录：

- 复审返工一：TTS 播放状态从非响应式 `activeSrcs` 改为响应式 `ttsPlaying`。
- 复审返工二：修 `startMic` 代际 token 与布尔返回契约。
- 复审返工三（13:23）：修 WS 身份竞态（socket 绑定、四回调首行身份校验、onopen 复检）。
- 集成裁决（13:38，root/integrator）：独立审查 PASS（代码层），合并入 main（merge `c84e66e`）。

即「reviewer 发现问题 → 原实现者返工 → 再审查」这条闭环在真实项目里被使用，但依靠协议自觉，无执法兜底。

### 2. 执法面漂移：PoseWise `check.py` 缺「未勾选退回」规则

- PoseWise `scripts/check.py:383-396` 只校验审阅意见**格式**（条目须以 `File:` 开头、续行只允许 `Lines:` / `Comment:`）。
- 缺 CoHarness `5820b44` 新增的执法：审阅意见存在未勾选项时卡片必须为 `doing`。
- 结果：`review` / `done` 状态带未勾选审阅意见不会被拦下。

### 3. 实证：`done` 卡带未勾选验收项

`backlog/tasks/T-019.md`（status: `done`）验收清单含一项未勾：

```
- [ ] `cd code/posewise-web && npm test` 全绿（… **truth 先在红**：`_coord/DATA.md` 已于 main `d36f461` 删除而测试未同步，main 树复跑同样红，与本卡无关 …）
```

- 该未勾项是**验收清单**项，不是「审阅意见」项。
- 卡片带 integrator 明确豁免：「`test:truth` 先在红不作为本卡返工项：main 同红，T-002 已在自身边界内修 `truth.test.mjs` 与阈值快照链；本卡不恢复 `_coord/DATA.md`，该豁免不改变 T-021 对全量测试的后续要求」。
- 边界：CoHarness 新规则只拦「审阅意见」节的未勾项，不拦「验收清单」未勾项；本条因此不会被现行规则拦下，属合理豁免场景，不计为漏网缺陷。

### 4. telemetry 旧字段

`.agent/telemetry.jsonl` 末尾 12 条 `card` 字段全为 `null`（旧版未做卡绑定）；`checks` 形如 `{"names":…,"tasks":…,"diff":…,"stale":…}`。

### 5. improvements 登记现状

| 编号 | 类别 | 状态 | 摘要 |
|---|---|---|---|
| I-001 | 骨架 | 试点中 | worktree 开工时 `check.py` 报「边界路径不存在: demo/」（空目录不被 git 跟踪） |
| I-002 | 能力 | 登记 | Mimosa L3 门禁按全项目扫描，用卡外既有 high 命中拦提交 |
| I-003 | 骨架 | 登记 | `git-wt remove` 时 gitignored 交付物随工作树删除 |

## 结论

- 返工闭环**机制有效**：T-019 三轮返工加集成裁决，证明「fail → 审阅意见 → 退回 doing → 修复 → 再审查」在真实项目里跑得动。
- 执法面**有漂移**：PoseWise schema 3 缺「未勾选退回」规则，`done` 卡可带未勾项；该漂移是 `maintain.py audit / migrate` 的真实目标场景。
- **连带发现（已修）**：漂移一度被漏报。`maintain.py` 的 `CHECK_CAPABILITIES` 原用宽泛词 `审阅意见` 做能力标记，而 PoseWise 的**格式校验**里也有 `## 审阅意见`，字符串命中即被判「规则能力齐全」。实测：修复前 `python maintain.py audit D:\job\PoseWise_Health --quick --json` 报 `missing_capabilities: []`；标记换成只有新版才有的精确符号 `has_unchecked` 后，同一命令报 `missing_capabilities: ["has_unchecked"]` 与 `[执法面] 缺规则能力：has_unchecked`。
- 待用户决策：是否把 PoseWise 作为 `maintain.py audit / migrate` 的端到端演练对象（观测与 audit 只读；migrate 落盘需用户另行批准）。
