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

    def test_library_path_is_resolved_at_instantiation(self):
        """`{{COHARNESS_LIB}}` 由 wsc init 代入本机骨架库路径：文档里的命令要能直接复制执行。

        原来写的是 `<骨架库>`/`<CoHarness>` 这种散文占位符，下游 harness 不知道库在哪，
        认领/体检命令只能靠猜——承诺等于没写。
        """
        lib = str(H.REPO)
        for sk, proj in self.projects.items():
            for src in sorted(proj.rglob("*.md")):
                self.assertNotIn("{{COHARNESS_LIB}}", src.read_text(encoding="utf-8"),
                                 f"{sk}/{src.relative_to(proj)} 里的库路径没被代入")
            self.assertNotIn("<骨架库>", (proj / "AGENTS.md").read_text(encoding="utf-8"))
        agents = (self.projects["03-multi-harness-project"] / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn(f"python {lib}/wsc.py claim", agents)
        self.assertIn(f"{lib}/ROUTER.md", agents,
                      "触发约定那行的调度权威没代入库路径：别的 harness 打开项目只能看见一个谜语名字")
        protocol = (self.projects["03-multi-harness-project"] / ".agent" / "workflows" /
                    "parallel-protocol.md").read_text(encoding="utf-8")
        self.assertIn(f"python {lib}/wsc.py claim", protocol)
        raw = (H.SKELETON / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("{{COHARNESS_LIB}}", raw, "骨架本体保留占位符，只实例化时代入")

    def test_trigger_word_is_coharness_everywhere(self):
        """触发词只剩一个：「coharness」。旧词「开工：」/`ws` 太泛——任何 harness 都可能把它
        当普通对话读走。这句话散在四套骨架的 AGENTS.md 头一行、ROUTER、双语 README 与 skill，
        漏改一处就等于留了第二个入口，所以交给机器数而不是靠我记得。
        """
        for rel in ("ROUTER.md", "README.md", "README.en.md", "skills/coharness/SKILL.md"):
            text = (H.REPO / rel).read_text(encoding="utf-8")
            self.assertIn("coharness", text, f"{rel} 没有新触发词")
            self.assertNotIn("「开工：X」", text, f"{rel} 还在把旧词当触发词写")
            self.assertNotIn("`ws X`", text, f"{rel} 还在给旧简写别名")
        for sk in SKELETONS:
            head = (H.REPO / sk / "AGENTS.md").read_text(encoding="utf-8").splitlines()[2]
            self.assertIn("「coharness X」", head, f"{sk} 的触发约定行没换词")
            self.assertIn("{{COHARNESS_LIB}}/ROUTER.md", head,
                          f"{sk} 的调度权威行没带库路径，换一个 harness 打开项目读不到 ROUTER")

    def test_remote_gate_workflow_ships_with_03_only(self):
        """远端门禁（W19 / RFC-0004）：`--no-verify` 与裸克隆两条绕过路径要在远端堵上。

        workflow 只随 03 骨架分发（03 才是多 harness 执法场景）；AGENTS.md 的远端门禁节
        必须声明这个文件；口径与 pre-push 同源（--names --tasks），CI 一律 --no-track。
        """
        rel = ".github/workflows/coharness.yml"
        text = (H.REPO / "03-multi-harness-project" / rel).read_text(encoding="utf-8")
        self.assertIn("scripts/check.py --names --tasks --no-track", text,
                      "workflow 口径必须与执法面同源，且 runner 上不写遥测")
        self.assertIn("fetch-depth: 0", text, "W20 的 --against 需要完整历史")
        self.assertIn("--against \"$COHARNESS_AGAINST\"", text,
                      "远端门禁没有把 CI 变更集交给 --against")
        self.assertIn("::notice::", text, "基线不可用时必须可见降级，不许静默")
        self.assertIn("git merge-base", text, "force-push 旧基线不可达时也要走可见降级")
        self.assertIn("merge_group:", text, "required check + merge queue 场景必须有 merge_group 触发器")
        self.assertIn("types: [checks_requested]", text, "merge_group 触发器类型不对")
        self.assertIn("permissions:\n  contents: read", text, "workflow 缺最小权限块")
        self.assertIn("github.event.merge_group.base_sha", text,
                      "merge_group 事件没有自己的基线来源")
        self.assertIn("actions/checkout@v4  # v4.", text, "checkout 版本注释半钉缺失")
        self.assertIn("actions/setup-python@v5  # v5.", text,
                      "setup-python 版本注释半钉缺失")
        for sk in SKELETONS:
            present = (H.REPO / sk / rel).exists()
            self.assertEqual(present, sk == "03-multi-harness-project",
                             f"{sk} 携带远端门禁 workflow 的状态不对（只许 03 带）")
        agents = (H.REPO / "03-multi-harness-project" / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("远端门禁", agents, "03 骨架 AGENTS.md 缺「远端门禁」小节")
        self.assertIn(f"`{rel}`", agents, "远端门禁小节没有声明 workflow 文件路径")

    def test_remote_gate_two_tier_wording_is_one_voice(self):
        """T-124：检测线/硬门禁两级口径必须在五个载体说同一件事。

        未配 required check 时 CI 红只是可见信号，不是拦截；把"逃不过远端"当无条件承诺
        是过度承诺。骨架 AGENTS.md、workflow 首行、RFC-0004、双语 README 一处都不能漏。
        """
        wf = (H.REPO / "03-multi-harness-project" / ".github" / "workflows" /
              "coharness.yml").read_text(encoding="utf-8")
        first = wf.splitlines()[0]
        self.assertIn("检测线", first, "workflow 首行没写检测线")
        self.assertIn("硬门禁", first, "workflow 首行没写硬门禁")
        self.assertIn("merge_group:", wf, "workflow 首行附近应有 merge_group")
        agents = (H.REPO / "03-multi-harness-project" / "AGENTS.md").read_text(encoding="utf-8")
        for token in ("检测线", "硬门禁", "可见信号", "required check",
                      "coharness-gate / check", "认领直推"):
            self.assertIn(token, agents, f"03 AGENTS.md 远端门禁小节缺 {token}")
        self.assertNotIn("逃不过远端", agents, "未限定硬门禁的'逃不过远端'是过度承诺")
        rfc = (H.REPO / "docs" / "rfcs" / "RFC-0004-远端门禁.md").read_text(encoding="utf-8")
        for token in ("检测线", "硬门禁", "coharness-gate / check",
                      '"include": ["~DEFAULT_BRANCH"]', "bypass"):
            self.assertIn(token, rfc, f"RFC-0004 硬门禁节缺 {token}")
        self.assertNotIn("逃不过远端", rfc, "RFC-0004 还留着未限定的'逃不过远端'")
        for rel, tokens in (("README.md", ("检测线", "可见信号")),
                            ("README.en.md", ("detection line", "visible signal"))):
            text = (H.REPO / rel).read_text(encoding="utf-8")
            for token in tokens:
                self.assertIn(token, text, f"{rel} 缺两级口径关键词 {token}")

    def test_skeletons_ship_no_run_residue(self):
        for sk in SKELETONS:
            junk = [p for p in (H.REPO / sk).rglob("*")
                    if p.name == "__pycache__" or p.suffix == ".pyc"]
            self.assertEqual(junk, [], f"{sk} 带运行残留: {junk}")

    def test_deep_read_index_conditions_reference_real_files(self):
        """深读指引（03 骨架 AGENTS.md）里的"读哪份"必须是真文件——
        指引指向不存在的文档比没有指引更糟：harness 按表去找，第一次就撞空。"""
        agents = (H.REPO / "03-multi-harness-project" / "AGENTS.md").read_text(encoding="utf-8")
        m = re.search(r"## 深读指引.*?\n(.*?)(?:\n## |\Z)", agents, re.S)
        self.assertIsNotNone(m, "03 骨架缺「深读指引」节")
        table = m.group(1)
        refs = re.findall(r"`([^`\s]+?\.md)`", table)
        self.assertGreaterEqual(len(refs), 5, f"深读指引条目太少: {refs}")
        self.assertIn("`.agent/roles/`", table, "深读指引缺角色目录这一行")
        for rel in refs:
            if "<" in rel:            # roles/<角色>.md 这类模式行：查父目录即可
                self.assertTrue((H.REPO / "03-multi-harness-project" / rel.split("<")[0]).is_dir(),
                                f"深读指引的模式目录不存在: {rel}")
                continue
            self.assertTrue((H.REPO / "03-multi-harness-project" / rel).is_file(),
                            f"深读指引指向不存在的文件: {rel}")


if __name__ == "__main__":
    unittest.main()
