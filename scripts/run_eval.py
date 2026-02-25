#!/usr/bin/env python3
"""V4.3-beta blind evaluation orchestrator.

Automates the full 7-phase viability evaluation pipeline:
  Phase 0: Pre-flight checks
  Phase 1: Exploration (24 agents: 12 tests x 2 tools)
  Phase 2: Sanitization
  Phase 3: Verification (optional)
  Phase 4: Scoring (24 agents: 12 tests x 2 scorers)
  Phase 5: Computation + behavioral extraction
  Phase 6: Disagreement resolution (conditional)

Usage:
    python3 scripts/run_eval.py [--resume] [--phase N]
"""

from __future__ import annotations

import asyncio
import argparse
import json
import logging
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
EVAL_DIR = PROJECT_ROOT / ".clew-eval" / "v4.3-beta"
RAW_DIR = EVAL_DIR / "raw-transcripts"
SANITIZED_DIR = EVAL_DIR / "sanitized-transcripts"
SCORES_DIR = EVAL_DIR / "scores"
STATE_FILE = EVAL_DIR / "eval_state.json"
LOG_FILE = EVAL_DIR / "run.log"
BEHAVIORAL_FILE = EVAL_DIR / "behavioral.json"

TARGET_CODEBASE = Path("/Users/albertgwo/Work/evvy")

GROUND_TRUTH_TRACK_A = PROJECT_ROOT / ".clew-eval" / "v3.0" / "ground-truth" / "track-b-checklists.md"
GROUND_TRUTH_E1 = PROJECT_ROOT / ".clew-eval" / "v4.1" / "ground-truth" / "E1-checklist.md"
GROUND_TRUTH_E2 = PROJECT_ROOT / ".clew-eval" / "v4.1" / "ground-truth" / "E2-checklist.md"
GROUND_TRUTH_E3 = PROJECT_ROOT / ".clew-eval" / "v4.1" / "ground-truth" / "E3-checklist.md"
GROUND_TRUTH_E4 = PROJECT_ROOT / ".clew-eval" / "v4.1" / "ground-truth" / "E4-checklist.md"

# Master seed for Alpha/Beta randomization (new for V4.3-beta)
MASTER_SEED = 20260223


def _clean_env() -> dict[str, str]:
    """Return a copy of os.environ without CLAUDECODE (prevents nested session error)."""
    env = dict(os.environ)
    env.pop("CLAUDECODE", None)
    return env

# ---------------------------------------------------------------------------
# Test scenarios
# ---------------------------------------------------------------------------
TESTS = ["A1", "A2", "A3", "A4", "B1", "B2", "C1", "C2", "E1", "E2", "E3", "E4"]

SCENARIOS: dict[str, str] = {
    "A1": "A customer reported their subscription renewal didn't create a prescription fill. Investigate the code path from order webhook to PrescriptionFill creation and identify where failures can occur.",
    "A2": "We need to add a new checkout source type for a partner integration. What code needs to change? Provide a comprehensive list of files and code locations that reference or depend on the checkout source concept.",
    "A3": "The pharmacy API is returning errors for some refill orders. Where in the codebase do we call the pharmacy API, how do we handle errors from it, and what retry/monitoring logic exists?",
    "A4": "Explain how the order processing system decides what type of order it is (e.g., new subscription vs. refill vs. one-time purchase) and how that determination affects downstream processing.",
    "B1": "We're considering changing the signature of the function that processes shopify orders for treatment refills. What would break? Find all callers, understand what arguments they pass, and identify any test coverage.",
    "B2": "Map the relationship between Order, PrescriptionFill, and Prescription models. Include foreign keys, many-to-many relationships, through-tables, and any computed properties that bridge them.",
    "C1": "Find all Django URL patterns that involve ecomm-related views. List each URL pattern with its view and URL path.",
    "C2": "Find all Stripe API calls in the codebase. List each call site with the Stripe API method being called and the context in which it's used.",
    "E1": 'Our application uses custom Django middleware for request processing. Map all custom middleware classes: what each one does, what order they run in, and how they interact with each other. Focus on application-specific middleware, not standard Django middleware. Also identify any middleware that conditionally skips processing based on request attributes.',
    "E2": 'Create a complete inventory of all Celery tasks in the codebase. For each task, identify: (1) the task function name and file location, (2) what arguments it accepts, (3) how it is enqueued (`.delay()`, `.apply_async()`, or `send_task()`), (4) what retry configuration it has (if any), and (5) the business purpose of the task.',
    "E3": 'Starting from the Order model, trace how creating an order triggers the creation of related records. Map the full chain: which models are created as side effects of order processing, what service functions orchestrate this creation, and what happens if any step in the chain fails. Include the relationships between the created records.',
    "E4": "A user reported that their subscription order was processed successfully but they didn't receive a confirmation email. Investigate the email sending pipeline from order completion to email dispatch. Focus on identifying the specific failure path — where in the code could the email send fail silently? Do NOT catalog all email-related code in the codebase.",
}

# Map test IDs to their ground-truth checklist files
# Track A: A1-A4 have no formal checklists; B1/B2/C1/C2 map to D1-D4 in track-b-checklists.md
# Track B: E1-E4 have individual checklist files
CHECKLIST_MAP: dict[str, Path | None] = {
    "A1": None, "A2": None, "A3": None, "A4": None,
    "B1": GROUND_TRUTH_TRACK_A,  # D1 section
    "B2": GROUND_TRUTH_TRACK_A,  # D2 section (actually B2 maps to D4)
    "C1": GROUND_TRUTH_TRACK_A,  # D3 section (actually C1 maps to D3-ish)
    "C2": GROUND_TRUTH_TRACK_A,  # D4 section
    "E1": GROUND_TRUTH_E1, "E2": GROUND_TRUTH_E2,
    "E3": GROUND_TRUTH_E3, "E4": GROUND_TRUTH_E4,
}

# ---------------------------------------------------------------------------
# Agent prompts
# ---------------------------------------------------------------------------
CLEW_PROMPT_TEMPLATE = """You are exploring a codebase to answer a question. You have access to a code search tool called `clew` (via Bash) and the Read tool for viewing files.

Working directory: {codebase}

SEARCH TOOL USAGE:
- Search: clew search "your query" --project-root {codebase} --json
- Trace: clew trace "entity_name" --project-root {codebase} --json

TASK:
{scenario}

INSTRUCTIONS:
- Budget: ~20 tool calls. Prioritize the most important artifacts first.
- Provide a comprehensive answer with specific file paths and code references.
- Do NOT access files outside the working directory.
- Do NOT read CLAUDE.md, .claude/, or tool documentation files."""

GREP_PROMPT_TEMPLATE = """You are exploring a codebase to answer a question. You have access to Grep, Glob, and Read tools only.

Working directory: {codebase}

TASK:
{scenario}

INSTRUCTIONS:
- Budget: ~20 tool calls. Prioritize the most important artifacts first.
- Provide a comprehensive answer with specific file paths and code references.
- Do NOT access files outside the working directory.
- Do NOT read CLAUDE.md, .claude/, or tool documentation files."""

SCORER_PROMPT_TEMPLATE = """You are scoring two agent transcripts that attempted the same codebase exploration task.
Score each agent independently on 5 dimensions (1-5 integers). Do NOT compute aggregates
or declare a winner.

RUBRIC:
| Dimension | Weight | 5 | 4 | 3 | 2 | 1 |
|-----------|--------|---|---|---|---|---|
| Discovery (30%) | Tool calls to understanding | <=5 | 6-7 | 8-12 | 13-15 | 15+ |
| Precision (25%) | Signal-to-noise ratio | <=10% | 10-20% | 20-40% | 40-60% | 60%+ |
| Completeness (20%) | Checklist coverage | All | >=90% | >=70% | 50-70% | <50% |
| Relational (15%) | Unexpected connections | >=3 | 2 | 1 | 0 | No capability |
| Confidence (10%) | Actionability | Immediate | 1 follow-up | 2-3 | Significant | Not actionable |

{checklist_section}

TRANSCRIPTS:

--- AGENT ALPHA ---
{alpha_transcript}

--- AGENT BETA ---
{beta_transcript}

Return ONLY valid JSON (no markdown, no explanation):
{{"test_id": "{test_id}", "alpha": {{"discovery": N, "precision": N, "completeness": N, "relational": N, "confidence": N}}, "beta": {{"discovery": N, "precision": N, "completeness": N, "relational": N, "confidence": N}}}}"""

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
log = logging.getLogger("eval")


def _setup_logging() -> None:
    """Configure logging after directories are created."""
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(LOG_FILE, mode="a"),
        ],
    )

# ---------------------------------------------------------------------------
# State management
# ---------------------------------------------------------------------------

def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {
        "phase": "preflight",
        "completed": {"exploration": [], "scoring": []},
        "failed": [],
        "started_at": datetime.now(timezone.utc).isoformat(),
    }


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2) + "\n")


def is_completed(state: dict, category: str, key: str) -> bool:
    return key in state["completed"].get(category, [])


def mark_completed(state: dict, category: str, key: str) -> None:
    state["completed"].setdefault(category, [])
    if key not in state["completed"][category]:
        state["completed"][category].append(key)
    save_state(state)


def mark_failed(state: dict, key: str, error: str) -> None:
    state["failed"].append({"key": key, "error": error, "at": datetime.now(timezone.utc).isoformat()})
    save_state(state)


# ---------------------------------------------------------------------------
# Phase 0: Pre-flight
# ---------------------------------------------------------------------------

def run_preflight() -> bool:
    log.info("=== Phase 0: Pre-flight ===")
    ok = True

    env = _clean_env()

    # 1. Check claude CLI
    try:
        result = subprocess.run(["claude", "--version"], capture_output=True, text=True, timeout=10, env=env)
        log.info(f"claude CLI: {result.stdout.strip()}")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        log.error("claude CLI not found or timed out")
        ok = False

    # 2. Check clew status
    try:
        result = subprocess.run(
            ["clew", "status"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            log.error(f"clew status failed: {result.stderr}")
            ok = False
        else:
            log.info(f"clew status: OK")
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        log.error(f"clew status check failed: {e}")
        ok = False

    # 3. Sample query
    try:
        result = subprocess.run(
            ["clew", "search", "order processing", "--project-root", str(TARGET_CODEBASE), "--json"],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            log.error(f"clew sample query failed: {result.stderr}")
            ok = False
        else:
            log.info("clew sample query: OK")
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        log.error(f"clew sample query failed: {e}")
        ok = False

    # 4. Target codebase exists
    if not TARGET_CODEBASE.exists():
        log.error(f"Target codebase not found: {TARGET_CODEBASE}")
        ok = False
    else:
        log.info(f"Target codebase: {TARGET_CODEBASE}")

    # 5. Ground-truth checklists exist
    for path in [GROUND_TRUTH_TRACK_A, GROUND_TRUTH_E1, GROUND_TRUTH_E2, GROUND_TRUTH_E3, GROUND_TRUTH_E4]:
        if not path.exists():
            log.error(f"Ground-truth checklist missing: {path}")
            ok = False

    # 6. Directory structure
    for d in [RAW_DIR, SANITIZED_DIR, SCORES_DIR]:
        d.mkdir(parents=True, exist_ok=True)

    if ok:
        log.info("Pre-flight: ALL CHECKS PASSED")
    else:
        log.error("Pre-flight: FAILED — fix issues above before proceeding")
    return ok


# ---------------------------------------------------------------------------
# Phase 1: Exploration
# ---------------------------------------------------------------------------

RAW_DUMP_DIR = EVAL_DIR / "raw-dumps"


def _count_assistant_events(output: str) -> int:
    """Count type:assistant events in stream-json output."""
    count = 0
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
            if entry.get("type") == "assistant":
                count += 1
        except json.JSONDecodeError:
            continue
    return count


async def run_agent(
    prompt: str,
    tools: str,
    label: str,
    timeout_s: int = 600,
    retry: bool = True,
) -> str | None:
    """Run a claude -p agent and return stdout."""
    cmd = [
        "claude", "-p",
        "--verbose",
        "--model", "sonnet",
        "--output-format", "stream-json",
        "--dangerously-skip-permissions",
        "--no-session-persistence",
        "--max-turns", "25",
        "--add-dir", str(TARGET_CODEBASE),
    ]
    # Only add --tools if a non-empty value is provided
    if tools:
        cmd.extend(["--tools", tools])

    env = _clean_env()

    RAW_DUMP_DIR.mkdir(parents=True, exist_ok=True)

    for attempt in range(2 if retry else 1):
        try:
            log.info(f"  [{label}] Starting (attempt {attempt + 1})")
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(input=prompt.encode()),
                timeout=timeout_s,
            )
            output = stdout.decode()
            stderr_text = stderr.decode()

            # Always save raw dump for debugging
            dump_path = RAW_DUMP_DIR / f"{label}-attempt{attempt + 1}.jsonl"
            dump_path.write_text(output)
            if stderr_text.strip():
                (RAW_DUMP_DIR / f"{label}-attempt{attempt + 1}.stderr").write_text(stderr_text)

            # Check for rate limit in stderr
            if "429" in stderr_text or "rate_limit" in stderr_text.lower():
                log.warning(f"  [{label}] Rate limited, backing off 30s")
                await asyncio.sleep(30)
                continue

            # Check for actual assistant content (not just system events)
            assistant_count = _count_assistant_events(output)
            if assistant_count == 0:
                log.warning(f"  [{label}] No assistant messages in output ({len(output)} chars total, dump: {dump_path})")
                if attempt == 0 and retry:
                    continue
                return None

            log.info(f"  [{label}] Completed ({len(output)} chars, {assistant_count} assistant events)")
            return output

        except asyncio.TimeoutError:
            log.warning(f"  [{label}] Timeout after {timeout_s}s")
            try:
                proc.kill()
            except ProcessLookupError:
                pass
            if attempt == 0 and retry:
                continue
            return None
        except Exception as e:
            log.error(f"  [{label}] Error: {e}")
            if attempt == 0 and retry:
                continue
            return None

    return None


def extract_transcript(stream_json_output: str) -> str:
    """Extract transcript from claude -p --output-format stream-json output.

    stream-json produces JSONL: one JSON object per line, each with
    a "type" field. Assistant messages have type="assistant" with a
    "message" sub-object containing role, content, etc.
    """
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
    from extract_transcripts import extract_transcript_from_messages

    messages: list[dict] = []
    event_types: dict[str, int] = {}

    for line in stream_json_output.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue

        event_type = entry.get("type", "unknown")
        event_types[event_type] = event_types.get(event_type, 0) + 1

        # stream-json emits: {"type": "assistant"|"user", "message": {...}}
        if event_type in ("assistant", "user"):
            msg = entry.get("message")
            if msg and isinstance(msg, dict):
                messages.append(msg)

    if not messages:
        log.warning(f"extract_transcript: 0 messages found. Event types: {event_types}")

    return extract_transcript_from_messages(messages)


def extract_result_text(stream_json_output: str) -> str:
    """Extract the 'result' field from stream-json output.

    The last line of stream-json is typically: {"type":"result","result":"..."}
    """
    for line in reversed(stream_json_output.splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
            if entry.get("type") == "result":
                return entry.get("result", "")
        except json.JSONDecodeError:
            continue
    return stream_json_output  # fallback: return raw output


async def run_exploration(state: dict) -> None:
    log.info("=== Phase 1: Exploration ===")
    codebase = str(TARGET_CODEBASE)

    # Build task list for incomplete explorations
    grep_tasks: list[tuple[str, str, str]] = []
    clew_tasks: list[tuple[str, str, str]] = []

    for test_id in TESTS:
        grep_key = f"{test_id}-grep"
        clew_key = f"{test_id}-clew"

        if not is_completed(state, "exploration", grep_key):
            prompt = GREP_PROMPT_TEMPLATE.format(codebase=codebase, scenario=SCENARIOS[test_id])
            grep_tasks.append((test_id, grep_key, prompt))

        if not is_completed(state, "exploration", clew_key):
            prompt = CLEW_PROMPT_TEMPLATE.format(codebase=codebase, scenario=SCENARIOS[test_id])
            clew_tasks.append((test_id, clew_key, prompt))

    log.info(f"Grep tasks remaining: {len(grep_tasks)}, Clew tasks remaining: {len(clew_tasks)}")

    # Run grep agents (6 concurrent)
    async def run_grep(test_id: str, key: str, prompt: str) -> None:
        output = await run_agent(prompt, "Grep,Glob,Read", key)
        if output:
            transcript = extract_transcript(output)
            (RAW_DIR / f"{test_id}-grep.md").write_text(transcript)
            mark_completed(state, "exploration", key)
        else:
            mark_failed(state, key, "empty or timed out")

    for batch_start in range(0, len(grep_tasks), 6):
        batch = grep_tasks[batch_start:batch_start + 6]
        log.info(f"Grep batch {batch_start // 6 + 1}: {[t[1] for t in batch]}")
        await asyncio.gather(*(run_grep(*t) for t in batch))

    # Run clew agents (3 concurrent — shared Qdrant/Voyage)
    async def run_clew(test_id: str, key: str, prompt: str) -> None:
        output = await run_agent(prompt, "Bash,Read", key)
        if output:
            transcript = extract_transcript(output)
            (RAW_DIR / f"{test_id}-clew.md").write_text(transcript)
            mark_completed(state, "exploration", key)
        else:
            mark_failed(state, key, "empty or timed out")

    for batch_start in range(0, len(clew_tasks), 3):
        batch = clew_tasks[batch_start:batch_start + 3]
        log.info(f"Clew batch {batch_start // 3 + 1}: {[t[1] for t in batch]}")
        await asyncio.gather(*(run_clew(*t) for t in batch))


# ---------------------------------------------------------------------------
# Phase 2: Sanitization
# ---------------------------------------------------------------------------

def run_sanitization() -> None:
    log.info("=== Phase 2: Sanitization ===")
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
    from sanitize_transcripts import process_test

    all_mappings: dict = {}
    for i, test_id in enumerate(TESTS):
        result = process_test(test_id, RAW_DIR, SANITIZED_DIR, seed=MASTER_SEED + i)
        all_mappings.update(result)

    mapping_path = SANITIZED_DIR / "mapping.json"
    mapping_path.write_text(json.dumps(all_mappings, indent=2) + "\n")
    log.info(f"Sanitized {len(all_mappings)} tests, mapping written to {mapping_path}")


# ---------------------------------------------------------------------------
# Phase 3: Verification (optional)
# ---------------------------------------------------------------------------

async def run_verification() -> bool:
    log.info("=== Phase 3: Verification (optional) ===")
    import random
    rng = random.Random(MASTER_SEED)

    # Pick 4 random tests
    sample_tests = rng.sample(TESTS, 4)
    transcripts = ""
    for test_id in sample_tests:
        alpha = (SANITIZED_DIR / f"{test_id}-Alpha.md").read_text()[:2000]
        beta = (SANITIZED_DIR / f"{test_id}-Beta.md").read_text()[:2000]
        transcripts += f"\n=== Test {test_id} ===\n\nAgent Alpha (first 2000 chars):\n{alpha}\n\nAgent Beta (first 2000 chars):\n{beta}\n"

    prompt = f"""You are verifying the blinding quality of sanitized agent transcripts.

For each of the 4 test pairs below, try to determine which agent used a semantic code search tool vs standard grep/glob.

For each test, report:
- Your guess: Alpha or Beta used the semantic tool?
- Your confidence: 0-100%

{transcripts}

Return JSON: {{"tests": [{{"test_id": "X", "semantic_agent": "Alpha|Beta", "confidence": N}}]}}"""

    output = await run_agent(prompt, "", "verification", timeout_s=120, retry=False)
    if not output:
        log.warning("Verification agent failed — skipping")
        return True

    try:
        result_text = extract_result_text(output)
        result = json.loads(result_text) if isinstance(result_text, str) else result_text
        tests = result.get("tests", [])
        correct_high = sum(1 for t in tests if t.get("confidence", 0) > 60)
        if correct_high > 1:
            log.warning(f"VERIFICATION WARNING: {correct_high}/4 identified with >60% confidence — review blinding")
            return False
        log.info(f"Verification passed: {correct_high}/4 high-confidence identifications")
        return True
    except (json.JSONDecodeError, TypeError, KeyError):
        log.warning("Could not parse verification output — proceeding")
        return True


# ---------------------------------------------------------------------------
# Phase 4: Scoring
# ---------------------------------------------------------------------------

def get_checklist_text(test_id: str) -> str:
    """Load ground-truth checklist for a test, or return empty string."""
    path = CHECKLIST_MAP.get(test_id)
    if path is None:
        return ""

    text = path.read_text()

    # For Track A tests using the combined file, extract relevant section
    # B1->D1, B2->D4, C1->D3, C2->D4 (C1 is actually email debug, C2 is auth)
    # Actually the mapping from the V4.2 test plan: Track A = A1-C2,
    # with B1/B2/C1/C2 using .clew-eval/v3.0/ground-truth/track-b-checklists.md
    # D1=Celery tasks, D2=Env vars, D3=Email debug, D4=Auth mapping
    # But test scenarios: B1=shopify refill signature, B2=Order/PrescriptionFill relationship
    # C1=Django URL patterns, C2=Stripe API calls
    # These don't directly map to D1-D4, so return the whole file
    return text


async def run_scoring(state: dict) -> None:
    log.info("=== Phase 4: Scoring ===")
    mapping = json.loads((SANITIZED_DIR / "mapping.json").read_text())

    tasks: list[tuple[str, int, str]] = []

    for test_id in TESTS:
        for scorer_num in [1, 2]:
            key = f"{test_id}-scorer{scorer_num}"
            if is_completed(state, "scoring", key):
                continue

            alpha_path = SANITIZED_DIR / f"{test_id}-Alpha.md"
            beta_path = SANITIZED_DIR / f"{test_id}-Beta.md"

            if not alpha_path.exists() or not beta_path.exists():
                log.warning(f"Missing sanitized transcript for {test_id}")
                continue

            alpha_text = alpha_path.read_text()
            beta_text = beta_path.read_text()

            checklist = get_checklist_text(test_id)
            checklist_section = f"GROUND-TRUTH CHECKLIST:\n{checklist}" if checklist else "No formal checklist for this test. Score against the absolute rubric."

            prompt = SCORER_PROMPT_TEMPLATE.format(
                checklist_section=checklist_section,
                alpha_transcript=alpha_text,
                beta_transcript=beta_text,
                test_id=test_id,
            )
            tasks.append((test_id, scorer_num, prompt))

    log.info(f"Scoring tasks remaining: {len(tasks)}")

    async def score_one(test_id: str, scorer_num: int, prompt: str) -> None:
        key = f"{test_id}-scorer{scorer_num}"
        output = await run_agent(prompt, "", key, timeout_s=180)

        if not output:
            mark_failed(state, key, "empty output")
            return

        # Extract the result text from stream-json output
        result_text = extract_result_text(output)

        # Extract JSON from the result text
        score_data = None
        # Try direct parse
        try:
            score_data = json.loads(result_text)
        except (json.JSONDecodeError, TypeError):
            pass

        # Try extracting JSON from markdown code block or text
        if score_data is None:
            json_match = re.search(r'\{[^{}]*"alpha"[^{}]*"beta"[^{}]*\}', result_text, re.DOTALL)
            if json_match:
                try:
                    score_data = json.loads(json_match.group())
                except json.JSONDecodeError:
                    pass

        # Try more aggressive extraction
        if score_data is None:
            json_match = re.search(r'\{[\s\S]*?"alpha"[\s\S]*?"beta"[\s\S]*?\}(?=\s*$|\s*```)', result_text)
            if json_match:
                try:
                    score_data = json.loads(json_match.group())
                except json.JSONDecodeError:
                    pass

        if score_data is None:
            log.warning(f"  [{key}] Failed to parse JSON — retrying with stricter prompt")
            retry_prompt = prompt + "\n\nIMPORTANT: Return ONLY valid JSON, no other text. No markdown, no explanation."
            retry_output = await run_agent(retry_prompt, "", f"{key}-retry", timeout_s=120, retry=False)
            if retry_output:
                try:
                    text2 = extract_result_text(retry_output)
                    score_data = json.loads(text2)
                except (json.JSONDecodeError, TypeError):
                    pass

        if score_data is None:
            mark_failed(state, key, "JSON parse failed after retry")
            return

        # Validate structure
        for agent_label in ["alpha", "beta"]:
            if agent_label not in score_data:
                mark_failed(state, key, f"missing '{agent_label}' in scores")
                return
            for dim in ["discovery", "precision", "completeness", "relational", "confidence"]:
                if dim not in score_data[agent_label]:
                    mark_failed(state, key, f"missing '{dim}' in {agent_label} scores")
                    return
                val = score_data[agent_label][dim]
                if not isinstance(val, (int, float)) or val < 1 or val > 5:
                    mark_failed(state, key, f"invalid score {agent_label}.{dim}={val}")
                    return

        # Write scorer output
        score_file = SCORES_DIR / f"{test_id}-scorer{scorer_num}.json"
        score_data["test_id"] = test_id
        score_file.write_text(json.dumps(score_data, indent=2) + "\n")
        mark_completed(state, "scoring", key)
        log.info(f"  [{key}] Scored: alpha={sum(score_data['alpha'].values())}, beta={sum(score_data['beta'].values())}")

    # Run all scorers concurrently (no resource contention)
    await asyncio.gather(*(score_one(*t) for t in tasks))


# ---------------------------------------------------------------------------
# Phase 5: Computation
# ---------------------------------------------------------------------------

def run_assembly() -> None:
    """Assemble scorer files into scores.json."""
    log.info("Assembling scores...")
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
    from assemble_scores import assemble_scores
    consolidated, missing = assemble_scores(SCORES_DIR)

    if missing:
        log.warning(f"Missing scorer files: {missing}")

    output_path = SCORES_DIR / "scores.json"
    output_path.write_text(json.dumps(consolidated, indent=2) + "\n")
    log.info(f"Assembled {len(consolidated['tests'])}/12 tests -> {output_path}")


def run_behavioral_extraction() -> None:
    """Phase 5.5: Extract behavioral metrics from raw clew transcripts."""
    log.info("=== Phase 5.5: Behavioral Extraction ===")

    total_queries = 0
    escalated_queries = 0
    confidence_dist: dict[str, int] = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    e4_auto_escalated = None
    location_escalations = 0

    for test_id in TESTS:
        raw_path = RAW_DIR / f"{test_id}-clew.md"
        if not raw_path.exists():
            continue

        text = raw_path.read_text()

        # Count clew search invocations
        search_calls = re.findall(r'clew search\b', text)
        trace_calls = re.findall(r'clew trace\b', text)
        queries = len(search_calls) + len(trace_calls)
        total_queries += queries

        # Count escalated queries (auto_escalated: true or mode_used: exhaustive)
        escalated = len(re.findall(r'"auto_escalated":\s*true', text))
        exhaustive = len(re.findall(r'"mode_used":\s*"exhaustive"', text))
        esc_count = max(escalated, exhaustive)
        escalated_queries += esc_count

        # Count confidence labels
        for label in ["HIGH", "MEDIUM", "LOW"]:
            confidence_dist[label] += len(re.findall(rf'"confidence_label":\s*"{label}"', text))

        # Check E4 honesty
        if test_id == "E4":
            e4_esc = re.findall(r'"auto_escalated":\s*(true|false)', text)
            if e4_esc:
                e4_auto_escalated = any(v == "true" for v in e4_esc)
            else:
                e4_auto_escalated = False

        # Check LOCATION escalations
        location_blocks = re.findall(r'"intent":\s*"LOCATION"[\s\S]{0,500}?"auto_escalated":\s*true', text)
        location_escalations += len(location_blocks)

    escalation_rate = escalated_queries / total_queries if total_queries > 0 else 0.0
    total_confidence = sum(confidence_dist.values())

    behavioral = {
        "total_queries": total_queries,
        "escalated_queries": escalated_queries,
        "escalation_rate": round(escalation_rate, 4),
        "feature_activations": {
            "auto_escalation": {"activated": escalated_queries, "total": total_queries},
        },
        "feature_health_cards": [
            {
                "feature": "Z-score confidence",
                "metric": "escalation_rate",
                "target": "15-25%",
                "actual": f"{escalation_rate:.0%}",
                "status": (
                    "IN_TARGET" if 0.15 <= escalation_rate <= 0.25
                    else "ABOVE_TARGET" if escalation_rate > 0.25
                    else "BELOW_TARGET"
                ),
            },
            {
                "feature": "Z-score confidence",
                "metric": "HIGH_distribution",
                "target": ">40%",
                "actual": f"{confidence_dist['HIGH']}/{total_confidence}" if total_confidence > 0 else "N/A",
                "status": (
                    "PASS" if total_confidence > 0 and confidence_dist["HIGH"] / total_confidence > 0.40
                    else "FAIL" if total_confidence > 0
                    else "NO_DATA"
                ),
            },
            {
                "feature": "Medium-tier escalation",
                "metric": "LOCATION_escalations",
                "target": ">0",
                "actual": str(location_escalations),
                "status": "PASS" if location_escalations > 0 else "NO_DATA",
            },
            {
                "feature": "E4 honesty",
                "metric": "auto_escalated",
                "target": "false",
                "actual": str(e4_auto_escalated).lower() if e4_auto_escalated is not None else "N/A",
                "status": "PASS" if e4_auto_escalated is False else "FAIL" if e4_auto_escalated is True else "NO_DATA",
            },
        ],
        "confidence_distribution": confidence_dist,
    }

    BEHAVIORAL_FILE.write_text(json.dumps(behavioral, indent=2) + "\n")
    log.info(f"Behavioral metrics: {escalated_queries}/{total_queries} escalated ({escalation_rate:.0%})")
    log.info(f"Confidence distribution: {confidence_dist}")
    log.info(f"E4 auto_escalated: {e4_auto_escalated}")
    log.info(f"Written to {BEHAVIORAL_FILE}")


def run_computation() -> None:
    """Phase 5: Run viability_compute.py."""
    log.info("=== Phase 5: Computation ===")

    scores_path = SCORES_DIR / "scores.json"
    mapping_path = SANITIZED_DIR / "mapping.json"

    if not scores_path.exists():
        log.error(f"scores.json not found at {scores_path}")
        return
    if not mapping_path.exists():
        log.error(f"mapping.json not found at {mapping_path}")
        return

    cmd = [
        "python3", str(PROJECT_ROOT / "scripts" / "viability_compute.py"),
        str(scores_path),
        str(mapping_path),
        "--rubric", "R3",
        "--flip-rate", "0.25",
    ]

    if BEHAVIORAL_FILE.exists():
        cmd.extend(["--behavioral", str(BEHAVIORAL_FILE)])

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    log.info(result.stdout)
    if result.stderr:
        log.warning(result.stderr)

    results_path = SCORES_DIR / "viability_results.json"
    if results_path.exists():
        log.info(f"Results written to {results_path}")
        # Copy to eval dir root for convenience
        (EVAL_DIR / "viability_results.json").write_text(results_path.read_text())
    else:
        log.error("viability_results.json not generated")


# ---------------------------------------------------------------------------
# Phase 6: Disagreement resolution
# ---------------------------------------------------------------------------

async def run_disagreement_resolution(state: dict) -> None:
    """Check for scorer disagreements and run tiebreaker if needed."""
    log.info("=== Phase 6: Disagreement Resolution ===")

    results_path = SCORES_DIR / "viability_results.json"
    if not results_path.exists():
        log.warning("No viability_results.json — skipping disagreement check")
        return

    results = json.loads(results_path.read_text())
    tests_needing_tiebreaker = []

    for test_result in results.get("per_test", []):
        if test_result.get("disagreements"):
            tests_needing_tiebreaker.append(test_result["test_id"])

    if not tests_needing_tiebreaker:
        log.info("No scorer disagreements detected. Phase 6 complete.")
        return

    log.info(f"Disagreements found in: {tests_needing_tiebreaker}")

    # Run scorer 3 for tests with disagreements
    mapping = json.loads((SANITIZED_DIR / "mapping.json").read_text())

    tasks = []
    for test_id in tests_needing_tiebreaker:
        key = f"{test_id}-scorer3"
        if is_completed(state, "scoring", key):
            continue

        alpha_text = (SANITIZED_DIR / f"{test_id}-Alpha.md").read_text()
        beta_text = (SANITIZED_DIR / f"{test_id}-Beta.md").read_text()

        checklist = get_checklist_text(test_id)
        checklist_section = f"GROUND-TRUTH CHECKLIST:\n{checklist}" if checklist else "No formal checklist."

        prompt = SCORER_PROMPT_TEMPLATE.format(
            checklist_section=checklist_section,
            alpha_transcript=alpha_text,
            beta_transcript=beta_text,
            test_id=test_id,
        )
        tasks.append((test_id, 3, prompt))

    if tasks:
        log.info(f"Running {len(tasks)} tiebreaker scorers")
        # Reuse the scoring logic
        async def score_tiebreaker(test_id: str, scorer_num: int, prompt: str) -> None:
            key = f"{test_id}-scorer{scorer_num}"
            output = await run_agent(prompt, "", key, timeout_s=180)
            if output:
                try:
                    result_text = extract_result_text(output)
                    score_data = json.loads(result_text)
                    score_data["test_id"] = test_id
                    (SCORES_DIR / f"{test_id}-scorer{scorer_num}.json").write_text(
                        json.dumps(score_data, indent=2) + "\n"
                    )
                    mark_completed(state, "scoring", key)
                except (json.JSONDecodeError, TypeError):
                    mark_failed(state, key, "JSON parse failed")

        await asyncio.gather(*(score_tiebreaker(*t) for t in tasks))

        # Re-assemble and re-compute
        run_assembly()
        run_computation()


# ---------------------------------------------------------------------------
# Verification summary
# ---------------------------------------------------------------------------

def print_verification_summary() -> None:
    log.info("\n=== Verification Summary ===")

    # 1. Raw transcripts
    raw_count = len(list(RAW_DIR.glob("*.md")))
    log.info(f"Raw transcripts: {raw_count}/24")

    # 2. Sanitized transcripts
    san_count = len(list(SANITIZED_DIR.glob("*.md")))
    mapping_exists = (SANITIZED_DIR / "mapping.json").exists()
    log.info(f"Sanitized transcripts: {san_count}/24, mapping.json: {'YES' if mapping_exists else 'NO'}")

    # 3. Scorer files
    scorer_count = len(list(SCORES_DIR.glob("*-scorer*.json")))
    scores_exists = (SCORES_DIR / "scores.json").exists()
    log.info(f"Scorer files: {scorer_count}/24, scores.json: {'YES' if scores_exists else 'NO'}")

    # 4. Results
    results_exists = (EVAL_DIR / "viability_results.json").exists()
    behavioral_exists = BEHAVIORAL_FILE.exists()
    log.info(f"viability_results.json: {'YES' if results_exists else 'NO'}")
    log.info(f"behavioral.json: {'YES' if behavioral_exists else 'NO'}")

    if results_exists:
        results = json.loads((EVAL_DIR / "viability_results.json").read_text())
        verdict = results.get("verdict", {}).get("verdict", "UNKNOWN")
        log.info(f"\n*** VERDICT: {verdict} ***")

    if behavioral_exists:
        beh = json.loads(BEHAVIORAL_FILE.read_text())
        rate = beh.get("escalation_rate", 0)
        log.info(f"Escalation rate: {rate:.0%} (gate: 5-55%)")
        if rate < 0.05 or rate > 0.55:
            log.warning("BEHAVIORAL GATE FAILURE")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main() -> None:
    parser = argparse.ArgumentParser(description="V4.3-beta blind evaluation orchestrator")
    parser.add_argument("--resume", action="store_true", help="Resume from checkpoint")
    parser.add_argument("--phase", type=int, default=0, help="Start from specific phase (0-6)")
    parser.add_argument("--skip-verification", action="store_true", help="Skip Phase 3 verification")
    args = parser.parse_args()

    # Ensure directories exist
    for d in [EVAL_DIR, RAW_DIR, SANITIZED_DIR, SCORES_DIR]:
        d.mkdir(parents=True, exist_ok=True)

    _setup_logging()

    if args.resume:
        state = load_state()
    else:
        state = {
            "phase": "preflight",
            "completed": {"exploration": [], "scoring": []},
            "failed": [],
            "started_at": datetime.now(timezone.utc).isoformat(),
        }
        save_state(state)
    start_time = time.time()

    log.info(f"V4.3-beta Blind Evaluation — started at {datetime.now().isoformat()}")
    log.info(f"Resume: {args.resume}, Start phase: {args.phase}")

    try:
        # Phase 0: Pre-flight
        if args.phase <= 0:
            if not run_preflight():
                log.error("Pre-flight failed. Aborting.")
                return
            state["phase"] = "exploration"
            save_state(state)

        # Phase 1: Exploration
        if args.phase <= 1:
            await run_exploration(state)
            state["phase"] = "sanitization"
            save_state(state)

        # Phase 2: Sanitization
        if args.phase <= 2:
            run_sanitization()
            state["phase"] = "verification"
            save_state(state)

        # Phase 3: Verification
        if args.phase <= 3 and not args.skip_verification:
            await run_verification()
            state["phase"] = "scoring"
            save_state(state)

        # Phase 4: Scoring
        if args.phase <= 4:
            await run_scoring(state)
            state["phase"] = "computation"
            save_state(state)

        # Phase 5: Assembly + Behavioral + Computation
        if args.phase <= 5:
            run_assembly()
            run_behavioral_extraction()
            run_computation()
            state["phase"] = "disagreement"
            save_state(state)

        # Phase 6: Disagreement resolution
        if args.phase <= 6:
            await run_disagreement_resolution(state)
            state["phase"] = "complete"
            save_state(state)

        # Summary
        elapsed = time.time() - start_time
        log.info(f"\nTotal runtime: {elapsed / 60:.1f} minutes")
        print_verification_summary()

    except KeyboardInterrupt:
        log.info("\nInterrupted — state saved. Resume with: python3 scripts/run_eval.py --resume")
        save_state(state)
    except Exception as e:
        log.error(f"Fatal error: {e}", exc_info=True)
        save_state(state)
        raise


if __name__ == "__main__":
    asyncio.run(main())
