# ADR-009: Autonomous Enrichment Workers — Teams with Bypass Permissions Over Background Subagents

**Status:** Revised (see Addendum)
**Date:** 2026-02-26
**Deciders:** Engineering team
**Related:** [ADR-006](./006-agent-tool-design-boundary.md) (tool-level intelligence), [ADR-008](./008-remove-autonomous-escalation.md) (autonomous escalation removal)

---

## Context

The `/clew-enrich` skill's parallel path spawns a team of workers to enrich code chunks with LLM-generated descriptions and keywords. Each worker processes a partition of chunks by running Python scripts that load batches from SQLite, generate enrichments, and save results to JSON files.

### The Approval Bottleneck

Without explicit permission configuration, every bash command a worker runs requires manual user approval. A typical enrichment run on a 5,000-chunk codebase generates ~170 bash commands per worker (load + save per batch of 30 chunks, repeated across the partition). With 4 workers, this produces ~680 approval prompts. The "parallel" orchestration is bottlenecked on human attention — the user must sit and approve each command, defeating the purpose of autonomous worker agents.

### Three Candidate Approaches

1. **Teams with `bypassPermissions`** — Keep the existing team orchestration, add `mode: "bypassPermissions"` to worker Task spawns so workers run without approval prompts.

2. **Background subagents with `bypassPermissions`** — Replace teams with `run_in_background: true` subagents. Each subagent runs autonomously and reports back on completion.

3. **Hookify auto-approve rules** — Create hookify rules that auto-approve specific bash patterns (e.g., `python3 /tmp/clew-enrich-*.py`), keeping the default permission model but surgically bypassing known-safe commands.

### The Context Bloat Observation

Background subagents (`run_in_background: true`) inject their completion results directly into the orchestrator's conversation context when they finish. With 4-5 workers completing asynchronously, each injecting their full output, the lead agent's context fills with per-worker completion data, causing "I'll wait for the others to finish" reasoning bloat and potential context window pressure.

Team workers use a mailbox system: notifications are buffered on disk and delivered as compact messages when the lead agent's turn begins. This keeps the lead's context stable regardless of how many workers are running or how verbose their outputs are.

---

## Decision

**Keep team-based orchestration. Add `mode: "bypassPermissions"` to worker Task spawns.**

Workers are spawned with `mode: "bypassPermissions"` so they can execute bash commands (Python scripts against `/tmp` files and `cache.db`) without prompting for user approval on each command.

### What Changes

1. **Worker spawn parameters.** The `Task` tool call for each worker includes `mode: "bypassPermissions"` alongside the existing `subagent_type`, `team_name`, and `name` parameters.

2. **No other changes.** The team structure, partition strategy, merge step, and cleanup flow remain identical. Only the permission model for workers changes.

### What Does Not Change

- Team creation and task assignment workflow
- Partition and bin-packing algorithm
- Worker instruction template and batch processing loop
- Merge step and re-embed flow
- Lead agent's monitoring and coordination role
- Single-agent path (< 200 chunks) — unaffected, runs in main context

---

## Alternatives Rejected

### Background subagents with `bypassPermissions`

Solves the approval bottleneck but introduces context bloat. Each subagent's completion result is injected directly into the orchestrator's conversation context. With 4-5 workers completing asynchronously, the lead agent's context fills with verbose per-worker outputs, leading to reasoning bloat ("I see worker 2 completed, let me wait for the others...") and context window pressure. **Rejected because:** the team mailbox model provides the same concurrency without context-side effects.

### Hookify auto-approve rules

Surgical approach: create rules that auto-approve bash commands matching `python3 /tmp/clew-enrich-*.py`. Preserves the default permission model for everything else. **Rejected because:** it adds configuration complexity (rules must be maintained, distributed, and explained), doesn't address any team coordination overhead, and is fragile if script paths or invocation patterns change. `bypassPermissions` is a single parameter that solves the entire class of approval prompts for a worker.

### Many small fire-and-forget subagents

Spawn one subagent per batch (30 chunks) instead of one per partition. Best cost control (each subagent has minimal context) and maximum parallelism. **Rejected because:** at scale this produces the worst context bloat — dozens of completion injections into the orchestrator, each triggering a reasoning turn. Also loses directory locality benefits of the partition strategy.

---

## Rationale

### Teams are the right orchestration model

The team model provides three properties that alternatives lack:

1. **Mailbox-buffered notifications.** Worker completion messages are written to disk and delivered as compact notifications when the lead's turn begins. The lead's context does not grow proportionally with worker count or output verbosity.

2. **Worker isolation.** Each worker has its own conversation context. A worker that encounters an error or generates verbose output does not affect other workers or the lead.

3. **Coordinated lifecycle.** The lead can monitor progress via `TaskList`, send messages to specific workers, and gracefully shut down the team when done. Background subagents lack this coordination layer.

### `bypassPermissions` has bounded risk

Workers execute a narrow, deterministic set of operations:
- Read partition files from `/tmp/clew-enrich-partition-{i}.json`
- Read chunk content from `{cache_dir}/cache.db` (SQLite read-only)
- Read relationship data from `/tmp/clew-enrich-relationships.json`
- Write enrichment output to `/tmp/clew-enrich-output-{i}.json`
- Call `TaskUpdate` to mark completion

No user input flows through the worker prompt. All file paths are hardcoded by the lead agent. The scripts are embedded verbatim in the skill instructions — workers do not generate novel bash commands. The blast radius is limited to `/tmp` files and SQLite reads.

---

## Consequences

**(+) Fully autonomous enrichment.** Zero manual approvals required for the parallel path. A 5,000-chunk enrichment run completes without user interaction after the initial `/clew-enrich` invocation.

**(+) Lead context stays stable.** Mailbox-buffered notifications prevent per-worker completion bloat. The lead agent processes compact status updates, not full worker outputs.

**(+) Workers remain isolated.** Each worker has its own context window. Errors or verbose output in one worker do not affect others or the lead.

**(-) `bypassPermissions` grants broad tool access.** Workers can execute any bash command without approval, not just the intended Python scripts. **Mitigated by:** workers receive only deterministic script instructions with hardcoded paths; no user input flows through; worker prompts are fully controlled by the skill template.

**(-) No per-command audit trail in the lead's context.** The lead does not see each bash command a worker runs. **Mitigated by:** workers log output to `/tmp/clew-enrich-output-{i}.json`; the merge step validates output format; enrichment is idempotent so partial failures are safe.

---

## Addendum: `bypassPermissions` Does Not Bypass Bash Prompts (2026-02-26)

**Finding:** Tested on the clew codebase (3,921 chunks, 4 workers). Workers spawned with `mode: "bypassPermissions"` still prompted the user for every bash command. The `bypassPermissions` mode does not suppress Claude Code's built-in bash command approval prompts for team workers.

**Evidence:** Workers produced enrichments, but only because the user manually approved each bash command. Output file growth correlated exactly with manual approvals, not autonomous execution.

**Impact:** The core premise of this ADR — that `bypassPermissions` enables zero-approval worker execution — is incorrect. The team orchestration model (mailbox buffering, worker isolation) remains sound, but the permission bypass does not work as expected for bash commands.

**Revised approach (TODO):** Investigate alternatives:
1. **Hookify auto-approve rules** — Auto-approve `python3 /tmp/clew-enrich-*` bash patterns. Originally rejected as fragile, but may be the only viable path since `bypassPermissions` doesn't work.
2. **`dontAsk` mode** — Test whether `mode: "dontAsk"` behaves differently from `bypassPermissions` for bash commands.
3. **Claude Code bug report** — If `bypassPermissions` is intended to bypass bash prompts, this is a bug worth reporting.

The SKILL.md retains `mode: "bypassPermissions"` pending resolution. It provides no harm (team orchestration still works) and will become effective if the underlying behavior is fixed.

---

## References

- `/clew-enrich` skill: `.claude/skills/clew-enrich/SKILL.md`
- Claude Code Task tool documentation: `mode` parameter controls permission model for spawned agents
- ADR-006 (Tool-level intelligence): Tools should be smarter so agents can be simpler
- ADR-008 (Remove autonomous escalation): Precedent for shifting decision authority to the right layer
