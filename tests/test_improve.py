"""wsc improve 的读取链路：编号约定、状态机、模板里的示例行不算条目。

原实现只收以 `| I-` 开头的行，而 4 份 improvements.md 模板的示例行是 `| （示例） |`，
`I-xxx` 编号只写在骨架库的 docs/EVOLUTION-PROCESS.md 里，骨架内没人被告知 ——
于是登记了条目也永远打印"无待处理改进"。
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import helpers as H

HEADER = ("| 编号 | 日期 | 类别 | 场景（哪个流程/角色卡在哪） | 问题或缺口 | 提议改动 |"
          " 证据（发生了什么） | 状态 |")
SEPARATOR = "|---|---|---|---|---|---|---|---|"

ROWS = [
    "| I-001 | 2026-09-20 | 规则 | 认领 | 卡改动被拦 | 常驻规则卡 | 见冒烟 | 登记 |",
    "| I-002 | 2026-09-21 | 能力 | 配图 | 缺图像 skill | 装某 skill | 试过一次 | 试点中 |",
    "| I-003 | 2026-09-22 | 规则 | 收工 | 汇报无模板 | 加收尾节 | 返工一次 | 待审 |",
    "| I-004 | 2026-09-23 | 规则 | 命名 | 已收紧 | 进 check.py | 已执法 | 已晋升 |",
    "| I-005 | 2026-09-24 | 规则 | 口味 | 不喜欢 | 改措辞 | 无 | 已驳回 |",
]

TEMPLATE = ("# improvements — 登记\n\n> 门槛见骨架库。\n\n" + HEADER + "\n" + SEPARATOR + "\n")


class ImproveList(unittest.TestCase):
    def setUp(self):
        self.tmp = H.tmp_dir()
        self.addCleanup(H.rmtree, self.tmp)
        self.proj = H.make_project(self.tmp)

    def ledger(self, rows):
        text = TEMPLATE + "\n".join(rows) + "\n"
        (self.proj / ".agent" / "improvements.md").write_text(text, encoding="utf-8")

    def run_improve(self):
        return H.out(H.wsc("improve", str(self.proj)))

    def test_lists_the_three_pending_states(self):
        self.ledger(ROWS)
        text = self.run_improve()
        self.assertIn("待处理改进 3 条", text)
        for cid, state in (("I-001", "登记"), ("I-002", "试点中"), ("I-003", "待审")):
            self.assertIn(f"{cid} [{state}]", text)
        self.assertNotIn("I-004", text)
        self.assertNotIn("I-005", text)

    def test_bad_id_is_warned_not_dropped_silently(self):
        self.ledger(["| 1 | 2026-09-25 | 规则 | 某处 | 问题 | 改法 | 证据 | 登记 |"])
        text = self.run_improve()
        self.assertIn("编号", text)
        self.assertIn("I-xxx", text)

    def test_unknown_status_is_warned(self):
        self.ledger(["| I-006 | 2026-09-26 | 规则 | 某处 | 问题 | 改法 | 证据 | 进行中 |"])
        text = self.run_improve()
        self.assertIn("I-006", text)
        self.assertIn("状态", text)
        self.assertNotIn("待处理改进 1 条", text)

    def test_shipped_templates_have_no_entries(self):
        for skeleton in ("01-solo-code", "02-study-office", "03-multi-harness-project",
                         "04-doc-production"):
            proj = self.tmp / skeleton
            (proj / ".agent").mkdir(parents=True, exist_ok=True)
            src = Path(H.REPO) / skeleton / ".agent" / "improvements.md"
            (proj / ".agent" / "improvements.md").write_text(
                src.read_text(encoding="utf-8"), encoding="utf-8")
            text = H.out(H.wsc("improve", str(proj)))
            self.assertIn("无待处理改进", text, msg=skeleton)
            self.assertNotIn("示例", text, msg=f"{skeleton} 的示例行不该被当条目")

    def test_all_four_templates_identical_and_document_the_id(self):
        texts = {}
        for skeleton in ("01-solo-code", "02-study-office", "03-multi-harness-project",
                         "04-doc-production"):
            p = Path(H.REPO) / skeleton / ".agent" / "improvements.md"
            texts[skeleton] = p.read_text(encoding="utf-8")
        first = texts["01-solo-code"]
        for name, text in texts.items():
            self.assertEqual(text, first, msg=f"{name} 与其他骨架的登记模板不一致")
        self.assertIn("I-001", first, "模板要写明编号约定，否则 improve 读不到条目")
        self.assertEqual(first.count(HEADER), 1)


if __name__ == "__main__":
    unittest.main()
