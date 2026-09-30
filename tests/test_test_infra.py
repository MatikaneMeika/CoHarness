"""测试基础设施自身的钉子：临时目录清理、git 后台维护。

这些不是产品行为，而是"CI 会不会因为环境抖动而红"——红过一次就得钉住，
否则每次都要花十几分钟从 annotation 里反推真因（2026-09-30 就是这么查的）。
"""
import os
import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import helpers as H


class CleanupRace(unittest.TestCase):
    """macOS 腿真红过：teardown 撞上 git 后台维护，`maintenance.lock` 在 chmod 前被删掉，
    rmtree 的重试回调抛 FileNotFoundError，整条腿染红（`Ran 296 tests ... errors=2`）。"""

    def test_vanished_target_is_not_an_error(self):
        """重试回调遇到"目标已经没了"必须当成功：那正是我们想要的结果。"""
        missing = Path(H.tmp_dir()) / "gone-already"
        H._force_remove(os.unlink, str(missing), FileNotFoundError())

    def test_readonly_file_is_still_removed(self):
        """正向：只读文件（Windows 上 git 对象就是这样）仍要被删掉——容忍竞态不等于放弃删除。"""
        d = H.tmp_dir()
        self.addCleanup(shutil.rmtree, str(d), True)
        ro = d / "readonly.txt"
        ro.write_text("x", encoding="utf-8")
        os.chmod(ro, 0o444)
        H.rmtree(d)
        self.assertFalse(d.exists(), "只读文件/目录没被删掉")

    def test_test_repos_do_not_run_git_maintenance(self):
        """测试仓库一律关掉后台维护：临时仓库活几分钟就删，维护进程只会在 teardown 时抢锁。"""
        proj = H.git_repo(H.tmp_dir() / "proj")
        self.addCleanup(H.rmtree, proj.parent)
        self.assertEqual(H.git(proj, "config", "gc.auto").stdout.strip(), "0")
        self.assertEqual(H.git(proj, "config", "maintenance.auto").stdout.strip(), "false")


if __name__ == "__main__":
    unittest.main()
