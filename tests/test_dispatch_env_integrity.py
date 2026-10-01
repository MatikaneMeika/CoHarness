"""03 骨架必须带上项目侧 harness 发现脚本，并把它接进角色与协议。

这条钉子单独放一个文件，避免和原有骨架完整性测试的长方法互相干扰。
"""
import unittest

import helpers as H


class DispatchEnvSkeleton(unittest.TestCase):
    def test_dispatch_env_is_shipped_and_referenced(self):
        proj = H.tmp_dir()
        self.addCleanup(H.rmtree, proj)
        r = H.wsc("init", "03", str(proj))
        self.assertEqual(r.returncode, 0, H.out(r))
        script = proj / "scripts" / "dispatch_env.py"
        self.assertTrue(script.is_file(), "03 装机缺 scripts/dispatch_env.py")
        checks = {
            ".agent/dispatch.md": ("候选 harness", "dispatch_env.py", "自动派发"),
            "AGENTS.md": ("dispatch_env.py",),
            ".agent/roles/architect.md": ("候选 harness", "dispatch_env.py"),
            ".agent/roles/integrator.md": ("dispatch_env.py",),
            ".agent/workflows/parallel-protocol.md": ("dispatch_env.py",),
        }
        for rel, needles in checks.items():
            text = (proj / rel).read_text(encoding="utf-8")
            for needle in needles:
                self.assertIn(needle, text, f"{rel} 没写清 {needle}")

    def test_skeleton_dispatch_config_does_not_bake_in_host_harness(self):
        proj = H.tmp_dir()
        self.addCleanup(H.rmtree, proj)
        r = H.wsc("init", "03", str(proj))
        self.assertEqual(r.returncode, 0, H.out(r))
        text = (proj / ".agent" / "dispatch.md").read_text(encoding="utf-8")
        self.assertIn("自动派发：关闭", text)
        self.assertIn('{"harnesses": []}', text)
        for forbidden in ("codex", "qodercli", "agy", "C:\\", "D:\\"):
            self.assertNotIn(forbidden, text, f"骨架写入了本机环境事实：{forbidden}")


if __name__ == "__main__":
    unittest.main()
