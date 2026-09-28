"""最小模式（计划书 W4）：`wsc init --minimal` 的零外部依赖起步形态。

要点不是"少装几个文件"，而是**降级必须被写明、且可逆**：
- 关掉的是以任务卡为前提的执法（改动挂卡 / 认领冲突 / 边界交集），AGENTS.md 里逐条写清
- 没关的仍要生效：命名规范、钩子本身
- 恢复路径是"放卡即生效"，不需要重装：check.py 认文件，不认 backlog CLI
"""
import sys
import unittest
from pathlib import Path

import helpers as H


class MinimalMode(unittest.TestCase):
    def setUp(self):
        self.tmp = H.tmp_dir()
        self.addCleanup(H.rmtree, self.tmp)

    def init(self, name, minimal=True):
        dst = self.tmp / name
        argv = ["init", "03", str(dst)] + (["--minimal"] if minimal else [])
        r = H.wsc(*argv)
        self.assertEqual(r.returncode, 0, msg=H.out(r))
        H.git_repo(dst)
        H.git(dst, "config", "user.name", name)
        H.git(dst, "config", "user.email", f"{name}@invalid")
        H.git(dst, "config", "core.autocrlf", "false")
        H.install_hook(dst)
        return dst

    def test_minimal_init_produces_todo_and_no_backlog(self):
        dst = self.init("m1")
        self.assertFalse((dst / "backlog").exists(), "--minimal 不该装 backlog/")
        self.assertTrue((dst / "TODO.md").is_file())
        agents = (dst / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("## 最小模式", agents)
        self.assertIn("改动挂卡", agents, "关闭了哪些执法要写在项目自己的规则里")
        self.assertIn("仍在执法", agents)

    def test_check_passes_and_says_what_is_off(self):
        dst = self.init("m2")
        r = H.check(dst)
        self.assertEqual(r.returncode, 0, msg=H.out(r))
        text = H.out(r)
        self.assertIn("最小模式", text)
        self.assertIn("卡片执法关闭", text)
        self.assertIn("[命名规范] 通过", text)

    def test_out_of_card_commit_is_allowed_in_minimal_mode(self):
        """最小模式没卡可挂：提交任何路径都不该被"改动挂卡"锁死——这是这条降级存在的理由。"""
        dst = self.init("m3")
        (dst / "code").mkdir(exist_ok=True)
        f = dst / "code" / "main.py"
        f.write_text("print('hi')\n", encoding="utf-8")
        self.assertEqual(H.git(dst, "add", "code/main.py").returncode, 0)
        r = H.git(dst, "commit", "-q", "-m", "最小模式下的普通提交")
        self.assertEqual(r.returncode, 0, msg=H.out(r))

    def test_naming_law_still_applies_in_minimal_mode(self):
        dst = self.init("m4")
        (dst / "docs").mkdir(exist_ok=True)
        bad = dst / "docs" / "report-v2.md"
        bad.write_text("还是旧稿\n", encoding="utf-8")
        H.git(dst, "add", "docs/report-v2.md")
        r = H.git(dst, "commit", "-q", "-m", "带 -v2 的文件名")
        self.assertNotEqual(r.returncode, 0, "命名规范不依赖任务卡，最小模式里照样拦")
        self.assertIn("命名", H.out(r))

    def test_sync_reads_the_todo_checklist(self):
        dst = self.init("m5")
        out = H.out(H.wsc("sync", str(dst)))
        self.assertIn("最小模式 TODO.md", out)
        self.assertIn("T-001", out)

    def test_dropping_a_card_back_restores_card_law(self):
        """恢复路径：往最小模式项目里放一张卡，改动挂卡立刻回来——认文件，不认工具。"""
        dst = self.init("m6")
        H.write_card(dst, "T-001", status="doing", assignee="[solo]", allowed=["  - docs/"])
        H.git(dst, "add", "backlog/tasks/T-001.md")
        self.assertEqual(H.git(dst, "commit", "-q", "-m", "补一张卡").returncode, 0,
                         msg="卡片自身属自授权改动")
        stray = dst / "code" / "loose.py"
        stray.write_text("x = 1\n", encoding="utf-8")
        H.git(dst, "add", "code/loose.py")
        r = H.git(dst, "commit", "-q", "-m", "卡外的改动")
        self.assertNotEqual(r.returncode, 0, "有了卡就该重新执法")
        self.assertIn("挂卡", H.out(r))

    def test_full_mode_init_is_unchanged(self):
        dst = self.init("full", minimal=False)
        self.assertTrue((dst / "backlog" / "tasks").is_dir())
        self.assertFalse((dst / "TODO.md").exists())
        self.assertNotIn("## 最小模式", (dst / "AGENTS.md").read_text(encoding="utf-8"))
        r = H.check(dst)
        self.assertEqual(r.returncode, 0, msg=H.out(r))
        self.assertNotIn("卡片执法关闭", H.out(r))


if __name__ == "__main__":
    unittest.main()
