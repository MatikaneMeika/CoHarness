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
        # 比 resolve 后的位置，不比字符串：runner 的 TEMP 是 8.3 短名（C:\Users\RUNNER~1\…），
        # 而 wsc 存的是长名，两边指向同一个目录。
        self.assertEqual(Path(data[0]["path"]).resolve(), proj.resolve())
        self.assertEqual(data[0]["skeleton"], "03-multi-harness-project")
        self.assertRegex(data[0]["skeleton_commit"], r"^[0-9a-f]{7,}$")
        self.assertRegex(data[0]["instantiated_at"], r"^\d{4}-\d{2}-\d{2}")

    def test_failed_registry_swap_leaves_the_old_file_intact(self):
        """登记表写盘走 tmp + os.replace 原子换入：换入失败要报错返回，旧表原样保留。
        直接 write_text 的旧写法在并行 init 撞写、或写一半崩掉时会把整份 JSON 报废。"""
        proj = self.instantiate("p-atomic")
        old = self.reg.read_text(encoding="utf-8")
        import importlib.util
        import os
        spec = importlib.util.spec_from_file_location("coh_wsc_atomic", H.WSC)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        real = os.replace

        def boom(src, dst):
            raise OSError("simulated crash between tmp write and swap")

        prev_env = os.environ.get("COHARNESS_HOME")
        os.environ["COHARNESS_HOME"] = str(self.tmp / "coh")
        os.replace = boom
        try:
            _, err = mod.register_project(Path(proj), "03-multi-harness-project")
        finally:
            os.replace = real
            if prev_env is None:
                os.environ.pop("COHARNESS_HOME", None)
            else:
                os.environ["COHARNESS_HOME"] = prev_env
        self.assertTrue(err, "换入失败必须报错，不许当没事")
        self.assertEqual(self.reg.read_text(encoding="utf-8"), old, "旧表一个字节都不许动")

    def test_short_and_long_paths_register_as_the_same_project(self):
        """Windows 专供：用 8.3 短名当参数装机，登记表里不许因此多出第二条记录。"""
        short = H.short_path(self.tmp)
        if not short or short == self.tmp:
            self.skipTest("这个卷没启用 8.3 短名，造不出 runner 的条件")
        proj = short / "p1"
        r = H.wsc("init", "03", str(proj), extra_env=self.env)
        self.assertEqual(r.returncode, 0, msg=H.out(r))
        again = H.wsc("init", "03", str(self.tmp / "p1"), extra_env=self.env)
        self.assertNotEqual(again.returncode, 0, "短名与长名是同一个目录，第二次必须被「非空」挡住")
        self.assertEqual(len([e for e in self.entries()
                              if Path(e["path"]).resolve() == (self.tmp / "p1").resolve()]), 1,
                         "同一路径的两种写法不许各占一条")

    def test_re_init_same_project_does_not_duplicate_the_entry(self):
        proj = self.instantiate("p1")
        again = H.wsc("init", "03", str(proj), extra_env=self.env)
        self.assertNotEqual(again.returncode, 0, "非空目录应被 init 拒绝")
        self.assertIn("目标目录非空", H.out(again))
        self.assertEqual(len([e for e in self.entries()
                              if Path(e["path"]).resolve() == proj.resolve()]), 1)

    def test_two_inits_register_two_distinct_entries(self):
        p1 = self.instantiate("p1")
        p2 = self.instantiate("p2")
        paths = {Path(e["path"]).resolve() for e in self.entries()}
        self.assertEqual(paths, {p1.resolve(), p2.resolve()})

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
