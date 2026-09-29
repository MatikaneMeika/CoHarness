"""wsc claim：认领原子化（ADR/计划书 W7）。

钉住的是"认领要么整体成立要么整体不动"：写卡、过项目自己的 check.py、真钩子提交、推 main
四步绑在一条命令里；任何一步不成就还原，不留半截状态。
最后一条是真双进程并发（不是模拟）：同一张卡两个身份同时认领，必须恰好一个成功。
"""
import threading
import unittest
from pathlib import Path

import helpers as H


class ClaimGround(unittest.TestCase):
    """bare origin + 两个 clone，两边都靠 wsc sync 自愈装上钩子。"""

    def setUp(self):
        self.tmp = H.tmp_dir()
        self.addCleanup(H.rmtree, self.tmp)
        self.origin = self.tmp / "origin.git"
        self.assertEqual(H.run(["git", "init", "-q", "--bare", "-b", "main",
                               str(self.origin)]).returncode, 0)
        src = H.make_project(self.tmp)
        H.git_repo(src)
        H.write_card(src, "T-001", status="todo", assignee="[]", allowed=["  - docs/"])
        H.write_card(src, "T-002", status="todo", assignee="[]", allowed=["  - scripts/"])
        H.git(src, "add", "-A")
        H.git(src, "commit", "-q", "-m", "播两张空卡")
        H.git(src, "remote", "add", "origin", str(self.origin))
        self.assertEqual(H.git(src, "push", "-q", "origin", "main").returncode, 0)
        self.a = self.clone("a")
        self.b = self.clone("b")

    def clone(self, tag):
        p = self.tmp / f"proj-{tag}"
        self.assertEqual(H.git(self.tmp, "clone", "-q", str(self.origin), str(p)).returncode, 0)
        for k, v in (("user.name", f"clone-{tag}"), ("user.email", f"clone-{tag}@invalid"),
                     ("core.autocrlf", "false")):
            H.git(p, "config", k, v)
        self.assertIn("补装", H.out(H.wsc("sync", str(p))))   # 新 clone 没钩子：sync 补装
        return p

    def card(self, proj, cid):
        return (proj / "backlog" / "tasks" / f"{cid}.md").read_text(encoding="utf-8")

    def main_card(self, cid):
        H.git(self.a, "fetch", "-q", "origin")
        return H.git(self.a, "show", f"origin/main:backlog/tasks/{cid}.md").stdout or ""

    def assertClean(self, proj):
        self.assertEqual(H.git(proj, "status", "--porcelain").stdout.strip(), "",
                         f"{proj.name} 认领失败后必须回到干净状态")

    def test_success_writes_three_fields_commits_and_pushes(self):
        r = H.wsc("claim", str(self.a), "T-001", "harness-a")
        self.assertEqual(r.returncode, 0, msg=H.out(r))
        text = self.card(self.a, "T-001")
        self.assertIn("status: doing", text)
        self.assertIn("assignee: [harness-a]", text)
        self.assertRegex(text, r"(?m)^updated_date: \d{4}-\d{2}-\d{2}")
        self.assertIn("assignee: [harness-a]", self.main_card("T-001"))
        self.assertIn("claim T-001 -> harness-a", H.git(self.a, "log", "--oneline", "-1").stdout)
        self.assertNotIn("status: doing", self.card(self.a, "T-002"), "只动被认领的那张卡")

    def test_dry_run_touches_nothing(self):
        before = self.card(self.a, "T-001")
        head = H.git(self.a, "rev-parse", "HEAD").stdout
        r = H.wsc("claim", str(self.a), "T-001", "harness-a", "--dry-run")
        self.assertEqual(r.returncode, 0, msg=H.out(r))
        self.assertIn("此刻可认领", H.out(r))
        self.assertEqual(self.card(self.a, "T-001"), before)
        self.assertEqual(H.git(self.a, "rev-parse", "HEAD").stdout, head)
        self.assertEqual(H.git(self.a, "status", "--porcelain").stdout.strip(), "")

    def test_refuses_card_that_is_not_todo(self):
        H.write_card(self.a, "T-003", status="done", assignee="[]", allowed=["  - docs/"])
        self.assertEqual(H.git(self.a, "add", "-A").returncode, 0)
        c = H.git(self.a, "commit", "-q", "-m", "一张已完成的卡")
        self.assertEqual(c.returncode, 0, msg=H.out(c))
        self.assertEqual(H.git(self.a, "push", "-q", "origin", "HEAD:main").returncode, 0)
        self.b = self.clone("b2")                      # 让 B 看到 main 上的新卡
        r = H.wsc("claim", str(self.b), "T-003", "harness-b")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("只有 todo 可领", H.out(r))
        self.assertIn("status: done", self.card(self.b, "T-003"))
        self.assertClean(self.b)

    def test_refuses_card_already_owned_and_lists_free_ones(self):
        self.assertEqual(H.wsc("claim", str(self.a), "T-001", "harness-a").returncode, 0)
        r = H.wsc("claim", str(self.b), "T-001", "harness-b")
        self.assertNotEqual(r.returncode, 0)
        msg = H.out(r)
        self.assertIn("已被 harness-a 认领", msg)
        self.assertIn("T-002", msg, "拒绝时要同时给出此刻可认领的卡")
        self.assertNotIn("harness-b", self.main_card("T-001"))
        self.assertClean(self.b)

    def test_refuses_dirty_worktree_before_writing_the_card(self):
        (self.a / "docs").mkdir(parents=True, exist_ok=True)
        stray = self.a / "docs" / "stray.md"
        stray.write_text("未提交的改动\n", encoding="utf-8")
        before = self.card(self.a, "T-001")
        r = H.wsc("claim", str(self.a), "T-001", "harness-a")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("未提交改动", H.out(r))
        self.assertEqual(self.card(self.a, "T-001"), before, "脏工作区阶段就该退出，不碰卡")

    def test_overlap_with_an_active_card_is_refused_and_reverted(self):
        """认领判定复用项目自己的执法：与在做的卡边界相交，认领当场被拒并把卡还原。"""
        c = self.a / "backlog" / "tasks" / "T-004.md"
        c.write_text(H.card_text("T-004", status="todo", assignee="[]", allowed=["  - docs/"]),
                     encoding="utf-8", newline="\n")
        H.git(self.a, "add", "backlog/tasks/T-004.md")
        H.git(self.a, "commit", "-q", "-m", "加一张与 T-001 边界相同的卡")
        H.git(self.a, "push", "-q", "origin", "HEAD:main")
        self.assertEqual(H.wsc("claim", str(self.b), "T-001", "harness-a").returncode, 0)
        self.b = self.clone("b2")
        r = H.wsc("claim", str(self.b), "T-004", "harness-b")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("边界交集不得并行", H.out(r))
        self.assertIn("status: todo", self.card(self.b, "T-004"), "被拒的认领必须还原")
        self.assertClean(self.b)

    def test_claim_without_remote_stays_local(self):
        solo = H.make_project(self.tmp / "solo")
        H.git_repo(solo)
        H.write_card(solo, "T-001", status="todo", assignee="[]", allowed=["  - docs/"])
        H.git(solo, "add", "-A")
        H.git(solo, "commit", "-q", "-m", "本地卡入库")
        H.git(solo, "config", "user.name", "solo")
        H.git(solo, "config", "user.email", "solo@invalid")   # 只设 name 不够：commit 要两样都有
        H.install_hook(solo)
        r = H.wsc("claim", str(solo), "T-001", "harness-solo")
        self.assertEqual(r.returncode, 0, msg=H.out(r))
        self.assertIn("无 origin 远端", H.out(r))
        self.assertIn("assignee: [harness-solo]", self.card(solo, "T-001"))

    def test_unknown_card_id_is_a_loud_failure(self):
        r = H.wsc("claim", str(self.a), "T-777", "harness-a")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("找不到卡 T-777", H.out(r))
        self.assertClean(self.a)

    def test_two_processes_claiming_the_same_card_exactly_one_wins(self):
        """真并发：两个进程同时认领同一张卡，恰好一个进 main，另一个干净退出。"""
        results = {}

        def go(tag, proj):
            results[tag] = H.wsc("claim", str(proj), "T-001", f"harness-{tag}")

        threads = [threading.Thread(target=go, args=(t, p)) for t, p in (("a", self.a), ("b", self.b))]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=300)
        winners = [t for t, r in results.items() if r.returncode == 0]
        self.assertEqual(len(winners), 1, msg="两个都成功或都失败：" +
                         "\n".join(f"[{k}] {H.out(v)}" for k, v in results.items()))
        loser = "b" if winners == ["a"] else "a"
        self.assertIn("harness-" + winners[0], self.main_card("T-001"))
        self.assertNotIn("harness-" + loser, self.main_card("T-001"))
        msg = H.out(results[loser])
        self.assertTrue(any(k in msg for k in ("已被 harness-", "抢输了")),
                        msg=f"落败方要说明是谁先占：{msg}")
        self.assertClean(self.a)
        self.assertClean(self.b)


if __name__ == "__main__":
    unittest.main()
