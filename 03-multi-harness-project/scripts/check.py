#!/usr/bin/env python3
"""仓库健康检查 v2：命名规范、Backlog 任务卡、越权改动、stale 提示、认领冲突。

任务卡由 Backlog.md 管理在 backlog/tasks/（或 backlog.config.yml 指定目录），
卡片格式约定见 .agent/tasks/CARD-CONVENTION.md。

用法（在项目根目录执行）:
    python scripts/check.py               # 全部检查（stale 仅提示，不影响退出码）
    python scripts/check.py --names       # 仅命名规范
    python scripts/check.py --tasks       # 仅任务卡格式 / 边界节 / 认领冲突
    python scripts/check.py --diff        # 仅改动挂卡检查（需要 git）
    python scripts/check.py --stale       # 仅 stale 卡报告（advisory）

退出码：0 = 通过；1 = 存在违规（stale 提示不算违规，不拦截提交）。
"""
import argparse
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TASKS_DIRNAME = "backlog"
DEFAULT_COLUMNS = ["todo", "doing", "review", "done"]
STALE_HOURS = 24
# 命名检查跳过这些目录：卡片标题、spec-kit 模板合法含 final 等词，不是交付文件
SKIP_DIRS = {
    ".git", "node_modules", ".venv", "venv", "__pycache__",
    "dist", "build", ".zcode", ".qoder", ".mimosa", ".agent",
    "backlog", ".backlog", ".specify", "templates",
}
# 交付文件名禁带的后缀（PoseWise 教训：版本后缀堆积）
BAD_NAME_RE = re.compile(
    r"(?i)[-_\s](v\d+|final|副本|copy|backup|bak|新版|最新版?|修正版?|最终版?)(\.[a-z0-9]+)?$"
)


def _read_text(p: Path):
    try:
        return p.read_text(encoding="utf-8")
    except OSError:
        return None


def parse_frontmatter(path: Path):
    """解析 Backlog 卡的扁平 frontmatter：key: value / key: [] / key: 换行 - item。"""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return None, text
    lines = text.splitlines()[1:]
    meta, current_key, body_start = {}, None, 0
    for i, line in enumerate(lines):
        if line.strip() == "---":
            body_start = i + 1
            break
        m = re.match(r"^([\w-]+):\s*(.*)$", line)
        if m and not line.startswith((" ", "\t")):
            current_key = m.group(1)
            val = re.split(r"\s+#", m.group(2).strip())[0].strip()
            if val.startswith("[") and val.endswith("]"):
                inner = val[1:-1].strip()
                meta[current_key] = (
                    [x.strip().strip('"').strip("'") for x in inner.split(",") if x.strip()]
                    if inner else []
                )
            elif val == "":
                meta[current_key] = []
            else:
                meta[current_key] = val.strip('"').strip("'")
        elif line.lstrip().startswith("- ") and current_key is not None and isinstance(
            meta.get(current_key), list
        ):
            meta[current_key].append(line.lstrip()[2:].strip().strip('"').strip("'"))
    body = "\n".join(lines[body_start:])
    return meta, body


def _yaml_scalar(text: str, key: str):
    m = re.search(rf"^{key}:\s*(.+?)\s*(#.*)?$", text, re.M)
    return m.group(1).strip().strip('"').strip("'") if m else None


def _yaml_list_under(text: str, key: str):
    """取某 key 下的 '- item' 列表或行内 [a, b]（浅层，容忍缩进）。"""
    items, in_block = [], False
    for line in text.splitlines():
        m = re.match(rf"^\s*{key}:\s*(.*)$", line)
        if m:
            inline = m.group(1).strip()
            if inline.startswith("[") and inline.endswith("]"):
                inner = inline[1:-1].strip()
                return [x.strip() for x in inner.split(",") if x.strip()]
            in_block = True
            continue
        if in_block:
            if re.match(r"^\s+-\s+\S", line):
                items.append(re.sub(r"^\s+-\s+", "", line).strip())
            elif line.strip():
                in_block = False
    return items


def load_config():
    """读 backlog 配置：卡片目录名与看板列。解析失败一律回落默认值。"""
    dirname = DEFAULT_TASKS_DIRNAME
    t = _read_text(ROOT / "backlog.config.yml")
    if t:
        d = _yaml_scalar(t, "backlog_directory")
        if d:
            dirname = d
    columns = list(DEFAULT_COLUMNS)
    for cand in (ROOT / dirname / "config.yml", ROOT / f"{Path(dirname).name}.config.yml"):
        t = _read_text(cand)
        if t:
            cols = _yaml_list_under(t, "columns")
            if cols:
                columns = [c.strip().lower() for c in cols]
            break
    return ROOT / dirname / "tasks", columns


def parse_boundary(body: str):
    """提取卡体 '## 边界' 节的 allowed_paths / forbidden_paths。"""
    m = re.search(r"^##\s*边界\s*$", body, re.M)
    if not m:
        return [], [], False
    rest = body[m.end():]
    nxt = re.search(r"^##\s+", rest, re.M)
    section = rest[: nxt.start()] if nxt else rest
    return _yaml_list_under(section, "allowed_paths"), _yaml_list_under(
        section, "forbidden_paths"
    ), True


def load_cards(tasks_dir: Path):
    cards = []
    if not tasks_dir.exists():
        return cards
    for p in sorted(tasks_dir.glob("*.md")):
        meta, body = parse_frontmatter(p)
        if not meta or "id" not in meta:  # 非卡片文件（如 README）
            continue
        allowed, forbidden, has_boundary = parse_boundary(body)
        assignees = meta.get("assignee") or []
        if isinstance(assignees, str):
            assignees = [assignees]
        cards.append({
            "name": p.name,
            "path": p,
            "meta": meta,
            "status": str(meta.get("status", "")).strip().lower(),
            "assignees": [a for a in assignees if str(a).strip()],
            "allowed": allowed,
            "forbidden": forbidden,
            "has_boundary": has_boundary,
        })
    return cards


def iter_files():
    for p in ROOT.rglob("*"):
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if p.is_file():
            yield p


def check_names():
    bad = []
    for p in iter_files():
        if BAD_NAME_RE.search(p.name):
            bad.append(p.relative_to(ROOT))
    if bad:
        print("[命名规范] 违规（交付文件名禁带版本/副本后缀，版本交给 git）:")
        for b in bad:
            print(f"  - {b}")
    else:
        print("[命名规范] 通过")
    return not bad


def check_tasks(cards, columns):
    ok = True
    if not cards:
        print("[任务卡] 无任务卡")
        return True
    doing_by = {}
    for c in cards:
        problems = []
        if c["status"] not in columns:
            problems.append(f"status 非法: '{c['status']}'（合法列: {', '.join(columns)}）")
        if not str(c["meta"].get("title", "")).strip():
            problems.append("title 为空")
        if c["status"] in ("doing", "review") and not c["assignees"]:
            problems.append(f"status={c['status']} 但未认领（assignee 为空）")
        if len(c["assignees"]) > 1:
            problems.append(f"一卡多 assignee: {c['assignees']}（认领必须唯一）")
        if not c["has_boundary"]:
            problems.append('卡体缺 "## 边界" 节（格式见 .agent/tasks/CARD-CONVENTION.md）')
        else:
            if not c["allowed"]:
                problems.append("allowed_paths 为空")
            for rel in c["allowed"] + c["forbidden"]:
                if not (ROOT / rel.strip("/")).exists():
                    problems.append(f"边界路径不存在: {rel}")
        if c["status"] == "doing" and len(c["assignees"]) == 1:
            doing_by.setdefault(c["assignees"][0], []).append(c["name"])
        if problems:
            ok = False
            print(f"[任务卡] {c['name']}:")
            for pr in problems:
                print(f"  - {pr}")
    for who, names in doing_by.items():
        if len(names) > 1:
            ok = False
            print(f"[任务卡] 认领冲突：{who} 同时持有多张 doing 卡（一 harness 一张）:")
            for n in names:
                print(f"  - {n}")
    if ok:
        print(f"[任务卡] 通过（{len(cards)} 张）")
    return ok


def git_changed_files():
    try:
        out = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=ROOT, capture_output=True, text=True, check=True,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    files = []
    for line in out.splitlines():
        if len(line) > 3:
            rel = line[3:].strip().strip('"')
            rel = rel.split(" -> ")[-1]  # rename 取新名
            files.append(rel.replace("\\", "/"))
    return files


def path_covered(rel: str, prefixes):
    rel = rel.rstrip("/")
    for pre in prefixes:
        pre = str(pre).strip().rstrip("/")
        if not pre:
            continue
        if rel == pre or rel.startswith(pre + "/") or pre == ".":
            return True
    return False


def check_diff(cards):
    changed = git_changed_files()
    if changed is None:
        print("[改动挂卡] 跳过（不是 git 仓库或 git 不可用）")
        return True
    if not changed:
        print("[改动挂卡] 通过（工作区干净）")
        return True
    ok = True
    for rel in changed:
        covering = [c for c in cards if path_covered(rel, c["allowed"])]
        if not covering:
            ok = False
            print(f"[改动挂卡] 改动未挂任何任务卡: {rel}")
            continue
        for c in covering:
            if path_covered(rel, c["forbidden"]):
                ok = False
                print(f"[改动挂卡] {rel} 命中 {c['name']} 的 forbidden_paths")
            if c["status"] in ("todo", ""):
                ok = False
                print(f"[改动挂卡] {rel} 挂在 {c['name']}，但该卡仍为 todo（应先认领取 doing）")
    if ok:
        print("[改动挂卡] 通过")
    return ok


def check_stale(cards):
    """advisory：只提示，不影响退出码（不拦截提交）。"""
    now = datetime.now()
    stale = []
    for c in cards:
        if c["status"] not in ("doing", "review"):
            continue
        updated = str(c["meta"].get("updated_date", "")).strip()
        if not updated:
            stale.append((c["name"], "缺 updated_date"))
            continue
        ts = None
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                ts = datetime.strptime(updated[:len(fmt) + 2].strip(), fmt)
                break
            except ValueError:
                continue
        if ts is None:
            stale.append((c["name"], f"updated_date 无法解析: {updated}"))
            continue
        hours = (now - ts).total_seconds() / 3600
        if hours > STALE_HOURS:
            stale.append((c["name"], f"已约 {hours:.0f}h 无更新（> {STALE_HOURS}h，integrator 可改派）"))
    if stale:
        print(f"[stale] 提示（不拦截提交）: {len(stale)} 张卡疑似僵死")
        for name, why in stale:
            print(f"  - {name}: {why}")
    else:
        print("[stale] 无僵死卡")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--names", action="store_true")
    ap.add_argument("--tasks", action="store_true")
    ap.add_argument("--diff", action="store_true")
    ap.add_argument("--stale", action="store_true")
    args = ap.parse_args()
    run_all = not (args.names or args.tasks or args.diff or args.stale)

    tasks_dir, columns = load_config()
    cards = load_cards(tasks_dir)

    ok = True
    if run_all or args.names:
        ok &= check_names()
    if run_all or args.tasks:
        ok &= check_tasks(cards, columns)
    if run_all or args.diff:
        ok &= check_diff(cards)
    if run_all or args.stale:
        check_stale(cards)  # advisory
    if run_all:
        print("\n结论:", "全部通过 ✓" if ok else "存在违规 ✗（见上）")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
