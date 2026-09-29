"""并发竞态探针：bare origin + clone + 两个 linked worktree，全程真钩子。

钉住两类东西：
- 硬断言：修好之后必须成立的（自授权认领跨 worktree 能走通、开工自愈装上钩子、
  边界交集当场被拒、同一张卡两次认领恰好一个成功）
- expectedFailure：还没解决的规则缺口。它们现在按"应有行为"断言会红，
  所以挂 expectedFailure；哪天变绿（unexpected success）就是该动手的信号。
  缺口在试点项目 .agent/improvements.md 登记（I-002 认领原子性已由
  wsc claim 闭口，见 test_b；I-004 main 无复查已于 2026-09-29 由 pre-push 推送门闭口，
  见 test_d 转正）。
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

    def test_b_double_claim_must_not_be_stolen_silently(self):
        """I-002 已闭口：认领走 wsc claim（同步+校验+提交+推送绑成一步），同一张卡第二方必败且干净。

        原来这条挂 xfail，是因为协议里的小手工步（pull --rebase -X theirs）会静默吃掉先占者；
        现在认领原子化到命令里，同步是命令内部的事，跳过同步就没机会写到 main。
        """
        self.assertEqual(H.wsc("claim", str(self.tmp / "wt-a"), "T-001", "h-a").returncode, 0)
        self.assertIn("assignee: [h-a]", self.main_card("T-001"))
        r = H.wsc("claim", str(self.tmp / "wt-b"), "T-001", "h-b")
        self.assertNotEqual(r.returncode, 0, msg="第二方认领同一张卡必须失败")
        self.assertIn("已被 h-a 认领", H.out(r))
        self.assertIn("assignee: [h-a]", self.main_card("T-001"), "先占者不能被静默覆盖")
        self.assertNotIn("h-b", H.git(self.tmp / "wt-b", "status", "--porcelain").stdout,
                         "落败方不能留半截改动")
        # 落败方仍然可以领走另一张不相干的卡：拒绝不是把看板锁死
        self.assertEqual(H.wsc("claim", str(self.tmp / "wt-b"), "T-002", "h-b").returncode, 0)
        self.assertIn("assignee: [h-b]", self.main_card("T-002"))

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

    def test_d_main_must_never_hold_an_illegal_board(self):
        """I-004 已闭口（2026-09-29）：每个提交当时都合法（各自基上 pre-commit 全绿），
        但 merge 不跑 pre-commit——两个合法提交合出来的非法看板，由 pre-push 钩子在
        推送前拦下，进不了共享 main。原来挂 expectedFailure 钉的是"无人复查"。
        """
        self.assertEqual(self.claim("wt-a", "T-001", "same-owner").returncode, 0)
        self.assertEqual(self.push("wt-a").returncode, 0)
        # wt-b 不 pull：在旧基上认领 T-002，此刻它自己的看板是合法的（T-001 还是 todo）
        self.assertEqual(self.claim("wt-b", "T-002", "same-owner", pull=False).returncode, 0)
        # merge 把 origin/main（含 T-001 doing）合进来：merge 提交不跑 pre-commit，
        # "same-owner 两张 doing"的非法态就此在本地凑成
        w = self.tmp / "wt-b"
        H.git(w, "fetch", "-q", "origin")
        self.assertEqual(H.git(w, "merge", "-q", "--no-edit", "origin/main").returncode, 0)
        r = H.check(w, "--tasks")
        self.assertNotEqual(r.returncode, 0, msg="合并凑出来的非法看板必须被 check 识破")
        self.assertIn("认领冲突", H.out(r))
        # 推送门：pre-push 钩子（wsc sync 补装）在 push 前跑 --tasks，非法态推不进 main
        self.assertTrue((H.hooks_dir(self.proj) / "pre-push").exists(),
                        "wsc sync 补装应包含 pre-push 推送门")
        pushed = self.push("wt-b")
        self.assertNotEqual(pushed.returncode, 0, msg="非法看板必须在推送前被拦下")
        self.assertIn("pre-push", H.out(pushed))


if __name__ == "__main__":
    unittest.main()
