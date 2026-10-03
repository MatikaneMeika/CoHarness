"""发布面（计划书 W3 的代码侧）：打包清单、运行期零依赖、单文件模式的真实边界。

三条都曾被文档说过头：
1. `pip install coharness` 之后必须还能 `wsc init`——骨架文件得真的进包
2. README 承诺"只下载 wsc.py 单文件也能装骨架"是不成立的：单文件旁边没有骨架目录，
   所以要么把话说清（现在这条），要么去联网拉骨架（破零网络，ADR-10 已回绝）
"""
import ast
import glob
import re
import subprocess
import sys
import tomllib
import unittest
from pathlib import Path

import helpers as H

PYPROJECT = tomllib.loads((H.REPO / "pyproject.toml").read_text(encoding="utf-8"))
PATTERNS = PYPROJECT["tool"]["setuptools"]["package-data"]["coharness"]


def tracked_shippables():
    out = subprocess.run(["git", "ls-files"], cwd=str(H.REPO), capture_output=True,
                         text=True, encoding="utf-8", errors="replace").stdout
    files = set(out.split())
    # docs/demo/ 与 docs/audits/ 是演示脚本和晋升审核存档，只在 clone 里用，不进 wheel
    dev_only = ("docs/demo/", "docs/audits/")
    keep = {f for f in files if f.startswith(("01-", "02-", "03-", "04-", "skills/", "docs/"))
            and not f.startswith(dev_only)}
    keep |= {"ROUTER.md", "SECURITY.md", "CONTRIBUTING.md", "README.md", "LICENSE"}
    return keep


class Packaging(unittest.TestCase):
    def test_no_runtime_dependencies(self):
        deps = PYPROJECT["project"].get("dependencies", [])
        self.assertEqual(deps, [], f"运行期依赖必须是空的，实际 {deps}")
        self.assertIn("dev", PYPROJECT["project"].get("optional-dependencies", {}),
                      "预言机要作为 dev extra 存在，而不是消失")

    def test_console_scripts_cover_the_five_entries(self):
        scripts = PYPROJECT["project"]["scripts"]
        self.assertEqual(scripts["wsc"], "coharness.wsc:main")
        for name in ("coharness-maintain", "coharness-evolve", "coharness-panel",
                     "coharness-dispatch"):
            self.assertIn(name, scripts)
        for mod in ("wsc", "maintain", "evolve", "panel", "dispatch"):
            tree = ast.parse((H.REPO / f"{mod}.py").read_text(encoding="utf-8"))
            names = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
            self.assertIn("main", names, f"{mod}.py 没有可作为入口的 main()")

    def test_package_data_patterns_cover_every_shipped_file(self):
        """glob 用 unix 语义（`*` 不匹配点开头），与 setuptools 实际收集时一致。"""
        matched = set()
        for pattern in PATTERNS:
            for hit in glob.glob(str(H.REPO / pattern), recursive=True):
                p = Path(hit)
                if p.is_file():
                    matched.add(p.relative_to(H.REPO).as_posix())
        missing = sorted(tracked_shippables() - matched)
        self.assertEqual(missing, [], f"这些文件该进包却没被任何 pattern 命中：{missing[:10]}")

    def test_remote_gate_workflow_is_shipped(self):
        """远端门禁（W19 / RFC-0004）必须进包：`.github` 以点开头，unix glob 的 `*`
        不匹配它，pattern 只能逐条写死；漏一条 pip 装出来的骨架就缺这道门。"""
        pattern = "0*/.github/workflows/*.yml"
        self.assertIn(pattern, PATTERNS, "package-data 缺远端门禁 workflow 的逐条写死项")
        hits = {Path(h).relative_to(H.REPO).as_posix()
                for h in glob.glob(str(H.REPO / pattern), recursive=True)
                if Path(h).is_file()}
        self.assertIn("03-multi-harness-project/.github/workflows/coharness.yml", hits,
                      "pattern 没命中 03 骨架的远端门禁 workflow")
        gate = (H.REPO / "03-multi-harness-project" / ".github" / "workflows" /
                "coharness.yml").read_text(encoding="utf-8")
        self.assertIn("merge_group:", gate, "随包分发的 workflow 缺 merge_group 预置")
        self.assertIn("permissions:\n  contents: read", gate,
                      "随包分发的 workflow 缺最小权限块")

    def test_shipped_skeleton_files_are_the_tracked_ones(self):
        """反向检查：pattern 不该把 tests/、workspace/ 这类开发面文件卷进分发物。"""
        # 库自己的开发面目录不许进分发物；骨架内部的 tests/ 是项目结构的一部分，另算
        should_not = ("tests/", "workspace/", ".github/", "build/", ".venv", "fixtures/")
        matched = set()
        for pattern in PATTERNS:
            for hit in glob.glob(str(H.REPO / pattern), recursive=True):
                p = Path(hit)
                if p.is_file():
                    matched.add(p.relative_to(H.REPO).as_posix())
        offenders = sorted(m for m in matched
                           if not m.startswith(("01-", "02-", "03-", "04-"))
                           and any(m.startswith(s) or s in "/" + m for s in should_not))
        self.assertEqual(offenders, [], f"分发物里混进了开发面文件：{offenders}")

    def test_single_file_mode_says_what_it_cannot_do(self):
        """把 wsc.py 单独拷进空目录：日常命令仍可用，但 init 必须把边界说清而不是报"没有骨架"。"""
        solo = H.tmp_dir()
        self.addCleanup(H.rmtree, solo)
        script = solo / "wsc.py"
        H.shutil.copyfile(H.WSC, script)
        r = H.run([sys.executable, script, "init", "03", str(solo / "proj")])
        self.assertNotEqual(r.returncode, 0)
        out = H.out(r)
        self.assertIn("单文件模式", out)
        self.assertIn("git clone", out)
        self.assertIn("pipx install coharness", out)
        listing = H.run([sys.executable, script, "list"])
        self.assertEqual(listing.returncode, 0, msg=H.out(listing))
        self.assertIn("可用骨架: 无", H.out(listing))

    def test_historical_release_file_counts_are_preserved(self):
        """v1.1.0 的发布记录是历史，不许被后续骨架文件数改写；init 仍真跑一次防命令腐烂。"""
        work = H.tmp_dir()
        self.addCleanup(H.rmtree, work)
        proj = work / "proj"
        r = H.run([sys.executable, H.WSC, "init", "03", str(proj)],
                  extra_env={"COHARNESS_HOME": str(work / "home")})
        self.assertEqual(r.returncode, 0, msg=H.out(r))
        self.assertGreater(sum(1 for p in proj.rglob("*") if p.is_file()), 0)
        # v1.1.0 的验收与发布文档是历史记录，不许被后续骨架文件数改写。
        for rel in ("docs/ACCEPTANCE-v1.1.md", "docs/RELEASE-v1.1.0.md"):
            text = (H.REPO / rel).read_text(encoding="utf-8")
            self.assertIn("28", text, f"{rel} 的历史复制文件数记录被改写")

    def test_panel_quick_entry_is_a_console_script_and_is_documented(self):
        """面板是五个入口里唯一天天敲的那个：入口要有能敲的名字，文档也得印出来。

        `pipx install coharness` 之后手上没有 `panel.py` 这个路径可敲，README 却只给了
        `python panel.py ...`（那只在 clone 里成立）。短入口与文档口径由同一条钉子对齐，
        不许一个改了另一个不跟。
        """
        scripts = PYPROJECT["project"]["scripts"]
        self.assertEqual(scripts["coh-panel"], "coharness.panel:main",
                         "展示面缺可敲的短入口")
        self.assertEqual(scripts["coharness-panel"], "coharness.panel:main",
                         "短入口是不加的别名，五入口口径的名字不许动")
        for rel in ("README.md", "README.en.md"):
            text = (H.REPO / rel).read_text(encoding="utf-8")
            self.assertIn("coh-panel", text, f"{rel} 装了机也找不到短入口")
            for block in re.findall(r"```bash\n(.*?)```", text, re.S):
                if "panel" not in block:
                    continue
                for line in block.splitlines():
                    tok = line.split("#")[0].split()
                    if not tok:
                        continue
                    if tok[0] == "python":
                        self.assertTrue((H.REPO / tok[1]).is_file(),
                                        f"{rel} 印了不存在的文件：{tok[1]}")
                    else:
                        self.assertIn(tok[0], scripts,
                                      f"{rel} 印了装不出来的命令：{tok[0]}")

    def test_version_and_license_are_real(self):
        self.assertRegex(PYPROJECT["project"]["version"], r"^\d+\.\d+\.\d+$")
        self.assertTrue((H.REPO / PYPROJECT["project"]["license"]["file"]).exists())
        self.assertTrue((H.REPO / "README.en.md").exists(),
                        "README 里有双语互链就要真有英文版")
        en = (H.REPO / "README.en.md").read_text(encoding="utf-8")
        self.assertIn("README.md", en, "英文版要链回中文原版")
        zh = (H.REPO / "README.md").read_text(encoding="utf-8")
        self.assertIn("README.en.md", zh)


if __name__ == "__main__":
    unittest.main()
