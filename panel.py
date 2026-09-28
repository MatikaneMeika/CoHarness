"""CoHarness 展示面入口：只读看板面板的终端循环。

数据装配与渲染在 board.py（那边全是纯函数、可单测）；本文件只管按键、清屏、刷新节奏，
以及 --plain 逃生门。**只读**：不写文件、不认领、不改卡、不出网。
"""
import argparse
import os
import sys
import time
from pathlib import Path

try:
    from . import wsc
    from .board import WATCH_SECONDS
    from .board import (
        _bar,
        _clip,
        _git,
        _hours_since,
        _norm_prefix,
        _table_rows,
        _title,
        checklist,
        collect_projects,
        commits_touching,
        current_page_lines,
        grouped_by_role,
        load_check,
        navigate,
        project_card_facts,
        project_snapshot,
        render_card,
        render_projects,
        render_tasks,
        role_label,
        role_of,
        term_width,
        unfilled,
        worktree_copies)
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import wsc
    from board import WATCH_SECONDS
    from board import (
        _bar,
        _clip,
        _git,
        _hours_since,
        _norm_prefix,
        _table_rows,
        _title,
        checklist,
        collect_projects,
        commits_touching,
        current_page_lines,
        grouped_by_role,
        load_check,
        navigate,
        project_card_facts,
        project_snapshot,
        render_card,
        render_projects,
        render_tasks,
        role_label,
        role_of,
        term_width,
        unfilled,
        worktree_copies)


def _utf8_streams():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def read_key(timeout):
    """读一个键；非 TTY（管道/CI）直接返回 None，让调用方回落 --plain。"""
    try:
        import msvcrt                                  # Windows
        msvcrt.flush()
        start = time.time()
        while time.time() - start < timeout:
            if msvcrt.kbhit():
                ch = msvcrt.getwch()
                if ch in ("\x00", "\xe0"):
                    ch2 = msvcrt.getwch()
                    return {"H": "left", "P": "up", "K": "up", "M": "right",
                            "N": "down", "J": "down", "Q": "ENT", "S": "BS"}.get(ch2, ch)
                return {"\r": "ENT", "\n": "ENT", "\x1b": "ESC", "\x08": "BS",
                        "\x7f": "BS"}.get(ch, ch)
            time.sleep(0.05)
        return "tick"
    except ImportError:
        pass
    import termios
    import tty
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        import select
        r, _, _ = select.select([sys.stdin], [], [], timeout)
        if not r:
            return "tick"
        ch = sys.stdin.read(1)
        if ch == "\x1b":
            ch2 = sys.stdin.read(2)
            return {"[A": "up", "[B": "down", "[C": "right", "[D": "left"}.get(ch2, "ESC")
        return {"\r": "ENT", "\n": "ENT", "\x7f": "BS", "\x08": "BS"}.get(ch, ch)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


KEYMAP = {"UP": "up", "DOWN": "down", "ENT": "enter", "BS": "back", "ESC": "back"}


def main(argv=None):
    ap = argparse.ArgumentParser(prog="coharness-panel",
                                 description="CoHarness 只读看板面板（展示面）")
    ap.add_argument("projects", nargs="*", help="项目路径；不给就用本机登记表")
    ap.add_argument("--plain", action="store_true",
                    help="一次性纯文本输出，不进全屏（conhost 花屏时的逃生门，也适合贴给人看）")
    ap.add_argument("--width", type=int, default=0, help="渲染宽度，默认按终端")
    ap.add_argument("--watch", type=float, default=WATCH_SECONDS, help="自动刷新秒数，0 表示不刷")
    ap.add_argument("--project", default="", help="直接打开某个项目，跳过顶层列表")
    args = ap.parse_args(argv)
    _utf8_streams()

    paths = collect_projects(args)
    if args.project:
        p = Path(args.project).resolve()
        paths = [p] + [x for x in paths if x != p]
    if not paths:
        print("没有可显示的项目：登记表里那些路径已经不在了（`wsc init` 会重新登记）。")
        return 1

    state = {"page": "projects", "sel": 0, "cursor": 0, "card": None, "quit": False}
    if args.project and paths and (paths[0] / "scripts" / "check.py").is_file():
        state["page"] = "tasks"
    width = args.width or term_width()
    color = not args.plain and sys.stdout.isatty()

    def build(deep):
        snaps = []
        for path in paths:
            try:
                s = project_snapshot(path, deep=deep)
            except SystemExit as e:
                print(str(e), file=sys.stderr)
                continue
            entry = next((e for e in wsc.read_registry()
                          if Path(str(e.get("path", ""))).resolve() == path), {})
            s["skeleton"] = str(entry.get("skeleton", ""))
            snaps.append(s)
        return snaps

    if args.plain or not sys.stdin.isatty():
        # 非 TTY（管道、CI、conhost 花屏）就走逃生门：一次性纯文本，不发任何转义序列。
        snaps = build(deep=True)
        if not snaps:
            return 1
        if state["page"] != "tasks":
            state["page"], state["sel"], state["cursor"] = "projects", 0, 0
        lines, _ = current_page_lines(snaps, state, width, color)
        print("\n".join(lines))
        return 0

    DEPTH = {"projects": 0, "tasks": 1, "card": 2}
    FIELD = {"tasks": "sel", "card": "card"}
    snaps = build(deep=False)
    while True:
        lines, ids = current_page_lines(snaps, state, width, color)
        sys.stdout.write("\033[2J\033[H\033[?25l")
        sys.stdout.write("\n".join(l[:width] for l in lines) + "\n")
        sys.stdout.flush()
        key = read_key(args.watch or 60)
        if key == "tick":
            if args.watch:
                snaps = build(deep=state["page"] != "projects")
            continue
        if key == "r":
            snaps = build(deep=state["page"] != "projects")
            continue
        if key == "ESC":
            key = "back" if state["page"] != "projects" else "q"
        prev_page, prev_cursor, ids_before = state["page"], state["cursor"], ids
        state = navigate(state, KEYMAP.get(key, key), max(len(ids), 1))
        if state.get("quit"):
            break
        if DEPTH[state["page"]] > DEPTH[prev_page]:
            # 下钻：光标所在位置就是被选中的对象，ids 是这一页的真实下标顺序
            state[FIELD[state["page"]]] = ids_before[min(prev_cursor, len(ids_before) - 1)] \
                if ids_before else 0
            state["cursor"] = 0
            snaps = build(deep=True)
        elif DEPTH[state["page"]] < DEPTH[prev_page] and state["page"] == "projects":
            state["cursor"] = min(state["sel"], max(len(snaps) - 1, 0))
            snaps = build(deep=False)
    sys.stdout.write("\033[?25h\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
