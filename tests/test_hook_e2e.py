"""pre-commit 端到端：钩子真拦、合法提交真过（git-for-windows 的 sh 环境）。"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import helpers as H


class HookCase(unittest.TestCase):
    def setUp(self):
        self.tmp = H.tmp_dir()
        self.addCleanup(H.rmtree, self.tmp)

    def build(self, name="proj", cards=(("T-001", {}),)):
        """建项目 → 写卡 → 全量入库（此时钩子未装）→ 装钩子。"""
        parent = self.tmp / name
        parent.mkdir(parents=True)
        proj = H.make_project(parent)
        for cid, kw in cards:
            kw.setdefault("assignee", "[zcode-0926a]")
            kw.setdefault("allowed", ["  - docs/"])
            H.write_card(proj, cid, **kw)
        H.git_repo(proj)
        self.assertIsNotNone(H.install_hook(proj), "钩子目录解析失败")
        return proj

    def commit(self, proj, msg):
        return H.git(proj, "commit", "-q", "-m", msg)

    def test_legal_change_passes(self):
        proj = self.build()
        f = proj / "docs" / "ARCHITECTURE.md"
        f.write_text(f.read_text(encoding="utf-8") + "\n补充一段。\n", encoding="utf-8")
        self.assertEqual(H.git(proj, "add", "docs/ARCHITECTURE.md").returncode, 0)
        res = self.commit(proj, "合法改动")
        self.assertEqual(res.returncode, 0, H.out(res))

    def test_version_suffix_blocks_commit(self):
        proj = self.build()
        (proj / "docs" / "报告-final.md").write_text("x", encoding="utf-8")
        H.git(proj, "add", "docs/报告-final.md")
        res = self.commit(proj, "违规命名")
        self.assertNotEqual(res.returncode, 0, "违规提交必须被拦")
        self.assertIn("拦截", H.out(res))
        self.assertEqual(H.git(proj, "rev-list", "--count", "HEAD").stdout.strip(), "1",
                         "被拦的提交不得进历史")

    def test_uncovered_change_blocks_commit(self):
        proj = self.build()
        (proj / "loose.md").write_text("x", encoding="utf-8")
        H.git(proj, "add", "loose.md")
        res = self.commit(proj, "卡外改动")
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("未挂任何任务卡", H.out(res))

    def test_forbidden_path_inside_allowed_blocks_commit(self):
        proj = self.build(
            cards=(("T-001", {"assignee": "[zcode-0926a]"}),
                   ("T-002", {"assignee": "[codex-0926b]",
                              "forbidden": ["  - docs/ARCHITECTURE.md"]}))
        )
        f = proj / "docs" / "ARCHITECTURE.md"
        f.write_text(f.read_text(encoding="utf-8") + "\n越权改动。\n", encoding="utf-8")
        H.git(proj, "add", "docs/ARCHITECTURE.md")
        res = self.commit(proj, "改到他人禁改文件")
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("forbidden_paths", H.out(res))

    def test_hook_is_verbatim_copy_of_skeleton_file(self):
        proj = self.build()
        installed = (H.hooks_dir(proj) / "pre-commit").read_text(encoding="utf-8")
        self.assertEqual(installed, H.HOOK_SRC.read_text(encoding="utf-8"),
                         "装机后的钩子必须与仓库里被审计的那份逐字相同")


if __name__ == "__main__":
    unittest.main()
