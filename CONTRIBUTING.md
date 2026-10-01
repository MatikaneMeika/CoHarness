# CONTRIBUTING — 怎么把改动并进 CoHarness

> 一句话版：**缺陷当场修并附复现；规则缺口先登记攒第二个数据点；晋升要过两道机器门禁；一个改动一个 commit。**
> 这套库的协作规则本体在骨架文件里（`AGENTS.md` / `scripts/check.py` / `ROUTER.md` / 三个脚本），
> 所以贡献的产物也是这些文件——不要新增"补充说明"文档。

## 先决条件

只需要 Python 3.11+（Windows/macOS/Linux 都行）与 git：

```bash
python -m unittest discover -s tests    # 零依赖；当前 365 条
```

想让差分测试也跑（拿 `python-frontmatter` 当预言机对照自写解析器）：

```bash
uv venv .venv-coh && uv pip --python .venv-coh install python-frontmatter pyyaml
.venv-coh/Scripts/python -m unittest discover -s tests     # 会多出 4 条不 skip
```

预言机**只在开发期与 CI 里用**，绝不进分发物（见 `docs/EVOLUTION-PLAN.md` 的 ADR-10）。

## 三条通道，先判断你走哪条

| 你的发现 | 走哪条 | 立刻能做什么 |
|---|---|---|
| 代码/执法与文档承诺不符（能写出红的最小复现） | **缺陷通道** | 修 + 复现方式写进 `docs/CHANGELOG.md` 的 `[缺陷修复]` 行 |
| 规则本身有缺口或互相冲突（现状按规则执行会卡住） | **规则通道** | 在**你实例化出来的项目**里 `.agent/improvements.md` 登记一行，别改执法代码 |
| 缺某个 skill / MCP / 依赖 | **能力缺口** | 同上登记（类别填"能力"），晋升去处是 `ROUTER.md` 推荐能力节 |

规则通道不许顺手改执法的 reason：进化管线第一次真实运转就开"我觉得该改就改"的先例，
比问题本身更伤。登记门槛（不满足不登记）：

1. 规则缺失或冲突造成了**实际返工**（不是"感觉会出问题"）
2. 同类摩擦出现 **≥2 次**（跨项目计数：`python wsc.py improve --cross`）
3. 或确有能力缺口

## 提改进的完整流程

```text
实例化项目里登记 → 本项目试点 → evolve 审核 → 用户批准 → 写回本体 → CHANGELOG 记行 → 一个 commit
```

审核与写回各有机器门禁，跑不动就不算数：

```bash
python evolve.py <项目> --rubric                       # 五条标准现读现印
python evolve.py <项目> --out 记录.json                 # 机器取客观证据，你填有效性与必要性
python evolve.py --apply-check 补丁.diff                # 临时副本套补丁 + 全套自测 + 新实例复查
python evolve.py --verify-record 记录.json              # 主观两栏 + 四项证据缺一即红
```

晋升写的 CHANGELOG 行必须带三证：**diff 位置 / 来源项目 / 测试·CI 运行标识**，外加用户批准的记录。

## 代码约束（会被测试当场拒绝的那种）

- **分发面只用标准库、零网络**：`wsc.py` 与 `scripts/check.py` 会被复制进每个下游项目，
  `tests/test_distribution_surface.py` 用 AST 检查 import、网络符号、eval/exec 与行数上限
- **新命令按面归位**：改已实例化项目的指纹/迁移/体检进 `maintain.py`（维护面），晋升审核进 `evolve.py`（开发面），只读呈现进展示面（`board.py` 装配 + `board_render.py` 渲染 + `panel.py` 终端，三者分开才好测）；不要再往 `wsc.py` 加——它的上限是最后一次上调后的 1250 行
- **卡片 frontmatter 只认声明子集**（`.agent/tasks/CARD-CONVENTION.md`）：子集外的写法必须**响亮失败**
  并带行号，不许静默忽略；要扩子集得先扩 `tests/test_card_subset.py` 与差分用例
- **不许改 `docs/CHANGELOG.md` 的历史行**（只增不改）
- **不在别人的项目里改骨架**：试点只落该项目自己的 `.agent/`；写回本体走审核

## PR 检查清单

- [ ] 能写成测试的改动，测试先红后绿（复现方式贴在 PR 描述与 CHANGELOG 里）
- [ ] `python -m unittest discover -s tests` 全绿，`expected failures` 只减不增
- [ ] 文档口径同步改真（README / SECURITY / 骨架 AGENTS.md），不留两套说法
- [ ] 骨架声明过的路径与命令在实例化后真存在、真能跑（`tests/test_skeleton_integrity.py`）
- [ ] 一个改动一个 commit；CHANGELOG 顶部加了行
- [ ] 没新增第三方依赖、没新增网络调用、没往 `wsc.py` 塞新命令

## 不接的东西

- 平行工具链（另做一套看板/另一份规则文档）——违反"文件即真相、AGENTS.md 唯一权威"
- 把 `check.py` 换成框架（pre-commit 框架、jsonschema、python-frontmatter 运行时依赖）——ADR-10 已决
- 只属于某个项目口味的规则——留在你自己项目的 `.agent/` 里
- 未过 `--apply-check` 的本体改动
