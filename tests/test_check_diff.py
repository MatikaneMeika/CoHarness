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


class DiffBuild(unittest.TestCase):
    """公共夹具：建项目 → 写卡 → 按需建仓/装钩子。测试类不互相继承，免得旧用例被重跑一遍。"""

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


class DiffCase(DiffBuild):
    """改动挂卡的判据：pre-commit 要判"进入本次提交的改动"，不是整个工作区。"""

    def test_first_commit_of_whole_skeleton_is_allowed(self):
        proj = self.build(repo="init", hook=True)
        self.assertEqual(H.git(proj, "add", "-A").returncode, 0)
        res = H.git(proj, "commit", "-q", "-m", "骨架本体入库")
        self.assertEqual(res.returncode, 0, H.out(res))
        self.assertEqual(H.git(proj, "rev-list", "--count", "HEAD").stdout.strip(), "1")

    def test_unstaged_changes_do_not_block_other_commits(self):
        proj = self.build(repo="full", hook=True,
                          cards=(("T-001", {"labels": ["role:architect"]}),))
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
        proj = self.build(repo="full", hook=True,
                          cards=(("T-001", {"labels": ["role:architect"]}),))
        (proj / "loose.md").write_text("x\n", encoding="utf-8")
        H.git(proj, "add", "loose.md")
        H.git(proj, "reset", "-q")
        f = proj / "docs" / "ARCHITECTURE.md"
        f.write_text(f.read_text(encoding="utf-8") + "\n补一段。\n", encoding="utf-8")
        H.git(proj, "add", "docs/ARCHITECTURE.md")
        res = H.git(proj, "commit", "-q", "-m", "取消暂存后提交")
        self.assertEqual(res.returncode, 0, H.out(res))

    def test_rename_is_judged_by_new_path(self):
        proj = self.build(repo="full", cards=(("T-001", {"labels": ["role:architect"]}),))
        self.assertEqual(H.git(proj, "mv", "docs/ARCHITECTURE.md", "docs/ARCH-NEW.md").returncode, 0)
        res = H.check(proj, "--diff")
        self.assertEqual(res.returncode, 0, msg=H.out(res))

    def test_deletion_inside_card_is_legal_outside_is_not(self):
        proj = self.build(repo="full", cards=(("T-001", {"labels": ["role:architect"]}),))
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


class OwnershipGate(DiffBuild):
    """I-005 的机械核：所有权表里"具体路径 + 角色一览里的具体角色"的行，提交时真拦。

    表是授权的总裁决（AGENTS.md 裁决句"以表为准、扩权先改表"），但认领者写的是
    harness 标识、表里写的是角色，两者之间唯一的桥梁是卡上的 `role:` 标签——
    "同一会话可身兼多角"（角色一览），所以判的是"卡有没有声明它以这个角色行事"，
    不是"assignee 是不是那个角色"。模板行/散文行判不了，如实报数留给审核人。
    """

    def stage_arch_edit(self, proj, name="docs/ARCHITECTURE.md"):
        f = proj / name
        f.write_text(f.read_text(encoding="utf-8") + "\n补一段。\n", encoding="utf-8")
        self.assertEqual(H.git(proj, "add", name).returncode, 0)

    def test_governed_file_without_role_label_is_blocked(self):
        proj = self.build(repo="full")          # 卡 allowed=docs/，无 role 标签
        self.stage_arch_edit(proj)
        res = H.check(proj, "--diff")
        self.assertNotEqual(res.returncode, 0, msg=H.out(res))
        self.assertIn("[所有权]", H.out(res))
        self.assertIn("扩权先改表", H.out(res))

    def test_declared_role_label_passes(self):
        proj = self.build(repo="full", cards=(("T-001", {"labels": ["role:architect"]}),))
        self.stage_arch_edit(proj)
        res = H.check(proj, "--diff")
        self.assertEqual(res.returncode, 0, msg=H.out(res))

    def test_broad_card_that_stays_off_governed_paths_passes(self):
        proj = self.build(repo="full")
        (proj / "docs" / "notes.md").write_text("随手记\n", encoding="utf-8")
        H.git(proj, "add", "docs/notes.md")
        res = H.check(proj, "--diff")
        self.assertEqual(res.returncode, 0, msg=H.out(res))
        self.assertIn("[所有权]", H.out(res))   # 表在场就要说话：报核对了多少行

    def test_rename_out_of_governed_path_is_caught_by_old_path(self):
        proj = self.build(repo="full")
        self.assertEqual(H.git(proj, "mv", "docs/ARCHITECTURE.md",
                               "docs/ARCH-NEW.md").returncode, 0)
        res = H.check(proj, "--diff")
        self.assertNotEqual(res.returncode, 0, msg=H.out(res))
        self.assertIn("[所有权]", H.out(res))


if __name__ == "__main__":
    unittest.main()
