"""钉住 wsc.py 现有行为：init 的三种目标、适配指针、improve、doctor、sync 不崩。"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import helpers as H

# W10 之后：适配指针用各家原生语法，内容仍是"只有指针 + 工具元数据"。
# 格式细节由 tests/test_adapters.py 钉；这里钉的是"init --adapter all 装出哪些位置、且都不是第二权威"。
ADAPTER_FILES = ["CLAUDE.md", "GEMINI.md", ".cursor/rules/coharness.mdc",
                 ".github/copilot-instructions.md", ".windsurf/rules/coharness.md"]
LEGACY_ADAPTER_FILES = [".cursorrules", ".windsurfrules"]


class TempCase(unittest.TestCase):
    def setUp(self):
        self.tmp = H.tmp_dir()
        self.addCleanup(H.rmtree, self.tmp)


class TestInit(TempCase):
    def test_list_shows_four_skeletons(self):
        text = H.out(H.wsc("list"))
        for name in ("01-solo-code", "02-study-office", "03-multi-harness-project",
                     "04-doc-production"):
            self.assertIn(name, text)

    def test_init_empty_dir(self):
        dst = self.tmp / "proj"
        dst.mkdir()
        res = H.wsc("init", "multi", str(dst))
        self.assertEqual(res.returncode, 0, H.out(res))
        self.assertTrue((dst / "AGENTS.md").exists())
        self.assertTrue((dst / "scripts" / "check.py").exists())
        text = H.out(res)
        self.assertIn("待填占位符", text)
        self.assertIn("{{PROJECT_NAME}}", text)
        self.assertIn("依赖安装", text)

    def test_init_refuses_non_empty_dir(self):
        dst = self.tmp / "busy"
        dst.mkdir()
        (dst / "已有规则.md").write_text("x", encoding="utf-8")
        res = H.wsc("init", "multi", str(dst))
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("目标目录非空", H.out(res))

    def test_init_allows_dir_containing_only_git(self):
        # 先 git init 再实例化（EVOLUTION-PLAN.md:114 记录过的修复）
        dst = self.tmp / "repo"
        dst.mkdir()
        H.git_repo(dst, bootstrap=False)
        res = H.wsc("init", "multi", str(dst))
        self.assertEqual(res.returncode, 0, H.out(res))
        self.assertTrue((dst / ".agent").is_dir())

    def test_init_installs_hook_into_existing_repo(self):
        dst = self.tmp / "repo2"
        dst.mkdir()
        H.git_repo(dst, bootstrap=False)
        H.wsc("init", "multi", str(dst))
        self.assertTrue((H.hooks_dir(dst) / "pre-commit").exists(),
                        "wsc init 应把 pre-commit 装进 git 认定的钩子目录")

    def test_adapters_are_native_format_pointers(self):
        """init --adapter all 装出各家原生位置，且每个文件都只是指针。"""
        dst = self.tmp / "adp"
        dst.mkdir()
        res = H.wsc("init", "solo", str(dst), "--adapter", "all")
        self.assertEqual(res.returncode, 0, H.out(res))
        for rel in ADAPTER_FILES:
            p = dst / rel
            self.assertTrue(p.exists(), rel)
            text = p.read_text(encoding="utf-8")
            self.assertIn("AGENTS.md", text, rel)
            self.assertLessEqual(len([l for l in text.splitlines() if l.strip()]), 8,
                                 f"{rel} 正文超过 8 行，不像指针")
        for rel in LEGACY_ADAPTER_FILES:
            self.assertFalse((dst / rel).exists(), f"旧单文件格式 {rel} 不该再生成")
        verify = H.wsc("adapters", "--verify", str(dst))
        self.assertEqual(verify.returncode, 0, H.out(verify))

    def test_unknown_adapter_is_reported_not_fatal(self):
        dst = self.tmp / "adp2"
        dst.mkdir()
        res = H.wsc("init", "solo", str(dst), "--adapter", "kimi")
        self.assertEqual(res.returncode, 0, H.out(res))
        self.assertIn("[跳过] 未知 adapter: kimi", H.out(res))

    def test_existing_adapter_file_is_not_overwritten(self):
        dst = self.tmp / "adp3"
        dst.mkdir()
        (dst / "CLAUDE.md").write_text("我自己的内容\n", encoding="utf-8")
        H.wsc("init", "solo", str(dst), "--adapter", "claude")
        self.assertEqual((dst / "CLAUDE.md").read_text(encoding="utf-8"), "我自己的内容\n")

    def test_unknown_skeleton_lists_options(self):
        res = H.wsc("init", "nope", str(self.tmp / "x"))
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("未找到骨架", H.out(res))


class TestImproveAndDoctor(TempCase):
    def test_improve_on_untouched_template(self):
        proj = H.make_project(self.tmp)
        res = H.wsc("improve", str(proj))
        self.assertEqual(res.returncode, 0, H.out(res))
        self.assertIn("无待处理改进", H.out(res))

    def test_improve_missing_file(self):
        res = H.wsc("improve", str(self.tmp))
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("未找到", H.out(res))

    def test_doctor_reports_missing_without_failing(self):
        res = H.wsc("doctor")
        self.assertEqual(res.returncode, 0, H.out(res))
        self.assertIn("依赖自检", H.out(res))
        for label in ("git", "node", "backlog", "uv", "worktrunk"):
            self.assertIn(label, H.out(res))


class TestCardFieldParsing(TempCase):
    """wsc._card_fields 的解析口径：认领冲突判定（--tasks 与 claim）都吃它的输出。"""

    @staticmethod
    def fields(text):
        import importlib.util
        spec = importlib.util.spec_from_file_location("coh_wsc_fields", H.WSC)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod._card_fields(text)

    def test_empty_value_does_not_swallow_next_line(self):
        """空字段值不许把下一行吞成自己的值：`assignee:` 挨着 `title:` 时，
        `:\\s*` 会越过换行把下一行整个抓进来——空 assignee 就被当成了有认领者，
        认领冲突判定与 claim 都会跟着错。工作区残留修复（2026-09-29）的钉子。"""
        status, who = self.fields("status: doing\nassignee: \ntitle: 顺手一行\n")
        self.assertEqual(status, "doing")
        self.assertEqual(who, [], "空 assignee 不该抓到下一行的 title")

    def test_plain_values_still_parse(self):
        self.assertEqual(self.fields("status: doing\nassignee: [zcode-0926a]"),
                         ("doing", ["zcode-0926a"]))


if __name__ == "__main__":
    unittest.main()
