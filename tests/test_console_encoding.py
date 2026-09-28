"""控制台编码：中文输出在本机默认 cp936/gbk 环境下不得崩溃、不得乱码。

复现条件（改动前红）：本机 `locale.getpreferredencoding()` = cp936，
wsc.py 的子进程调用用 text=True 而不写 encoding，check.py 输出的是 utf-8。
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import helpers as H


class ConsoleEncoding(unittest.TestCase):
    def setUp(self):
        self.tmp = H.tmp_dir()
        self.addCleanup(H.rmtree, self.tmp)

    def assertReadable(self, res, *fragments):
        text = H.out(res)
        for bad in ("UnicodeDecodeError", "Traceback", "Exception in thread"):
            self.assertNotIn(bad, text, text)
        for frag in fragments:
            self.assertIn(frag, text, text)


class TestWscSubprocess(ConsoleEncoding):
    def test_check_forwards_child_output(self):
        proj = H.make_project(self.tmp)
        (proj / "deliverable-final.md").write_text("x", encoding="utf-8")
        res = H.native_cli("check", str(proj))
        self.assertEqual(res.returncode, 1, H.out(res))
        self.assertReadable(res, "[命名规范]", "deliverable-final.md")

    def test_sync_runs_stale_report(self):
        proj = H.make_project(self.tmp)
        H.write_card(proj, "T-001", allowed=["  - docs/"])
        H.git_repo(proj)
        res = H.native_cli("sync", str(proj))
        self.assertEqual(res.returncode, 0, H.out(res))
        self.assertReadable(res, "[pull]", "[stale]")

    def test_sync_without_git_repo_reports_instead_of_traceback(self):
        res = H.native_cli("sync", str(self.tmp))
        self.assertEqual(res.returncode, 0, H.out(res))
        self.assertReadable(res, "[pull]")


class TestStderrReadable(ConsoleEncoding):
    def test_improve_missing_file_stderr(self):
        res = H.native_cli("improve", str(self.tmp))
        self.assertNotEqual(res.returncode, 0)
        self.assertReadable(res, "未找到")

    def test_init_refuses_non_empty_dir_stderr(self):
        dst = self.tmp / "busy"
        dst.mkdir()
        (dst / "已有规则.md").write_text("x", encoding="utf-8")
        res = H.native_cli("init", "multi", str(dst))
        self.assertNotEqual(res.returncode, 0)
        self.assertReadable(res, "目标目录非空")

    def test_unknown_skeleton_lists_options_stderr(self):
        res = H.native_cli("init", "nope", str(self.tmp / "x"))
        self.assertNotEqual(res.returncode, 0)
        self.assertReadable(res, "未找到骨架")

    def test_check_py_stderr_readable(self):
        proj = H.make_project(self.tmp)
        res = H.run([sys.executable, proj / "scripts" / "check.py"], cwd=proj, native_env=True)
        self.assertReadable(res, "[命名规范]")


if __name__ == "__main__":
    unittest.main()
