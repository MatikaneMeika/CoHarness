#!/usr/bin/env python3
"""CoHarness 工具链：骨架实例化 + 合作区日常操作。

用法:
    python wsc.py list                     # 列出可用骨架
    python wsc.py init <骨架名> <目标路径>   # 实例化骨架（占位符清单 + pre-commit 安装）
    python wsc.py sync [项目路径]           # 开工协议：pull + 看板摘要 + stale 报告
    python wsc.py claim <项目> <卡号> <标识> # 原子认领一张 todo 卡（被抢自动还原）
    python wsc.py check [项目路径]          # 跑项目 scripts/check.py 全部检查
    python wsc.py stats [项目路径]          # 本地统计：遵循率 / 返工信号 / stale 分布
    python wsc.py doctor                   # 依赖自检（node/backlog/uv/specify/worktrunk）

骨架名支持全名/编号/前缀，如 solo / 03 / doc-production。
所有 subprocess 调用均为同一安全形状：argv 全字面量、shell=False、用户路径只作 cwd、
输出显式按 utf-8 解码（见 _run）。
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PLACEHOLDER_RE = re.compile(r"\{\{([A-Z][A-Z0-9_]*)\}\}")
LIB_PATH_TOKEN = "{{COHARNESS_LIB}}"


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
        "npm i -g backlog.md && backlog init --task-prefix T --agent-instructions none",
        "  注意：--agent-instructions 会往 AGENTS.md 里注入 24 行它自己的说明（实测 1.53.0），"
        "协作规则唯一权威是 AGENTS.md，所以这里要写 none",
        "  然后把 backlog/config.yml 里的 statuses 与 default_status 改成: todo, doing, review, done",
        "  （真工具默认是 To Do / In Progress / Done，不改的话 `-s doing` 会被它拒绝；"
        "`backlog config set statuses` 也拒绝直改，只能编辑文件）",
        "uv tool install specify-cli，再对每个在场工具各跑一次:",
        "  specify init --integration zcode   # codex / qodercli / generic（Antigravity）同理",
        "winget install max-sixty.worktrunk   # Windows 下命令为 git-wt",
    ],
    "02-study-office": [
        "可选（仅交付型多任务/多人分工时）：npm i -g backlog.md && backlog init",
        "  然后把看板列改为: todo, doing, review, done",
    ],
}

# 每家一个列表：有的工具一个入口不够（Copilot 既有全局文件也有路径特定文件）。
# 各家语法按实测核对，来源记在 tests/test_adapters.py 的 SOURCES；产物只含指针与工具元数据。
ADAPTERS = {
    "claude": [("CLAUDE.md",
                "CoHarness 适配指针。规则唯一权威是 AGENTS.md，本文件不复制第二份。\n\n"
                "@AGENTS.md\n")],                      # Claude Code 的 @ 导入语法
    "gemini": [("GEMINI.md",
                "CoHarness 适配指针。规则唯一权威是 AGENTS.md，本文件不复制第二份。\n\n"
                "@AGENTS.md\n")],                      # Gemini CLI 的上下文文件同样支持 @ 导入
    "cursor": [(".cursor/rules/coharness.mdc",
                "---\ndescription: CoHarness 协作规则指针（规则本体在 AGENTS.md）\n"
                "globs:\nalwaysApply: true\n---\n\n"
                "本项目协作规则唯一权威是 `AGENTS.md` 与 `.agent/`；本文件只作指针，不复制规则正文。\n")],
    "copilot": [
        (".github/copilot-instructions.md",
         "CoHarness 适配指针。项目协作规则唯一权威是仓库根的 `AGENTS.md` 与 `.agent/`；"
         "本文件只作指针，不复制规则正文。\n"),
        # 路径特定指令的官方格式：.github/instructions/*.instructions.md + YAML 头 applyTo
        (".github/instructions/coharness.instructions.md",
         "---\napplyTo: '**'\n---\n\n"
         "CoHarness 适配指针：协作规则唯一权威是仓库根的 `AGENTS.md` 与 `.agent/`，"
         "本文件只作指针，不复制第二份规则。\n"),
    ],
    "windsurf": [(".windsurf/rules/coharness.md",
                  "---\ntrigger: always_on\n---\n\n"
                  "CoHarness 适配指针：规则唯一权威是 `AGENTS.md` 与 `.agent/`，本文件不复制第二份。\n")],
    "zcode": [],       # 原生读 AGENTS.md
    "codex": [],       # 原生
    "qoder": [],       # 原生读 AGENTS.md
}
LEGACY_ADAPTERS = (".cursorrules", ".windsurfrules")   # Wave 8 前的单文件写法，仍被兼容但不是标准


def adapter_targets(spec):
    names = list(ADAPTERS) if spec.strip().lower() == "all" else \
        [s.strip() for s in spec.split(",") if s.strip()]
    out = []
    for n in names:
        for rel, _body in ADAPTERS.get(n, []):
            out.append((n, rel))
    return out


def write_adapters(dst: Path, spec: str):
    """按各工具原生语法生成合法格式的指针文件。已存在的不覆盖。"""
    unknown = [s.strip() for s in spec.split(",")
               if s.strip() and s.strip().lower() not in ADAPTERS and s.strip().lower() != "all"]
    for n in unknown:
        print(f"  [跳过] 未知 adapter: {n}（可选: {', '.join(ADAPTERS)} 或 all）")
    made = []
    for name, rel in adapter_targets(spec):
        p = dst / rel
        if p.exists():
            print(f"  [跳过] {rel} 已存在")
            continue
        p.parent.mkdir(parents=True, exist_ok=True)
        body = next(b for r, b in ADAPTERS[name] if r == rel)
        p.write_text(body, encoding="utf-8", newline="\n")
        made.append(rel)
    return made


def cmd_adapters(args):
    """--install 往已有项目补指针（装机后又来了一家的场景）；--verify 检查它们还是薄指针。"""
    if getattr(args, "install", None):
        project = Path(args.project).resolve() if args.project else Path.cwd()
        if not (project / "AGENTS.md").exists():
            sys.exit(f"[adapters] {project} 里没有 AGENTS.md，指针没有可指向的权威")
        made = write_adapters(project, args.install)
        if made:
            print(f"  已补适配指针: {', '.join(made)}")
        else:
            print("  没有新文件（要么已存在不覆盖，要么名字都不认识）")
        return
    if not args.verify:
        print("支持的 adapter（生成用 `wsc init ... --adapter <名>`，逗号分隔或 all）:")
        for name, files in ADAPTERS.items():
            print(f"  {name:<9} " + ("、".join(rel for rel, _b in files)
                                     if files else "（原生读 AGENTS.md，无需适配文件）"))
        print(f"\n旧格式（不再生成）：{', '.join(LEGACY_ADAPTERS)}")
        print("自检：python wsc.py adapters --verify <项目>")
        return
    project = Path(args.project).resolve() if args.project else Path.cwd()
    if not (project / "AGENTS.md").exists():
        sys.exit(f"[adapters] {project} 里没有 AGENTS.md——适配指针没有可指向的权威")
    problems, checked = [], 0
    print(f"== adapters --verify {project} ==")
    for name, rel in adapter_targets("all"):
        p = project / rel
        if not p.exists():
            print(f"  [未装] {name:<9} {rel}")
            continue
        checked += 1
        text = p.read_text(encoding="utf-8")
        lines = [l for l in text.splitlines() if l.strip()]
        if "AGENTS.md" not in text:
            problems.append(f"{rel}: 没指向 AGENTS.md，等于另立权威")
        if len(lines) > 8:
            problems.append(f"{rel}: 有 {len(lines)} 行正文，疑似复制了规则本体（指针应 ≤8 行）")
        for marker in ("必须", "禁止", "不得"):
            if marker in text and "不复制" not in text and "唯一权威" not in text:
                problems.append(f"{rel}: 出现规则措辞 '{marker}' 却没有权威声明")
                break
        if rel.endswith(".mdc"):
            if not text.startswith("---"):
                problems.append(f"{rel}: Cursor .mdc 缺 frontmatter（alwaysApply 无处可写）")
            elif "alwaysApply" not in text.split("---")[1]:
                problems.append(f"{rel}: frontmatter 没有 alwaysApply")
        if rel.endswith(".windsurf/rules/coharness.md") or ".windsurf/rules/" in rel:
            if "trigger:" not in text:
                problems.append(f"{rel}: Windsurf 规则缺 trigger 键，不会被激活")
        print(f"  [已装] {name:<9} {rel}（{len(lines)} 行）")
    for legacy in LEGACY_ADAPTERS:
        if (project / legacy).exists():
            print(f"  [旧格式] {legacy} 仍在——工具还兼容它，但标准位置已换成 "
                  f"{ADAPTERS['cursor'][0][0]} / {ADAPTERS['windsurf'][0][0]}")
            problems.append(f"{legacy}: 旧单文件规则还在，建议迁到 .cursor/rules / .windsurf/rules")
    if not checked:
        print("  没有任何适配指针（装机时加 --adapter claude,cursor,... 生成）")
        return
    if problems:
        print(f"\n[违规] {len(problems)} 处：")
        for pr in problems:
            print(f"  - {pr}")
        sys.exit(1)
    print(f"\n结论：{checked} 个适配指针都只含指针与工具元数据 ✓")



def discover_skeletons():
    return sorted(
        p for p in ROOT.iterdir()
        if p.is_dir() and re.match(r"^\d{2}-", p.name)
    )


NO_SKELETON_HINT = (
    "这里没找到骨架目录（{} 下没有 01- 到 04- 的目录）。\n"
    "单文件模式只能跑项目内的日常命令（sync / check / claim / stats / improve / doctor）；"
    "装机要拿到骨架本体，二选一：\n"
    "  git clone https://github.com/MatikaneMeika/CoHarness.git  然后 python CoHarness/wsc.py init <骨架> <路径>\n"
    "  pipx install coharness（或 pip install coharness）      然后 wsc init <骨架> <路径>"
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
    if not skeletons:
        sys.exit(f"未找到骨架 '{name}'。{NO_SKELETON_HINT.format(ROOT)}")
    sys.exit(
        f"未找到骨架 '{name}'。可用骨架: {[s.name for s in skeletons]}"
    )


def instantiate(src: Path, dst: Path, skip_names=()):
    copied, skipped = [], []
    for p in sorted(src.rglob("*")):
        if not p.is_file():
            continue
        if "__pycache__" in p.parts or p.suffix == ".pyc":
            continue  # 运行残留不进骨架
        rel = p.relative_to(src)
        if skip_names and set(rel.parts) & set(skip_names):
            continue  # --minimal：整棵 backlog/ 不装
        target = dst / rel
        if target.exists():
            skipped.append(rel)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, target)
        fill_library_path(target)
        copied.append(rel)
    return copied, skipped


def fill_library_path(target: Path):
    """把 {{COHARNESS_LIB}} 换成本机骨架库路径：文档里的命令要能直接复制粘贴执行。

    写成 `<骨架库>` 时下游 harness 拿到的是个谜语——它不知道库在哪，认领命令就只能靠猜。
    """
    try:
        text = target.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return
    if LIB_PATH_TOKEN not in text:
        return
    target.write_text(text.replace(LIB_PATH_TOKEN, str(ROOT)), encoding="utf-8", newline="\n")


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


def install_hook(dst: Path, name: str):
    """把骨架钩子（pre-commit / pre-push）复制进 git 认定的 hooks 目录，返回 (状态, 说明)。

    状态：installed / exists / not-a-repo / outer-repo / git-missing / no-hook-file。
    """
    src = dst / "scripts" / "hooks" / name
    if not src.exists():
        return "no-hook-file", ""
    hooks, status, note = _hooks_target(dst)
    if status != "ok":
        return status, note
    target = hooks / name
    if target.exists():
        return "exists", str(hooks)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, target)
    try:
        target.chmod(0o755)
    except OSError:
        pass
    return "installed", str(hooks)


def install_pre_commit(dst: Path):
    return install_hook(dst, "pre-commit")


MINIMAL_TODO = """# TODO — 最小模式看板（没有 backlog 也能开工）

一行一项：`- [ ]` 待办，`- [x]` 做完。想让 ID 稳定就在行首写 `T-001：`。
要恢复卡片执法（改动挂卡 / 认领冲突 / 边界交集）：装 backlog CLI，或直接建
`backlog/tasks/` 放卡——check.py 认文件，不认工具。

- [ ] T-001：把第一个需求写成一行
"""

MINIMAL_NOTE = """
## 最小模式（装机时选了 --minimal）

- 没有 `backlog/`，任务清单在本文件同级的 `TODO.md`
- **关闭的执法**：卡片格式、改动挂卡、认领冲突、边界交集——这些都依赖任务卡
- **仍在执法**：命名规范、`.agent/improvements.md` 登记管线、pre-commit 钩子本身
- 升级路径：`python {lib}/wsc.py init <骨架> <新的空目录>`（不带 --minimal），
  或装 backlog CLI / 手建 `backlog/tasks/` 放卡，check.py 自动恢复卡片执法
"""


def write_minimal_mode(dst: Path):
    """最小模式产物：TODO.md 清单 + AGENTS.md 里写明关了什么、留了什么。"""
    (dst / "TODO.md").write_text(MINIMAL_TODO, encoding="utf-8", newline="\n")
    agents = dst / "AGENTS.md"
    if agents.exists():
        text = agents.read_text(encoding="utf-8")
        if "## 最小模式" not in text:
            agents.write_text(text.rstrip() + "\n" + MINIMAL_NOTE.format(lib=ROOT),
                              encoding="utf-8", newline="\n")


def cmd_list(_args):
    skeletons = discover_skeletons()
    if not skeletons:
        print(f"可用骨架: 无——{NO_SKELETON_HINT.format(ROOT)}")
        return
    print("可用骨架:")
    for s in skeletons:
        desc = ""
        readme = s / "AGENTS.md"
        if readme.exists():
            for line in readme.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    desc = line.lstrip("# ").strip()
                    break
        print(f"  {s.name:<28} {desc}")


def registry_path():
    """本机实例登记表：纯本地一个 json，跨项目摩擦统计用它。位置可用 COHARNESS_HOME 挪走。"""
    home = os.environ.get("COHARNESS_HOME")
    base = Path(home).expanduser() if home else Path.home() / ".coharness"
    return base / "projects.json"


def read_registry():
    try:
        data = json.loads(registry_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return data if isinstance(data, list) else []


def register_project(dst, skeleton):
    """把这次实例化记进本机登记表（路径 + 骨架名 + 本体 commit + 时间）。写失败只提示，不影响装机。"""
    rev = _git_field(["git", "rev-parse", "--short", "HEAD"], ROOT)
    entry = {"path": str(dst), "skeleton": skeleton,
             "skeleton_commit": rev[1] if rev[0] == "ok" else "",
             "instantiated_at": f"{datetime.now():%Y-%m-%d %H:%M}"}
    rows = [r for r in read_registry() if isinstance(r, dict) and r.get("path") != entry["path"]]
    rows.append(entry)
    f = registry_path()
    try:
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(rows, ensure_ascii=False, indent=1) + "\n",
                     encoding="utf-8", newline="\n")
    except OSError as e:
        return None, f"（未写入本机登记表 {f}: {e}）"
    return f, None


def cmd_init(args):
    src = resolve_skeleton(args.skeleton)
    dst = Path(args.target).resolve()
    if dst.exists() and any(p.name != ".git" for p in dst.iterdir()):
        sys.exit(f"目标目录非空: {dst}\n（骨架只能复制到空目录或新目录，避免覆盖现有规则；仅含 .git 的目录允许）")
    dst.mkdir(parents=True, exist_ok=True)

    minimal = bool(getattr(args, "minimal", False))
    skip = ("backlog",) if minimal else ()
    copied, skipped = instantiate(src, dst, skip_names=skip)
    mode = "（最小模式：不装 backlog/，任务清单走 TODO.md）" if minimal else ""
    print(f"已实例化骨架 [{src.name}]{mode} -> {dst}")
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

    pstatus, pnote = install_hook(dst, "pre-push")
    if pstatus == "installed":
        print(f"  pre-push 钩子已装进 {pnote}（merge 不跑 pre-commit，推送前再查一次看板——I-004）")
    elif pstatus == "exists":
        print(f"  {pnote}\\pre-push 已存在，未覆盖")

    if args.adapter:
        made = write_adapters(dst, args.adapter)
        if made:
            print("  适配指针（各工具原生格式，内容只有指针与工具元数据）:")
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
    if minimal:
        write_minimal_mode(dst)
        print("  最小模式产物：TODO.md + AGENTS.md 的「最小模式」节（写清了关掉哪些执法）")
        if steps:
            print("\n最小模式跳过的依赖（哪天要并行/边界执法再装）:")
            for line in steps:
                print(f"    [可选] {line}")
    elif steps:
        print(f"\n依赖安装（自检: python {ROOT / 'wsc.py'} doctor）:")
        for line in steps:
            print(f"  {line}")

    f, warn = register_project(dst, src.name)
    if f is not None:
        print(f"\n已记入本机登记表 {f}（跨项目摩擦统计用，纯本地零网络；删掉该文件即不再参与统计）")
    else:
        print(f"\n{warn}")


HOOK_NOTICES = {
    "not-a-repo": "目标不是 git 仓库根",
    "outer-repo": "目标不是仓库根（属外层仓库）",
    "git-missing": "找不到 git 命令",
}


def _contracts(project: Path):
    """读 AGENTS.md 的「接口契约」表：[(路径前缀, 契约定义在哪, 变更要通知谁)]。"""
    f = project / "AGENTS.md"
    if not f.exists():
        return []
    text = f.read_text(encoding="utf-8")
    if "## 接口契约" not in text:
        return []
    section = text.split("## 接口契约", 1)[1].split("\n## ", 1)[0]
    rows = []
    for line in section.splitlines():
        s = line.strip()
        if not (s.startswith("|") and s.endswith("|")):
            continue
        cells = [c.strip().strip("`") for c in s.strip("|").split("|")]
        if len(cells) < 3 or cells[0] == "路径前缀" or set(cells[0]) <= set("-: "):
            continue
        rows.append(tuple(cells[:3]))
    return rows


def _doing_boundaries(project: Path):
    """在看板上找在做的卡：返回 [(卡号, 持有者, [allowed 前缀])]。"""
    d = project / "backlog" / "tasks"
    out = []
    if not d.is_dir():
        return out
    for p in sorted(d.glob("*.md")):
        try:
            text = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if not text.startswith("---"):
            continue
        status, who = _card_fields(text)
        cid = (re.search(r"^id:\s*(\S+)", text, re.M) or [None, p.stem])[1]
        if status not in ("doing", "review") or not who:
            continue
        allowed = []
        body = text.split("## 边界", 1)
        if len(body) > 1:
            for line in body[1].split("allowed_paths:", 1)[-1].splitlines():
                s = line.strip()
                if s.startswith("forbidden_paths:") or (s.startswith("##") and len(s) > 2):
                    break
                if s.startswith("-"):
                    allowed.append(s.lstrip("-").strip().strip("\"'").rstrip("/"))
        out.append((cid, ", ".join(who), allowed))
    return out


def incoming_report(project: Path):
    """`sync --dry-run` 的正文：只读现有的远端跟踪引用，不 fetch、不 pull、不写任何文件。"""
    tip = _git_field(["git", "rev-parse", "--verify", "-q", "origin/main"], project)
    if tip[0] != "ok":
        print("[dry-run] 本地还没有 origin/main 的远端跟踪引用——先跑一次真 sync/fetch，"
              "之后再开工就用 --dry-run 看代价")
        return
    behind = _git_field(["git", "rev-list", "--count", "HEAD..origin/main"], project)
    log = _run(["git", "log", "--pretty=format:@@%h %s", "--name-only",
                "HEAD..origin/main"], project)
    commits, touched = [], {}
    head = ""
    for line in (log.stdout or "").splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith("@@"):
            head = s[2:]
            commits.append(head)
        else:
            touched.setdefault(s, []).append(head.split(" ", 1)[0])
    print(f"[dry-run] 不 pull、不装钩子。origin/main 领先 {behind[1] if behind[0] == 'ok' else '?'} 个提交：")
    for c in commits[:8]:
        print(f"  {c}")
    if len(commits) > 8:
        print(f"  …另有 {len(commits) - 8} 个")
    if not touched:
        print("  （看不出文件级改动：可能是 merge 提交）")
        return
    contracts = _contracts(project)
    board = _doing_boundaries(project)
    print(f"  涉及 {len(touched)} 个文件。对照接口契约表与在看板的卡：")
    hits = 0
    for f, cs in sorted(touched.items()):
        for prefix, where, whom in contracts:
            if f == prefix or f.startswith(prefix.rstrip("*") + "/") or prefix in f:
                print(f"    [契约] {f} → 定义在 {where}；变更要通知：{whom}（来自 {', '.join(cs)}）")
                hits += 1
                break
        for cid, owner, allowed in board:
            if any(f == a or f.startswith(a + "/") for a in allowed if a):
                print(f"    [边界] {f} 落在 {cid}（{owner}）的 allowed_paths 里——"
                      f"这次同步会带来冲突或返工，先看交接说明再 pull")
                hits += 1
    if not hits:
        print("    没有触及契约表或在做卡边界内的文件（仍是只读报告，实际 pull 才算数）")


def cmd_sync(args):
    project = Path(args.project).resolve() if args.project else Path.cwd()
    if not project.exists():
        sys.exit(f"项目路径不存在: {project}")
    print(f"== sync {project} ==")

    if getattr(args, "dry_run", False):
        return incoming_report(project)

    # 钩子不入版本库：clone 出来的项目默认没有执法，开工第一步顺手补装
    status, note = install_pre_commit(project)
    if status == "installed":
        print(f"[钩子] 本次开工补装进 {note}")
    elif status in HOOK_NOTICES:
        print(f"[钩子] 未装（{HOOK_NOTICES[status]}）：check.py 不会被自动触发")
    pstatus, pnote = install_hook(project, "pre-push")
    if pstatus == "installed":
        print(f"[钩子] pre-push 本次开工补装进 {pnote}（merge 不跑 pre-commit，推送前再查一次看板）")

    branch = _git_field(["git", "rev-parse", "--abbrev-ref", "HEAD"], project)
    try:
        r = _run(["git", "pull", "--ff-only"], project)
        if r.returncode != 0 and branch[0] == "ok" and branch[1] != "HEAD":
            # worktree 里的 harness 分支通常没有 upstream（git worktree add -b 就是这样），
            # 裸 pull 会 rc=1；协议要求同步的是共享分支 main，显式指名再试一次
            r2 = _run(["git", "pull", "--ff-only", "origin", "main"], project)
            if r2.returncode == 0:
                r = r2
        out = (r.stdout or r.stderr).strip() or "完成"
    except (OSError, subprocess.TimeoutExpired) as e:
        out = f"（执行失败: {e}）"
    print(f"[pull] {out}")

    if (project / "TODO.md").exists() and not (project / "backlog" / "tasks").is_dir():
        todo = (project / "TODO.md").read_text(encoding="utf-8")
        open_items = [l.strip() for l in todo.splitlines() if l.strip().startswith("- [ ]")]
        done_items = [l.strip() for l in todo.splitlines() if l.strip().startswith("- [x]")]
        print(f"[看板] 最小模式 TODO.md：{len(open_items)} 项待办 / {len(done_items)} 项已完成")
        for line in open_items[:12]:
            print(f"  {line}")
        if len(open_items) > 12:
            print(f"  …另有 {len(open_items) - 12} 项")
    elif shutil.which("backlog"):
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


def load_ledger(f: Path):
    """读改进登记表：返回 (全部条目, 非终态条目, 告警)。只读文件。"""
    rows, pending, warnings = [], [], []
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
        rows.append(cells)
        if cells[7] in UNFINISHED:
            pending.append(cells)
    return rows, pending, warnings


def _friction_key(cells):
    """同类摩擦的机械判据：类别 + 提议改动正文（去空白与 markdown 记号后取前 40 字）。"""
    proposal = re.sub(r"[\s`*_|]", "", cells[5]) or re.sub(r"[\s`*_|]", "", cells[4])
    return (cells[2], proposal[:40])


def cmd_improve_cross(args):
    """跨项目摩擦统计：把本机登记过的实例的非终态条目按同类归并，只出机械计数。

    门槛"同类摩擦 ≥2 次"是审核标准里的客观那一半，这里给的是证据；
    "是不是真的同一件事"仍归人判——所以每条都带来源项目，不做自动晋升。
    """
    reg = read_registry()
    if not reg:
        sys.exit(f"本机登记表是空的（{registry_path()}）：先用 wsc init 实例化骨架，"
                 f"或设 COHARNESS_HOME 指向已有登记表")
    print(f"== 跨项目改进统计（本机登记表 {registry_path()}）==")
    groups, scanned, skipped, _paths, warns = _scan_registry_ledgers()
    for w in warns:
        print(f"  {w}")
    for proj in skipped:
        print(f"  [跳过] {proj}（无 .agent/improvements.md，路径可能已移走）")
    missing = len(skipped)
    if not groups:
        print(f"扫描 {scanned} 个实例：无非终态条目，没有可统计的摩擦。")
        return
    print(f"扫描 {scanned} 个实例（另有 {missing} 个登记路径已失效），非终态条目按同类归并：\n")
    for (category, _), hits in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        projects = sorted({p for p, _ in hits})
        verdict = "达到 ≥2 门槛，可进待审" if len(projects) >= 2 else "单项目孤证，继续攒证据"
        print(f"  [{category}] {len(projects)} 个项目 / {len(hits)} 条 → {verdict}")
        print(f"    提议：{hits[0][1][5] or hits[0][1][4]}")
        for pname, cells in hits:
            print(f"    - {pname} {cells[0]}（{cells[7]}）：{cells[3]}")
    print("\n机械计数只回答「出现过几次」；有效性/必要性/副作用三条标准见 "
          f"{ROOT / 'docs' / 'EVOLUTION-PROCESS.md'}。")


def _scan_registry_ledgers():
    """{同类键: [(项目名, 条目)]} + 扫描统计；evolve 与 improve --cross 共用同一份计数。"""
    groups, scanned, skipped, paths, warns = {}, 0, [], set(), []
    for entry in read_registry():
        proj = Path(entry.get("path", ""))
        f = proj / ".agent" / "improvements.md"
        if not f.exists():
            skipped.append(str(proj))
            continue
        scanned += 1
        paths.add(str(proj.resolve()))
        _, pending, warnings = load_ledger(f)
        for w in warnings:
            warns.append(f"{proj.name}:{w}")
        for cells in pending:
            groups.setdefault(_friction_key(cells), []).append((proj.name, cells))
    return groups, scanned, skipped, paths, warns


def cmd_improve(args):
    """列出项目改进登记表中的非终态条目（登记/试点中/待审）。纯读文件，不改任何东西。"""
    if getattr(args, "cross", False):
        return cmd_improve_cross(args)
    project = Path(args.project).resolve() if args.project else Path.cwd()
    f = project / ".agent" / "improvements.md"
    if not f.exists():
        sys.exit(f"未找到 {f}（该骨架不含改进登记表，或项目未实例化）")
    _, pending, warnings = load_ledger(f)
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


def _read_telemetry(project: Path):
    f = project / ".agent" / "telemetry.jsonl"
    if not f.exists():
        return [], 0, f
    entries, bad = [], 0
    for line in f.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            e = json.loads(line)
        except ValueError:
            bad += 1
            continue
        if isinstance(e, dict):
            entries.append(e)
        else:
            bad += 1
    return entries, bad, f


def _churn(project, days):
    """git log 里近 N 天每个文件被几次提交、哪些作者触及：返工信号的原始计数。"""
    r = _run(["git", "log", f"--since={days} days ago", "--name-only",
              "--pretty=format:@@%h|%an"], project)
    if r.returncode != 0:
        return None
    counts = {}
    commit_id, author = "", ""
    for line in (r.stdout or "").splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith("@@"):
            _, _, rest = s.partition("|")
            commit_id, author = s[2:].split("|", 1)[0], rest
            continue
        rec = counts.setdefault(s, {"ids": set(), "who": set()})
        rec["ids"].add(commit_id)
        rec["who"].add(author)
    return counts


def cmd_stats(args):
    """三张报告：规则遵循率 / 返工信号 / stale 分布。数据源只有本地文件与 git log。"""
    project = Path(args.project).resolve() if args.project else Path.cwd()
    days = args.days
    print(f"== stats {project}（近 {days} 天）==")

    entries, bad, tfile = _read_telemetry(project)
    print(f"\n[1] 规则遵循率（{tfile}，{len(entries)} 条执行记录"
          + (f"，{bad} 行读不懂已跳过" if bad else "") + "）")
    if not entries:
        print("  还没有运行记录：check.py 每次执行会追加一行（--no-track 或 COHARNESS_NO_TRACK=1 可关）")
    else:
        by = {}
        for e in entries:
            by.setdefault(e.get("harness", "unknown"), []).append(e)
        for who, rows in sorted(by.items()):
            passed = sum(1 for e in rows if e.get("rc") == 0)
            print(f"  {who}: {passed}/{len(rows)} 次全绿（{passed * 100 // len(rows)}%）")
            per = {}
            for e in rows:
                for k, v in (e.get("checks") or {}).items():
                    hit = per.setdefault(k, [0, 0])
                    hit[1] += 1
                    hit[0] += 1 if v else 0
            detail = "  ".join(f"{k} {ok}/{tot}" for k, (ok, tot) in sorted(per.items()) if ok != tot)
            if detail:
                print(f"      失分项：{detail}")
        cards_seen = sorted({e.get("card") for e in entries if e.get("card")})
        print(f"  记录覆盖的卡片：{', '.join(cards_seen) if cards_seen else '（无 doing 卡记录）'}")

    print(f"\n[2] 返工信号（git log 近 {days} 天，同一文件被 ≥3 次提交触及）")
    churn = _churn(project, days)
    if churn is None:
        print("  git log 读不到（不是仓库？），跳过")
    else:
        hits = sorted(((f, v) for f, v in churn.items() if len(v["ids"]) >= 3),
                      key=lambda kv: -len(kv[1]["ids"]))
        if not hits:
            print("  无：近期内没有反复改动的文件")
        for f, v in hits[:10]:
            cross = "（跨 harness，先看是不是边界没切清）" if len(v["who"]) > 1 else ""
            print(f"  {f}：{len(v['ids'])} 次提交，作者 {', '.join(sorted(v['who']))}{cross}")
        if len(hits) > 10:
            print(f"  …另有 {len(hits) - 10} 个文件")

    print("\n[3] stale 分布（check.py --stale 原样转述）")
    if (project / "scripts" / "check.py").exists():
        # --no-track：统计工具不该把自己读到的数据写胖（否则每次 stats 都 +1 条"执行记录"）
        r = _run([sys.executable, "scripts/check.py", "--stale", "--no-track"], project, timeout=120)
        print(_indent(r.stdout or "") or "  （无输出）")
        if r.stderr:
            print(_indent(r.stderr))
    else:
        print("  项目不带 scripts/check.py，无 stale 报告")


DEGRADE = {
    "backlog": {
        "丢了什么": "看板 CLI（backlog board / task list / task edit）与它的自动提交",
        "降级行为": "卡还是 md 文件：`wsc sync` 回落读 `backlog/tasks/*.md`，"
                    "手工建卡/改卡照旧被 check.py 执法；零依赖起步用 `init --minimal` 的 TODO.md 清单",
        "执法变化": "无（卡片层执法读文件，不读工具）",
        "probe": ("any", ["backlog/tasks", "TODO.md"]),
    },
    "specify": {
        "丢了什么": "spec-kit 的 /speckit-specify|clarify|plan|tasks 流程命令",
        "降级行为": "手工五步拆解：需求 → 技术口径 → 边界(allowed/forbidden) → 验收清单 → 交接说明，"
                    "照样写成卡与 spec 文档，pm 角色转卡这步由人做",
        "执法变化": "无；只是规格产物的格式没人替你校验，边界要自己写准",
        "probe": ("file", [".agent/workflows", "AGENTS.md"]),
    },
    "worktrunk": {
        "丢了什么": "`git-wt` 的便捷工作树管理（Windows 下工作树并行靠它省事）",
        "降级行为": "用原生 `git worktree add` 建工作树，或退成普通分支 + 串行干活——"
                    "**一个 harness 一个工作目录**这条不变，两条 harness 不许共居同一 clone",
        "执法变化": "无（pre-commit 在共享的 .git/hooks 里，worktree 照样过钩子）",
        "probe": ("dir", [".git"]),
    },
    "node": {
        "丢了什么": "npm 生态（backlog.md 是 npm 包）",
        "降级行为": "同上：手建卡片文件；或换 uv/pipx 侧的等价工具，规则不变",
        "执法变化": "无",
        "probe": ("any", ["backlog/tasks", "TODO.md"]),
    },
}


def _probe_ok(project: Path, kind, names):
    for n in names:
        p = project / n
        if kind == "dir" and p.is_dir():
            return p
        if kind == "file" and p.exists():
            return p
        if kind == "any" and p.exists():
            return p
    return None


def cmd_doctor(args):
    if getattr(args, "explain", None):
        for key in args.explain.split(","):
            spec = DEGRADE.get(key.strip())
            if spec is None:
                print(f"[doctor --explain] 没有登记过 '{key}' 的降级行为，可选项：{', '.join(DEGRADE)}")
                continue
            print(f"{key} 没装时:")
            for label in ("丢了什么", "降级行为", "执法变化"):
                print(f"  {label}：{spec[label]}")
        return
    if getattr(args, "simulate_missing", None):
        project = Path(args.project).resolve() if getattr(args, "project", None) else Path.cwd()
        for key in args.simulate_missing.split(","):
            spec = DEGRADE.get(key.strip())
            if spec is None:
                print(f"[simulate] 没有 '{key}' 的降级规格，可选项：{', '.join(DEGRADE)}")
                continue
            kind, names = spec["probe"]
            hit = _probe_ok(project, kind, names)
            print(f"{key} 缺失时演练（项目 {project}）：")
            print(f"  丢了什么：{spec['丢了什么']}")
            print(f"  降级路径：{spec['降级行为']}")
            if hit:
                print(f"  [可用] 回落产物在位：{hit.relative_to(project).as_posix()}")
            else:
                print(f"  [不可用] 项目里找不到 {names} 中任何一个——"
                      f"照上面那条路补一个（`init --minimal` 会生成 TODO.md）")
        return

    tools = [
        ("git", "git", None),
        ("node", "node", None),
        ("npm", "npm", None),
        ("backlog", "backlog", "npm i -g backlog.md"),
        ("uv", "uv", None),
        ("specify", "specify", "uv tool install specify-cli"),
        ("worktrunk", "git-wt", "winget install max-sixty.worktrunk"),
    ]
    missing = []
    print("依赖自检（03 需要 backlog/specify/git-wt；02 backlog 可选；01/04 零依赖）:")
    for label, cmd, hint in tools:
        path = shutil.which(cmd)
        if path:
            print(f"  [OK]    {label:<10} {path}")
        else:
            missing.append(label)
            line = f"  [缺失]  {label:<10}"
            if hint:
                line += f"安装: {hint}"
            print(line)
    if missing:
        print(f"\n{len(missing)} 项缺失：{', '.join(missing)}")
        print("按需安装即可——不用到齐也能开工，缺的走回落路径：")
        print(f"  python {ROOT / 'wsc.py'} doctor --explain {','.join(m for m in missing if m in DEGRADE)}")
    else:
        print("\n全部就绪。")


def _find_card(project: Path, card_id: str):
    """按 frontmatter 的 id 找卡文件（兼容手工 T-001.md 与 backlog 的 t-1 - 标题.md）。"""
    d = project / "backlog" / "tasks"
    if not d.is_dir():
        return None
    for p in sorted(d.glob("*.md")):
        try:
            text = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if re.search(rf"^id:\s*{re.escape(card_id)}\s*$", text, re.M) and text.startswith("---"):
            return p
    return None


def _card_fields(text: str):
    get = lambda k: (re.search(rf"^{k}:[ \t]*(.*)$", text, re.M) or [None, ""])[1].strip()
    assignee = get("assignee")
    who = [w for w in re.split(r"[,\s]+", assignee.strip("[]\"'")) if w]
    return get("status").strip("\"'").lower(), who


def _claimable(project: Path, limit=6):
    d = project / "backlog" / "tasks"
    out = []
    if d.is_dir():
        for p in sorted(d.glob("*.md")):
            try:
                text = p.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            if not text.startswith("---"):
                continue
            status, who = _card_fields(text)
            cid = re.search(r"^id:\s*(\S+)", text, re.M)
            if status == "todo" and not who and cid:
                out.append(cid.group(1))
    return out


def _set_card_field(text, key, value):
    """改写卡片 frontmatter 的一个标量键；键不存在就按声明子集追加。"""
    line = f"{key}: {value}"
    if re.search(rf"^{key}:", text, re.M):
        return re.sub(rf"^{key}:.*$", line, text, count=1, flags=re.M)
    if text.startswith("---\n"):
        head, sep, rest = text.partition("\n---")
        return f"{head}\n{line}\n---{rest}"
    return line + "\n" + text


def _stage_claim(project, card_id, who, now):
    """把认领写进卡并交给项目自己的 check.py 判：返回 (卡片相对路径, None) 或 (None, 失败原因)。

    判定不另写一套——一 harness 一张 doing 卡、边界交集不得并行都在 check.py 里，
    这里只负责"被拒就把卡还原成读到的原文"。
    """
    path = _find_card(project, card_id)
    if path is None:
        return None, f"卡 {card_id} 不在看板上"
    text = path.read_text(encoding="utf-8")
    status, owners = _card_fields(text)
    if owners and owners != [who]:
        return None, f"已被 {', '.join(owners)} 认领（状态 {status or '空'}）"
    if status not in ("todo", ""):
        return None, f"状态是 {status}，只有 todo 可领"
    rel = path.relative_to(project).as_posix()
    new = _set_card_field(text, "status", "doing")
    new = _set_card_field(new, "assignee", f"[{who}]")
    new = _set_card_field(new, "updated_date", now)
    path.write_text(new, encoding="utf-8", newline="\n")
    verdict = _run([sys.executable, "scripts/check.py", "--tasks"], project, timeout=120)
    if verdict.returncode != 0:
        path.write_text(text, encoding="utf-8", newline="\n")
        detail = ((verdict.stdout or "") + (verdict.stderr or "")).strip()
        return None, f"认领被执法拒回（已还原 {rel}）：\n{detail}"
    return rel, None


def cmd_claim(args):
    """原子认领：先同步，再校验，写卡过钩子，推 main；被抢就放弃并回到远端状态。

    冲突判定不另写一套：写卡后交给项目自己的 check.py --tasks（一 harness 一张 doing 卡、
    边界交集不得并行都在那里）。认领被拒时 reset --hard origin/main 是安全的，
    因为开头已经确认过工作区干净。
    """
    project = Path(args.project).resolve()
    if not (project / "scripts" / "check.py").exists():
        sys.exit(f"未找到 {project / 'scripts' / 'check.py'}（该骨架不带执法脚本，无需认领）")
    path = _find_card(project, args.card)
    if path is None:
        sys.exit(f"[claim] 找不到卡 {args.card}（在 {project / 'backlog' / 'tasks'} 里按 id 查）")

    if args.dry_run:
        status, who = _card_fields(path.read_text(encoding="utf-8"))
        print(f"[claim --dry-run] {args.card}: status={status or '空'} assignee={who or '（无）'}")
        print(f"  将改为 status: doing / assignee: [{args.who}]，过 check.py 后 commit 并 push origin HEAD:main")
        free = _claimable(project)
        print(f"  此刻可认领：{', '.join(free) if free else '（无）'}")
        return

    dirty = _run(["git", "status", "--porcelain"], project)
    if (dirty.stdout or "").strip():
        sys.exit("[claim] 工作区有未提交改动：先提交或撤销再认领，"
                 "免得把别人的改动卷进这次提交")

    has_remote = "origin" in (_run(["git", "remote"], project).stdout or "")
    if has_remote:
        r = _run(["git", "fetch", "-q", "origin"], project)
        if r.returncode != 0:
            sys.exit(f"[claim] fetch 失败：{(r.stderr or r.stdout).strip()}")
        rebase = _run(["git", "rebase", "-q", "origin/main"], project)
        if rebase.returncode != 0:
            _run(["git", "rebase", "--abort"], project)
            sys.exit("[claim] 与 origin/main 变基冲突，已中止变基不做半截认领："
                     f"\n{(rebase.stdout or '') + (rebase.stderr or '')}")

    # 校验与写卡都在同步之后：同步前读到的快照可能已被别人改走，
    # 拿旧快照改写就是静默覆盖别人的认领（演练抓到的 A1 形态）。
    now = f"{datetime.now():%Y-%m-%d %H:%M}"
    out = ""
    for attempt in range(1, 4):
        # 每一轮都从当前树重新写卡：上一轮推送失败后已经回滚到远端状态，
        # 这一轮的 _stage_claim 顺带负责"抢输了"的判定。
        rel, why = _stage_claim(project, args.card, args.who, now)
        if rel is None:
            free = ", ".join(_claimable(project)) or "（无，等看板更新）"
            if attempt == 1:
                sys.exit(f"[claim] {args.card} {why}。此刻可认领：{free}")
            sys.exit(f"[claim] 抢输了：{args.card} {why}，已回到远端状态。"
                     f"此刻可认领：{free}\n{out}")
        if _run(["git", "add", rel], project).returncode != 0:
            sys.exit("[claim] git add 失败")
        commit = _run(["git", "commit", "-q", "-m", f"claim {args.card} -> {args.who}"], project)
        out += (commit.stdout or "") + (commit.stderr or "")
        if commit.returncode != 0:
            # 开头确认过工作区干净，此刻盘上只有这张卡的改动，硬回退不会伤到别人
            _run(["git", "reset", "-q", "--hard", "HEAD"], project)
            sys.exit(f"[claim] 提交被钩子拦下（已还原）：\n{out}")
        if not has_remote:
            print(f"[claim] 已本地认领 {args.card} → {args.who}（无 origin 远端，跳过 push：{rel}）")
            return
        push = _run(["git", "push", "-q", "origin", "HEAD:main"], project)
        if push.returncode == 0:
            print(f"[claim] {args.card} → {args.who}（第 {attempt} 次尝试，已进 main）")
            return
        out += (push.stdout or "") + (push.stderr or "")
        _run(["git", "fetch", "-q", "origin"], project)
        _run(["git", "reset", "-q", "--hard", "origin/main"], project)
    sys.exit(f"[claim] 三次推送都被拒，已回到远端状态：\n{out}")


def main():
    _utf8_streams()
    ap = argparse.ArgumentParser(description="CoHarness 工具链")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("list", help="列出可用骨架")
    p_init = sub.add_parser("init", help="实例化骨架")
    p_init.add_argument("skeleton", help="骨架名或前缀，如 solo-code / 03")
    p_init.add_argument("target", help="目标项目路径")
    p_init.add_argument("--adapter", help="生成工具适配指针，逗号分隔: claude,gemini,cursor,copilot,windsurf 或 all")
    p_init.add_argument("--minimal", action="store_true",
                        help="零外部依赖起步：不装 backlog/，任务清单用 TODO.md（卡片执法随之关闭）")
    p_sync = sub.add_parser("sync", help="开工协议：pull + 看板 + stale")
    p_sync.add_argument("project", nargs="?", help="项目路径（默认当前目录）")
    p_sync.add_argument("--dry-run", action="store_true",
                        help="不 pull、不写盘：报告即将进来的改动触及哪些契约与在做卡的边界")
    p_check = sub.add_parser("check", help="跑项目 check.py")
    p_check.add_argument("project", nargs="?", help="项目路径（默认当前目录）")
    p_imp = sub.add_parser("improve", help="列出项目待审改进条目")
    p_imp.add_argument("project", nargs="?", help="项目路径（默认当前目录）")
    p_imp.add_argument("--cross", action="store_true",
                       help="扫本机登记表里的全部实例，按同类摩擦出机械计数")
    p_claim = sub.add_parser("claim", help="原子认领一张 todo 卡（写卡+过钩子+推 main）")
    p_claim.add_argument("project", help="项目路径")
    p_claim.add_argument("card", help="卡片 id，如 T-003")
    p_claim.add_argument("who", help="认领者标识（harness id，与卡 assignee/分支名一致）")
    p_claim.add_argument("--dry-run", action="store_true", help="只报告会不会成功，不写盘不提交")
    p_stats = sub.add_parser("stats", help="本地运行统计：规则遵循率 / 返工信号 / stale 分布")
    p_stats.add_argument("project", nargs="?", help="项目路径（默认当前目录）")
    p_stats.add_argument("--days", type=int, default=7, help="返工信号回溯天数（默认 7）")
    p_adp = sub.add_parser("adapters", help="列出/自检工具适配指针（只含指针，不含第二份规则）")
    p_adp.add_argument("project", nargs="?", help="项目路径（--verify 时用）")
    p_adp.add_argument("--verify", action="store_true", help="检查项目里的适配指针是否还是薄指针")
    p_adp.add_argument("--install", metavar="名",
                       help="往已有项目补生成指针（逗号分隔或 all），已存在的不覆盖")
    p_doc = sub.add_parser("doctor", help="依赖自检")
    p_doc.add_argument("project", nargs="?", help="演练降级路径时使用的项目路径")
    p_doc.add_argument("--explain", help="打印某个依赖缺失后的降级行为（逗号分隔），如 backlog,specify")
    p_doc.add_argument("--simulate-missing", metavar="依赖名",
                       help="假装该依赖没装：在指定项目里核对回落产物是否真在位")
    args = ap.parse_args()

    if args.cmd is None:
        cmd_list(None)
        print("\n用法: python wsc.py {list|init|sync|check|improve|claim|stats|doctor} ...（-h 看详情）")
        return
    {"list": cmd_list, "init": cmd_init, "sync": cmd_sync,
     "check": cmd_check, "improve": cmd_improve, "claim": cmd_claim,
     "stats": cmd_stats, "adapters": cmd_adapters, "doctor": cmd_doctor}[args.cmd](args)


if __name__ == "__main__":
    main()
