"""差分测试：拿 python-frontmatter（PyYAML）当预言机，验自写子集解析器没读错。

预言机只在骨架库开发期与 CI 里用，**不进任何分发物**（ADR-10：check.py 随骨架
复制进每个下游项目，必须纯标准库零依赖；"本机恰好装了某个库"不是可以依赖它的理由）。

跑法：
    uv venv ../.venv-coh && uv pip --python ../.venv-coh/Scripts/python.exe install python-frontmatter pyyaml
    ../.venv-coh/Scripts/python.exe -m unittest discover -s tests
未装预言机时整文件 skip，不影响零依赖的 `python -m unittest discover -s tests`。
"""
import datetime
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import helpers as H

try:
    import frontmatter  # 开发期预言机，非分发依赖
    HAVE_ORACLE = True
except ImportError:
    frontmatter = None
    HAVE_ORACLE = False

FIX = Path(__file__).resolve().parent / "fixtures"

# 这些写法 PyYAML 认（能解析出 metadata），我们**主动**拒绝：子集比 YAML 窄是政策，不是能力不足。
# 要放宽子集就得同步改这个名单，改的人得说清下游项目为什么需要它。
# 名单由预言机实测得出（python-frontmatter 1.3.0 / PyYAML 6.0.3）：
# 剩下 7 张 unsupported 夹具连 YAML 都不合法（colon-unquoted、dash-nospace、tab-nested、
# unclosed-bracket、unterminated、bare-dash、bom），两边一致，不算政策差异。
DELIBERATE_REJECTIONS = {
    "duplicate-key.md",     # YAML 后者覆盖前者 —— 静默丢数据，正是要拦的
    "block-scalar.md",      # | 与 > 的多行值
    "flow-map.md",          # {a: 1}
    "anchor.md",            # & 与 *
    "list-in-list.md",      # [[a]]
    "nested-map.md",        # 键下套键
    "multiline-scalar.md",  # 缩进续行拼成多行值
    "scalar-then-item.md",  # 已有标量的键下面再接列表项
}


def normalize(meta):
    """把两边差异限定在"空值"与"日期"两类可解释的表示差异上。"""
    out = {}
    for key, val in meta.items():
        if val is None:
            out[key] = ""
        elif isinstance(val, (list, tuple)):
            out[key] = [str(x) if isinstance(x, (datetime.date, datetime.datetime)) else x
                        for x in val]
        elif isinstance(val, (datetime.date, datetime.datetime)):
            out[key] = str(val)
        else:
            out[key] = val
    return out


@unittest.skipUnless(HAVE_ORACLE, "开发期预言机未装：uv pip install python-frontmatter pyyaml")
class DifferentialAgainstOracle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = H.load_check_module()

    def test_subset_valid_cards_agree_with_oracle(self):
        for p in sorted((FIX / "good").glob("*.md")):
            mine, _ = self.mod.parse_frontmatter(p, p.read_text(encoding="utf-8"))
            theirs = normalize(frontmatter.load(str(p)).metadata)
            self.assertEqual(mine, theirs, msg=p.name)

    def test_every_superset_card_fails_loud_for_us(self):
        for p in sorted((FIX / "unsupported").glob("*.md")):
            with self.assertRaises(self.mod.CardFormatError, msg=p.name):
                self.mod.parse_frontmatter(p, p.read_text(encoding="utf-8", errors="replace"))

    def test_policy_rejection_list_is_accurate(self):
        """DELIBERATE_REJECTIONS 必须与预言机的实际行为对得上，多写少写都算失败。"""
        parses = set()
        for p in sorted((FIX / "unsupported").glob("*.md")):
            try:
                if frontmatter.load(str(p)).metadata:
                    parses.add(p.name)
            except Exception:
                pass
        self.assertEqual(parses, DELIBERATE_REJECTIONS,
                         msg=f"预言机能解析的：{sorted(parses)}")

    def test_boundary_section_valid_cards_agree(self):
        for name in ("scalar-allowed.md",):
            p = FIX / "boundary" / name
            text = p.read_text(encoding="utf-8")
            meta, body = self.mod.parse_frontmatter(p, text)
            oracle = normalize(frontmatter.load(str(p)).metadata)
            self.assertEqual(meta, oracle, msg=name)


if __name__ == "__main__":
    unittest.main()
