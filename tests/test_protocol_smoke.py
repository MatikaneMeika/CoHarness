"""协议冒烟：多 harness 并行的关键提交序列，按"正确行为"写断言。

计划书 W2 的最小本地版（原生 git + 手写卡，不需要 backlog/specify/git-wt）。
两类断言分开：
- 硬断言：现在就该成立的（首次入库、两 harness 并行、一 harness 一卡的门禁、常驻规则卡绕行）
- expectedFailure：规则缺口 I-001（看板状态流转与 improvements 登记没有授权通道）。
  I-001 晋升、把放行写进 check.py 本体后，这两条会变成 unexpected success 报错 ——
  那就是摘掉标记、改硬断言的信号。
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

    def test_d_resident_card_workaround_is_executable(self):
        """绕行要真能跑：认领常驻规则卡 → 登记 I-001 → 提交进 main → improve 读得到。"""
        proj = self.fresh_project()
        self.assertEqual(self.commit(proj, "骨架入库").returncode, 0)
        board = proj / BOARD
        board.write_text(board.read_text(encoding="utf-8").replace(
            "status: todo\nassignee: []", "status: doing\nassignee: [qoder-0928a]"),
            encoding="utf-8")
        res = self.commit(proj, "认领常驻卡", [BOARD])
        self.assertEqual(res.returncode, 0, msg=H.out(res))

        ledger = proj / ".agent" / "improvements.md"
        ledger.write_text(ledger.read_text(encoding="utf-8") + (
            "| I-001 | 2026-09-28 | 规则 | 认领/状态流转/登记 | 三类合法提交无授权通道 | "
            "卡与登记自授权，或常驻规则卡 | 冒烟步序复现，见 tests/test_protocol_smoke.py | 登记 |\n"),
            encoding="utf-8")
        res = self.commit(proj, "登记 I-001", [".agent/improvements.md"])
        self.assertEqual(res.returncode, 0, msg=H.out(res))
        listed = H.out(H.wsc("improve", str(proj)))
        self.assertIn("I-001", listed)
        self.assertIn("[登记]", listed)

    @unittest.expectedFailure
    def test_e_claim_commit_should_not_need_an_extra_card(self):
        """缺口 I-001：改自己卡的 assignee/status 就是协议规定的认领动作，不该再被要求挂卡。"""
        proj = self.fresh_project(extra_cards=(("T-021", {"status": "todo", "assignee": "[]"}),))
        self.assertEqual(self.commit(proj, "建卡入库").returncode, 0)
        target = proj / "backlog" / "tasks" / "T-021.md"
        target.write_text(target.read_text(encoding="utf-8").replace(
            "status: todo\nassignee: []", "status: doing\nassignee: [zcode-0926a]"),
            encoding="utf-8")
        self.assertEqual(self.commit(proj, "认领 T-021", ["backlog/tasks/T-021.md"]).returncode, 0)

    @unittest.expectedFailure
    def test_f_registration_commit_should_not_need_a_card(self):
        """缺口 I-001：全局禁令第 7 条要求登记，执法却把登记拦住。"""
        proj = self.fresh_project()
        self.assertEqual(self.commit(proj, "骨架入库").returncode, 0)
        ledger = proj / ".agent" / "improvements.md"
        ledger.write_text(ledger.read_text(encoding="utf-8") + (
            "| I-009 | 2026-09-28 | 规则 | 登记 | 登记被拦 | 自授权 | 冒烟复现 | 登记 |\n"),
            encoding="utf-8")
        self.assertEqual(self.commit(proj, "登记 I-009", [".agent/improvements.md"]).returncode, 0)


if __name__ == "__main__":
    unittest.main()
