# CHANGELOG — 骨架本体变更日志

> 格式：`- YYYY-MM-DD [晋升 I-xxx@来源项目] 摘要`；非晋升的本体演进用 `[演进]` 标签，缺陷修复用 `[缺陷修复]` 并附复现方式。只增不改。

- 2026-09-29 [缺陷修复] **同一条 CHANGELOG 里藏了一个响铃符（0x07），人眼看不出来**：用 shell heredoc 生成 Python 源码来写文档时，字符串里的 `D:\\a\\_temp` 被 bash 先折成 `D:\a\_temp`，Python 再把 `\a` 解释成 BEL 控制字符写进文件——显示出来仍是正常文字，字节里已经是 0x07。这是本会话第三次踩"往 shell 里塞带反斜杠的 Python 源码"这一类坑（前两次是 `\n` 折叠把源码当场改坏），区别是前两次立刻报错，这次只有字节知道。已就地修回那一行（同一批次刚写进去的，不是历史条目），并改用 Edit 工具而不是 heredoc 来写这类文本。
  补一条机器钉子：`tests/test_distribution_surface.py::test_no_control_characters_in_tracked_text`——`git ls-files` 里所有 `.md`/`.py`/`.yml`/`.json`/`pre-commit` 不许出现 C0 控制字符（`\t` `\n` `\r` 除外）与 DEL，命中就报文件名与码位。这类"只有机器能发现"的缺陷不该指望人眼。验证：全套 245 条 OK（skipped=4，expected failures=1，434.1 秒），文档条数 244→245 同步。

- 2026-09-29 [缺陷修复] **windows两条腿的真身：CI runner 的 TEMP 是8.3短名，测试拿它和 `wsc` resolve 后的长名比字符串**（这次 annotation 直接给了名字：`test_registry_cross` 三条 + `test_hook_install::test_linked_worktree_gets_shared_hook` + 被连带的 `test_apply_check_passes_a_doc_only_patch`；日志尾巴里那句 `WindowsPath('C:/Users/RUNNER~1/AppData/Local/Temp/…')` 就是证据）：`wsc init` 存的是 `Path(args.target).resolve()`，Windows 的 `resolve()` 会把 `RUNNER~1` 展开成长名，而测试拿 `tempfile.mkdtemp()` 得到的是短名，于是 `Path(entry) == proj` 恒假。本机测不出来——我的用户名 `666666` 没有短名形态。
  修法在测试侧（产品存长名是对的，登记表要靠它去重）：`helpers.hooks_dir()` 返回 resolve 后的路径（git 对 worktree 与主仓库报出的形状一个短名一个长名，同源同因），登记表那三条断言改成比 resolve。并补一条能**自己造出短名**的回归用例 `test_short_and_long_paths_register_as_the_same_project`：用 `H.short_path()`（ctypes `GetShortPathNameW`）取临时目录的8.3别名去装机，再断言用长名第二次 init 被「非空」挡住、登记表里只有一条。本机 C 盘启用了8.3，所以这条真的跑起来了（`test_registry_cross` 11条无 skip）。红绿对照同一份数据：旧口径 False、新口径 True。
  这一条也是"本机绿不等于绿"的第三次复发：前两次是全局 git 身份与 `::error::` 染色，这次是路径形状。共同点是**测试把开发机的环境当成了前提**。收口办法不是多写断言，而是让测试自己造出 runner 的条件。

- 2026-09-29 [缺陷修复] **成功时也不许发 `::error::`：五条腿 rc=0、245条 OK，却全被判红**（实测：run 36511280247 的 annotation 里只有我发的 7条 error（rc行 + 6行 tail），一条 "Process completed with exit code" 都没有，job 仍是 failed）。上一版为了"报平安"把 rc 无条件写成 `::error::`，等于自己给自己造失败。改法：只在 `rc != 0` 时写 error，绿的时候走普通 echo。两个 job 一致，注释里把两个坑都记下（pipefail 与 ::error:: 染色）。验证：本地拿 OK 日志与 FAILED 日志各跑一遍——绿情形退出0且不产 error 行，红情形退出1并列出 `FAIL: test_x (t.A.test_x)`；PyYAML 解析通过。

- 2026-09-29 [缺陷修复] **CI 五条腿全红的最后一条原因是我自己写的包装**：GitHub 给 `shell: bash` 默认加 `set -e -o pipefail`，`grep` 没匹配到就返回1，整步被中止。复现：`bash -c 'set -e -o pipefail; log=$(mktemp); printf "Ran 3 tests" > "$log"; grep -E "^(FAIL|ERROR): " "$log" | head -5 | sed "s/^/x/"; echo 不该出现'` → rc=1 且最后一行不打印；同样命令加 `|| true` 后 rc=0。这一次 annotation 把真话说清了：五条腿的自测**全部 rc=0、245条 OK**（ubuntu 两条腿 skipped=5、oracle skipped=1，与 Windows 专用用例、差分预言机用例的跳过条件正好对得上），红的是 annotation 那一步自己。我为了"看得见失败"加的包装反过来制造了一轮假红——工具比被测物先坏，而且坏在只有 CI 才有的默认值上。修法：两条 grep 管道都补 `|| true`，并把那个默认值写进注释。教训比上一条再进一格：**改 CI 的 shell 片段必须在 `set -e -o pipefail` 下验**，本地 bash 不带这两个选项，跑通了不算数。验证：本地红绿各跑一次；PyYAML 解析通过，两个 job 里未保护的 grep 管道数为0。

- 2026-09-29 [演进] annotation 那一步**改成无条件报平安**：上一版只在 `rc != 0` 时 grep 测试名，结果 windows 腿红的时候一条 annotation 都没有——分不清"没有失败行"还是"grep 没跑成"。现在先 `echo "::error::rc=… 匹配到 N 条 总结行: …"`，再贴逐条测试名与日志尾巴；两个 job 一致。本地拿假日志与空日志各验一遍（空日志匹配数为 0 但仍会发 annotation），PyYAML 解析通过。

- 2026-09-29 [缺陷修复] **上一条自己把 windows 两条腿改坏了：`"$RUNNER_TEMP/ci-test.log"` 在 Git bash 里重定向直接失败**（复现：`RUNNER_TEMP='D:\a\_temp'` 后执行 `echo x > "$RUNNER_TEMP/ci-test.log"` → `No such file or directory`，rc=1；GitHub 给 Windows runner 的 `RUNNER_TEMP` 是反斜杠路径，bash 里反斜杠是转义符，于是整个路径变成一个不存在的相对名字）。后果是那条步骤连测试都没跑就 exit 1，annotation 里自然一条测试名都没有——跑完看时长也能反推出来：windows 两条腿几秒就完，9 分钟全是 ubuntu 在跑门禁。改法：`log=$(mktemp)`，Linux 与 Git bash 都可用，也仍然不落进工作树。验证：本地把 `mktemp` + `grep -E '^(FAIL|ERROR): '` + `sed 's/^/::error::/'` 整条管道跑通，输出 `::error::FAIL: test_x (t.A.test_x)`；PyYAML 解析 `ci.yml` 通过。
  这条也是给上一条记账的补账：上一条写「放 RUNNER_TEMP 而不是工作树，免得给只读断言添变量」——动机对、实现错，而且错在只在一台机器上想过没在另一种 shell 上试过。教训是**改 CI 的 shell 片段必须同时在两种 shell 下验**，本地能验的那半（bash 语义）我这次才补上。

- 2026-09-29 [演进] **CI 失败要把红掉的测试名写成 annotation——日志要登录才能看，annotation 不用**（起因是本轮实测：封闭环境修好之后推一次，ubuntu 两条腿与 oracle 都绿了，只剩 windows 两条腿红，而我读不到 job 日志：raw logs 匿名 404、未认证 API 被出口 IP 限流、annotations 只有 "Process completed with exit code 1"。等于每轮都要靠本地猜）：`ci.yml` 两个跑自测的步骤改成 `shell: bash` + 先把输出写到 `"$RUNNER_TEMP/ci-test.log"`，非零退出前用 `grep -E '^(FAIL|ERROR): '` 与 `grep -E '^(Ran |OK|FAILED)'` 把测试名和总结行以 `::error::` 形式打出来，再 `tail -4` 保留原始结尾，最后 `exit $rc` 保持红。写进 RUNNER_TEMP 而不是工作树，免得给"面板只读、跑完工作区不变"那类断言添变量。验证：`../.venv-coh` 里的 PyYAML 解析 `ci.yml` 通过（stdlib 4 步、最后一步 shell=bash）；同一段 grep+sed 管道拿假日志本地跑过，输出形如 `::error::FAIL: test_x (t.A.test_x)`。

- 2026-09-29 [缺陷修复] **四条 CI 腿从第 1 次运行就红，本机 244 条却全绿：测试蹭了开发机的全局 git 配置**（复现：把 `HOME`/`USERPROFILE`/`GIT_CONFIG_GLOBAL` 指到一个空目录再跑全套 → 2 条判红，内层试装副本的套件也判红；还原成本机环境就全绿）：`tests/test_claim.py::test_claim_without_remote_stays_local` 只给仓库写了 `user.name`，没写 `user.email`，`wsc claim` 内部那次 `git commit` 在本机被全局配置兜住、在 runner 上直接 `Please tell me who you are` 退出 1；另一条红是连带——`--apply-check` 门禁会在临时副本里再跑一遍全套，内层一红门禁就判「补丁让自测变红」。**根因不是 CI 环境特殊，是测试没把自己和开发机隔开**——这种「本机绿」测不出真实用户的失败。
  两处一起改：①那条测试补上 `user.email`（只设 name 不够，commit 两样都要）；②`tests/helpers.py` 的 `run()` 从此强制封闭 git 环境——把 `GIT_CONFIG_GLOBAL` 与 `GIT_CONFIG_SYSTEM` 指到一个空文件，测试要身份只能走 `GIT_ID`（`-c` 注入）或给仓库写 local config，蹭不到全局。这条改动本身就是回归测试：以后再有测试依赖开发机配置，本机就会红，不用等 CI 才发现。
  取证过程也记一下：匿名状态下 job 日志读不到（raw logs 全 404，annotations 只有 Process completed with exit code 1），但公开页面给了两条决定性事实——oracle job 通过、stdlib 四条腿全红，且连 windows/py3.13 也红（我本机同版本是绿的）。于是把嫌疑从「Linux 轴」改到「runner 的干净环境」，一次本地复现就中了。验证：封闭环境下 `python -m unittest discover -s tests` 244 条 OK（skipped=4，expected failures=1，443.5 秒）。

- 2026-09-28 [演进] `skills/collab-zone/SKILL.md` 的日常操作命令旁补一行只读看板：`python <WS>/panel.py --plain [项目路径]`。第四门面落地后 skill 的命令清单没跟着长，照着 skill 干活的 harness 就永远不知道有这个东西——分发物之间的口径也要一致。验证：`test_skeleton_integrity` 5 条、`test_packaging` 7 条、`test_adapters` 11 条仍 OK。

- 2026-09-28 [缺陷修复] **测试装钩子少了 chmod：本机测不出来，但测的就不是产品装出来的那个钩子**（复现方式是对照读码：`wsc.install_pre_commit` 复制钩子后 `target.chmod(0o755)`，而 `tests/helpers.py:install_hook` 只 `shutil.copyfile` 就走完——Windows 不看执行位，本机 244 条全绿也照不出这个差异；unix 上不可执行的 `pre-commit` 会被 git 跳过或报权限错，于是 `test_hook_e2e` / `test_check_diff` 里那些"提交必须被拦"的断言在 Linux runner 上测的是另一回事）。修法：测试侧与产品侧做同一件事（同样 copyfile + chmod 0o755 + 同样的 OSError 兜底），并把理由写在旁边。**如实说明这是按机制推出来的保真度修复，不是已证实的 CI 红因**——Linux 那一轴的 job 日志我读不到（未认证 API 被出口 IP 限流，本机无 WSL/docker/act），已排除的轴：py3.11 整跑绿、`core.autocrlf=true` 重新检出整跑绿、git 身份与默认分支与路径大小写静态排查无命中。剩下的定位要一次 `gh auth login`。

- 2026-09-28 [演进] **面板的刷新从"每卡一次 git"改成"整库一次 + 按 HEAD 缓存"**（写第一版时留下的性能账，在补 `--watch` 的成本测试时才暴露）：原来每张卡各跑一次 `git log --name-only -- <边界>`、一次 `git worktree list`，20 张卡的看板每 5 秒就是 40 个 git 进程——"实时"两个字是拿 CPU 换的。现在一次 `git log` 取全部边界内的提交，按文件归属回每张卡（`_norm_prefix` 归一后做前缀匹配，这条改错一次就被测试抓住：卡片里的前缀带尾斜杠，不归一就永远匹配不上、提交数全成 0）；worktree 清单与提交结果按 HEAD 缓存，`rev-parse HEAD` 一变整体作废。实测 `.coh-p2/work/wt-a`：第一轮 3 次 git，第二轮 1 次（只剩 HEAD 探测），数据一字不差。
  新增 `tests/test_panel.py::RefreshCost` 两条：`test_second_build_only_probes_head`（第二轮必须比第一轮少干活，且缓存不能把数据也省掉）、`test_new_commit_invalidates_the_cache`（新提交后每张卡的提交数必须 +1——面板不许拿旧账当现状）。`board.py` 上限随之从 540 调到 580（ADR-10 附注的表同步），全套 244 条 OK。

- 2026-09-28 [缺陷修复] **全屏面板在 Windows 上第一次读键就崩；测试全走 `--plain` 所以整轮没发现**（复现：`mintty -- python panel.py --project <项目>` 起窗后进程立刻退出，`tasklist` 里查不到 mintty；直接调 `panel.read_key(0.05)` 报 `AttributeError: module 'msvcrt' has no attribute 'flush'`）：`read_key` 里我照抄了 posix 侧的习惯写了一句 `msvcrt.flush()`，而 msvcrt 根本没有这个函数——`--plain` 那条路不进 `read_key`，25 条面板用例又都不碰它，于是这个 bug 只在真终端里出现。修法：去掉那句；顺手把两个平台的按键解码抽成纯函数 `decode_msvcrt` / `decode_posix`（表也提到模块级），这样读键的 IO 与判定分开，判定可测。补三类用例：`test_read_key_returns_tick_without_a_console`（没有控制台时超时返回 tick，不抛异常——这条就是本次的回归钉）、`test_msvcrt_key_decoding`、`test_posix_key_decoding`；再加 `InteractiveLoop` 两条，用假 stdin/stdout 与脚本化 read_key 把 `main()` 的整条循环跑完（渲染→读键→换页→重建→退出时找回光标），这样全屏模式在 CI 里也被覆盖，不再依赖有没有终端。
  真机也验了：修完后 mintty 里三页正常渲染（标题行、按角色分组的青色表头、进度条 `[######] 1/1`、红色 `!提交了没勾 !跨工作树分叉`、页脚按键提示），截图确认中文列对齐没有漂。全套 242 条 OK。

- 2026-09-28 [演进] **加第四个门面：只读看板面板**（RFC-0002，用户需求“多级页面 + 角色进度实时显示 + 谁负责什么 + 核心角色突出”）：新增 `board.py`（数据装配与渲染，全是纯函数）+ `panel.py`（终端循环 205 行），入口 `coharness-panel`。三页：本机项目 → 任务列表（**按角色分组**，integrator/pm/architect/reviewer/tester/doc-writer 这类拍板与下派角色置顶，`coder-*` 在其下，推不到就写“边界没落进所有权表”）→ 卡详情（验收清单逐项、边界内提交、各工作树副本并排、底部印出可复制的 `wsc claim`/`wsc check`/`maintain audit`）。
  **完成度读的是已经存在的约定**：卡片第 4 节 `## 验收清单` 的 `- [ ]`——角色规程本来就要求勾（`coder-frontend.md:32`、`coder-backend.md:32`、`reviewer.md:23`），只是没有任何代码读它。面板把四类不一致摆出来：`提交了没勾`、`勾了没提交`、`done 但清单未满`、`跨工作树分岔`。最后一条不是设想：`.coh-p2` 里 `wt-a`/`wt-b` 的 T-101 是 `review` + 1/1 已勾（提交 `6571da6` 收工流转），而 `seed`/`work/proj` 还停在 `89f494c` 的 `todo` + 0 勾。
  **口径与代价**：①只读——不写文件、不认领、不改卡，`test_panel_writes_nothing_into_the_project` 断言跑完 `git status --porcelain` 不变且不留 `__pycache__`；②卡片解析复用**项目自己的** `scripts/check.py`，代价是全链唯一的 `exec` 口子，由 `test_only_the_projects_own_check_py_may_be_executed` 钉死“只允一次 exec、一次 compile，路径必须是 `<项目>/scripts/check.py`”，SECURITY.md 第 12 条同步写明；③对没跑 `migrate` 的老实例降级——缺 `minimal_mode` 照样读，缺 `load_cards` 响亮失败并给出 `maintain.py migrate` 命令（这条是真数据打出来的：`.coh-pilot-03` 就这么炸过一回）；③中文按显示宽度对齐，`--plain` 是本机 conhost 花屏时的逃生门；④“边做边勾”纪律属规则改动，**没有顺手改执法**，登记为试点台账 I-007（两个数据点已陏）。
  验证：`tests/test_panel.py` 20 条；全套 237 条 OK；`panel.py --plain` 在 `.coh-p2/work/wt-a`、`.coh-p4/proj`、`.coh-pilot-03` 三个真项目上各跑通。装机文件数仍是 27（面板住在库里，不进骨架）。

- 2026-09-28 [缺陷修复] **把"我这边读不到"写成了"没发生 / 只有你能做"——实测下来两处都不成立**（复现：`curl -s https://github.com/MatikaneMeika/CoHarness/actions/workflows/ci.yml/badge.svg` 返回 `failing`；`where pipx` 无此命令而 `uv tool install --from dist/coharness-1.1.0-py3-none-any.whl coharness` 一次成功）：验收表第 1 格原写"本地已绿，Actions 未首跑"，理由是"本机无 act/docker，结果只有 push 后才存在"——**后半句是假的**：`ci.yml` 是 `on: push`，仓库公开，17 次运行早就存在，而且**pass/fail 不需要凭据就能读**。真读不到的只有 job 级日志（未认证 REST 被本机出口 IP 限流 403，`gh` 又未登录）。所以这一格现在的实情是：**CI 红着，且这是我的活**——它排在任何新能力前面，因为红的 CI 会让表里其余"已证"都带一句存疑。第 2 格同理过窄：pipx 那半我用等价路径补测了（隔离工具环境里 `wsc list` 列四套骨架、`wsc init 03` 复制 27 个文件——与刚钉住的那个数吻合、`wsc check` 全过，跑完卸载清痕迹），如实分开记成"pipx 等价路径实测通过、pipx 字面路径未验"而不是"待你执行"。`docs/RELEASE-v1.1.0.md` 第三节按**谁能做成**重分三层：A 我能做但要你当次点头（打 tag 推 ref——git 凭据本来就通，前 16 次 push 是证据；条件是 CI 先绿，红的 commit 上打 tag 等于给发布物挂个已知坏状态）、B 只有你（`gh auth login`、pypi.org 建 API token；顺带实测 `coharness` 这名字在 PyPI 未被占）、C 只有时间（star/外部 PR/装机指纹）。

- 2026-09-28 [缺陷修复] **晋升门禁每过一次，就在用户真实登记表里留一条死记录**（复现：本机 `~/.coharness/projects.json` 里躺着 4 条 `…/Temp/coh-trial-*/proj`，目录早被门禁自己删掉了；来源是 `evolve.py --apply-check` 手工跑的那几次，包括 I-005 那次真晋升）：`apply_check` 末尾"从打了补丁的副本新实例化一个项目、跑一次全量 `wsc check`"这一步是 I-004 的最小实现，它用的是**原样继承来的环境**，而 `wsc init` 会把新项目追加进 `COHARNESS_HOME` 指向的登记表。测试里跑看不出来（登记表已被 `tests/helpers.py` 隔离），**手跑门禁时**写的就是真表——登记表的用途是让 `improve --cross` 扫遍本机实例，多一条死记录就多一处"扫过但跳过"，而这类污染只会由最该干净的那个动作留下。修法：那一步的 `init`/`check` 把 `COHARNESS_HOME` 指到临时副本里面，跑完连着副本一起删。断言挂在已有的门禁用例上（那条本来就要跑完整套，加断言不额外花时间）：`tests/test_evolve.py::test_apply_check_passes_a_doc_only_patch` 判"调用方登记表里不许出现 `coh-trial` 路径"。**红绿两态都实测**：还原修复后单跑该用例判红，输出里就是那条 `coh-trial-687901vv\proj`；装回修复判绿。

- 2026-09-28 [缺陷修复] **文档里写死的实测数字又烂了四处，这次交给机器去数**（复现：改动前跑 `python -m unittest discover -s tests -p test_distribution_surface.py -k docs_declare`，它判出全量 214≠216、`test_protocol_smoke.py` 8≠9、`test_packaging.py` 6≠7、`test_evolve.py` 12≠13）：上一轮刚把会腐烂的**行数**从文档清掉，这轮对照计划书自查发现**条数**是同一个病——加一条断言、加一个测试文件，五个文档里的手写数字就同时过期，最离谱的是发布草稿写"199→206 条零依赖自测"，那是**同一轮里的两个中间快照**，不是 v1.0→v1.1 的对照（v1.0 连一套可跑测试都没有，`tests/` 是本轮 `8f74102` 才建的）。条数和"骨架装出几个文件"是面向用户的承诺，值得写死，但写死就得有红了会报警的东西兜着：新增 `tests/test_distribution_surface.py::test_docs_declare_the_real_self_test_count`（用与 CLI 同一个 `discover` 入口数，全量条数和"`tests/test_x.py` N 条"两种写法一起对齐，并顺手断言文档引用的测试模块真存在）与 `tests/test_packaging.py::test_documented_init_file_count_matches_reality`（**真跑一次 `wsc init 03` 再数**：本轮给四套骨架补 `.gitattributes`，26 就变 27，这种数靠手写记不住）。五份文档共 11 处数字按实跑改真，全套自测 214→216 条。

- 2026-09-28 [演进] **骨架自己声明 schema，migrate 补齐计划书点名的三项 v1 遗留**（W9 自查续）：
  四套骨架的项目卡新增 `| 骨架 schema | 3 |` 一行——计划书写的是"骨架文件头加 schema"，之前只把版本放在
  `maintain.py` 常量与锁文件里，等于**没装过指纹的老项目说不清自己是哪版**；现在 schema 有三个来源，
  `migrate` 会在标题行说明用的是哪个（`←指纹` / `←AGENTS.md 声明` / 都没有才按 v1 猜），
  并由 `tests/test_maintain.py::test_skeleton_declares_its_schema_and_it_matches_maintain` 钉住
  "骨架声明 == `maintain.SCHEMA`"，两个来源不许漂。
  v1→v2 的步骤从四条补到七条，多出的三条正是计划书点名的演示内容：**删常驻规则卡 `T-000-board.md`**
  （I-001 之后它是反模式）、**`backlog/config.yml` 改成本骨架四列 `statuses`**（真工具默认英文三列，
  不改则 `-s doing` 被工具拒）、**刷新 I-001 之前那版不认识自授权的 `check.py`**
  （只在缺 `SELF_AUTHORIZED` 这个明确旧版特征时覆盖，其它差异交 `audit` 报漂移，不静默改人家的执法脚本）。
  `docs/demo/migrate_demo.py` 的 v1 夹具同步造出这三项遗留，演示实跑从"4 步待办"变"7 步待办"、
  核对项 7→10 全 OK，`docs/DEMO-migrate.md` 按新实跑输出重写（不是手改文字）。
  另修一处自查时暴露的顺序缺陷：`migrate --yes` 原来在"已是最新 schema"分支里提前返回，
  非 git 仓库也就没机会被拒绝——现在建不了备份分支就**先拒**，再谈有没有步骤。

- 2026-09-28 [缺陷修复] **对照计划书自查出的四处"说了但没做"**（我自己上一轮报"完成"时打的折扣，逐条补）：
  ① A3 的"同类摩擦 **≥2 才允许进待审**"只被 `improve --cross` 数出来，没写进门禁口径——
  `docs/EVOLUTION-PROCESS.md` 状态机"待审"行现在明确要求跨项目 ≥2，并指名去哪数；
  复现方式：`grep ≥2` 在待审行原本为 0 命中，新增 `tests/test_improve.py::test_pending_review_gate_requires_cross_project_count`。
  ② B3 承诺的机器客观维度里有 **fingerprint 校验**，`evolve.py` 一行都没实现——
  现在每条待审项都带 `装机指纹` 结论（缺 / 在 / schema 漂移三态，缺时给出 `maintain.py lock` 命令），
  记录 json 与终端输出各一份；`tests/test_evolve.py::test_fingerprint_check_distinguishes_missing_present_drifted`。
  ③ C4 点名的两个 audit 检测器都没有：**`.agent/` 外的 improvements 写入痕迹**（按 `| I-0xx |` 表格形状扫，
  命中即判"登记表写错位置"——写在别处的条目 improve/evolve 读不到，等于没登记）与
  **merge/rebase 这类不跑钩子的入口**（列最近 merge 提交与 reflog 痕迹，只点名不定罪，是否非法看合成态那一条）；
  `tests/test_maintain.py` 新增两条对应断言。
  ④ C5 写了"Copilot 带 YAML 头"却只生成纯文本 `.github/copilot-instructions.md`——补上官方路径特定指令格式
  `.github/instructions/coharness.instructions.md`（`applyTo: '**'`，格式取自 GitHub 官方文档），
  `ADAPTERS` 随之改成"一家可多文件"，`adapters --verify` 现在检查 6 个产物。 验证：`python -m unittest discover -s tests` 214 条 OK（skipped=4，expected failures=1）；带预言机跑同一命令 214 条 OK（skipped=0）；`docs/demo/migrate_demo.py` 实跑 10 项核对全 OK。

- 2026-09-28 [晋升 I-005@.coh-pilot-03] **所有权表优先于卡片边界：补齐口径同步与测试**（三证齐全的第一条晋升）。改动两处：`03-multi-harness-project/.agent/tasks/CARD-CONVENTION.md` 规则 1 下加子款——两源冲突以 `AGENTS.md` 单写者所有权表为准，卡只能收窄不能把表里"只读"扩成可写，扩权先改表走规则卡 + ADR，并**明写当前 `check.py` 没有读所有权表做自动拦截**（仍是纪律层约束）；`tests/test_protocol_smoke.py::test_i_ownership_precedence_is_one_voice_in_both_docs` 钉住两份文件都得说这条，并钉住"check.py 里没有读所有权表的代码"这个事实——将来谁加拦截，就必须同时把两份文档的说法改真。
  三证：diff 位置 `CARD-CONVENTION.md 规则 1 子款（2 行）+ tests/test_protocol_smoke.py（17 行）`，补丁 `D:/gongju/ai/VibeWorkspace/i005.patch`；来源项目 `.coh-pilot-03` I-005，触发事实为 `.coh-p2` 真会话 wt-b 提交 `58d9ce0`（照卡片边界改了 architect 独占的 `docs/ARCHITECTURE.md`）；测试运行标识 `trial-20260928-190816`（`evolve.py --apply-check` 的临时副本内 207 条 OK，skipped=7 = 3 条门禁 + 4 条预言机；副本新实例化项目全量 check rc=0）。审核存档连同机器取证与主观两维落在 `docs/audits/I-005-所有权表优先.md`。
  **如实记下流程偏差**：本条的裁决句本体（`03-multi-harness-project/AGENTS.md:36`）早在 commit `a90cf0c` 就已写回，而当时台账仍是「待审」——先写回、后审核，开的正是这条管线最该避免的先例。本次审核不掩盖它：CHANGELOG 与本行即为追认记录，补齐的是另外两处；往后晋升以 `--verify-record` 作硬门禁（缺「用户批准」一格就红，本轮已实测该格为空时确实红）。
  门禁自身的另一条实证：本次第一版补丁被 `--apply-check` 判红——新用例把"仍未执法"错断成"`check.py` 源码里不出现『所有权表』"，而它在注释里出现两处；断言写错了对象，副本内 207 条跑出 1 条 FAILED，改精确断言后才过。

- 2026-09-28 [演进] **发布工程：pip 可装、边界说清、验收对照成文**（计划书 W3 的代码侧 + 第 7 节对照）：
  ① 新增 `pyproject.toml`——三个面各给一个入口（`wsc` / `coharness-maintain` / `coharness-evolve`），
  骨架与文档作 package-data 随包走，**运行期依赖列表为空**（`python-frontmatter` 只进 `dev` extra，
  当差分预言机用，不进任何运行时路径，ADR-10）；`maintain.py`/`evolve.py` 改成双形态导入
  （装成包走 `from . import wsc`，clone/curl 直跑走同目录 `import wsc`）。
  本地实测：`uv build --wheel` → 干净 venv `pip install --no-build-isolation ./` →
  `wsc list` 列四套骨架、`wsc init 03` 复制出 26 个文件、`wsc check` 全绿。
  ② **改掉两条说谎的承诺**：README/SECURITY 原写"只下载 `wsc.py` 单文件即可 `init` 装骨架"——
  骨架文件就在 `wsc.py` 旁边，单文件根本没有它们（复现：把 `wsc.py` 单独拷进空目录跑 `init`，
  旧行为是报"可用骨架: []"却不解释）。现在文档写清边界，`init` 与 `list` 在无骨架目录时直接给出
  `git clone` / `pipx install coharness` 两条可执行替代；顺手为四套骨架补 `.gitattributes`
  （装机后首次 `git add` 的 24 条 CRLF 警告归零，执法面脚本与钩子在下游也钉 LF）。
  ③ 装机指纹改为**可提交**：`maintain.py lock` 不再写本机绝对路径（队友与 CI 都要能看出 schema 漂了没）。
  ④ W9 的"公开演示项目"落地为 `docs/demo/migrate_demo.py` + `docs/DEMO-migrate.md` 实跑记录
  （v1 形态是本轮改动之前的真实样子：`<骨架库>` 散文占位符、旧认领句、`.cursorrules`、缺降级节；
  dry-run 前后 `git status` 一致、`--yes` 前自动建 `coh-backup-*`、幂等、无仓库拒绝落盘）。
  ⑤ 双语 README 互链；`.github/ISSUE_TEMPLATE` 两模板 + PR 模板 + `CONTRIBUTING.md` 在 W14 已备，
  发布清单与草稿见 `docs/RELEASE-v1.1.0.md`（**打标 / Release / PyPI / Actions 首跑属对外动作，未执行**）。
  ⑥ 九项验收指标逐条对照写在 `docs/ACCEPTANCE-v1.1.md`：已证 4 项（stats/claim/migrate/adapters），
  部分成立 2 项（CI 本地绿但 Actions 未首跑、pip 已测但 pipx 与 Release 待执行 + 计时未在 CI 做），
  机制就绪但数据待发布 2 项（CHANGELOG 三证的第一条、克隆→开工 CI 计时），明确未成立 1 项（社区 star/外部 PR）。
  证据：新增 `tests/test_packaging.py` 6 条 + `tests/test_maintain.py` 加 1 条（指纹可移植）；
  全套 206 条 OK（skipped=4，expected failures=1），带预言机跑同一命令 skipped=0

- 2026-09-28 [演进] **适配语义桥、契约通知、社区文档三件**（计划书 W10 + W13 + W14）：
  ① `--adapter` 不再给各家写"同一句中文指针塞进五种文件名"，改为**按各家原生语法生成**——
  `.cursor/rules/coharness.mdc`（frontmatter `alwaysApply: true`）、`.windsurf/rules/coharness.md`
  （`trigger: always_on`，Wave 8 之前的 `.windsurfrules` 降级为"旧格式，不再生成"）、
  `CLAUDE.md`/`GEMINI.md` 用 `@AGENTS.md` 导入、`.github/copilot-instructions.md` 纯文本；
  产物一律只含指针 + 工具元数据（ADR-5），新增 `wsc adapters`（列表）/ `--verify`（查有没有变成第二权威：
  行数 >8、没指向 AGENTS.md、出现"必须/禁止"却无权威声明、`.mdc` 缺 frontmatter、旧单文件残留）/
  `--install`（装机后又来一家工具时补指针，已存在不覆盖）。语法格式不靠记忆：来源记在
  `tests/test_adapters.py` 的 `SOURCES`（Cursor 官方论坛 .mdc 深读、Windsurf Wave 8 规则目录说明等）；
  `maintain.py` 的 **schema 升到 3**，v2→v3 步骤只替换真有过旧适配的项目，没要过指针的项目不凭空生成。
  ② `wsc sync --dry-run`（W13）：不 pull、不装钩子、不 fetch（因此零网络），拿本地远端跟踪引用报告
  即将进来的改动，对照 03 骨架新增的「接口契约」表（路径前缀 → 契约定义在哪 → 变更要通知谁）与在看板的卡
  `allowed_paths`，打出 `[契约]` / `[边界]` 两类命中。**通知只落在自己的输出与交接说明里，不往别人的卡上写行**——
  他人卡的唯一写者是他自己，自动改他人卡就是制造第二权威；这一条按计划书原文实现时被我否掉，改为只读报告 +
  登记待议（计划书"在其它 doing 卡的交接说明生成变更提醒行"与本仓库所有权表直接冲突，按规则通道处理）。
  ③ 社区面（W14）：`CONTRIBUTING.md`（三条通道的判定表、登记门槛、`evolve.py` 的四步门禁、代码约束、
  PR 检查清单、明确"不接的东西"）、`docs/rfcs/`（README + `TEMPLATE.md` + **RFC-0001 认领原子化**：
  四个备选方案含"什么都不做"与被牺牲项，采纳 D）、`.github/ISSUE_TEMPLATE/` 两个模板（Bug 要求写得出
  红了的最小复现与对应测试名；改进提案要求先走项目登记表）、`.github/PULL_REQUEST_TEMPLATE.md`（三证 +
  用户批准 + 口径同步清单）、`SECURITY.md` 披露节从一句扩成四条路径。
  同步修正：`README.md` 里"会生成一行指针文件，内容就一句……"已被 ① 改真；`tests/test_wsc_current.py`
  钉旧契约的用例 `test_adapters_are_one_line_pointers` 改为 `test_adapters_are_native_format_pointers`
  （断言换成各家原生位置 + 指针仍薄 + 旧格式不再生成 + `adapters --verify` 必须过）。
  证据：`tests/test_adapters.py` 11 条、`tests/test_contracts.py` 6 条、`tests/test_maintain.py` 加 2 条
  （v2→v3 迁移与"不许凭空生成指针"）；全套 199 条 OK（skipped=4，expected failures=1）。
  分层收口：`wsc.py` 本轮最后一次抬上限到 1250，**之后新命令一律进 `maintain.py`**（写在
  `tests/test_distribution_surface.py` 的注释与 `CONTRIBUTING.md` 的代码约束里）

- 2026-09-28 [演进] **装机指纹 + schema 迁移 + 只读体检**（计划书 W9 + W12），落在新文件 `maintain.py`（维护面）：`lock <项目>` 写 `.agent/skeleton.lock`（骨架名 / 骨架库 commit / schema / adapters 清单 / `check.py` 的 sha256）；`migrate <项目>` 默认 dry-run 且**一个字不写**，加 `--yes` 才落盘并**先自动建备份分支** `coh-backup-<时间戳>`（回滚 = `git reset --hard` 那条分支），非 git 仓库直接拒绝落盘；`schema` 打印版本与步骤表。v1→v2 的四步升级不是演示，是本轮真做过的改动：补 `.gitignore` 的 `telemetry.jsonl`、把文档里的 `<骨架库>`/`<CoHarness>` 代入本机绝对路径、认领条款改首选 `wsc claim`、缺「降级行为」节就从骨架本体搬。`audit <项目>` 全程只读，四类问题各有判决：钩子缺失 / 钩子被改（与骨架本体逐字节比哈希）、`check.py` 与指纹不符（漂移）、**main 合成态违规**——最后一条把 I-004 变成可查的：两条分支各自合法、merge 进 main 后成同人两张 doing 卡（merge 不跑 pre-commit），audit 当场判不合法并列出行；文档同时写明不覆盖的范围（harness 自身网络与 IDE 遥测、模型 API、`--no-verify` 的事后痕迹只在 reflog 里可人工核对，不自动定罪）。分层：这些不进 `wsc.py`（分发面单文件承诺），`maintain.py` 只 `import wsc` 复用调用形状；`test_distribution_surface.py` 的三面上限表随之立住（`wsc.py` 上限放宽到 1100 并写明理由：curl 单文件不许把命令散进多文件；`check.py` 仍最严 650）。证据：`tests/test_maintain.py` 12 条，其中 `test_audit_flags_an_illegal_merged_board` 用真实的双 worktree 分叉 + merge 复现 I-004，未用 `--no-verify`；全套 180 条 OK（skipped=4，expected failures=1）

- 2026-09-28 [演进] **最小模式与依赖降级规格**（计划书 W4 + W11）：`wsc init <骨架> <路径> --minimal` 产出零外部依赖起步版——不复制 `backlog/`，任务清单换成项目根 `TODO.md`，并往 `AGENTS.md` 追加「最小模式」节**逐条写明关掉了什么**（卡片格式、改动挂卡、认领冲突、边界交集都以任务卡为前提）、**留住了什么**（命名规范、`.agent/improvements.md` 登记管线、钩子本身）；`check.py` 新增 `minimal_mode()`，无 `backlog/tasks` 且有 `TODO.md` 时把卡片层执法显式关闭并打印原因（不是静默跳过），`wsc sync` 改读 TODO.md 的 `- [ ]` 项。恢复路径是"放卡即生效"：往最小模式项目里补一张卡，改动挂卡当场重新拦（`check.py` 认文件不认工具）。同时把降级规格写成一处表一处文：`wsc.py` 里 `DEGRADE`（backlog / specify / worktrunk / node 的"丢了什么 / 降级行为 / 执法变化 / probe"）+ 四套骨架 `AGENTS.md` 各一节「降级行为」，新增 `wsc doctor --explain <项>` 与 `--simulate-missing=<项> <项目>`——后者不假装卸载，而是去项目里核对回落产物真在不在位（`[可用]` / `[不可用]` + 补救命令）。证据：`tests/test_minimal.py` 7 条（含"关掉的必须写明""没关的仍生效""补卡即恢复"）、`tests/test_degrade.py` 9 条（含表格与文档口径一致性：带 `scripts/check.py` 的骨架才允许提 TODO.md 回落，03 的降级节必须覆盖它声明过的四个依赖）

- 2026-09-28 [演进] **晋升审核命令化 + patch 化三证**（计划书 W5/W8）：新增库侧 `evolve.py`，四个动作各管一段——① `evolve.py <项目> --rubric` 从 `docs/EVOLUTION-PROCESS.md` 现读现印五条标准（不留第二套口径）；② `evolve.py <项目> --out 记录.json` 只做机器可数的客观维度：状态机合法性、同类摩擦跨项目计数（普遍性）、证据列点到的路径/commit 能否翻出来（真实性，整路径打不到时按文件名兜并说明）、提议落点预判与落点文件已有条款（兼容性提示）；**有效性与必要性仍归人/LLM，且必须写进记录的 `主观评估` 字段**；③ `--verify-record` 是写回前的机器门禁：结论必须 ∈ {晋升,继续试点,驳回}，判"晋升"必须两项主观评估齐 + 四项证据齐（diff 位置 / 来源项目 / 测试·CI 运行标识 / 用户批准），缺一即红——把 I-001 那次"自我迭代自开先例"的风险变成会报警的检查；④ `--apply-check 补丁.diff` 在临时副本里复制骨架库 → `git apply --check` → 套上跑全套自测 → 再从打了补丁的副本新实例化一个项目跑一次全量 `wsc check`（I-004"合并后无人复查"的最小实现），自测变红就拒绝且本体一个字不动。**分层修正**：这些能力原写进 `wsc.py`，实做后 wsc.py 涨到 1137 行、破了"分发面单文件读得动"与 `curl` 单文件承诺（同一轮里 `test_distribution_surface` 的行数上限测试就红了）——按 ADR-10 把审核面挪出分发面：晋升改的是本体，属维护者侧，`wsc.py` 回落到 857 行以内，新文件 `evolve.py`（同样受行数上限测试约束）只允许 `import wsc` 复用读表与调用形状。证据：`tests/test_evolve.py` 12 条（含两条真跑全套自测的门禁用例：文档补丁必须过、把断言改绝不可能命中的补丁必须红）、`tests/test_distribution_surface.py` 扩到 7 条并新增"分发面里不得残留 evolve 接线"；`docs/EVOLUTION-PROCESS.md` 的"审核方式/晋升操作"两节按四步重写。全套 152 条 OK（skipped=4，expected failures=1）；其中两条门禁用例各带一次副本内全套自测，整套跑时长从 95 秒涨到 350 秒——这是门禁要真跑就得付的价钱

- 2026-09-28 [演进] **本地运行记账 + `wsc stats` 三张报告**（计划书 W6）：`check.py` 每次执行往项目内 `.agent/telemetry.jsonl` 追加一行 `{ts, harness, checks{names/tasks/diff/stale 各项布尔}, rc, card, ms}`——harness 标识取 `COHARNESS_HARNESS`，回落 `git config user.name`，再回落 `unknown`；`--no-track` 或 `COHARNESS_NO_TRACK=1` 关闭；文件进骨架 `.gitignore`（不进版本库、不弄脏工作区，实测 `git status` 仍干净），写失败只打一行 stderr，执法不因记账失效。新增 `wsc stats <项目> [--days N]`：① 规则遵循率（按 harness 分组的 rc 全绿率 + 失分项明细）② 返工信号（`git log --name-only --since` 里同一文件被 ≥3 次提交触及，跨作者额外标注）③ stale 分布（转述 `check.py --stale`；stats 转述时带 `--no-track`，否则统计会把自己读到的数据写胖）。**口径冲突由本轮修正**：`SECURITY.md:6` 与 `README.md` 原写"不遥测任何内容 / 文件操作不出项目目录"，与刚落地的本地记账和上一落的 `~/.coharness/projects.json` 都不符——改成可核的口径（本地、零上传、可关可删、位置可用 `COHARNESS_HOME` 挪走）。同时把"check.py 五百余行/实测 544 行"这类会腐烂的手写行数从文档里去掉，改由新增 `tests/test_distribution_surface.py` 钉住：分发面两脚本只用标准库、无网络符号（`urlopen`/`socket.`/`Popen(`/`os.system` 与 12 个网络模块名）、无 eval/exec、行数在上限内（`wsc.py` ≤900、`check.py` ≤650），并断言文档里不得再出现写死的行数。证据：`tests/test_stats.py` 12 条 + `tests/test_distribution_surface.py` 6 条；全套 138 条 OK（skipped=4，expected failures=1）

- 2026-09-28 [演进] **真双 harness 并发认领演练取证**（`.coh-p4`，两个 `qodercli -p` 会话，模型 Qwen3.8-Flash/中度思考，各自独占一个 linked worktree，共享同一 `.git/hooks` 里的 pre-commit）：看板上只播一张 todo 卡，两会话同一时刻起跑，提示词里**没有**出现 `wsc claim`——两边都从实例项目内的 `AGENTS.md`/`parallel-protocol.md` 自己读到并执行了 `python <库>/wsc.py claim <wt> T-001 harness-<x>`。结果：a 抢到（`[claim] T-001 → harness-a（第 1 次尝试，已进 main）`，commit `f2d75fc`，随后按其卡完成 `docs/DRILL.md` 留痕 `2214d78`）；b 在命令内部同步后看到 `status: doing / assignee: [harness-a]`，当场被拒、未提交未推送、工作区干净（HEAD 停在 `f2d75fc`）。origin/main 上 T-001 归 harness-a，全程没用 `--no-verify`、没 force push。这条补齐 W7 的"并发下恰好一个成功"外部证据（本地证据是 `tests/test_claim.py` 的真双进程用例）；同时暴露一个可复现缺陷——骨架文档里的库路径写作 `<骨架库>`/`<CoHarness>` 散文占位符，实例化后原样留在下游项目里，见下一条

- 2026-09-28 [缺陷修复] **骨架文档里的库路径是散文占位符，命令不可执行**：`AGENTS.md`/`parallel-protocol.md`/`.agent/improvements.md` 写的是 `<骨架库>`、`<CoHarness>`，实例化后原样留在下游项目里——harness 读到自己项目内的"认领 = python <CoHarness>/wsc.py claim …"却不知道库在哪，只能猜路径或退回手工改卡（复现：`.coh-p4` 演练装机后 grep 实例项目，两处命令都带未替换的尖括号）。修法：统一成 `{{COHARNESS_LIB}}`，`wsc init` 复制时代入本机骨架库绝对路径（`instantiate` → `fill_library_path`），骨架本体仍保留占位符。证据：`tests/test_skeleton_integrity.py::test_library_path_is_resolved_at_instantiation`（实例项目里不得残留该占位符与 `<骨架库>`；实例化后的 AGENTS.md 与协议文件里必须出现 `python <库路径>/wsc.py claim`；骨架本体仍有占位符）。全套 120 条 OK

- 2026-09-28 [演进] **跨项目摩擦统计**（计划书 W7/A3）：`wsc init` 成功后把「项目路径 + 骨架名 + 骨架库 commit + 时间」追加进本机登记表 `~/.coharness/projects.json`（位置可用 `COHARNESS_HOME` 挪走，写失败只提示不阻断装机，纯本地零网络）；`wsc improve --cross` 按登记表扫全部实例，把非终态条目按「类别 + 提议改动」归并，输出机械计数与来源项目——晋升门槛"同类摩擦 ≥2 次"里可数的这一半从此有证据源，"是不是同一件事"仍留给人判，统计不做自动晋升。证据：`tests/test_registry_cross.py` 10 条（登记内容/重复 init 不重复登记/两项目同提议达门槛/孤证标注/终态条目不计数/不同提议不合并/失效路径跳过并计数/空表提示 COHARNESS_HOME/默认 improve 行为不变）；全套 119 条 OK

- 2026-09-28 [演进] **认领原子化：`wsc claim <项目> <卡号> <标识>`**（计划书 W7，闭口试点登记的 I-002）。把 fetch→变基→读卡校验→写卡（`status`/`assignee`/`updated_date`，只用声明子集语法）→跑项目自己的 `check.py --tasks`→真钩子 commit→`push origin HEAD:main` 绑成一步：任何一步不成都还原卡片，推送被拒则重新同步后再判一次（最多 3 轮），被抢就退回远端状态并列出此刻可认领的卡；工作区不干净当场拒绝；`--dry-run` 只报告不写盘。冲突判定不另写一套，全部复用 `check.py`，避免两套口径。演练取证的原缺陷：手工路径下 B 不 pull 就改同一张卡，`pull --rebase -X theirs` 会静默吃掉 A 的先占且无人报警——现在同步是命令内部动作，跳过同步就没有覆盖入口。证据：新增 `tests/test_claim.py` 9 条（成功/`--dry-run` 不写盘/非 todo/他人已占并列出可认领/脏工作区/边界交集被执法拒回并还原/无 origin 只本地认领/找不到卡/**真双进程同时认领同一张卡恰好一个成功**）；`tests/test_parallel_race.py::test_b` 摘掉 `expectedFailure` 改硬断言（worktree 拓扑下二次认领必败且落败方干净，之后仍能领走另一张卡）。全套 109 条 OK（skipped=4，expected failures 由 2 减到 1，只剩 I-004）。协议同步：`parallel-protocol.md` 认领节把 `wsc claim` 列为首选、手工路径保留为回落，`AGENTS.md` 看板行同改
- 2026-09-28 [缺陷修复] `SECURITY.md` 第 5 条写"check.py 五百行内"，实测 544 行——承诺与实际不符（本轮主题正是"README/SECURITY 的承诺要能验证"），改为"五百余行"

- 2026-09-28 [演进] 并发演练钉成 `tests/test_parallel_race.py`（bare origin + clone + 两个 linked worktree，全程真钩子，零外部依赖）：1 条硬断言证明自授权后的跨工作树认领能走通；3 条 `expectedFailure` 钉住仍未解决的规则缺口——I-002 双认领可被 `pull --rebase -X theirs` 静默覆盖、I-003 跨卡 `allowed_paths` 交集零检查、I-004 非法态能长期驻留 main（rebase/merge 不跑 pre-commit，push 不跑本地钩子，bare origin 无服务端钩子）。三条已在试点 `.agent/improvements.md` 登记（状态=登记），按管线攒证据与审核，不改执法代码。全套 95 条：OK（skipped=4，expected failures=3）
- 2026-09-28 [缺陷修复] **新 clone 零执法**：pre-commit 不入版本库，`git clone` 出来的合作区没有任何钩子，`AGENTS.md` 承诺的"所有工具的提交都过这一个钩子"对后来者不成立（实测：无钩子时违规文件照样 commit + push 成功 rc=0）。修法：`wsc sync`（协议规定的开工第一步）自愈——发现骨架带钩子而 git 认定的 hooks 目录里没有，就地补装并打印一行；已装好则不吭声。证据：`tests/test_hook_install.py::test_clone_then_sync_installs_the_hook`（补装后违规 commit 被拦，二次 sync 不重复打印）
- 2026-09-28 [演进] `docs/EVOLUTION-PLAN.md` 开"决策记录（ADR）"节并落 **ADR-10 · 依赖面按分发面分层**：`check.py` 随骨架复制进每个下游项目 ⇒ 纯标准库 + 只认 CARD-CONVENTION 子集 + 子集外响亮失败；`wsc.py` 同等，W3 发布后才复议；`python-frontmatter`/`pyyaml` 只作开发期差分预言机，不进分发物。据此否决优化计划书对照表里的 ADR-7（copier 替骨架分发：经 git URL 取模板，与零网络、clone 即用冲突）、ADR-8（运行时引 frontmatter/jsonschema）、ADR-9（pre-commit 框架装钩子）在本轮落地。重启条件与"翻案必须同步改 SECURITY.md/README 口径"一并写死
- 2026-09-28 [演进] 加 `.github/workflows/ci.yml`：`stdlib` job 在 ubuntu/windows × py3.11/3.13 上跑 `python -m unittest discover -s tests`（零安装，对应分发面的承诺），`oracle` job 用 uv 装 `python-frontmatter`+`pyyaml` 让差分用例真跑。同时加 `.gitattributes` 把脚本与钩子的换行钉在 LF——`wsc init` 复制的是逐字节的那份，被审计的钩子必须就是被执行的钩子。README 增"自测"一节。**如实标注**：本机没有 `act`/`docker`，Actions 未在本地跑过，首次真跑发生在 push 之后，不作为已完成证据
- 2026-09-28 [演进] 差分预言机测试落盘（`tests/test_frontmatter_differential.py`）：同一批夹具分别喂给自写子集解析器与 `python-frontmatter`（PyYAML），断言子集内的卡片解析结果一致；子集外则钉住"我们主动拒绝、预言机却能解析"的 8 条名单（duplicate-key / block-scalar / flow-map / anchor / list-in-list / nested-map / multiline-scalar / scalar-then-item），另 7 条连 YAML 都不合法、两边一致。预言机只活在开发期与 CI（ADR-10：不进分发物），未装时整文件 skip——零依赖跑法照旧 `python -m unittest discover -s tests`（86 条 OK, skipped=4, expected failures=2）。首轮实跑就纠正了名单里 4 处凭想象写错的政策项
- 2026-09-28 [缺陷修复] 与真 Backlog.md 1.53.0 对齐（首次真装真跑，装在 `D:\gongju
ode.js
ode_global`）：① `check.py load_config` 读的键名是 `columns`，真工具写的是 `statuses` → 配置永远读不到、回落默认四列；② 行内列表解析不剥引号，而真配置恰是 `statuses: ["To Do", "In Progress", "Done"]` → 解出带引号的列名，任何状态都被判"非法"；③ 骨架硬写的 `backlog task edit -a x -s doing` 被真工具当场拒（默认词表是英文三列），`wsc init` 的依赖提示改为要求编辑 `backlog/config.yml` 的 `statuses`+`default_status`（`backlog config set statuses` 被工具拒绝直改），并写明 `--agent-instructions` 会往 AGENTS.md 注入 24 行自家说明、本骨架要求填 `none`；④ 工具按 `t-<n> - <标题>.md` 认卡，手工建的 `T-001.md` 它不列（执法读得到、看板 CLI 看不见），`backlog/tasks/README.md` 写清两条路的分界。真卡 frontmatter（`'@name'` 块列表、带引号 datetime、`ordinal` 等额外字段）实测全在子集内，原文已钉成测试。证据：`tests/test_check_current.py` 新增 3 条（①②两条改动前红），全套 91 条 OK
- 2026-09-28 [晋升 I-001@.coh-pilot-03] **卡片文件（`backlog/tasks/*.md`）与 `.agent/improvements.md` 改为自授权改动**：认领、状态流转、改进登记不再需要被某张卡的 `allowed_paths` 覆盖，直接 commit + push main。晋升依据是并发演练 D0：绕行方案（常驻规则卡）实测**无路可走**——持它领实现卡撞"一 harness 一张 doing 卡"（rc=1），退回它又卡在"该卡仍为 todo"（rc=1），退+领同一提交同样 rc=1，且常驻卡一旦领了就退不回；历史里除了装机提交一步都没落进去。据此删除常驻卡 `T-000-board.md`，`parallel-protocol.md` 与 `AGENTS.md`、`CARD-CONVENTION.md` 规则 1/2/4 同步改写；规则文件（`AGENTS.md`、`.agent/roles|workflows|tasks`）不在自授权之列，仍串行。
  同批修掉 A3 假阳性：`check_diff` 原先"任一覆盖卡是 todo 即违规"，重叠边界会让没被认领的卡诬告已认领的一方（演练里已认领的 harness 被告知"应先认领"）；改为**禁改优先**——任何一张覆盖卡点名 forbidden 即拒绝（别的卡的 allowed 不能绕过，这是安全语义不能松），无人认领才报 todo。
  `tests/test_protocol_smoke.py` 的两条 `expectedFailure` 翻成硬断言（正是它们设计的翻转信号），并补三条：登记后可读回、规则文件仍非自授权、重叠边界不再诬告已认领方。全套 88 条 OK（skipped=4，无 expected failure）
- 2026-09-28 [演进] R2 规则缺口的**绕行**落骨架（不改执法代码）：协议要求的三类提交——认领（改自己卡的 assignee/status）、看板状态流转、`.agent/improvements.md` 登记——在 `check.py` 的挂卡执法里没有授权通道（`backlog/` 与 `.agent/` 是每张卡 `forbidden_paths` 的默认值，卡自身改动又必须挂卡才放行），冒烟实测全新装机后按协议走第一步就 `rc=1`。03 骨架随带常驻规则卡 `backlog/tasks/T-000-board.md`（allowed_paths 含 `backlog/` 与 `.agent/improvements.md`）；`parallel-protocol.md` 新增"看板改动与登记怎么提交"节，写明四步绕行与"持卡期间不得再持实现卡"这条硬约束；AGENTS.md 任务看板节加一行指过去。**缺口本身**按管线登记为 `I-001`（状态：登记，落在试点项目 `../.coh-pilot-03`，不动本体规则），攒够第二次同类摩擦或经 evolve 审核后再定放行方案。证据：`tests/test_protocol_smoke.py` 6 条 = 4 条硬断言（首次入库过钩子 / 两 harness 并行各自交工 / 一 harness 双 doing 卡被拦 / 常驻卡绕行真能跑通且 improve 读得到）+ 2 条 `expectedFailure`（认领与登记本不该再挂卡）——缺口修好后那两条会以 unexpected success 报错逼摘标记。全套 82 条 OK（expected failures=2）
- 2026-09-28 [演进] 骨架的目录地图由"虚构"变"真存在"：`wsc init` 只复制文件、不建目录，而四套骨架的目录地图/角色文件引用了一批从来不存在的路径——01 `src/`+`tests/`、02 `docs/notes.md`（debug/assignment 流程要往里写）、03 `code/`+`backlog/tasks/`+`docs/reviews/`+`docs/regression/`、04 `docs/CHANGELOG.md`。其中 `03/backlog/tasks/` 最要命：目录不存在时 `load_cards` 返回空集，整套执法静默空转。按 02 既有的"目录里放 README.md"惯例补齐 8 个文件；`docs/rfc/`、`tests/fixtures/` 这类"用到时自建"的改为在原文里写明自建。孤儿占位符一并归并到项目卡能解释的名字：`{{EXAM_DATE}}`→`{{DUE_DATE}}`、`{{EXAM_NAME}}`→`{{PROJECT_NAME}}`、`{{REPORT_TEMPLATE}}`→新增卡行 `{{FORMAT_TEMPLATE}}`（与 04 同名）、`{{BACKEND/FRONTEND_COMPONENT}}`→改指组件地图、`{{DATE}}`→`YYYY-MM-DD`；01/04 的 `tasks/TEMPLATE.md` 自身用了子集外 YAML（裸 `-`、缩进 `[]`），按新声明的子集改正。"05 骨架"笔误：`ROUTER.md` 就地改，`docs/EVOLUTION-PLAN.md` 带日期的原文不动、文末追加补注。证据：`tests/test_skeleton_integrity.py` 4 条（目录地图声明 / AGENTS+README 路径引用 / 占位符必须能被项目卡解释 / 骨架不带运行残留），改动前 4 红、全套 76 绿
- 2026-09-28 [缺陷修复] `wsc improve` 永远打印"无待处理改进"：读取端只收以 `| I-` 开头的行，而 4 份 `.agent/improvements.md` 模板给的示例行是 `| （示例） |`，`I-xxx` 编号约定只写在骨架库 `docs/EVOLUTION-PROCESS.md`（实例化后根本不在项目里），骨架内没人被告知——登记了条目也读不出来，头部卖点"会自己进化的模板"读取链路是断的。改：模板把示例移出表体、在表头注里写明"编号自 `I-001` 起递增"（4 份保持逐字节相同）；`cmd_improve` 改为按 Markdown 表格解析，跳过表头/分隔行，编号不合 `I-xxx` 与状态不在状态机（登记/试点中/待审/已晋升/已驳回）的都**打警告而不是静默丢弃**。证据：`tests/test_improve.py` 5 条（改动前 4 红），全套 72 绿
- 2026-09-28 [缺陷修复] pre-commit 装机只认 `dst/.git` 是目录：linked worktree 下 `.git` 是文件（而 parallel-protocol 规定一 harness 一 worktree，这是主装机路径），装不上；目标非仓库时静默跳过不打字——而 03/AGENTS.md 承诺"wsc init 自动安装"。改：用 `git rev-parse --path-format=absolute --git-path hooks` 问 git 自己（git<2.43 回落 `--git-dir` + `commondir`），worktree 装进主仓库的公共 hooks 目录、所有 worktree 共享同一执法点；目标不是仓库根时**不写任何东西**，只打印可执行提示（顺带堵住把项目钩子装进外层仓库）。钩子本体的解释器从硬编码 `python` 改为 `python`/`python3`/`py -3` 逐个真跑 `-c "import sys"` 探测（WindowsApps 的 `python3` 占位符 `command -v` 找得到但一跑就废），三者皆废则 exit 1 拦住提交而非静默放过。`SECURITY.md` 第 4、5 条同步改口径。证据：`tests/test_hook_install.py` 7 条（改动前 6 红，全套 67 绿）
- 2026-09-28 [演进] check.py 的卡片解析收窄成 CARD-CONVENTION 子集 + 响亮失败（ADR-10：check.py 随骨架复制进每个下游项目，必须保持纯标准库零依赖）。`parse_frontmatter` 与 `_yaml_list_under` 两套正则合并为一个 tokenizer；嵌套 map、块标量 `|`/`>`、行内 `{}`、锚点/别名、多行续值、制表符缩进、重复键、`---` 不闭合、BOM 一律报 `文件:行号` 加改写提示并让提交失败，不再静默给出错的值。顺带修掉一个静默 bug：`title:` 空值被读成空列表，`str([])="[]"` 非空，"title 为空"这条执法从未生效过。`CARD-CONVENTION.md` 增补"支持的写法子集"节（此前只声明字段、没声明语法边界）；`SECURITY.md` 的"约 300 行纯标准库"按实测 496 行改为"五百行内"。证据：`tests/test_card_subset.py` 9 条 + 23 个夹具（`tests/fixtures/{good,unsupported,boundary}/`），全套 60 条绿
- 2026-09-28 [缺陷修复] `check.py --diff` 判错了对象：用 `git status --porcelain`（整个工作区，含没 add 的文件与被折叠成目录的未跟踪项），导致全新实例化的项目**连第一个提交都被自己的钩子拦死**（骨架本体每个文件都"未挂任何任务卡"），只能 `--no-verify`。复现：`cp -r 03-multi-harness-project p && cd p && git init && cp scripts/hooks/pre-commit .git/hooks/ && git add -A && git commit`。修：改判本次提交的暂存集（`git diff --cached --name-only`，含删除、重命名取新路径、`core.quotepath=false`），仓库尚无提交时跳过执法并明确提示；`CARD-CONVENTION.md` 规则 1 同步写明"判暂存集、首个提交不执法"。证据：`tests/test_check_diff.py` 8 条（改动前 4 红）
- 2026-09-28 [缺陷修复] 简体中文 Windows（默认 cp936 控制台）上 `wsc check` / `wsc sync` 崩溃、`wsc init`/`improve` 的中文报错经管道后乱码：wsc.py 的子进程调用未写 encoding，把 check.py 的 utf-8 输出按 GBK 解码抛 UnicodeDecodeError；两个脚本又只重配置 stdout 不管 stderr。修法：新增 `_run()` 统一显式 utf-8 解码、子进程解释器由 PATH 别名 `python` 改为 `sys.executable`、stdout+stderr 一并 utf-8。复现与验证：`tests/test_console_encoding.py`（改动前 4 条红，改动后 43 条全绿）
- 2026-09-28 [演进] 新增骨架库自测 `tests/`（36 条，纯标准库 unittest，`python -m unittest discover -s tests` 零安装可跑）：EVOLUTION-PLAN.md 附录里 2026-09-26 手工跑过、从未落盘的 check.py 断言全部钉成可重复执行的测试；覆盖命名规范、卡格式与认领冲突、stale advisory、pre-commit 端到端拦截、wsc init 三种目标与适配指针
- 2026-09-26 [演进] 建立自我迭代管线（登记→试点→审核→晋升）：新增 EVOLUTION-PROCESS 与本日志；4 套骨架加 improvements 登记模板与纪律行；wsc.py 加 improve 子命令；collab-zone skill 加 evolve 指令；ROUTER.md 加推荐能力节
