"""dispatch.py 的测试：候选推导、预选、角色与命令解析、拉起。

三条口径逐条钉住：
1. **无状态**——拉起后不持有句柄、不读输出、不自动重试、不留运行时状态；
2. **不另写一套判定**——候选的边界冲突复用项目自己 check.py 的 boundary_intersection，
   卡片经项目自己的 check.py 读，不自己写解析器；
3. **不自主决定**——预选是写死的确定性规则；失败只上报，不改派。
"""
import os
import sys
import unittest
import unittest.mock
from pathlib import Path

import helpers as H

sys.path.insert(0, str(H.REPO))
import dispatch as D                                          # noqa: E402

AGENTS = """# 示例项目 — 测试

## 项目卡

| 项 | 内容 |
|---|---|
| 一句话 | 把事做成 |
| 运行方式 | `python -m app` |
| schema | 3 |

## 单写者所有权表（路径前缀 → 唯一写者）

| 路径 | 唯一写者 | 其他人 |
|---|---|---|
| `project/src/models/` | coder-ml | 只读 |
| `project/docs/` | doc-writer | 只读 |

## 角色一览

| 角色 | 文件 | 职责 |
|---|---|---|
| coder-ml | `.agent/roles/coder-backend.md` | 模型 |
| doc-writer | `.agent/roles/doc-writer.md` | 文档 |
"""

TABLE = """# dispatch — 启动命令表

| 角色 | 启动命令 |
|---|---|
| coder-ml | `codex --cd {worktree}` |
| doc-writer | `qodercli --project {worktree} --card {card}` |
"""

CARD = """---
id: {cid}
title: 卡 {cid}
status: {status}
assignee: {assignee}
labels: []
{deps}created_date: 2026-09-20
updated_date: 2026-09-28 09:00
---

## 需求
卡 {cid}

## 技术口径
（architect 填）

## 边界
allowed_paths:
{allowed}
forbidden_paths:
  - AGENTS.md
  - .agent/

## 验收清单
- [ ] check.py 全绿

## 交接说明
（收工时填，≤5 行）
"""


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = H.tmp_dir()
        self.addCleanup(H.rmtree, self.tmp)
        self.proj = H.make_project(self.tmp)
        (self.proj / "AGENTS.md").write_text(AGENTS, encoding="utf-8")
        (self.proj / ".agent" / "dispatch.md").write_text(TABLE, encoding="utf-8")
        # 边界路径要真存在，项目自己的 check.py --tasks 才放行（边界路径不存在 = 拒领）
        for rel in ("project/src/models", "project/docs"):
            (self.proj / rel).mkdir(parents=True, exist_ok=True)
        # 工具在不在 PATH 是环境事实：钉成替身，测试不依赖本机装了什么 CLI
        self._which = unittest.mock.patch.object(
            D, "which", lambda t: f"/fake/bin/{t}" if t in ("codex", "qodercli") else None)
        self._which.start()
        self.addCleanup(self._which.stop)
        # 认领子进程不许看见开发机的全局 git 配置与家目录
        self._env = unittest.mock.patch.dict(os.environ, {
            "GIT_CONFIG_GLOBAL": str(H.EMPTY_GITCONFIG),
            "GIT_CONFIG_SYSTEM": str(H.EMPTY_GITCONFIG),
            "COHARNESS_HOME": str(H.COH_HOME)})
        self._env.start()
        self.addCleanup(self._env.stop)
        H.git_repo(self.proj)
        H.git(self.proj, "config", "user.name", "coharness-test")
        H.git(self.proj, "config", "user.email", "coharness-test@invalid")

    def card(self, cid, **kw):
        deps = kw.pop("deps", ())
        kw.setdefault("status", "doing")
        kw.setdefault("assignee", "[]")
        kw.setdefault("allowed", ("  - project/docs/",))
        d = self.proj / "backlog" / "tasks"
        d.mkdir(parents=True, exist_ok=True)
        p = d / f"{cid}.md"
        p.write_text(CARD.format(
            cid=cid, deps=("dependencies: [" + ", ".join(deps) + "]\n") if deps else "",
            allowed="\n".join(kw["allowed"]), status=kw["status"],
            assignee=kw["assignee"]), encoding="utf-8")
        H.git(self.proj, "add", "-A")
        H.git(self.proj, "commit", "-q", "-m", f"card {cid}")
        return p


class Table(Base):
    def test_table_maps_role_to_command(self):
        t = D.load_table(self.proj)
        self.assertEqual(t["coder-ml"], "codex --cd {worktree}")
        self.assertEqual(t["doc-writer"], "qodercli --project {worktree} --card {card}")

    def test_missing_table_is_empty_not_an_error(self):
        (self.proj / ".agent" / "dispatch.md").unlink()
        self.assertEqual(D.load_table(self.proj), {})


class Candidates(Base):
    def test_todo_without_assignee_is_a_candidate(self):
        self.card("T-002", status="todo", assignee="[]", allowed=("  - project/src/models/",))
        got = [c["id"] for c in D.candidates(self.proj)]
        self.assertEqual(got, ["T-002"])

    def test_todo_with_assignee_is_not_a_candidate(self):
        self.card("T-002", status="todo", assignee="[someone]",
                  allowed=("  - project/src/models/",))
        self.assertEqual(D.candidates(self.proj), [])

    def test_doing_card_is_not_a_candidate(self):
        self.card("T-002", status="doing", assignee="[someone]",
                  allowed=("  - project/src/models/",))
        self.assertEqual(D.candidates(self.proj), [])

    def test_unfinished_dependency_blocks_the_candidate(self):
        self.card("T-001", status="doing", assignee="[a]",
                  allowed=("  - project/docs/",))
        self.card("T-002", status="todo", assignee="[]",
                  allowed=("  - project/src/models/",), deps=("T-001",))
        self.assertEqual([c["id"] for c in D.candidates(self.proj)], [])
        self.assertIn("T-001", dict(D.blocked(self.proj))["T-002"])

    def test_finished_dependency_unblocks_the_candidate(self):
        self.card("T-001", status="done", assignee="[a]", allowed=("  - project/docs/",))
        self.card("T-002", status="todo", assignee="[]",
                  allowed=("  - project/src/models/",), deps=("T-001",))
        self.assertEqual([c["id"] for c in D.candidates(self.proj)], ["T-002"])

    def test_boundary_collision_with_an_in_progress_card_blocks(self):
        self.card("T-001", status="doing", assignee="[a]",
                  allowed=("  - project/src/models/",))
        self.card("T-002", status="todo", assignee="[]",
                  allowed=("  - project/src/models/sub/",))
        self.assertEqual([c["id"] for c in D.candidates(self.proj)], [])
        self.assertIn("T-001", dict(D.blocked(self.proj))["T-002"])

    def test_candidates_carry_the_role_from_the_ownership_table(self):
        self.card("T-002", status="todo", assignee="[]", allowed=("  - project/src/models/",))
        self.card("T-003", status="todo", assignee="[]", allowed=("  - project/docs/",))
        roles = {c["id"]: c["role"] for c in D.candidates(self.proj)}
        self.assertEqual(roles, {"T-002": "coder-ml", "T-003": "doc-writer"})

    def test_candidates_are_sorted_by_card_number(self):
        for cid in ("T-010", "T-002", "T-001"):
            self.card(cid, status="todo", assignee="[]",
                      allowed=(f"  - project/docs/{cid}/",))
        self.assertEqual([c["id"] for c in D.candidates(self.proj)],
                         ["T-001", "T-002", "T-010"])

    def test_candidates_accept_a_symlinked_project_root(self):
        """macOS 的临时目录经 /var -> /private/var 符号链接；候选路径必须与 check.py 的 ROOT 同口径。"""
        link = self.tmp / "linked-project"
        try:
            link.symlink_to(self.proj, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("当前平台不允许创建目录符号链接")
        self.card("T-002", status="todo", assignee="[]",
                  allowed=("  - project/src/models/",))
        self.assertEqual([c["id"] for c in D.candidates(link)], ["T-002"])


class Pick(Base):
    def test_pick_takes_the_lowest_card_number(self):
        cards = [{"id": "T-010"}, {"id": "T-002"}, {"id": "T-001"}]
        self.assertEqual(D.pick(cards)["id"], "T-001")

    def test_pick_is_deterministic_for_equal_numbers(self):
        cards = [{"id": "T-002b"}, {"id": "T-002a"}]
        self.assertEqual(D.pick(cards)["id"], D.pick(list(reversed(cards)))["id"])

    def test_pick_of_nothing_is_none(self):
        self.assertIsNone(D.pick([]))


class Plan(Base):
    def test_plan_preselects_and_fills_the_command(self):
        self.card("T-002", status="todo", assignee="[]", allowed=("  - project/src/models/",))
        p = D.plan(self.proj)
        self.assertEqual(p["card"], "T-002")
        self.assertEqual(p["role"], "coder-ml")
        self.assertEqual(p["tool"], "codex")
        self.assertTrue(p["ready"])
        self.assertEqual(p["who"], "coharness-test")
        self.assertIn(str(p["worktree"]), p["command"])
        self.assertNotIn("{worktree}", p["command"])

    def test_explicit_card_overrides_the_preselection(self):
        self.card("T-002", status="todo", assignee="[]", allowed=("  - project/src/models/",))
        self.card("T-003", status="todo", assignee="[]", allowed=("  - project/docs/",))
        self.assertEqual(D.plan(self.proj)["card"], "T-002")
        self.assertEqual(D.plan(self.proj, card="T-003")["card"], "T-003")

    def test_explicit_tool_overrides_the_table_command(self):
        self.card("T-002", status="todo", assignee="[]", allowed=("  - project/src/models/",))
        p = D.plan(self.proj, tool="qodercli")
        self.assertEqual(p["tool"], "qodercli")
        self.assertTrue(p["command"].startswith("qodercli"))

    def test_missing_table_is_reported_not_guessed(self):
        (self.proj / ".agent" / "dispatch.md").unlink()
        self.card("T-002", status="todo", assignee="[]", allowed=("  - project/src/models/",))
        p = D.plan(self.proj)
        self.assertFalse(p["ready"])
        self.assertIn("dispatch.md", " ".join(p["reasons"]))

    def test_unknown_role_is_reported_not_guessed(self):
        self.card("T-002", status="todo", assignee="[]", allowed=("  - project/nothing/",))
        p = D.plan(self.proj)
        self.assertFalse(p["ready"])
        self.assertIn("所有权表", " ".join(p["reasons"]))

    def test_role_without_a_command_is_reported(self):
        (self.proj / ".agent" / "dispatch.md").write_text(
            "# dispatch\n\n| 角色 | 启动命令 |\n|---|---|\n| doc-writer | `x {card}` |\n",
            encoding="utf-8")
        self.card("T-002", status="todo", assignee="[]", allowed=("  - project/src/models/",))
        p = D.plan(self.proj)
        self.assertFalse(p["ready"])
        self.assertIn("coder-ml", " ".join(p["reasons"]))

    def test_no_candidate_is_reported(self):
        p = D.plan(self.proj)
        self.assertFalse(p["ready"])
        self.assertIn("没有可派", " ".join(p["reasons"]))

    def test_tool_missing_is_flagged_without_failing_the_plan(self):
        self.card("T-002", status="todo", assignee="[]", allowed=("  - project/src/models/",))
        with unittest.mock.patch.object(D, "which", lambda t: None):
            p = D.plan(self.proj)
        self.assertTrue(p["tool_missing"])
        self.assertFalse(p["ready"])
        self.assertIn("codex", " ".join(p["reasons"]))


class Launch(Base):
    def setUp(self):
        super().setUp()
        # 认领要落一个提交：仓库里得有身份（测试不许蹭全局配置）
        H.git(self.proj, "config", "user.name", "coharness-test")
        H.git(self.proj, "config", "user.email", "coharness-test@invalid")
        self.card("T-002", status="todo", assignee="[]", allowed=("  - project/src/models/",))
        self.calls = []

        def spawn(command, cwd):
            self.calls.append((command, str(cwd)))
            return True, ""

        self.spawn = spawn

    def launch(self, **kw):
        p = D.plan(self.proj, **kw)
        return D.launch(self.proj, p, spawn=self.spawn)

    def test_launch_claims_the_card_then_spawns_and_returns(self):
        r = self.launch()
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["card"], "T-002")
        text = (self.proj / "backlog" / "tasks" / "T-002.md").read_text(encoding="utf-8")
        self.assertIn("status: doing", text)
        self.assertIn("coharness-test", text)
        self.assertNotIn("assignee: [coder-ml]", text)
        self.assertEqual(len(self.calls), 1)
        self.assertIn("codex", self.calls[0][0])

    def test_launch_writes_the_branch_binding(self):
        self.launch()
        r = H.git(self.proj, "config", "--get", "branch.main.coharness-card")
        self.assertEqual(r.stdout.strip(), "T-002.md")

    def test_launch_creates_a_worktree_outside_the_project(self):
        self.launch()
        trees = H.git(self.proj, "worktree", "list", "--porcelain").stdout
        paths = [Path(line[len("worktree "):]) for line in trees.splitlines()
                 if line.startswith("worktree ")]
        self.assertTrue(any(os.path.samefile(self.proj, p) for p in paths), trees)
        self.assertGreaterEqual(len(paths), 2)

    def test_launch_refuses_a_plan_that_is_not_ready(self):
        p = D.plan(self.proj)
        p["ready"] = False
        p["reasons"] = ["没准备好"]
        with self.assertRaises(SystemExit) as ctx:
            D.launch(self.proj, p, spawn=self.spawn)
        self.assertIn("没准备好", str(ctx.exception))
        self.assertEqual(self.calls, [])

    def test_launch_refuses_when_the_tool_is_missing(self):
        p = D.plan(self.proj)
        p["tool_missing"] = True
        p["ready"] = False
        p["reasons"] = ["codex 不在 PATH"]
        with self.assertRaises(SystemExit):
            D.launch(self.proj, p, spawn=self.spawn)
        self.assertEqual(self.calls, [])

    def test_a_failed_claim_does_not_spawn_and_does_not_retry(self):
        H.git(self.proj, "config", "user.email", "x@invalid")
        # 先被别人抢走：认领必然失败
        other = H.run([sys.executable, str(H.WSC), "claim", str(self.proj), "T-002", "someone"],
                      cwd=self.proj)
        self.assertEqual(other.returncode, 0, H.out(other))
        before = self.calls[:]
        p = D.plan(self.proj)
        with self.assertRaises(SystemExit):
            D.launch(self.proj, p, spawn=self.spawn)
        self.assertEqual(self.calls, before, "认领失败不许拉起，也不许自动改派或重试")

    def test_spawn_failure_is_reported_and_not_retried(self):
        def boom(command, cwd):
            self.calls.append((command, str(cwd)))
            return False, "终端起不来"

        p = D.plan(self.proj)
        with self.assertRaises(SystemExit) as ctx:
            D.launch(self.proj, p, spawn=boom)
        self.assertIn("终端起不来", str(ctx.exception))
        self.assertEqual(len(self.calls), 1, "失败只报一次，不许自动重试")

    def test_claim_success_then_bad_existing_worktree_leaves_card_doing(self):
        p = D.plan(self.proj)
        Path(p["worktree"]).mkdir(parents=True)
        with self.assertRaises(SystemExit) as ctx:
            D.launch(self.proj, p, spawn=self.spawn)
        self.assertIn("不是本卡的 worktree", str(ctx.exception))
        text = (self.proj / "backlog" / "tasks" / "T-002.md").read_text(encoding="utf-8")
        self.assertIn("status: doing", text, "认领已落盘，失败不得自动回滚")
        self.assertEqual(self.calls, [])

    def test_existing_worktree_from_another_project_is_rejected(self):
        p = D.plan(self.proj)
        other = self.tmp / "other-project"
        H.git_repo(other)
        H.git(other, "config", "user.name", "other")
        H.git(other, "config", "user.email", "other@invalid")
        path = Path(p["worktree"])
        path.parent.mkdir(parents=True, exist_ok=True)
        r = H.git(other, "worktree", "add", "-q", "-b", "coh/T-002", str(path))
        self.assertEqual(r.returncode, 0, msg=H.out(r))
        with self.assertRaises(SystemExit) as ctx:
            D.launch(self.proj, p, spawn=self.spawn)
        self.assertIn("same_repo=no", str(ctx.exception))
        self.assertEqual(self.calls, [])

    def test_spawn_windows_uses_quoted_inner_command(self):
        seen = {}

        def fake_popen(argv, **kw):
            seen["argv"] = argv
            return object()

        with unittest.mock.patch.object(D.os, "name", "nt"), \
             unittest.mock.patch.object(D.subprocess, "Popen", fake_popen):
            ok, _detail = D._spawn_default('codex --cd "C:\\path with spaces"', "C:\\wt")
        self.assertTrue(ok)
        self.assertEqual(seen["argv"][-3:], ["codex", "--cd", "C:\\path with spaces"],
                         "Windows 拉起必须把命令拆成独立 argv，路径含空格仍保持一个参数")


class Advance(Base):
    def setUp(self):
        super().setUp()
        H.git(self.proj, "config", "user.name", "coharness-test")
        H.git(self.proj, "config", "user.email", "coharness-test@invalid")
        self.card("T-002", status="todo", assignee="[]", allowed=("  - project/src/models/",))
        self.calls = []

        def spawn(command, cwd):
            self.calls.append((command, str(cwd)))
            return True, ""

        self.spawn = spawn

    def test_advance_plans_then_launches_once(self):
        p = D.advance(self.proj, spawn=self.spawn)
        self.assertEqual(p["card"], "T-002")
        self.assertEqual(p["role"], "coder-ml")
        self.assertEqual(len(self.calls), 1)
        text = (self.proj / "backlog" / "tasks" / "T-002.md").read_text(encoding="utf-8")
        self.assertIn("status: doing", text)

    def test_advance_honours_an_explicit_card(self):
        self.card("T-010", status="todo", assignee="[]", allowed=("  - project/docs/",))
        p = D.advance(self.proj, card="T-010", spawn=self.spawn)
        self.assertEqual(p["card"], "T-010")
        self.assertEqual(p["role"], "doc-writer")
        self.assertEqual(len(self.calls), 1)

    def test_advance_without_a_ready_candidate_does_not_launch(self):
        (self.proj / ".agent" / "dispatch.md").unlink()          # 缺表 = 未就绪
        with self.assertRaises(SystemExit):
            D.advance(self.proj, spawn=self.spawn)
        self.assertEqual(self.calls, [], "未就绪不许拉起，也不许重试")


class Cli(Base):
    def test_default_lists_candidates_without_executing(self):
        self.card("T-002", status="todo", assignee="[]", allowed=("  - project/src/models/",))
        with unittest.mock.patch.object(D, "launch") as spy:
            rc = D.main([str(self.proj)])
        self.assertEqual(rc, 0)
        spy.assert_not_called()

    def test_cli_output_survives_a_cp1252_console(self):
        self.card("T-002", status="todo", assignee="[]", allowed=("  - project/src/models/",))
        r = H.run([sys.executable, str(H.REPO / "dispatch.py"), str(self.proj)],
                  cwd=self.proj, native_env=True, extra_env={"PYTHONIOENCODING": "cp1252"})
        self.assertEqual(r.returncode, 0, H.out(r))
        self.assertIn("[dispatch]", H.out(r))

    def test_advance_executes_once(self):
        self.card("T-002", status="todo", assignee="[]", allowed=("  - project/src/models/",))
        seen = []

        def fake_launch(project, p, **kw):
            seen.append(p["card"])
            return {"ok": True, "card": p["card"], "worktree": str(p["worktree"])}

        with unittest.mock.patch.object(D, "launch", fake_launch):
            rc = D.main([str(self.proj), "--advance"])
        self.assertEqual(rc, 0)
        self.assertEqual(seen, ["T-002"])


if __name__ == "__main__":
    unittest.main()
