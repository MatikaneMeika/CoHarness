"""协议冒烟：多 harness 并行的关键提交序列，按"正确行为"写断言。

计划书 W2 的最小本地版（原生 git + 手写卡，不需要 backlog/specify/git-wt）。
2026-09-28 之前的两条 expectedFailure（认领、登记不该再挂卡）在 I-001 晋升后已翻成硬断言。
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import helpers as H

BOARD = "backlog/tasks/T-000-board.md"


class ProtocolSmoke(unittest.TestCase):
    def setUp(self):
        self.tmp = H.tmp_dir()
        self.addCleanup(H.rmtree, self.tmp)

    def fresh_project(self, name="pilot", extra_cards=()):
        """按 README 的装机路径走一遍：git init → wsc init 03 →（可选写卡）→ 首次入库。"""
        proj = self.tmp / name
        proj.mkdir(parents=True)
        self.assertEqual(H.git(proj, "init", "-q", "--initial-branch=main").returncode, 0)
        res = H.wsc("init", "03", str(proj))
        self.assertEqual(res.returncode, 0, H.out(res))
        self.assertTrue((H.hooks_dir(proj) / "pre-commit").exists(), "wsc init 应装好钩子")
        for cid, kw in extra_cards:
            H.write_card(proj, cid, **kw)
        return proj

    def commit(self, proj, msg, paths=None):
        args = ["add", "-A"] if paths is None else ["add"] + list(paths)
        self.assertEqual(H.git(proj, *args).returncode, 0)
        return H.git(proj, "commit", "-q", "-m", msg)

    def test_a_first_commit_goes_through_the_hook(self):
        proj = self.fresh_project()
        res = self.commit(proj, "骨架入库")
        self.assertEqual(res.returncode, 0, msg=H.out(res))
        self.assertIn("首次入库", H.out(res))
        self.assertEqual(H.git(proj, "rev-list", "--count", "HEAD").stdout.strip(), "1")

    def test_b_two_harnesses_parallel_on_disjoint_paths(self):
        proj = self.fresh_project(extra_cards=(
            ("T-001", {"assignee": "[zcode-0926a]", "allowed": ["  - docs/"]}),
            ("T-002", {"assignee": "[codex-0926b]", "allowed": ["  - scripts/"]}),
        ))
        self.assertEqual(self.commit(proj, "入库含两张并行卡").returncode, 0)
        (proj / "docs" / "ARCHITECTURE.md").write_text("zcode 改的\n", encoding="utf-8")
        self.assertEqual(self.commit(proj, "zcode 交工", ["docs/ARCHITECTURE.md"]).returncode, 0)
        (proj / "scripts" / "note.md").write_text("codex 改的\n", encoding="utf-8")
        self.assertEqual(self.commit(proj, "codex 交工", ["scripts/note.md"]).returncode, 0)
        self.assertEqual(H.git(proj, "rev-list", "--count", "HEAD").stdout.strip(), "3")

    def test_c_one_harness_two_doing_cards_is_blocked(self):
        proj = self.fresh_project()
        H.write_card(proj, "T-011", assignee="[zcode-0926a]")
        H.write_card(proj, "T-012", assignee="[zcode-0926a]")
        res = self.commit(proj, "双 doing 卡")
        self.assertNotEqual(res.returncode, 0, msg=H.out(res))
        self.assertIn("认领冲突", H.out(res))

    def test_d_claim_commit_needs_no_card(self):
        """I-001 晋升产物：认领 = 改自己的卡 + commit + push main，一步过钩子。"""
        proj = self.fresh_project(extra_cards=(("T-021", {"status": "todo", "assignee": "[]"}),))
        self.assertEqual(self.commit(proj, "建卡入库").returncode, 0)
        target = proj / "backlog" / "tasks" / "T-021.md"
        target.write_text(target.read_text(encoding="utf-8").replace(
            "status: todo", "status: doing").replace("assignee: []", "assignee: [zcode-0926a]"),
            encoding="utf-8")
        res = self.commit(proj, "认领 T-021", ["backlog/tasks/T-021.md"])
        self.assertEqual(res.returncode, 0, msg=H.out(res))
        # 认领完就能在自己边界内交工
        (proj / "docs" / "ARCHITECTURE.md").write_text("认领后交工\n", encoding="utf-8")
        self.assertEqual(self.commit(proj, "交工", ["docs/ARCHITECTURE.md"]).returncode, 0)

    def test_e_registration_commit_needs_no_card(self):
        """I-001 晋升产物：全局禁令第 7 条要求的登记，不该被执法拦住。"""
        proj = self.fresh_project()
        self.assertEqual(self.commit(proj, "骨架入库").returncode, 0)
        ledger = proj / ".agent" / "improvements.md"
        ledger.write_text(ledger.read_text(encoding="utf-8") + (
            "| I-001 | 2026-09-28 | 规则 | 认领/状态流转/登记 | 三类合法提交无授权通道 | "
            "卡与登记自授权 | 并发演练 D0：四条路全 rc=1 | 登记 |\n"), encoding="utf-8")
        res = self.commit(proj, "登记 I-001", [".agent/improvements.md"])
        self.assertEqual(res.returncode, 0, msg=H.out(res))
        self.assertIn("I-001", H.out(H.wsc("improve", str(proj))))

    def test_f_rule_files_are_still_not_self_authorized(self):
        """自授权只覆盖卡片与登记表：规则文件仍不许随实现卡改。"""
        proj = self.fresh_project(extra_cards=(("T-031", {"allowed": ["  - docs/"]}),))
        self.assertEqual(self.commit(proj, "入库").returncode, 0)
        (proj / ".agent" / "roles" / "reviewer.md").write_text("偷偷改规则\n", encoding="utf-8")
        res = self.commit(proj, "改规则", [".agent/roles/reviewer.md"])
        self.assertNotEqual(res.returncode, 0, msg=H.out(res))
        self.assertIn("未挂任何任务卡", H.out(res))

    def test_g_overlapping_todo_card_no_longer_frames_the_owner(self):
        """A3 假阳性回归：同一文件被 doing 与 todo 两张卡覆盖时，已认领的一方不该被诬告。"""
        proj = self.fresh_project(extra_cards=(
            ("T-041", {"assignee": "[zcode-0926a]", "allowed": ["  - docs/"]}),
            ("T-042", {"status": "todo", "assignee": "[]", "allowed": ["  - docs/"]}),
        ))
        self.assertEqual(self.commit(proj, "两张都指向 docs/ 的卡入库").returncode, 0)
        (proj / "docs" / "ARCHITECTURE.md").write_text("T-041 的活\n", encoding="utf-8")
        res = self.commit(proj, "已认领者交工", ["docs/ARCHITECTURE.md"])
        self.assertEqual(res.returncode, 0, msg=H.out(res))

    def test_h_no_resident_card_in_skeleton(self):
        """死锁的根因是"唯一授权来源是一张必须长持的卡"，路修通后它不该再出现。"""
        self.assertFalse((H.SKELETON / BOARD).exists())


if __name__ == "__main__":
    unittest.main()
