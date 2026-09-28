"""本机登记表 + 跨项目摩擦统计（计划书 W7/A3）：晋升门槛"同类摩擦 ≥2 次"的机器证据源。

登记表是纯本地一个 json（路径 + 骨架名 + 本体 commit + 时间）：零网络，位置可用
COHARNESS_HOME 挪走，删掉文件即不再参与统计。统计只出机械计数与来源，
"是不是真的同一件事"仍归人判——这条线在 cmd_improve_cross 的注释里也写着。
"""
import json
import unittest
from pathlib import Path

import helpers as H

HEADER = ("| 编号 | 日期 | 类别 | 场景（哪个流程/角色卡在哪） | 问题或缺口 | 提议改动 |"
          " 证据（发生了什么） | 状态 |")
SEPARATOR = "|---|---|---|---|---|---|---|---|"
TEMPLATE = "# improvements — 登记\n\n" + HEADER + "\n" + SEPARATOR + "\n"


def row(cid, proposal, status="登记", category="规则", scene="认领"):
    return f"| {cid} | 2026-09-28 | {category} | {scene} | 卡改动被拦 | {proposal} | 冒烟 | {status} |"


class CrossGround(unittest.TestCase):
    def setUp(self):
        self.tmp = H.tmp_dir()
        self.addCleanup(H.rmtree, self.tmp)
        self.env = {"COHARNESS_HOME": str(self.tmp / "coh")}
        self.reg = self.tmp / "coh" / "projects.json"

    def entries(self):
        return json.loads(self.reg.read_text(encoding="utf-8"))

    def instantiate(self, name, rows=()):
        proj = self.tmp / name
        r = H.wsc("init", "03", str(proj), extra_env=self.env)
        self.assertEqual(r.returncode, 0, msg=H.out(r))
        if rows:
            (proj / ".agent" / "improvements.md").write_text(
                TEMPLATE + "\n".join(rows) + "\n", encoding="utf-8")
        return proj

    def cross(self):
        r = H.wsc("improve", "--cross", extra_env=self.env)
        self.assertEqual(r.returncode, 0, msg=H.out(r))
        return H.out(r)

    def test_init_registers_path_skeleton_and_commit(self):
        proj = self.instantiate("p1")
        data = self.entries()
        self.assertEqual(len(data), 1)
        self.assertEqual(Path(data[0]["path"]), proj)
        self.assertEqual(data[0]["skeleton"], "03-multi-harness-project")
        self.assertRegex(data[0]["skeleton_commit"], r"^[0-9a-f]{7,}$")
        self.assertRegex(data[0]["instantiated_at"], r"^\d{4}-\d{2}-\d{2}")

    def test_re_init_same_project_does_not_duplicate_the_entry(self):
        proj = self.instantiate("p1")
        again = H.wsc("init", "03", str(proj), extra_env=self.env)
        self.assertNotEqual(again.returncode, 0, "非空目录应被 init 拒绝")
        self.assertIn("目标目录非空", H.out(again))
        self.assertEqual(len([e for e in self.entries()
                              if Path(e["path"]) == proj]), 1)

    def test_two_inits_register_two_distinct_entries(self):
        p1 = self.instantiate("p1")
        p2 = self.instantiate("p2")
        paths = {Path(e["path"]) for e in self.entries()}
        self.assertEqual(paths, {p1, p2})

    def test_two_projects_with_the_same_proposal_reach_the_threshold(self):
        self.instantiate("p1", [row("I-001", "卡片与登记自授权放行")])
        self.instantiate("p2", [row("I-001", "卡片与登记自授权放行")])
        text = self.cross()
        self.assertIn("扫描 2 个实例", text)
        self.assertIn("2 个项目 / 2 条", text)
        self.assertIn("达到 ≥2 门槛，可进待审", text)
        self.assertIn("p1 I-001", text)
        self.assertIn("p2 I-001", text)

    def test_single_project_is_flagged_as_isolated_evidence(self):
        self.instantiate("p1", [row("I-001", "认领原子化")])
        text = self.cross()
        self.assertIn("1 个项目 / 1 条", text)
        self.assertIn("单项目孤证，继续攒证据", text)

    def test_promoted_and_rejected_entries_are_not_counted(self):
        self.instantiate("p1", [row("I-001", "认领原子化", status="已晋升"),
                               row("I-002", "改措辞", status="已驳回")])
        self.instantiate("p2", [row("I-001", "认领原子化", status="已晋升")])
        text = self.cross()
        self.assertIn("无非终态条目", text)

    def test_different_proposals_are_not_merged(self):
        self.instantiate("p1", [row("I-001", "认领原子化")])
        self.instantiate("p2", [row("I-001", "服务端钩子门禁")])
        text = self.cross()
        self.assertEqual(text.count("单项目孤证"), 2)
        self.assertNotIn("达到 ≥2 门槛", text)

    def test_stale_registered_path_is_skipped_with_a_note(self):
        dead = self.instantiate("p1", [row("I-001", "认领原子化")])
        self.instantiate("p2", [row("I-001", "认领原子化")])
        H.rmtree(dead)
        text = self.cross()
        self.assertIn("[跳过]", text)
        self.assertIn("扫描 1 个实例（另有 1 个登记路径已失效）", text)
        self.assertIn("1 个项目 / 1 条", text)

    def test_empty_registry_tells_you_how_to_start(self):
        r = H.wsc("improve", "--cross", extra_env=self.env)
        self.assertNotEqual(r.returncode, 0)
        msg = H.out(r)
        self.assertIn("本机登记表是空的", msg)
        self.assertIn("COHARNESS_HOME", msg)

    def test_plain_improve_still_reads_one_project_only(self):
        """--cross 不能改变默认行为：不带它只读一个项目，也不碰登记表。"""
        proj = self.instantiate("p1", [row("I-001", "认领原子化")])
        text = H.out(H.wsc("improve", str(proj), extra_env=self.env))
        self.assertIn("待处理改进 1 条", text)
        self.assertNotIn("个项目", text)
        self.assertTrue(self.reg.exists(), "init 就应当已经登记")


if __name__ == "__main__":
    unittest.main()
