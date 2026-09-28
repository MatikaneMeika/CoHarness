"""发布面（计划书 W3 的代码侧）：打包清单、运行期零依赖、单文件模式的真实边界。

三条都曾被文档说过头：
1. `pip install coharness` 之后必须还能 `wsc init`——骨架文件得真的进包
2. README 承诺"只下载 wsc.py 单文件也能装骨架"是不成立的：单文件旁边没有骨架目录，
   所以要么把话说清（现在这条），要么去联网拉骨架（破零网络，ADR-10 已回绝）
"""
import ast
import glob
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
    # docs/demo/ 是演示与取证脚本，只在 clone 里跑，不进 wheel（不进下游项目）
    keep = {f for f in files if f.startswith(("01-", "02-", "03-", "04-", "skills/", "docs/"))
            and not f.startswith("docs/demo/")}
    keep |= {"ROUTER.md", "SECURITY.md", "CONTRIBUTING.md", "README.md", "LICENSE"}
    return keep


class Packaging(unittest.TestCase):
    def test_no_runtime_dependencies(self):
        deps = PYPROJECT["project"].get("dependencies", [])
        self.assertEqual(deps, [], f"运行期依赖必须是空的，实际 {deps}")
        self.assertIn("dev", PYPROJECT["project"].get("optional-dependencies", {}),
                      "预言机要作为 dev extra 存在，而不是消失")

    def test_console_scripts_cover_the_three_faces(self):
        scripts = PYPROJECT["project"]["scripts"]
        self.assertEqual(scripts["wsc"], "coharness.wsc:main")
        for name in ("coharness-maintain", "coharness-evolve"):
            self.assertIn(name, scripts)
        for mod in ("wsc", "maintain", "evolve"):
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
