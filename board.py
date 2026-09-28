"""CoHarness 展示面的数据装配与渲染（终端 IO 在 panel.py）。

职责边界：这里只**读**并把事实拼成可断言的结构——project_snapshot() 出纯数据，
render_*() 出字符串行，navigate() 是纯状态机。按键、清屏、刷新节奏都在 panel.py，
所以这个文件里每个函数都能被 unittest 直接吃。卡片解析一律用项目自己的
scripts/check.py：不写第二套口径（与 wsc claim 同一条原则）。
"""

import os
import re
import subprocess
import sys
import time
import types
import unicodedata
from datetime import datetime
from pathlib import Path


try:                                   # 装成包时按包内模块导入
    from . import wsc
except ImportError:                    # curl/源码树直跑
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import wsc

CORE = ("integrator", "pm", "architect", "reviewer", "tester", "doc-writer")
UNKNOWN_ROLE = "边界没落进所有权表"
WATCH_SECONDS = 5
INACTIVE_HOURS = 24

RESET, BOLD, DIM, RED, GREEN, YELLOW, CYAN, MAGENTA = (
    "\033[0m", "\033[1m", "\033[2m", "\033[31m", "\033[32m",
    "\033[33m", "\033[36m", "\033[35m")
MARKS = {"ok": "✓", "bad": "✗", "warn": "!", "idle": "·", "cursor": ">", "bar": "#"}



def _bar(done, total, width=10):
    if not total:
        return "—"
    filled = int(round(width * done / total))
    return "[" + MARKS["bar"] * filled + "." * (width - filled) + f"] {done}/{total}"


def dw(text):
    """显示宽度：中日韩字符占两列，按 len() 算会让中文列错位。"""
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in str(text))


def clip(text, width):
    """按显示宽度截断。"""
    out, used = "", 0
    for ch in str(text):
        w = 2 if unicodedata.east_asian_width(ch) in "WF" else 1
        if used + w > max(0, width - 1):
            return out + "…"
        out, used = out + ch, used + w
    return out


def pad(text, width):
    s = str(text)
    return s + " " * max(0, width - dw(s))


def rpad(text, width):
    return " " * max(0, width - dw(str(text))) + str(text)


def _clip_left(text, width):
    """路径要保尾巴（区分 proj/p 的在最后一节），所以从左截。"""
    text = str(text)
    return text if len(text) <= width else "…" + text[-(width - 1):]


def _clip(text, width):
    text = str(text)
    if len(text) <= width:
        return text
    return text[:max(0, width - 1)] + "…"


def _git(project, argv, timeout=15):
    """跑 git；返回 (ok, stdout)。非仓库/超时都算失败但不炸。"""
    try:
        r = subprocess.run(["git", *argv], cwd=str(project), capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return False, ""
    return r.returncode == 0, (r.stdout or "")


def _hours_since(text):
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            then = datetime.strptime(text.strip(), fmt)
        except ValueError:
            continue
        return (datetime.now() - then).total_seconds() / 3600
    return 1e9


def _norm_prefix(s):
    return str(s).strip().strip("`").strip("/")


ROLE_STEMS = ("integrator", "architect", "reviewer", "tester", "doc-writer", "coder", "pm")


def _table_rows(text, heading, ncols):
    """读 Markdown 表格体（跳过表头与分隔行）。所有权表/契约表/项目卡共用这个形状。"""
    if f"## {heading}" not in text:
        return []
    section = text.split(f"## {heading}", 1)[1].split("\n## ", 1)[0]
    rows = []
    for line in section.splitlines():
        s = line.strip()
        if not (s.startswith("|") and s.endswith("|")):
            continue
        cells = [c.strip().strip("`").strip() for c in s.strip("|").split("|")]
        if len(cells) < ncols or set("".join(cells[:ncols])) <= set("-: "):
            continue
        rows.append(cells)
    return rows


def _title(lines, text, width):
    lines.append(MARKS["bar"] * 3 + " " + text + " " + MARKS["bar"] * max(0, width - len(text) - 5))
    return lines


def checklist(body):
    """卡体「验收清单」节的勾选项：返回 (已勾, 总数, [(勾, 文本)])。没有这节就是 (0,0,[])。"""
    if "## 验收清单" not in body:
        return 0, 0, []
    section = body.split("## 验收清单", 1)[1].split("\n## ", 1)[0]
    items = []
    for line in section.splitlines():
        m = re.match(r"^\s*[-*]\s*\[([ xX])\]\s*(.*)$", line)
        if m:
            items.append((m.group(1).lower() == "x", m.group(2).strip()))
    return sum(1 for d, _ in items if d), len(items), items


def collect_projects(args):
    """顶层数据源：命令行给的项目优先，其余来自本机登记表（活着的）。"""
    paths = [Path(p).resolve() for p in args.projects if Path(p).is_dir()]
    seen = {str(p) for p in paths}
    for e in wsc.read_registry():
        p = Path(str(e.get("path", "")))
        if p.is_dir() and str(p) not in seen and (p / "scripts" / "check.py").is_file():
            paths.append(p.resolve())
            seen.add(str(p))
    return paths


def commits_touching(project, prefixes, limit=3):
    """卡边界内的提交：返回 (总次数, 最近几条, 作者集合)。git 不可用时给 (0, [], set())。"""
    paths = [_norm_prefix(p) for p in prefixes if _norm_prefix(p)]
    if not paths:
        return 0, [], set()
    ok, out = _git(project, ["log", "-n", "50", "--name-only", "--pretty=format:@@%h|%an|%ar",
                             "--", *paths])
    if not ok:
        return 0, [], set()
    commits, cur = [], None
    for line in out.splitlines():
        if line.startswith("@@"):
            sha, author, ago = line[2:].split("|")
            cur = {"sha": sha, "author": author, "ago": ago}
            commits.append(cur)
        elif line.strip() and cur is not None:
            cur.setdefault("files", set()).add(line.strip())
    authors = {c["author"] for c in commits}
    return len(commits), commits[:limit], authors


def current_page_lines(snapshots, state, width, color):
    """按当前页渲染；返回 (lines, ids)。ids[cursor] 就是"进入"要选中的那个对象的下标。"""
    if state["page"] == "projects":
        rows = []
        for s in snapshots:
            active = [c for c in s["cards"] if c["status"] in ("doing", "review")]
            rows.append({"name": s["label"], "skeleton": s.get("skeleton", ""),
                         "doing": len(active),
                         "todo": sum(1 for c in s["cards"] if c["status"] == "todo"),
                         "flags": sum(1 for c in s["cards"] if c["flags"]),
                         "errors": len(s["card_errors"])})
        return render_projects(rows, state["cursor"], width, color), list(range(len(rows)))
    snap = snapshots[state["sel"]]
    if state["page"] == "tasks":
        lines, order = render_tasks(snap, state["cursor"], width, color)
        return lines, order
    if not snap["cards"]:
        return ["  这个项目还没有任务卡。"], []
    return render_card(snap, snap["cards"][state["card"]], width, color), [state["card"]]


def grouped_by_role(cards):
    """按角色分组：拍板与下派类置顶，其余按卡的 id 序。"""
    groups = {}
    for c in cards:
        groups.setdefault(c["role"], []).append(c)

    def rank(role):
        low = role.lower()
        for i, key in enumerate(CORE):
            if key in low:
                return (0, i, role)
        return (2 if role == UNKNOWN_ROLE else 1, 0, role)
    return sorted(groups.items(), key=lambda kv: rank(kv[0]))


def load_check(project):
    """把**项目自己的** scripts/check.py 载入内存当解析器用。

    不用 importlib 的 from_file_location：那会在项目里留下 __pycache__，
    把"面板只读"这条承诺当场破掉。exec + 正确的 __file__ 让 check.py 的 ROOT
    指向该项目，于是 load_cards/parse_frontmatter 与 pre-commit 判的完全同一套。
    """
    f = Path(project) / "scripts" / "check.py"
    if not f.is_file():
        raise SystemExit(f"[panel] {project} 里没有 scripts/check.py——这个目录不是 CoHarness 实例，"
                         f"或装机不完整（补救：python -m coharness.wsc init <骨架> <路径>）")
    mod = types.ModuleType("coh_panel_check")
    mod.__file__ = str(f)
    exec(compile(f.read_text(encoding="utf-8"), str(f), "exec"), mod.__dict__)
    return mod


def navigate(state, key, count):
    """导航状态机（纯函数，测试直接吃它）。"""
    s = dict(state)
    if key in ("q", "quit", "ESC"):
        s["page"], s["quit"] = s["page"], True
    elif key in ("up", "k", "UP"):
        s["cursor"] = max(0, s["cursor"] - 1)
    elif key in ("down", "j", "DOWN"):
        s["cursor"] = min(max(count - 1, 0), s["cursor"] + 1)
    elif key in ("enter", "ENT", "l", "right", "RIGHT"):
        s["page"] = {"projects": "tasks", "tasks": "card", "card": "card"}[s["page"]]
    elif key in ("back", "BS", "h", "left", "LEFT"):
        s["page"] = {"card": "tasks", "tasks": "projects", "projects": "projects"}[s["page"]]
        if s["page"] == "projects":
            s["card"] = None
    return s


def project_card_facts(project):
    """AGENTS.md 的项目卡 + 所有权表 + 角色一览，一次读全。"""
    f = Path(project) / "AGENTS.md"
    out = {"name": Path(project).name, "goal": "", "run": "", "schema": "", "owners": [],
           "roles": []}
    if not f.is_file():
        return out
    text = f.read_text(encoding="utf-8")
    head = text.splitlines()[0].strip() if text else ""
    out["name"] = unfilled(re.sub(r"^#\s*", "", head).split("—")[0]) or out["name"]
    for cells in _table_rows(text, "项目卡", 2):
        key, val = cells[0], cells[1]
        if "一句话" in key:
            out["goal"] = unfilled(val)
        elif "运行方式" in key:
            out["run"] = unfilled(val)
        elif "schema" in key.lower():
            out["schema"] = unfilled(val)
    for cells in _table_rows(text, "单写者所有权表", 2):
        out["owners"].append((cells[0].strip("`"), cells[1]))
    for cells in _table_rows(text, "角色一览", 2):
        out["roles"].append(cells[0])
    return out


def project_snapshot(project, deep=True):
    """一个项目的全量快照（纯数据，渲染与测试都吃这个）。deep=False 跳过 git 逐卡查询。

    老实例（没跑 `maintain.py migrate`）的 check.py 可能缺后来加的函数——面板按"缺什么
    就少说什么"处理，绝不因此崩：读不到的信息一律显式标 unknown，不猜。
    """
    project = Path(project).resolve()
    check = load_check(project)
    facts = project_card_facts(project)
    if hasattr(check, "load_config"):
        tasks_dir, columns = check.load_config()
    else:
        tasks_dir, columns = project / "backlog" / "tasks", ["todo", "doing", "review", "done"]
    if not hasattr(check, "load_cards"):
        raise SystemExit(f"[panel] {project} 的 scripts/check.py 太旧（没有 load_cards），"
                         f"读不了卡片：先 python {Path(__file__).parent / 'maintain.py'} migrate {project}")
    cards_raw, card_errors = check.load_cards(tasks_dir)
    if hasattr(check, "minimal_mode"):
        minimal = bool(check.minimal_mode())
    else:
        minimal = not tasks_dir.is_dir() and (project / "TODO.md").exists()
    tel_entries, tel_bad, tel_file = wsc._read_telemetry(project)
    snap = {"path": project, "name": facts["name"], "label": facts["name"] if facts["goal"]
            else str(project), "goal": facts["goal"], "run": facts["run"],
            "schema": facts["schema"], "columns": columns, "minimal": minimal,
            "tasks_dir": tasks_dir, "card_errors": list(card_errors), "cards": [],
            "telemetry": {"runs": len(tel_entries), "bad": tel_bad, "file": tel_file,
                          "last": tel_entries[-1] if tel_entries else None,
                          "harnesses": sorted({str(e.get("harness", "?")) for e in tel_entries[-40:]})},
            "owners": facts["owners"], "heads": [], "diverged": 0}
    now = time.time()
    for c in cards_raw:
        try:
            body = c["path"].read_text(encoding="utf-8").split("---", 2)[-1]
        except (OSError, UnicodeDecodeError):
            body = ""
        done, total, items = checklist(body)
        raw_role = role_of([_norm_prefix(p) for p in c["allowed"]], facts["owners"])
        role = UNKNOWN_ROLE if raw_role == UNKNOWN_ROLE else role_label(raw_role, facts["roles"])
        rel = str(c["path"].relative_to(project)).replace(os.sep, "/")
        n_commits, recent, authors = (0, [], set())
        copies = []
        if deep:
            n_commits, recent, authors = commits_touching(project, c["allowed"])
            if n_commits or total:
                copies = worktree_copies(project, rel)
        flags = []
        active = c["status"] in ("doing", "review")
        if active and total and done == 0 and n_commits:
            flags.append("提交了没勾")
        if done and not n_commits and c["status"] != "done":
            flags.append("勾了没提交")
        if c["status"] == "done" and total and done < total:
            flags.append("done 但清单未满")
        uniq = {(r["status"], r["done"]) for r in copies}
        if len(uniq) > 1:
            flags.append("跨工作树分叉")
            snap["diverged"] += 1
        updated = str(c["meta"].get("updated_date") or "")
        snap["cards"].append({
            "id": str(c["meta"].get("id") or c["name"]), "title": str(c["meta"].get("title") or ""),
            "status": c["status"], "assignees": c["assignees"], "role": role,
            "allowed": [_norm_prefix(p) for p in c["allowed"]], "rel": rel,
            "done": done, "total": total, "items": items, "commits": n_commits,
            "recent": recent, "authors": sorted(authors), "copies": copies,
            "flags": flags, "updated": updated,
            "stale": active and _hours_since(updated) > INACTIVE_HOURS})
    order = {col: i for i, col in enumerate(columns)}
    snap["cards"].sort(key=lambda k: (order.get(k["status"], 9), k["id"]))
    return snap


def render_card(snap, card, width=78, color=True):
    """第 3 页：卡详情——勾选项、git 佐证、跨工作树副本、可复制的命令。"""
    out = []
    _title(out, f"{card['id']} · {card['title']}", width)
    out.append(f"  状态 {card['status']} · 认领 {', '.join(card['assignees']) or '—'}"
               f" · 角色 {card['role']} · 更新 {card['updated'] or '—'}")
    out.append(f"  验收清单 {_bar(card['done'], card['total'], 14)}")
    for done, text in card["items"]:
        mark = MARKS["ok"] if done else MARKS["idle"]
        col = GREEN if done else DIM
        out.append((col + f"    [{mark}] {_clip(text, width - 10)}" + RESET) if color
                   else f"    [{mark}] {_clip(text, width - 10)}")
    if not card["items"]:
        out.append("    （这张卡没有验收清单节——勾选项即完成度的前提是写了清单）")
    out.append("")
    out.append(f"  边界内提交：{card['commits']} 次"
               + (f"，作者 {', '.join(card['authors'])}" if card["authors"] else ""))
    for c in card["recent"]:
        out.append(f"    {c['sha']}  {c['author']:<12} {c['ago']}")
    if card["copies"]:
        same = len({(r["status"], r["done"]) for r in card["copies"]}) == 1
        out.append(("  " if same else RED + "  ") + f"各工作树副本{'（一致）' if same else '（分叉！同一张卡状态不同）'}"
                   + (RESET if not same and color else ""))
        for r in card["copies"]:
            out.append("    " + pad(clip(Path(r["path"]).name, 18), 18)
                       + " " + pad("status=" + r["status"], 15)
                       + pad("认领=" + clip(r["assignee"], 12), 15)
                       + f"已勾 {r['done']}/{r['total']}")
    if card["flags"]:
        out.append(RED + "  ⚠ " + "、".join(card["flags"]) + RESET if color
                   else "  ! " + "、".join(card["flags"]))
    out.append("")
    out.append("  可复制的命令：")
    proj = str(snap["path"])
    lib = Path(wsc.ROOT)
    out.append(f"    python {lib / 'wsc.py'} check {proj}")
    out.append(f"    python {lib / 'wsc.py'} claim {proj} {card['id']} <你的 harness 标识>")
    out.append(f"    python {lib / 'maintain.py'} audit {proj}")
    out.append("  ←/Backspace 返回 · q 退出")
    return out


def render_projects(rows, cursor, width=78, color=True):
    """第 1 页：本机装出来的项目。"""
    out = []
    _title(out, f"CoHarness 面板 · 本机项目（{len(rows)}）", width)
    out.append("   " + pad("项目（AGENTS.md 没填名就显示路径）", 34) + pad("骨架", 26)
               + rpad("在做", 6) + rpad("待办", 6) + rpad("报警", 6))
    for i, r in enumerate(rows):
        mark = MARKS["cursor"] if i == cursor else " "
        warn = r["flags"] + r["errors"]
        out.append(mark + "  " + pad(clip(_clip_left(r["name"], 34), 34), 34)
                   + pad(clip(r["skeleton"], 26), 26)
                   + rpad(str(r["doing"]), 6) + rpad(str(r["todo"]), 6) + rpad(str(warn), 6))
    if not rows:
        out.append("  本机登记表是空的：先 `wsc init <骨架> <路径>`，或用 `panel <项目路径>` 直接打开。")
        out.append(f"  登记表位置：{wsc.registry_path()}")
    out.append("")
    out.append("  ↑↓ 选择 · Enter 进入 · q 退出")
    return out


def render_tasks(snap, cursor, width=78, color=True):
    """第 2 页：任务列表，按角色分组，核心角色置顶。"""
    out = []
    _title(out, f"{_clip_left(snap['label'], 40)} · 任务看板", width)
    line = (f"骨架 schema {snap['schema'] or '未声明'} · 目标 "
            f"{_clip(snap['goal'], 40) or '（装机时没填，AGENTS.md 里还是占位符）'}")
    out.append(DIM + "  " + line + RESET if color else "  " + line)
    t = snap["telemetry"]
    last = t["last"] or {}
    out.append(DIM + f"  最近一次 check：{last.get('ts', '从没跑过')}"
               f" 通过={last.get('rc') == 0 if t['runs'] else '-'}"
               f" · 在场 harness：{', '.join(t['harnesses']) or '—'}" + RESET if color else
               f"  最近一次 check：{last.get('ts', '从没跑过')} · 在场 harness：{', '.join(t['harnesses']) or '—'}")
    if snap["minimal"]:
        out.append(YELLOW + "  最小模式实例：没有任务卡，任务清单在 TODO.md，卡片层执法已关闭" + RESET
                   if color else "  最小模式实例：没有任务卡，任务清单在 TODO.md")
    if snap["card_errors"]:
        out.append(RED + f"  {len(snap['card_errors'])} 张卡格式不合法（check.py 拒绝解析）：" + RESET
                   if color else f"  {len(snap['card_errors'])} 张卡格式不合法：")
        for e in snap["card_errors"][:3]:
            out.append("    " + _clip(e, width - 4))
    index_of = {id(c): i for i, c in enumerate(snap["cards"])}
    order, pos = [], 0
    for role, cards in grouped_by_role(snap["cards"]):
        core = any(k in role.lower() for k in CORE)
        head = f"{role}  ·  {len(cards)} 张"
        out.append("")
        out.append((BOLD + CYAN if core and color else "") + _clip(head, width)
                   + (RESET if core and color else ""))
        for c in cards:
            mark = MARKS["cursor"] if pos == cursor else " "
            pos += 1
            order.append(index_of[id(c)])
            who = ",".join(c["assignees"]) or "—"
            badge = " ".join("!" + f for f in c["flags"]) or "  "
            stale = " ~stale" if c["stale"] else ""
            row = (mark + "  " + pad(clip(c["id"], 8), 8) + pad(clip(c["status"], 7), 7)
                   + pad(clip(who, 12), 12) + pad(_bar(c["done"], c["total"], 6), 13)
                   + pad(clip(c["title"], 26), 26) + badge + stale)
            col = RED if c["flags"] else (YELLOW if c["stale"] else "")
            out.append((col + row + RESET) if (col and color) else row)
    out.append("")
    out.append(f"  共 {len(snap['cards'])} 张 · 完成度 "
               f"{sum(c['done'] for c in snap['cards'])}/{sum(c['total'] for c in snap['cards'])}"
               " 验收项已勾")
    out.append("  ↑↓ 选择 · Enter 看卡 · Backspace 返回 · r 立即刷新 · q 退出")
    return out, order


def _prefix_variants(p):
    """骨架的所有权表是模板，写的是 `code/<组件>/` 这种带通配的行——实例化后没人会去替换它
    （组件名在各项目里长出来），所以按通配之前的那段匹配，角色标签仍取那一格的写者。"""
    for token in ("<", "*", "…"):
        if token in p:
            head = p.split(token)[0].rstrip("/")
            return [head] if head else []
    return [p]


def role_label(writer_cell, known_roles):
    """所有权表那一格常是一句话（"各 harness 改自己的卡，总裁决归 integrator"）。
    从角色一览里挑出**文本中最后出现**的那个角色名当标签——一句话里提到多个角色时，
    后提到的通常是写者本人。一个都对不上就照原文显示，不编。"""
    text = str(writer_cell)
    low = text.lower()
    names = [r.strip("`").split("<")[0].strip("-").strip() for r in known_roles]
    names = [n for n in dict.fromkeys(names + list(ROLE_STEMS)) if n and n.lower() in low]
    if not names:
        return text
    return max(names, key=lambda n: low.find(n.lower()))


def role_of(allowed, owners):
    """卡的前缀 → 所有权表里最长匹配那一行的"唯一写者"。匹配不上就说匹配不上，不猜。"""
    best, best_len = None, -1
    for prefix, writer in owners:
        for v in _prefix_variants(_norm_prefix(prefix)):
            if not v or v == "*":
                continue
            for path in allowed:
                a = _norm_prefix(path)
                if a and (a == v or a.startswith(v + "/") or v.startswith(a + "/")):
                    if len(v) > best_len:
                        best, best_len = writer, len(v)
    return best or UNKNOWN_ROLE


def term_width(default=78):
    try:
        return max(60, os.get_terminal_size().columns - 1)
    except (OSError, ValueError):
        return default


def unfilled(value):
    """装机没替换的 {{占位符}} 不是事实，别拿它当项目名/目标显示。"""
    v = str(value or "").strip()
    return "" if "{{" in v or "}}" in v else v


def worktree_copies(project, rel_card):
    """同一张卡在各工作树的副本状态——I-007 点名的分叉症状在这里变成可见。"""
    ok, out = _git(project, ["worktree", "list", "--porcelain"])
    if not ok:
        return []
    rows = []
    for line in out.splitlines():
        if line.startswith("worktree "):
            wt = Path(line.split(" ", 1)[1])
            f = wt / rel_card
            if not f.is_file():
                continue
            try:
                text = f.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            status, who = wsc._card_fields(text)
            body = text.split("---", 2)[-1] if text.startswith("---") else text
            done, total, _ = checklist(body)
            rows.append({"path": str(wt), "status": status or "?",
                         "assignee": ",".join(who) or "-", "done": done, "total": total})
    return rows

