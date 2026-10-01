#!/usr/bin/env python3
"""maintain.py — 已实例化项目的维护面工具（装机指纹、模式迁移、只读体检）。

分层理由（ADR-10）：`wsc.py` 是分发面——curl 单文件、下游天天用，所以命令表要小；
`evolve.py` 审的是骨架本体；本文件管的是**已经装出去的项目**：它们随骨架漂了没有、
钩子还在不在、能不能从 v1 升到 v2。这三件事都只在维护时发生，不该挤进下游日常命令表。
纯标准库、零网络；对项目的写只有两处：`.agent/skeleton.lock` 与 `migrate --yes` 的显式升级。

用法:
    python maintain.py lock    <项目>              # 写/刷新装机指纹（骨架名 + 本体 commit + schema）
    python maintain.py migrate <项目> [--yes]      # 默认 dry-run 出补丁；--yes 先建备份分支再落盘
    python maintain.py audit   <项目>              # 只读体检：钩子/漂移/合成态合法性，不写任何东西
    python maintain.py schema                      # 打印当前 schema 版本与升级步骤
"""
import argparse
import hashlib
import json
import re
import shutil
import tempfile
import sys
from datetime import datetime
from pathlib import Path

try:                      # 装成包时（pip install coharness）走相对导入
    from . import wsc
except ImportError:       # curl 单文件 / clone 后直接跑脚本时的形状
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import wsc

ROOT = wsc.ROOT
_run = wsc._run
SCHEMA = 4
CHECK_CAPABILITIES = ("审阅意见", "结果:", "可观察", "ownership_rows", "_role_declared")
LOCK_NAME = ".agent/skeleton.lock"
TELEMETRY_IGNORE = ".agent/telemetry.jsonl"


def now_stamp():
    return f"{datetime.now():%Y%m%d-%H%M%S}"


def read_lock(project: Path):
    f = project / LOCK_NAME
    if not f.exists():
        return None
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except ValueError:
        return {"_坏掉": f"无法解析 {f}"}


def cmd_lock(args):
    project = Path(args.project).resolve()
    skeleton = _guess_skeleton(project)
    if skeleton is None:
        sys.exit(f"[lock] {project} 里找不到 AGENTS.md，看不出是哪套骨架")
    rev = wsc._git_field(["git", "rev-parse", "--short", "HEAD"], ROOT)
    # 指纹里不写本机绝对路径：它是要提交进项目仓库的共享事实（队友与 CI 都要能看出 schema 漂了没）
    entry = {"skeleton": skeleton.name, "skeleton_commit": rev[1] if rev[0] == "ok" else "",
             "schema": SCHEMA,
             "adapters": _adapters_present(project), "locked_at": f"{datetime.now():%Y-%m-%d %H:%M}",
             "check_sha256": _sha(project / "scripts" / "check.py")}
    f = project / LOCK_NAME
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(entry, ensure_ascii=False, indent=1) + "\n",
                 encoding="utf-8", newline="\n")
    print(f"[lock] 已写 {f}（这份指纹可以提交进项目仓库：不含本机路径）")
    for k in ("skeleton", "skeleton_commit", "schema", "check_sha256"):
        print(f"  {k} = {entry[k]}")


def _sha(path: Path):
    """文本先归一行尾再哈希；二进制保持原始字节。"""
    if not path.exists():
        return ""
    raw = path.read_bytes()
    try:
        raw = raw.decode("utf-8").replace("\r\n", "\n").encode("utf-8")
    except UnicodeDecodeError:
        pass
    return hashlib.sha256(raw).hexdigest()[:12]


def _guess_skeleton(project: Path):
    """按 AGENTS.md 的标题反推骨架名（装机时标题里的占位符已被填掉，只能比对结构）。"""
    lock = read_lock(project) or {}
    wanted = lock.get("skeleton")
    for sk in wsc.discover_skeletons():
        if wanted and sk.name == wanted:
            return sk
    agents = project / "AGENTS.md"
    if not agents.exists():
        return None
    text = agents.read_text(encoding="utf-8")
    for sk in wsc.discover_skeletons():
        src = sk / "AGENTS.md"
        if not src.exists():
            continue
        first_src = src.read_text(encoding="utf-8").splitlines()[0]
        first_dst = text.splitlines()[0]
        # 标题里的 {{PROJECT_NAME}} 被填过，比较去掉占位符后的骨架特征
        tail = re.sub(r"^#\s*\S+\s*[—-]\s*", "", first_src)
        if tail and tail in first_dst:
            return sk
    return None


def _adapters_present(project: Path):
    cands = {"CLAUDE.md": "claude", "GEMINI.md": "gemini", ".cursor/rules": "cursor",
             ".github/copilot-instructions.md": "copilot", ".windsurf/rules": "windsurf"}
    return sorted(v for k, v in cands.items() if (project / k).exists())


def cmd_schema(_args):
    print(f"骨架 schema 版本：{SCHEMA}")
    for step in sorted(UPGRADES):
        print(f"  v{step} -> v{step + 1}: {UPGRADES[step][0]}")
    print("（装机指纹记在项目的 .agent/skeleton.lock；migrate 按 schema 差值决定跑哪几步）")


def up_ignore_telemetry(project: Path, apply_changes):
    """.gitignore 里补上本地记账文件，否则每次 check 都把工作区弄脏。"""
    f = project / ".gitignore"
    text = f.read_text(encoding="utf-8") if f.exists() else ""
    if TELEMETRY_IGNORE in text:
        return ["已到位：.gitignore 忽略 telemetry.jsonl"]
    if apply_changes:
        f.write_text((text.rstrip() + "\n\n# 本地运行记账（不进版本库）\n" + TELEMETRY_IGNORE + "\n"),
                     encoding="utf-8", newline="\n")
    return [f"{'已追加' if apply_changes else '待追加'}：{f.name} 里补 '{TELEMETRY_IGNORE}'"]


def up_library_paths(project: Path, apply_changes):
    """把散文占位符 `<骨架库>`/`<CoHarness>` 换成本机骨架库路径（命令要能直接复制执行）。"""
    hits = []
    for p in sorted(project.rglob("*.md")):
        text = p.read_text(encoding="utf-8")
        if "<骨架库>" not in text and "<CoHarness>" not in text:
            continue
        hits.append(p.relative_to(project).as_posix())
        if apply_changes:
            new = text.replace("<骨架库>", str(ROOT)).replace("<CoHarness>", str(ROOT))
            p.write_text(new, encoding="utf-8", newline="\n")
    if not hits:
        return ["已到位：文档里的库路径都已代入本机绝对路径"]
    return [f"{'已改写' if apply_changes else '待改写'}："
            f"{', '.join(hits)}（原本写着 <骨架库>/<CoHarness>）"]


def up_claim_line(project: Path, apply_changes):
    """看板节里的认领行升级为首选 `wsc claim`（I-002 的晋升产物）。"""
    f = project / "AGENTS.md"
    if not f.exists():
        return ["跳过：没有 AGENTS.md"]
    text = f.read_text(encoding="utf-8")
    if "wsc.py claim" in text:
        return ["已到位：认领指向 wsc claim"]
    m = re.search(r"(?m)^- 认领 = .*$", text)
    if not m:
        return ["跳过：这一档骨架没有认领条款（单 harness 骨架）"]
    line = (f"- 认领 = `python {ROOT}/wsc.py claim <项目> T-xxx <harness标识>`"
            f"（同步+校验+提交+推送绑成一步，被抢就还原并列出可认领的卡）")
    if apply_changes:
        f.write_text(text.replace(m.group(0), line, 1), encoding="utf-8", newline="\n")
    return [f"{'已改为' if apply_changes else '待改'}：认领条款首选 wsc claim"
            f"（原句：'{m.group(0)[:36]}…'）"]


def up_degrade_section(project: Path, apply_changes):
    """补「降级行为」节：从骨架本体复制该节，缺了才补（W11 的规格化产物）。"""
    f = project / "AGENTS.md"
    if not f.exists():
        return ["跳过：没有 AGENTS.md"]
    text = f.read_text(encoding="utf-8")
    if "## 降级行为" in text:
        return ["已到位：AGENTS.md 有降级行为节"]
    skeleton = _guess_skeleton(project)
    if skeleton is None:
        return ["跳过：认不出骨架来源，无法搬该节"]
    src = (skeleton / "AGENTS.md").read_text(encoding="utf-8")
    if "## 降级行为" not in src:
        return ["跳过：骨架本体也没有该节"]
    section = "## 降级行为" + src.split("## 降级行为", 1)[1]
    section = section.split("\n## ")[0].rstrip() + "\n"
    section = section.replace("{{COHARNESS_LIB}}", str(ROOT))
    if apply_changes:
        f.write_text(text.rstrip() + "\n" + section, encoding="utf-8", newline="\n")
    return [f"{'已补' if apply_changes else '待补'}：从 {skeleton.name} 搬「降级行为」节进 AGENTS.md"]

def up_native_adapters(project: Path, apply_changes):
    """v2→v3：旧单文件适配（.cursorrules / .windsurfrules）换成对应工具的原生目录格式。

    只替换有旧文件的那几家：装机时选过 --adapter 子集的项目，不该被 migrate 塞进它没要的文件。
    """
    replacement = {".cursorrules": "cursor", ".windsurfrules": "windsurf"}
    notes = []
    for old, name in replacement.items():
        f = project / old
        if not f.exists():
            continue
        rel = wsc.ADAPTERS[name][0][0]
        notes.append(f"{'已迁移' if apply_changes else '待迁移'} {old} → {rel}")
        if apply_changes:
            wsc.write_adapters(project, name)
            f.unlink()
    if notes:
        return notes
    have = [rel for _n, rel in wsc.adapter_targets("all") if (project / rel).exists()]
    if have:
        return [f"已到位：{len(have)} 个原生格式指针，无旧单文件残留"]
    return ["跳过：项目里没有适配指针（装机时没要 --adapter，不该凭空生成）"]


def declared_schema(project: Path):
    """从项目 AGENTS.md 的项目卡读声明的骨架 schema；老项目没这行 → 算 1。

    有了它，没装过指纹的项目也能说清自己是哪一版骨架，migrate 不必一律按 v1 猜。
    """
    f = project / "AGENTS.md"
    if not f.exists():
        return None
    m = re.search(r"^\|\s*骨架 schema\s*\|\s*(\d+)\s*\|", f.read_text(encoding="utf-8"), re.M)
    return int(m.group(1)) if m else None


def up_drop_resident_card(project: Path, apply_changes):
    """v1 遗留：常驻规则卡 T-000-board.md。I-001 晋升后它是反模式，留着会诱使人长持它。"""
    f = project / "backlog" / "tasks" / "T-000-board.md"
    if not f.exists():
        return ["已到位：没有常驻规则卡（认领与登记已属自授权改动）"]
    if apply_changes:
        f.unlink()
    return [f"{'已删除' if apply_changes else '待删除'}：{f.relative_to(project).as_posix()}"
            "（常驻卡作废，见 I-001）"]


def up_backlog_statuses(project: Path, apply_changes):
    """v1 遗留：backlog/config.yml 的看板列。真工具默认英文三列，本骨架要四列且键名是 statuses。"""
    f = project / "backlog" / "config.yml"
    if not f.exists():
        return ["跳过：项目里没有 backlog/config.yml（未装 backlog CLI 或最小模式）"]
    text = f.read_text(encoding="utf-8")
    want = "statuses: [todo, doing, review, done]"
    if re.search(r"(?m)^statuses:\s*\[?\s*todo,\s*doing,\s*review,\s*done", text.replace("'", "").replace('"', "")):
        return ["已到位：statuses 已是 todo/doing/review/done 四列"]
    if re.search(r"(?m)^(columns|statuses):", text):
        new = re.sub(r"(?m)^(columns|statuses):.*$", want, text)
    else:
        new = text.rstrip() + "\n" + want + "\n"
    if apply_changes:
        f.write_text(new, encoding="utf-8", newline="\n")
    return [f"{'已改写' if apply_changes else '待改写'}：backlog/config.yml → {want}"
            "（真工具默认 To Do/In Progress/Done，不改则 `-s doing` 被拒）"]


def up_refresh_check_py(project: Path, apply_changes):
    """v1 遗留：老项目的 check.py 没有"卡与登记自授权"，认领与登记会被自己锁死。

    只在这一个条件下覆盖：项目里的 check.py 缺 SELF_AUTHORIZED 标记（说明确是旧版）。
    其它差异一律交给 audit 报漂移，不静默覆盖——本地改过的执法脚本要人决定怎么处理。
    """
    skeleton = _guess_skeleton(project)
    src = skeleton / "scripts" / "check.py" if skeleton else None
    dst = project / "scripts" / "check.py"
    if not src or not src.exists() or not dst.exists():
        return ["跳过：项目不带 scripts/check.py（这一档骨架没有卡片层执法）"]
    text = dst.read_text(encoding="utf-8")
    if "SELF_AUTHORIZED" in text:
        return ["已到位：check.py 含卡与登记自授权（I-001 晋升产物）"]
    if apply_changes:
        shutil.copyfile(str(src), str(dst))
    return [f"{'已刷新' if apply_changes else '待刷新'}：scripts/check.py 是 I-001 之前的旧版，"
            "缺自授权（会锁死认领与登记）；其余差异不自动覆盖，由 audit 报漂移"]


def _missing_capabilities(path: Path):
    if not path.exists():
        return list(CHECK_CAPABILITIES)
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return list(CHECK_CAPABILITIES)
    return [name for name in CHECK_CAPABILITIES if name not in text]


def drift_notice(project: Path):
    """sync 的一行漂移提示：只读 lock/AGENTS.md 与 check.py，不改项目文件。"""
    lock = read_lock(project) or {}
    schema = lock.get("schema") or declared_schema(project)
    notes = []
    if isinstance(schema, int) and schema < SCHEMA:
        notes.append(f"[漂移] 骨架 schema {schema} < {SCHEMA}：跑 maintain.py audit/migrate，"
                     "sync 不自动改项目文件")
    check = project / "scripts" / "check.py"
    missing = _missing_capabilities(check) if check.exists() else []
    if missing:
        notes.append(f"[漂移] check.py 缺规则能力：{', '.join(missing)}："
                     "跑 maintain.py audit/migrate，sync 不自动改项目文件")
    return notes


def _three_way_merge(ours: str, base: str, theirs: str):
    """用 git merge-file 做三方合并；冲突时返回 None 和带标记的补丁正文。"""
    with tempfile.TemporaryDirectory(prefix="coh-merge-") as td:
        d = Path(td)
        (d / "ours").write_text(ours, encoding="utf-8", newline="\n")
        (d / "base").write_text(base, encoding="utf-8", newline="\n")
        (d / "theirs").write_text(theirs, encoding="utf-8", newline="\n")
        r = _run(["git", "merge-file", "-p", "ours", "base", "theirs"], d)
    if r.returncode == 0:
        return r.stdout or "", None
    if r.returncode == 1:
        return None, r.stdout or "（git merge-file 没有输出补丁）"
    return None, (r.stderr or r.stdout or "git merge-file 执行失败").strip()


def up_merge_check_py(project: Path, apply_changes):
    """v3→v4：把项目 check.py 与当前骨架做三方合并，保留本地改动、冲突不落盘。"""
    skeleton = _guess_skeleton(project)
    dst = project / "scripts" / "check.py"
    if skeleton is None or not dst.exists():
        return ["跳过：项目不带 scripts/check.py（这一档骨架没有卡片层执法）"]
    src = skeleton / "scripts" / "check.py"
    if not src.exists():
        return ["跳过：当前骨架没有 scripts/check.py"]
    lock = read_lock(project) or {}
    commit = lock.get("skeleton_commit")
    rel = f"{skeleton.name}/scripts/check.py"
    ours = dst.read_text(encoding="utf-8")
    theirs = src.read_text(encoding="utf-8")
    if ours == theirs:
        return ["已到位：scripts/check.py 已是当前骨架版本"]
    if not commit:
        return ["冲突：指纹里没有 skeleton_commit，无法取三方合并基线；check.py 未改，请先补指纹或人工同步"]
    base_run = _run(["git", "show", f"{commit}:{rel}"], ROOT)
    if base_run.returncode != 0:
        return [f"冲突：取不到基线 {commit}:{rel}，check.py 未改，请人工同步"]
    merged, conflict = _three_way_merge(ours, base_run.stdout or "", theirs)
    if conflict is not None:
        return ["冲突：scripts/check.py 三方合并失败，未覆盖；请人工处理以下补丁", conflict]
    missing = [name for name in CHECK_CAPABILITIES if name not in merged]
    if missing:
        return [f"冲突：合并结果仍缺执法能力 {', '.join(missing)}，未覆盖 check.py"]
    if apply_changes:
        dst.write_text(merged, encoding="utf-8", newline="\n")
    return [f"{'已合并' if apply_changes else '待合并'}：scripts/check.py 按基线 {commit} 做三方合并"]


UPGRADES = {
    1: ("本地记账进 .gitignore + 库路径代入绝对值 + 认领首选 wsc claim + 补降级行为节 + "
        "删常驻卡 + 看板列改四列 statuses + 刷新缺自授权的旧 check.py",
        (up_ignore_telemetry, up_library_paths, up_claim_line, up_degrade_section,
         up_drop_resident_card, up_backlog_statuses, up_refresh_check_py)),
    2: ("适配指针升级为各工具原生目录格式（.cursor/rules、.windsurf/rules），清掉旧单文件",
        (up_native_adapters,)),
    3: ("scripts/check.py 三方合并到当前骨架（审阅意见 / 结果行 / 可观察验收 / 所有权执法），"
        "冲突拒绝覆盖",
        (up_merge_check_py,)),
}


def _pending_steps(schema):
    return [v for v in sorted(UPGRADES) if v >= schema]


_PENDING_PREFIX = (("已追加", "待追加"), ("已改写", "待改写"), ("已改为", "待改"),
                  ("已补", "待补"), ("已迁移", "待迁移"), ("已删除", "待删除"),
                  ("已刷新", "待刷新"), ("已合并", "待合并"))


def _pending_line(line):
    for done, pending in _PENDING_PREFIX:
        if line.startswith(done):
            return pending + line[len(done):]
    return line


def _run_migration_steps(project, steps, apply_changes, pending=False):
    conflicts = []
    for v in steps:
        title, funcs = UPGRADES[v]
        print(f"\nv{v} -> v{v + 1}: {title}")
        for fn in funcs:
            for raw in fn(project, apply_changes):
                print(f"  - {_pending_line(raw) if pending else raw}")
                if raw.startswith("冲突："):
                    conflicts.append(raw)
    return conflicts


def _preflight_migration(project, steps):
    """在临时副本上顺序执行全部步骤，验证多步依赖且不碰真实项目。"""
    with tempfile.TemporaryDirectory(prefix="coh-migrate-") as td:
        shadow = Path(td) / "project"
        shutil.copytree(project, shadow, ignore=shutil.ignore_patterns(".git"))
        return _run_migration_steps(shadow, steps, True, pending=True)




def cmd_migrate(args):
    project = Path(args.project).resolve()
    lock = read_lock(project)
    if isinstance(lock, dict) and "_坏掉" in lock:
        sys.exit(f"[migrate] {lock['_坏掉']}（先跑 maintain.py lock 重写指纹）")
    schema = (lock or {}).get("schema") or declared_schema(project) or 1
    source = "指纹" if (lock or {}).get("schema") else ("AGENTS.md 声明" if declared_schema(project) else "无来源，按 v1")
    steps = _pending_steps(schema)
    print(f"== migrate {project}（当前 schema={schema}←{source}，本体 schema={SCHEMA}）==")
    if args.yes and not (project / ".git").exists():
        sys.exit("[migrate] 项目不是 git 仓库，建不了备份分支——先 git init 再 --yes")
    if not steps and schema >= SCHEMA:
        print("已是最新 schema，无升级步骤。")
        return
    conflicts = _preflight_migration(project, steps)
    if conflicts:
        sys.exit("[migrate] 预检发现未解决冲突，未建备份分支也未落盘；请人工处理后重跑")
    if args.yes:
        backup = f"coh-backup-{now_stamp()}"
        r = _run(["git", "branch", backup], project)
        if r.returncode != 0:
            sys.exit(f"[migrate] 备份分支建不起来，不落盘：{(r.stdout or '') + (r.stderr or '')}")
        print(f"[migrate] 已建备份分支 {backup}（回到旧状态：git reset --hard {backup}）")
        conflicts = _run_migration_steps(project, steps, True)
        if conflicts:
            sys.exit("[migrate] 落盘时出现冲突，schema 未推进；请人工处理后重跑")
        cmd_lock(argparse.Namespace(project=str(project)))
        print(f"\n[migrate] 已落盘并把 schema 记到 {SCHEMA}；改动都在备份分支 {backup} 的对照下，"
              f"回滚：git reset --hard {backup}")
    else:
        print("\n（dry-run：什么都没写。确认无误再加 --yes，落盘前会自动建备份分支）")


def cmd_audit(args):
    """只读体检：钩子在不在、被没被改、指纹漂了没、合成态合不合法。"""
    project = Path(args.project).resolve()
    quick = bool(getattr(args, "quick", False))
    as_json = bool(getattr(args, "json", False))
    issues, lines = [], []

    def say(line=""):
        lines.append(line)
        if not as_json:
            print(line)

    say(f"== audit {project}（只读）==")
    lock = read_lock(project)
    if lock is None:
        say("[指纹] 未记录：跑 `python maintain.py lock <项目>` 补一份（audit 仍可继续）")
        issues.append("缺装机指纹")
    elif "_坏掉" in lock:
        say(f"[指纹] {lock['_坏掉']}")
        issues.append("指纹读不懂")
    else:
        say(f"[指纹] 骨架={lock.get('skeleton')} commit={lock.get('skeleton_commit')} "
            f"schema={lock.get('schema')} adapters={lock.get('adapters') or '无'}")
        if lock.get("schema", 1) < SCHEMA:
            say(f"  [警告] schema 落后（{lock.get('schema')} < {SCHEMA}）：跑 maintain.py migrate")
            issues.append("schema 落后")

    hook_src = None
    skel = _guess_skeleton(project)
    if skel:
        hook_src = skel / "scripts" / "hooks" / "pre-commit"
    target, state, extra = wsc._hooks_target(project)
    if state != "ok":
        why = {"git-missing": "找不到 git 命令", "not-a-repo": "项目不是 git 仓库",
               "outer-repo": f"项目在外层仓库 {extra} 里"}[state]
        say(f"[钩子] 无法安装：{why}——check.py 不会被任何提交自动触发")
        issues.append("钩子无处安放")
    else:
        installed = Path(target) / "pre-commit"
        if not installed.exists():
            say(f"[钩子] 缺失：{installed} 没有 pre-commit（clone 不带钩子；跑 wsc sync 自愈或手动 cp）")
            issues.append("钩子缺失")
        elif hook_src and hook_src.exists():
            want, got = _sha(hook_src), _sha(installed)
            say(f"[钩子] 在位；骨架版 {want} / 装的 {got}" + ("（一致）" if want == got else ""))
            if want != got:
                say("  [违规] 钩子被改过：执法面与骨架不一致，要么还原要么走规则卡说明")
                issues.append("钩子被改")
        else:
            say("[钩子] 在位（这一档骨架不带 scripts/hooks/pre-commit，无法比对）")

    check_path = project / "scripts" / "check.py"
    cur = _sha(check_path)
    missing = _missing_capabilities(check_path) if check_path.exists() else []
    if missing:
        say(f"[执法面] 缺规则能力：{', '.join(missing)}（跑 maintain.py migrate 或人工同步）")
        issues.append("执法能力缺失")
    elif check_path.exists():
        say("[执法面] 规则能力标记齐全")
    if lock and lock.get("check_sha256") and cur:
        if lock["check_sha256"] != cur:
            say(f"[执法面] 项目里的 check.py 与指纹不符（{lock['check_sha256']} → {cur}）")
            issues.append("check.py 漂移")
        else:
            say(f"[执法面] check.py 与指纹一致（{cur}）")

    stray = []
    for p in sorted(project.rglob("*.md")):
        rel = p.relative_to(project).as_posix()
        if rel.startswith(".agent/") or ".git" in p.parts:
            continue
        try:
            body = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if re.search(r"(?m)^\|\s*I-\d+\s*\|", body):
            stray.append(rel)
    if stray:
        say("[登记表] 有 improvements 形状的表格写在 .agent/ 之外：" + "、".join(stray))
        say("  [违规] 登记条目只认 `.agent/improvements.md`——写在别处的条目 improve/evolve 读不到，等于没登记")
        issues.append("登记表写错位置")
    else:
        say("[登记表] 未在 .agent/ 外发现登记痕迹")

    merges = _run(["git", "log", "--merges", "--oneline", "-n", "10"], project)
    n_merges = len([l for l in (merges.stdout or "").splitlines() if l.strip()]) \
        if merges.returncode == 0 else 0
    rebases = [l for l in (_run(["git", "reflog", "-n", "50"], project).stdout or "").splitlines()
               if "rebase" in l or "reset:" in l or "merge" in l]
    if n_merges or rebases:
        say(f"[入口] 最近 {n_merges} 个 merge 提交、reflog 里 {len(rebases)} 条 rebase/reset/merge 记录"
            "——这些路径都不跑 pre-commit")
        for line in merges.stdout.splitlines()[:3] if merges.returncode == 0 else []:
            say(f"  {line}")
        say("  合成态是否因此变非法，看下面一条；本轮不据此定罪，只点名待复查的入口")
    else:
        say("[入口] 最近没有 merge/rebase 痕迹（pre-commit 覆盖得到的提交都在钩子后面）")

    if quick:
        say("[合成态] quick：跳过全量 check")
    elif check_path.exists():
        r = _run([sys.executable, "scripts/check.py", "--no-track"], project, timeout=300)
        state = "合法" if r.returncode == 0 else "不合法"
        say(f"[合成态] 全量 check：rc={r.returncode} → main 当前{state}")
        if r.returncode != 0:
            say("  每个提交当时都合法不代表 main 合法（rebase/merge 不跑钩子）——这是 I-004 的形状")
            for line in (r.stdout or "").splitlines():
                if line.startswith("[") and "通过" not in line:
                    say(f"  {line}")
            issues.append("main 合成态违规")
    say("\n不覆盖的范围：harness 自身的网络与 IDE 遥测、模型 API、`--no-verify` 绕过当时的事后痕迹"
        "（绕过会在 reflog 里留下没有钩子判决的提交，可人工核对，不自动定罪）")
    say(f"结论：{'发现 %d 类问题：%s' % (len(issues), '、'.join(issues)) if issues else '干净'}")
    if as_json:
        print(json.dumps({"project": str(project), "quick": quick, "ok": not issues,
                          "issues": issues, "missing_capabilities": missing,
                          "lines": lines}, ensure_ascii=False, sort_keys=True))
    sys.exit(1 if issues else 0)


def main():
    wsc._utf8_streams()
    ap = argparse.ArgumentParser(description="CoHarness 已实例化项目的维护面工具")
    sub = ap.add_subparsers(dest="cmd")
    p_lock = sub.add_parser("lock", help="写/刷新装机指纹")
    p_lock.add_argument("project")
    p_mig = sub.add_parser("migrate", help="按 schema 差值升级已实例化项目（默认 dry-run）")
    p_mig.add_argument("project")
    p_mig.add_argument("--yes", action="store_true", help="落盘（先自动建备份分支）")
    p_aud = sub.add_parser("audit", help="只读体检：钩子/指纹/合成态")
    p_aud.add_argument("project")
    p_aud.add_argument("--quick", action="store_true", help="只读摘要，跳过全量 check")
    p_aud.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    sub.add_parser("schema", help="打印 schema 版本与升级步骤")
    args = ap.parse_args()
    if args.cmd == "lock":
        return cmd_lock(args)
    if args.cmd == "migrate":
        return cmd_migrate(args)
    if args.cmd == "audit":
        return cmd_audit(args)
    if args.cmd == "schema":
        return cmd_schema(args)
    print(__doc__)


if __name__ == "__main__":
    main()
