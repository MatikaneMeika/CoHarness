"""maintain.py：装机指纹、schema 迁移、只读体检（计划书 W9 + W12）。

migrate 的默认必须是 dry-run 且落盘前先建备份分支——它改的是别人项目里的规则文件；
audit 必须一个字都不写，因为它要在"项目可能已经漂了"的场景下安全地跑。
v1→v2 的升级步骤就是本轮真实做过的四件事，不是编的演示。
"""
import hashlib
import re
import sys
import unittest
from pathlib import Path

import helpers as H

MAINTAIN = H.REPO / "maintain.py"


def maintain(*args, timeout=300):
    return H.run([sys.executable, MAINTAIN, *args], cwd=H.REPO, timeout=timeout)


def tree_hash(project):
    h = hashlib.sha256()
    for p in sorted(project.rglob("*")):
        if p.is_file() and ".git" not in p.parts:
            h.update(str(p.relative_to(project)).encode("utf-8"))
            h.update(p.read_bytes())
    return h.hexdigest()


class Maintain(unittest.TestCase):
    def setUp(self):
        self.tmp = H.tmp_dir()
        self.addCleanup(H.rmtree, self.tmp)

    def fresh(self, name, downgrade=False):
        proj = H.make_project(self.tmp, H.REPO / name) if name != "03" else \
            H.make_project(self.tmp)
        H.git_repo(proj)
        H.git(proj, "config", "user.name", "maint")
        H.git(proj, "config", "user.email", "maint@invalid")
        H.git(proj, "config", "core.autocrlf", "false")
        H.install_hook(proj)
        if downgrade:
            self.make_v1(proj)
        return proj

    def proj_lock(self, proj):
        return proj / ".agent" / "skeleton.lock"

    def downgrade_schema(self, lock, to):
        """把指纹里的 schema 调低，模拟"这个项目还停在老版本"。"""
        text = lock.read_text(encoding="utf-8")
        lock.write_text(text.replace('"schema": 3', f'"schema": {to}'),
                        encoding="utf-8", newline="")

    def make_v1(self, proj):
        """把项目退回本轮改动之前的样子（v1），migrate 才有东西可做。"""
        agents = proj / "AGENTS.md"
        text = agents.read_text(encoding="utf-8")
        text = re.split(r"\n## 降级行为", text)[0]
        text = text.replace("wsc.py claim", "task edit -s doing")
        text = text.replace(str(H.REPO), "<CoHarness>")
        agents.write_text(text + "\n", encoding="utf-8", newline="\n")
        gi = proj / ".gitignore"
        gi.write_text(gi.read_text(encoding="utf-8").replace(".agent/telemetry.jsonl", "telemetry.off"),
                      encoding="utf-8", newline="\n")
        proto = proj / ".agent" / "workflows" / "parallel-protocol.md"
        proto.write_text(proto.read_text(encoding="utf-8").replace(str(H.REPO), "<骨架库>"),
                         encoding="utf-8", newline="\n")

    def test_lock_records_the_fingerprint(self):
        proj = self.fresh("03")
        r = maintain("lock", str(proj))
        self.assertEqual(r.returncode, 0, msg=H.out(r))
        lock = (proj / ".agent" / "skeleton.lock")
        self.assertTrue(lock.is_file())
        text = lock.read_text(encoding="utf-8")
        self.assertIn("03-multi-harness-project", text)
        self.assertIn('"schema": 3', text)
        self.assertRegex(text, r'"check_sha256": "[0-9a-f]{12}"')

    def test_schema_lists_upgrade_steps(self):
        out = H.out(maintain("schema"))
        self.assertIn("骨架 schema 版本：3", out)
        self.assertIn("v1 -> v2", out)
        self.assertIn("v2 -> v3", out)

    def test_migrate_dry_run_writes_nothing(self):
        proj = self.fresh("03", downgrade=True)
        before = tree_hash(proj)
        r = maintain("migrate", str(proj))
        self.assertEqual(r.returncode, 0, msg=H.out(r))
        out = H.out(r)
        self.assertIn("dry-run", out)
        self.assertIn("待改", out)
        self.assertIn("降级行为", out)
        self.assertIn("wsc claim", out)
        self.assertEqual(tree_hash(proj), before, "dry-run 不许写盘")

    def test_migrate_yes_applies_and_backs_up(self):
        proj = self.fresh("03", downgrade=True)
        r = maintain("migrate", str(proj), "--yes")
        self.assertEqual(r.returncode, 0, msg=H.out(r))
        self.assertIn("已建备份分支", H.out(r))
        branches = H.git(proj, "branch", "--list", "coh-backup-*").stdout
        self.assertIn("coh-backup-", branches)
        agents = (proj / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("## 降级行为", agents)
        self.assertIn("wsc.py claim", agents)
        self.assertNotIn("<CoHarness>", agents)
        self.assertIn(".agent/telemetry.jsonl", (proj / ".gitignore").read_text(encoding="utf-8"))
        self.assertNotIn("<骨架库>", (proj / ".agent" / "workflows" /
                                    "parallel-protocol.md").read_text(encoding="utf-8"))
        self.assertIn('"schema": 3', (proj / ".agent" / "skeleton.lock").read_text(encoding="utf-8"))

    def fresh_with_legacy(self, name):
        """带旧单文件适配的项目：旧文件必须进 bootstrap 提交，否则"改动未挂卡"当场拦下。"""
        proj = H.make_project(self.tmp)
        (proj / ".cursorrules").write_text("旧版 Cursor 单文件规则" + chr(10),
                                           encoding="utf-8", newline="")
        H.git_repo(proj)
        H.git(proj, "config", "user.name", name)
        H.git(proj, "config", "user.email", f"{name}@invalid")
        H.git(proj, "config", "core.autocrlf", "false")
        H.install_hook(proj)
        return proj

    def test_migrate_v2_to_v3_moves_legacy_adapters(self):
        """v2→v3：旧单文件适配换成各家原生目录格式；没装过指针的项目不该被塞新文件。"""
        proj = self.fresh_with_legacy("v23")
        self.assertEqual(maintain("lock", str(proj)).returncode, 0)
        lock = self.proj_lock(proj)
        self.assertIn('"schema": 3', lock.read_text(encoding="utf-8"))
        self.downgrade_schema(lock, 2)
        dry = maintain("migrate", str(proj))
        self.assertIn("待迁移 .cursorrules", H.out(dry))
        self.assertTrue((proj / ".cursorrules").exists(), "dry-run 不该删旧文件")
        yes = maintain("migrate", str(proj), "--yes")
        self.assertEqual(yes.returncode, 0, msg=H.out(yes))
        self.assertFalse((proj / ".cursorrules").exists())
        self.assertTrue((proj / ".cursor" / "rules" / "coharness.mdc").exists())
        self.assertIn('"schema": 3', lock.read_text(encoding="utf-8"))

    def test_migrate_v2_to_v3_does_not_invent_adapters(self):
        proj = self.fresh("03")
        self.assertEqual(maintain("lock", str(proj)).returncode, 0)
        self.downgrade_schema(self.proj_lock(proj), 2)
        self.assertEqual(maintain("migrate", str(proj), "--yes").returncode, 0)
        for rel in ("CLAUDE.md", ".cursor/rules/coharness.mdc", ".windsurf/rules/coharness.md"):
            self.assertFalse((proj / rel).exists(), f"没要过适配指针的项目不该被生成 {rel}")

    def test_migrate_is_idempotent(self):
        proj = self.fresh("03", downgrade=True)
        self.assertEqual(maintain("migrate", str(proj), "--yes").returncode, 0)
        second = maintain("migrate", str(proj))
        self.assertIn("已是最新 schema", H.out(second))

    def test_migrate_refuses_yes_without_a_repo(self):
        proj = H.make_project(self.tmp)
        r = maintain("migrate", str(proj), "--yes")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("建不了备份分支", H.out(r))
        self.assertFalse((proj / ".agent" / "skeleton.lock").exists(),
                         "拒绝落盘时一个文件都不该写")

    def test_audit_clean_project_passes(self):
        proj = self.fresh("03")
        self.assertEqual(maintain("lock", str(proj)).returncode, 0)
        r = maintain("audit", str(proj))
        self.assertEqual(r.returncode, 0, msg=H.out(r))
        out = H.out(r)
        self.assertIn("[钩子] 在位", out)
        self.assertIn("（一致）", out)
        self.assertIn("[执法面] check.py 与指纹一致", out)
        self.assertIn("结论：干净", out)
        self.assertIn("不覆盖的范围", out)

    def test_audit_catches_a_missing_hook(self):
        proj = self.fresh("03")
        hook = H.hooks_dir(proj) / "pre-commit"
        hook.unlink()
        r = maintain("audit", str(proj))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("钩子缺失", H.out(r))

    def test_audit_catches_a_tampered_hook(self):
        proj = self.fresh("03")
        hook = H.hooks_dir(proj) / "pre-commit"
        hook.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8", newline="\n")
        r = maintain("audit", str(proj))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("钩子被改", H.out(r))

    def test_audit_catches_check_py_drift(self):
        proj = self.fresh("03")
        self.assertEqual(maintain("lock", str(proj)).returncode, 0)
        (proj / "scripts" / "check.py").write_text(
            (proj / "scripts" / "check.py").read_text(encoding="utf-8") + "\n# 手改\n",
            encoding="utf-8", newline="\n")
        r = maintain("audit", str(proj))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("check.py 漂移", H.out(r))

    def test_audit_flags_an_illegal_merged_board(self):
        """I-004 的真实形状：两条分支各自合法，合进 main 后是同人两张 doing 卡——merge 不跑钩子。"""
        proj = self.fresh("03")
        base = H.git(proj, "rev-parse", "HEAD").stdout.strip()
        H.write_card(proj, "T-001", status="doing", assignee="[solo]", allowed=["  - docs/"])
        H.git(proj, "add", "backlog/tasks/T-001.md")
        self.assertEqual(H.git(proj, "commit", "-q", "-m", "分支 A：领 T-001").returncode, 0)
        wt2 = self.tmp / "wt2"
        self.assertEqual(H.git(proj, "worktree", "add", "-q", str(wt2), "-b", "b2",
                               base).returncode, 0)
        H.git(wt2, "config", "user.name", "solo-b")
        H.git(wt2, "config", "user.email", "solo-b@invalid")
        H.git(wt2, "config", "core.autocrlf", "false")
        H.write_card(wt2, "T-002", status="doing", assignee="[solo]", allowed=["  - scripts/"])
        H.git(wt2, "add", "backlog/tasks/T-002.md")
        self.assertEqual(H.git(wt2, "commit", "-q", "-m", "分支 B：领 T-002").returncode, 0,
                         "每条分支当时都合法——这正是缺口成立的前提")
        m = H.git(proj, "merge", "-q", "--no-edit", "b2")
        self.assertEqual(m.returncode, 0, msg=H.out(m))
        self.assertEqual(H.git(proj, "status", "--porcelain").stdout.strip(), "",
                         "合并已入库，没人复查过")
        a = maintain("audit", str(proj))
        self.assertNotEqual(a.returncode, 0)
        self.assertIn("main 合成态违规", H.out(a))
        self.assertIn("认领冲突", H.out(a))

    def test_audit_without_lock_still_runs(self):
        proj = self.fresh("03")
        r = maintain("audit", str(proj))
        self.assertIn("未记录", H.out(r))
        self.assertIn("maintain.py lock", H.out(r), "缺指纹要给补救命令")


if __name__ == "__main__":
    unittest.main()
