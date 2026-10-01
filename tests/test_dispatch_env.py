"""项目侧 harness 发现脚本：只读探测、配置错误、机器输出。

这个脚本活在 03 骨架项目里，不进库侧 `dispatch.py`。它只回答两件事：
1. `.agent/dispatch.md` 登记的候选 harness 哪些在当前 PATH 上；
2. 角色启动命令表里的工具是否就绪，哪些可用候选还没被任何角色采用。
它不执行候选 CLI、不写文件、不自动改映射。
"""
import contextlib
import importlib.util
import io
import json
import sys
import unittest
from pathlib import Path

import helpers as H

SCRIPT = H.SKELETON / "scripts" / "dispatch_env.py"

TABLE = """# dispatch — 启动命令表
自动派发：关闭（默认）

## 角色 → 启动命令

| 角色 | 启动命令 |
|---|---|
| coder | `codex --cd {worktree}` |
| reviewer | `qodercli --project {worktree}` |
| tester | `missing-cli --run {worktree}` |

## 候选 harness（只读探测）

```json
{"harnesses": [
  {"name": "codex", "probe": "codex"},
  {"name": "qodercli", "probe": "qodercli"},
  {"name": "agy", "probe": "agy"}
]}
```
"""


def load_module():
    spec = importlib.util.spec_from_file_location("coh_dispatch_env_under_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    prev = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.dont_write_bytecode = prev
    return mod


class DispatchEnv(unittest.TestCase):
    def setUp(self):
        self.tmp = H.tmp_dir()
        self.addCleanup(H.rmtree, self.tmp)
        self.proj = self.tmp / "project"
        (self.proj / ".agent").mkdir(parents=True)
        (self.proj / ".agent" / "dispatch.md").write_text(TABLE, encoding="utf-8")
        self.mod = load_module()
        self.available = {"codex": "/fake/codex", "qodercli": "/fake/qodercli",
                          "agy": "/fake/agy"}

    def which(self, tool):
        return self.available.get(tool)

    def test_inspect_reports_available_missing_and_unmapped(self):
        report = self.mod.inspect(self.proj, which=self.which)
        self.assertEqual([x["name"] for x in report["available"]], ["codex", "qodercli", "agy"])
        self.assertEqual([x["name"] for x in report["missing"]], [])
        self.assertEqual(report["unmapped"], ["agy"])
        roles = {x["role"]: x for x in report["roles"]}
        self.assertTrue(roles["coder"]["available"])
        self.assertTrue(roles["reviewer"]["available"])
        self.assertFalse(roles["tester"]["available"])
        self.assertEqual(report["unready_roles"], ["tester"])

    def test_missing_configured_tool_returns_one(self):
        self.available.pop("qodercli")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = self.mod.main([str(self.proj), "--json"], which=self.which)
        self.assertEqual(rc, 1)
        data = json.loads(out.getvalue())
        self.assertEqual(data["missing"], [{"name": "qodercli", "probe": "qodercli"}])
        self.assertEqual(data["unready_roles"], ["reviewer", "tester"])

    def test_missing_candidate_block_is_config_error(self):
        (self.proj / ".agent" / "dispatch.md").write_text(
            "# dispatch\n\n| 角色 | 启动命令 |\n|---|---|\n| coder | `codex` |\n",
            encoding="utf-8")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = self.mod.main([str(self.proj)], which=self.which)
        self.assertEqual(rc, 2)
        self.assertIn("候选 harness", out.getvalue())

    def test_empty_candidate_list_is_explicitly_unconfigured(self):
        empty = TABLE.replace(
            '{"harnesses": [\n  {"name": "codex", "probe": "codex"},\n  {"name": "qodercli", "probe": "qodercli"},\n  {"name": "agy", "probe": "agy"}\n]}',
            '{"harnesses": []}')
        (self.proj / ".agent" / "dispatch.md").write_text(empty, encoding="utf-8")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = self.mod.main([str(self.proj)], which=self.which)
        self.assertEqual(rc, 2)
        self.assertIn("未配置", out.getvalue())

    def test_auto_dispatch_defaults_off_and_requires_explicit_switch(self):
        self.assertFalse(self.mod.inspect(self.proj, which=self.which)["auto_dispatch"])
        (self.proj / ".agent" / "dispatch.md").write_text(
            TABLE.replace("自动派发：关闭（默认）", "自动派发：开启"), encoding="utf-8")
        self.assertTrue(self.mod.inspect(self.proj, which=self.which)["auto_dispatch"])

    def test_missing_auto_dispatch_line_stays_off(self):
        (self.proj / ".agent" / "dispatch.md").write_text(
            TABLE.replace("自动派发：关闭（默认）\n", ""), encoding="utf-8")
        self.assertFalse(self.mod.inspect(self.proj, which=self.which)["auto_dispatch"])

    def test_bad_candidate_json_is_config_error(self):
        bad = TABLE.replace('{"name": "agy", "probe": "agy"}',
                            '{"name": "agy", "probe": "agy"')
        (self.proj / ".agent" / "dispatch.md").write_text(bad, encoding="utf-8")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = self.mod.main([str(self.proj)], which=self.which)
        self.assertEqual(rc, 2)
        self.assertIn("JSON", out.getvalue())

    def test_json_output_is_stable_and_script_is_read_only(self):
        (self.proj / ".agent" / "dispatch.md").write_text(
            TABLE.replace("| tester | `missing-cli --run {worktree}` |\n", ""),
            encoding="utf-8")
        before = sorted(str(p.relative_to(self.proj)) for p in self.proj.rglob("*"))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = self.mod.main([str(self.proj), "--json"], which=self.which)
        self.assertEqual(rc, 0)
        data = json.loads(out.getvalue())
        self.assertEqual(list(data), ["auto_dispatch", "available", "missing", "roles",
                                      "unmapped", "unready_roles"])
        after = sorted(str(p.relative_to(self.proj)) for p in self.proj.rglob("*"))
        self.assertEqual(after, before, "发现脚本只能读，不得写项目")


if __name__ == "__main__":
    unittest.main()
