"""CoHarness 展示面入口：只读看板面板的终端循环。

数据装配与渲染在 board.py（那边全是纯函数、可单测）；本文件只管按键、清屏、刷新节奏，
以及 --plain 逃生门。**只读**：不写文件、不认领、不改卡、不出网。
"""
import argparse
import os
import sys
import time
from pathlib import Path

try:                                   # 装成包时按包内模块导入
    from . import wsc
    from . import board
except ImportError:                    # curl/源码树直跑
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import wsc
    import board

# 名字表只写一份：两个分支导入的是同一个 board，重复两遍迟早漂（而且白占四十行）。
# 逐个绑成模块全局而不是就地 import，是为了 `panel_mod.project_snapshot` 这类测试注入点照旧可用。
for _name in ("_bar", "_clip", "_git", "_hours_since", "_norm_prefix", "_table_rows", "_title",
              "WATCH_SECONDS", "board_fingerprint", "checklist", "clip", "collect_projects",
              "commits_touching", "current_page_lines", "grouped_by_role", "load_check",
              "navigate", "project_card_facts", "project_snapshot", "render_card",
              "render_projects", "render_tasks", "role_label", "role_of", "term_width",
              "unfilled", "viewport", "worktree_copies"):
    globals()[_name] = getattr(board, _name)
del _name


def _utf8_streams():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


# Windows 增强键的第二字符码是 VK 码低字节（H=↑ P=↓ K=← M=→ G=Home O=End
# I=PgUp Q=PgDn S=Del），2026-09-29 前的表把方向键相互配错，全屏模式里
# 按方向键走错方向。POSIX 的 CSI 序列补长键：旧实现固定读 2 字符，Home/End/PgUp/PgDn 全失灵。
MSVCRT_PFX = {"H": "up", "P": "down", "K": "left", "M": "right",
              "G": "home", "O": "end", "I": "pgup", "Q": "pgdn", "S": "BS"}
MSVCRT_KEYS = {"\r": "ENT", "\n": "ENT", "\x1b": "ESC", "\x08": "BS", "\x7f": "BS"}
POSIX_KEYS = {"\r": "ENT", "\n": "ENT", "\x7f": "BS", "\x08": "BS"}
POSIX_SEQ = {"[A": "up", "[B": "down", "[C": "right", "[D": "left",
             "[H": "home", "[F": "end", "[1~": "home", "[4~": "end",
             "[5~": "pgup", "[6~": "pgdn", "[7~": "home", "[8~": "end"}


def decode_msvcrt(ch, ch2=""):
    """Windows 读键的解码（纯函数，可测；IO 留在 read_key 里）。"""
    if ch in ("\x00", "\xe0"):
        return MSVCRT_PFX.get(ch2, "")
    return MSVCRT_KEYS.get(ch, ch)


def decode_posix(ch, rest=""):
    if ch == "\x1b":
        return POSIX_SEQ.get(rest, "ESC")
    return POSIX_KEYS.get(ch, ch)


def read_escape_sequence(readch, has_more, maxlen=6):
    """把 ESC 后面的转义序列读满（纯函数：读字符与"还有没有"都由调用方注入）。

    读到字母或 '~'（CSI 序列的收尾）就停，不许把跟在后面的普通字符吞掉；
    流中断就到哪算哪——decode 层认不出的形状兜底成 ESC。
    """
    out = []
    while len(out) < maxlen and has_more():
        out.append(readch())
        if out[-1].isalpha() or out[-1] == "~":
            break
    return "".join(out)


def read_key(timeout):
    """读一个键；非 TTY 的跑法由 main() 挡在 --plain，不会走到这里。"""
    try:
        import msvcrt                                  # Windows
        start = time.time()
        while time.time() - start < timeout:
            if msvcrt.kbhit():
                ch = msvcrt.getwch()
                if ch in ("\x00", "\xe0"):
                    return decode_msvcrt(ch, msvcrt.getwch())
                return decode_msvcrt(ch)
            time.sleep(0.05)
        return "tick"
    except ImportError:
        pass
    import select
    import termios
    import tty
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        r, _, _ = select.select([sys.stdin], [], [], timeout)
        if not r:
            return "tick"
        ch = sys.stdin.read(1)
        if ch == "\x1b":
            if not select.select([sys.stdin], [], [], 0.05)[0]:
                return decode_posix(ch)                # 单独的 ESC：不再拖住等下一击键
            rest = read_escape_sequence(
                lambda: sys.stdin.read(1),
                lambda: bool(select.select([sys.stdin], [], [], 0.02)[0]))
            return decode_posix(ch, rest)
        return decode_posix(ch)
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

    state = {"page": "projects", "sel": 0, "cursor": 0, "card": None, "quit": False,
             "filter": "all", "top": 0}
    if args.project and paths and (paths[0] / "scripts" / "check.py").is_file():
        state["page"] = "tasks"
    width = args.width or term_width()
    color = not args.plain and sys.stdout.isatty()
    snap_cache = {}

    def build(deep):
        """逐项目出快照；deep 时按 (HEAD, 卡片 mtime) 增量复用——项目一多，没变化
        的项目就不必每轮从头重算（报警/分叉这些 git 查询是大头）。"""
        snaps = []
        for path in paths:
            fp = (str(path), board_fingerprint(path))
            hit = snap_cache.get(fp) if deep else None
            if hit is not None:
                snaps.append(hit)
                continue
            try:
                s = project_snapshot(path, deep=deep)
            except SystemExit as e:
                print(str(e), file=sys.stderr)
                continue
            entry = next((e for e in wsc.read_registry()
                          if Path(str(e.get("path", ""))).resolve() == path), {})
            s["skeleton"] = str(entry.get("skeleton", ""))
            if deep:
                snap_cache[fp] = s
            snaps.append(s)
        return snaps

    if args.plain or not sys.stdin.isatty():
        # 非 TTY（管道、CI、conhost 花屏）就走逃生门：一次性纯文本，不发任何转义序列。
        snaps = build(deep=True)
        if not snaps:
            return 1
        if state["page"] != "tasks":
            state["page"], state["sel"], state["cursor"] = "projects", 0, 0
        lines, _, _ = current_page_lines(snaps, state, width, color)
        print("\n".join(lines))
        return 0

    DEPTH = {"projects": 0, "tasks": 1, "card": 2}
    FIELD = {"tasks": "sel", "card": "card"}
    FILTER_CYCLE = ["all", "doing", "todo", "done"]
    # 顶层也吃 deep：浅快照算不出报警，画 0 等于把"没查"报成"没有报警"（实测卡上挂着
    # "跨工作树分叉"时顶层仍是 0）。代价由 board 的 HEAD 缓存与上面的指纹缓存兜住。
    snaps = build(deep=True)
    try:
        while True:
            lines, ids, cursor_row = current_page_lines(snaps, state, width, color)
            try:
                height = max(5, os.get_terminal_size().lines - 2)
            except (OSError, ValueError):
                height = 20
            state["top"] = viewport(len(lines), cursor_row, state.get("top", 0), height)
            shown = lines[state["top"]:state["top"] + height]
            overflow = f"  -*- {len(lines)} 行，PgUp/PgDn 翻页 · s 筛选" if len(lines) > height else ""
            sys.stdout.write("\033[2J\033[H\033[?25l")
            sys.stdout.write("\n".join(clip(l, width) for l in shown)
                             + ("\n" + overflow if overflow else "") + "\n")
            sys.stdout.flush()
            key = read_key(args.watch or 60)
            if key == "tick":
                if args.watch:
                    snaps = build(deep=True)
                continue
            if key == "r":
                snaps = build(deep=True)
                continue
            if key == "s" and state["page"] == "tasks":
                cyc = FILTER_CYCLE.index(state.get("filter", "all"))
                state["filter"] = FILTER_CYCLE[(cyc + 1) % len(FILTER_CYCLE)]
                state["cursor"], state["top"] = 0, 0
                continue
            if key == "ESC":
                key = "back" if state["page"] != "projects" else "q"
            prev_page, prev_cursor, ids_before = state["page"], state["cursor"], ids
            state = navigate(state, KEYMAP.get(key, key), max(len(ids), 1))
            if state.get("quit"):
                break
            if DEPTH[state["page"]] != DEPTH[prev_page]:
                state["top"] = 0                  # 换页：视口回到页顶
            if DEPTH[state["page"]] > DEPTH[prev_page]:
                # 下钻：光标所在位置就是被选中的对象，ids 是这一页的真实下标顺序
                state[FIELD[state["page"]]] = ids_before[min(prev_cursor, len(ids_before) - 1)] \
                    if ids_before else 0
                state["cursor"] = 0
                snaps = build(deep=True)
            elif DEPTH[state["page"]] < DEPTH[prev_page] and state["page"] == "projects":
                state["cursor"] = min(state["sel"], max(len(snaps) - 1, 0))
    except KeyboardInterrupt:
        pass                                      # Ctrl+C 也算退出方式，不该甩一屏栈
    finally:
        # 光标是全屏绘制时藏掉的：q、Ctrl+C、哪条路径退出都得还回去，否则终端留个隐形光标
        sys.stdout.write("\033[?25h\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
