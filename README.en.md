# CoHarness

[![CI](https://github.com/MatikaneMeika/CoHarness/actions/workflows/ci.yml/badge.svg)](https://github.com/MatikaneMeika/CoHarness/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/coharness?label=PyPI)](https://pypi.org/project/coharness/)
[![Python](https://img.shields.io/pypi/pyversions/coharness)](https://pypi.org/project/coharness/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

English · [中文](README.md)

A set of file templates and small tools that let multiple AI coding tools (harnesses) work in one repository under a shared set of conventions. There is no official collaboration mechanism between harnesses — when several people (or several tools) touch the same repo, what actually works is writing the conventions into files everyone reads. This repository is that set of conventions, distilled from real failures into four templates you can clone and use.

Four things set it apart from a typical template library:

- **The conventions are files in the repo**: just Markdown plus a few hundred-line pure-stdlib Python scripts — no server, no config center, no runtime dependencies
- **Discipline is mechanical**: file naming, card format, claim conflicts, out-of-boundary edits are blocked by pre-commit / pre-push running `check.py` — not by reminders
- **The templates improve themselves**: file it, pilot it, review it; accepted changes are written back into the templates — your experience accumulates into the conventions instead of rotting in your fork
- **A read-only dashboard**: when several tools work in parallel, who is doing what, how far along, and which cards are flagged — one screen

## Quick start

**Option 1: clone and use** (recommended for a first look)

```bash
git clone https://github.com/MatikaneMeika/CoHarness
python CoHarness/wsc.py init <skeleton> <target>    # skeleton: solo / study / multi / doc, or 01-04
```

Then tell your harness "**coharness** <task>" — it works according to the conventions in the project's AGENTS.md. You write those conventions once; switching tools or sessions never means re-explaining them.

**Option 2: install as a command** (for a typeable `wsc` and `coh-panel`)

```bash
pipx install coharness      # or pip install coharness; still zero runtime dependencies
wsc init 03 ./my-project
```

Runtime dependencies: none. `wsc.py`, `maintain.py`, `evolve.py`, the dashboard (`panel.py` + `board.py`) and the `scripts/check.py` that ships with skeleton 03 are pure Python standard library (3.11+). `python-frontmatter` exists only as a development-time differential oracle for the parser tests; it is never imported by shipped code.

> **Downloading `wsc.py` alone is not enough to instantiate a project**: installation copies the
> skeleton bodies, which live next to `wsc.py`. The single file does cover day-to-day commands inside an
> already installed project (`sync`, `check`, `claim`, `stats`, `improve`, `doctor`), and `init` says so
> plainly instead of failing cryptically. CoHarness never fetches templates over the network: that would
> trade "clone and go" for a runtime dependency on a remote host (rationale in ADR-10).

## Which skeleton

Four templates, pick by deliverable:

| Skeleton | Use it for | External dependencies |
|---|---|---|
| `01-solo-code` | one person, one codebase | none |
| `02-study-office` | assignments, lab reports, exam prep, weekly docs | `backlog` optional |
| `03-multi-harness-project` | several components and/or several AI tools in one repo | `backlog`, `specify`, `worktrunk` (all have documented fallbacks) |
| `04-doc-production` | long documents with versions, exports and a delivery checklist | none |

Missing dependencies do not block you — the toolchain has fallback paths, and `wsc.py doctor` tells you what is missing, how to install it, and what degrades.

Skeleton 03 is the full one, and what the project calls a *collaboration zone*: an ownership table says who may write which path prefix; parallel claim serialises through `main`; one harness per worktree; every commit from every tool passes the same `pre-commit` hook; skeleton 03 also ships a `.github/workflows/coharness.yml` remote gate: local hooks are the first line, the CI detection line is the second — red CI is a visible signal, not an enforcement block, until `coharness-gate / check` is installed as a required check in the repo rulesets; hard gate conflicts with direct claim pushes and is not recommended by default (see [RFC-0004](docs/rfcs/RFC-0004-远端门禁.md)). The discipline in the other three comes from real lessons — `-v2`/`-final` filename suffixes pile up, edits that skip the source fork it, and one hand-edited number makes an entire report untrustworthy.

## How CoHarness relates to other tools

The layer that "several heterogeneous harnesses in one repo do not step on each other" -- path ownership, serialised claims, edits bound to cards, mutually-exclusive card boundaries -- has no high-incumbent implementation. CoHarness sits in a narrow, mostly empty slot:

| Category | State lives in | Owns | Does not own |
|---|---|---|---|
| Orchestrators ([claude-squad](https://github.com/smtg-ai/claude-squad), [cmux](https://github.com/mafialink-ai/cmux), [orca](https://github.com/stablyai/orca), ...) | each app / process side | isolating and running several agent processes in parallel | the conventions inside the repo: who may write which path, whether an edit is bound to a card |
| Kanban tools (Vibe Kanban -- see below) | server + local app dir | dispatching cards to agents | state not in git; the tool has been discontinued |
| Spec layers ([spec-kit](https://github.com/github/spec-kit), [OpenSpec](https://github.com/Fission-AI/OpenSpec), [ECC](https://github.com/affaan-m/ECC), [agents.md](https://github.com/agentsmd/agents.md), ...) | repo files | how a single agent works (spec / skill / rule) | the boundaries and conflicts between several agents |
| **CoHarness** | repo files + git | boundaries, serialised claims, mechanical enforcement for several heterogeneous harnesses in one repo | process isolation and wake-up (left to orchestrators -- coexistence, not competition) |

The table is written by mechanism, not by popularity numbers, which decay. Each named project describes its own mechanism; this section does not rank them.

### Coming from Vibe Kanban?

[Vibe Kanban](https://github.com/BloopAI/vibe-kanban) announced it is sunsetting (README banner, last commit 2026-09-19); no migration target is recommended. The audiences also overlap: cards and a board in repo Markdown, no server, no local app database. If that is your shape, the four-column semantics (`todo / doing / review / done`) carry over directly. CoHarness keeps all telemetry local and switchable off with `--no-track` / `COHARNESS_NO_TRACK=1`. State lives in git, not in an app directory next to your repo.


## Everyday commands

**Install and start work**

```bash
python wsc.py init <skeleton> <dir> [--minimal]      # --minimal = zero-dependency start (TODO.md)
python wsc.py list                                   # list skeletons
python wsc.py sync <project>                         # start of session: pull + board summary + stale report
python wsc.py sync <project> --dry-run               # no pull, no network: what would land on you
python wsc.py claim <project> T-001 <id>             # atomic claim; the loser rolls back cleanly
python wsc.py check <project>                        # full audit (naming, cards, ownership, conflicts)
```

**Stats, audits, diagnostics**

```bash
python wsc.py stats <project>                # rule adherence, rework signal, stale spread (only repo files and git log)
python wsc.py doctor                         # dependency self-check
python wsc.py doctor --explain backlog,specify            # what degrades when these are missing
python wsc.py doctor --simulate-missing backlog <project> # verify the fallback artifacts are in place
```

**Template improvements and tool adapters**

```bash
python wsc.py improve <project>              # pending improvements
python wsc.py improve --cross                # cross-project friction counts (evidence for the ≥2 threshold)
python wsc.py adapters                       # where each tool's adapter pointer should live
python wsc.py adapters <project> --verify    # self-check the pointers are still thin (not a second authority)
python wsc.py adapters <project> --install cursor  # a new tool joined mid-project: add its pointer
```

**Maintenance and review** (two more entry points; neither ships into your project — ADR-10 keeps the distribution surface small and auditable)

```bash
python maintain.py lock    <project>   # record the install fingerprint (skeleton + template commit + schema + check.py hash)
python maintain.py migrate <project>   # upgrade by schema diff: dry-run by default, --yes creates a backup branch first
python maintain.py audit   <project>   # read-only health check: hooks present/tampered, fingerprint drift, merge-style entries, main's combined state
python evolve.py  <project> --out record.json   # promotion review: the machine gathers objective evidence, a human fills the rest
```

**Dashboard + console** — who is doing what, and how far; read-only by default, with dispatch as the only write path (one key to wake the next harness). After `pipx install coharness` type `coh-panel` (`coharness-panel` is the same entry under its long name); inside a clone `python panel.py` is the same command with nothing installed:

```bash
coh-panel --plain                            # one-shot plain text: installed projects + doing/todo/flag counts
coh-panel --plain --project <project>         # one project's task list (grouped by role, core roles first)
coh-panel                                    # full-screen four pages: projects → tasks → card detail → dispatch (↑↓/Enter/Backspace/d/q)
coh-dispatch --advance <project>              # dispatch without the panel: claim + worktree + new terminal, then detach
                                              # auto-dispatch is off by default; only an explicit user switch enables it
```

- Progress reads the card's own `- [ ]` acceptance checklist, cross-checked against git and local run records; mismatches are flagged outright: "committed but unticked", "ticked but not committed", "done but checklist incomplete", "diverged across worktrees"
- Roles are derived from the single-writer ownership table in `AGENTS.md`; when it cannot be derived it says "boundary not in the ownership table" — no guessing
- Full screen is the default; if the legacy Windows console garbles it, use `--plain` or a terminal that hands out a real TTY — Git's own mintty, verified both ways: `mintty -e coh-panel`, or `mintty -e python <lib>\panel.py` inside a clone
- Design and rejected alternatives: [docs/rfcs/RFC-0002-面板展示面.md](docs/rfcs/RFC-0002-面板展示面.md)
- Dispatch page (press `d` on the task page): candidates are `todo` cards whose dependencies are done and whose boundaries do not collide with an in-progress card; the system pre-selects one by a deterministic rule (lowest card number), ↑↓ re-selects, Enter dispatches, `m` prints the command without running it, `r` retries in place. A dispatch is claim + worktree + new terminal, then it detaches at once (no handle held, no output read, no runtime state kept). The launch-command table lives project-side in `.agent/dispatch.md` (`role → command`, with `{worktree}`/`{card}` placeholders); a missing table only lists candidates and does not execute
- Host harness discovery: the project-side `python scripts/dispatch_env.py --json` probes candidates and role commands read-only; skeletons bake in no local CLI names or paths, and the architect fills them from the host or an explicit user instruction. Auto-dispatch is off by default and only the user can ask the architect/integrator to enable or disable it; an available candidate is not an automatic mapping
- Boundary of delegation vs. wake-up, the rejected resident-scheduler design, and the cost of retiring the old "dashboard is read-only" promise: [docs/rfcs/RFC-0003-委托与唤醒.md](docs/rfcs/RFC-0003-委托与唤醒.md)

## A template that improves itself

Most template repos are static: the author writes one version, you find it awkward, and either you live with it or you fork and diverge. CoHarness makes "change it" a formal pipeline, four steps:

1. **Register** — when a rule gap or a missing capability actually costs rework, add one line to the project's `.agent/improvements.md`. Threshold: real rework, the same friction twice or more, or a genuine capability gap
2. **Pilot** — the change lands only in that project's own `.agent/`
3. **Audit** — tell your harness "evolve <project path>": `python CoHarness/evolve.py <project> --out record.json` gathers what is countable (state-machine validity, cross-project friction, whether cited evidence can be found, where the proposal would land); a human or LLM fills in the two subjective criteria, effectiveness and necessity
4. **Write back** — a promotion candidate must pass `evolve.py --apply-check <patch>` (trial copy of the library, patch applied, whole suite re-run, fresh instantiation re-checked) and `evolve.py --verify-record <record.json>` (missing subjective field or missing proof ⇒ red). After your approval, the change enters the skeletons, gets one CHANGELOG line and one commit

A real upgrade from this repo: "no `-v2` / `-final` in deliverable filenames" started as a written rule; reminders did not work and the suffixes kept piling up, so it became a regex in check.py enforced by pre-commit. From "written reminder" to "mechanical enforcement" — that is the pipeline above.

Using your own clone? Improvements write back into your local templates; to give back upstream, send a PR — every upgrade of this repo came through the same pipeline. Rejection is a first-class outcome at the review gate; see [docs/EVOLUTION-PROCESS.md](docs/EVOLUTION-PROCESS.md).

## Hooking up your tools

Most mainstream harnesses read the project-root `AGENTS.md` automatically — nothing to generate. Tools that only read their own files get **native-format** thin pointers via `init --adapter` (content is a pointer plus tool metadata, never a second copy of the rules; `wsc adapters --verify` checks exactly that):

| Tool | Pointer |
|---|---|
| ZCode, Codex, Qoder, opencode, Copilot CLI, etc. | read the project-root `AGENTS.md` automatically; nothing to generate |
| Claude | `CLAUDE.md` (imports via `@AGENTS.md`) |
| Gemini | `GEMINI.md` (imports via `@AGENTS.md`) |
| Cursor | `.cursor/rules/coharness.mdc` (frontmatter `alwaysApply`) |
| Windsurf | `.windsurf/rules/coharness.md` (`trigger: always_on`) |
| Copilot (IDE) | global `.github/copilot-instructions.md` + path-specific `.github/instructions/coharness.instructions.md` (YAML `applyTo`) |

A tool joining mid-project: `wsc adapters <project> --install <tool>`. Tools that support skills can optionally install `skills/coharness/` (copy over, adjust one path); skipping it changes nothing.

When guidance conflicts: **project rules > spec-kit output > task cards > verbal session agreements**.

## Tests and quality

The repo ships 416 self-tests that run without installing anything:

```bash
python -m unittest discover -s tests     # zero deps; CI runs the same command on ubuntu/windows/macos × py3.11/3.12/3.13
```

They assert the promises themselves: every rule `check.py` claims to enforce, the dashboard's read-only behavior and divergence flags, end-to-end hook block/allow behaviour, `init` across repo / linked worktree / non-repo / nested-repo targets, skeleton self-consistency (declared paths exist, referenced files exist, placeholders are explained), the strict YAML subset failing loudly outside its declared grammar, and — in `tests/test_distribution_surface.py` and `tests/test_packaging.py` — that the shipped scripts import only the standard library, make no network calls, use no `eval`/`exec`, stay inside their line and function budgets, and that the wheel ships the skeletons and nothing from the development surface.

Three gate tests re-run the whole suite inside a temporary copy (that is what `--apply-check` is for), so a full run takes on the order of ten minutes; every other promise is checked by the fast tests.

## On security

Templates, protocol text and a few standard-library scripts: no network client, no telemetry that leaves the machine, argv-only subprocess calls without a shell. The local bookkeeping (`.agent/telemetry.jsonl` inside your project, `~/.coharness/projects.json` for cross-project counts) is plain local files — git-ignored, deletable, switchable off with `--no-track` / `COHARNESS_NO_TRACK=1`, relocatable with `COHARNESS_HOME`. The projects you instantiate belong to your repository — nothing is collected or uploaded here. Details: [SECURITY.md](SECURITY.md).

## Docs and provenance

- [ROUTER.md](ROUTER.md) — the "coharness" dispatch logic and role matching
- [CONTRIBUTING.md](CONTRIBUTING.md) — the three channels, registration threshold, promotion gates, PR checklist
- [docs/rfcs/](docs/rfcs/README.md) — design trade-offs with their rejected alternatives (RFC-0001 atomic claims, RFC-0002 the dashboard, RFC-0003 delegation and wake-up; all adopted)
- [docs/EVOLUTION-PROCESS.md](docs/EVOLUTION-PROCESS.md) — the pipeline; [docs/CHANGELOG.md](docs/CHANGELOG.md) — append-only log
- [docs/EVOLUTION-PLAN.md](docs/EVOLUTION-PLAN.md) — why it is shaped like this (ADRs)
- [SECURITY.md](SECURITY.md) — safety and data boundary

Task cards use [Backlog.md](https://github.com/MrLesk/backlog.md) (1.53.0), spec decomposition uses [GitHub Spec Kit](https://github.com/github/spec-kit) (1.0.13), worktrees use [Worktrunk](https://github.com/max-sixty/worktrunk) (0.80.0, the command is called git-wt on Windows); all three verified by full-workflow install and execution in an isolated sandbox on 2026-10-02.

<details>
<summary>Known third-party quirks and hands-on lessons (Backlog 1.53.0 / Spec Kit 1.0.13 / Worktrunk 0.80.0, really installed and run 2026-10-02)</summary>

- **Backlog.md**:
  - The default board columns are `To Do / In Progress / Done`; this skeleton's four columns require editing `statuses` in `backlog/config.yml` (`backlog config set` refuses direct edits)
  - It recognizes cards as `t-<number> - <title>.md`; a hand-made `T-001.md` is not listed by the tool
  - `backlog init --agent-instructions` injects its own instructions into AGENTS.md; this skeleton requires `none`
- **Spec Kit**:
  - `specify init` does not tamper with `AGENTS.md` (all four integrations tamper with 0 tracked files), but creates a `.specify/memory/constitution.md` skeleton; after project instantiation, `docs/CONSTITUTION-SOURCE.md` must be pumped in to maintain a single source of global discipline
  - The Codex integration installs skills to `.agents/skills` (plural); generic requires explicitly specifying `--commands-dir`
- **Worktrunk** (`git-wt`):
  - `git-wt switch -c` creates a new tree in a sibling directory `../<repo>.<branch>`; in environments without shell hooks it does not automatically change the terminal's working directory, so you must explicitly switch into it
  - On Windows, background cleanup is delayed when a process holds a handle to the worktree; after merge at sign-off, return to the main worktree and run `git-wt remove <branch> -y`
  - Commands are `switch` / `list` / `merge` / `remove`; there is no `add` subcommand
- **Dropped tools**: Vibe Kanban was evaluated and dropped: announced sunset, and its board data lives in an app directory outside the repo

</details>

## License

MIT — see [LICENSE](LICENSE).
