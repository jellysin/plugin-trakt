<!-- markdownlint-capture -->
<!-- markdownlint-disable MD013 -->
# jellysin/plugin-trakt Agent Operating Harness

Run read-only: file edits, state mutations, commits prohibited. Mutating steps dropped; prohibitions kept.

<!-- praetor:head -->

## Core Directives & Invariants

Adopted check = coverage state + catalog path; else audit scanner; else `unknown`. Gates = (generated verification gate + praetor `lefthook.yml`); edits not reflected. Adopted-check cells credit generated gates only.

| Invariant | Rule | Adopted check | On fail |
| :--- | :--- | :--- | :--- |
| **HISS-01** control flow | recursion prohibited; call graph = DAG | `praetorctl audit` HISS scan in verify-all + lefthook pre-commit/pre-push: Go `goto`, recursion + plain-function call cycles; Rust, Python direct recursion; C `goto` | new finding fails verify-all, blocks commit, blocks push |
| **HISS-02** loops, I/O | scalar upper bound on every loop; explicit deadline on every I/O call | `praetorctl audit` HISS scan in verify-all + lefthook pre-commit/pre-push: unbounded loop shapes in Go, C, Rust, Python; I/O deadlines unchecked | new finding fails verify-all, blocks commit, blocks push |
| **HISS-03** memory | n/a: no such construct in repository languages; advisory | unknown | advisory |
| **HISS-04** complexity | McCabe cyclomatic <= 15, cognitive <= 20, statements <= 75; func LOC <= 60 (audit ceiling) | `praetorctl audit` HISS scan in verify-all + lefthook pre-commit/pre-push: function length only; other caps need repository linter | new finding fails verify-all, blocks commit, blocks push |
| **HISS-05** scoping | declare every identifier in smallest lexical scope serving it | unknown | advisory |
| **HISS-06** concurrency | explicit scalar upper bound on every worker pool + concurrent fan-out | unknown | advisory |
| **HISS-07** errors | every error handled or wrapped with context | `praetorctl audit` HISS scan in verify-all + lefthook pre-commit/pre-push: partial in Go, Rust, Python | new finding fails verify-all, blocks commit, blocks push |
| **HISS-08** determinism | zero dynamic code execution (`eval` / `exec`); a process signal's target is bounded above 1 (`killpg`, `kill(-pid)`, Go `syscall.Kill`) | `praetorctl audit` HISS scan in verify-all + lefthook pre-commit/pre-push: C banned calls, Python `eval` / `exec`, Go `syscall.Kill` / `unix.Kill` | new finding fails verify-all, blocks commit, blocks push |
| **HISS-09** reference safety | n/a: no such construct in repository languages; advisory | unknown | advisory |
| **HISS-10** warnings | zero warnings: compiler, linter, format sweeps | unknown | advisory |
| **HISS-11** supply chain | pinned lockfiles; zero floating tags; signed provenance | `praetorctl audit` supply chain + image digest pins in verify-all + lefthook pre-commit/pre-push: Actions SHA pins, Python lock hashes, CDN imports unchecked | new finding fails verify-all, blocks commit, blocks push |
| **HISS-12** secrets | zero credentials in Git history | `praetorctl security secrets` (gitleaks history scan) in verify-all + lefthook pre-push | new finding fails verify-all, blocks push |
| **HISS-13** debt ratchet | recorded infractions never grow vs committed baseline | `praetorctl audit` ratchet vs `.standards-baseline.json` in verify-all + lefthook pre-commit/pre-push | growth fails verify-all, blocks commit, blocks push |
| **HISS-14** append-only ABI | public API append-only; breaking change = `!` subject + `Migration:` footer | unknown | advisory |
| **HISS-15** 3D testing | positive + negative + boundary tests, every public interface | unknown | advisory |
| **HISS-16** context integrity | single canonical `AGENTS.md`; vendor files compiled via `praetorctl compile-context` | `praetorctl compile-context --verify` in verify-all + lefthook pre-commit | drift fails verify-all, blocks commit |
| **HISS-17** state ledger | turn start `praetorctl state status` | read-only run: step dropped | none; records only |
| **HISS-18** CI efficiency | diff-aware gating via `praetorctl ci filter` | unknown | advisory |
| **HISS-19** reuse before writing | one behavior = one implementation; extend or call existing code | unknown | advisory |
| **HISS-20** replayable evidence | every enforcement claim backed by fixtures replayed both directions | unknown | advisory |
| **HISS-21** platform neutrality | gates, hooks, emitted templates run on Linux, macOS, Windows, or skip with stated reason | unknown | advisory |

## Operational Rules

1. **Act on verified state.** Read source files, run real commands before hypothesis or edit. Never guess flag names, library signatures, repo configuration from memory.

2. **Lead with output.** Direct answers, diffs, commands. No filler preamble, no "Based on", no restatement, no chatter.

3. **Context transpiler first.** Never edit `CLAUDE.md`, `.cursor/rules/hiss-invariants.mdc`, `.github/copilot-instructions.md`, `.windsurfrules`, `.gemini/GEMINI.md`, `.codex/rules.md` manually. All agent instruction updates -> `AGENTS.md`, then:

   ```bash
   praetorctl compile-context
   ```

   - `AGENTS.md` = agent-only text -> caveman (internal register). `praetorctl compile-context --verify` + `praetorctl audit` run caveman lint; findings fail gate; no opt-out. Check first: `praetorctl caveman check --kind=context AGENTS.md`.

4. **SARIF diagnostic distillation.** Compiler/linter errors -> distill to $\le 1,500$ tokens ($< 60$ lines): top 3 root-cause failures with file/line pointers; full SARIF logs -> ephemeral storage.

5. **No evasion.** Never attempt `--no-verify`, `LEFTHOOK=0`, or modifying `.git/hooks`. Hooks = local gate adoption installs. Adoption scaffolds no CI workflow: `praetorctl` gates run local only.

6. **Anti-loop interception.** Same AST diff + error category repeats $\ge 3$ times -> halt immediately. Re-evaluate design; no micro-textual retries.

<!-- praetor:config -->

## Text Register

<!-- praetor:register:start -->
Register follows the audience, then the task label of your brief (`register:` in `.standards.yaml`; labels are the router's `target_tasks`).

| Register | Where | Form |
| :--- | :--- | :--- |
| social | forge: issues, PR bodies, review comments, commit bodies | `social-text` skill: BLUF, full sentences, scannable, enough and no more; conventional commit subject unchanged |
| docs | docs/, README, ADR bodies | complete without bloat: newcomer path first, expert reference after; every claim points at a file, command or test; no restated code |
| internal | briefs, agent-to-agent traffic, research fan-outs, workflow returns | `caveman` skill: fragments, no filler, verbatim code/paths/errors; facts, paths, commands, verdict |

- Task rows: social = commit_message_synthesis, waiver_signoff; docs = architecture_synthesis, function_docstrings; every other label and any unlabeled text = internal. Subagent launch brief: `caveman` brief shape with `task:` = routing label.
- Evidence above 58 lines or 1500 tokens leaves the message as a file under `.workingdir/evidence/`; return `evidence: <path> sha256:<12 hex> lines:<n>` and fetch it only when a decision needs it.
- An internal return carries verdict, changed paths, commands run, evidence pointers and open questions, nothing else.
<!-- praetor:register:end -->

<!-- praetor:tail -->

## Primary Verification Commands

```bash
# Fast local test suite
# Project verification unavailable: Select the Python test runner explicitly: a pytest configuration (pytest.toml, pytest.ini, a [tool.pytest] or [tool.pytest.ini_options] table in pyproject.toml, a [pytest] section in tox.ini or a [tool:pytest] section in setup.cfg), or tests/ with a Python 3.14+ pin; a pyproject.toml without a pytest table does not identify a runnable test gate. A required build or test command is absent; define and exercise the project's verify-all contract.
exit 1

# Recompile and verify cross-agent context outputs
praetorctl compile-context --verify

# Audit repository against declared HISS standards
praetorctl audit
```

<!-- markdownlint-restore -->
<!-- markdownlint-disable MD025 -->
<!-- praetor:harness:end -->
