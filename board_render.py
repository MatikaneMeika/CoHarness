"""CoHarness 展示面的渲染层：把快照拼成字符串行（终端 IO 仍在 panel.py）。

2026-09-30 从 board.py 按面拆出来：装配（读盘、git、缓存、快照）与渲染（行文本、列宽）
本来就是两件事——拆开后装配那侧不必为行数上限牺牲可读性，渲染这侧也不必知道 git 怎么读。
这里的函数全是纯函数：只吃数据、只吐行列表，unittest 直接可断言。名字照旧挂在 board 上
（board.py 再导出），panel 与测试的取名字面不变。
"""

import sys
import unicodedata
from pathlib import Path


try:                                   # 装成包时按包内模块导入
    from . import wsc
except ImportError:                    # curl/源码树直跑
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import wsc

CORE = ("integrator", "pm", "architect", "reviewer", "tester", "doc-writer")
UNKNOWN_ROLE = "边界没落进所有权表"

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


def _title(lines, text, width):
    lines.append(MARKS["bar"] * 3 + " " + text + " " + MARKS["bar"] * max(0, width - len(text) - 5))
    return lines


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
    reviews = card.get("reviews") or []
    if reviews:
        out.append(f"  审阅意见 {sum(1 for r in reviews if not r['unread'])}/{len(reviews)} 已传达")
        for r in reviews:
            head = f"    [{'未读' if r['unread'] else '已传达'}] {r['file']}" \
                   + (f":{r['lines']}" if r["lines"] and r["lines"] != "all" else "")
            out.append((RED + head + RESET) if (r["unread"] and color) else head)
            if r["comment"]:
                col = "" if r["unread"] else DIM
                out.append((col + f"      {_clip(r['comment'], width - 8)}" + RESET)
                           if col and color else f"      {_clip(r['comment'], width - 8)}")
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
    """第 1 页：本机装出来的项目。返回 (行列表, 光标行号)。"""
    out = []
    cursor_row = 2                                    # 标题 + 表头之后就是第一行数据
    _title(out, f"CoHarness 面板 · 本机项目（{len(rows)}）", width)
    out.append("   " + pad("项目（AGENTS.md 没填名就显示路径）", 34) + pad("骨架", 26)
               + rpad("在做", 6) + rpad("待办", 6) + rpad("报警", 6))
    for i, r in enumerate(rows):
        if i == cursor:
            cursor_row = len(out)
        mark = MARKS["cursor"] if i == cursor else " "
        warn = "-" if r["flags"] is None else r["flags"] + r["errors"]
        out.append(mark + "  " + pad(clip(_clip_left(r["name"], 34), 34), 34)
                   + pad(clip(r["skeleton"], 26), 26)
                   + rpad(str(r["doing"]), 6) + rpad(str(r["todo"]), 6) + rpad(str(warn), 6))
    if not rows:
        out.append("  本机登记表是空的：先 `wsc init <骨架> <路径>`，或用 `panel <项目路径>` 直接打开。")
        out.append(f"  登记表位置：{wsc.registry_path()}")
    out.append("")
    out.append("  ↑↓ 选择 · Enter 进入 · q 退出")
    return out, cursor_row


def render_tasks(snap, cursor, width=78, color=True):
    """第 2 页：任务列表，按角色分组，核心角色置顶。返回 (行列表, 下标序, 光标行号)。"""
    out = []
    cursor_row = 0
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
            if pos == cursor:
                cursor_row = len(out)
            mark = MARKS["cursor"] if pos == cursor else " "
            pos += 1
            order.append(index_of[id(c)])
            who = ",".join(c["assignees"]) or "—"
            badge = " ".join("!" + f for f in c["flags"]) or "  "
            unread = c.get("reviews_unread") or 0
            if unread:
                badge += f" !{unread}条未读"
            stale = " ~stale" if c["stale"] else ""
            row = (mark + "  " + pad(clip(c["id"], 8), 8) + pad(clip(c["status"], 7), 7)
                   + pad(clip(who, 12), 12) + pad(_bar(c["done"], c["total"], 6), 13)
                   + pad(clip(c["title"], 26), 26) + badge + stale)
            col = RED if c["flags"] else (YELLOW if c["stale"] else "")
            out.append((col + row + RESET) if (col and color) else row)
    out.append("")
    flt = snap.get("filter", "all")
    n_shown = (f"{len(snap['cards'])}/{snap['total_cards']}" if flt != "all"
               else str(len(snap["cards"])))
    tail = f" · 筛选 {flt}（按 s 换）" if flt != "all" else ""
    out.append(f"  共 {n_shown} 张{tail} · 完成度 "
               f"{sum(c['done'] for c in snap['cards'])}/{sum(c['total'] for c in snap['cards'])}"
               " 验收项已勾")
    out.append("  ↑↓ 选择 · Enter 看卡 · Backspace 返回 · s 筛选 · PgUp/PgDn 翻页 · r 刷新 · q 退出")
    return out, order, cursor_row
