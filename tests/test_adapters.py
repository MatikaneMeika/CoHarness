"""适配指针的语义桥（计划书 W10）：生成的是各工具原生格式，内容只有指针与工具元数据。

两条承诺都要能测：
1. 格式合法——frontmatter 的键名与位置按各家语法写（来源记在 SOURCES 里，不是凭印象）
2. 不制造第二权威——ADR-5：指针文件只指向 AGENTS.md，正文薄到几行；`adapters --verify` 查的就是这个
"""
import unittest
from pathlib import Path

import helpers as H

SOURCES = {
    "cursor": ".cursor/rules/*.mdc + frontmatter(description/globs/alwaysApply)，"
              "Cursor 官方论坛《A Deep Dive into Cursor Rules (>0.45)》与 .mdc 实例库",
    "windsurf": ".windsurf/rules/*.md + frontmatter(trigger: always_on)；"
                ".windsurfrules 是 Wave 8 之前的单文件写法，仍兼容但非标准",
    "claude": "CLAUDE.md 支持 @路径 导入，导入即指向 AGENTS.md",
    "gemini": "GEMINI.md 同样支持 @ 导入",
    "copilot": ".github/copilot-instructions.md 纯 markdown 全局指令",
}


class Adapters(unittest.TestCase):
    def setUp(self):
        self.tmp = H.tmp_dir()
        self.addCleanup(H.rmtree, self.tmp)

    def init_all(self, name="p"):
        dst = self.tmp / name
        r = H.wsc("init", "03", str(dst), "--adapter", "all")
        self.assertEqual(r.returncode, 0, msg=H.out(r))
        return dst

    def test_all_five_native_locations_are_written(self):
        dst = self.init_all()
        for rel in ("CLAUDE.md", "GEMINI.md", ".cursor/rules/coharness.mdc",
                    ".github/copilot-instructions.md", ".windsurf/rules/coharness.md"):
            self.assertTrue((dst / rel).is_file(), f"缺 {rel}")
        for legacy in (".cursorrules", ".windsurfrules"):
            self.assertFalse((dst / legacy).exists(), f"不该再生成旧格式 {legacy}")

    def test_each_pointer_is_thin_and_points_at_agents(self):
        dst = self.init_all()
        for rel in ("CLAUDE.md", "GEMINI.md", ".cursor/rules/coharness.mdc",
                    ".github/copilot-instructions.md", ".windsurf/rules/coharness.md"):
            lines = [l for l in (dst / rel).read_text(encoding="utf-8").splitlines() if l.strip()]
            self.assertLessEqual(len(lines), 8, f"{rel} 有 {len(lines)} 行，不像指针")
            self.assertIn("AGENTS.md", (dst / rel).read_text(encoding="utf-8"),
                          f"{rel} 没指向权威")

    def test_frontmatter_keys_match_each_tool_grammar(self):
        dst = self.init_all()
        cursor = (dst / ".cursor" / "rules" / "coharness.mdc").read_text(encoding="utf-8")
        self.assertTrue(cursor.startswith("---"), "Cursor .mdc 必须带 frontmatter")
        self.assertIn("alwaysApply: true", cursor)
        windsurf = (dst / ".windsurf" / "rules" / "coharness.md").read_text(encoding="utf-8")
        self.assertIn("trigger: always_on", windsurf)
        claude = (dst / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertIn("@AGENTS.md", claude, "Claude 的导入语法是 @路径")

    def test_verify_passes_on_a_fresh_install(self):
        dst = self.init_all()
        r = H.wsc("adapters", "--verify", str(dst))
        self.assertEqual(r.returncode, 0, msg=H.out(r))
        out = H.out(r)
        self.assertIn("都只含指针与工具元数据", out)
        self.assertEqual(out.count("[已装]"), 5)

    def test_verify_catches_a_second_authority(self):
        dst = self.init_all()
        (dst / "CLAUDE.md").write_text(
            "\n".join(f"{i}. 每次提交必须写测试；禁止直接改主干；不得引入新依赖" for i in range(12)) + "\n",
            encoding="utf-8")
        r = H.wsc("adapters", "--verify", str(dst))
        self.assertNotEqual(r.returncode, 0)
        out = H.out(r)
        self.assertIn("疑似复制了规则本体", out)
        self.assertIn("没指向 AGENTS.md", out)

    def test_verify_catches_missing_frontmatter(self):
        dst = self.init_all()
        (dst / ".cursor" / "rules" / "coharness.mdc").write_text(
            "指向 AGENTS.md 就行\n", encoding="utf-8")
        r = H.wsc("adapters", "--verify", str(dst))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("缺 frontmatter", H.out(r))

    def test_verify_warns_about_legacy_single_files(self):
        dst = self.init_all()
        (dst / ".cursorrules").write_text("旧格式还在\nAGENTS.md\n", encoding="utf-8")
        r = H.wsc("adapters", "--verify", str(dst))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("旧单文件规则还在", H.out(r))

    def test_verify_without_any_pointer_says_so(self):
        dst = H.make_project(self.tmp)
        out = H.out(H.wsc("adapters", "--verify", str(dst)))
        self.assertIn("没有任何适配指针", out)

    def test_list_mode_documents_native_locations_and_legacy(self):
        out = H.out(H.wsc("adapters"))
        self.assertIn(".cursor/rules/coharness.mdc", out)
        self.assertIn(".windsurf/rules/coharness.md", out)
        self.assertIn("原生读 AGENTS.md", out)
        self.assertIn(".cursorrules", out, "旧格式要说明它不再生成")

    def test_unknown_adapter_is_skipped_loudly(self):
        dst = self.tmp / "u"
        r = H.wsc("init", "03", str(dst), "--adapter", "vscode,claude")
        self.assertEqual(r.returncode, 0, msg=H.out(r))
        self.assertIn("未知 adapter: vscode", H.out(r))
        self.assertTrue((dst / "CLAUDE.md").exists(), "已知的名字仍要生成")

    def test_install_adds_pointers_later_and_never_overwrites(self):
        """装机后又来一家工具是常态：adapters --install 补指针，已存在的一律不覆盖。"""
        dst = self.init_all("base")
        (dst / "CLAUDE.md").write_text("我自己写的指针\n", encoding="utf-8", newline="\n")
        r = H.wsc("adapters", str(dst), "--install", "claude,cursor")
        self.assertEqual(r.returncode, 0, msg=H.out(r))
        self.assertIn("CLAUDE.md 已存在", H.out(r), "补指针不许覆盖用户自己写的那份")
        self.assertEqual((dst / "CLAUDE.md").read_text(encoding="utf-8"), "我自己写的指针\n")
        self.assertTrue((dst / ".cursor" / "rules" / "coharness.mdc").exists())


if __name__ == "__main__":
    unittest.main()
