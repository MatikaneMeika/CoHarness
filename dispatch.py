"""CoHarness 委托与唤醒门面：候选 → 预选 → 计划 → 拉起（唯一写路径）。

边界（见 docs/rfcs/RFC-0003-委托与唤醒.md）：委托记录全在 git——卡状态、`claim` 写的
`branch.<分支>.coharness-card` 绑定、工作树在场。唤醒是无状态的一次性动作：拉起进程后
立刻失联，不持有句柄、不读子进程输出、不记运行时状态、不自动重试、不改派。
越线判据：把本进程杀掉再重启，状态一条都不丢。

不另写一套判定：卡片经**项目自己的** scripts/check.py 读（board.load_check），依赖就绪
与边界冲突复用 check.boundary_intersection，角色复用 board.role_of（最长匹配所有权表）。
预选是写死的确定性规则（依赖就绪的 todo 里取卡号最小），人可随时覆盖。

副作用只在 launch() 里，且注入替身后可整条断言：claim → 建工作树 → 开新终端。
"""
import argparse
import os
import shlex
import re
import shutil
import subprocess
import sys
from pathlib import Path

try:                                   # 装成包时按包内模块导入
    from . import board
except ImportError:                    # curl/源码树直跑
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import board

TABLE_REL = ".agent/dispatch.md"
WSC = Path(__file__).resolve().parent / "wsc.py"
UNKNOWN = board.UNKNOWN_ROLE

def which(tool):
    """工具是否在 PATH 上（替身注入点：测试不依赖本机装了什么 CLI）。"""
    return shutil.which(tool)

def load_table(project):
    """读项目侧 `.agent/dispatch.md` 的「角色 → 启动命令」表；缺表返回 {}，不猜。"""
    f = Path(project) / TABLE_REL
    if not f.is_file():
        return {}
    rows = {}
    for line in f.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not (s.startswith("|") and s.endswith("|")):
            continue
        cells = [c.strip().strip("`").strip() for c in s.strip("|").split("|")]
        if len(cells) < 2 or set("".join(cells[:2])) <= set("-: ") or cells[0] in ("角色", "role"):
            continue
        rows[cells[0]] = cells[1]
    return rows

def _quote_arg(value):
    return subprocess.list2cmdline([str(value)]) if os.name == "nt" else shlex.quote(str(value))

def _card_number(cid):
    """卡号排序键：取第一段数字，再拿完整卡号兜平局（同号不同后缀也稳定）。"""
    m = re.search(r"\d+", str(cid))
    return (int(m.group()) if m else 1 << 30, str(cid))

def _scan(project):
    """候选与受阻一次算清：todo + 无人认领 + 依赖就绪 + 边界不与在做卡冲突。"""
    # check.py 的 ROOT 会 resolve；先对齐它，macOS 的 /var 符号链接才不会炸 relative_to()。
    project = Path(project).resolve()
    check = board.load_check(project)
    tasks_dir, _columns = (check.load_config() if hasattr(check, "load_config")
                           else (project / "backlog" / "tasks", []))
    cards, _errors = check.load_cards(tasks_dir)
    facts = board.project_card_facts(project)
    owners, known = facts["owners"], facts["roles"]
    done = {str(c["meta"].get("id")) for c in cards if c["status"] == "done"}
    on_air = [c for c in cards if c["status"] in ("doing", "review")]
    cands, blocked = [], []
    for c in cards:
        if c["status"] != "todo" or c["assignees"]:
            continue
        cid = str(c["meta"].get("id"))
        deps = c["meta"].get("dependencies") or []
        if isinstance(deps, str):
            deps = [deps]
        waiting = [str(d) for d in deps if str(d) not in done]
        hits = [str(o["meta"].get("id")) for o in on_air
                if check.boundary_intersection(c["allowed"], o["allowed"])]
        if waiting or hits:
            blocked.append((cid, sorted(set(waiting + hits))))
            continue
        raw = board.role_of(c["allowed"], owners)
        role = UNKNOWN if raw == UNKNOWN else board.role_label(raw, known)
        cands.append({"id": cid, "role": role,
                      "allowed": list(c["allowed"]),
                      "rel": str(c["path"].relative_to(project)).replace(os.sep, "/")})
    cands.sort(key=lambda c: _card_number(c["id"]))
    blocked.sort(key=lambda b: _card_number(b[0]))
    return cands, blocked

def candidates(project):
    """依赖就绪、边界不冲突的 todo 卡（无人认领），按卡号升序。"""
    return _scan(project)[0]

def blocked(project):
    """被依赖或边界挡住的 todo 卡：[(卡号, [挡它的卡号…])]，按卡号升序。"""
    return _scan(project)[1]

def pick(cards):
    """确定性预选：依赖就绪的 todo 里取卡号最小；空候选返回 None。"""
    return min(cards, key=lambda c: _card_number(c["id"])) if cards else None

def _worktree_path(project, card):
    """工作树落在项目外的兄弟目录：`<项目名>.wt/<卡号>`（不污染项目自身）。"""
    root = Path(project).resolve()
    return root.parent / f"{root.name}.wt" / (str(card) or "card")

def _harness_id(project):
    """这次派发是谁：环境变量优先，其次 git user.name；都没有就返回空串。"""
    env = os.environ.get("COHARNESS_HARNESS", "").strip()
    if env:
        return env
    r = subprocess.run(["git", "config", "user.name"], cwd=str(project),
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    name = (r.stdout or "").strip()
    return name if r.returncode == 0 else ""

def _git_in(cwd, *args):
    """在指定目录跑一条只读 git 命令；失败返回空串。"""
    r = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    return (r.stdout or "").strip() if r.returncode == 0 else ""

def _common_git_dir(cwd):
    raw = _git_in(cwd, "rev-parse", "--git-common-dir")
    path = Path(raw) if raw else None
    return (path if path.is_absolute() else Path(cwd) / path).resolve() if path else None

def _install_hint(tool):
    return f"先装 {tool} 并确认它在 PATH（安装方式由该工具提供），或改 {TABLE_REL} 的启动命令"

def plan(project, card=None, tool=None, who=None):
    """出一次派发计划：选卡 → 推角色 → 解析命令 → 探工具。不产生任何副作用。"""
    project = Path(project).resolve()
    cands, _blocked = _scan(project)
    chosen = (next((c for c in cands if c["id"] == card), None) if card else pick(cands))
    cid = chosen["id"] if chosen else (card or "")
    role = chosen["role"] if chosen else ""
    who = (who or "").strip() or _harness_id(project)
    worktree = _worktree_path(project, cid)
    reasons, ready = [], True
    if not who:
        ready = False
        reasons.append("缺 harness 身份：设置 COHARNESS_HARNESS 或 git user.name")
    if chosen is None:
        ready = False
        reasons.append(f"没有可派的 todo 卡（{card} 不在候选里：非 todo / 已被认领 / 依赖未就绪 / 边界冲突）"
                       if card else "没有可派的 todo 卡（依赖未就绪或边界冲突）")
    elif role == UNKNOWN:
        ready = False
        reasons.append(f"卡 {cid} 的边界没落进所有权表（AGENTS.md 单写者所有权表）")
    table = load_table(project)
    if not table:
        ready = False
        reasons.append(f"缺 {TABLE_REL} 启动命令表（角色 → 启动命令），无法解析启动命令")
    template = table.get(role) if role and role != UNKNOWN else None
    if chosen is not None and role and role != UNKNOWN and template is None:
        ready = False
        reasons.append(f"角色 {role} 在 {TABLE_REL} 里没有启动命令")
    tool_name, command = "", ""
    if template:
        head, _sep, tail = template.partition(" ")
        tool_name = (tool or head)
        command = (tool_name + (" " + tail if tail else "")) if tool else template
        command = command.replace("{worktree}", _quote_arg(worktree)).replace("{card}", _quote_arg(cid))
    tool_missing = bool(tool_name) and which(tool_name) is None
    if tool_missing:
        ready = False
        reasons.append(f"{tool_name} 不在 PATH：{_install_hint(tool_name)}")
    return {"card": cid, "role": role, "tool": tool_name, "command": command, "who": who,
            "worktree": worktree, "ready": ready, "reasons": reasons,
            "tool_missing": tool_missing}


def _claim(project, card, who):
    """走 `wsc claim` 这一条既有认领路径（原子、过钩子、写分支绑定），不另写一套。"""
    r = subprocess.run([sys.executable, str(WSC), "claim", str(project), str(card), str(who)],
                       cwd=str(project), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return r.returncode == 0, (r.stdout or "") + (r.stderr or "")

def _worktree(project, path, card):
    """建工作树：一律走原生 `git worktree add`。

    不用 git-wt（worktrunk）：0.80.0 无 add 子命令且 switch -c 无法满足
    dispatch 指定路径（<项目名>.wt/<卡号>）契约；坚守契约不改路径。
    """
    path = Path(path)
    if path.exists():
        root = _git_in(path, "rev-parse", "--show-toplevel")
        branch = _git_in(path, "rev-parse", "--abbrev-ref", "HEAD")
        same_repo = _common_git_dir(path) == _common_git_dir(project)
        if (root and Path(root).resolve() == path.resolve() and same_repo
                and branch == f"coh/{card}"):
            return True, ""
        return False, (f"路径已存在但不是本卡的 worktree：{path}"
                      f"（git root={root or '不是 git 仓库'}，branch={branch or '未知'}，"
                      f"same_repo={'yes' if same_repo else 'no'}）")
    argv = ["git", "worktree", "add", "-b", f"coh/{card}", str(path)]
    r = subprocess.run(argv, cwd=str(project), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        out = ((r.stdout or "") + (r.stderr or "")).strip()
        return False, f"argv={argv} returncode={r.returncode}" + (f"\n{out}" if out else "")
    return True, ""


def _spawn_default(command, cwd):
    """开新终端跑命令；拉起后立刻失联——不读输出、不持有句柄、不等待。"""
    try:
        if os.name == "nt":
            parts = shlex.split(command, posix=False)
            parts = [p[1:-1] if len(p) >= 2 and p[0] == p[-1] == '"' else p for p in parts]
            argv = ["cmd", "/c", "start", "", "cmd", "/k", *parts]
        else:
            argv = ["x-terminal-emulator", "-e", "bash", "-lc", command]
        subprocess.Popen(argv, cwd=str(cwd), stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError as e:
        return False, str(e)
    return True, ""


def launch(project, plan, spawn=None):
    """认领 → 建工作树 → 开新终端 → 返回并失联。失败只上报：不重试、不改派。"""
    project = Path(project).resolve()
    if not plan.get("ready"):
        raise SystemExit("[dispatch] 未就绪，不派发：" + "；".join(plan.get("reasons") or ["未知原因"]))
    card, who = plan["card"], plan.get("who", "")
    if not who:
        raise SystemExit("[dispatch] 缺 harness 身份，不派发（设置 COHARNESS_HARNESS 或 git user.name）")
    ok, detail = _claim(project, card, who)
    if not ok:
        raise SystemExit(f"[dispatch] 认领 {card} 失败，不派发、不重试：\n{detail.strip()}")
    ok, detail = _worktree(project, plan["worktree"], card)
    if not ok:
        raise SystemExit(f"[dispatch] 建工作树失败，不派发、不重试：\n{detail.strip()}")
    ok, detail = (spawn or _spawn_default)(plan["command"], plan["worktree"])
    if not ok:
        raise SystemExit(f"[dispatch] 拉起失败，不派发、不重试：\n{detail.strip()}")
    return {"ok": True, "card": card, "worktree": str(plan["worktree"])}


def advance(project, card=None, tool=None, who=None, spawn=None):
    """plan + launch：协议步骤（收工唤醒）调用的那一口气。失败只上报，不重试、不改派。"""
    project = Path(project).resolve()
    p = plan(project, card=card, tool=tool, who=who)
    launch(project, p, spawn=spawn)
    return p

def _report(project, p):
    """默认动作：只列候选与预选，不执行任何写路径。"""
    cands, waits = _scan(project)
    if not cands:
        print(f"[dispatch] {Path(project).name} 没有可派的 todo 卡。")
        for cid, why in waits:
            print(f"  - {cid} 受阻：{', '.join(why)}")
        return 1
    print(f"[dispatch] 候选（{len(cands)}）：")
    for c in cands:
        print(f"  {'→' if c['id'] == p['card'] else ' '} {c['id']}  {c['role']}")
    for cid, why in waits:
        print(f"  - {cid} 受阻：{', '.join(why)}")
    print(f"[dispatch] 预选 {p['card']} → {p['role']}：{p['command'] or '（命令未解析）'}")
    if not p["ready"]:
        for reason in p["reasons"]:
            print(f"[dispatch] 未就绪：{reason}")
        return 1
    print(f"[dispatch] 就绪。跑 `coh-dispatch {project} --advance` 才真拉起。")
    return 0

def main(argv=None):
    board.wsc._utf8_streams()
    ap = argparse.ArgumentParser(
        prog="coh-dispatch",
        description="CoHarness 委托与唤醒：列候选 / 一次性拉起（认领 + 工作树 + 新终端）")
    ap.add_argument("project", nargs="?", default=".", help="项目路径（默认当前目录）")
    ap.add_argument("--advance", action="store_true",
                    help="派发一次：认领 + 建工作树 + 开新终端，然后失联")
    ap.add_argument("--card", help="显式指定卡号，覆盖确定性预选")
    ap.add_argument("--tool", help="显式指定 CLI，覆盖启动命令表里的工具")
    ap.add_argument("--who", help="显式指定 harness 身份，覆盖 COHARNESS_HARNESS 与 git user.name")
    args = ap.parse_args(argv)
    project = Path(args.project).resolve()
    p = plan(project, card=args.card, tool=args.tool, who=args.who)
    if not args.advance:
        return _report(project, p)
    launch(project, p)
    print(f"[dispatch] 已拉起 {p['card']} → {p['role']}（{p['tool']}），本进程到此失联")
    return 0


if __name__ == "__main__":
    sys.exit(main())
