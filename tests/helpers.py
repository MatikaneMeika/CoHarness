"""测试公共工具：临时项目、字面量 argv 调用、卡片写入。

只在骨架库自己的测试里用，不进任何骨架分发物（ADR-10：分发面保持纯标准库零依赖）。
"""
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKELETON = REPO / "03-multi-harness-project"
WSC = REPO / "wsc.py"
CHECK_SRC = SKELETON / "scripts" / "check.py"
HOOK_SRC = SKELETON / "scripts" / "hooks" / "pre-commit"

# 测试身份用 -c 注入，不读也不改用户全局配置
GIT_ID = ["-c", "user.name=coharness-test", "-c", "user.email=coharness-test@invalid",
          "-c", "commit.gpgsign=false", "-c", "core.autocrlf=false"]


def load_check_module():
    """把骨架里的 check.py 当模块载入，只用于解析器的单元测试（不跑它的 main）。"""
    spec = importlib.util.spec_from_file_location("coh_check", CHECK_SRC)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run(argv, cwd=None, native_env=False, extra_env=None):
    # PYTHONIOENCODING 只统一子进程 stdio 编码，不改 locale 首选编码，
    # 这样 wsc 内部 subprocess(text=True) 的解码缺陷仍能被测出（见 test_console_encoding）
    env = dict(os.environ) if native_env else dict(os.environ, PYTHONIOENCODING="utf-8")
    if extra_env:
        env.update(extra_env)
    return subprocess.run([str(a) for a in argv], cwd=str(cwd) if cwd is not None else None,
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=180, shell=False, env=env)


def native_cli(*args, cwd=None):
    """按本机真实控制台环境跑 wsc.py（不注入 PYTHONIOENCODING）。"""
    return run([sys.executable, WSC, *args], cwd=cwd, native_env=True)


def check(project, *args):
    """跑项目里的 scripts/check.py（ROOT 由脚本自身位置决定，所以必须跑副本）。"""
    return run([sys.executable, Path(project) / "scripts" / "check.py", *args], cwd=project)


def wsc(*args, cwd=None):
    return run([sys.executable, WSC, *args], cwd=cwd)


def git(cwd, *args):
    return run(["git", *GIT_ID, *args], cwd=cwd)


def out(res):
    return (res.stdout or "") + (res.stderr or "")


def tmp_dir():
    d = Path(tempfile.mkdtemp(prefix="coh-test-"))
    return d


def rmtree(path):
    def _clear(func, p, exc):
        Path(p).chmod(0o700)
        func(p)

    shutil.rmtree(str(path), onerror=_clear)


def make_project(parent, skeleton=None):
    """把骨架复制成临时项目（不带 .git）。"""
    src = Path(skeleton) if skeleton else SKELETON
    dst = Path(parent) / src.name
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    return dst


def git_repo(dst, bootstrap=True):
    """在 dst 建仓库（目录不存在就建）；bootstrap=True 时把现有内容提交进 main。"""
    Path(dst).mkdir(parents=True, exist_ok=True)
    git(dst, "init", "-q", "--initial-branch=main")
    if bootstrap:
        git(dst, "add", "-A")
        git(dst, "commit", "-q", "-m", "bootstrap")
    return dst


def hooks_dir(project):
    """问 git 自己钩子该放哪（兼容 worktree 的公共目录与 core.hooksPath）。"""
    r = run(["git", "rev-parse", "--git-path", "hooks"], cwd=project)
    if r.returncode != 0:
        return None
    p = Path(out(r).strip())
    return p if p.is_absolute() else Path(project) / p


def install_hook(project):
    hd = hooks_dir(project)
    if hd is None:
        return None
    hd.mkdir(parents=True, exist_ok=True)
    target = hd / "pre-commit"
    shutil.copyfile(HOOK_SRC, target)
    return target


CARD_TMPL = """---
id: {cid}
title: {title}
status: {status}
assignee: {assignee}
labels: []
created_date: 2026-09-20
updated_date: {updated}
---

## 需求
{title}

## 技术口径
（architect 填）

## 边界
allowed_paths:
{allowed}
forbidden_paths:
{forbidden}

## 验收清单
- [ ] check.py 全绿

## 交接说明
（收工时填，≤5 行）
"""

DEFAULT_ALLOWED = ["  - docs/"]
DEFAULT_FORBIDDEN = ["  - AGENTS.md", "  - .agent/"]


def card_text(cid, *, status="doing", assignee="[zcode-0926a]", allowed=None,
              forbidden=None, updated="2026-09-28 09:00", title=None):
    return CARD_TMPL.format(
        cid=cid, title=title or f"卡 {cid}", status=status,
        assignee=assignee if isinstance(assignee, str) else str(list(assignee)),
        allowed="\n".join(allowed if allowed is not None else DEFAULT_ALLOWED),
        forbidden="\n".join(forbidden if forbidden is not None else DEFAULT_FORBIDDEN),
        updated=updated,
    )


def write_card(project, cid, **kw):
    d = Path(project) / "backlog" / "tasks"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{cid}.md"
    p.write_text(card_text(cid, **kw), encoding="utf-8")
    return p
