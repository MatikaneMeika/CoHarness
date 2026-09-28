#!/usr/bin/env python3
"""CoHarness 工具链：骨架实例化 + 合作区日常操作。

用法:
    python wsc.py list                     # 列出可用骨架
    python wsc.py init <骨架名> <目标路径>   # 实例化骨架（占位符清单 + pre-commit 安装）
    python wsc.py sync [项目路径]           # 开工协议：pull + 看板摘要 + stale 报告
    python wsc.py check [项目路径]          # 跑项目 scripts/check.py 全部检查
    python wsc.py doctor                   # 依赖自检（node/backlog/uv/specify/worktrunk）

骨架名支持全名/编号/前缀，如 solo / 03 / doc-production。
所有 subprocess 调用均为同一安全形状：argv 全字面量、shell=False、用户路径只作 cwd、
输出显式按 utf-8 解码（见 _run）。
"""
import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PLACEHOLDER_RE = re.compile(r"\{\{([A-Z][A-Z0-9_]*)\}\}")


def _utf8_streams():
    """中文提示在 cp936/gbk 控制台下要先保证自己可读：stdout 与 stderr 一起管。"""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def _run(argv, cwd, timeout=60):
    """统一的子进程调用形状：argv 全字面量、shell=False、输出显式按 utf-8 解码。

    不写 encoding 时子进程输出按 locale 首选编码解码（简体中文 Windows 是 cp936），
    被调脚本输出的 utf-8 中文会让读取线程直接抛 UnicodeDecodeError。
    """
    return subprocess.run([str(a) for a in argv], cwd=str(cwd), capture_output=True,
                          text=True, encoding="utf-8", errors="replace",
                          timeout=timeout, shell=False)

NEXT_STEPS = {
    "03-multi-harness-project": [
        "npm i -g backlog.md && backlog init --task-prefix T",
        "  然后把 backlog/ 或 backlog.config.yml 里看板列改为: todo, doing, review, done",
        "uv tool install specify-cli，再对每个在场工具各跑一次:",
        "  specify init --integration zcode   # codex / qodercli / generic（Antigravity）同理",
        "winget install max-sixty.worktrunk   # Windows 下命令为 git-wt",
    ],
    "02-study-office": [
        "可选（仅交付型多任务/多人分工时）：npm i -g backlog.md && backlog init",
        "  然后把看板列改为: todo, doing, review, done",
    ],
}

# 非 AGENTS.md 标准的工具适配指针：内容一律一行，指向 AGENTS.md（不构成第二权威）
ADAPTERS = {
    "claude": ["CLAUDE.md"],
    "gemini": ["GEMINI.md"],
    "cursor": [".cursorrules"],
    "copilot": [".github/copilot-instructions.md"],
    "windsurf": [".windsurfrules"],
    "zcode": [],   # 原生读 AGENTS.md，无需适配
    "codex": [],   # 原生
    "qoder": [],   # 原生读 AGENTS.md（可在项目 Rules 再加一行指向）
}
POINTER_TEXT = (
    "读 AGENTS.md，以其为准。（CoHarness 适配指针；协作规则唯一权威是 AGENTS.md 与 .agent/）\n"
)


def discover_skeletons():
    return sorted(
        p for p in ROOT.iterdir()
        if p.is_dir() and re.match(r"^\d{2}-", p.name)
    )


def resolve_skeleton(name: str) -> Path:
    """支持全名、编号或任意段前缀匹配，如 solo / 03 / study / office。"""
    skeletons = discover_skeletons()
    for s in skeletons:
        if s.name == name:
            return s
    matches = [
        s for s in skeletons
        if any(seg.startswith(name) for seg in s.name.split("-"))
    ]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        sys.exit(f"骨架名 '{name}' 有歧义: {[m.name for m in matches]}")
    sys.exit(
        f"未找到骨架 '{name}'。可用骨架: {[s.name for s in skeletons]}"
    )


def instantiate(src: Path, dst: Path):
    copied, skipped = [], []
    for p in sorted(src.rglob("*")):
        if not p.is_file():
            continue
        if "__pycache__" in p.parts or p.suffix == ".pyc":
            continue  # 运行残留不进骨架
        rel = p.relative_to(src)
        target = dst / rel
        if target.exists():
            skipped.append(rel)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, target)
        copied.append(rel)
    return copied, skipped


def collect_placeholders(dst: Path, copied):
    found = {}  # name -> [files]
    for rel in copied:
        try:
            text = (dst / rel).read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for m in PLACEHOLDER_RE.findall(text):
            found.setdefault(m, []).append(str(rel))
    return found


def _git_field(argv, cwd, timeout=30):
    """跑一条只读 git 命令，返回 (状态, 首行输出)：ok / not-repo / no-git。"""
    try:
        r = _run(argv, cwd, timeout=timeout)
    except OSError:
        return "no-git", ""
    lines = (r.stdout or "").strip().splitlines()
    return ("ok", lines[0]) if r.returncode == 0 and lines else ("not-repo", "")


def _hooks_target(project: Path):
    """解析 pre-commit 该落在哪：普通仓库 / linked worktree（公共 .git）/ 非仓库 / 外层仓库。

    只用只读命令，不代跑 `git init`——"init 只向目标目录写文件"是 SECURITY.md 的承诺。
    """
    st, top = _git_field(["git", "rev-parse", "--show-toplevel"], project)
    if st == "no-git":
        return None, "git-missing", ""
    if st != "ok":
        return None, "not-a-repo", ""
    if Path(top).resolve() != project.resolve():
        return None, "outer-repo", top          # 不许把项目钩子装进别人的仓库
    st, hooks = _git_field(
        ["git", "rev-parse", "--path-format=absolute", "--git-path", "hooks"], project)
    if st != "ok":  # git < 2.43 不认 --path-format，退回 --git-dir 自己拼（含 commondir）
        st, gd = _git_field(["git", "rev-parse", "--git-dir"], project)
        if st != "ok":
            return None, "not-a-repo", top
        gd = Path(gd)
        if not gd.is_absolute():
            gd = project / gd
        common = gd / "commondir"
        if common.exists():
            gd = (gd / common.read_text(encoding="utf-8").strip()).resolve()
        hooks = str(gd / "hooks")
    p = Path(hooks)
    return (p if p.is_absolute() else project / p), "ok", top


def install_pre_commit(dst: Path):
    """把骨架钩子复制进 git 认定的 hooks 目录，返回 (状态, 说明)。

    状态：installed / exists / not-a-repo / outer-repo / git-missing / no-hook-file。
    """
    src = dst / "scripts" / "hooks" / "pre-commit"
    if not src.exists():
        return "no-hook-file", ""
    hooks, status, note = _hooks_target(dst)
    if status != "ok":
        return status, note
    target = hooks / "pre-commit"
    if target.exists():
        return "exists", str(hooks)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, target)
    try:
        target.chmod(0o755)
    except OSError:
        pass
    return "installed", str(hooks)


def write_adapters(dst: Path, spec: str):
    """按 --adapter 生成一行式指针文件。已存在的不覆盖。"""
    spec = spec.strip().lower()
    names = list(ADAPTERS) if spec == "all" else [s.strip() for s in spec.split(",") if s.strip()]
    made = []
    for name in names:
        if name not in ADAPTERS:
            print(f"  [跳过] 未知 adapter: {name}（可选: {', '.join(ADAPTERS)} 或 all）")
            continue
        for rel in ADAPTERS[name]:
            p = dst / rel
            if p.exists():
                print(f"  [跳过] {rel} 已存在")
                continue
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(POINTER_TEXT, encoding="utf-8")
            made.append(rel)
    return made


def cmd_list(_args):
    print("可用骨架:")
    for s in discover_skeletons():
        desc = ""
        readme = s / "AGENTS.md"
        if readme.exists():
            for line in readme.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    desc = line.lstrip("# ").strip()
                    break
        print(f"  {s.name:<28} {desc}")


def cmd_init(args):
    src = resolve_skeleton(args.skeleton)
    dst = Path(args.target).resolve()
    if dst.exists() and any(p.name != ".git" for p in dst.iterdir()):
        sys.exit(f"目标目录非空: {dst}\n（骨架只能复制到空目录或新目录，避免覆盖现有规则；仅含 .git 的目录允许）")
    dst.mkdir(parents=True, exist_ok=True)

    copied, skipped = instantiate(src, dst)
    print(f"已实例化骨架 [{src.name}] -> {dst}")
    print(f"  复制 {len(copied)} 个文件" + (f"，跳过已存在 {len(skipped)} 个" if skipped else ""))

    status, note = install_pre_commit(dst)
    if status == "installed":
        print(f"  pre-commit 钩子已装进 {note}（所有 harness 的提交都过 check.py）")
    elif status == "exists":
        print(f"  {note}\\pre-commit 已存在，未覆盖")
    elif status == "not-a-repo":
        print("  [未装钩子] 目标目录还不是 git 仓库，check.py 不会被自动触发：")
        print("            先 `git init` 再重跑 wsc init，或手动 "
              "cp scripts/hooks/pre-commit .git/hooks/pre-commit")
    elif status == "outer-repo":
        print(f"  [未装钩子] 目标不是仓库根（外层仓库 {note}），钩子只装进项目自己的仓库：")
        print("            把这个项目单独 git init，或手动 cp scripts/hooks/pre-commit .git/hooks/")
    elif status == "git-missing":
        print("  [未装钩子] 找不到 git 命令：装好 git 后重跑 wsc init")

    if args.adapter:
        made = write_adapters(dst, args.adapter)
        if made:
            print("  适配指针（均一行指向 AGENTS.md）:")
            for rel in made:
                print(f"    + {rel}")

    placeholders = collect_placeholders(dst, copied)
    if placeholders:
        print("\n待填占位符（填完后即可开工）:")
        for name, files in sorted(placeholders.items()):
            print(f"  {{{{{name}}}}}  出现于 {len(files)} 个文件，如 {files[0]}")
    else:
        print("无待填占位符。")

    steps = NEXT_STEPS.get(src.name)
    if steps:
        print(f"\n依赖安装（自检: python {ROOT / 'wsc.py'} doctor）:")
        for line in steps:
            print(f"  {line}")


def cmd_sync(args):
    project = Path(args.project).resolve() if args.project else Path.cwd()
    if not project.exists():
        sys.exit(f"项目路径不存在: {project}")
    print(f"== sync {project} ==")

    try:
        r = _run(["git", "pull", "--ff-only"], project)
        out = (r.stdout or r.stderr).strip() or "完成"
    except (OSError, subprocess.TimeoutExpired) as e:
        out = f"（执行失败: {e}）"
    print(f"[pull] {out}")

    if shutil.which("backlog"):
        try:
            r = _run(["backlog", "task", "list"], project)
            out = (r.stdout or r.stderr).strip()
        except (OSError, subprocess.TimeoutExpired) as e:
            out = f"（执行失败: {e}）"
        print(f"[看板] backlog task list:\n{_indent(out)}")
    else:
        print("[看板] 未安装 backlog CLI，回落读文件（npm i -g backlog.md 后更完整）:")
        for p in sorted((project / "backlog" / "tasks").glob("*.md")):
            line = _card_summary(p)
            if line:
                print(f"  {line}")

    if (project / "scripts" / "check.py").exists():
        try:
            r = _run([sys.executable, "scripts/check.py", "--stale"], project)
            out = (r.stdout or r.stderr).strip()
        except (OSError, subprocess.TimeoutExpired) as e:
            out = f"（执行失败: {e}）"
        print(f"[stale] {_indent(out)}")


def _card_summary(p: Path):
    """无 backlog CLI 时的极简卡摘要：id / status / assignee。"""
    try:
        text = p.read_text(encoding="utf-8")
    except OSError:
        return None
    if not text.startswith("---"):
        return None
    fields = {}
    for line in text.splitlines()[1:]:
        if line.strip() == "---":
            break
        m = re.match(r"^(id|status|assignee):\s*(.*)$", line)
        if m:
            fields[m.group(1)] = m.group(2).strip().strip("[]\"'")
    if "id" not in fields:
        return None
    return f"{fields.get('id', '?'):<8} {fields.get('status', '?'):<8} {fields.get('assignee', '')}"


def _indent(text: str):
    return "\n".join(f"  {line}" for line in (text or "（无输出）").splitlines())


def cmd_check(args):
    project = Path(args.project).resolve() if args.project else Path.cwd()
    if not (project / "scripts" / "check.py").exists():
        sys.exit(f"未找到 {project / 'scripts' / 'check.py'}（该骨架不带执法脚本）")
    try:
        r = _run([sys.executable, "scripts/check.py"], project, timeout=300)
        sys.stdout.write(r.stdout or "")
        sys.stderr.write(r.stderr or "")
        sys.exit(r.returncode)
    except (OSError, subprocess.TimeoutExpired) as e:
        sys.exit(f"（执行失败: {e}）")


LEDGER_STATUSES = ("登记", "试点中", "待审", "已晋升", "已驳回")
UNFINISHED = LEDGER_STATUSES[:3]


def cmd_improve(args):
    """列出项目改进登记表中的非终态条目（登记/试点中/待审）。纯读文件，不改任何东西。"""
    project = Path(args.project).resolve() if args.project else Path.cwd()
    f = project / ".agent" / "improvements.md"
    if not f.exists():
        sys.exit(f"未找到 {f}（该骨架不含改进登记表，或项目未实例化）")
    pending, warnings = [], []
    for lineno, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
        s = line.strip()
        if not (s.startswith("|") and s.endswith("|")):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if len(cells) < 8:
            continue
        head = cells[0]
        if head in ("编号", "") or set(head) <= set("-: "):
            continue  # 表头与分隔行
        if not re.match(r"^I-\d+$", head):
            warnings.append(f"  [编号不合约定] 第 {lineno} 行 '{head}'："
                            f"登记条目要写成 I-xxx（自 I-001 递增）")
            continue
        if cells[7] not in LEDGER_STATUSES:
            warnings.append(f"  [状态存疑] {head}：'{cells[7]}' 不在状态机里（"
                            f"{' / '.join(LEDGER_STATUSES)}）")
            continue
        if cells[7] in UNFINISHED:
            pending.append(cells)
    for w in warnings:
        print(w)
    if not pending:
        print("无待处理改进（全部已晋升/驳回；登记条目的编号与状态见骨架库 docs/EVOLUTION-PROCESS.md）。")
        return
    print(f"待处理改进 {len(pending)} 条（{f}）:")
    for c in pending:
        scene = c[4] or c[3] or "（无描述）"
        print(f"  {c[0]} [{c[7]}] 类别={c[2] or '?'} {scene}")
    print("\n审核：对任意 harness 说「evolve <项目路径>」，标准见骨架库 docs/EVOLUTION-PROCESS.md")


def cmd_doctor(_args):
    tools = [
        ("git", "git", None),
        ("node", "node", None),
        ("npm", "npm", None),
        ("backlog", "backlog", "npm i -g backlog.md"),
        ("uv", "uv", None),
        ("specify", "specify", "uv tool install specify-cli"),
        ("worktrunk", "git-wt", "winget install max-sixty.worktrunk"),
    ]
    missing = 0
    print("依赖自检（03 需要 backlog/specify/git-wt；02 backlog 可选；01/04 零依赖）:")
    for label, cmd, hint in tools:
        path = shutil.which(cmd)
        if path:
            print(f"  [OK]    {label:<10} {path}")
        else:
            missing += 1
            line = f"  [缺失]  {label:<10}"
            if hint:
                line += f"安装: {hint}"
            print(line)
    if missing:
        print(f"\n{missing} 项缺失。按需安装即可——对应骨架不用到齐也能开工，缺的走回落路径。")
    else:
        print("\n全部就绪。")


def main():
    _utf8_streams()
    ap = argparse.ArgumentParser(description="CoHarness 工具链")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("list", help="列出可用骨架")
    p_init = sub.add_parser("init", help="实例化骨架")
    p_init.add_argument("skeleton", help="骨架名或前缀，如 solo-code / 03")
    p_init.add_argument("target", help="目标项目路径")
    p_init.add_argument("--adapter", help="生成工具适配指针，逗号分隔: claude,gemini,cursor,copilot,windsurf 或 all")
    p_sync = sub.add_parser("sync", help="开工协议：pull + 看板 + stale")
    p_sync.add_argument("project", nargs="?", help="项目路径（默认当前目录）")
    p_check = sub.add_parser("check", help="跑项目 check.py")
    p_check.add_argument("project", nargs="?", help="项目路径（默认当前目录）")
    p_imp = sub.add_parser("improve", help="列出项目待审改进条目")
    p_imp.add_argument("project", nargs="?", help="项目路径（默认当前目录）")
    sub.add_parser("doctor", help="依赖自检")
    args = ap.parse_args()

    if args.cmd is None:
        cmd_list(None)
        print("\n用法: python wsc.py {list|init|sync|check|improve|doctor} ...（-h 看详情）")
        return
    {"list": cmd_list, "init": cmd_init, "sync": cmd_sync,
     "check": cmd_check, "improve": cmd_improve, "doctor": cmd_doctor}[args.cmd](args)


if __name__ == "__main__":
    main()
