#!/usr/bin/env python3
"""只读探测项目声明的候选 harness 与角色启动命令。

项目事实来自 `.agent/dispatch.md`：
- `## 候选 harness（只读探测）` 下的 JSON 块声明本机可探测的命令；
- 角色启动命令表声明角色实际用哪个 CLI。
- `自动派发：开启/关闭` 声明收工后是否允许协议自动唤醒；缺省按关闭处理。

本脚本只用标准库：不执行候选 CLI、不联网、不写项目文件。它不决定角色映射，
只报告 PATH 上有什么、角色命令是否就绪、哪些可用候选尚未被采用。
"""
import argparse
import json
import re
import shutil
import sys
from pathlib import Path

CANDIDATE_HEADING = "## 候选 harness（只读探测）"
_AUTO_RE = re.compile(r"^\s*自动派发\s*[:：]\s*(开启|关闭)\s*$", re.M)
_CANDIDATE_BLOCK = re.compile(
    r"##\s*候选 harness（只读探测）\s*.*?```json\s*(\{.*?\})\s*```", re.S)
_TABLE_ROW = re.compile(r"^\|.*\|$")


class ConfigError(ValueError):
    """项目侧派发配置缺失或格式错误。"""


def _read_dispatch(project):
    path = Path(project).resolve() / ".agent" / "dispatch.md"
    if not path.is_file():
        raise ConfigError(f"缺 {path}：先补角色启动命令表与候选 harness 块")
    return path.read_text(encoding="utf-8")


def load_candidates(text):
    match = _CANDIDATE_BLOCK.search(text)
    if not match:
        raise ConfigError(f"缺「{CANDIDATE_HEADING}」下的 JSON 块")
    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError as e:
        raise ConfigError(f"候选 harness JSON 无法解析：{e}") from e
    rows = data.get("harnesses") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        raise ConfigError("候选 harness JSON 必须包含 harnesses 列表")
    out = []
    for row in rows:
        if not isinstance(row, dict):
            raise ConfigError("候选 harness 每项必须是对象")
        name, probe = str(row.get("name", "")).strip(), str(row.get("probe", "")).strip()
        if not name or not probe:
            raise ConfigError("候选 harness 每项都必须有 name 与 probe")
        out.append({"name": name, "probe": probe})
    return out


def load_auto_dispatch(text):
    """自动派发是显式开关；缺行时按关闭处理，旧项目不会被静默打开。"""
    match = _AUTO_RE.search(text)
    return bool(match and match.group(1) == "开启")


def load_roles(text):
    rows = []
    for line in text.splitlines():
        s = line.strip()
        if not _TABLE_ROW.match(s):
            continue
        cells = [c.strip().strip("`").strip() for c in s.strip("|").split("|")]
        if len(cells) < 2:
            continue
        if set("".join(cells[:2])) <= set("-: ") or cells[0] in ("角色", "role"):
            continue
        role, command = cells[0], cells[1]
        if not role or not command:
            raise ConfigError(f"角色启动命令表有空行：{line.strip()}")
        rows.append({"role": role, "command": command,
                     "tool": command.split(maxsplit=1)[0]})
    if not rows:
        raise ConfigError("缺角色启动命令表（角色 | 启动命令）")
    return rows


def inspect(project, which=shutil.which):
    text = _read_dispatch(project)
    candidates = load_candidates(text)
    if not candidates:
        raise ConfigError("候选 harness 未配置：由 architect 按本机环境探测或用户指定后填写")
    roles = load_roles(text)
    for role in roles:
        role["available"] = bool(which(role["tool"]))
    available = []
    missing = []
    for row in candidates:
        path = which(row["probe"])
        item = {"name": row["name"], "probe": row["probe"]}
        if path:
            item["path"] = path
            available.append(item)
        else:
            missing.append(item)
    used = {r["tool"] for r in roles}
    unmapped = [x["name"] for x in available if x["probe"] not in used]
    unready = [r["role"] for r in roles if not r["available"]]
    return {"auto_dispatch": load_auto_dispatch(text), "available": available,
            "missing": missing, "roles": roles, "unmapped": unmapped,
            "unready_roles": unready}


def render(report):
    mode = "开启" if report["auto_dispatch"] else "关闭（默认）"
    lines = [f"[dispatch-env] 自动派发：{mode}",
             "[dispatch-env] 候选 harness（PATH 只读探测）"]
    if report["available"]:
        for x in report["available"]:
            lines.append(f"  [可用] {x['name']} -> {x['path']}")
    if report["missing"]:
        for x in report["missing"]:
            lines.append(f"  [缺失] {x['name']}（探测命令：{x['probe']}）")
    if report["unmapped"]:
        lines.append("  [未映射] " + ", ".join(report["unmapped"]))
    lines.append("[dispatch-env] 角色启动命令")
    for r in report["roles"]:
        state = "可用" if r["available"] else "缺失"
        lines.append(f"  [{state}] {r['role']} -> {r['tool']}")
    if report["unready_roles"]:
        lines.append("[dispatch-env] 未就绪角色：" + ", ".join(report["unready_roles"]))
    else:
        lines.append("[dispatch-env] 所有已配置角色就绪。")
    return "\n".join(lines)


def main(argv=None, which=shutil.which):
    ap = argparse.ArgumentParser(
        prog="dispatch_env.py",
        description="只读探测候选 harness 与角色启动命令")
    ap.add_argument("project", nargs="?", default=str(Path(__file__).resolve().parents[1]),
                    help="项目路径（默认脚本所在项目）")
    ap.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    args = ap.parse_args(argv)
    try:
        report = inspect(args.project, which=which)
    except ConfigError as e:
        print(f"[dispatch-env] 配置错误：{e}")
        return 2
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render(report))
    return 1 if report["unready_roles"] else 0


if __name__ == "__main__":
    sys.exit(main())
