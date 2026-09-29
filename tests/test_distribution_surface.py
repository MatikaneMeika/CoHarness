"""分发面与开发面脚本的承诺必须都能被机器复查（ADR-10：依赖面按分发面分层）。

`wsc.py`/`check.py` 是分发面：随骨架进每个下游项目、可 curl 单文件下载，所以纯标准库、
零网络、单文件读得动。`evolve.py` 是开发面：只审骨架本体，允许 import 同目录的 wsc 复用
读表与调用形状，但同样不许引第三方、不许出网。
这些断言针对 SECURITY.md 与 README.md 里的说法——写了就要有红了会报警的测试兜着。
"""
import ast
import collections
import re
import subprocess
import sys
import unittest
from pathlib import Path

import helpers as H

SHIPPED = (H.WSC, H.CHECK_SRC)                  # 分发面：随骨架进每个下游项目，可 curl 单文件
DEV = (H.REPO / "evolve.py",)                    # 开发面：审骨架本体
MAINT = (H.REPO / "maintain.py",)                # 维护面：管已实例化项目的指纹/迁移/体检
VIEW = (H.REPO / "board.py", H.REPO / "panel.py")  # 展示面：只读看板（装配/渲染与终端分开）
ALL = SHIPPED + DEV + MAINT + VIEW
FIRST_PARTY = {"wsc", "maintain", "board"}         # 同目录自带模块（panel 复用 board，evolve 读指纹 import maintain）
# 行数上限：只防"无人再读得动"，不防正常生长；超了先删冗余或按面分层拆出去，别抬数字。
# wsc.py 比 check.py 宽是因为 README 承诺"curl 一个文件就能装机"，下游命令不许散到多文件；
# check.py 才是复制进每个项目的那一份，最严。新增能力一律进 maintain.py / evolve.py。
# 2026-09-28 定字：wsc.py 到 1250 为止，之后**新命令一律进 maintain.py**（决策记录见
# docs/EVOLUTION-PLAN.md 的 ADR-10 附注）。这条上限是最后一次为 wsc.py 上调。
LINE_BUDGET = {H.WSC: 1250, H.CHECK_SRC: 650, H.REPO / "evolve.py": 400,
               H.REPO / "maintain.py": 700, H.REPO / "board.py": 580, H.REPO / "panel.py": 220}
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


def discovered_module_names():
    """与 `python -m unittest discover -s tests` 同一个发现入口，只数不跑。"""
    suite = unittest.TestLoader().discover(str(H.REPO / "tests"),
                                           top_level_dir=str(H.REPO / "tests"))

    def walk(s):
        for x in s:
            if isinstance(x, unittest.TestSuite):
                yield from walk(x)
            else:
                yield x

    return [str(t.id()).split(".")[0] for t in walk(suite)]


class DistributionSurface(unittest.TestCase):
    def test_distribution_face_imports_only_stdlib(self):
        for p in SHIPPED:
            non_std = sorted(m for m in imports_of(p)
                             if m.split(".")[0] not in sys.stdlib_module_names)
            self.assertEqual(non_std, [], f"分发面 {p.name} 引了非标准库依赖: {non_std}")

    def test_dev_maint_and_view_faces_may_only_add_first_party_modules(self):
        for p in DEV + MAINT + VIEW:
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
            self.assertNotIn("exec", calls, f"{p.name} 用了 exec")

    def test_panel_loads_check_py_without_dynamic_execution(self):
        """展示面复用**项目自己的** scripts/check.py，但不许动态执行。

        历史口径是"全链唯一的 exec 口子"，安全门按 CWE-95 把它判成高危、拦截提交；
        改用 importlib 按固定路径装载，装载期间临时关掉字节码写入——别人的项目里
        照样不留 __pycache__，"只读"承诺不变，动态执行口子归零。
        这条钉子钉两件事：board.py 无任何 exec/eval/compile；load_check 装载的
        路径必须是 <项目>/scripts/check.py，不是任意路径。
        """
        src = (H.REPO / "board.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        calls = [n.func.id for n in ast.walk(tree)
                 if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)]
        for bad in ("exec", "eval", "compile"):
            self.assertNotIn(bad, calls, f"board.py 出现 {bad}()——动态执行必须为零")
        fn = next(n for n in tree.body
                  if isinstance(n, ast.FunctionDef) and n.name == "load_check")
        seg = ast.get_source_segment(src, fn) or ""
        self.assertIn('Path(project) / "scripts" / "check.py"', seg,
                      "装载的必须是项目自己的执法脚本，不是任意路径")

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
        self.assertNotIn("import board", src, "看板是第四面，不接进分发面的单文件")
        self.assertNotIn("panel", src, "同上")
        self.assertIn("evolve.py", (H.REPO / "docs" / "EVOLUTION-PROCESS.md")
                      .read_text(encoding="utf-8"),
                      "管线文档要写清审核命令是 evolve.py，别让人去喊 wsc evolve")

    def test_docs_do_not_hardcode_line_counts(self):
        """文档里不写死行数：写过"五百行内"而实际 544 行，就是这类承诺腐烂的样子。"""
        for rel in ("SECURITY.md", "README.md"):
            text = (H.REPO / rel).read_text(encoding="utf-8")
            hits = re.findall(r"[（(][^）)]{0,12}\d{3,}\s*行[^）)]*[）)]", text)
            self.assertEqual(hits, [], f"{rel} 写死了行数 {hits}，改由行数上限测试钉住")

    def test_no_control_characters_in_tracked_text(self):
        """文本里不许留 C0 控制字符：本轮就出过一次——生成 Python 源码的 shell 里写 `D:\\a\\_temp`，
        `\\a` 被当成响铃符写进 CHANGELOG，人眼看是正常文字，字节里藏了 0x07。
        这类字符只能由机器发现，不能指望读。"""
        banned = {chr(c) for c in range(0x20) if chr(c) not in "\t\n\r"} | {chr(0x7f)}
        out = subprocess.run(["git", "ls-files"], cwd=str(H.REPO), capture_output=True,
                             text=True, encoding="utf-8", errors="replace").stdout
        bad = []
        for rel in out.splitlines():
            if not rel.endswith((".md", ".py", ".yml", ".toml", ".json", "pre-commit")):
                continue
            f = H.REPO / rel
            if not f.is_file():
                continue
            text = f.read_text(encoding="utf-8", errors="replace")
            hits = sorted({hex(ord(c)) for c in text if c in banned})
            if hits:
                bad.append((rel, hits))
        self.assertEqual(bad, [], f"这些文件里藏了控制字符：{bad}")

    def test_markdown_table_rows_are_not_split(self):
        """表格一行必须一行写完：Edit 工具往一行单元格里插了换行，渲染时那一行直接散架，
        而读源码的人（包括我）看不出问题——本轮真实踩到过一次。只由机器发现。"""
        out = subprocess.run(["git", "-c", "core.quotepath=false", "ls-files", "-z", "*.md"],
                             cwd=str(H.REPO), capture_output=True).stdout.decode("utf-8")
        bad = []
        for rel in [p for p in out.split("\0") if p]:
            f = H.REPO / rel
            if not f.is_file():
                continue
            in_row = False
            for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
                s = line.strip()
                if s.startswith("|"):
                    in_row = True
                    if not s.endswith("|"):
                        bad.append(f"{rel}:{n} 行首是 | 行尾不是（这行被换行拆断了）")
                elif in_row and s.endswith("|") and not s.startswith("|"):
                    bad.append(f"{rel}:{n} 上一行是表格行，这行不以 | 开头却以 | 结尾（续行）")
                    in_row = False
                else:
                    in_row = False
        self.assertEqual(bad, [], "Markdown 表格行被拆成多行：\n" + "\n".join(bad))

    def test_docs_declare_the_real_self_test_count(self):
        """写死条数比写死行数值得留（"零依赖 N 条"是对用户的承诺），但必须跟实跑对齐。

        本轮实跑发现四处已经腐烂：`test_packaging.py 6 条`（真 7）、`test_protocol_smoke.py 8 条`
        （真 9）、`test_evolve.py 12 条`（真 13）、发布草稿里的"199→206 条"（那是同一轮的两个
        中间快照，不是 v1.0→v1.1 的对照）。手写记不住就交给机器记。
        """
        modules = discovered_module_names()
        total = len(modules)
        per_module = collections.Counter(modules)
        docs = ("README.md", "README.en.md", "docs/ACCEPTANCE-v1.1.md", "CONTRIBUTING.md",
                "docs/RELEASE-v1.1.0.md", "docs/DEMO-migrate.md")
        for rel in docs:
            text = (H.REPO / rel).read_text(encoding="utf-8")
            for n in re.findall(r"(?<!\d)(\d{3})\s*(?:条|tests)", text):
                self.assertEqual(int(n), total,
                                 f"{rel} 写着 {n} 条自测，实际发现 {total} 条")
            for mod, n in re.findall(r"test_([a-z_]+)\.py`?[^0-9\n]{0,4}(\d{1,3})\s*条", text):
                name = f"test_{mod}"
                self.assertIn(name, per_module, f"{rel} 引用了不存在的测试模块 {name}")
                self.assertEqual(int(n), per_module[name],
                                 f"{rel} 写着 {name} 有 {n} 条，实际 {per_module[name]} 条")

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
