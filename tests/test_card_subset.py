"""CARD-CONVENTION 子集：支持的写法照单解析，超出去的写法逐条响亮报错（ADR-10）。

原来 `parse_frontmatter` / `_yaml_list_under` 是两套各自的正则，遇到嵌套值、引号、
注释、未闭合 '---'、重复键会静默给出错的值——比如 `title:` 空值被当成空列表，
`str([])` = "[]" 非空，于是"title 为空"这条执法从来没生效过。
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import helpers as H

FIX = Path(__file__).resolve().parent / "fixtures"

GOOD = {
    "basic.md": {
        "id": "T-101", "title": "基础卡", "status": "doing",
        "assignee": ["zcode-0926a"], "labels": [], "dependencies": ["T-100"],
        "priority": "high", "created_date": "2026-09-20",
        "updated_date": "2026-09-28 09:00",
    },
    # 空值就是空值（不是空列表），这样 "title 为空" 才抓得到
    "empty-values.md": {
        "id": "T-105", "title": "", "status": "todo", "assignee": "", "labels": [],
        "created_date": "2026-09-20", "updated_date": "2026-09-28 09:00",
    },
    # 引号内的 ': ' 与 # 不算结构符
    "quotes.md": {
        "id": "T-103", "title": "方案: A 与 B", "status": "review",
        "assignee": ["codex-0926b"], "labels": ["REQ-3", "REQ-4"],
        "created_date": "2026-09-20", "updated_date": "2026-09-28 09:00",
    },
    # 整行注释与行尾注释
    "comments.md": {
        "id": "T-102", "title": "带注释的卡", "status": "doing",
        "assignee": ["zcode-0926a"], "labels": [],
        "created_date": "2026-09-20", "updated_date": "2026-09-28 09:00",
    },
    # key: 下挂块列表
    "block-list.md": {
        "id": "T-104", "title": "块列表卡", "status": "doing",
        "assignee": ["zcode-0926a"], "labels": ["REQ-1", "REQ 2"],
        "created_date": "2026-09-20", "updated_date": "2026-09-28 09:00",
    },
}

# 夹具名 -> (出错行号, 消息里必须出现的词)
UNSUPPORTED = {
    "tab-nested.md": (5, "制表符"),
    "duplicate-key.md": (4, "重复键"),
    "unterminated.md": (1, "没有结束的 '---'"),
    "block-scalar.md": (5, "块标量"),
    "flow-map.md": (4, "行内 map"),
    "anchor.md": (3, "锚点"),
    "bare-dash.md": (4, "已经有值"),
    "multiline-scalar.md": (5, "多行值"),
    "nested-map.md": (5, "嵌套 map"),
    "list-in-list.md": (3, "又套了一层"),
    "colon-unquoted.md": (3, "用引号"),
    "dash-nospace.md": (4, "少空格"),
    "unclosed-bracket.md": (3, "缺 ']'"),
    "scalar-then-item.md": (4, "已经有值"),
    "bom.md": (1, "BOM"),
}


class SubsetParser(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = H.load_check_module()

    def parse(self, name, folder="good"):
        p = FIX / folder / name
        return self.mod.parse_frontmatter(p, p.read_text(encoding="utf-8"))

    def test_supported_subset_parses_exactly(self):
        for name, expected in GOOD.items():
            meta, body = self.parse(name)
            self.assertEqual(meta, expected, msg=name)
            self.assertIn("## 边界", body, msg=name)

    def test_every_superset_fails_loud_with_line(self):
        for name, (line, word) in UNSUPPORTED.items():
            p = FIX / "unsupported" / name
            with self.assertRaises(self.mod.CardFormatError, msg=name) as cm:
                self.mod.parse_frontmatter(p, p.read_text(encoding="utf-8"))
            text = str(cm.exception)
            self.assertIn(f"{p.as_posix()}:{line}", text, msg=f"{name} -> {text}")
            self.assertIn(word, text, msg=f"{name} -> {text}")
            self.assertIn(name.split(".")[0], text)

    def test_boundary_section_uses_the_same_tokenizer(self):
        cases = {
            "nested-item.md": (13, "嵌套结构"),
            "prose.md": (12, "看不懂的行"),
        }
        for name, (line, word) in cases.items():
            p = FIX / "boundary" / name
            text = p.read_text(encoding="utf-8")
            meta, body = self.mod.parse_frontmatter(p, text)
            body_first_line = text.splitlines().index("---", 1) + 2
            with self.assertRaises(self.mod.CardFormatError, msg=name) as cm:
                self.mod.parse_boundary(body, p.as_posix(), body_first_line=body_first_line)
            self.assertIn(f"{p.as_posix()}:{line}", str(cm.exception))
            self.assertIn(word, str(cm.exception))

    def test_scalar_boundary_value_is_accepted_as_one_item(self):
        p = FIX / "boundary" / "scalar-allowed.md"
        text = p.read_text(encoding="utf-8")
        meta, body = self.mod.parse_frontmatter(p, text)
        first = text.splitlines().index("---", 1) + 2
        allowed, forbidden, has = self.mod.parse_boundary(body, p.as_posix(), body_first_line=first)
        self.assertTrue(has)
        self.assertEqual(allowed, ["docs/"])
        self.assertEqual(forbidden, ["AGENTS.md"])


class LoudFailureReachesExitCode(unittest.TestCase):
    """报错要走到退出码，否则人看不见。"""

    def setUp(self):
        self.tmp = H.tmp_dir()
        self.addCleanup(H.rmtree, self.tmp)
        self.proj = H.make_project(self.tmp)

    def put(self, name, folder):
        src = (FIX / folder / name).read_text(encoding="utf-8")
        d = self.proj / "backlog" / "tasks"
        d.mkdir(parents=True, exist_ok=True)
        (d / name).write_text(src, encoding="utf-8")
        return d / name

    def test_malformed_card_blocks_with_card_format_label(self):
        self.put("nested-map.md", "unsupported")
        res = H.check(self.proj, "--tasks")
        self.assertEqual(res.returncode, 1, msg=H.out(res))
        self.assertIn("[卡格式]", H.out(res))
        self.assertIn("nested-map.md:5", H.out(res))

    def test_bom_card_blocks(self):
        self.put("bom.md", "unsupported")
        res = H.check(self.proj, "--tasks")
        self.assertEqual(res.returncode, 1, msg=H.out(res))
        self.assertIn("BOM", H.out(res))

    def test_closing_marker_with_trailing_whitespace_does_not_crash(self):
        """tokenizer 按 strip 后相等放行 `--- `，load_cards 定位卡体却用 lines.index
        要求逐字节相等——ValueError 把整个 check 崩成 traceback。两处必须同一口径：
        tokenizer 放行的写法，定位也放行。"""
        src = (FIX / "good" / "basic.md").read_text(encoding="utf-8")
        head, _, body = src.rpartition("\n---\n")
        d = self.proj / "backlog" / "tasks"
        d.mkdir(parents=True, exist_ok=True)
        (d / "ws-close.md").write_text(head + "\n--- \n" + body,
                                       encoding="utf-8", newline="\n")
        res = H.check(self.proj, "--tasks")
        self.assertNotIn("Traceback", H.out(res), "闭合行带空白不该把整个 check 崩掉")
        self.assertNotIn("[卡格式]", H.out(res))
        self.assertEqual(res.returncode, 0, msg=H.out(res))

    def test_boundary_nesting_is_not_disguised_as_empty_allowed(self):
        # 原解析器把嵌套结构读成空列表，报的是"allowed_paths 为空"，真因被掩盖
        self.put("nested-item.md", "boundary")
        out = H.out(H.check(self.proj, "--tasks"))
        self.assertIn("[卡格式]", out)
        self.assertNotIn("allowed_paths 为空", out)

    def test_empty_title_is_caught_now(self):
        self.put("empty-values.md", "good")
        out = H.out(H.check(self.proj, "--tasks"))
        self.assertIn("title 为空", out)

    def test_valid_cards_pass_the_rules_too(self):
        # 只放一张：两张 doing 卡若边界相同，会被"边界交集不得并行"判违规
        self.put("basic.md", "good")
        res = H.check(self.proj, "--tasks")
        self.assertEqual(res.returncode, 0, msg=H.out(res))
        self.assertNotIn("[卡格式]", H.out(res))


if __name__ == "__main__":
    unittest.main()
