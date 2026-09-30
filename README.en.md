# CoHarness

Four Markdown collaboration skeletons plus a zero-dependency toolchain, so several AI coding
tools can work in one repository without stepping on each other.
中文原版：[README.md](README.md)

## What it is

A skeleton is a directory of Markdown rules (`AGENTS.md` plus `.agent/roles`, `.agent/workflows`,
`.agent/tasks`) together with the enforcement that makes those rules real: a `pre-commit` hook that
runs `scripts/check.py`, so an out-of-bounds change is refused at commit time instead of being a
polite reminder.

```bash
git clone https://github.com/MatikaneMeika/CoHarness
python CoHarness/wsc.py init <skeleton> <target-dir>     # solo / study / multi / doc, or 01-04
```

Then say “coharness <task>” to any harness inside that project; it reads the project’s
own `AGENTS.md`. Write the convention once — switching tools or sessions does not require retelling it.

Prefer a real command on `PATH`?

```bash
pipx install coharness      # or: pip install coharness
wsc init 03 ./my-project
```

Runtime dependencies: none. `wsc.py`, `maintain.py`, `evolve.py` and the `scripts/check.py` that ships
with skeleton 03 are pure Python standard library (3.11+). `python-frontmatter` exists only as a
development-time differential oracle for the parser tests; it is never imported by shipped code.

**Downloading `wsc.py` alone is not enough to instantiate a project** — instantiation copies the
skeleton bodies, which live next to `wsc.py`. The single file does cover day-to-day commands inside an
already installed project (`sync`, `check`, `claim`, `stats`, `improve`, `doctor`), and `init` says so
plainly instead of failing cryptically. CoHarness never fetches templates over the network: that would
trade “clone and go” for a runtime dependency on a remote host (see ADR-10 in
[docs/EVOLUTION-PLAN.md](docs/EVOLUTION-PLAN.md)).

## The four skeletons

| Skeleton | Use it for | External dependencies |
|---|---|---|
| `01-solo-code` | one person, one codebase | none |
| `02-study-office` | assignments, lab reports, exam prep, weekly docs | `backlog` optional |
| `03-multi-harness-project` | several components and/or several AI tools in one repo | `backlog`, `specify`, `worktrunk` (all have documented fallbacks) |
| `04-doc-production` | long documents with versions, exports and a delivery checklist | none |

03 is the full one, and what the project calls a *collaboration zone*: an ownership table says who may
write which path prefix; parallel claim serialises through `main`; one harness per worktree; every
commit from every tool passes the same `pre-commit` hook.

## It evolves itself

Most template repos are static: the author writes one version, you find it awkward, and either you live
with it or you fork and diverge. CoHarness makes “change it” a formal pipeline:

1. **Register** — when a rule gap or a missing capability actually costs rework, add one line to the
   project’s `.agent/improvements.md`. Threshold: real rework, the same friction twice or more, or a
   genuine capability gap.
2. **Pilot** — the change lands only in that project’s own `.agent/`.
3. **Audit** — `python evolve.py <project> --out record.json`: the machine gathers what is countable
   (state-machine validity, cross-project friction, whether cited evidence can be found, where the
   proposal would land); a human or LLM fills in the two subjective criteria, effectiveness and
   necessity.
4. **Write back** — a promotion candidate must pass `evolve.py --apply-check <patch>` (trial copy of
   the library, patch applied, whole suite re-run, fresh instantiation re-checked) and
   `evolve.py --verify-record <record.json>` (missing subjective field or missing proof ⇒ red). After
   your approval, the change enters the skeletons, gets one CHANGELOG line and one commit.

## Daily commands

```bash
python wsc.py init <skeleton> <dir> [--minimal]      # --minimal = zero-dependency start (TODO.md)
python wsc.py sync <project>                         # start of session: pull + board + stale
python wsc.py sync <project> --dry-run               # no pull, no network: what would land on you
python wsc.py claim <project> T-001 <id>             # atomic claim; loser rolls back cleanly
python wsc.py check <project>                        # full lint (naming, cards, ownership, conflicts)
python wsc.py improve <project> [--cross]            # pending improvements / cross-project friction
python wsc.py stats <project>                        # rule compliance, rework signal, stale spread
python wsc.py doctor [--explain <dep> | --simulate-missing <dep> <project>]
python wsc.py adapters <project> [--verify | --install <tool>]
```

Maintenance and review live in two other entry points, which deliberately do **not** ship into your
project: `maintain.py` (install fingerprint, schema migration, read-only audit) and `evolve.py`
(promotion review). The split follows ADR-10: the distribution surface stays small and auditable.

## The board

The read-only board is the fourth entry point. After `pipx install coharness` type `coh-panel`
(`coharness-panel` is the same entry under its long name); inside a clone `python panel.py` is the
same command with nothing installed. `coh-panel --plain` lists projects on this machine, then task
lists grouped by role and per-card detail. Progress comes from the
card's own `- [ ]` acceptance checklist, cross-checked against git and local run records;
mismatches are flagged (`committed but unticked`, `diverged across worktrees`).
Full screen is the default. On Windows the legacy console garbles it: use `--plain`, or start the
panel in a terminal that hands out a real TTY — Git's own mintty, verified both ways:
`mintty -e coh-panel`, or `mintty -e python panel.py` inside a clone.

## Self-tests

296 tests, no install required:

```bash
python -m unittest discover -s tests
```

They assert the promises themselves: every rule `check.py` claims to enforce, end-to-end hook
block/allow behaviour, `init` across repo / linked worktree / non-repo / nested-repo targets, skeleton
self-consistency (declared paths exist, referenced files exist, placeholders are explained), the strict
YAML subset failing loudly outside its declared grammar, and — in `tests/test_distribution_surface.py`
and `tests/test_packaging.py` — that the shipped scripts import only the standard library, make no
network calls, use no `eval`/`exec`, stay inside their line budget, and that the wheel ships the
skeletons and nothing from the development surface.

Three gate tests re-run the whole suite inside a temporary copy (that is what `--apply-check` is for), so a
full run takes on the order of ten minutes; every other promise is checked by the fast tests.

## Safety

Templates, protocol text and three standard-library scripts: no network client, no telemetry that
leaves the machine, argv-only subprocess calls without a shell. The local bookkeeping
(`.agent/telemetry.jsonl` inside your project, `~/.coharness/projects.json` for cross-project counts)
is plain local files — git-ignored, deletable, switchable off with `--no-track` /
`COHARNESS_NO_TRACK=1`, relocatable with `COHARNESS_HOME`. Details: [SECURITY.md](SECURITY.md).

## Index

- [ROUTER.md](ROUTER.md) — the “开工:” dispatch logic
- [CONTRIBUTING.md](CONTRIBUTING.md) — the three channels, registration threshold, promotion gates
- [docs/EVOLUTION-PROCESS.md](docs/EVOLUTION-PROCESS.md) — the pipeline; [docs/CHANGELOG.md](docs/CHANGELOG.md) — append-only log
- [docs/EVOLUTION-PLAN.md](docs/EVOLUTION-PLAN.md) — why it is shaped like this (ADRs)
- [docs/rfcs/](docs/rfcs/README.md) — design trade-offs with their rejected alternatives
- [SECURITY.md](SECURITY.md) — safety and data boundary

## License

MIT — see [LICENSE](LICENSE).
