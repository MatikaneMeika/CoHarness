"""evolve.py：晋升审核的机器侧（计划书 W5 命令化 + W8 patch 化与三证门禁）。

分工要能被测试钉住：机器只答可数的部分（状态机合法性、跨项目同类计数、证据能不能翻出来、
提议落点在不在），有效性与必要性归人/LLM 且必须留 json 痕迹；晋升写回前必须过
--apply-check（临时副本试装 + 全套自测）与 --verify-record（缺证即红）。
两条 --apply-check 用例会各跑一遍全套自测（约 2 分钟/条），因为门禁的价值就在"真跑"。
"""
import difflib
import json
import os
import sys
import unittest
from pathlib import Path

import helpers as H

EVOLVE = H.REPO / "evolve.py"

HEADER = ("| 编号 | 日期 | 类别 | 场景（哪个流程/角色卡在哪） | 问题或缺口 | 提议改动 |"
          " 证据（发生了什么） | 状态 |")
SEPARATOR = "|---|---|---|---|---|---|---|---|"
TEMPLATE = "# improvements — 登记\n\n" + HEADER + "\n" + SEPARATOR + "\n"


def row(cid, proposal, evidence, status="登记", category="规则", scene="认领"):
    return f"| {cid} | 2026-09-28 | {category} | {scene} | 卡改动被拦 | {proposal} | {evidence} | {status} |"


# 门禁的递归防线：evolve.py 用 COHARNESS_TRIAL 标记"这是一次试装里的自测"，
# 那种跑法里再调 --apply-check 就是让门禁自己套自己，所以这两条用例跳过。
IN_TRIAL = bool(os.environ.get("COHARNESS_TRIAL"))


def run_evolve(*args, extra_env=None, timeout=180):
    return H.run([sys.executable, EVOLVE, *args], cwd=H.REPO, extra_env=extra_env,
                 timeout=timeout)


def make_patch(repo, rel, old, new):
    """在工作树外造一个 -p1 可套的统一差异（difflib 直出，路径头写成 a/<rel> b/<rel>）。"""
    tmp = H.tmp_dir()
    src = (repo / rel).read_text(encoding="utf-8")
    assert old in src, f"{rel} 里找不到要改的行：{old}"
    patched = src.replace(old, new, 1)
    diff = "".join(difflib.unified_diff(
        src.splitlines(keepends=True), patched.splitlines(keepends=True),
        fromfile=f"a/{rel}", tofile=f"b/{rel}", n=3))
    p = tmp / "trial.diff"
    p.write_text(diff, encoding="utf-8", newline="\n")
    return tmp, p


class EvolveTool(unittest.TestCase):
    def setUp(self):
        self.tmp = H.tmp_dir()
        self.addCleanup(H.rmtree, self.tmp)
        self.env_home = str(self.tmp / "home")
        self.projects = []
        for tag in ("p1", "p2"):
            proj = self.tmp / tag
            r = H.run([sys.executable, H.WSC, "init", "03", str(proj)],
                      extra_env={"COHARNESS_HOME": self.env_home})
            self.assertEqual(r.returncode, 0, msg=H.out(r))
            self.projects.append(proj)

    def ledger(self, proj, rows):
        (proj / ".agent" / "improvements.md").write_text(
            TEMPLATE + "\n".join(rows) + "\n", encoding="utf-8")

    def run_evo(self, *args, timeout=180):
        return run_evolve(*args, extra_env={"COHARNESS_HOME": self.env_home}, timeout=timeout)

    def test_rubric_is_read_from_the_doc_not_copied(self):
        r = self.run_evo("--rubric")
        self.assertEqual(r.returncode, 0, msg=H.out(r))
        text = H.out(r)
        doc = (H.REPO / "docs" / "EVOLUTION-PROCESS.md").read_text(encoding="utf-8")
        for name in ("真实性", "普遍性", "有效性", "兼容性", "必要性"):
            self.assertIn(name, text)
            self.assertIn(name, doc)
        self.assertEqual(len([l for l in text.splitlines() if l.strip().startswith(tuple("12345"))]), 5)

    def test_machine_findings_count_friction_across_registered_projects(self):
        same = "卡片与登记自授权放行"
        self.ledger(self.projects[0], [row("I-001", same, "见 tests/test_stats.py")])
        self.ledger(self.projects[1], [row("I-001", same, "见 tests/test_stats.py")])
        text = H.out(self.run_evo(str(self.projects[0])))
        self.assertIn("2 个项目登记过同类", text)
        self.assertIn("tests/test_stats.py", text)
        self.assertNotIn("翻不到", text)

    def test_unregistered_project_still_joins_the_count(self):
        """被审项目可能装机时还没登记表：审核要把它自己也算进计数，不能报"0 个实例"。"""
        solo = self.tmp / "solo"
        r = H.run([sys.executable, H.WSC, "init", "03", str(solo)],
                  extra_env={"COHARNESS_HOME": str(self.tmp / "other-home")})
        self.assertEqual(r.returncode, 0, msg=H.out(r))
        self.ledger(solo, [row("I-001", "认领原子化", "见 tests/test_claim.py")])
        text = H.out(self.run_evo(str(solo)))
        self.assertIn("已并入计数", text)
        self.assertIn("待审 1 条", text)
        self.assertIn("tests/test_claim.py", text)
        self.assertNotIn("翻不到", text, "按登记表数不到自己时，证据仍要能在骨架库里翻出来")

    def test_evidence_that_cannot_be_found_is_called_out(self):
        self.ledger(self.projects[0], [row("I-002", "加个门禁", "见 tests/根本不存在.py")])
        text = H.out(self.run_evo(str(self.projects[0])))
        self.assertIn("翻不到（要补出处）", text)

    def test_capability_gap_lands_on_router_not_skeleton(self):
        self.ledger(self.projects[0], [row("I-003", "装个图像 skill", "试过一次", category="能力")])
        text = H.out(self.run_evo(str(self.projects[0])))
        self.assertIn("ROUTER.md（推荐能力节）", text)

    def test_out_writes_a_record_the_reviewer_must_fill(self):
        self.ledger(self.projects[0], [row("I-001", "认领原子化", "见 tests/test_claim.py")])
        rec = self.tmp / "record.json"
        r = self.run_evo(str(self.projects[0]), "--out", str(rec))
        self.assertEqual(r.returncode, 0, msg=H.out(r))
        data = json.loads(rec.read_text(encoding="utf-8"))
        self.assertEqual(len(data["条目"]), 1)
        e = data["条目"][0]
        self.assertEqual(e["结论"], None)
        self.assertEqual(e["主观评估"], {"有效性": None, "必要性": None, "理由": ""})
        self.assertEqual(set(e["三证"]), {"diff 位置", "来源项目", "测试/CI 运行标识", "用户批准"})
        self.assertTrue(data["审核标准"], "记录里要带上五条标准，审核人不必另开文档")

    def fill(self, rec, verdict="晋升", drop=None):
        data = json.loads(rec.read_text(encoding="utf-8"))
        for e in data["条目"]:
            e["结论"] = verdict
            e["主观评估"] = {"有效性": "试点两天没再撞车", "必要性": "现有条款覆盖不了",
                             "理由": "跨 harness 都需要同一条路"}
            e["三证"] = {"diff 位置": "wsc.py:cmd_claim", "来源项目": "p1",
                         "测试/CI 运行标识": "trial-20260928-151642", "用户批准": "2026-09-28 同意"}
            if drop:
                e[drop[0]][drop[1]] = ""
        rec.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")

    def test_verify_record_blocks_unfilled_then_passes_complete(self):
        self.ledger(self.projects[0], [row("I-001", "认领原子化", "见 tests/test_claim.py")])
        rec = self.tmp / "record.json"
        self.run_evo(str(self.projects[0]), "--out", str(rec))
        bad = self.run_evo("--verify-record", str(rec))
        self.assertNotEqual(bad.returncode, 0)
        self.assertIn("结论 'None' 不在", H.out(bad))
        self.fill(rec)
        good = self.run_evo("--verify-record", str(rec))
        self.assertEqual(good.returncode, 0, msg=H.out(good))
        self.assertIn("全部合格", H.out(good))

    def test_missing_proof_blocks_promotion(self):
        """三证 + 用户批准缺任何一项都不许写回：这是 I-001 那次"自开先例"的机器防线。"""
        self.ledger(self.projects[0], [row("I-001", "认领原子化", "见 tests/test_claim.py")])
        rec = self.tmp / "record.json"
        self.run_evo(str(self.projects[0]), "--out", str(rec))
        for drop in (("三证", "测试/CI 运行标识"), ("三证", "用户批准"),
                     ("主观评估", "必要性")):
            self.fill(rec, drop=drop)
            r = self.run_evo("--verify-record", str(rec))
            self.assertNotEqual(r.returncode, 0, msg=f"{drop} 空着也该过？")
            self.assertIn(drop[1], H.out(r))

    def test_reject_and_pilot_verdicts_need_no_proofs(self):
        self.ledger(self.projects[0], [row("I-001", "改个措辞", "一次返工")])
        rec = self.tmp / "record.json"
        self.run_evo(str(self.projects[0]), "--out", str(rec))
        self.fill(rec, verdict="驳回")
        r = self.run_evo("--verify-record", str(rec))
        self.assertEqual(r.returncode, 0, msg=H.out(r))

    @unittest.skipIf(IN_TRIAL, "试装副本里的自测不再递归试装")
    def test_apply_check_refuses_a_patch_that_does_not_fit(self):
        p = self.tmp / "bad.diff"
        p.write_text("--- a/nope.md\n+++ b/nope.md\n@@ -1,2 +1,2 @@\n-没有这行\n+有的行\n",
                     encoding="utf-8", newline="\n")
        r = self.run_evo("--apply-check", str(p), timeout=1500)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("补丁套不上", H.out(r))

    @unittest.skipIf(IN_TRIAL, "试装副本里的自测不再递归试装")
    def test_apply_check_passes_a_doc_only_patch(self):
        tmpdir, patch = make_patch(H.REPO, "docs/EVOLUTION-PROCESS.md",
                                   "## 状态机", "## 状态机（试装补丁用的标记）")
        self.addCleanup(H.rmtree, tmpdir)
        r = self.run_evo("--apply-check", str(patch), timeout=1500)
        self.assertEqual(r.returncode, 0, msg=H.out(r)[-800:])
        out = H.out(r)
        self.assertIn("全套自测：rc=0", out)
        self.assertIn("三证填法", out)
        self.assertIn("run=trial-", out)
        self.assertNotIn("（试装补丁用的标记）",
                         (H.REPO / "docs" / "EVOLUTION-PROCESS.md").read_text(encoding="utf-8"),
                         "试装只发生在临时副本，本体一个字都不能动")

    @unittest.skipIf(IN_TRIAL, "试装副本里的自测不再递归试装")
    def test_apply_check_refuses_a_patch_that_breaks_tests(self):
        tmpdir, patch = make_patch(H.REPO, "tests/test_stats.py",
                                   'self.assertIn("[1] 规则遵循率", text)',
                                   'self.assertIn("这句绝不可能出现", text)')
        self.addCleanup(H.rmtree, tmpdir)
        r = self.run_evo("--apply-check", str(patch), timeout=1500)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("补丁让自测变红，不得写回本体", H.out(r))


if __name__ == "__main__":
    unittest.main()
