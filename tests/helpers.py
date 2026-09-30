"""测试公共工具：临时项目、字面量 argv 调用、卡片写入。

只在骨架库自己的测试里用，不进任何骨架分发物（ADR-10：分发面保持纯标准库零依赖）。
"""
import atexit
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

# 本机登记表也不能落到用户家目录：测试里的 wsc init 一律写到这个临时 HOME
COH_HOME = Path(tempfile.mkdtemp(prefix="coh-home-"))
atexit.register(shutil.rmtree, str(COH_HOME), True)

# 测试一律看不见开发机的全局 git 配置。CI 的 runner 上没有 user.name/user.email，
# 本机有——这个差异曾让一条只设了 user.name 的测试在本机绿、四条 stdlib 腿全红。
# 需要身份的测试要么用 GIT_ID（-c 注入），要么给仓库写 local config，不许蹭全局。
EMPTY_GITCONFIG = COH_HOME / "gitconfig"
EMPTY_GITCONFIG.write_text("", encoding="utf-8")


def run(argv, cwd=None, native_env=False, extra_env=None, timeout=180):
    # PYTHONIOENCODING 只统一子进程 stdio 编码，不改 locale 首选编码，
    # 这样 wsc 内部 subprocess(text=True) 的解码缺陷仍能被测出（见 test_console_encoding）
    env = dict(os.environ) if native_env else dict(os.environ, PYTHONIOENCODING="utf-8")
    env.setdefault("COHARNESS_HOME", str(COH_HOME))
    env.setdefault("GIT_CONFIG_GLOBAL", str(EMPTY_GITCONFIG))
    env.setdefault("GIT_CONFIG_SYSTEM", str(EMPTY_GITCONFIG))
    if extra_env:
        env.update(extra_env)
    return subprocess.run([str(a) for a in argv], cwd=str(cwd) if cwd is not None else None,
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=timeout, shell=False, env=env)


def check(project, *args):
    """跑项目里的 scripts/check.py（ROOT 由脚本自身位置决定，所以必须跑副本）。"""
    return run([sys.executable, Path(project) / "scripts" / "check.py", *args], cwd=project)


def wsc(*args, cwd=None, extra_env=None):
    return run([sys.executable, WSC, *args], cwd=cwd, extra_env=extra_env)


def native_cli(*args, cwd=None):
    """按本机真实控制台环境跑 wsc.py（不注入 PYTHONIOENCODING）。"""
    return run([sys.executable, WSC, *args], cwd=cwd, native_env=True)


def git(cwd, *args):
    return run(["git", *GIT_ID, *args], cwd=cwd)


def out(res):
    return (res.stdout or "") + (res.stderr or "")


def load_check_module():
    """把骨架里的 check.py 载入内存做解析器单元测试。

    importlib 按固定路径装载，装载期间临时关掉字节码写入：不在骨架目录留
    __pycache__（"骨架混入运行残留"正是 EVOLUTION-PLAN.md:113 记过的坑），
    也不再走 exec/compile（安全门按 CWE-95 判红）。
    """
    spec = importlib.util.spec_from_file_location("coh_check_under_test", CHECK_SRC)
    mod = importlib.util.module_from_spec(spec)
    prev = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.dont_write_bytecode = prev
    return mod


def tmp_dir():
    return Path(tempfile.mkdtemp(prefix="coh-test-"))


def rmtree(path):
    """onexc 是 3.12 起的正参数；onerror 已弃用，CI 的 3.11/3.12/3.13 腿各验一个分支。"""
    def _clear(func, p, exc):
        Path(p).chmod(0o700)
        func(p)

    kwargs = {"onexc" if sys.version_info >= (3, 12) else "onerror": _clear}
    shutil.rmtree(str(path), **kwargs)


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
    p = p if p.is_absolute() else Path(project) / p
    # 必须 resolve：Windows 上 worktree 与主仓库问出来的路径可能一个是 8.3 短名
    # （CI runner 的 TEMP 就是 C:\Users\RUNNER~1\…）、一个是长名，字符串比不等但指向同一处。
    return p.resolve()


def short_path(p):
    """取 Windows 的 8.3 短名（拿不到就返回 None）。CI 的 runner 上 TEMP 本身就是短名，
    本机默认不是——用这个函数造出同样的条件，短名/长名的比较才在本地也测得到。"""
    if os.name != "nt":
        return None
    try:
        from ctypes import create_unicode_buffer, windll
    except ImportError:
        return None
    buf = create_unicode_buffer(260)
    if windll.kernel32.GetShortPathNameW(str(p), buf, 260):
        return Path(buf.value)
    return None


def install_hook(project):
    hd = hooks_dir(project)
    if hd is None:
        return None
    hd.mkdir(parents=True, exist_ok=True)
    target = hd / "pre-commit"
    shutil.copyfile(HOOK_SRC, target)
    try:
        target.chmod(0o755)
    except OSError:
        pass
    # 必须和 wsc.install_pre_commit 做同样的事：unix 上不可执行的钩子会被 git 跳过，
    # 少了这一步，测试测的就不是产品装出来的那个钩子（Windows 不看执行位，所以本机测不出来）。
    return target


CARD_TMPL = """---
id: {cid}
title: {title}
status: {status}
assignee: {assignee}
labels: {labels}
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
              forbidden=None, updated="2026-09-28 09:00", title=None, labels=None):
    return CARD_TMPL.format(
        cid=cid, title=title or f"卡 {cid}", status=status,
        assignee=assignee if isinstance(assignee, str) else str(list(assignee)),
        labels="[]" if labels is None else "[" + ", ".join(labels) + "]",
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
