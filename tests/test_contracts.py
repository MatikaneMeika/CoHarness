"""接口契约通知（计划书 W13）：`wsc sync --dry-run` 只读报告"这次同步会碰到谁"。

设计边界要写清：通知只落在自己的交接说明与终端输出里，**不往别人的卡上写行**——
他人卡的唯一写者是他自己（所有权表），自动改他人卡等于制造第二权威。
dry-run 也不 fetch：它读的是本地已有的远端跟踪引用，所以绝不产生网络流量。
"""
import unittest
from pathlib import Path

import helpers as H

CARD = """---
id: {cid}
title: 契约测试卡 {cid}
status: doing
assignee: [{who}]
labels: []
created_date: 2026-09-20
updated_date: 2026-09-28 10:00
---

## 需求
{cid}

## 技术口径
（architect 填）

## 边界
allowed_paths:
{allowed}
forbidden_paths:
  - AGENTS.md

## 验收清单
- [ ] check.py 全绿

## 交接说明
（收工时填）
"""


class Contracts(unittest.TestCase):
    def setUp(self):
        self.tmp = H.tmp_dir()
        self.addCleanup(H.rmtree, self.tmp)
        self.origin = self.tmp / "origin.git"
        H.run(["git", "init", "-q", "--bare", "-b", "main", str(self.origin)])
        self.seed = H.make_project(self.tmp)
        H.git_repo(self.seed)
        H.git(self.seed, "remote", "add", "origin", str(self.origin))
        self.assertEqual(H.git(self.seed, "push", "-q", "origin", "main").returncode, 0)

    def clone(self, tag):
        p = self.tmp / f"work-{tag}"
        self.assertEqual(H.git(self.tmp, "clone", "-q", str(self.origin), str(p)).returncode, 0)
        for k, v in (("user.name", tag), ("user.email", f"{tag}@invalid"),
                     ("core.autocrlf", "false")):
            H.git(p, "config", k, v)
        return p

    def push_change_from(self, tag, rel):
        """从另一个 clone 造一次"别人已经推进 main"的改动。"""
        w = self.clone(tag)
        (Path(w) / rel).parent.mkdir(parents=True, exist_ok=True)
        (w / rel).write_text(f"{rel} 被别人改过\n", encoding="utf-8")
        H.git(w, "add", "-A")
        self.assertEqual(H.git(w, "commit", "-q", "-m", f"改 {rel}").returncode, 0)
        self.assertEqual(H.git(w, "push", "-q", "origin", "HEAD:main").returncode, 0)
        return w

    def test_dry_run_is_read_only_and_names_the_contract(self):
        w = self.clone("me")
        H.git(w, "fetch", "-q", "origin")
        self.push_change_from("other", "code/api/routes.py")
        H.git(w, "fetch", "-q", "origin")
        before = H.git(w, "rev-parse", "HEAD").stdout.strip()
        r = H.wsc("sync", str(w), "--dry-run")
        self.assertEqual(r.returncode, 0, msg=H.out(r))
        out = H.out(r)
        self.assertIn("[dry-run] 不 pull、不装钩子", out)
        self.assertIn("[契约] code/api/routes.py", out)
        self.assertIn("docs/ARCHITECTURE.md", out, "要说出契约定义在哪")
        self.assertIn("通知", out)
        self.assertEqual(H.git(w, "rev-parse", "HEAD").stdout.strip(), before, "dry-run 不许动 HEAD")
        self.assertEqual(H.git(w, "status", "--porcelain").stdout.strip(), "", "dry-run 不许写盘")

    def test_dry_run_flags_files_inside_an_active_cards_boundary(self):
        w = self.clone("me2")
        H.write_card(w, "T-101", status="doing", assignee="[me2]", allowed=["  - code/api/"])
        H.git(w, "add", "-A")
        self.assertEqual(H.git(w, "commit", "-q", "--author=me2 <me2@invalid>",
                               "-m", "领 T-101").returncode, 0)
        H.git(w, "push", "-q", "origin", "HEAD:main")
        self.push_change_from("other2", "code/api/models.py")
        H.git(w, "fetch", "-q", "origin")
        out = H.out(H.wsc("sync", str(w), "--dry-run"))
        self.assertIn("[边界]", out)
        self.assertIn("T-101", out)
        self.assertIn("me2", out)

    def test_dry_run_says_nothing_is_touched(self):
        w = self.clone("me3")
        H.git(w, "fetch", "-q", "origin")
        self.push_change_from("other3", "docs/notes/loose.md")
        H.git(w, "fetch", "-q", "origin")
        out = H.out(H.wsc("sync", str(w), "--dry-run"))
        self.assertIn("没有触及契约表或在做卡边界内", out)

    def test_contract_match_is_a_path_prefix_not_a_substring(self):
        """契约前缀按路径边界匹配：`notes/code/api/legacy.md` 不在契约 `code/api/` 之下。
        旧实现多了一条 `prefix in f` 子串兜底，路径里碰巧含这段字样的文件全被误报，
        狼来了几次之后没人再看这张报告。"""
        w = self.clone("me6")
        H.git(w, "fetch", "-q", "origin")
        self.push_change_from("other6", "notes/code/api/legacy.md")
        H.git(w, "fetch", "-q", "origin")
        out = H.out(H.wsc("sync", str(w), "--dry-run"))
        self.assertNotIn("[契约] notes/code/api/legacy.md", out,
                         "子串撞上的路径不许报成契约文件")
        self.assertIn("没有触及契约表或在做卡边界内", out)

    def test_dry_run_without_a_remote_ref_tells_you_why(self):
        fresh = H.make_project(self.tmp / "no-remote")
        H.git_repo(fresh)
        out = H.out(H.wsc("sync", str(fresh), "--dry-run"))
        self.assertIn("本地还没有 origin/main 的远端跟踪引用", out)

    def test_contract_table_is_parsed_from_agents_md(self):
        w = self.clone("me4")
        text = (w / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("## 接口契约", text, "骨架要自带契约表，否则这张报告没有数据源")
        section = text.split("## 接口契约", 1)[1].split("\n## ", 1)[0]
        self.assertTrue(any("| `code/api/`" in l for l in section.splitlines()),
                        "契约表里要有 code/api/ 这一行，dry-run 才报得出通知对象")

    def test_real_sync_still_pulls(self):
        w = self.clone("me5")
        H.git(w, "fetch", "-q", "origin")
        self.push_change_from("other5", "docs/ship.md")
        r = H.wsc("sync", str(w))
        self.assertEqual(r.returncode, 0, msg=H.out(r))
        self.assertTrue((w / "docs" / "ship.md").exists(), "不带 --dry-run 时才真的拉")


if __name__ == "__main__":
    unittest.main()
