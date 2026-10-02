"""Backlog.md 1.53.0 真实 CLI 产物夹具测试（W21 产物兼容，T-109 钉入，T-112 修复）。

验证 check.py 解析 Backlog 真实 frontmatter 的语义准确性：
- 7 张绿夹具（basic/quotes/hash/lists/empty/labels/updated）语义完全一致；
- 1 张红夹具（escaped-quote）验证 YAML 成对单引号 '' 转义修复（title == "Fix user's issue #123"）；
- _strip_comment 与 _unquote 针对单双引号转义与尾部注释的单元契约。
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import helpers as H

FIX = Path(__file__).resolve().parent / "fixtures"

GREEN_FIXTURES = {
    "backlog-real-basic.md": {
        "id": "T-101",
        "title": "Basic Task CLI Real Verification",
        "status": "todo",
        "assignee": ["@developer-01"],
        "created_date": "2026-10-02 09:44",
        "labels": ["core"],
        "dependencies": [],
        "ordinal": "1000",
    },
    "backlog-real-quotes.md": {
        "id": "T-102",
        "title": 'Plan: Evaluation of "Option A" and "Option B"',
        "status": "todo",
        "assignee": ["@developer-01"],
        "created_date": "2026-10-02 09:44",
        "labels": [],
        "dependencies": [],
        "ordinal": "2000",
    },
    "backlog-real-hash.md": {
        "id": "T-103",
        "title": "Fix issue #42 and #99",
        "status": "todo",
        "assignee": ["@developer-01"],
        "created_date": "2026-10-02 09:44",
        "labels": ["bug"],
        "dependencies": [],
        "ordinal": "3000",
    },
    "backlog-real-lists.md": {
        "id": "T-104",
        "title": "Multi Assignees and Labels",
        "status": "todo",
        "assignee": ["@alice", "@bob"],
        "created_date": "2026-10-02 09:44",
        "labels": ["frontend", "backend", "urgent"],
        "dependencies": ["T-101", "T-102"],
        "ordinal": "4000",
    },
    "backlog-real-empty.md": {
        "id": "T-105",
        "title": "Empty Fields Task",
        "status": "todo",
        "assignee": [],
        "created_date": "2026-10-02 09:44",
        "labels": [],
        "dependencies": [],
        "ordinal": "5000",
    },
    "backlog-real-labels.md": {
        "id": "T-106",
        "title": "Role Labeled Task",
        "status": "todo",
        "assignee": ["@tester-01"],
        "created_date": "2026-10-02 09:44",
        "labels": ["role:tester", "scope:cli"],
        "dependencies": [],
        "ordinal": "6000",
    },
    "backlog-real-updated.md": {
        "id": "T-107",
        "title": "Task with Updated Date",
        "status": "doing",
        "assignee": ["@developer-01"],
        "created_date": "2026-10-02 09:44",
        "updated_date": "2026-10-02 09:44",
        "labels": [],
        "dependencies": [],
        "ordinal": "7000",
    },
}

RED_FIXTURE = {
    "backlog-real-escaped-quote.md": {
        "id": "T-108",
        "title": "Fix user's issue #123",
        "status": "todo",
        "assignee": ["@developer-01"],
        "created_date": "2026-10-02 09:44",
        "labels": [],
        "dependencies": [],
        "ordinal": "8000",
    },
}


class TestBacklogRealFixtures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = H.load_check_module()

    def test_seven_green_fixtures_parse_exact_semantics(self):
        for name, expected in GREEN_FIXTURES.items():
            p = FIX / name
            self.assertTrue(p.exists(), f"夹具不存在: {p}")
            meta, body = self.mod.parse_frontmatter(p, p.read_text(encoding="utf-8"))
            self.assertEqual(meta, expected, f"绿夹具 {name} 解析语义不符")
            self.assertIn("## 边界", body, f"绿夹具 {name} 卡体缺边界节")

    def test_escaped_quote_red_fixture_proves_defect_and_fix(self):
        p = FIX / "backlog-real-escaped-quote.md"
        self.assertTrue(p.exists(), f"夹具不存在: {p}")
        meta, body = self.mod.parse_frontmatter(p, p.read_text(encoding="utf-8"))
        expected = RED_FIXTURE["backlog-real-escaped-quote.md"]
        self.assertEqual(meta.get("title"), expected["title"],
                         f"title 解析错误（被截断）：得到 {meta.get('title')!r}，应为 {expected['title']!r}")
        self.assertEqual(meta, expected, "escaped-quote 夹具整体解析结果与真实语义不符")
        self.assertIn("## 边界", body)

    def test_strip_comment_escaped_quotes_unit(self):
        _strip = self.mod._strip_comment
        # 单引号 '' 转义
        self.assertEqual(_strip("'Fix user''s issue #123'"), "'Fix user''s issue #123'")
        self.assertEqual(_strip("'Fix user''s issue #123'  # 尾部注释"), "'Fix user''s issue #123'")
        # 双引号 \" 转义
        self.assertEqual(_strip(r'"Fix \"user\" issue #123"'), r'"Fix \"user\" issue #123"')
        self.assertEqual(_strip(r'"Fix \"user\" issue #123"  # 尾部注释'), r'"Fix \"user\" issue #123"')
        # 普通无引号或无转义
        self.assertEqual(_strip("plain value  # comment"), "plain value")
        self.assertEqual(_strip("''"), "''")
        self.assertEqual(_strip('""'), '""')

    def test_unquote_unescapes_quotes_unit(self):
        _unquote = self.mod._unquote
        # 单引号 '' 反转义为 '
        self.assertEqual(_unquote("'Fix user''s issue #123'"), "Fix user's issue #123")
        self.assertEqual(_unquote("''''"), "'")
        # 双引号 \" 反转义为 "
        self.assertEqual(_unquote(r'"Fix \"user\" issue #123"'), 'Fix "user" issue #123')
        # 普通值保持
        self.assertEqual(_unquote("'normal'"), "normal")
        self.assertEqual(_unquote('"normal"'), "normal")
        self.assertEqual(_unquote("unquoted"), "unquoted")


if __name__ == "__main__":
    unittest.main()
