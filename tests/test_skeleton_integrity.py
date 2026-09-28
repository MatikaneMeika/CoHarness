"""骨架自洽性：目录地图声明的路径必须真存在、引用的文件必须真在、占位符必须能被解释。

`wsc init` 只复制文件、不创建目录，所以骨架里写了 `src/`、`docs/CHANGELOG.md` 却没有
对应文件时，实例化出来的项目地图是假的——harness 第一次照着写就撞空路径。
"""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import helpers as H

SKELETONS = ("01-solo-code", "02-study-office", "03-multi-harness-project",
             "04-doc-production")
PLACEHOLDER_RE = re.compile(r"\{\{([A-Z][A-Z0-9_]*)\}\}")
REF_RE = re.compile(r"`([^`\s]+?\.(?:md|py))`")
FIRST_TOKEN_RE = re.compile(r"^([A-Za-z0-9_.-]+/|[A-Za-z0-9_.-]+\.[A-Za-z0-9]+)")
# 散文里的文件名是样式而非结构承诺：含 <>*{{ 或两个以上连续 x（T-xxx / XX-章节）
PLACEHOLDER_NAME_RE = re.compile(r"(?i)[<>*{]|xx+")
# 这些说法表明路径是"用到时自己建"，不是骨架应当已经提供的东西
CREATE_ON_DEMAND = ("如 `", "首次建立", "新建", "按需", "示例", "骨架库")


class SkeletonIntegrity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = H.tmp_dir()
        cls.addClassCleanup(H.rmtree, cls.tmp)
        cls.projects = {}
        for sk in SKELETONS:
            dst = cls.tmp / sk
            dst.mkdir(parents=True, exist_ok=True)
            res = H.wsc("init", sk.split("-")[0], str(dst))
            assert res.returncode == 0, H.out(res)
            cls.projects[sk] = dst

    def map_paths(self, agents_text):
        m = re.search(r"## 目录地图\s*```(.*?)```", agents_text, re.S)
        if not m:
            return []
        out = []
        for line in m.group(1).splitlines():
            tokens = line.strip().split()
            if tokens and FIRST_TOKEN_RE.match(tokens[0]):
                out.append(tokens[0])
        return out

    def test_declared_paths_exist_after_init(self):
        checked = 0
        for sk, proj in self.projects.items():
            text = (proj / "AGENTS.md").read_text(encoding="utf-8")
            for rel in self.map_paths(text):
                checked += 1
                self.assertTrue((proj / rel).exists(),
                                f"{sk} 目录地图声明 {rel}，实例化后却不存在")
        self.assertGreaterEqual(checked, 15, "目录地图检查项过少说明解析没生效")

    def test_referenced_files_exist(self):
        """只查声明性文本（AGENTS.md 与各目录 README.md）里的路径引用。

        roles/workflows 写的是"活儿"，那里的文件名多半是要产生的输出物
        （`source/00-大纲.md`、`docs/reviews/T-xxx.md`），不是骨架承诺已经存在的结构。
        """
        for sk, proj in self.projects.items():
            for src in sorted(p for p in proj.rglob("*.md")
                              if p.name in ("AGENTS.md", "README.md")):
                for line in src.read_text(encoding="utf-8").splitlines():
                    if any(marker in line for marker in CREATE_ON_DEMAND):
                        continue  # 举例、"用到时自建"、指向骨架库本体的引用，都不算结构承诺
                    for ref in REF_RE.findall(line):
                        # 只查带路径的引用：裸文件名在散文里多半是泛指（"各组件的 README.md"）
                        if "/" not in ref or ref.startswith(("http", "/")):
                            continue
                        if PLACEHOLDER_NAME_RE.search(ref):
                            continue
                        rel = ref[2:] if ref.startswith("./") else ref
                        self.assertTrue((proj / rel).exists(),
                                        f"{sk}/{src.relative_to(proj)} 引用了不存在的 {ref}")

    def test_every_placeholder_is_explained_by_the_card(self):
        """占位符要在 AGENTS.md 的项目卡里出现，否则 init 打出的待填清单没人知道填什么。"""
        for sk, proj in self.projects.items():
            card = (proj / "AGENTS.md").read_text(encoding="utf-8")
            card_names = set(PLACEHOLDER_RE.findall(card))
            self.assertTrue(card_names, f"{sk} 的项目卡没有占位符？")
            for src in sorted(list(proj.rglob("*.md")) + list(proj.rglob("*.py"))):
                names = set(PLACEHOLDER_RE.findall(src.read_text(encoding="utf-8")))
                self.assertFalse(names - card_names,
                                 f"{sk}/{src.relative_to(proj)} 用了卡里没有的占位符 "
                                 f"{sorted(names - card_names)}")

    def test_skeletons_ship_no_run_residue(self):
        for sk in SKELETONS:
            junk = [p for p in (H.REPO / sk).rglob("*")
                    if p.name == "__pycache__" or p.suffix == ".pyc"]
            self.assertEqual(junk, [], f"{sk} 带运行残留: {junk}")


if __name__ == "__main__":
    unittest.main()
