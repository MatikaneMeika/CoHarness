"""改动挂卡的判据：pre-commit 要判"进入本次提交的改动"，不是整个工作区。

复现（改动前红）：全新实例化的项目 `git add -A && git commit` 被自己的钩子拦死
（骨架本体每个文件都"未挂任何任务卡"），首个提交只能 --no-verify —— README 的
"克隆走就能用"当场破。另一例：工作区里躺着没 add 的文件，会拦住一次与它无关的提交。
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import helpers as H


class DiffCase(unittest.TestCase):
    def setUp(self):
        self.tmp = H.tmp_dir()
        self.addCleanup(H.rmtree, self.tmp)

    def build(self, name="proj", cards=(("T-001", {}),), repo="none", hook=False):
        """repo: none=不建仓库 / init=只 git init / full=git init 并全量入库"""
        parent = self.tmp / name
        parent.mkdir(parents=True)
        proj = H.make_project(parent)
        for cid, kw in cards:
            kw.setdefault("assignee", "[zcode-0926a]")
            kw.setdefault("allowed", ["  - docs/"])
            H.write_card(proj, cid, **kw)
        if repo == "init":
            H.git(proj, "init", "-q", "--initial-branch=main")
        elif repo == "full":
            H.git_repo(proj)
        if hook:
            self.assertIsNotNone(H.install_hook(proj))
        return proj

    def test_first_commit_of_whole_skeleton_is_allowed(self):
        proj = self.build(repo="init", hook=True)
        self.assertEqual(H.git(proj, "add", "-A").returncode, 0)
        res = H.git(proj, "commit", "-q", "-m", "骨架本体入库")
        self.assertEqual(res.returncode, 0, H.out(res))
        self.assertEqual(H.git(proj, "rev-list", "--count", "HEAD").stdout.strip(), "1")

    def test_unstaged_changes_do_not_block_other_commits(self):
        proj = self.build(repo="full", hook=True)
        (proj / "scratch.md").write_text("没打算提交的草稿\n", encoding="utf-8")
        f = proj / "docs" / "ARCHITECTURE.md"
        f.write_text(f.read_text(encoding="utf-8") + "\n补一段。\n", encoding="utf-8")
        self.assertEqual(H.git(proj, "add", "docs/ARCHITECTURE.md").returncode, 0)
        res = H.git(proj, "commit", "-q", "-m", "只提交卡内改动")
        self.assertEqual(res.returncode, 0, H.out(res))

    def test_staged_uncovered_file_is_blocked(self):
        proj = self.build(repo="full", hook=True)
        (proj / "loose.md").write_text("x\n", encoding="utf-8")
        H.git(proj, "add", "loose.md")
        res = H.git(proj, "commit", "-q", "-m", "卡外改动")
        self.assertNotEqual(res.returncode, 0, H.out(res))
        self.assertIn("未挂任何任务卡", H.out(res))

    def test_unstaging_a_file_frees_the_commit(self):
        proj = self.build(repo="full", hook=True)
        (proj / "loose.md").write_text("x\n", encoding="utf-8")
        H.git(proj, "add", "loose.md")
        H.git(proj, "reset", "-q")
        f = proj / "docs" / "ARCHITECTURE.md"
        f.write_text(f.read_text(encoding="utf-8") + "\n补一段。\n", encoding="utf-8")
        H.git(proj, "add", "docs/ARCHITECTURE.md")
        res = H.git(proj, "commit", "-q", "-m", "取消暂存后提交")
        self.assertEqual(res.returncode, 0, H.out(res))

    def test_rename_is_judged_by_new_path(self):
        proj = self.build(repo="full")
        self.assertEqual(H.git(proj, "mv", "docs/ARCHITECTURE.md", "docs/ARCH-NEW.md").returncode, 0)
        res = H.check(proj, "--diff")
        self.assertEqual(res.returncode, 0, msg=H.out(res))

    def test_deletion_inside_card_is_legal_outside_is_not(self):
        proj = self.build(repo="full")
        H.git(proj, "rm", "-q", "docs/ARCHITECTURE.md")
        res = H.check(proj, "--diff")
        self.assertEqual(res.returncode, 0, msg=H.out(res))

        proj2 = self.build("proj2", repo="full")
        (proj2 / "extra.md").write_text("x\n", encoding="utf-8")
        H.git(proj2, "add", "extra.md")
        self.assertEqual(H.git(proj2, "commit", "-q", "-m", "入库").returncode, 0)
        H.git(proj2, "rm", "-q", "extra.md")
        res = H.check(proj2, "--diff")
        self.assertNotEqual(res.returncode, 0, msg=H.out(res))
        self.assertIn("未挂任何任务卡", H.out(res))

    def test_non_git_project_skips_with_notice(self):
        proj = self.build(cards=())
        res = H.check(proj, "--diff")
        self.assertEqual(res.returncode, 0, msg=H.out(res))
        self.assertIn("跳过", H.out(res))

    def test_empty_staging_area_is_reported_as_pass(self):
        proj = self.build(repo="full")
        res = H.check(proj, "--diff")
        self.assertEqual(res.returncode, 0, msg=H.out(res))
        self.assertIn("暂存", H.out(res))


if __name__ == "__main__":
    unittest.main()
