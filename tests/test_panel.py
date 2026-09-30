"""展示面测试：board.py 的装配/渲染与 panel.py 的导航。

三条不容妥协的口径，逐条钉住：
1. **只读**——面板跑完不许留下任何文件改动或 __pycache__（写路径只有 wsc claim）；
2. **不写第二套解析器**——卡片必须经项目自己的 scripts/check.py 读，缺函数就降级不崩；
3. **报警要有凭据**——"提交了没勾""跨工作树分叉"这些旗子必须由真 git 状态触发，
   不能是渲染层的装饰。角色一律从 AGENTS.md 所有权表推，推不到就明说推不到。
"""
import os
import shutil
import subprocess
import sys
import time
import types
import unittest
import unittest.mock
from pathlib import Path

import helpers as H

sys.path.insert(0, str(H.REPO))
import board                                               # noqa: E402
import panel as panel_mod                                  # noqa: E402

CARD = """---
id: {cid}
title: {title}
status: {status}
assignee: {assignee}
labels: []
created_date: 2026-09-20
updated_date: {updated}
---

## 需求
{title}

## 技术口径
（architect 填）

## 边界
allowed_paths:
{allowed}
forbidden_paths:
  - AGENTS.md
  - .agent/

## 验收清单
{items}

## 交接说明
（收工时填，≤5 行）
"""


def git(proj, *args):
    return H.run(["git", *H.GIT_ID[:4], *args], cwd=proj)


def make_card(proj, cid, *, status="doing", assignee="[wt-a]", allowed=("  - docs/",),
              items=("- [ ] 第一条", "- [ ] 第二条"), updated="2026-09-28 09:00",
              title=None):
    d = Path(proj) / "backlog" / "tasks"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{cid}.md"
    p.write_text(CARD.format(cid=cid, title=title or f"卡 {cid}", status=status,
                             assignee=assignee, allowed="\n".join(allowed),
                             items="\n".join(items), updated=updated),
                 encoding="utf-8", newline="\n")
    return p


class BoardData(unittest.TestCase):
    def setUp(self):
        self.tmp = H.tmp_dir()
        self.addCleanup(H.rmtree, self.tmp)
        self.proj = self.tmp / "proj"
        r = H.wsc("init", "03", str(self.proj))
        self.assertEqual(r.returncode, 0, msg=H.out(r))
        git(self.proj, "init", "-q", "--initial-branch=main")

    def test_reads_columns_and_ticks_through_the_projects_own_parser(self):
        make_card(self.proj, "T-010", items=("- [x] 做完的一条", "- [ ] 没做的一条"))
        snap = board.project_snapshot(self.proj, deep=False)
        self.assertEqual(snap["columns"], ["todo", "doing", "review", "done"])
        card = snap["cards"][0]
        self.assertEqual((card["done"], card["total"]), (1, 2))
        self.assertEqual(card["status"], "doing")
        self.assertEqual(card["assignees"], ["wt-a"])
        self.assertEqual(snap["card_errors"], [])

    def test_role_comes_from_ownership_table_or_says_unknown(self):
        make_card(self.proj, "T-011", allowed=("  - docs/ARCHITECTURE.md",))
        make_card(self.proj, "T-012", allowed=("  - notes/xyz/",))
        snap = board.project_snapshot(self.proj, deep=False)
        by = {c["id"]: c for c in snap["cards"]}
        self.assertEqual(by["T-011"]["role"], "architect")
        self.assertEqual(by["T-012"]["role"], board.UNKNOWN_ROLE)

    def test_template_placeholder_row_still_matches(self):
        """骨架所有权表里写的是 code/<组件>/，实例化后不会真替换那一行，
        所以带通配的条目要能匹配到 code/ 下的路径——否则面板对任何 coder 卡都推不出角色。"""
        make_card(self.proj, "T-013", allowed=("  - code/frontend/",))
        snap = board.project_snapshot(self.proj, deep=False)
        self.assertIn("coder", snap["cards"][0]["role"])

    def test_load_check_reuses_the_module_until_the_file_changes(self):
        """watch 每 5 秒快照一次：check.py 一个字没改就别重复编译（指纹缓存只挡快照重算，
        挡不住模块装载——多项目 watch 时每轮都在重编同一份执法脚本）。文件真变了必须重载。"""
        first = board.load_check(self.proj)
        self.assertIs(board.load_check(self.proj), first, "check.py 没变却重新装载了一遍")
        f = self.proj / "scripts" / "check.py"
        os.utime(f, (time.time() + 10, time.time() + 10))
        self.assertIsNot(board.load_check(self.proj), first, "check.py 变了必须重新装载")

    def test_flag_submit_without_tick(self):
        make_card(self.proj, "T-014", items=("- [ ] 一条",))
        (self.proj / "docs").mkdir(exist_ok=True)
        (self.proj / "docs" / "X.md").write_text("改动\n", encoding="utf-8", newline="\n")
        git(self.proj, "add", "-A")
        self.assertEqual(git(self.proj, "commit", "-q", "-m", "改 docs").returncode, 0)
        snap = board.project_snapshot(self.proj)
        card = next(c for c in snap["cards"] if c["id"] == "T-014")
        self.assertGreaterEqual(card["commits"], 1)
        self.assertIn("提交了没勾", card["flags"])

    def test_flag_done_with_unticked_checklist(self):
        make_card(self.proj, "T-015", status="done", items=("- [x] 一条", "- [ ] 另一条"))
        snap = board.project_snapshot(self.proj, deep=False)
        self.assertIn("done 但清单未满", snap["cards"][0]["flags"])

    def test_flag_cross_worktree_divergence(self):
        """I-007 点名的形状：同一张卡在不同工作树里状态/勾选不一样，面板必须报分叉。"""
        make_card(self.proj, "T-016", items=("- [ ] 一条",))
        git(self.proj, "add", "-A")
        self.assertEqual(git(self.proj, "commit", "-q", "-m", "播卡").returncode, 0)
        wt = self.tmp / "wt"
        self.assertEqual(git(self.proj, "worktree", "add", "-q", "-b", "wt",
                             str(wt)).returncode, 0)
        p = wt / "backlog" / "tasks" / "T-016.md"
        p.write_text(p.read_text(encoding="utf-8").replace("- [ ] 一条", "- [x] 一条")
                     .replace("status: doing", "status: review"), encoding="utf-8", newline="\n")
        snap = board.project_snapshot(self.proj)
        card = snap["cards"][0]
        self.assertIn("跨工作树分叉", card["flags"])
        self.assertEqual(len(card["copies"]), 2)

    def test_old_check_py_without_minimal_mode_still_reads(self):
        """没跑 maintain migrate 的老实例：check.py 里可能没有后来加的 minimal_mode，
        面板要降级继续读，而不是当场炸（这正是 audit 报"漂移"之外的另一面）。"""
        f = self.proj / "scripts" / "check.py"
        text = f.read_text(encoding="utf-8")
        cut = text[text.index("def minimal_mode("):]
        cut = cut[:cut.index("\ndef ")]
        self.assertIn("minimal_mode", cut)
        self.assertNotIn("def load_cards", cut)
        f.write_text(text.replace(cut, ""), encoding="utf-8", newline="\n")
        make_card(self.proj, "T-017", items=("- [x] 一条",))
        snap = board.project_snapshot(self.proj, deep=False)
        self.assertEqual(snap["cards"][0]["done"], 1)
        self.assertFalse(snap["minimal"], "有 backlog/tasks 就不是最小模式")

    def test_too_old_check_py_says_what_to_run(self):
        """连 load_cards 都没有的老执法脚本：要给出可执行补救命令，不许抛 AttributeError。"""
        (self.proj / "scripts" / "check.py").write_text(
            "import pathlib\nROOT = pathlib.Path('.')\n", encoding="utf-8", newline="\n")
        with self.assertRaises(SystemExit) as ctx:
            board.project_snapshot(self.proj, deep=False)
        self.assertIn("maintain.py migrate", str(ctx.exception))

    def test_missing_check_py_fails_loudly_with_a_fix_command(self):
        bare = self.tmp / "bare"
        bare.mkdir()
        with self.assertRaises(SystemExit) as ctx:
            board.project_snapshot(bare)
        msg = str(ctx.exception)
        self.assertIn("scripts/check.py", msg)
        self.assertIn("init", msg)

    def test_panel_writes_nothing_into_the_project(self):
        make_card(self.proj, "T-018")
        git(self.proj, "add", "-A")
        self.assertEqual(git(self.proj, "commit", "-q", "-m", "基线").returncode, 0)
        before = H.run(["git", "status", "--porcelain"], cwd=self.proj).stdout.strip()
        board.project_snapshot(self.proj)
        board.render_projects([{"name": "x", "skeleton": "y", "doing": 0, "todo": 0,
                                "flags": 0, "errors": 0}], 0, 60, color=True)
        self.assertEqual(H.run(["git", "status", "--porcelain"], cwd=self.proj).stdout.strip(),
                         before, "面板是只读面，跑完工作区必须一模一样")
        junk = [p for p in self.proj.rglob("__pycache__")]
        self.assertEqual(junk, [], "载入项目 check.py 不许留下 __pycache__")


class BoardView(unittest.TestCase):
    def setUp(self):
        self.snap = {"path": Path("P"), "name": "示例项目", "label": "示例项目",
                     "goal": "把事做成", "run": "", "schema": "3",
                     "columns": ["todo", "doing", "review", "done"], "minimal": False,
                     "card_errors": [], "owners": [], "heads": [], "diverged": 0,
                     "cards": [{"id": "T-001", "title": "甲", "status": "doing",
                                "assignees": ["codex-a"], "role": "coder", "allowed": ["docs/"],
                                "rel": "backlog/tasks/T-001.md", "done": 1, "total": 2,
                                "items": [(True, "一"), (False, "二")], "commits": 3,
                                "recent": [{"sha": "abc1234", "author": "codex-a",
                                            "ago": "2 hours ago"}],
                                "authors": ["codex-a"], "copies": [], "flags": ["提交了没勾"],
                                "updated": "2026-09-28 09:00", "stale": False}],
                     "telemetry": {"runs": 0, "bad": 0, "file": Path("t"), "last": None,
                                   "harnesses": []}}

    def test_alarm_column_dashes_instead_of_zero_when_shallow(self):
        """浅快照算不出报警位——那格画 0 等于把"没查"报成"没有报警"（真机踩过：
        卡上挂着"跨工作树分叉"，顶层仍显示 0，而 --plain 显示 1）。"""
        st = {"page": "projects", "sel": 0, "cursor": 0, "card": None}
        shallow, _, _ = board.current_page_lines([dict(self.snap, deep=False)], st, 78, False)
        deep, _, _ = board.current_page_lines([dict(self.snap, deep=True)], st, 78, False)
        self.assertTrue(shallow[2].rstrip().endswith("-"),
                        f"浅快照的报警位不是 -：{shallow[2]!r}")
        self.assertTrue(deep[2].rstrip().endswith("1"),
                        f"深快照该报出那一条报警：{deep[2]!r}")

    def test_plain_render_emits_no_escape_sequences(self):
        lines, order, _ = board.render_tasks(self.snap, 0, 78, color=False)
        text = "\n".join(lines)
        self.assertNotIn("\033", text)
        self.assertEqual(order, [0])
        self.assertIn("T-001", text)
        self.assertIn("!提交了没勾", text)

    def test_core_roles_sort_above_workers_and_unknown_last(self):
        cards = [{"role": "coder", "id": "1"}, {"role": board.UNKNOWN_ROLE, "id": "2"},
                 {"role": "integrator", "id": "3"}, {"role": "architect", "id": "4"}]
        order = [role for role, _ in board.grouped_by_role(cards)]
        self.assertEqual(order[:2], ["integrator", "architect"])
        self.assertEqual(order[-1], board.UNKNOWN_ROLE)

    def test_card_page_prints_the_command_rather_than_running_it(self):
        text = "\n".join(board.render_card(self.snap, self.snap["cards"][0], 78, color=False))
        self.assertIn("wsc.py claim", text)
        self.assertIn("wsc.py check", text)
        self.assertIn("maintain.py audit", text)
        self.assertIn("验收清单", text)
        self.assertIn("1/2", text)

    def test_chinese_columns_align_by_display_width(self):
        self.assertEqual(board.dw("骨架"), 4)
        self.assertLessEqual(board.dw(board.clip("骨架骨架骨架", 6)), 6)
        self.assertEqual(board.dw(board.pad(board.clip("骨架骨架骨架", 6), 6)), 6)
        self.assertEqual(board.dw(board.pad("骨架", 10)), 10)
        self.assertEqual(board.dw(board.rpad("在做", 6)), 6)


class Navigate(unittest.TestCase):
    def base(self):
        return {"page": "projects", "sel": 0, "cursor": 0, "card": None, "quit": False}

    def test_cursor_clamps_at_both_ends(self):
        s = board.navigate(self.base(), "up", 3)
        self.assertEqual(s["cursor"], 0)
        for _ in range(9):
            s = board.navigate(s, "down", 3)
        self.assertEqual(s["cursor"], 2)

    def test_enter_and_back_move_one_level_at_a_time(self):
        s = board.navigate(self.base(), "enter", 2)
        self.assertEqual(s["page"], "tasks")
        s = board.navigate(s, "enter", 2)
        self.assertEqual(s["page"], "card")
        s = board.navigate(s, "back", 1)
        self.assertEqual(s["page"], "tasks")
        s = board.navigate(s, "back", 2)
        self.assertEqual(s["page"], "projects")
        self.assertIsNone(s["card"])

    def test_q_quits_and_projects_cannot_back_out(self):
        self.assertTrue(board.navigate(self.base(), "q", 1)["quit"])
        self.assertEqual(board.navigate(self.base(), "back", 1)["page"], "projects")

    def test_pgup_pgdn_home_end_move_the_viewport(self):
        s = dict(self.base(), top=0)
        s = board.navigate(s, "pgdn", 40)
        self.assertEqual(s["top"], board.VIEW_STEP)
        s = board.navigate(s, "pgdn", 40)
        self.assertEqual(s["top"], board.VIEW_STEP * 2)
        s = board.navigate(s, "pgup", 40)
        self.assertEqual(s["top"], board.VIEW_STEP)
        s = board.navigate(s, "pgup", 40)
        self.assertEqual(s["top"], 0, "在最顶上再上翻不许变负")
        s = board.navigate(s, "end", 40)
        self.assertGreater(s["top"], 0, "end 应该把视口推到底（panel 负责钳制）")
        self.assertEqual(board.navigate(s, "home", 40)["top"], 0)


class ScrollFilterKeys(unittest.TestCase):
    """滚动/筛选/视口：行数超屏要能平移，卡多的时候要能按状态收窄，窄终端不许破宽度承诺。"""

    def setUp(self):
        def card(i):
            st = ("todo", "doing", "review", "done")[i % 4]
            return {"id": f"T-{i:03d}", "title": f"任务{i}", "status": st,
                    "assignees": ["h"] if st in ("doing", "review") else [], "role": "coder",
                    "allowed": ["docs/"], "rel": f"backlog/tasks/T-{i:03d}.md",
                    "done": 0, "total": 1, "items": [(False, "x")], "commits": 0,
                    "recent": [], "authors": set(), "copies": [], "flags": [],
                    "updated": "2026-09-28 09:00", "stale": False}
        self.snap = {"path": Path("P"), "name": "示例项目", "label": "示例项目", "goal": "",
                     "run": "", "schema": "3", "columns": ["todo", "doing", "review", "done"],
                     "minimal": False, "card_errors": [], "owners": [], "heads": [],
                     "diverged": 0, "cards": [card(i) for i in range(40)],
                     "telemetry": {"runs": 0, "bad": 0, "file": Path("t"), "last": None,
                                   "harnesses": []}}

    def tasks_state(self, **kw):
        return dict({"page": "tasks", "sel": 0, "cursor": 0, "card": None,
                     "quit": False, "filter": "all", "top": 0}, **kw)

    def test_filter_narrows_tasks_and_ids_still_point_at_original_cards(self):
        lines, ids, row = board.current_page_lines(
            [self.snap], self.tasks_state(filter="doing"), 78, False)
        self.assertEqual(len(ids), 10, "40 张里 doing 应有 10 张")
        self.assertEqual(ids, [i for i in range(40) if self.snap["cards"][i]["status"] == "doing"],
                         "ids 必须指回未筛选卡片的真实下标，Enter 进卡页才不会进错卡")
        self.assertIn("doing", "\n".join(lines))

    def test_filter_all_shows_everything(self):
        _, ids, _ = board.current_page_lines([self.snap], self.tasks_state(), 78, False)
        self.assertEqual(len(ids), 40)

    def test_viewport_keeps_the_cursor_row_visible(self):
        self.assertEqual(board.viewport(50, 3, 0, 20), 0, "光标在窗口内：视口不动")
        self.assertEqual(board.viewport(50, 25, 0, 20), 6, "光标掉出窗口底：视口跟下去")
        self.assertEqual(board.viewport(50, 4, 10, 20), 4, "光标在窗口上方：视口跟上去，光标贴窗口顶")
        self.assertEqual(board.viewport(50, 49, 0, 20), 30, "底部钳制：不许滑出末行")

    def test_cursor_row_marks_the_selected_card_line(self):
        lines, ids, row = board.current_page_lines(
            [self.snap], self.tasks_state(cursor=5), 78, False)
        self.assertIn("T-005", lines[row], f"cursor_row 应指向第 5 张可见卡：{lines[row]!r}")

    def test_narrow_width_still_clips_by_display_width(self):
        for w in (60, 100):
            lines, _, _ = board.current_page_lines(
                [self.snap], self.tasks_state(), w, False)
            bad = [l for l in lines if board.dw(board.clip(l, w)) > w]
            self.assertFalse(bad, f"宽度 {w} 下有行超出显示宽度：{bad[:2]}")

    def test_clip_helpers_measure_display_width_not_char_count(self):
        """中文占两列，渲染层的截断必须按显示宽度算：`_clip_left`/`_clip`/`_title` 曾用 len()，
        含中文的标题与路径能到预算宽度的两倍——`--plain` 直接打印这些行，越界就在终端里折行错位。"""
        self.assertLessEqual(board.dw(board._clip_left("项目/很长的中文路径/卡-001.md", 12)), 12,
                             "从左边截的路径也要按显示宽度")
        self.assertLessEqual(board.dw(board.clip("中文字符很长的清单项", 10)), 10)
        lines = []
        board._title(lines, "中文字符标题啊", 20)
        self.assertLessEqual(board.dw(lines[0]), 20, f"标题条超出宽度：{lines[0]!r}")
        snap = dict(self.snap, label="中文项目名很长很长很长很长很长")
        head = board.render_tasks(snap, 0, 20, False)[0][0]
        self.assertLessEqual(board.dw(head), 20, f"任务页标题条超出宽度：{head!r}")

    def test_term_width_falls_back_when_no_terminal(self):
        with unittest.mock.patch.object(board.os, "get_terminal_size",
                                        side_effect=OSError("no tty")):
            self.assertEqual(board.term_width(default=99), 99)


class ReviewNotes(unittest.TestCase):
    """F1 审阅意见协议：卡体可选节，条目三行结构（File:/Lines:/Comment:，借鉴 orca 的
    diff 批注契约），勾选 = 已传达给 agent；未勾的就是未读队列。"""

    ENTRIES = (
        "- [ ] File: docs/ARCHITECTURE.md\n"
        "  Lines: 12-18\n"
        '  Comment: "接口这里要写清幂等性"\n'
        "- [x] File: code/api/\n"
        "  Lines: all\n"
        '  Comment: "命名已经改好"\n'
    )

    def setUp(self):
        self.tmp = H.tmp_dir()
        self.addCleanup(H.rmtree, self.tmp)
        self.proj = self.tmp / "proj"
        r = H.wsc("init", "03", str(self.proj))
        self.assertEqual(r.returncode, 0, msg=H.out(r))
        git(self.proj, "init", "-q", "--initial-branch=main")

    def append_reviews(self, p, entries=ENTRIES):
        p.write_text(p.read_text(encoding="utf-8") + "\n## 审阅意见\n" + entries,
                     encoding="utf-8", newline="\n")

    def test_review_notes_parse(self):
        p = make_card(self.proj, "T-050")
        self.append_reviews(p)
        notes = board.review_notes(p.read_text(encoding="utf-8"))
        self.assertEqual(len(notes), 2)
        self.assertTrue(notes[0]["unread"])
        self.assertFalse(notes[1]["unread"])
        self.assertEqual(notes[0]["lines"], "12-18")
        self.assertEqual(notes[0]["file"], "docs/ARCHITECTURE.md")

    def test_snapshot_counts_unread_reviews(self):
        p = make_card(self.proj, "T-051")
        self.append_reviews(p)
        snap = board.project_snapshot(self.proj, deep=False)
        self.assertEqual(snap["cards"][0]["reviews_unread"], 1)

    def test_card_without_the_section_is_unaffected(self):
        make_card(self.proj, "T-052")
        snap = board.project_snapshot(self.proj, deep=False)
        self.assertEqual(snap["cards"][0]["reviews_unread"], 0)

    def test_worktree_bound_to_another_card_is_not_a_copy_of_this_one(self):
        """F4：带 `branch.<名>.coharness-card` 绑定的工作树只算绑定卡的工作树——
        别的卡的工作树里躺着这张卡的陈旧副本，不该报成"跨工作树分叉"；未绑定的按文件在场算。"""
        p = make_card(self.proj, "T-070")
        git(self.proj, "add", "-A")
        git(self.proj, "commit", "-q", "-m", "建卡")
        git(self.proj, "worktree", "add", "-q", str(self.tmp / "wt-b"), "-b", "wt-b")
        rel = "backlog/tasks/T-070.md"
        board.cache_reset(self.proj)
        self.assertEqual(len(board.worktree_copies(self.proj, rel)), 2,
                         "未绑定：两个树都有这份卡文件，都算副本")
        git(self.proj, "config", "branch.wt-b.coharness-card", "T-999.md")
        board.cache_reset(self.proj)
        rows = board.worktree_copies(self.proj, rel)
        self.assertEqual([r for r in rows if "wt-b" in str(r["path"])], [],
                         "绑定到别的卡的工作树不许算这张卡的副本")
        self.assertEqual(len(rows), 1, "主工作树仍在")

    def test_tasks_badge_marks_unread_reviews(self):
        card = dict(self.badge_card(), reviews_unread=2)
        text = "\n".join(board.render_tasks(dict(self.badge_snap(), cards=[card]), 0, 78, False)[0])
        self.assertIn("2条未读", text)

    def test_card_page_renders_review_notes(self):
        notes = [{"unread": True, "file": "docs/ARCHITECTURE.md", "lines": "12-18",
                  "comment": "接口这里要写清幂等性"}]
        card = dict(self.badge_card(), reviews=notes)
        text = "\n".join(board.render_card(self.badge_snap(), card, 78, False))
        self.assertIn("审阅意见", text)
        self.assertIn("未读", text)
        self.assertIn("接口这里要写清幂等性", text)

    def badge_card(self):
        return {"id": "T-060", "title": "甲", "status": "doing", "assignees": ["codex-a"],
                "role": "coder", "allowed": ["docs/"], "rel": "backlog/tasks/T-060.md",
                "done": 1, "total": 2, "items": [(True, "一"), (False, "二")], "commits": 3,
                "recent": [], "authors": [], "copies": [], "flags": [],
                "updated": "2026-09-28 09:00", "stale": False}

    def badge_snap(self):
        return {"path": Path("P"), "name": "示例项目", "label": "示例项目", "goal": "把事做成",
                "run": "", "schema": "3", "columns": ["todo", "doing", "review", "done"],
                "minimal": False, "card_errors": [], "owners": [], "heads": [], "diverged": 0,
                "cards": [self.badge_card()],
                "telemetry": {"runs": 0, "bad": 0, "file": Path("t"), "last": None,
                              "harnesses": []}}


class PosixLongEscapes(unittest.TestCase):
    """POSIX 读键要吃满整个转义序列：旧实现固定读 2 字符，Home/End/PgUp/PgDn 全都失灵。"""

    def test_long_sequences_decode(self):
        for rest, want in (("[5~", "pgup"), ("[6~", "pgdn"), ("[H", "home"), ("[F", "end"),
                           ("[1~", "home"), ("[4~", "end"), ("[A", "up"), ("[B", "down")):
            self.assertEqual(panel_mod.decode_posix("\x1b", rest), want, rest)

    def test_drain_reads_the_whole_sequence(self):
        seq = iter("[5~xyz")
        self.assertEqual(panel_mod.read_escape_sequence(lambda: next(seq), lambda: True, 4),
                         "[5~", "读到 '~' 就该停，不许把后续普通字符吞掉")
        self.assertEqual(panel_mod.read_escape_sequence(lambda: next(iter("AB")),
                                                        lambda: False, 4), "",
                         "无字符可读就返回空串：decode 层认不出形状，兜底成 ESC")

    def test_msvcrt_standard_enhanced_key_codes(self):
        for ch2, want in (("H", "up"), ("P", "down"), ("K", "left"), ("M", "right"),
                          ("G", "home"), ("O", "end"), ("I", "pgup"), ("Q", "pgdn"),
                          ("S", "BS")):
            self.assertEqual(panel_mod.decode_msvcrt("\x00", ch2), want, ch2)


class EndToEnd(unittest.TestCase):
    def test_plain_mode_lists_registered_projects_and_opens_one(self):
        tmp = H.tmp_dir()
        self.addCleanup(H.rmtree, tmp)
        home = tmp / "home"
        a, b = tmp / "alpha", tmp / "beta"
        for proj in (a, b):
            r = H.wsc("init", "03", str(proj), extra_env={"COHARNESS_HOME": str(home)})
            self.assertEqual(r.returncode, 0, msg=H.out(r))
        r = H.run([sys.executable, str(H.REPO / "panel.py"), "--plain"],
                  extra_env={"COHARNESS_HOME": str(home)})
        self.assertEqual(r.returncode, 0, msg=H.out(r))
        out = H.out(r)
        self.assertIn("本机项目（2）", out)
        self.assertIn("03-multi-harness-project", out)

        make_card(a, "T-002", status="todo", assignee="[]", items=("- [ ] 一条",))
        r2 = H.run([sys.executable, str(H.REPO / "panel.py"), "--plain",
                    "--project", str(a)], extra_env={"COHARNESS_HOME": str(home)})
        self.assertEqual(r2.returncode, 0, msg=H.out(r2))
        self.assertIn("任务看板", H.out(r2))
        self.assertIn("T-002", H.out(r2))
        # 只读承诺在子进程这条路上同样成立：项目里不许多出文件
        self.assertEqual(list(a.rglob("__pycache__")), [])

    def test_minimal_instance_is_labeled_not_broken(self):
        tmp = H.tmp_dir()
        self.addCleanup(H.rmtree, tmp)
        proj = tmp / "m"
        r = H.wsc("init", "03", str(proj), "--minimal")
        self.assertEqual(r.returncode, 0, msg=H.out(r))
        out = H.out(H.run([sys.executable, str(H.REPO / "panel.py"), "--plain",
                          "--project", str(proj)]))
        self.assertIn("最小模式", out)

    def test_console_script_entry_exists(self):
        import tomllib
        data = tomllib.loads((H.REPO / "pyproject.toml").read_text(encoding="utf-8"))
        self.assertEqual(data["project"]["scripts"]["coharness-panel"], "coharness.panel:main")
        self.assertTrue(hasattr(panel_mod, "main"))


class TerminalIO(unittest.TestCase):
    """补的一课：全屏模式在 Windows 上第一次读键就崩（`msvcrt.flush()` 根本不存在），
    而所有测试都走 --plain，所以整整一轮都没发现。读键的解码必须是纯函数才可测。"""

    @unittest.skipUnless(sys.platform.startswith("win"), "msvcrt 分支只在 Windows 上跑")
    def test_read_key_returns_tick_without_a_console(self):
        self.assertEqual(panel_mod.read_key(0.05), "tick")

    def test_msvcrt_key_decoding(self):
        # 2026-09-29 修正：第二字符码是 VK 码低字节（旧表把 ↑/↓/← 写错位）
        self.assertEqual(panel_mod.decode_msvcrt("\r"), "ENT")
        self.assertEqual(panel_mod.decode_msvcrt("\x00", "H"), "up")
        self.assertEqual(panel_mod.decode_msvcrt("\xe0", "P"), "down")
        self.assertEqual(panel_mod.decode_msvcrt("\xe0", "K"), "left")
        self.assertEqual(panel_mod.decode_msvcrt("\xe0", "M"), "right")
        self.assertEqual(panel_mod.decode_msvcrt("j"), "j")

    def test_posix_key_decoding(self):
        self.assertEqual(panel_mod.decode_posix("\x1b", "[A"), "up")
        self.assertEqual(panel_mod.decode_posix("\x1b", "[B"), "down")
        self.assertEqual(panel_mod.decode_posix("\x1b", "x"), "ESC")
        self.assertEqual(panel_mod.decode_posix("\x7f"), "BS")


class InteractiveLoop(unittest.TestCase):
    """把 main() 的循环整条跑一遍：渲染 → 读键 → 换页 → 重建快照。

    真终端里截图只能证明"看着对"，证不了按键与刷新；这里用假 stdin/stdout 与脚本化的
    read_key 驱动，所以 CI 上（没有控制台）也一样跑得动。
    """

    def setUp(self):
        self.tmp = H.tmp_dir()
        self.addCleanup(H.rmtree, self.tmp)
        self.proj = self.tmp / "proj"
        self.assertEqual(H.wsc("init", "03", str(self.proj)).returncode, 0)
        make_card(self.proj, "T-020", items=("- [x] 一条", "- [ ] 另一条"))

    def _run(self, keys):
        import io
        script = list(keys)
        seen = []

        def fake_read_key(timeout):
            if not script:
                return "q"
            seen.append(script[0])
            return script.pop(0)

        class FakeStdin:
            @staticmethod
            def isatty():
                return True

        fake_sys = types.SimpleNamespace(stdin=FakeStdin(), stdout=io.StringIO(),
                                        stderr=io.StringIO(), path=sys.path)
        real_sys, real_key = panel_mod.sys, panel_mod.read_key
        panel_mod.sys, panel_mod.read_key = fake_sys, fake_read_key
        try:
            rc = panel_mod.main(["--project", str(self.proj)])
        finally:
            panel_mod.sys, panel_mod.read_key = real_sys, real_key
        return rc, fake_sys.stdout.getvalue(), seen

    def test_keys_walk_the_three_pages_and_quit(self):
        rc, out, keys = self._run(["ENT", "BS", "ENT", "q"])
        self.assertEqual(rc, 0)
        self.assertEqual(keys, ["ENT", "BS", "ENT", "q"])
        self.assertIn("任务看板", out)                       # 第二页
        self.assertIn("T-020", out)
        self.assertIn("验收清单", out)                       # 第三页（Enter 之后）
        self.assertIn("[#", out)                             # 一条已勾的进度条
        self.assertIn("\033[2J", out, "全屏模式要清屏重绘")
        self.assertIn("\033[?25h", out, "退出时必须把光标找回来")

    def test_down_then_enter_opens_the_selected_card(self):
        rc, out, _ = self._run(["down", "ENT", "q"])
        self.assertEqual(rc, 0)
        self.assertIn("T-020", out)
        self.assertNotIn("Traceback", out)


    def test_the_loop_never_builds_a_shallow_snapshot(self):
        """交互模式一律 deep：报警位是这个面板存在的理由，宁可多一次 rev-parse。"""
        calls, real = [], panel_mod.project_snapshot
        panel_mod.project_snapshot = lambda p, deep=True: (
            calls.append(deep), real(p, deep=deep))[1]
        try:
            rc, out, keys = self._run(["ENT", "BS", "ENT", "q"])
        finally:
            panel_mod.project_snapshot = real
        self.assertEqual(rc, 0)
        self.assertIn(True, calls)
        self.assertNotIn(False, calls, "还有一处在用浅快照，顶层报警会报成 0")


class RefreshCost(unittest.TestCase):
    """`--watch` 每 5 秒重画一次：不缓存的话每张卡每轮都要起一个 git 进程。"""

    def setUp(self):
        self.tmp = H.tmp_dir()
        self.addCleanup(H.rmtree, self.tmp)
        self.proj = self.tmp / "proj"
        self.assertEqual(H.wsc("init", "03", str(self.proj)).returncode, 0)
        git(self.proj, "init", "-q", "--initial-branch=main")
        (self.proj / "docs").mkdir(exist_ok=True)
        for cid in ("T-030", "T-031", "T-032"):
            make_card(self.proj, cid, allowed=("  - docs/",), items=("- [ ] 一条",))
        (self.proj / "docs" / "a.md").write_text("x\n", encoding="utf-8", newline="\n")
        git(self.proj, "add", "-A")
        self.assertEqual(git(self.proj, "commit", "-q", "-m", "基线").returncode, 0)
        board.cache_reset(self.proj)
        self.addCleanup(board.cache_reset, self.proj)
        self.real_git = board._git
        self.calls = []
        board._git = lambda pr, av, timeout=15: (self.calls.append(av), self.real_git(pr, av, timeout))[1]
        self.addCleanup(setattr, board, "_git", self.real_git)

    def test_second_build_only_probes_head(self):
        board.project_snapshot(self.proj)
        first = len(self.calls)
        self.calls.clear()
        snap2 = board.project_snapshot(self.proj)
        self.assertLessEqual(len(self.calls), 1,
                             f"缓存没生效：第二轮还是打了 {len(self.calls)} 次 git")
        self.assertEqual([c["commits"] for c in snap2["cards"]], [1, 1, 1],
                         "缓存不能把数据也省掉")
        self.assertGreaterEqual(first, 3, "第一轮本该真取提交与 worktree 清单，否则这条测试没意义")
        self.assertLess(len(self.calls), first, "第二轮必须比第一轮少干活")

    def test_new_commit_invalidates_the_cache(self):
        board.project_snapshot(self.proj)
        before = [c["commits"] for c in board.project_snapshot(self.proj)["cards"]]
        (self.proj / "docs" / "b.md").write_text("y\n", encoding="utf-8", newline="\n")
        git(self.proj, "add", "-A")
        self.assertEqual(git(self.proj, "commit", "-q", "-m", "又一次提交").returncode, 0)
        after = [c["commits"] for c in board.project_snapshot(self.proj)["cards"]]
        self.assertEqual(after, [b + 1 for b in before],
                         "HEAD 一变必须重取提交数——面板不许拿旧账当现状")

    def test_commit_count_is_not_capped_at_the_recent_three(self):
        """"边界内提交 N 次"要按全量明细数，recent 只是展示面截取——
        以前 n_commits 被最近 3 条整体覆盖，提交 5 次也显示 3，"提交了没勾"的判定跟着失真。"""
        for i in range(4):
            (self.proj / "docs" / f"b{i}.md").write_text(f"{i}\n", encoding="utf-8", newline="\n")
            git(self.proj, "add", "-A")
            self.assertEqual(git(self.proj, "commit", "-q", "-m", f"第{i}次").returncode, 0)
        snap = board.project_snapshot(self.proj)
        self.assertEqual([c["commits"] for c in snap["cards"]], [5, 5, 5],
                         "5 次边界内提交就得显示 5，不许被 recent 的 3 条封顶")
        self.assertEqual(len(snap["cards"][0]["recent"]), 3, "recent 是展示面截取，最多 3 条")

    def test_git_cache_is_per_project(self):
        """同前缀的两个项目轮流出快照：各报各的数，且回访命中缓存（≤1 次 git）。
        HEAD 单值缓存会让两个项目互相当对方的失效器——watch 多项目时命中率归零。"""
        proj_b = self.tmp / "proj-b"
        self.assertEqual(H.wsc("init", "03", str(proj_b)).returncode, 0)
        git(proj_b, "init", "-q", "--initial-branch=main")
        (proj_b / "docs").mkdir(exist_ok=True)
        make_card(proj_b, "T-033", allowed=("  - docs/",), items=("- [ ] 一条",))
        (proj_b / "docs" / "x.md").write_text("x\n", encoding="utf-8", newline="\n")
        git(proj_b, "add", "-A")
        self.assertEqual(git(proj_b, "commit", "-q", "-m", "B 一次").returncode, 0)
        (proj_b / "docs" / "y.md").write_text("y\n", encoding="utf-8", newline="\n")
        git(proj_b, "add", "-A")
        self.assertEqual(git(proj_b, "commit", "-q", "-m", "B 两次").returncode, 0)
        board.cache_reset(self.proj)
        board.cache_reset(proj_b)
        commits_of = lambda s, cid: next(c["commits"] for c in s["cards"] if c["id"] == cid)
        self.assertEqual(commits_of(board.project_snapshot(self.proj), "T-030"), 1)
        self.assertEqual(commits_of(board.project_snapshot(proj_b), "T-033"), 2)
        self.calls.clear()
        again = board.project_snapshot(self.proj)
        self.assertEqual(commits_of(again, "T-030"), 1, "B 的数字不许串到 A 上")
        self.assertLessEqual(len(self.calls), 1,
                             f"回访 A 还是重打了 {len(self.calls)} 次 git：缓存被 B 清掉了")


if __name__ == "__main__":
    unittest.main()
