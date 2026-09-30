"""wsc stats 与 check.py 的本地运行记账（计划书 W6）。

数据源只有两个：项目内 `.agent/telemetry.jsonl`（check.py 每次执行追加一行，本地、零上传、
可关）与 `git log`。这三张报告是"登记门槛 ≥2 次"的机器证据源，所以计数口径必须可复算：
遵循率按执行记录里的 rc，返工信号按同一文件被几次提交触及，stale 直接转述 check.py。
"""
import json
import sys
import unittest
from pathlib import Path

import helpers as H


class StatsGround(unittest.TestCase):
    def setUp(self):
        self.tmp = H.tmp_dir()
        self.addCleanup(H.rmtree, self.tmp)
        self.proj = H.make_project(self.tmp)
        H.git_repo(self.proj)
        self.tel = self.proj / ".agent" / "telemetry.jsonl"

    def entries(self):
        if not self.tel.exists():
            return []
        return [json.loads(l) for l in self.tel.read_text(encoding="utf-8").splitlines() if l.strip()]

    def commit_env(self, **extra):
        return extra

    def test_check_run_appends_one_local_line(self):
        self.assertEqual(len(self.entries()), 0)
        H.check(self.proj)
        rows = self.entries()
        self.assertEqual(len(rows), 1)
        e = rows[0]
        self.assertEqual(e["rc"], 0)
        self.assertEqual(set(e["checks"]), {"names", "tasks", "diff", "stale"})
        self.assertIn("ts", e)
        self.assertIn("harness", e)

    def test_telemetry_is_trimmed_so_readers_stay_bounded(self):
        """记账文件不许无界增长：stats/面板每次都要读全量，几千行之后展示面会被拖慢。
        超过上限就截到最近一段——最新那行必须在（它是"最近一次 check"的数据源）。"""
        self.tel.parent.mkdir(parents=True, exist_ok=True)
        filler = "\n".join(json.dumps({"ts": "2020-01-01T00:00:00", "n": i})
                           for i in range(2001))
        self.tel.write_text(filler + "\n", encoding="utf-8", newline="\n")
        H.check(self.proj, "--tasks")
        lines = self.tel.read_text(encoding="utf-8").splitlines()
        self.assertLessEqual(len(lines), 1000, f"记账文件没被截断：{len(lines)} 行")
        self.assertIn("rc", json.loads(lines[-1]), "最新一行必须留下")

    def test_telemetry_stays_out_of_git(self):
        H.check(self.proj)
        self.assertTrue(self.tel.exists())
        self.assertEqual(H.git(self.proj, "status", "--porcelain").stdout.strip(), "",
                         "本地记账不能把项目工作区弄脏，否则每次提交都会被自己的记录绊住")

    def test_no_track_flag_and_env_both_silence_it(self):
        H.check(self.proj)
        n = len(self.entries())
        H.check(self.proj, "--no-track")
        self.assertEqual(len(self.entries()), n, "--no-track 不该写行")
        r = H.run([sys.executable, self.proj / "scripts" / "check.py"], cwd=self.proj,
                  extra_env={"COHARNESS_NO_TRACK": "1"})
        self.assertEqual(r.returncode, 0, msg=H.out(r))
        self.assertEqual(len(self.entries()), n, "COHARNESS_NO_TRACK=1 同样不该写行")

    def test_env_override_names_the_harness(self):
        r = H.run([sys.executable, self.proj / "scripts" / "check.py", "--tasks"], cwd=self.proj,
                  extra_env={"COHARNESS_HARNESS": "qoder-0928"})
        self.assertEqual(r.returncode, 0, msg=H.out(r))
        self.assertEqual(self.entries()[-1]["harness"], "qoder-0928")

    def test_stats_reports_pass_rate_and_failing_check(self):
        H.check(self.proj)                                   # 全绿
        H.write_card(self.proj, "T-001", status="doing", assignee="[a]",
                     allowed=["  - 不存在的路径/"])
        bad = H.check(self.proj)                              # 违规
        self.assertNotEqual(bad.returncode, 0)
        text = H.out(H.wsc("stats", str(self.proj)))
        self.assertIn("[1] 规则遵循率", text)
        self.assertIn("1/2 次全绿（50%）", text)
        self.assertIn("失分项：tasks", text)

    def test_stats_is_read_only(self):
        H.check(self.proj)
        n = len(self.entries())
        first = H.out(H.wsc("stats", str(self.proj)))
        second = H.out(H.wsc("stats", str(self.proj)))
        self.assertEqual(n, len(self.entries()), "stats 不能往它要读的数据里加行")
        self.assertEqual(first.replace(str(self.tmp), ""), second.replace(str(self.tmp), ""))

    def test_rework_signal_needs_three_commits(self):
        for i in (1, 2):
            (self.proj / "docs" / f"d.md").write_text(f"{i}\n", encoding="utf-8")
            H.git(self.proj, "add", "-A")
            H.git(self.proj, "commit", "-q", "-m", f"改 {i}")
        text = H.out(H.wsc("stats", str(self.proj)))
        self.assertIn("无：近期内没有反复改动的文件", text)
        (self.proj / "docs" / "d.md").write_text("3\n", encoding="utf-8")
        H.git(self.proj, "add", "-A")
        H.git(self.proj, "commit", "-q", "-m", "改 3")
        text = H.out(H.wsc("stats", str(self.proj)))
        self.assertIn("docs/d.md", text)
        self.assertIn("3 次提交", text)

    def test_days_window_excludes_older_commits(self):
        f = self.proj / "docs" / "old.md"
        for i in (1, 2, 3):
            f.write_text(f"{i}\n", encoding="utf-8")
            H.git(self.proj, "add", "-A")
            H.run(["git", *H.GIT_ID, "commit", "-q", "-m", f"old {i}"], cwd=self.proj,
                  extra_env={"GIT_COMMITTER_DATE": "2026-01-01T10:00:00"})
        recent = H.out(H.wsc("stats", str(self.proj), "--days", "7"))
        self.assertNotIn("docs/old.md", recent)
        wide = H.out(H.wsc("stats", str(self.proj), "--days", "600"))
        self.assertIn("docs/old.md", wide)

    def test_cross_harness_churn_is_called_out(self):
        f = self.proj / "docs" / "x.md"
        for who in ("h-a", "h-b", "h-a"):
            f.write_text(who + "\n", encoding="utf-8")
            H.git(self.proj, "add", "-A")
            H.run(["git", "-c", f"user.name={who}", "-c", "user.email=x@invalid",
                   "-c", "commit.gpgsign=false", "-c", "core.autocrlf=false",
                   "commit", "-q", "-m", f"by {who}"], cwd=self.proj)
        text = H.out(H.wsc("stats", str(self.proj)))
        self.assertIn("跨 harness", text)
        self.assertIn("h-a, h-b", text)

    def test_stale_report_is_passed_through(self):
        H.write_card(self.proj, "T-009", status="doing", assignee="[z]",
                     allowed=["  - docs/"], updated="2020-01-01 09:00")
        H.git(self.proj, "add", "-A")
        H.git(self.proj, "commit", "-q", "-m", "一张僵死卡")
        text = H.out(H.wsc("stats", str(self.proj)))
        self.assertIn("[stale]", text)
        self.assertIn("T-009", text)

    def test_unparsable_line_is_counted_not_fatal(self):
        H.check(self.proj)
        with open(self.tel, "a", encoding="utf-8", newline="\n") as fh:
            fh.write("这一行不是 json\n")
        text = H.out(H.wsc("stats", str(self.proj)))
        self.assertIn("1 行读不懂已跳过", text)
        self.assertIn("[1] 规则遵循率", text)

    def test_stats_without_git_repo_still_reports_telemetry(self):
        solo = H.make_project(self.tmp / "nogit")
        H.run([sys.executable, solo / "scripts" / "check.py"], cwd=solo)
        text = H.out(H.wsc("stats", str(solo)))
        self.assertIn("1 条执行记录", text)
        self.assertIn("git log 读不到", text)


if __name__ == "__main__":
    unittest.main()
