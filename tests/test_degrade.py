"""依赖降级规格（计划书 W11）：doctor 说得清的降级路径，骨架文档里必须同样写着。

这一节防的是两套口径：`wsc.py` 里的 DEGRADE 表和骨架 AGENTS.md 的「降级行为」节各说各话——
harness 读项目内文档，维护者读工具输出，两边不一致就等于没人知道缺依赖时该怎么办。
"""
import importlib.util
import sys
import unittest
from pathlib import Path

import helpers as H

SKELETONS = ("01-solo-code", "02-study-office", "03-multi-harness-project",
             "04-doc-production")
# 每套骨架声明"需要/可选"的依赖；DEGRADE 里多出来的项不许在文档里失踪
NEEDS = {
    "01-solo-code": [],
    "02-study-office": ["backlog"],
    "03-multi-harness-project": ["backlog", "specify", "worktrunk", "node"],
    "04-doc-production": [],
}


def load_degrade():
    # 按固定路径装载 wsc 模块读数据表；装载期间关字节码写入，仓库根不留 __pycache__，
    # 也不用 exec/compile 切源码（安全门按 CWE-95 判红）。
    spec = importlib.util.spec_from_file_location("coh_wsc_under_test", H.WSC)
    mod = importlib.util.module_from_spec(spec)
    prev = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.dont_write_bytecode = prev
    return mod.DEGRADE


class DegradeSpec(unittest.TestCase):
    def setUp(self):
        self.degrade = load_degrade()
        self.tmp = H.tmp_dir()
        self.addCleanup(H.rmtree, self.tmp)

    def test_every_degrade_entry_has_the_three_fields(self):
        for key, spec in self.degrade.items():
            self.assertEqual(set(spec), {"丢了什么", "降级行为", "执法变化", "probe"},
                             f"{key} 的降级规格字段不齐")
            for label in ("丢了什么", "降级行为", "执法变化"):
                self.assertTrue(str(spec[label]).strip(), f"{key}.{label} 是空的")

    def test_skeleton_docs_cover_their_declared_dependencies(self):
        for sk, needs in NEEDS.items():
            text = (H.REPO / sk / "AGENTS.md").read_text(encoding="utf-8")
            self.assertIn("## 降级行为", text, f"{sk} 的 AGENTS.md 没有降级行为节")
            for dep in needs:
                self.assertIn(dep, text, f"{sk} 声明需要 {dep}，却没在降级节里写它没装时怎么办")

    def test_degrade_table_and_docs_agree_on_tool_names(self):
        for sk in SKELETONS:
            text = (H.REPO / sk / "AGENTS.md").read_text(encoding="utf-8")
            section = text.split("## 降级行为", 1)[1].split("\n## ", 1)[0]
            for dep in NEEDS[sk]:
                self.assertIn(dep, section, f"{sk} 的降级节没覆盖 {dep}")
            has_law = (H.REPO / sk / "scripts" / "check.py").exists()
            if has_law:
                self.assertIn("TODO.md", section,
                              f"{sk} 带卡片层执法，降级节就该写明 --minimal 的 TODO.md 回落路径")
            else:
                self.assertNotIn("TODO.md", section,
                                 f"{sk} 没有 scripts/check.py，谈不上卡片执法，"
                                 f"不该冒出别档的回落产物")

    def test_doctor_explain_prints_the_fallback(self):
        r = H.wsc("doctor", "--explain", "backlog,specify")
        self.assertEqual(r.returncode, 0, msg=H.out(r))
        out = H.out(r)
        self.assertIn("backlog 没装时:", out)
        self.assertIn("丢了什么", out)
        self.assertIn("TODO.md", out)
        self.assertIn("specify 没装时:", out)

    def test_doctor_explain_unknown_tool_is_loud(self):
        out = H.out(H.wsc("doctor", "--explain", "docker"))
        self.assertIn("没有登记过 'docker'", out)
        self.assertIn("backlog", out, "报错要把可选项列出来")

    def test_simulate_missing_checks_the_fallback_actually_exists(self):
        full = H.make_project(self.tmp)
        out = H.out(H.wsc("doctor", "--simulate-missing", "backlog", str(full)))
        self.assertIn("[可用]", out)
        self.assertIn("backlog/tasks", out)

    def test_simulate_missing_in_minimal_project_finds_todo(self):
        dst = self.tmp / "min"
        r = H.wsc("init", "03", str(dst), "--minimal")
        self.assertEqual(r.returncode, 0, msg=H.out(r))
        out = H.out(H.wsc("doctor", "--simulate-missing", "backlog", str(dst)))
        self.assertIn("[可用]", out)
        self.assertIn("TODO.md", out)

    def test_simulate_missing_reports_unavailable_honestly(self):
        bare = self.tmp / "bare"
        (bare / ".agent").mkdir(parents=True)
        out = H.out(H.wsc("doctor", "--simulate-missing", "backlog", str(bare)))
        self.assertIn("[不可用]", out)
        self.assertIn("init --minimal", out, "不可用时要把补救动作说清楚")

    def test_doctor_lists_missing_items_with_an_explain_command(self):
        # 用一个只含 git 的 PATH 跑 doctor，缺失项必须自己说出降级入口在哪
        out = H.out(H.run([sys.executable, H.WSC, "doctor"],
                          extra_env={"PATH": str(Path(H.COH_HOME))}))
        self.assertIn("[缺失]", out)
        self.assertIn("doctor --explain", out)


if __name__ == "__main__":
    unittest.main()
