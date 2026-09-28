"""钉住 check.py 的命名规范与 flag 契约（docs/EVOLUTION-PLAN.md:100-111 的手工断言落盘）。"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import helpers as H


class TempProjectCase(unittest.TestCase):
    def setUp(self):
        self.tmp = H.tmp_dir()
        self.addCleanup(H.rmtree, self.tmp)
        self.proj = H.make_project(self.tmp)

    def assertCheck(self, args, rc, *fragments):
        res = H.check(self.proj, *args)
        text = H.out(res)
        self.assertEqual(res.returncode, rc, f"args={args} rc={res.returncode}\n{text}")
        for frag in fragments:
            self.assertIn(frag, text, f"args={args}\n{text}")
        return text


class TestNames(TempProjectCase):
    def test_version_suffix_is_blocked(self):
        (self.proj / "report-final.md").write_text("x", encoding="utf-8")
        self.assertCheck(["--names"], 1, "[命名规范]", "report-final.md")

    def test_clean_tree_passes(self):
        self.assertCheck(["--names"], 0, "[命名规范] 通过")

    def test_chinese_suffix_variants(self):
        for name in ("方案-v2.docx", "报告-副本.md", "稿_final.pdf", "笔记 新版.txt"):
            (self.proj / name).write_text("x", encoding="utf-8")
        text = self.assertCheck(["--names"], 1)
        self.assertEqual(text.count("  - "), 4, text)

    def test_card_titles_are_not_delivery_names(self):
        # SKIP_DIRS 里的卡片标题合法含 final，不该被当成交付文件报错
        H.write_card(self.proj, "T-001", title="final 版验收")
        self.assertCheck(["--names"], 0, "[命名规范] 通过")

    def test_four_flags_and_exit_code_contract(self):
        for flag, label in (("--names", "[命名规范]"), ("--tasks", "[任务卡]"),
                            ("--diff", "[改动挂卡]"), ("--stale", "[stale]")):
            res = H.check(self.proj, flag)
            self.assertIn(res.returncode, (0, 1), f"{flag} -> {res.returncode}")
            self.assertIn(label, H.out(res), flag)

    def test_run_all_prints_conclusion(self):
        res = H.check(self.proj)
        self.assertIn("结论:", H.out(res))


class TestCardFormat(TempProjectCase):
    def test_valid_card_passes(self):
        H.write_card(self.proj, "T-001")
        self.assertCheck(["--tasks"], 0, "[任务卡] 通过（1 张）")

    def test_missing_boundary_section(self):
        p = H.write_card(self.proj, "T-002")
        p.write_text(p.read_text(encoding="utf-8").split("## 边界")[0], encoding="utf-8")
        self.assertCheck(["--tasks"], 1, "T-002.md", '卡体缺 "## 边界" 节')

    def test_multiple_assignees(self):
        H.write_card(self.proj, "T-003", assignee="[zcode-0926a, codex-0926b]")
        self.assertCheck(["--tasks"], 1, "T-003.md", "一卡多 assignee")

    def test_doing_without_assignee(self):
        H.write_card(self.proj, "T-004", status="doing", assignee="[]")
        self.assertCheck(["--tasks"], 1, "T-004.md", "未认领")

    def test_illegal_status(self):
        H.write_card(self.proj, "T-005", status="doing-gone")
        self.assertCheck(["--tasks"], 1, "T-005.md", "status 非法")

    def test_allowed_paths_empty(self):
        H.write_card(self.proj, "T-007", allowed=[])
        self.assertCheck(["--tasks"], 1, "T-007.md", "allowed_paths 为空")

    def test_boundary_path_must_exist(self):
        H.write_card(self.proj, "T-008", allowed=["  - no-such-dir/"])
        self.assertCheck(["--tasks"], 1, "T-008.md", "边界路径不存在: no-such-dir/")

    def test_one_harness_one_doing_card(self):
        H.write_card(self.proj, "T-009")
        H.write_card(self.proj, "T-010")
        self.assertCheck(["--tasks"], 1, "认领冲突", "zcode-0926a")

    def test_two_harnesses_parallel_is_legal(self):
        H.write_card(self.proj, "T-011", assignee="[zcode-0926a]")
        H.write_card(self.proj, "T-012", assignee="[codex-0926b]")
        self.assertCheck(["--tasks"], 0, "[任务卡] 通过（2 张）")

    def test_stale_is_advisory_only(self):
        H.write_card(self.proj, "T-013", updated="2026-01-01 00:00")
        self.assertCheck(["--stale"], 0, "[stale] 提示（不拦截提交）", "T-013.md")

    def test_fresh_card_not_stale(self):
        from datetime import datetime
        H.write_card(self.proj, "T-014", updated=datetime.now().strftime("%Y-%m-%d %H:%M"))
        self.assertCheck(["--stale"], 0, "[stale] 无僵死卡")

    def test_missing_tasks_dir_is_not_a_failure(self):
        self.assertCheck(["--tasks"], 0, "[任务卡] 无任务卡")

    def test_non_card_files_in_tasks_dir_ignored(self):
        d = self.proj / "backlog" / "tasks"
        d.mkdir(parents=True, exist_ok=True)
        (d / "README.md").write_text("# tasks\n\n卡片目录。\n", encoding="utf-8")
        self.assertCheck(["--tasks"], 0, "[任务卡] 无任务卡")


if __name__ == "__main__":
    unittest.main()
