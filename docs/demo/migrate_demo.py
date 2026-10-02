#!/usr/bin/env python3
"""公开演示：一个 v1 装机的项目，怎么被 `maintain.py migrate` 升级到当前 schema。

跑法（在 clone 出来的骨架库任意位置）：

    python docs/demo/migrate_demo.py            # 造 v1 项目 → dry-run → --yes → 核对
    python docs/demo/migrate_demo.py --keep     # 跑完保留临时项目目录，自己进去看

全程零网络：只用本地文件、本地 git，以及仓库里的 maintain.py。
输出与 docs/DEMO-migrate.md 里贴的一致（那份是 2026-10-02 实跑记录）。
"""
import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MAINTAIN = REPO / "maintain.py"


def sh(argv, cwd):
    return subprocess.run([str(a) for a in argv], cwd=str(cwd), capture_output=True,
                          text=True, encoding="utf-8", errors="replace")


def maintain(*args, cwd=None):
    r = sh([sys.executable, MAINTAIN, *args], cwd or REPO)
    print(f"$ python maintain.py {' '.join(args)}")
    print((r.stdout or "") + (r.stderr or ""), end="" if not (r.stdout or "").endswith("\n") else "")
    return r


def current_schema():
    r = sh([sys.executable, MAINTAIN, "schema"], REPO)
    m = re.search(r"骨架 schema 版本：(\d+)", r.stdout or "")
    return int(m.group(1))


def build_v1(root: Path) -> Path:
    """把 03 骨架复制成"本轮改动之前"的样子，migrate 才有东西可做。

    每一项都是真出现过的 v1 形态，不是为了让步骤好看而编的：散文占位符、旧认领句、
    `.cursorrules` 单文件、缺记账忽略、没有降级节、常驻规则卡、英文三列看板、
    以及 I-001 之前那版不认识自授权的 check.py。
    """
    src = REPO / "03-multi-harness-project"
    proj = root / src.name
    shutil.copytree(src, proj, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    agents = proj / "AGENTS.md"
    text = agents.read_text(encoding="utf-8").split("\n## 降级行为")[0]
    text = text.replace("wsc.py claim", "task edit -s doing")
    text = text.replace("{{COHARNESS_LIB}}", "<骨架库>")          # v1 的写法：下游猜不出路径
    text = re.sub(r"(?m)^\|\s*骨架 schema\s*\|\s*\d+\s*\|\n", "", text)  # v1 的项目卡没有这行声明
    agents.write_text(text + "\n## 工作方式\n\n（略）\n", encoding="utf-8", newline="\n")
    proto = proj / ".agent" / "workflows" / "parallel-protocol.md"
    proto.write_text(proto.read_text(encoding="utf-8").replace("{{COHARNESS_LIB}}", "<骨架库>"),
                     encoding="utf-8", newline="\n")
    gi = proj / ".gitignore"
    gi.write_text(gi.read_text(encoding="utf-8").replace(".agent/telemetry.jsonl", "telemetry.off"),
                  encoding="utf-8", newline="\n")
    (proj / ".cursorrules").write_text("旧版 Cursor 单文件规则\n", encoding="utf-8", newline="\n")
    (proj / "backlog" / "tasks" / "T-000-board.md").write_text(
        "---\nid: T-000\ntitle: 常驻规则卡\nstatus: todo\nassignee: []\n---\n\n"
        "## 边界\nallowed_paths:\n  - docs/\nforbidden_paths:\n  - AGENTS.md\n",
        encoding="utf-8", newline="\n")
    (proj / "backlog" / "config.yml").write_text(
        "columns: [To Do, In Progress, Done]\n", encoding="utf-8", newline="\n")
    check = proj / "scripts" / "check.py"
    check.write_text(check.read_text(encoding="utf-8").replace("SELF_AUTHORIZED", "OLD_NAME"),
                     encoding="utf-8", newline="\n")
    ident = ["-c", "user.name=demo", "-c", "user.email=demo@invalid",
             "-c", "commit.gpgsign=false", "-c", "core.autocrlf=false"]
    sh(["git", "init", "-q", "--initial-branch=main"], proj)
    sh(["git", *ident, "add", "-A"], proj)
    sh(["git", *ident, "commit", "-q", "-m", "v1 装机"], proj)
    return proj


def main():
    ap = argparse.ArgumentParser(description="migrate 演示")
    ap.add_argument("--keep", action="store_true", help="保留临时项目目录")
    args = ap.parse_args()
    root = Path(tempfile.mkdtemp(prefix="coh-migrate-demo-"))
    try:
        proj = build_v1(root)
        print(f"=== v1 演示项目：{proj}\n")
        print("### 第 1 步：记一次装机指纹（schema 由骨架库当前版本决定）\n")
        maintain("lock", str(proj))
        ident = ["-c", "user.name=demo", "-c", "user.email=demo@invalid",
                 "-c", "commit.gpgsign=false", "-c", "core.autocrlf=false"]
        sh(["git", *ident, "add", ".agent/skeleton.lock"], proj)
        sh(["git", *ident, "commit", "-q", "-m", "记装机指纹"], proj)
        lock = proj / ".agent" / "skeleton.lock"
        lock.write_text(re.sub(r'"schema":\s*\d+', '"schema": 1', lock.read_text(encoding="utf-8")),
                        encoding="utf-8", newline="\n")
        print("### 第 2 步：把指纹改回 schema=1，模拟「这个项目还停在老版本」\n")
        before = sh(["git", "status", "--porcelain"], proj).stdout.strip()
        dry = maintain("migrate", str(proj))
        assert dry.returncode == 0, "dry-run 应当成功退出"
        after = sh(["git", "status", "--porcelain"], proj).stdout.strip()
        assert after == before, f"dry-run 不该写盘，前后不同：\n改前 {before}\n改后 {after}"
        assert '"schema": 1' in lock.read_text(encoding="utf-8"), "dry-run 也不该动指纹"
        print("（已核对：dry-run 前后 git status 一致，指纹未动）\n")
        print("### 第 3 步：确认后落盘——先自动建备份分支\n")
        yes = maintain("migrate", str(proj), "--yes")
        assert yes.returncode == 0
        print("\n### 第 4 步：核对结果\n")
        checks = {
            "旧单文件适配已删除": not (proj / ".cursorrules").exists(),
            "原生 Cursor 规则已生成": (proj / ".cursor" / "rules" / "coharness.mdc").exists(),
            ".gitignore 已忽略本地记账": ".agent/telemetry.jsonl" in (proj / ".gitignore").read_text(encoding="utf-8"),
            "AGENTS.md 已有降级行为节": "## 降级行为" in (proj / "AGENTS.md").read_text(encoding="utf-8"),
            "文档里的库路径已代入绝对路径": "<骨架库>" not in (proj / "AGENTS.md").read_text(encoding="utf-8"),
            "认领句已升级为 wsc claim": "wsc.py claim" in (proj / "AGENTS.md").read_text(encoding="utf-8"),
            "指纹记到当前 schema": f'"schema": {current_schema()}' in lock.read_text(encoding="utf-8"),
            "AGENTS.md 已声明当前 schema": f"| 骨架 schema | {current_schema()} |"
                                    in (proj / "AGENTS.md").read_text(encoding="utf-8"),
            "常驻规则卡已清掉": not (proj / "backlog" / "tasks" / "T-000-board.md").exists(),
            "看板列已改成本骨架四列": "statuses: [todo, doing, review, done]"
                                 in (proj / "backlog" / "config.yml").read_text(encoding="utf-8"),
            "旧版 check.py 已刷新为含自授权的那版": "SELF_AUTHORIZED"
                                        in (proj / "scripts" / "check.py").read_text(encoding="utf-8"),
        }
        for name, ok in checks.items():
            print(f"  [{'OK' if ok else 'FAIL'}] {name}")
        assert all(checks.values()), "有核对项不过"
        branches = sh(["git", "branch", "--list", "coh-backup-*"], proj).stdout.strip()
        print(f"  备份分支：{branches}")
        print(f"  回滚办法：git reset --hard {branches.split()[-1] if branches else '(没建上)'}")
        status = sh(["git", "status", "--short"], proj).stdout
        print(f"\n升级带来的未提交改动：\n{status}")
        print(f"下一步就是常规提交：git add -A && git commit -m 'migrate v1 -> v{current_schema()}'")
    finally:
        if args.keep:
            print(f"\n（已保留演示项目：{root}）")
        else:
            shutil.rmtree(str(root), ignore_errors=True)


if __name__ == "__main__":
    main()
