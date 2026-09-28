"""分发面与开发面脚本的承诺必须都能被机器复查（ADR-10：依赖面按分发面分层）。

`wsc.py`/`check.py` 是分发面：随骨架进每个下游项目、可 curl 单文件下载，所以纯标准库、
零网络、单文件读得动。`evolve.py` 是开发面：只审骨架本体，允许 import 同目录的 wsc 复用
读表与调用形状，但同样不许引第三方、不许出网。
这些断言针对 SECURITY.md 与 README.md 里的说法——写了就要有红了会报警的测试兜着。
"""
import ast
import re
import sys
import unittest
from pathlib import Path

import helpers as H

SHIPPED = (H.WSC, H.CHECK_SRC)                  # 分发面：随骨架进每个下游项目，可 curl 单文件
DEV = (H.REPO / "evolve.py",)                    # 开发面：审骨架本体
MAINT = (H.REPO / "maintain.py",)                # 维护面：管已实例化项目的指纹/迁移/体检
ALL = SHIPPED + DEV + MAINT
FIRST_PARTY = {"wsc", "maintain"}                 # 同目录自带模块（evolve 读指纹会 import maintain）
# 行数上限：只防"无人再读得动"，不防正常生长；超了先删冗余或按面分层拆出去，别抬数字。
# wsc.py 比 check.py 宽是因为 README 承诺"curl 一个文件就能装机"，下游命令不许散到多文件；
# check.py 才是复制进每个项目的那一份，最严。新增能力一律进 maintain.py / evolve.py。
# 2026-09-28 定字：wsc.py 到 1250 为止，之后**新命令一律进 maintain.py**（决策记录见
# docs/EVOLUTION-PLAN.md 的 ADR-10 附注）。这条上限是最后一次为 wsc.py 上调。
LINE_BUDGET = {H.WSC: 1250, H.CHECK_SRC: 650, H.REPO / "evolve.py": 400,
               H.REPO / "maintain.py": 700}
NETWORK_TOKENS = ("urllib.request", "http.client", "socket", "ftplib", "smtplib",
                  "poplib", "imaplib", "telnetlib", "requests", "urllib3", "httpx", "aiohttp")


def imports_of(path):
    top = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            top.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            top.add(node.module)
    return top


class DistributionSurface(unittest.TestCase):
    def test_distribution_face_imports_only_stdlib(self):
        for p in SHIPPED:
            non_std = sorted(m for m in imports_of(p)
                             if m.split(".")[0] not in sys.stdlib_module_names)
            self.assertEqual(non_std, [], f"分发面 {p.name} 引了非标准库依赖: {non_std}")

    def test_dev_and_maint_faces_may_only_add_first_party_module(self):
        for p in DEV + MAINT:
            extra = sorted(m for m in imports_of(p)
                           if m.split(".")[0] not in sys.stdlib_module_names and m not in FIRST_PARTY)
            self.assertEqual(extra, [], f"{p.name} 引了第三方依赖: {extra}")

    def test_scripts_make_no_network_call(self):
        for p in ALL:
            src = p.read_text(encoding="utf-8")
            for token in NETWORK_TOKENS:
                self.assertNotIn(token, src, f"{p.name} 出现网络符号 {token}")
            for bad in ("urlopen", "socket.", "Popen(", "os.system"):
                self.assertNotIn(bad, src, f"{p.name} 出现 {bad}")

    def test_scripts_do_not_dynamically_execute(self):
        for p in ALL:
            tree = ast.parse(p.read_text(encoding="utf-8"))
            calls = [n.func.id for n in ast.walk(tree)
                     if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)]
            self.assertNotIn("eval", calls, f"{p.name} 用了 eval")
            if p != H.CHECK_SRC:
                # check.py 本体没有 exec；把它当模块载入只发生在测试侧（helpers.load_check_module）
                self.assertNotIn("exec", calls, f"{p.name} 用了 exec")

    def test_scripts_stay_readable_within_budget(self):
        for p in ALL:
            lines = len(p.read_text(encoding="utf-8").splitlines())
            self.assertLessEqual(lines, LINE_BUDGET[p],
                                 f"{p.name} 已 {lines} 行，超过 {LINE_BUDGET[p]} 行上限："
                                 f"先删冗余或按分发面分层拆出去，别抬上限")

    def test_evolve_is_not_wired_into_the_distribution_face(self):
        """晋升审核只活在库侧：curl 到的单文件里不该带着 evolve 的接线。"""
        src = H.WSC.read_text(encoding="utf-8")
        self.assertNotIn("cmd_evolve", src)
        self.assertNotIn('"evolve"', src)
        self.assertIn("evolve.py", (H.REPO / "docs" / "EVOLUTION-PROCESS.md")
                      .read_text(encoding="utf-8"),
                      "管线文档要写清审核命令是 evolve.py，别让人去喊 wsc evolve")

    def test_docs_do_not_hardcode_line_counts(self):
        """文档里不写死行数：写过"五百行内"而实际 544 行，就是这类承诺腐烂的样子。"""
        for rel in ("SECURITY.md", "README.md"):
            text = (H.REPO / rel).read_text(encoding="utf-8")
            hits = re.findall(r"[（(][^）)]{0,12}\d{3,}\s*行[^）)]*[）)]", text)
            self.assertEqual(hits, [], f"{rel} 写死了行数 {hits}，改由行数上限测试钉住")

    def test_local_telemetry_is_documented_and_ignorable(self):
        sec = (H.REPO / "SECURITY.md").read_text(encoding="utf-8")
        self.assertIn("telemetry.jsonl", sec)
        self.assertIn("--no-track", sec)
        self.assertNotIn("不遥测任何内容", sec, "本地记账已存在，'不遥测'的说法要改成可核的口径")
        ignore = (H.SKELETON / ".gitignore").read_text(encoding="utf-8")
        self.assertIn(".agent/telemetry.jsonl", ignore,
                      "记账文件不进版本库，否则每次提交都被自己的记录绊住")


if __name__ == "__main__":
    unittest.main()
