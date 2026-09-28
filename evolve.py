#!/usr/bin/env python3
"""evolve.py — 骨架改进审核工具（骨架库的开发期工具，不进分发面）。

为什么不在 wsc.py 里：`wsc.py` 会被 `curl` 单文件下载、并被复制进每个下游项目的使用路径，
它只该管下游要用的事（装机/开工/认领/体检/统计）。审核晋升改的是**本体**——读登记表、
去本机所有实例里数同类摩擦、拿补丁在临时副本上试装跑自测，这些都是维护者侧动作。
按 ADR-10「依赖面按分发面分层」，它单独立个文件，纯标准库、零网络，共享的读表与调用形状
从 `wsc` 模块取（同目录）。

用法:
    python evolve.py <项目路径> [--rubric] [--out 记录.json]
    python evolve.py --verify-record 记录.json      # 晋升资格机器门禁（缺一不得写回）
    python evolve.py --apply-check 补丁.diff        # 临时副本试装 + 全套自测
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

try:                      # 装成包时（pip install coharness）走相对导入
    from . import wsc
except ImportError:       # curl 单文件 / clone 后直接跑脚本时的形状
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import wsc

ROOT = wsc.ROOT
_run = wsc._run
load_ledger = wsc.load_ledger
friction_key = wsc._friction_key
scan_registry = wsc._scan_registry_ledgers
TRIAL_ENV = "COHARNESS_TRIAL"
LOCK_NAME = ".agent/skeleton.lock"


def _run_env(argv, cwd, env, timeout=1800):
    """同 wsc._run 的形状（argv 全字面量、shell=False、显式 utf-8），只多一个环境覆盖。"""
    return subprocess.run([str(a) for a in argv], cwd=str(cwd), capture_output=True,
                          text=True, encoding="utf-8", errors="replace",
                          timeout=timeout, shell=False, env=env)


REF_TOKEN_RE = re.compile(r"[\w./*-]+\.(?:md|py|json|jsonl|yml)")
COMMIT_REF_RE = re.compile(r"commit\s+([0-9a-f]{7,40})")
VERDICTS = ("晋升", "继续试点", "驳回")
PROOF_KEYS = ("diff 位置", "来源项目", "测试/CI 运行标识", "用户批准")
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", "dist", "build"}


def _rubric():
    """审核标准从 docs/EVOLUTION-PROCESS.md 现读现印，避免工具和文档两套口径。"""
    doc = ROOT / "docs" / "EVOLUTION-PROCESS.md"
    try:
        text = doc.read_text(encoding="utf-8")
    except OSError:
        return []
    m = re.search(r"##\s*五条审核标准.*?\n(.*?)\n(?=##)", text, re.S)
    if not m:
        return []
    return [l.strip() for l in m.group(1).splitlines() if re.match(r"^\d+\.", l.strip())]


def _tree_index(base: Path, limit=4000):
    """{相对路径集合, 文件名: [相对路径]}：证据引用按整路径找不到时按文件名兜。"""
    paths, by_name = set(), {}
    if not base.is_dir():
        return paths, by_name
    for p in base.rglob("*"):
        if not p.is_file() or SKIP_DIRS & set(p.parts):
            continue
        rel = p.relative_to(base).as_posix()
        paths.add(rel)
        by_name.setdefault(p.name, []).append(rel)
        if len(paths) >= limit:
            break
    return paths, by_name


def _refs_in(*texts):
    refs, commits = set(), set()
    for t in texts:
        refs.update(r for r in REF_TOKEN_RE.findall(t or "") if "/" in r or "." in r)
        commits.update(COMMIT_REF_RE.findall(t or ""))
    return sorted(refs), sorted(commits)


def _locate_refs(refs, commits, project):
    """证据列里点到的路径/commit 能不能翻出来——真实性那条标准的机器部分。"""
    indexes = {b: _tree_index(b) for b in (project, ROOT)}
    found = []
    for r in refs:
        where = []
        for base, (paths, by_name) in indexes.items():
            if r in paths:
                where.append(f"{(base / r).as_posix()}")
            else:
                for a in by_name.get(Path(r).name, [])[:2]:
                    where.append(f"{(base / a).as_posix()}（按文件名兜到）")
        found.append({"ref": r, "found": sorted(set(where))})
    commit_state = {}
    for c in commits:
        commit_state[c] = _run(["git", "cat-file", "-e", f"{c}^{{commit}}"], ROOT).returncode == 0
    return found, commit_state


def _landing(cells):
    """提议落点预判：能力缺口去 ROUTER.md 推荐能力节；点了文件就用它；否则要审核人补。"""
    refs, _ = _refs_in(cells[5])
    if cells[2] == "能力":
        return ["ROUTER.md（推荐能力节）"]
    if refs:
        return refs
    return [f"（提议未点文件：按场景'{cells[3]}'定位骨架文件）"]


def _machine_findings(cells, project, groups):
    same = sorted({p for p, _ in groups.get(friction_key(cells), [])})
    refs, commits = _refs_in(cells[3], cells[4], cells[6])
    found, commit_state = _locate_refs(refs, commits, project)
    landing = _landing(cells)
    overlap = []
    for item in landing:
        f = ROOT / item.split("（")[0]
        if f.is_file():
            hits = [l for l in f.read_text(encoding="utf-8").splitlines()
                    for r in refs[:3] if r in l]
            if hits:
                overlap.append({"file": item, "lines": len(set(hits))})
    return {"同类摩擦项目": same,
            "摩擦条数": len(groups.get(friction_key(cells), [])),
            "证据引用": found, "证据 commit": commit_state,
            "提议落点": landing, "落点文件已有的相关条款": overlap}


def fingerprint(project: Path):
    """装机指纹校验：读项目的 .agent/skeleton.lock，与骨架本体的 schema / commit 比对。

    指纹缺失不是错误（登记表之前的老项目就没有），但它意味着 migrate 与 audit 没有可比基准，
    所以机器取证里要显式说出来，而不是让审核人以为"没提就是没问题"。
    """
    import json
    import maintain
    f = project / LOCK_NAME
    if not f.exists():
        return {"指纹": "缺", "建议": f"跑 python {ROOT / 'maintain.py'} lock <项目>"}
    try:
        lock = json.loads(f.read_text(encoding="utf-8"))
    except ValueError:
        return {"指纹": "读不懂", "路径": str(f)}
    if not isinstance(lock, dict):
        return {"指纹": "格式不对", "路径": str(f)}
    out = {"指纹": "在", "schema": lock.get("schema"), "装机骨架": lock.get("skeleton"),
           "装机时本体 commit": lock.get("skeleton_commit")}
    if lock.get("schema") != maintain.SCHEMA:
        out["漂移"] = f"schema {lock.get('schema')} ≠ 本体 {maintain.SCHEMA} → 跑 maintain.py migrate"
    return out


def _entry_record(cells, project, groups):
    return {"id": cells[0], "日期": cells[1], "类别": cells[2], "场景": cells[3],
            "问题": cells[4], "提议": cells[5], "证据": cells[6], "状态": cells[7],
            "来源项目": str(project),
            "装机指纹": fingerprint(project),
            "机器取证": _machine_findings(cells, project, groups),
            "主观评估": {"有效性": None, "必要性": None, "理由": ""},
            "结论": None,
            "三证": {k: "" for k in PROOF_KEYS}}


def _print_findings(rec):
    m = rec["机器取证"]
    print(f"  {rec['id']} [{rec['状态']}] 类别={rec['类别']} 场景={rec['场景']}")
    fp = rec.get("装机指纹", {})
    note = "；".join(f"{k}={v}" for k, v in fp.items() if k != "指纹")
    print(f"      装机指纹：{fp.get('指纹', '?')}" + (f"（{note}）" if note else ""))
    print(f"      问题：{rec['问题']}")
    print(f"      提议：{rec['提议']}")
    if len(m["同类摩擦项目"]) >= 2:
        print(f"      普遍性（机器）：{len(m['同类摩擦项目'])} 个项目登记过同类 → "
              f"{', '.join(m['同类摩擦项目'])}")
    else:
        print("      普遍性（机器）：本机只此一处，孤证；按门槛继续攒证据")
    for item in m["证据引用"]:
        print(f"      证据可核：{item['ref']} → "
              + ("、".join(item["found"]) if item["found"] else "翻不到（要补出处）"))
    for c, ok in m["证据 commit"].items():
        print(f"      证据 commit：{c} → " + ("骨架库里存在" if ok else "骨架库里没有这个 commit"))
    print(f"      提议落点：{', '.join(m['提议落点'])}")
    for o in m["落点文件已有的相关条款"]:
        print(f"      兼容性提示：{o['file']} 已有 {o['lines']} 行提到同一批路径"
              f"——是否重复造轮子需人判")


def _rmtree(path):
    """git 对象是只读的，Windows 上直接删会失败——先改权限再删。"""
    def _clear(func, p, exc):
        Path(p).chmod(0o700)
        func(p)
    shutil.rmtree(str(path), onerror=_clear)


def apply_check(patch):
    """晋升前的机械化试装：把骨架库复制到临时目录，套上 patch 跑全套自测（本体不动）。"""
    p = Path(patch).resolve()
    if not p.is_file():
        sys.exit(f"[evolve --apply-check] 找不到补丁 {p}")
    tmp = Path(tempfile.mkdtemp(prefix="coh-trial-"))
    lib = tmp / "lib"
    # 连 .git 一起复制：本机登记表要记骨架库 commit，副本里没 .git 会把这条承诺测成假红
    shutil.copytree(str(ROOT), str(lib), ignore=shutil.ignore_patterns(
        "workspace", "__pycache__", "*.pyc", ".venv*"))
    run_id = f"trial-{datetime.now():%Y%m%d-%H%M%S}"
    print(f"[evolve --apply-check] 临时副本 {lib}（run={run_id}，本体未改动）")
    check = _run(["git", "apply", "--check", "-p1", str(p)], lib)
    if check.returncode != 0:
        print((check.stdout or "") + (check.stderr or ""))
        _rmtree(tmp)
        sys.exit("[evolve --apply-check] 补丁套不上（上下文不符或路径错），不得写回")
    numstat = _run(["git", "apply", "--numstat", "-p1", str(p)], lib).stdout or ""
    applied = _run(["git", "apply", "-p1", str(p)], lib)
    if applied.returncode != 0:
        _rmtree(tmp)
        sys.exit("[evolve --apply-check] --check 过了但真套失败：\n"
                 + (applied.stdout or "") + (applied.stderr or ""))
    print("  补丁可套用，改动文件（diff 位置就是这条的来源）：")
    for line in numstat.splitlines():
        print(f"    {line}")
    # 递归防线：副本里的 tests/test_evolve.py 会再调一次 --apply-check，
    # 带着这个标记跑就等于让门禁自己套自己、无限递归。被标记的跑法里那两条用例自动跳过。
    inner_env = dict(os.environ, **{TRIAL_ENV: run_id})
    tests = _run_env([sys.executable, "-m", "unittest", "discover", "-s", "tests"], lib, inner_env)
    tail = ((tests.stdout or "") + (tests.stderr or "")).splitlines()[-6:]
    print(f"  全套自测：rc={tests.returncode}")
    for line in tail:
        print(f"    {line}")
    # I-004 的最小实现：合并之后必须有人复查一次全量检查——这里当场补一次
    trial_proj = tmp / "proj"
    init = _run([sys.executable, str(lib / "wsc.py"), "init", "03", str(trial_proj)], lib)
    verdict = "（未能实例化测试项目，跳过复查）"
    if init.returncode == 0:
        full = _run([sys.executable, str(lib / "wsc.py"), "check", str(trial_proj)], lib)
        verdict = f"rc={full.returncode}"
    print(f"  套上补丁后新实例化项目全量 check：{verdict}")
    _rmtree(tmp)
    if tests.returncode != 0:
        sys.exit(f"[evolve --apply-check] 补丁让自测变红，不得写回本体（run={run_id}）")
    print(f"\n三证填法：diff 位置={p}；测试/CI 运行标识={run_id}；"
          "来源项目与用户批准由审核记录补全")


def verify_record(path):
    """审核记录的机器门禁：结论合法；晋升必须有两项主观评估 + 四项证据齐，缺一不得写回。"""
    f = Path(path).resolve()
    if not f.is_file():
        sys.exit(f"[evolve --verify-record] 找不到记录 {f}")
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
    except ValueError as e:
        sys.exit(f"[evolve --verify-record] 记录不是合法 json: {e}")
    entries = data.get("条目") if isinstance(data, dict) else data
    if not isinstance(entries, list):
        sys.exit("[evolve --verify-record] 记录里没有『条目』数组")
    problems = []
    for rec in entries:
        rid = rec.get("id", "?")
        verdict = rec.get("结论")
        if verdict not in VERDICTS:
            problems.append(f"{rid}: 结论 '{verdict}' 不在 {VERDICTS}")
            continue
        if verdict != "晋升":
            continue
        sub = rec.get("主观评估") or {}
        for k in ("有效性", "必要性"):
            if not str(sub.get(k) or "").strip():
                problems.append(f"{rid}: 晋升缺主观项『{k}』（这两条归人判，不能空着）")
        if not str(sub.get("理由") or "").strip():
            problems.append(f"{rid}: 晋升没写理由")
        proofs = rec.get("三证") or {}
        for k in PROOF_KEYS:
            if not str(proofs.get(k) or "").strip():
                problems.append(f"{rid}: 晋升缺证据『{k}』")
    if problems:
        print(f"[evolve --verify-record] {len(problems)} 处不合格，不得写回本体：")
        for p in problems:
            print(f"  - {p}")
        sys.exit(1)
    print(f"[evolve --verify-record] {len(entries)} 条记录全部合格")


def review(args):
    if not args.project:
        sys.exit("用法：python evolve.py <项目> [--rubric] [--out 记录.json]，"
                 "或 --verify-record 记录.json / --apply-check 补丁.diff")
    project = Path(args.project).resolve()
    f = project / ".agent" / "improvements.md"
    if not f.exists():
        sys.exit(f"未找到 {f}")
    _, pending, warnings = load_ledger(f)
    for w in warnings:
        print(f"状态机告警:{w}")
    groups, scanned, skipped, paths, _warns = scan_registry()
    key = str(project)
    if key not in paths and f.exists():
        for cells in pending:
            groups.setdefault(friction_key(cells), []).append((project.name, cells))
    joined = "" if key in paths else "，被审项目不在本机登记表内，已并入计数"
    print(f"== evolve {project}（本机登记 {scanned} 个实例，{len(skipped)} 个路径已失效{joined}）==")
    if not pending:
        print("无待审条目。")
        return
    records = [_entry_record(c, project, groups) for c in pending]
    print(f"待审 {len(records)} 条，机器取证如下（结论与两个主观项要你填）:\n")
    for rec in records:
        _print_findings(rec)
    payload = {"项目": str(project), "生成时间": f"{datetime.now():%Y-%m-%d %H:%M:%S}",
               "审核标准": _rubric(), "条目": records}
    text = json.dumps(payload, ensure_ascii=False, indent=1)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8", newline="\n")
        print(f"\n评估记录已落盘 {args.out}：填完『主观评估/结论/三证』后跑 "
              f"`python {ROOT / 'evolve.py'} --verify-record {args.out}`，红的不许写回")
    else:
        print("\n（加 --out 记录.json 拿到可填的评估记录；--rubric 只印五条标准）")


def main():
    wsc._utf8_streams()
    ap = argparse.ArgumentParser(description="CoHarness 骨架改进审核（开发期工具，不进分发面）")
    ap.add_argument("project", nargs="?", help="被审项目路径")
    ap.add_argument("--rubric", action="store_true", help="打印五条审核标准（现读文档）")
    ap.add_argument("--out", help="把评估记录写成 json，填完交给 --verify-record 把关")
    ap.add_argument("--verify-record", metavar="JSON", help="检查评估记录够不够写回本体的资格")
    ap.add_argument("--apply-check", metavar="PATCH",
                    help="在骨架库临时副本上试装补丁并跑全套自测（不改本体）")
    args = ap.parse_args()
    if args.apply_check:
        return apply_check(args.apply_check)
    if args.verify_record:
        return verify_record(args.verify_record)
    if args.rubric:
        rub = _rubric()
        print("五条审核标准（晋升必须全部成立，取自 docs/EVOLUTION-PROCESS.md）:")
        for line in rub:
            print(f"  {line}")
        if not rub:
            print("  （读不到 docs/EVOLUTION-PROCESS.md）")
        if not args.project:
            return
    review(args)


if __name__ == "__main__":
    main()
