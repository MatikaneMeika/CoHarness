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
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wsc  # noqa: E402  复用 ROOT / _run / 骨架发现，不在本文件里重写一套

ROOT = wsc.ROOT
_run = wsc._run
SCHEMA = 3
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
    entry = {"skeleton": skeleton.name, "skeleton_commit": rev[1] if rev[0] == "ok" else "",
             "schema": SCHEMA, "library": str(ROOT),
             "adapters": _adapters_present(project), "locked_at": f"{datetime.now():%Y-%m-%d %H:%M}",
             "check_sha256": _sha(project / "scripts" / "check.py")}
    f = project / LOCK_NAME
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(entry, ensure_ascii=False, indent=1) + "\n",
                 encoding="utf-8", newline="\n")
    print(f"[lock] 已写 {f}")
    for k in ("skeleton", "skeleton_commit", "schema", "check_sha256"):
        print(f"  {k} = {entry[k]}")


def _sha(path: Path):
    if not path.exists():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12]


def _guess_skeleton(project: Path):
    """按 AGENTS.md 的标题反推骨架名（装机时标题里的占位符已被填掉，只能比对结构）。"""
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
    return [f"待改：{f.name} 追加 '{TELEMETRY_IGNORE}'"]


def up_library_paths(project: Path, apply_changes):
    """把散文占位符 `<骨架库>`/`<CoHarness>` 换成本机骨架库路径（命令要能直接复制执行）。"""
    hits = []
    for p in sorted(project.rglob("*.md")):
        text = p.read_text(encoding="utf-8")
        if "<骨架库>" not in text and "<CoHarness>" not in text:
            continue
        hits.append(p.relative_to(project).as_posix())
        if apply_changes:
            new = text.replace("<骨架库>/wsc.py", f"{ROOT}/wsc.py")
            new = new.replace("<CoHarness>/wsc.py", f"{ROOT}/wsc.py")
            p.write_text(new, encoding="utf-8", newline="\n")
    if not hits:
        return ["已到位：文档里的库路径都已代入本机绝对路径"]
    verb = "已改写" if apply_changes else "待改写"
    return [f"{verb}：{', '.join(hits)} 里还有 <骨架库>/<CoHarness>"]


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
    return ["待改：认领条款换成 wsc claim 首选（原句：'认领 = -a <标识> -s doing'）"]


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
    return [f"待补：从 {skeleton.name} 搬「降级行为」节进 AGENTS.md"]


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
        rel = wsc.ADAPTERS[name][0]
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


UPGRADES = {
    1: ("补 .gitignore 的本地记账项 + 代入骨架库绝对路径 + 认领首选 wsc claim + 补降级行为节",
        (up_ignore_telemetry, up_library_paths, up_claim_line, up_degrade_section)),
    2: ("适配指针升级为各工具原生目录格式（.cursor/rules、.windsurf/rules），清掉旧单文件",
        (up_native_adapters,)),
}


def _pending_steps(schema):
    return [v for v in sorted(UPGRADES) if v >= schema]


def cmd_migrate(args):
    project = Path(args.project).resolve()
    lock = read_lock(project)
    if isinstance(lock, dict) and "_坏掉" in lock:
        sys.exit(f"[migrate] {lock['_坏掉']}（先跑 maintain.py lock 重写指纹）")
    schema = (lock or {}).get("schema", 1)
    steps = _pending_steps(schema)
    print(f"== migrate {project}（当前 schema={schema}，本体 schema={SCHEMA}）==")
    if not steps and schema >= SCHEMA:
        print("已是最新 schema，无升级步骤。")
        return
    backup = None
    if args.yes:
        if (project / ".git").exists():
            backup = f"coh-backup-{now_stamp()}"
            r = _run(["git", "branch", backup], project)
            if r.returncode != 0:
                sys.exit(f"[migrate] 备份分支建不起来，不落盘：{(r.stdout or '') + (r.stderr or '')}")
            print(f"[migrate] 已建备份分支 {backup}（回到旧状态：git reset --hard {backup}）")
        else:
            sys.exit("[migrate] 项目不是 git 仓库，建不了备份分支——先 git init 再 --yes")
    for v in steps:
        title, funcs = UPGRADES[v]
        print(f"\nv{v} -> v{v + 1}: {title}")
        for fn in funcs:
            for line in fn(project, args.yes):
                print(f"  - {line}")
    if args.yes:
        cmd_lock(argparse.Namespace(project=str(project)))
        print(f"\n[migrate] 已落盘并把 schema 记到 {SCHEMA}；改动都在备份分支 {backup} 的对照下，"
              f"回滚：git reset --hard {backup}")
    else:
        print("\n（dry-run：什么都没写。确认无误再加 --yes，落盘前会自动建备份分支）")


def cmd_audit(args):
    """只读体检：钩子在不在、被没被改、装机指纹漂了没、main 上的合成态合不合法。"""
    project = Path(args.project).resolve()
    issues = []
    print(f"== audit {project}（只读）==")

    lock = read_lock(project)
    if lock is None:
        print("[指纹] 未记录：跑 `python maintain.py lock <项目>` 补一份（audit 仍可继续）")
        issues.append("缺装机指纹")
    elif "_坏掉" in lock:
        print(f"[指纹] {lock['_坏掉']}")
        issues.append("指纹读不懂")
    else:
        print(f"[指纹] 骨架={lock.get('skeleton')} commit={lock.get('skeleton_commit')} "
              f"schema={lock.get('schema')} adapters={lock.get('adapters') or '无'}")
        if lock.get("schema", 1) < SCHEMA:
            print(f"  [警告] schema 落后（{lock.get('schema')} < {SCHEMA}）：跑 maintain.py migrate")
            issues.append("schema 落后")

    hook_src = None
    skel = _guess_skeleton(project)
    if skel:
        hook_src = skel / "scripts" / "hooks" / "pre-commit"
    target, state, extra = wsc._hooks_target(project)
    if state != "ok":
        why = {"git-missing": "找不到 git 命令", "not-a-repo": "项目不是 git 仓库",
               "outer-repo": f"项目在外层仓库 {extra} 里"}[state]
        print(f"[钩子] 无法安装：{why}——check.py 不会被任何提交自动触发")
        issues.append("钩子无处安放")
    else:
        installed = Path(target) / "pre-commit"
        if not installed.exists():
            print(f"[钩子] 缺失：{installed} 没有 pre-commit（clone 不带钩子；跑 wsc sync 自愈或手动 cp）")
            issues.append("钩子缺失")
        elif hook_src and hook_src.exists():
            want = hashlib.sha256(hook_src.read_bytes()).hexdigest()[:12]
            got = hashlib.sha256(installed.read_bytes()).hexdigest()[:12]
            print(f"[钩子] 在位；骨架版 {want} / 装的 {got}" + ("（一致）" if want == got else ""))
            if want != got:
                print("  [违规] 钩子被改过：执法面与骨架不一致，要么还原要么走规则卡说明")
                issues.append("钩子被改")
        else:
            print("[钩子] 在位（这一档骨架不带 scripts/hooks/pre-commit，无法比对）")

    cur = _sha(project / "scripts" / "check.py")
    if lock and lock.get("check_sha256") and cur:
        if lock["check_sha256"] != cur:
            print(f"[执法面] 项目里的 check.py 与指纹不符（{lock['check_sha256']} → {cur}）")
            issues.append("check.py 漂移")
        else:
            print(f"[执法面] check.py 与指纹一致（{cur}）")

    if (project / "scripts" / "check.py").exists():
        r = _run([sys.executable, "scripts/check.py"], project, timeout=300)
        state = "合法" if r.returncode == 0 else "不合法"
        print(f"[合成态] 全量 check：rc={r.returncode} → main 当前{state}")
        if r.returncode != 0:
            print("  每个提交当时都合法不代表 main 合法（rebase/merge 不跑钩子）——这是 I-004 的形状")
            for line in (r.stdout or "").splitlines():
                if line.startswith("[") and "通过" not in line:
                    print(f"  {line}")
            issues.append("main 合成态违规")
    print("\n不覆盖的范围：harness 自身的网络与 IDE 遥测、模型 API、`--no-verify` 绕过当时的事后痕迹"
          "（绕过会在 reflog 里留下没有钩子判决的提交，可人工核对，不自动定罪）")
    print(f"结论：{'发现 %d 类问题：%s' % (len(issues), '、'.join(issues)) if issues else '干净'}")
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
