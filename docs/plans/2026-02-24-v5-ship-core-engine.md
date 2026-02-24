# V5: Ship the Core Engine

## Context

Clew has been through 6 evaluation rounds (V2.3→V4.3). Three consecutive attempts to calibrate autonomous grep escalation have failed (gap ratio: 0%, revised gap ratio: 0%, Z-score: 64%). The core semantic engine works — it wins consistently on vocabulary bridging (B1, B2) and debugging (E4) across every evaluation. But the evaluation methodology (12-test blind A/B with ~46% noise floor) can no longer detect incremental improvements.

V5 stops iterating on thresholds, strips autonomous escalation, preserves the core engine that demonstrably adds value, adds agent skills for distribution, and instruments for real-world testing. V4.1 (7/12 wins, 4.42 avg) is the baseline.

## Approach: Forward-Fix from HEAD (Not Git Revert)

Rather than reverting to V4.1 and cherry-picking forward, we work from the current HEAD and make targeted changes. The V4.3 codebase already has the dead code removal and intent improvements we want — we just need to remove autonomous escalation and clean up. This avoids risky git resets and keeps history clean.

**Preserve current work:** Create `v4-experiments` branch from HEAD before any changes.

## Implementation Order

Phases are independently shippable. Recommended order:
1. **Phase 1** (V5 baseline) — gate to real-world testing
2. **Phase 7** (positioning + docs) — reframe identity, competitive chart, ADR-008
3. **Phase 3** (agent skills) — distribution mechanism
4. **Phase 4** (telemetry) — data collection
5. **Phase 5** (install friction) — setup script, doctor command, quickstart
6. **Phase 6** (local/offline providers) — Ollama embeddings, local reranker (research-gated)
7. **Phase 2** (count heuristic) — informed by telemetry data

## Phase 1: V5 Baseline — Remove Autonomous Escalation

**Goal:** Ship the core semantic engine with grep as explicit-only.

- Remove `_should_post_hoc_grep()` from engine
- Simplify Step 8 to explicit-only grep
- Remove `auto_escalation_enabled` config, rename `auto_escalation_timeout` → `grep_timeout`
- Remove `mode_used` and `auto_escalated` from MCP search response
- Remove auto-escalation banner from CLI
- Delete `TestShouldPostHocGrep` test class, simplify `TestAutoEscalation`
- Update integration tests for explicit-only mode

## Phase 2: Result-Count Heuristic (Opt-In) — DEFERRED

Lightweight, codebase-size-independent escalation for users who want it. Not default. Deferred until informed by telemetry data.

## Phase 3: Agent Skills (Weaviate Model)

Package clew as Claude Code skills for natural agent discovery.

## Phase 4: Query Telemetry

Lightweight JSONL logger for real-world usage data collection.

## Phase 5: Installation Friction Reduction

Setup script, `clew doctor` command, quickstart documentation.

## Phase 6: Local/Offline Provider Support — RESEARCH-GATED

Ollama embeddings, local reranker for zero-API-key deployments.

## Phase 7: Positioning Update & Competitive Comparison

ADR-008, competitive comparison chart, updated product vision and README.
