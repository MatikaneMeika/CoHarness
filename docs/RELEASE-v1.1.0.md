# 发布 v1.1.0 — 草稿与待你执行的清单

这份文件里，**上半部分是已完成的准备**（内容与证据都在仓库里），
**下半部分是只有你能做的动作**（打标、发 Release、传 PyPI）。我不会替你执行它们。

## 一、代码侧已就绪（本地可证）

| 项 | 状态 | 证据 |
|---|---|---|
| 包定义 `pyproject.toml` | 已就绪 | `tests/test_packaging.py`（7 条：运行期零依赖、三个入口脚本、wheel 清单覆盖骨架、不夹带开发面文件、指纹可移植、README 双语互链真存在、`init` 复制文件数与文档一致） |
| 本地安装可用 | 已实测两种 | ① `uv build --wheel` + 干净 venv 里 `pip install --no-build-isolation ./`；② `uv tool install --from <wheel> coharness` 的隔离工具环境（pipx 等价，工具目录指 D 盘）。两条都验到 `wsc list` 列出四套骨架、`wsc init 03 <空目录>` 复制出 28 个文件、`wsc check` 全绿；wheel 含四个门面的模块与入口，装出来的 `coharness-panel` 在仓库外目录跑通（rc=0） |
| 单文件模式的真实边界 | 已改真 | `README.md` / `README.en.md` / `SECURITY.md` 不再承诺"curl 一个 wsc.py 就能装骨架"；`wsc.py init` 在无骨架目录时给出可执行的两条替代路径（`tests/test_packaging.py::test_single_file_mode_says_what_it_cannot_do`） |
| 双语 README | 已就绪 | `README.md` ↔ `README.en.md` 互链 |
| 贡献与审核门禁 | 已就绪 | `CONTRIBUTING.md`、`docs/EVOLUTION-PROCESS.md`、`docs/rfcs/`、`.github/ISSUE_TEMPLATE/*`、`.github/PULL_REQUEST_TEMPLATE.md` |
| 自测 | 全绿 | `python -m unittest discover -s tests`（零依赖），带预言机时 skipped=0；详见 `docs/ACCEPTANCE-v1.1.md` |
| CI 剧本 | **run #33（`bcddc3a`）五条腿全绿，badge 实测 `passing`** | `.github/workflows/ci.yml`（`on: push`，ubuntu/windows × py3.11/3.13 + oracle job）。状态无需登录就能读：`curl` 取 workflow 的 `badge.svg`；失败时也一样无需登录——自测步骤只在 `rc≠0` 时发 `::error::` annotation，公开运行页把 annotation 渲染出来，两轮红（全局 git 身份、8.3 短名 `TEMP`）都是这么定位的。本机仍无 `act`/`docker`，所以平台相关的坑只能靠 CI 的腿 |

## 二、v1.1.0 相对 v1.0 的改动摘要（发布说明草稿）

```markdown
## CoHarness v1.1.0

把 README 的承诺变成可验证的事实：自测从 0 条（v1.0 没有一套可跑测试）长到 266 条零依赖、执法面纯标准库、分发面分层。

### 新增
- `wsc claim <项目> <卡号> <标识>`：认领原子化。同步→校验→写卡→过项目自己的 check.py→提交→推 main
  绑成一步；抢输自动还原并列出此刻可认领的卡；`--dry-run` 只报告不写盘
- 本地运行记账 `.agent/telemetry.jsonl` + `wsc stats`：规则遵循率 / 返工信号 / stale 分布
  （只落本地、已 gitignore、`--no-track` 或 `COHARNESS_NO_TRACK=1` 可关）
- `wsc improve --cross`：跨本机实例数同类摩擦，晋升门槛"≥2 次"从此有机械证据
- `maintain.py`（维护面）：`lock` 装机指纹 / `migrate` 按 schema 升级（默认 dry-run，落盘前建备份分支）/
  `audit` 只读体检（钩子缺失或被改、指纹漂移、main 合成态违规）
- `evolve.py`（开发面）：`--rubric` / `--out` 机器取证 / `--apply-check` 临时副本试装 + 全套自测 /
  `--verify-record` 晋升缺证即红
- 只读面板 `coharness-panel`（展示面，`board.py` 组装数据 + `panel.py` 只管终端）：本机项目列表 →
  任务列表（按角色分组，architect/pm/integrator 这类核心角色排在最前）→ 单卡详情，三级页面；
  进度直接读卡片"验收清单"的勾选数，报警位标出"提交了没勾""done 但清单未满""跨工作树分叉"，
  并显示哪个 harness 在负责哪张卡、这卡被几个工作树各写了一份。纯标准库自绘，`--plain` 出一次性
  文本（conhost 花屏的逃生门），全程只读、不写项目一个字
- `wsc init --minimal`：零外部依赖起步（TODO.md 清单），关掉了哪些执法写在项目自己的 AGENTS.md 里
- 依赖降级规格：四套骨架各一节「降级行为」+ `wsc doctor --explain` / `--simulate-missing`
- `wsc sync --dry-run`：不 pull、不出网，报告即将进来的改动碰到哪些接口契约与在做卡的边界
- 适配语义桥：各家原生格式（`.cursor/rules/*.mdc` 的 `alwaysApply`、`.windsurf/rules/*.md` 的
  `trigger: always_on`、`CLAUDE.md`/`GEMINI.md` 的 `@AGENTS.md`）+ `wsc adapters --verify/--install`
- `pip install coharness` / `pipx install coharness`，命令 `wsc`、`coharness-maintain`、`coharness-evolve`、
  `coharness-panel`（四个门面各一个入口）
- 社区面：`CONTRIBUTING.md`、`docs/rfcs/`（RFC-0001 认领原子化）、Issue/PR 模板、SECURITY 披露路径

### 变化（破坏性都列出来）
- 卡片与 `.agent/improvements.md` 属**自授权改动**，认领/状态流转/登记不再要求挂任务卡（旧"常驻规则卡"方案作废）
- 跨卡 `allowed_paths` 交集从"只靠 git 撞车"升级为**当场拒绝**（`check.py --tasks`）
- 适配指针位置变更：`.cursorrules` → `.cursor/rules/coharness.mdc`，`.windsurfrules` →
  `.windsurf/rules/coharness.md`（旧文件仍被工具兼容，`maintain.py migrate` 会替你迁）
- `check.py` 的 frontmatter 只认声明子集，子集外**响亮失败并带行号**（不再静默忽略）
- 文档里的 `<骨架库>`/`<CoHarness>` 由装机时代入绝对路径（散文占位符阶段留下的命令其实不可执行）

### 已知边界（未成立，别当成已完成）
- GitHub Actions 首跑已成立（run #33 全绿）；**发布后的装机成功率**与社区指标（star / 外部 PR）仍需时间
- CI 的 `actions/checkout@v4` / `setup-python@v5` / `setup-uv@v4` 每条腿报一条 Node 20 deprecation
  warning（共 5 条，纯噪音，不影响判定）。**故意没跟大版本**：checkout 已到 v7、setup-python v7、
  setup-uv v10，其中 setup-uv 的 v5/v6 发布说明自己写着"改了默认值 / 含破坏性变更"，
  而这里的收益只是消掉 warning——发布后单独一条提交升，让 CI 自己判
- `I-004`：合并后 main 的非法态仍无自动复查——`maintain.py audit` 提供可查面，`evolve.py --apply-check`
  只做晋升时的复查；服务端钩子/CI 门禁仍待议
- 去中心化审核池与 LLM-as-Judge：ADR-3/ADR-4 明确推迟，重启条件写在 `docs/EVOLUTION-PLAN.md`
```

## 三、分三层：谁来做才做得成

上一版把这一节整节写成"只有你能执行"，其中一半其实是我把"我还没查"当成"你不可替代"。按谁能做成重分：

**A 层——我能做，只是对外动作要你当次点头**

```bash
# 1. 打标并推送（本机 git 凭据已通，此前的 push 就是证据；回退 = 删远端 ref，不动历史）
git tag -a v1.1.0 -m "v1.1.0：认领原子化 + 本地 stats + 迁移与审核门禁 + 只读面板"
git push origin v1.1.0
# 前置条件已满足：CI 于 run #33 转绿（ubuntu×2 + windows×2 + oracle 五条腿，0 条 ::error::）。

# 2. 每次 push 后自检 CI 状态（不需要凭据）
curl -s https://github.com/MatikaneMeika/CoHarness/actions/workflows/ci.yml/badge.svg | grep -o passing
```

**B 层——只有你能做（凭据在我够不到的地方）**

```bash
# 0. 登录一次 gh，之后 CI 日志、GitHub Release 我都能接手做
gh auth login            # GitHub.com + 浏览器授权，约 30 秒
gh run list --limit 5    # 登录后能读 job 级日志与建 Release（失败测试名此前已可经公开 annotation 读到）

# 1. PyPI：需要你在 pypi.org 账号里建 API token（名字 coharness 实测未被占：/pypi/coharness/json 返回 404）
#    先 uv build，再 uv publish。注意别写 `python -m uv publish`——uv 不是可 -m 的模块（本机实测 No module named uv）
uv publish --publish-url https://test.pypi.org/legacy/ --check-url \
  https://test.pypi.org/simple/
uv publish
```

**C 层——谁都替代不了，只有时间会给**

`star 1→50`、第一个外部 PR、ADR-3 的"≥50 装机指纹"。前置件（`CONTRIBUTING.md`、Issue/PR 模板、
RFC 档案、SECURITY 披露路径）都已就位，但这一格的数字不是任何一次执行能造出来的。
**2026-09-29 起整格暂缓**：用户裁定当前单用户、暂不运营社区，目标数字不撤，重启条件=对外发布后出现真实协作者。

**pipx 那条已经不用你跑**：本机没有 pipx，但我用 `uv tool install --from dist/coharness-1.1.0-py3-none-any.whl coharness`
做了等价验证（隔离环境 + 全局命令 + D 盘工具目录），装出来的 `wsc list`/`init`/`check` 全部正常。
你若要字面那条，`pipx install coharness && wsc list` 照旧可用。

发布后请把这一格数据补进 `docs/ACCEPTANCE-v1.1.md`：`pipx install coharness` 是否在你机器与目标
Python 版本上成功（Actions 首跑已成立，发布后要盯的是**长绿**与 PyPI 装机）。
