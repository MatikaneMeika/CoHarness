"""pre-commit 装机：普通仓库 / linked worktree / 非仓库 / 外层仓库四种目标。

原 install_pre_commit 要求 dst/.git 是目录：worktree 下 .git 是文件（并行协议
规定的默认形态）装不上，非仓库目标静默跳过 —— 而 03/AGENTS.md 写着"wsc init
自动安装"。钩子本体还硬编码 `python`，只有 py/python3 的机器上直接失败。
"""
import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import helpers as H


class HookInstall(unittest.TestCase):
    def setUp(self):
        self.tmp = H.tmp_dir()
        self.addCleanup(H.rmtree, self.tmp)

    def init(self, dst, skeleton="multi"):
        dst.mkdir(parents=True, exist_ok=True)
        return H.wsc("init", skeleton, str(dst))

    def test_plain_repo_gets_hook(self):
        dst = self.tmp / "plain"
        H.git_repo(dst, bootstrap=False)
        res = self.init(dst)
        self.assertEqual(res.returncode, 0, H.out(res))
        self.assertIn("钩子已", H.out(res))
        self.assertTrue((H.hooks_dir(dst) / "pre-commit").exists())

    def test_linked_worktree_gets_shared_hook(self):
        main = self.tmp / "main"
        H.git_repo(main, bootstrap=False)
        wt = self.tmp / "wt-a"
        r = H.git(main, "worktree", "add", "--orphan", "-b", "harness-a", str(wt))
        self.assertEqual(r.returncode, 0, H.out(r))
        self.assertTrue((wt / ".git").is_file(), "worktree 的 .git 是文件，不是目录")

        res = self.init(wt)
        self.assertEqual(res.returncode, 0, H.out(res))
        self.assertIn("钩子已", H.out(res))
        self.assertTrue((H.hooks_dir(main) / "pre-commit").exists(),
                        "钩子要落在主仓库的公共 hooks 目录，worktree 才共享执法")
        self.assertEqual(H.hooks_dir(wt), H.hooks_dir(main))

        (wt / "报告-final.md").write_text("x", encoding="utf-8")
        H.git(wt, "add", "报告-final.md")
        bad = H.git(wt, "commit", "-q", "-m", "worktree 违规提交")
        self.assertNotEqual(bad.returncode, 0, msg=H.out(bad))
        self.assertEqual(H.git(wt, "rev-list", "--count", "--all").stdout.strip(), "0",
                         "被拦的提交不得进历史")

    def test_non_repo_target_says_so(self):
        dst = self.tmp / "loose"
        res = self.init(dst)
        self.assertEqual(res.returncode, 0, H.out(res))
        text = H.out(res)
        self.assertIn("未装钩子", text)
        self.assertIn("git init", text)

    def test_target_inside_an_outer_repo_is_not_touched(self):
        outer = self.tmp / "outer"
        H.git_repo(outer, bootstrap=False)
        dst = outer / "scratch" / "proj"
        res = self.init(dst)
        self.assertEqual(res.returncode, 0, H.out(res))
        self.assertIn("未装钩子", H.out(res))
        self.assertIn("外层", H.out(res))
        self.assertFalse((H.hooks_dir(outer) / "pre-commit").exists(),
                         "不许把项目钩子装进外层仓库")

    def test_clone_then_sync_installs_the_hook(self):
        """钩子不入版本库：clone 出来的项目默认零执法，开工第一步要自愈补上。"""
        src = self.tmp / "src"
        H.git_repo(src, bootstrap=False)
        self.init(src)
        H.git(src, "add", "-A")
        H.git(src, "commit", "-q", "-m", "骨架入库").returncode
        clone = self.tmp / "clone"
        H.git(self.tmp, "clone", "-q", str(src), str(clone))
        self.assertFalse((H.hooks_dir(clone) / "pre-commit").exists(),
                         "前提：git clone 不会带上 .git/hooks 里的钩子")
        res = H.wsc("sync", str(clone))
        self.assertEqual(res.returncode, 0, H.out(res))
        self.assertIn("补装", H.out(res))
        self.assertTrue((H.hooks_dir(clone) / "pre-commit").exists())
        # 违规改动在补装后的 clone 里会被拦
        (clone / "报告-final.md").write_text("x", encoding="utf-8")
        H.git(clone, "add", "报告-final.md")
        bad = H.git(clone, "commit", "-q", "-m", "违规命名")
        self.assertNotEqual(bad.returncode, 0, msg=H.out(bad))
        again = H.wsc("sync", str(clone))
        self.assertNotIn("补装", H.out(again), "已装好时不该重复打印")

    def test_existing_hook_is_not_overwritten(self):
        dst = self.tmp / "kept"
        H.git_repo(dst, bootstrap=False)
        hd = H.hooks_dir(dst)
        hd.mkdir(parents=True, exist_ok=True)
        (hd / "pre-commit").write_text("#!/bin/sh\n# 用户自己的钩子\n", encoding="utf-8")
        res = self.init(dst)
        self.assertIn("已存在", H.out(res))
        self.assertEqual((hd / "pre-commit").read_text(encoding="utf-8"),
                         "#!/bin/sh\n# 用户自己的钩子\n")


@unittest.skipUnless(shutil.which("sh"), "需要 sh 环境跑钩子")
class HookInterpreter(unittest.TestCase):
    def setUp(self):
        self.tmp = H.tmp_dir()
        self.addCleanup(H.rmtree, self.tmp)

    def run_hook(self, env):
        proj = H.make_project(self.tmp)
        hook = proj / "scripts" / "hooks" / "pre-commit"
        import os
        return H.run([shutil.which("sh"), str(hook)], cwd=proj,
                     extra_env=dict(os.environ, **env))

    def test_fails_loudly_without_any_interpreter(self):
        # 只留 sh 所在的系统目录，PATH 里没有任何 python
        empty = self.tmp / "emptybin"
        empty.mkdir()
        res = self.run_hook({"PATH": str(empty)})
        self.assertEqual(res.returncode, 1, msg=H.out(res))
        self.assertIn("找不到可用", H.out(res))

    def test_skips_unusable_python3_stub(self):
        """本机 python3 是 WindowsApps 占位符：command -v 能找到，但一跑就废。"""
        import os
        fake = self.tmp / "fakebin"
        fake.mkdir()
        stub = fake / "python3"
        stub.write_text("#!/bin/sh\nexit 49\n", encoding="utf-8")
        stub.chmod(0o755)
        real_dir = str(Path(sys.executable).parent)
        proj = H.make_project(self.tmp)
        (proj / "报告-final.md").write_text("x", encoding="utf-8")
        hook = proj / "scripts" / "hooks" / "pre-commit"
        res = H.run([shutil.which("sh"), str(hook)], cwd=proj,
                    extra_env=dict(os.environ, PATH=f"{fake}{os.pathsep}{real_dir}"))
        self.assertEqual(res.returncode, 1, msg=H.out(res))
        self.assertIn("[命名规范]", H.out(res), "要跳到真能用的解释器，而不是被占位符糊过去")


if __name__ == "__main__":
    unittest.main()
