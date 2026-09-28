"""并发竞态探针：bare origin + clone + 两个 linked worktree，全程真钩子。

钉住两类东西：
- 硬断言：修好之后必须成立的（自授权认领跨 worktree 能走通、开工自愈装上钩子）
- expectedFailure：还没解决的规则缺口。它们现在按"应有行为"断言会红，
  所以挂 expectedFailure；哪天变绿（unexpected success）就是该动手的信号。
  缺口在试点项目 .agent/improvements.md 登记（I-002 认领原子性 / I-003 边界交集 / I-004 main 无复查）。
"""
import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import helpers as H


class RaceGround(unittest.TestCase):
    """每个用例一套独立演练场：bare origin → clone（wsc sync 补钩子）→ 两个 worktree。"""

    def setUp(self):
        self.tmp = H.tmp_dir()
        self.addCleanup(H.rmtree, self.tmp)
        self.origin = self.tmp / "origin.git"
        self.assertEqual(H.run(["git", "init", "-q", "--bare", "-b", "main", str(self.origin)]).returncode, 0)
        src = H.make_project(self.tmp)
        H.git_repo(src)
        cards = (("T-001", {"allowed": ["  - docs/"]}), ("T-002", {"allowed": ["  - scripts/"]}))
        for cid, kw in cards:
            kw.setdefault("assignee", "[]")
            kw.setdefault("status", "todo")
            H.write_card(src, cid, **kw)
        H.git(src, "add", "-A")
        H.git(src, "commit", "-q", "-m", "卡入库")
        H.git(src, "remote", "add", "origin", str(self.origin))
        self.assertEqual(H.git(src, "push", "-q", "origin", "main").returncode, 0)
        self.proj = self.tmp / "proj"
        self.assertEqual(H.git(self.tmp, "clone", "-q", str(self.origin), str(self.proj)).returncode, 0)
        # 新 clone 没有钩子：靠 wsc sync 自愈补装（同时验证 F4）
        self.assertIn("补装", H.out(H.wsc("sync", str(self.proj))))
        for name, br in (("wt-a", "h-a"), ("wt-b", "h-b")):
            wt = self.tmp / name
            self.assertEqual(H.git(self.proj, "worktree", "add", "-q", str(wt), "-b", br).returncode, 0)
            H.git(wt, "config", "user.name", name)
            H.git(wt, "config", "user.email", f"{name}@invalid")
            H.git(wt, "config", "core.autocrlf", "false")
            H.git(wt, "config", "rerere.enabled", "false")
            self.assertEqual(H.git(wt, "push", "-q", "origin", f"HEAD:main").returncode, 0)

    def claim(self, wt, cid, who, pull=True):
        w = self.tmp / wt
        if pull:
            H.git(w, "fetch", "-q", "origin")
            H.git(w, "reset", "-q", "--hard", "origin/main")
        p = w / "backlog" / "tasks" / f"{cid}.md"
        t = p.read_text(encoding="utf-8").replace("status: todo", "status: doing", 1)
        t = t.replace("assignee: []", f"assignee: [{who}]", 1)
        p.write_text(t, encoding="utf-8", newline="\n")
        self.assertEqual(H.git(w, "add", f"backlog/tasks/{cid}.md").returncode, 0)
        return H.git(w, "commit", "-q", "-m", f"{who} 领 {cid}")

    def push(self, wt):
        return H.git(self.tmp / wt, "push", "-q", "origin", "HEAD:main")

    def main_card(self, cid):
        H.git(self.proj, "fetch", "-q", "origin")
        return H.git(self.proj, "show", f"origin/main:backlog/tasks/{cid}.md").stdout or ""

    def test_a_self_authorized_claim_works_across_worktrees(self):
        """修好的路：两边各自认领一张卡并推 main，全程真钩子，一步不多。"""
        self.assertEqual(self.claim("wt-a", "T-001", "h-a").returncode, 0)
        self.assertEqual(self.push("wt-a").returncode, 0)
        self.assertEqual(self.claim("wt-b", "T-002", "h-b").returncode, 0)
        self.assertEqual(self.push("wt-b").returncode, 0)
        self.assertIn("assignee: [h-a]", self.main_card("T-001"))
        self.assertIn("assignee: [h-b]", self.main_card("T-002"))

    @unittest.expectedFailure
    def test_b_double_claim_must_not_be_stolen_silently(self):
        """I-002：B 不 pull 就认领同一张卡，rebase -X theirs 之后 A 的认领还在不在。"""
        self.assertEqual(self.claim("wt-a", "T-001", "h-a").returncode, 0)
        self.assertEqual(self.push("wt-a").returncode, 0)
        b = self.claim("wt-b", "T-001", "h-b", pull=False)   # 跳过 pull，正是协议禁止的动作
        self.assertEqual(b.returncode, 0, msg=H.out(b))      # 钩子看不见 A 的认领，判它合法
        self.assertNotEqual(self.push("wt-b").returncode, 0)  # git 确实拒了
        H.git(self.tmp / "wt-b", "pull", "-q", "--rebase", "-X", "theirs", "origin", "main")
        self.assertEqual(self.push("wt-b").returncode, 0)
        self.assertIn("assignee: [h-a]", self.main_card("T-001"),
                      "期望：A 的先占不被静默覆盖（现实：被 -X theirs 吃掉且无人报警）")

    def test_c_overlapping_boundaries_are_blocked_at_claim(self):
        """I-003 已晋升：两张 allowed_paths 交集的卡同时在做，执法当场拒绝（原来只靠 git 撞车）。"""
        p = self.proj / "backlog" / "tasks" / "T-003.md"
        shutil.copyfile(self.proj / "backlog" / "tasks" / "T-001.md", p)
        p.write_text(p.read_text(encoding="utf-8").replace("T-001", "T-003"), encoding="utf-8")
        self.assertEqual(H.git(self.proj, "add", "backlog/tasks/T-003.md").returncode, 0)
        H.git(self.proj, "commit", "-q", "-m", "加一张与 T-001 边界重叠的卡")
        H.git(self.proj, "push", "-q", "origin", "HEAD:main")
        self.assertEqual(self.claim("wt-a", "T-001", "h-a").returncode, 0)
        self.assertEqual(self.push("wt-a").returncode, 0)
        second = self.claim("wt-b", "T-003", "h-b")
        self.assertNotEqual(second.returncode, 0, msg=H.out(second))
        self.assertIn("边界交集不得并行", H.out(second))

    @unittest.expectedFailure
    def test_d_main_must_never_hold_an_illegal_board(self):
        """I-004：每个提交当时都合法，凑起来 main 上是非法态；rebase/merge 不跑钩子，无人复查。"""
        self.assertEqual(self.claim("wt-a", "T-001", "same-owner").returncode, 0)
        self.assertEqual(self.push("wt-a").returncode, 0)
        self.assertEqual(self.claim("wt-b", "T-002", "same-owner").returncode, 0)
        self.assertEqual(self.push("wt-b").returncode, 0)
        merged = self.tmp / "merged"
        merged.mkdir()
        self.assertEqual(H.git(self.tmp, "clone", "-q", str(self.origin), str(merged)).returncode, 0)
        H.wsc("sync", str(merged))          # 补钩子顺带把 scripts/ 之外的东西不动
        r = H.check(merged, "--tasks")
        self.assertEqual(r.returncode, 0, msg="期望：合并后的 main 合法（现实：同一人两张 doing 卡，"
                                              "只有下一次不相关的提交才会撞上钩子）")


if __name__ == "__main__":
    unittest.main()
