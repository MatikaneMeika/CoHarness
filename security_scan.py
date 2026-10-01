#!/usr/bin/env python3
"""Deterministic AST security scan for the CoHarness repository.

This is intentionally small and policy-based. It is not a full SAST product:
it checks a fixed set of dangerous Python constructs and prints stable output.
Runtime dependencies stay at zero; CI may add pip-audit separately for dev deps.
"""
import argparse
import ast
import json
import sys
from pathlib import Path

NETWORK_MODULES = {
    "aiohttp", "ftplib", "http", "httpx", "imaplib", "poplib", "requests",
    "smtplib", "socket", "telnetlib", "urllib", "urllib3",
}
SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules", "dist", "build", "workspace"}
SHELL_CALLS = {"Popen", "run", "call", "check_call", "check_output"}


def _is_true(node):
    return isinstance(node, ast.Constant) and node.value is True


def _finding(path, node, rule, message):
    return {"file": path.as_posix(), "line": getattr(node, "lineno", 0),
            "rule": rule, "message": message}


def scan_file(path, root):
    findings = []
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, UnicodeDecodeError, SyntaxError) as e:
        return [_finding(path.relative_to(root), path, "parse", f"无法解析: {e}")]
    rel = path.relative_to(root)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fn = node.func
            if isinstance(fn, ast.Name) and fn.id in {"eval", "exec", "__import__"}:
                findings.append(_finding(rel, node, "dynamic-exec", f"禁止调用 {fn.id}()"))
            if isinstance(fn, ast.Attribute) and isinstance(fn.value, ast.Name):
                if fn.value.id == "os" and fn.attr == "system":
                    findings.append(_finding(rel, node, "shell", "禁止调用 os.system()"))
                if fn.value.id == "subprocess" and fn.attr in SHELL_CALLS:
                    for kw in node.keywords:
                        if kw.arg == "shell" and _is_true(kw.value):
                            findings.append(_finding(rel, node, "shell",
                                                     f"subprocess.{fn.attr}(shell=True) 禁止"))
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = ([a.name for a in node.names] if isinstance(node, ast.Import)
                     else [node.module or ""])
            for name in names:
                if name.split(".")[0] in NETWORK_MODULES:
                    findings.append(_finding(rel, node, "network", f"运行时禁止 import {name}"))
    return findings


def scan(root):
    root = Path(root).resolve()
    findings = []
    for path in sorted(root.rglob("*.py")):
        if SKIP_DIRS & set(path.relative_to(root).parts):
            continue
        findings.extend(scan_file(path, root))
    return findings


def main(argv=None):
    ap = argparse.ArgumentParser(description="CoHarness deterministic AST security scan")
    ap.add_argument("root", nargs="?", default=".", help="仓库根目录（默认当前目录）")
    ap.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    args = ap.parse_args(argv)
    findings = scan(args.root)
    if args.json:
        print(json.dumps({"ok": not findings, "findings": findings}, ensure_ascii=False,
                         indent=1, sort_keys=True))
    elif findings:
        for item in findings:
            print(f"{item['file']}:{item['line']}: [{item['rule']}] {item['message']}")
    else:
        print("确定性 AST 扫描：未发现问题")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
