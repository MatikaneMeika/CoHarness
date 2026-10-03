"""maintain.py：装机指纹、schema 迁移、只读体检（计划书 W9 + W12）。

migrate 的默认必须是 dry-run 且落盘前先建备份分支——它改的是别人项目里的规则文件；
audit 必须一个字都不写，因为它要在"项目可能已经漂了"的场景下安全地跑。
v1→v2 的升级步骤就是本轮真实做过的四件事，不是编的演示。
"""
import hashlib
import json
import importlib.util
import re
import sys
import unittest
from pathlib import Path

import helpers as H

MAINTAIN = H.REPO / "maintain.py"


def maintain_module():
    """载入 maintain.py 本体，直接断言内部小节提取器（不在骨架目录留字节码）。"""
    sys.path.insert(0, str(H.REPO))
    spec = importlib.util.spec_from_file_location("coh_maintain_under_test", MAINTAIN)
    mod = importlib.util.module_from_spec(spec)
    prev = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.dont_write_bytecode = prev
    return mod


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

    def fresh(self, name, downgrade=False, parent=None):
        proj = H.make_project(parent or self.tmp, H.REPO / name) if name != "03" else \
            H.make_project(parent or self.tmp)
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
        lock.write_text(text.replace('"schema": 5', f'"schema": {to}'),
                        encoding="utf-8", newline="")

    def make_v1(self, proj):
        """把项目退回本轮改动之前的样子（v1），migrate 才有东西可做。"""
        agents = proj / "AGENTS.md"
        text = agents.read_text(encoding="utf-8")
        wf = proj / ".github" / "workflows" / "coharness.yml"
        wf.unlink(missing_ok=True)
        if "\n### 远端门禁" in text:
            text = re.split(r"\n### 远端门禁", text)[0] + "\n\n## 冲突裁决顺序" + \
                   text.split("## 冲突裁决顺序", 1)[1]
        text = re.split(r"\n## 降级行为", text)[0]
        text = text.replace("wsc.py claim", "task edit -s doing")
        text = text.replace(str(H.REPO), "<CoHarness>")
        # schema 声明行留着：这些测试都补了指纹（migrate 信指纹，schema 以指纹为准），
        # 留着它与骨架一致，v4→v5 的 AGENTS.md 三方合并就少一个无谓的冲突面
        agents.write_text(text + "\n", encoding="utf-8", newline="\n")
        gi = proj / ".gitignore"
        gi.write_text(gi.read_text(encoding="utf-8").replace(".agent/telemetry.jsonl", "telemetry.off"),
                      encoding="utf-8", newline="\n")
        proto = proj / ".agent" / "workflows" / "parallel-protocol.md"
        proto.write_text(proto.read_text(encoding="utf-8").replace(str(H.REPO), "<骨架库>"),
                         encoding="utf-8", newline="\n")

    def test_lock_is_portable_no_machine_paths(self):
        """指纹要能提交进项目仓库：里面不许有本机绝对路径。"""
        proj = self.fresh("03")
        self.assertEqual(maintain("lock", str(proj)).returncode, 0)
        text = self.proj_lock(proj).read_text(encoding="utf-8")
        self.assertNotIn(str(H.REPO), text)
        self.assertNotIn(str(self.tmp), text)
        self.assertIn("可以提交", H.out(maintain("lock", str(proj))))

    def test_lock_records_the_fingerprint(self):
        proj = self.fresh("03")
        r = maintain("lock", str(proj))
        self.assertEqual(r.returncode, 0, msg=H.out(r))
        lock = (proj / ".agent" / "skeleton.lock")
        self.assertTrue(lock.is_file())
        text = lock.read_text(encoding="utf-8")
        self.assertIn("03-multi-harness-project", text)
        self.assertIn('"schema": 5', text)
        self.assertRegex(text, r'"check_sha256": "[0-9a-f]{12}"')

    def test_schema_lists_upgrade_steps(self):
        out = H.out(maintain("schema"))
        self.assertIn("骨架 schema 版本：5", out)
        self.assertIn("v1 -> v2", out)
        self.assertIn("v2 -> v3", out)
        self.assertIn("v3 -> v4", out)
        self.assertIn("v4 -> v5", out)

    def test_sha_normalizes_line_endings_and_keeps_binary(self):
        import maintain
        lf = self.tmp / "lf.txt"
        crlf = self.tmp / "crlf.txt"
        lf.write_bytes(b"a\nb\n")
        crlf.write_bytes(b"a\r\nb\r\n")
        self.assertEqual(maintain._sha(lf), maintain._sha(crlf),
                         "文本哈希必须先归一行尾，否则 CRLF 检出会漂")
        raw = b"\xff\r\n\x00\x01"
        binary = self.tmp / "binary.dat"
        binary.write_bytes(raw)
        self.assertEqual(maintain._sha(binary), hashlib.sha256(raw).hexdigest()[:12],
                         "二进制必须按原始字节哈希，不能被行尾归一误伤")

    def test_migrate_dry_run_writes_nothing(self):
        proj = self.fresh("03", downgrade=True)
        self.assertEqual(maintain("lock", str(proj)).returncode, 0)
        self.downgrade_schema(self.proj_lock(proj), 1)
        before = tree_hash(proj)
        r = maintain("migrate", str(proj))
        self.assertEqual(r.returncode, 0, msg=H.out(r))
        out = H.out(r)
        self.assertIn("dry-run", out)
        self.assertIn("待改", out)
        self.assertIn("降级行为", out)
        self.assertIn("wsc claim", out)
        self.assertIn("待复制", out)
        self.assertIn("待补", out)
        self.assertFalse((proj / ".github" / "workflows" / "coharness.yml").exists(),
                         "dry-run 不许复制 workflow")
        self.assertEqual(tree_hash(proj), before, "dry-run 不许写盘")

    def test_migrate_yes_applies_and_backs_up(self):
        proj = self.fresh("03", downgrade=True)
        self.assertEqual(maintain("lock", str(proj)).returncode, 0)
        self.downgrade_schema(self.proj_lock(proj), 1)
        r = maintain("migrate", str(proj), "--yes")
        self.assertEqual(r.returncode, 0, msg=H.out(r))
        self.assertIn("已建备份分支", H.out(r))
        branches = H.git(proj, "branch", "--list", "coh-backup-*").stdout
        self.assertIn("coh-backup-", branches)
        agents = (proj / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("## 降级行为", agents)
        self.assertIn("wsc.py claim", agents)
        self.assertNotIn("<CoHarness>", agents)
        self.assertNotIn("<骨架库>", agents, "AGENTS.md 里指向 ROUTER 的占位符也要代入绝对路径")
        self.assertIn(".agent/telemetry.jsonl", (proj / ".gitignore").read_text(encoding="utf-8"))
        self.assertNotIn("<骨架库>", (proj / ".agent" / "workflows" /
                                    "parallel-protocol.md").read_text(encoding="utf-8"))
        wf = proj / ".github" / "workflows" / "coharness.yml"
        self.assertTrue(wf.is_file(), "migrate 必须把远端门禁 workflow 带进老项目")
        self.assertIn("--names --tasks --no-track", wf.read_text(encoding="utf-8"))
        self.assertIn('"schema": 5', (proj / ".agent" / "skeleton.lock").read_text(encoding="utf-8"))

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
        self.assertIn('"schema": 5', lock.read_text(encoding="utf-8"))
        self.downgrade_schema(lock, 2)
        dry = maintain("migrate", str(proj))
        self.assertIn("待迁移 .cursorrules", H.out(dry))
        self.assertTrue((proj / ".cursorrules").exists(), "dry-run 不该删旧文件")
        yes = maintain("migrate", str(proj), "--yes")
        self.assertEqual(yes.returncode, 0, msg=H.out(yes))
        self.assertFalse((proj / ".cursorrules").exists())
        self.assertTrue((proj / ".cursor" / "rules" / "coharness.mdc").exists())
        self.assertIn('"schema": 5', lock.read_text(encoding="utf-8"))

    def test_migrate_v2_to_v3_does_not_invent_adapters(self):
        proj = self.fresh("03")
        self.assertEqual(maintain("lock", str(proj)).returncode, 0)
        self.downgrade_schema(self.proj_lock(proj), 2)
        self.assertEqual(maintain("migrate", str(proj), "--yes").returncode, 0)
        for rel in ("CLAUDE.md", ".cursor/rules/coharness.mdc", ".windsurf/rules/coharness.md"):
            self.assertFalse((proj / rel).exists(), f"没要过适配指针的项目不该被生成 {rel}")

    def test_migrate_is_idempotent(self):
        proj = self.fresh("03", downgrade=True)
        self.assertEqual(maintain("lock", str(proj)).returncode, 0)
        self.downgrade_schema(self.proj_lock(proj), 1)
        self.assertEqual(maintain("migrate", str(proj), "--yes").returncode, 0)
        second = maintain("migrate", str(proj))
        self.assertIn("已是最新 schema", H.out(second))

    def _write_v3_check(self, proj):
        old = H.out(H.git(H.REPO, "show", "1617d1c:03-multi-harness-project/scripts/check.py"))
        (proj / "scripts" / "check.py").write_text(old, encoding="utf-8", newline="\n")
        self.assertEqual(maintain("lock", str(proj)).returncode, 0)
        lock = json.loads(self.proj_lock(proj).read_text(encoding="utf-8"))
        lock["skeleton_commit"] = "1617d1c"
        lock["schema"] = 3
        self.proj_lock(proj).write_text(json.dumps(lock, ensure_ascii=False, indent=1) + "\n",
                                       encoding="utf-8", newline="\n")
        return lock

    def test_migrate_v3_to_v5_merges_check_py_and_brings_remote_gate(self):
        """v3 老项目一路迁到最新：check.py 按 1617d1c 基线三方合并（v3→v4），再复制远端门禁
        workflow + AGENTS.md 合并补「远端门禁」小节（v4→v5）；幂等。"""
        proj = self.fresh("03")
        self._write_v3_check(proj)
        agents = proj / "AGENTS.md"
        agents.write_text(H.out(H.git(H.REPO, "show", "1617d1c:03-multi-harness-project/AGENTS.md")),
                          encoding="utf-8", newline="\n")
        wf = proj / ".github" / "workflows" / "coharness.yml"
        wf.unlink(missing_ok=True)
        dry = maintain("migrate", str(proj))
        self.assertEqual(dry.returncode, 0, msg=H.out(dry))
        self.assertIn("待复制", H.out(dry))
        self.assertIn("待补", H.out(dry))
        self.assertFalse(wf.exists(), "dry-run 不许复制 workflow")
        r = maintain("migrate", str(proj), "--yes")
        self.assertEqual(r.returncode, 0, msg=H.out(r))
        self.assertIn("v3 -> v4", H.out(r))
        self.assertIn("v4 -> v5", H.out(r))
        check = proj / "scripts" / "check.py"
        self.assertIn("ownership_rows", check.read_text(encoding="utf-8"))
        self.assertTrue(wf.is_file())
        wf_text = wf.read_text(encoding="utf-8")
        self.assertIn("--names --tasks --no-track", wf_text)
        self.assertIn("merge_group:", wf_text, "迁移后的 workflow 必须带 merge_group 预置")
        self.assertIn("permissions:\n  contents: read", wf_text, "迁移后的 workflow 必须带最小权限")
        self.assertIn("github.event.merge_group.base_sha", wf_text,
                      "迁移后的 workflow 必须为 merge_group 提供基线")
        self.assertIn("远端门禁", agents.read_text(encoding="utf-8"))
        self.assertEqual(json.loads(self.proj_lock(proj).read_text(encoding="utf-8"))["schema"], 5)
        again = maintain("migrate", str(proj))
        self.assertIn("已是最新 schema", H.out(again))

    def test_migrate_v3_without_lock_uses_builtin_baseline_and_injects_remote_gate(self):
        """PoseWise_Health 形状：无指纹的 schema 3 老项目也能安全升到 5。

        旧实现把“指纹里没有 skeleton_commit”当冲突，直接卡死预检；lock 补指纹又只会记当前
        HEAD，导致 base=当前骨架、升级被静默跳过。本用例钉住内置历史基线 + 微创补远端门禁。
        """
        proj = self.fresh("03")
        old_check = H.out(H.git(H.REPO, "show", "1617d1c:03-multi-harness-project/scripts/check.py"))
        (proj / "scripts" / "check.py").write_text(old_check, encoding="utf-8", newline="\n")
        old_agents = H.out(H.git(H.REPO, "show", "1617d1c:03-multi-harness-project/AGENTS.md"))
        (proj / "AGENTS.md").write_text(old_agents, encoding="utf-8", newline="\n")
        self.proj_lock(proj).unlink(missing_ok=True)
        wf = proj / ".github" / "workflows" / "coharness.yml"
        wf.unlink(missing_ok=True)
        r = maintain("migrate", str(proj), "--yes")
        self.assertEqual(r.returncode, 0, msg=H.out(r))
        self.assertIn("内置基线", H.out(r))
        self.assertIn("has_unchecked", (proj / "scripts" / "check.py").read_text(encoding="utf-8"))
        self.assertTrue(wf.is_file())
        agents = (proj / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("### 远端门禁", agents)
        self.assertIn("| 骨架 schema | 5 |", agents)
        self.assertEqual(json.loads(self.proj_lock(proj).read_text(encoding="utf-8"))["schema"], 5)

    def test_migrate_merge_conflict_refuses_to_overwrite(self):
        """两条三方合并冲突路径都拒绝覆盖：check.py（v3→v4，本地改过基线行）与 AGENTS.md
        （v4→v5，本地在「远端门禁」小节插入点写了自家内容）。冲突时预检退出：不落盘、不建
        备份分支、schema 不推进。"""
        proj = self.fresh("03")
        self._write_v3_check(proj)
        check = proj / "scripts" / "check.py"
        local = check.read_text(encoding="utf-8").replace("仍为 todo", "仍为 本地状态")
        check.write_text(local, encoding="utf-8", newline="\n")
        self.assertEqual(maintain("lock", str(proj)).returncode, 0)
        lock = json.loads(self.proj_lock(proj).read_text(encoding="utf-8"))
        lock["skeleton_commit"] = "1617d1c"
        lock["schema"] = 3
        self.proj_lock(proj).write_text(json.dumps(lock, ensure_ascii=False, indent=1) + "\n",
                                       encoding="utf-8", newline="\n")
        r = maintain("migrate", str(proj), "--yes")
        self.assertNotEqual(r.returncode, 0, msg=H.out(r))
        self.assertIn("三方合并失败", H.out(r))
        self.assertEqual(check.read_text(encoding="utf-8"), local, "冲突时不得覆盖本地 check.py")
        self.assertEqual(json.loads(self.proj_lock(proj).read_text(encoding="utf-8"))["schema"], 3)
        branches = H.git(proj, "branch", "--list", "coh-backup-*").stdout
        self.assertNotIn("coh-backup-", branches, "预检失败不得留下备份分支")
        proj2 = self.fresh("03", parent=self.tmp / "v45conflict")
        agents2 = proj2 / "AGENTS.md"
        old = H.out(H.git(H.REPO, "show", "1617d1c:03-multi-harness-project/AGENTS.md"))
        marker = "## 冲突裁决顺序"
        own = old.replace(marker, "### 远端门禁\n\n本项目自定义旧门禁。\n\n" + marker, 1)
        agents2.write_text(own, encoding="utf-8", newline="\n")
        wf2 = proj2 / ".github" / "workflows" / "coharness.yml"
        wf2.unlink(missing_ok=True)
        self.assertEqual(maintain("lock", str(proj2)).returncode, 0)
        lock2 = json.loads(self.proj_lock(proj2).read_text(encoding="utf-8"))
        lock2["skeleton_commit"] = "1617d1c"
        lock2["schema"] = 4
        self.proj_lock(proj2).write_text(json.dumps(lock2, ensure_ascii=False, indent=1) + "\n",
                                        encoding="utf-8", newline="\n")
        dry2 = maintain("migrate", str(proj2))
        self.assertIn("待复制", H.out(dry2), "schema 4 项目 dry-run 要显示将复制 workflow")
        self.assertFalse(wf2.exists(), "dry-run 不许复制 workflow")
        r2 = maintain("migrate", str(proj2), "--yes")
        self.assertNotEqual(r2.returncode, 0, msg=H.out(r2))
        self.assertIn("已有不同的「远端门禁」小节", H.out(r2))
        self.assertEqual(agents2.read_text(encoding="utf-8"), own, "冲突时不得覆盖本地 AGENTS.md")
        self.assertFalse(wf2.exists(), "预检失败连 workflow 也不该复制")
        self.assertEqual(json.loads(self.proj_lock(proj2).read_text(encoding="utf-8"))["schema"], 4,
                         "冲突时 schema 不推进")
        branches2 = H.git(proj2, "branch", "--list", "coh-backup-*").stdout
        self.assertNotIn("coh-backup-", branches2, "预检失败不得留下备份分支")

    def test_migrate_v4_to_v5_preserves_local_agents_and_injects_remote_gate(self):
        """远端门禁是小节注入，不是全文合并：项目自己的 AGENTS.md 定制必须原样保留。"""
        proj = self.fresh("03")
        agents = proj / "AGENTS.md"
        old = H.out(H.git(H.REPO, "show", "1617d1c:03-multi-harness-project/AGENTS.md"))
        marker = "## 冲突裁决顺序"
        own = old.replace(marker, "### 本地钩子（第一道门）\n\n本项目自定义的门禁说明。\n\n" + marker, 1)
        agents.write_text(own, encoding="utf-8", newline="\n")
        wf = proj / ".github" / "workflows" / "coharness.yml"
        wf.unlink(missing_ok=True)
        self.assertEqual(maintain("lock", str(proj)).returncode, 0)
        lock = json.loads(self.proj_lock(proj).read_text(encoding="utf-8"))
        lock["skeleton_commit"] = "1617d1c"
        lock["schema"] = 4
        self.proj_lock(proj).write_text(json.dumps(lock, ensure_ascii=False, indent=1) + "\n",
                                       encoding="utf-8", newline="\n")
        r = maintain("migrate", str(proj), "--yes")
        self.assertEqual(r.returncode, 0, msg=H.out(r))
        text = agents.read_text(encoding="utf-8")
        self.assertIn("### 本地钩子", text)
        self.assertIn("### 远端门禁", text)
        expected = maintain_module()._section(
            (H.SKELETON / "AGENTS.md").read_text(encoding="utf-8"), "### 远端门禁")
        self.assertIn(expected, text, "迁移注入的小节必须与骨架 AGENTS.md 逐字同源")
        self.assertTrue(wf.is_file())

    def test_skeleton_detection_uses_lock_before_custom_title(self):
        """ClassObserver 这类项目会把 AGENTS.md 标题改成项目名，锁里的 skeleton 必须先被信任。"""
        proj = self.fresh("03")
        self.assertEqual(maintain("lock", str(proj)).returncode, 0)
        lock = json.loads(self.proj_lock(proj).read_text(encoding="utf-8"))
        lock["schema"] = 3
        self.proj_lock(proj).write_text(json.dumps(lock, ensure_ascii=False, indent=1) + "\n",
                                       encoding="utf-8", newline="\n")
        agents = proj / "AGENTS.md"
        body = agents.read_text(encoding="utf-8").splitlines()
        agents.write_text("# ClassObserver - 自定义论文项目\n" + "\n".join(body[1:]) + "\n",
                          encoding="utf-8", newline="\n")
        out = H.out(maintain("migrate", str(proj)))
        self.assertIn("v3 -> v4", out)
        self.assertNotIn("找不到 AGENTS.md", out)

    def test_sync_prints_drift_hint_without_rewriting_check(self):
        proj = self.fresh("03")
        self.assertEqual(maintain("lock", str(proj)).returncode, 0)
        lock = json.loads(self.proj_lock(proj).read_text(encoding="utf-8"))
        lock["schema"] = 3
        self.proj_lock(proj).write_text(json.dumps(lock, ensure_ascii=False, indent=1) + "\n",
                                       encoding="utf-8", newline="\n")
        check = proj / "scripts" / "check.py"
        before = check.read_text(encoding="utf-8")
        out = H.out(H.wsc("sync", str(proj)))
        self.assertIn("[漂移]", out)
        self.assertEqual(check.read_text(encoding="utf-8"), before, "sync 不自动改项目文件")

    def test_sync_has_no_drift_hint_when_project_is_current(self):
        """指纹 schema 与本体一致时 sync 不许误报漂移（旧实现硬编码 4，对 schema 5 项目误报）。"""
        proj = self.fresh("03")
        self.assertEqual(maintain("lock", str(proj)).returncode, 0)
        out = H.out(H.wsc("sync", str(proj)))
        self.assertNotIn("[漂移]", out)

    def test_sync_drift_hint_uses_precise_capability_marker(self):
        """漂移检测与 maintain 同源：缺 has_unchecked 的 check.py 必须点名它（宽词“审阅意见”会漏报）。"""
        proj = self.fresh("03")
        self.assertEqual(maintain("lock", str(proj)).returncode, 0)
        check = proj / "scripts" / "check.py"
        check.write_text(check.read_text(encoding="utf-8").replace("has_unchecked", "old_marker"),
                         encoding="utf-8", newline="\n")
        out = H.out(H.wsc("sync", str(proj)))
        self.assertIn("[漂移]", out)
        self.assertIn("has_unchecked", out)

    def test_migrate_declares_current_schema_when_row_missing(self):
        """migrate 收尾要把 AGENTS.md 的 schema 声明推到本体版本，否则 lock 退回旧值、项目永远显得落后。"""
        proj = self.fresh("03", downgrade=True)
        agents = proj / "AGENTS.md"
        text = re.sub(r"(?m)^\|\s*骨架 schema\s*\|\s*\d+\s*\|\n", "",
                     agents.read_text(encoding="utf-8"))
        agents.write_text(text, encoding="utf-8", newline="\n")
        self.assertEqual(maintain("lock", str(proj)).returncode, 0)
        self.downgrade_schema(self.proj_lock(proj), 1)
        r = maintain("migrate", str(proj), "--yes")
        self.assertEqual(r.returncode, 0, msg=H.out(r))
        self.assertIn("| 骨架 schema | 5 |", agents.read_text(encoding="utf-8"))
        self.assertEqual(json.loads(self.proj_lock(proj).read_text(encoding="utf-8"))["schema"], 5)

    def test_migrate_demo_runs_green(self):
        """docs/demo/migrate_demo.py 是公开演示，必须真跑通（本轮它曾因 schema 硬编码 4 崩）。"""
        demo = H.REPO / "docs" / "demo" / "migrate_demo.py"
        r = H.run([sys.executable, str(demo)], cwd=H.REPO, timeout=300)
        self.assertEqual(r.returncode, 0, msg=H.out(r))
        self.assertNotIn("[FAIL]", H.out(r))

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

    def test_audit_quick_json_is_read_only_and_stable(self):
        proj = self.fresh("03")
        self.assertEqual(maintain("lock", str(proj)).returncode, 0)
        before = tree_hash(proj)
        first = maintain("audit", str(proj), "--quick", "--json")
        self.assertEqual(first.returncode, 0, msg=H.out(first))
        data = json.loads(first.stdout)
        self.assertTrue(data["quick"])
        self.assertIn("issues", data)
        second = maintain("audit", str(proj), "--quick", "--json")
        self.assertEqual(first.stdout, second.stdout, "--json 输出必须可稳定比对")
        self.assertEqual(tree_hash(proj), before, "audit 不得写工作区")
        self.assertFalse((proj / ".agent" / "telemetry.jsonl").exists())

    def test_audit_full_check_never_tracks(self):
        proj = self.fresh("03")
        self.assertEqual(maintain("lock", str(proj)).returncode, 0)
        before = tree_hash(proj)
        r = maintain("audit", str(proj))
        self.assertEqual(r.returncode, 0, msg=H.out(r))
        self.assertEqual(tree_hash(proj), before)
        self.assertFalse((proj / ".agent" / "telemetry.jsonl").exists(),
                         "audit 内部跑 check.py 必须带 --no-track")

    def test_audit_json_reports_missing_capabilities(self):
        proj = self.fresh("03")
        check = proj / "scripts" / "check.py"
        check.write_text(check.read_text(encoding="utf-8").replace("ownership_rows", "ownership"),
                         encoding="utf-8", newline="\n")
        self.assertEqual(maintain("lock", str(proj)).returncode, 0)
        lock = json.loads(self.proj_lock(proj).read_text(encoding="utf-8"))
        lock["schema"] = 3
        self.proj_lock(proj).write_text(json.dumps(lock, ensure_ascii=False, indent=1) + "\n",
                                       encoding="utf-8", newline="\n")
        r = maintain("audit", str(proj), "--quick", "--json")
        self.assertEqual(r.returncode, 1, msg=H.out(r))
        self.assertIn("ownership_rows", json.loads(r.stdout)["missing_capabilities"])

    def test_audit_flags_missing_review_return_enforcement(self):
        """PoseWise 形状：有 `## 审阅意见` 格式校验、无 `has_unchecked` 返工执法——不得报“规则能力齐全”。

        旧的宽泛标记 `审阅意见` 会被格式校验命中，导致 audit 误报齐全（2026-10-02 对 PoseWise_Health
        实测：audit --quick --json 报 missing_capabilities=[]，但该卡确实停在 done+未勾项无拦截）。
        """
        proj = self.fresh("03")
        check = proj / "scripts" / "check.py"
        text = check.read_text(encoding="utf-8")
        self.assertIn("## 审阅意见", text, "夹具前提：格式校验在位")
        self.assertIn("has_unchecked", text, "夹具前提：新版执法标记在位")
        check.write_text(text.replace("has_unchecked", "unchecked_seen"),
                         encoding="utf-8", newline="\n")
        self.assertEqual(maintain("lock", str(proj)).returncode, 0)
        r = maintain("audit", str(proj), "--quick", "--json")
        self.assertEqual(r.returncode, 1, msg=H.out(r))
        self.assertIn("has_unchecked", json.loads(r.stdout)["missing_capabilities"])

    def test_lock_records_declared_schema_not_body_schema(self):
        """老项目 lock 不能把落后 schema 伪装成最新，否则 migrate 会被静默跳过。"

        2026-10-02 PoseWise_Health（schema 3）实测：maintain.py lock 硬写 SCHEMA=5，会让后续
        migrate 判定“已是最新”而跳过 v3→v4→v5；本用例钉住指纹必须记项目真实版本。
        """
        proj = self.fresh("03")
        agents = proj / "AGENTS.md"
        text = agents.read_text(encoding="utf-8")
        agents.write_text(re.sub(r"(\|\s*骨架 schema\s*\|\s*)\d+", r"\g<1>3", text),
                          encoding="utf-8", newline="\n")
        r = maintain("lock", str(proj))
        self.assertEqual(r.returncode, 0, msg=H.out(r))
        lock = json.loads(self.proj_lock(proj).read_text(encoding="utf-8"))
        self.assertEqual(lock["schema"], 3, "指纹必须记项目真实 schema，而不是本体 SCHEMA")

    def test_lock_backfills_schema3_baseline_instead_of_current_head(self):
        """无指纹的 schema 3 老项目跑 lock 时，骨架基线不能写成当前 HEAD。

        PoseWise_Health 实测：lock 写当前 HEAD 后，migrate 的 base 等于当前骨架，升级被静默跳过。
        """
        proj = self.fresh("03")
        agents = proj / "AGENTS.md"
        agents.write_text(re.sub(r"(\|\s*骨架 schema\s*\|\s*)\d+", r"\g<1>3",
                                 agents.read_text(encoding="utf-8")),
                          encoding="utf-8", newline="\n")
        r = maintain("lock", str(proj))
        self.assertEqual(r.returncode, 0, msg=H.out(r))
        lock = json.loads(self.proj_lock(proj).read_text(encoding="utf-8"))
        self.assertEqual(lock["schema"], 3)
        self.assertEqual(lock["skeleton_commit"], "1617d1c")

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

    def test_skeleton_declares_its_schema_and_it_matches_maintain(self):
        """骨架项目卡声明的 schema 必须与 maintain.SCHEMA 一致——两个来源不许漂。

        schema 升版时，migrate 步（maintain.py）与四套骨架卡里的声明行必须同一提交落地，
        否则新实例化的项目会声明一个 migrate 迁不到的版本。"""
        import maintain
        pattern = r"^\|\s*骨架 schema\s*\|\s*(\d+)\s*\|"
        for sk in ("01-solo-code", "02-study-office", "03-multi-harness-project",
                   "04-doc-production"):
            text = (H.REPO / sk / "AGENTS.md").read_text(encoding="utf-8")
            m = re.search(pattern, text, re.M)
            self.assertTrue(m, f"{sk} 的项目卡没声明骨架 schema")
            self.assertEqual(int(m.group(1)), maintain.SCHEMA,
                             f"{sk} 声明的 schema 与 maintain.SCHEMA 不一致")

    def test_migrate_covers_the_named_v1_residue(self):
        """计划书点名的三项 v1 遗留：常驻规则卡、英文看板列、缺自授权的旧 check.py。"""
        proj = H.make_project(self.tmp)
        (proj / "backlog" / "tasks" / "T-000-board.md").write_text(
            "---\nid: T-000\ntitle: 常驻规则卡\nstatus: todo\nassignee: []\n---\n\n"
            "## 边界\nallowed_paths:\n  - docs/\nforbidden_paths:\n  - AGENTS.md\n",
            encoding="utf-8", newline="")
        (proj / "backlog" / "config.yml").write_text(
            "columns: [To Do, In Progress, Done]\n", encoding="utf-8", newline="")
        check = proj / "scripts" / "check.py"
        check.write_text(check.read_text(encoding="utf-8").replace("SELF_AUTHORIZED", "OLD_NAME"),
                         encoding="utf-8", newline="")
        H.git_repo(proj)
        H.git(proj, "config", "user.name", "v1")
        H.git(proj, "config", "user.email", "v1@invalid")
        self.assertEqual(maintain("lock", str(proj)).returncode, 0)
        self.downgrade_schema(self.proj_lock(proj), 1)
        dry = maintain("migrate", str(proj))
        out = H.out(dry)
        for needle in ("待删除", "T-000-board.md", "待改写", "statuses", "待刷新"):
            self.assertIn(needle, out)
        self.assertTrue((proj / "backlog" / "tasks" / "T-000-board.md").exists(), "dry-run 不删文件")
        self.assertEqual(maintain("migrate", str(proj), "--yes").returncode, 0)
        self.assertFalse((proj / "backlog" / "tasks" / "T-000-board.md").exists())
        self.assertIn("statuses: [todo, doing, review, done]",
                      (proj / "backlog" / "config.yml").read_text(encoding="utf-8"))
        self.assertIn("SELF_AUTHORIZED", check.read_text(encoding="utf-8"))
        # 落盘后指纹记到当前 schema：再跑一次不该重复改文件，也不该再报待办
        again = H.out(maintain("migrate", str(proj)))
        self.assertIn("已是最新 schema", again)
        self.assertNotIn("待", again.split("== migrate", 1)[-1])

    def test_schema_can_come_from_the_project_card(self):
        """没有指纹的老项目：migrate 该从 AGENTS.md 的声明读 schema，而不是硬按 v1 猜。

        声明值直接从项目卡里读出来断言——骨架升版改声明值时不影响这条测试的意图。"""
        proj = self.fresh("03")
        card = re.search(r"^\|\s*骨架 schema\s*\|\s*(\d+)\s*\|",
                         (proj / "AGENTS.md").read_text(encoding="utf-8"), re.M)
        self.assertTrue(card, "骨架项目卡里必须有 schema 声明行")
        r = maintain("migrate", str(proj))
        self.assertEqual(r.returncode, 0, msg=H.out(r))
        out = H.out(r)
        self.assertIn("AGENTS.md 声明", out)
        self.assertIn(f"当前 schema={card.group(1)}", out)

    def test_audit_flags_a_ledger_written_outside_agent(self):
        proj = self.fresh("03")
        (proj / "docs" / "改进台账.md").write_text(
            "| 编号 | 日期 | 类别 | 场景 | 问题 | 提议 | 证据 | 状态 |\n"
            "|---|---|---|---|---|---|---|---|\n"
            "| I-001 | 2026-09-28 | 规则 | 认领 | 问题 | 提议 | 证据 | 登记 |\n",
            encoding="utf-8", newline="")
        r = maintain("audit", str(proj))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("登记表写错位置", H.out(r))
        self.assertIn("改进台账.md", H.out(r))

    def test_audit_names_merge_entries_without_convicting_them(self):
        """merge 不跑钩子——audit 点名这条入口，但不因为"有 merge"就定罪。"""
        proj = self.fresh("03")
        base = H.git(proj, "rev-parse", "HEAD").stdout.strip()
        H.git(proj, "branch", "side", base)
        H.write_card(proj, "T-101", status="doing", assignee="[ma]", allowed=["  - docs/"])
        H.git(proj, "add", "backlog/tasks/T-101.md")
        self.assertEqual(H.git(proj, "commit", "-q", "-m", "主干：领 T-101").returncode, 0)
        side = self.tmp / "side"
        self.assertEqual(H.git(proj, "worktree", "add", "-q", str(side), "side").returncode, 0)
        H.write_card(side, "T-102", status="doing", assignee="[sb]", allowed=["  - code/"])
        H.git(side, "add", "backlog/tasks/T-102.md")
        self.assertEqual(H.git(side, "commit", "-q", "-m", "分支：领 T-102").returncode, 0)
        m = H.git(proj, "merge", "-q", "--no-edit", "side")
        self.assertEqual(m.returncode, 0, msg=H.out(m))
        self.assertEqual(maintain("lock", str(proj)).returncode, 0)   # 别让"缺指纹"混进这条断言
        r = maintain("audit", str(proj))
        out = H.out(r)
        self.assertIn("[入口] 最近 1 个 merge 提交", out)
        self.assertIn("都不跑 pre-commit", out)
        self.assertNotIn("钩子被改", out)
        self.assertEqual(r.returncode, 0, msg="只有 merge 痕迹不构成问题：" + out)

    def test_audit_without_lock_still_runs(self):
        proj = self.fresh("03")
        r = maintain("audit", str(proj))
        self.assertIn("未记录", H.out(r))
        self.assertIn("maintain.py lock", H.out(r), "缺指纹要给补救命令")


if __name__ == "__main__":
    unittest.main()
