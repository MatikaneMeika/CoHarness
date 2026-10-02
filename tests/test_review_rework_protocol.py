"""审阅返工闭环的协议钉子。

reviewer fail 后卡片必须先回到 doing，原实现者修完并勾掉意见后才能再进 review；
这组断言把五处协议文档的关键口径钉在一起，防止只改一处造成流程漂移。
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import helpers as H


class ReviewReworkProtocol(unittest.TestCase):
    def test_reviewer_fail_returns_card_to_doing(self):
        reviewer = (H.SKELETON / ".agent" / "roles" / "reviewer.md").read_text(encoding="utf-8")
        self.assertIn("## 审阅意见", reviewer)
        self.assertIn("卡退回 `doing`", reviewer)
        self.assertIn("原 assignee 和 worktree 保持不变", reviewer)

    def test_card_convention_marks_unchecked_notes_as_rework_only(self):
        conv = (H.SKELETON / ".agent" / "tasks" / "CARD-CONVENTION.md").read_text(encoding="utf-8")
        self.assertIn("`doing` 可以带未勾选审阅意见", conv)
        self.assertIn("`review` / `done` 不得带未勾选审阅意见", conv)

    def test_parallel_protocol_requires_new_commit_before_review(self):
        proto = (H.SKELETON / ".agent" / "workflows" / "parallel-protocol.md").read_text(encoding="utf-8")
        self.assertIn("返工后追加新 commit", proto)
        self.assertIn("勾完审阅意见", proto)
        self.assertIn("再退回 `review`", proto)

    def test_new_feature_workflow_names_the_return_loop(self):
        feature = (H.SKELETON / ".agent" / "workflows" / "new-feature.md").read_text(encoding="utf-8")
        self.assertIn("写审阅意见并退回 `doing`", feature)
        self.assertIn("返工后追加 commit", feature)

    def test_integrator_blocks_unchecked_review_notes(self):
        integrator = (H.SKELETON / ".agent" / "roles" / "integrator.md").read_text(encoding="utf-8")
        self.assertIn("存在未勾选审阅意见的卡不得合并", integrator)
        self.assertIn("退回原 assignee 的 `doing`", integrator)


if __name__ == "__main__":
    unittest.main()
