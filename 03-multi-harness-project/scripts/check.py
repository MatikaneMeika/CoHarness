#!/usr/bin/env python3
"""仓库健康检查 v2：命名规范、Backlog 任务卡、越权改动、stale 提示、认领冲突。

任务卡由 Backlog.md 管理在 backlog/tasks/（或 backlog.config.yml 指定目录），
卡片格式约定见 .agent/tasks/CARD-CONVENTION.md。

用法（在项目根目录执行）:
    python scripts/check.py               # 全部检查（stale 仅提示，不影响退出码）
    python scripts/check.py --names       # 仅命名规范
    python scripts/check.py --tasks       # 仅任务卡格式 / 边界节 / 认领冲突
    python scripts/check.py --diff        # 仅改动挂卡（判本次提交暂存的改动，需要 git）
    python scripts/check.py --against REF # 仅改动挂卡（判 REF...HEAD，供 CI 使用）
    python scripts/check.py --stale       # 仅 stale 卡报告（advisory）

退出码：0 = 通过；1 = 存在违规（stale 提示不算违规，不拦截提交）。
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta
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
# 自授权改动的固定路径（卡片文件按目录判定，见 is_self_authorized）
SELF_AUTHORIZED = (".agent/improvements.md",)


def _read_text(p: Path):
    try: return p.read_text(encoding="utf-8")
    except OSError: return None


def _utf8_streams():
    """中文提示在 cp936/gbk 控制台下要先保证自己可读：stdout 与 stderr 一起管。"""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


class CardFormatError(Exception):
    """卡片用了 CARD-CONVENTION 之外的写法：宁可不解析，也不静默给出错的值。"""


_PENDING = object()  # `key:` 后面空着，是列表还是空值要等下一行才定
_SUBSET = "只认扁平写法：`key: 值`、`key: [a, b]`、`key:` 下缩进 `- 项`"


def _origin(path):
    try:
        return Path(path).relative_to(ROOT).as_posix()
    except ValueError:
        return Path(path).as_posix()


def _strip_comment(value: str):
    """去行尾注释；引号里的 # 不算注释。"""
    v = value.strip()
    if v[:1] in ("\"", "'"):
        close = v.find(v[0], 1)
        if close != -1:
            return v[: close + 1]
    return re.split(r"\s+#", v)[0].strip()


def _unquote(value: str):
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def _scalar(value: str, origin, lineno):
    v = _strip_comment(value)
    if not v: return ""
    head = v[0]
    if head in "|>":
        raise CardFormatError(f"{origin}:{lineno} 块标量 '{head}' 不支持，{_SUBSET}")
    if head == "{":
        raise CardFormatError(f"{origin}:{lineno} 行内 map 写法不支持，{_SUBSET}")
    if head in "&*":
        raise CardFormatError(f"{origin}:{lineno} 锚点/别名不支持，{_SUBSET}")
    if head == "[":
        raise CardFormatError(f"{origin}:{lineno} 列表项不能再套一层 []，{_SUBSET}")
    quoted = len(v) > 1 and v[0] in "\"'" and v[-1] == v[0]
    if not quoted and ": " in v:
        raise CardFormatError(f"{origin}:{lineno} 值里有 ': '，整个值要用引号包起来")
    return _unquote(v)


def _inline_list(value: str, origin, lineno):
    inner = _strip_comment(value)[1:-1].strip()
    items = []
    for part in inner.split(","):
        part = part.strip()
        if not part:
            continue
        if part[0] in "[{":
            raise CardFormatError(f"{origin}:{lineno} 行内列表里又套了一层，{_SUBSET}")
        items.append(_unquote(part))
    return items


def _parse_pairs(lines, origin, start, end_marker, lineno0=1):
    """按 CARD-CONVENTION 的子集读 `key: value`，返回 (meta, 结束行偏移或 None)。

    frontmatter 与卡体 '## 边界' 节共用这一个 tokenizer：两处各写一遍迟早漂。
    backlog.config.yml 是别人家的文件，仍走下面的宽容解析，不进这里。
    """
    meta, pending, awaiting = {}, None, False
    for offset in range(start, len(lines)):
        raw = lines[offset]
        lineno = lineno0 + offset
        if end_marker is not None and raw.strip() == end_marker:
            return meta, offset
        if not raw.strip():
            continue
        lead = raw[: len(raw) - len(raw.lstrip())]
        if "\t" in lead:
            raise CardFormatError(f"{origin}:{lineno} 用制表符缩进，改成空格")
        stripped = raw.strip()
        if stripped.startswith("#"):
            # 单个 # 当 YAML 注释；'## ' 往上才是卡体的节标题，多半说明 '---' 忘了闭合
            if end_marker is not None and re.match(r"^#{2,6}\s", stripped):
                return meta, None
            continue
        if stripped.startswith("-"):
            if not stripped.startswith("- "):
                raise CardFormatError(f"{origin}:{lineno} '-项' 少空格：写成 '- 项'")
            if pending is None:
                raise CardFormatError(f"{origin}:{lineno} '- 项' 上面没有可挂靠的 key:")
            if not awaiting:
                raise CardFormatError(f"{origin}:{lineno} '{pending}' 已经有值，'- 项' 接不到它下面")
            if meta[pending] is _PENDING:
                meta[pending] = []
            item = stripped[2:]
            if re.match(r"^[\w.-]+:(\s|$)", item):
                raise CardFormatError(f"{origin}:{lineno} 列表项里又开了键（嵌套结构），{_SUBSET}")
            meta[pending].append(_scalar(item, origin, lineno))
            continue
        if lead:
            why = "键下又套了键（嵌套 map）" if ":" in stripped else "缩进的续行属于多行值"
            raise CardFormatError(f"{origin}:{lineno} {why}，{_SUBSET}")
        m = re.match(r"^([\w-]+):(.*)$", stripped)
        if not m:
            raise CardFormatError(f"{origin}:{lineno} 看不懂的行，{_SUBSET}")
        key, value = m.group(1), _strip_comment(m.group(2))
        if key in meta:
            raise CardFormatError(f"{origin}:{lineno} 重复键 '{key}'，后写的会静默盖掉前面的")
        pending = key
        if value == "":
            meta[key] = _PENDING
            awaiting = True
        elif value.startswith("[") and value.endswith("]"):
            meta[key] = _inline_list(value, origin, lineno)
            awaiting = False
        elif value.startswith("["):
            raise CardFormatError(f"{origin}:{lineno} 行内列表缺 ']'，{_SUBSET}")
        else:
            meta[key] = _scalar(value, origin, lineno)
            awaiting = False
    return meta, None


def _finish(meta):
    return {k: ("" if v is _PENDING else v) for k, v in meta.items()}


def parse_frontmatter(path: Path, text=None):
    """解析 Backlog 卡的 frontmatter；子集外的写法抛 CardFormatError 并带行号。"""
    if text is None:
        text = path.read_text(encoding="utf-8")
    if text.startswith("\ufeff"):
        raise CardFormatError(f"{_origin(path)}:1 文件带 BOM，请另存为无 BOM 的 UTF-8")
    if not text.startswith("---"):
        return None, text
    lines = text.splitlines()
    meta, end = _parse_pairs(lines, _origin(path), 1, "---")
    if end is None:
        raise CardFormatError(
            f"{_origin(path)}:1 frontmatter 没有结束的 '---'，后面整段会被当成正文")
    return _finish(meta), "\n".join(lines[end + 1:])


def _yaml_scalar(text: str, key: str):
    m = re.search(rf"^{key}:\s*(.+?)\s*(#.*)?$", text, re.M)
    return m.group(1).strip().strip('"').strip("'") if m else None


def _yaml_list_under(text: str, key: str):
    """取某 key 下的 '- item' 列表或行内 [a, b]。只用于 backlog 自己的配置文件（宽容）。"""
    items, in_block = [], False
    for line in text.splitlines():
        m = re.match(rf"^\s*{key}:\s*(.*)$", line)
        if m:
            inline = m.group(1).strip()
            if inline.startswith("[") and inline.endswith("]"):
                inner = inline[1:-1].strip()
                return [x.strip().strip("\"'") for x in inner.split(",") if x.strip()]
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
            # 真 Backlog.md 1.53.0 用的键是 statuses；columns 是早期猜测的键名，留着兼容
            cols = _yaml_list_under(t, "statuses") or _yaml_list_under(t, "columns")
            if cols:
                columns = [c.strip().lower() for c in cols]
            break
    return ROOT / dirname / "tasks", columns


def parse_boundary(body: str, origin, body_first_line=1):
    """提取卡体 '## 边界' 节的 allowed_paths / forbidden_paths（与 frontmatter 同一套子集）。"""
    m = re.search(r"^##\s*边界\s*$", body, re.M)
    if not m: return [], [], False
    rest = body[m.end():]
    nxt = re.search(r"^##\s+", rest, re.M)
    section = rest[: nxt.start()] if nxt else rest
    lineno0 = body_first_line + body[: m.end()].count("\n")
    pairs, _ = _parse_pairs(section.splitlines(), origin, 0, None, lineno0=lineno0)
    pairs = _finish(pairs)

    def as_list(key):
        val = pairs.get(key, [])
        if val in ("", None):
            return []
        return val if isinstance(val, list) else [str(val)]

    return as_list("allowed_paths"), as_list("forbidden_paths"), True


def load_cards(tasks_dir: Path):
    """读卡目录。返回 (卡片, 格式错误) —— 写错的卡绝不静默跳过或给错值。"""
    cards, errors = [], []
    if not tasks_dir.exists(): return cards, errors
    for p in sorted(tasks_dir.glob("*.md")):
        text = _read_text(p)
        if text is None:
            continue
        if not (text.startswith("---") or text.startswith("\ufeff---")):
            continue  # 不是卡片（如目录说明 README）
        try:
            meta, body = parse_frontmatter(p, text)
            if not meta or "id" not in meta:
                continue
            lines = text.splitlines()
            # 闭合行按 tokenizer 的口径找（strip 后相等）：lines.index 要求逐字节相等，
            # " --- " 会被上面放行、在这里炸成 ValueError 把整个 check 崩掉
            close = next((i for i, l in enumerate(lines) if i and l.strip() == "---"), None)
            if close is None:
                raise CardFormatError(f"{_origin(p)}:1 frontmatter 没有结束的 '---'")
            body_first_line = close + 2  # 卡体首行的 1-based 行号
            allowed, forbidden, has_boundary = parse_boundary(
                body, _origin(p), body_first_line=body_first_line)
        except CardFormatError as e:
            errors.append(str(e))
            continue
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
            "body": body,
        })
    return cards, errors


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


def norm_prefix(p):
    return str(p).strip().rstrip("/") or "."


def boundary_intersection(allowed_a, allowed_b):
    """两卡 allowed_paths 的前缀交集（AGENTS.md 所有权表与 CARD-CONVENTION 规则 3 的承诺）。"""
    hits = []
    for x in allowed_a:
        for y in allowed_b:
            xn, yn = norm_prefix(x), norm_prefix(y)
            if xn == yn or xn == "." or yn == "." or xn.startswith(yn + "/") or yn.startswith(xn + "/"):
                hits.append(f"{xn} × {yn}")
    return hits


def check_tasks(cards, columns, card_errors=()):
    ok = True
    for err in card_errors:
        ok = False
        print(f"[卡格式] {err}")
    if not cards:
        if minimal_mode():
            print("[任务卡] 最小模式：无 backlog/tasks，卡片执法关闭（清单在 TODO.md）")
            return True
        print("[任务卡] 无任务卡")
        return True if not card_errors else False
    doing_by = {}
    for c in cards:
        problems = []
        if c["status"] not in columns:
            problems.append(f"status 非法: '{c['status']}'（合法列: {', '.join(columns)}）")
        if not str(c["meta"].get("title", "")).strip():
            problems.append("title 为空")
        if c["status"] in ("doing", "review") and not c["assignees"]:
            problems.append(f"status={c['status']} 但未认领（assignee 为空）")
        updated = str(c["meta"].get("updated_date", "")).strip()
        if (ts := _parse_updated(updated)) and ts > datetime.now() + timedelta(minutes=10):
            problems.append(f"updated_date 超出本地当前时间 10 分钟: {updated}")
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
        body = c.get("body") or ""
        if "## 审阅意见" in body:  # 三行契约（借鉴 orca 的 diff 批注格式）：条目 File: 开头，续行只允许 Lines:/Comment:
            seen_entry = has_unchecked = False
            for raw in body.split("## 审阅意见", 1)[1].split("\n## ", 1)[0].splitlines():
                s = raw.strip()
                if not s:
                    continue
                m = re.match(r"^[-*]\s*\[([ xX])\]\s*(.*)$", s)
                if m:
                    seen_entry, has_unchecked = True, has_unchecked or m.group(1).lower() != "x"
                    if not m.group(2).startswith("File:"):
                        problems.append(f"审阅意见条目必须以 `File: <路径>` 开头: {s[:40]}")
                elif not seen_entry or not (s.startswith("Lines:") or s.startswith("Comment:")):
                    problems.append(f"审阅意见续行只允许 `Lines:` / `Comment:`: {s[:40]}")
            if has_unchecked and c["status"] != "doing": problems.append("审阅意见有未勾选项：卡必须退回 doing；review/done 不得带未勾选项")
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
    onAir = [c for c in cards if c["status"] in ("doing", "review")]
    for i, a in enumerate(onAir):
        for b in onAir[i + 1:]:
            hits = boundary_intersection(a["allowed"], b["allowed"])
            if hits:
                ok = False
                print(f"[任务卡] 边界交集不得并行：{a['name']} × {b['name']} → "
                      f"{', '.join(sorted(set(hits)))}")
    if ok:
        print(f"[任务卡] 通过（{len(cards)} 张）")
    return ok


def _git_out(args):
    """跑 git，返回 (是否成功, stdout)。git 不可用或不在仓库内时成功位为 False。"""
    try:
        r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=60, shell=False)
    except (OSError, subprocess.TimeoutExpired):
        return False, ""
    return r.returncode == 0, (r.stdout or "")


def _name_status(args):
    """把 git --name-status 输出拆成 (新路径, 全路径)；重命名旧路径也进全路径。"""
    ok, out = _git_out(args)
    if not ok:
        return None
    fresh, every = [], []
    for ln in out.splitlines():
        parts = ln.split("\t")
        if len(parts) < 2 or not parts[1].strip():
            continue
        if parts[0].startswith("R") and len(parts) >= 3:
            fresh.append(parts[2].replace("\\", "/"))
            every += [parts[1].replace("\\", "/"), parts[2].replace("\\", "/")]
        else:
            p = parts[1].replace("\\", "/")
            fresh.append(p)
            every.append(p)
    return fresh, every


def staged_files():
    """本次提交将纳入的改动，返回 (新路径列表, 全路径列表)。

    判据必须是暂存集而不是工作区：`git status` 会把没 add 的文件、以及被折叠成
    目录的未跟踪项都算进来，全新实例化的项目连第一个提交都拦掉。
    挂卡判"新路径"（重命名按新路径归属）；所有权核对拿"全路径"——重命名的旧路径
    也盯，改个名逃不出所有权表。
    """
    return _name_status(["-c", "core.quotepath=false", "diff", "--cached",
                        "--name-status", "--no-ext-diff", "-M"])


def against_files(ref):
    """CI 形态的变更集：`<ref>...HEAD`；ref 或合并基缺失都响亮失败，不按空集全绿。"""
    ok, _ = _git_out(["rev-parse", "--verify", "-q", f"{ref}^{{commit}}"])
    if not ok:
        print(f"[改动挂卡] 基线不存在或不是 commit: {ref}")
        return None
    ok, _ = _git_out(["merge-base", ref, "HEAD"])
    if not ok:
        print(f"[改动挂卡] 基线 {ref} 与 HEAD 没有合并基，无法计算变更集")
        return None
    changed = _name_status(["-c", "core.quotepath=false", "diff", "--name-status",
                            "--no-ext-diff", "-M", f"{ref}...HEAD"])
    if changed is None:
        print(f"[改动挂卡] 无法读取 {ref}...HEAD 的变更集")
    return changed


def has_commits():
    ok, out = _git_out(["rev-parse", "--verify", "-q", "HEAD"])
    return ok and bool(out.strip())


def path_covered(rel: str, prefixes):
    rel = rel.rstrip("/")
    for pre in prefixes:
        pre = str(pre).strip().rstrip("/")
        if not pre:
            continue
        if rel == pre or rel.startswith(pre + "/") or pre == ".":
            return True
    return False


def is_self_authorized(rel, tasks_rel):
    """卡片本身与改进登记表不需要"挂卡"：改卡就是认领动作，登记是全局禁令第 7 条要求的动作。

    并发演练实测：要求它们挂卡会让认领与登记无路可走（唯一的授权来源是常驻卡，
    而持常驻卡再领实现卡会撞"一 harness 一张 doing 卡"，退回常驻卡又卡在 todo 上）。
    这两类改动仍受 --tasks 的全局纪律约束：一卡一 assignee、一 harness 一张 doing、缺边界节即违规。
    """
    return rel in SELF_AUTHORIZED or (
        tasks_rel and rel.startswith(tasks_rel + "/") and rel.endswith(".md"))


def minimal_mode():
    """`wsc init --minimal` 的形态：没有 backlog/tasks，任务清单在 TODO.md。

    卡片层执法（改动挂卡、认领冲突、边界交集）都以任务卡为前提，没卡就全量报违规等于
    把项目锁死；所以这里显式关闭并说明关闭了什么——AGENTS.md 的「最小模式」节写着同样的话。
    命名规范、卡格式（有卡才判）、登记管线与钩子本身不受影响。
    """
    return not (ROOT / "backlog" / "tasks").is_dir() and (ROOT / "TODO.md").exists()


def ownership_rows():
    """AGENTS.md 单写者所有权表里**能机械核对**的行：(路径前缀, 角色) + 判不了的行数。

    裁决句说"以表为准、扩权先改表"，但表里写者是角色、卡上 assignee 是 harness 标识
    （"同一会话可身兼多角"），机械桥梁只有卡上的 `role:` 标签。所以只判"具体路径 +
    写者恰是角色一览里一个角色"的行；模板行与散文行判不了，报数留给审核人——宁少判，不诬判。
    """
    text = _read_text(ROOT / "AGENTS.md")
    if text is None: return [], 0
    roles, cands, section = set(), [], ""
    for ln in text.splitlines():
        s = ln.strip()
        if s.startswith("## "):
            section = s[3:].strip()
        elif s.startswith("|") and (section == "角色一览"
                                    or section.startswith("单写者所有权表")):
            cells = [c.strip().strip("`") for c in s.strip("|").split("|")]
            if not cells or not cells[0] or set(cells[0]) == {"-"}:
                continue
            if section == "角色一览" and cells[0] != "角色" and "<" not in cells[0]:
                roles.add(cells[0])
            elif section.startswith("单写者所有权表") and len(cells) >= 2 and cells[0] != "路径":
                cands.append(cells)
    rows, opaque = [], 0
    for cells in cands:
        named = [t for t in re.findall(r"[A-Za-z][\w-]*", cells[1]) if t in roles]
        if "<" in cells[0] or re.search(r"[^\w./-]", cells[0]) or len(named) != 1:
            opaque += 1
        else:
            rows.append((norm_prefix(cells[0]), named[0]))
    return rows, opaque


def _owning_row(rel, rows):
    """rel 命中的最长所有权前缀行；不在任何管辖路径下就 None。"""
    best = None
    for path, role in rows:
        if (rel == path or rel.startswith(path + "/")) and (best is None or len(path) > len(best[0])):
            best = (path, role)
    return best


def _role_declared(rel, rows, cards):
    """该路径被表的"可判"行管辖时，覆盖它的在做卡必须带 role: 标签（身兼多角由卡声明）。"""
    row = _owning_row(rel, rows)
    if not row: return True
    act = [c for c in cards if c["status"] in ("doing", "review")
           and path_covered(rel, c["allowed"])]
    return any(f"role:{row[1]}" in str(x) for c in act
               for x in (c["meta"].get("labels") or []))


def _judge_changes(cards, tasks_rel, fresh, every):
    rows, opaque = ownership_rows()
    ok, governed = True, 0
    for rel in every:
        if is_self_authorized(rel, tasks_rel):
            continue
        if rel in fresh:
            covering = [c for c in cards if path_covered(rel, c["allowed"])]
            if not covering:
                ok = False
                print(f"[改动挂卡] 改动未挂任何任务卡: {rel}")
                continue
            blocked = [c for c in covering if path_covered(rel, c["forbidden"])]
            if blocked:
                # 禁改优先：任何一张卡点名禁止，别的卡的 allowed_paths 不能把它绕开
                ok = False
                print(f"[改动挂卡] {rel} 命中 {blocked[0]['name']} 的 forbidden_paths")
                continue
            active = [c for c in covering if c["status"] in ("doing", "review")]
            if not active:
                ok = False
                # 以前逢 todo 就报，会让重叠边界把已正确认领的一方一起诬告（并发演练 A3）
                print(f"[改动挂卡] {rel} 只被未认领的卡覆盖（{covering[0]['name']} 仍为 "
                      f"{covering[0]['status']}，应先认领取 doing）")
                if "/evidence/" in rel or rel.startswith("evidence/"):
                    print(f"[改动挂卡]   ↑ 疑似跑测试被动改写的证据（I-002）：用 "
                          f"`git restore --source=HEAD --staged --worktree {rel}` 还原")
                continue
            governed += 1 if _owning_row(rel, rows) else 0
        elif not _role_declared(rel, rows, cards):
            ok = False
            print(f"[所有权] 扩权: {rel}（重命名旧路径）按所有权表只归 "
                  f"{_owning_row(rel, rows)[1]} 写——以表为准，扩权先改表")
            continue
        if rel in fresh and not _role_declared(rel, rows, cards):
            ok = False
            print(f"[所有权] 扩权: {rel} 按所有权表只归 {_owning_row(rel, rows)[1]} 写"
                  f"（在做的卡没有对应 role: 标签）——以表为准，扩权先改表")
    return ok, governed, rows, opaque


def check_diff(cards, tasks_rel="", against=None):
    if against is not None:
        changed = against_files(against)
        source = f"{against}...HEAD"
        if changed is None:
            return False
    else:
        changed = staged_files()
        source = "暂存区"
        if changed is None:
            print("[改动挂卡] 跳过（不是 git 仓库或 git 不可用）")
            return True
    if minimal_mode() and not cards:
        print("[改动挂卡] 最小模式关闭（无任务卡可挂；清单见 TODO.md）")
        return True
    if not has_commits():
        print("[改动挂卡] 首次入库（仓库还没有提交）：不执法；此后每次提交都必须在卡内")
        return True
    fresh, every = changed
    if not fresh:
        print(f"[改动挂卡] 通过（{source}没有改动）")
        return True
    ok, governed, rows, opaque = _judge_changes(cards, tasks_rel, fresh, every)
    if ok:
        print("[改动挂卡] 通过")
    print(f"[所有权] 核对 {governed} 个路径 × {len(rows)} 行可判；"
          f"{opaque} 行是模板/散文写者，留给审核人")
    return ok


def _parse_updated(text):
    """updated_date 整串按候选格式解析，容忍秒与 ISO 的 T 分隔——旧实现按格式串长度切输入，
    空格分隔碰巧切得对，T 分隔会静默退化成"只按日期算"（stale 判断最多差 24 小时）。"""
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M",
                "%Y-%m-%d"):
        try:
            return datetime.strptime(str(text).strip(), fmt)
        except ValueError:
            continue
    return None


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
        ts = _parse_updated(updated)
        if ts is None:
            stale.append((c["name"], f"updated_date 无法解析: {updated}"))
            continue
        hours = (now - ts).total_seconds() / 3600
        if hours > STALE_HOURS:
            stale.append((c["name"], f"已约 {hours:.0f}h 无更新（> {STALE_HOURS}h；stale 是提示不是改派授权）"))
    if stale:
        print(f"[stale] 提示（不拦截提交）: {len(stale)} 张卡疑似僵死")
        for name, why in stale:
            print(f"  - {name}: {why}")
    else:
        print("[stale] 无僵死卡")


def check_hints(cards):
    """advisory 提示（不拦截提交，不影响退出码；借鉴 orca 的显式 outcome 契约）：
    ① done/review 卡的交接说明缺 `结果:` 首行——接手方没有会话记忆，结果行是机器可扫的收工口径；
    ② 验收清单项不含反引号命令/路径/测试名——可能不可验证。格式执法仍在卡格式声明子集层，这里只提示。"""
    hints = []
    for c in cards:
        body = c.get("body") or ""
        if c["status"] in ("done", "review") and "## 交接说明" in body:
            sec = body.split("## 交接说明", 1)[1].split("\n## ", 1)[0]
            lines = [l.strip() for l in sec.splitlines() if l.strip()]
            if lines and not lines[0].startswith("结果:"):
                hints.append(f"{c['name']}: 交接说明缺首行 `结果: 成功|失败|部分`")
        if "## 验收清单" in body:
            sec = body.split("## 验收清单", 1)[1].split("\n## ", 1)[0]
            n = 0
            for line in sec.splitlines():
                m = re.match(r"^\s*[-*]\s*\[([ xX])\]\s*(.*)$", line)
                if not m:
                    continue
                n += 1
                if "`" not in m.group(2):
                    hints.append(f"{c['name']}: 验收清单第 {n} 项不含可观察证据（反引号命令/路径/测试名）")
    if hints:
        print(f"[提示] advisory（不拦截提交）: {len(hints)} 条")
        for h in hints:
            print(f"  - {h}")
    else:
        print("[提示] 无")


def _harness_id():
    """这次执行算在谁头上：环境变量优先，其次 git 身份，都没有就 unknown。"""
    if env := os.environ.get("COHARNESS_HARNESS", "").strip(): return env
    ok, name = _git_out(["config", "user.name"])
    return name.strip() if ok and name.strip() else "unknown"


def _bound_card():
    """优先读分支绑定：branch.<branch>.coharness-card = <卡文件名>。"""
    ok, branch = _git_out(["rev-parse", "--abbrev-ref", "HEAD"])
    branch = branch.strip()
    if not ok or not branch or branch == "HEAD": return None
    ok, value = _git_out(["config", "--get", f"branch.{branch}.coharness-card"])
    return Path(value.strip()).stem if ok and value.strip() else None

TELEMETRY_MAX_LINES = 2000   # 记账上限：stats/面板每次都读全量，无界增长会拖慢展示面


def record_run(checks, rc, my_card, started):
    """把本次执行追加进项目内 .agent/telemetry.jsonl：本地、零上传、可关。

    关掉用 `--no-track` 或环境变量 COHARNESS_NO_TRACK=1；删掉那个文件（它已在 .gitignore 里）
    就回到零持久化痕迹。写失败只提示一行，不影响检查结论——执法不能因为记账而失效。
    """
    if os.environ.get("COHARNESS_NO_TRACK") or "--no-track" in sys.argv:
        return
    entry = {"ts": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
             "harness": _harness_id(),
             "checks": checks, "rc": rc, "card": my_card,
             "ms": int((time.monotonic() - started) * 1000)}
    f = ROOT / ".agent" / "telemetry.jsonl"
    try:
        f.parent.mkdir(parents=True, exist_ok=True)
        with open(f, "a", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        # 记账要有界：超过上限就截到最近一半，最新那行必须留下（它是"最近一次 check"的数据源）
        lines = f.read_text(encoding="utf-8").splitlines()
        if len(lines) > TELEMETRY_MAX_LINES:
            f.write_text("\n".join(lines[-(TELEMETRY_MAX_LINES // 2):]) + "\n",
                         encoding="utf-8", newline="\n")
    except (OSError, UnicodeDecodeError) as e:
        print(f"[遥测] 写入 {f} 失败（不影响检查结论）: {e}", file=sys.stderr)


def main():
    _utf8_streams()
    ap = argparse.ArgumentParser()
    ap.add_argument("--names", action="store_true")
    ap.add_argument("--tasks", action="store_true")
    ap.add_argument("--diff", action="store_true")
    ap.add_argument("--stale", action="store_true")
    ap.add_argument("--against", metavar="REF", help="CI：检查 <REF>...HEAD 的改动挂卡")
    ap.add_argument("--card", help="本次执行归属的卡号；缺省优先读分支绑定")
    ap.add_argument("--no-track", action="store_true", help="这次执行不写 .agent/telemetry.jsonl")
    args = ap.parse_args()
    run_all = not (args.names or args.tasks or args.diff or args.stale or args.against is not None)
    started = time.monotonic()

    tasks_dir, columns = load_config()
    cards, card_errors = load_cards(tasks_dir)
    try:
        tasks_rel = tasks_dir.relative_to(ROOT).as_posix()
    except ValueError:
        tasks_rel = ""

    ran = {}
    ok = True
    if run_all or args.names:
        ran["names"] = check_names()
        ok &= ran["names"]
    if run_all or args.tasks:
        ran["tasks"] = check_tasks(cards, columns, card_errors)
        ok &= ran["tasks"]
    if run_all or args.diff or args.against is not None:
        ran["diff"] = check_diff(cards, tasks_rel, args.against)
        ok &= ran["diff"]
    if run_all or args.stale:
        check_stale(cards)  # advisory
        check_hints(cards)  # advisory（结果行 / 可观察验收）
        ran["stale"] = True
    if run_all:
        print("\n结论:", "全部通过 ✓" if ok else "存在违规 ✗（见上）")
    my_card = args.card or _bound_card() or next((
        c["meta"].get("id") for c in cards if c["status"] == "doing" and
        _harness_id() in c["assignees"]), None)
    record_run(ran, 0 if ok else 1, my_card, started)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
