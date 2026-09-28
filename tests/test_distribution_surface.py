"""分发面的承诺必须能被机器复查（ADR-10：check.py/wsc.py 随骨架走，纯标准库、可读、不出网）。

这些断言针对的是 SECURITY.md 与 README.md 里的说法，不是代码风格：
文档写了"纯标准库""没有网络请求""行数上限"，就得有一条红了会报警的测试兜着——
本轮优化的主题正是"README 的承诺先变成事实"。
"""
import ast
import re
import sys
import unittest
from pathlib import Path

import helpers as H

SHIPPED = (H.WSC, H.CHECK_SRC)
# 行数上限：只防"无人再读得动"，不防正常生长；超了先删冗余而不是抬数字
LINE_BUDGET = {H.WSC: 900, H.CHECK_SRC: 650}
NETWORK_TOKENS = ("urllib.request", "http.client", "socket", "ftplib", "smtplib",
                  "poplib", "imaplib", "telnetlib", "requests", "urllib3", "httpx", "aiohttp")


def imports_of(path):
    top, attr_chain = set(), []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            top.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            top.add(node.module)
        elif isinstance(node, ast.Attribute):
            attr_chain.append(node)
    return top, attr_chain


class DistributionSurface(unittest.TestCase):
    def test_shipped_scripts_import_only_stdlib(self):
        for p in SHIPPED:
            top, _ = imports_of(p)
            non_std = sorted(m for m in top if m.split(".")[0] not in sys.stdlib_module_names)
            self.assertEqual(non_std, [], f"{p.name} 引了非标准库依赖: {non_std}")

    def test_shipped_scripts_make_no_network_call(self):
        for p in SHIPPED:
            src = p.read_text(encoding="utf-8")
            for token in NETWORK_TOKENS:
                self.assertNotIn(token, src, f"{p.name} 出现网络符号 {token}")
            for bad in ("urlopen", "socket.", "Popen(", "os.system"):
                self.assertNotIn(bad, src, f"{p.name} 出现 {bad}")

    def test_shipped_scripts_do_not_dynamically_execute(self):
        for p in SHIPPED:
            tree = ast.parse(p.read_text(encoding="utf-8"))
            calls = [n.func.id for n in ast.walk(tree)
                    if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)]
            self.assertNotIn("eval", calls, f"{p.name} 用了 eval")
            # check.py 只被测试用 exec 载入（helpers.load_check_module），本体不许有
            if p == H.WSC:
                self.assertNotIn("exec", calls, f"{p.name} 用了 exec")

    def test_shipped_scripts_stay_readable_within_budget(self):
        for p in SHIPPED:
            lines = len(p.read_text(encoding="utf-8").splitlines())
            self.assertLessEqual(lines, LINE_BUDGET[p],
                                 f"{p.name} 已 {lines} 行，超过 {LINE_BUDGET[p]} 行上限："
                                 f"先删冗余或拆出非分发物，别抬上限")

    def test_docs_do_not_hardcode_line_counts(self):
        """文档里不写死行数：写过"五百行内"而实际 544 行，就是这类承诺腐烂的样子。"""
        for rel in ("SECURITY.md", "README.md"):
            text = (H.REPO / rel).read_text(encoding="utf-8")
            hits = re.findall(r"[（(][^）)]{0,12}\d{3,}\s*行[^）)]*[）)]", text)
            self.assertEqual(hits, [], f"{rel} 写死了行数 {hits}，改由 test_..._within_budget 钉住")

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
