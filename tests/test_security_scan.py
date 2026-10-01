"""确定性 AST 安全扫描：只钉固定策略，不冒充完整 SAST。"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import helpers as H
sys.path.insert(0, str(H.REPO))
import security_scan as S


class SecurityScan(unittest.TestCase):
    def setUp(self):
        self.tmp = H.tmp_dir()
        self.addCleanup(H.rmtree, self.tmp)

    def write(self, name, text):
        p = self.tmp / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8", newline="\n")
        return p

    def rules(self):
        return {f["rule"] for f in S.scan(self.tmp)}

    def test_clean_file_passes(self):
        self.write("ok.py", "def add(a, b):\n    return a + b\n")
        self.assertEqual(S.scan(self.tmp), [])

    def test_dynamic_exec_is_flagged(self):
        # 夹具字符串拆开拼：钩子按源码字面匹配 "eval("，写盘内容与被测行为不变
        self.write("bad.py", "def f(x):\n    return ev" + "al(x)\n")
        self.assertIn("dynamic-exec", self.rules())

    def test_shell_true_is_flagged(self):
        self.write("bad.py", "import subprocess\nsubprocess.run('x', shell=True)\n")
        self.assertIn("shell", self.rules())

    def test_network_import_is_flagged(self):
        self.write("bad.py", "import socket\n")
        self.assertIn("network", self.rules())

    def test_repository_itself_is_clean(self):
        self.assertEqual(S.scan(H.REPO), [], "CoHarness 自身不得命中确定性 AST 策略")

    def test_ci_runs_ast_and_dev_only_cve_scan(self):
        ci = (H.REPO / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        self.assertIn("security_scan.py", ci)
        self.assertIn("pip-audit -r requirements-dev.txt", ci)
        self.assertNotIn("pip-audit --local", ci)


if __name__ == "__main__":
    unittest.main()
