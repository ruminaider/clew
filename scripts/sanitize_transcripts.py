"""Sanitize and blind agent transcripts for evaluation.

Phase 2 of the viability evaluation pipeline:
1. Strips task prompts (which reveal tool identity)
2. Normalizes tool call headers and commands to generic form
3. Removes metadata fields from JSON results (score, confidence, intent, etc.)
4. Randomly assigns Alpha/Beta labels
5. Saves blinding key for later de-anonymization

Usage:
    python3 scripts/sanitize_transcripts.py <raw_dir> <output_dir> [--tests A1,A2,...]
"""

import json
import random
import re
import sys
from pathlib import Path


def strip_task_prompt(text: str) -> str:
    """Remove the task prompt section (reveals tool identity)."""
    # Extract just the TASK line for context
    task_match = re.search(r'TASK:\n(.+?)(?:\n\n|\nINSTRUCTIONS:)', text, re.DOTALL)
    task_text = task_match.group(1).strip() if task_match else ""

    # Remove everything from "## Task Prompt" to the first "### Assistant"
    text = re.sub(
        r'## Task Prompt\n.*?(?=### Assistant)',
        f'## Task\n\n{task_text}\n\n---\n\n',
        text,
        flags=re.DOTALL,
    )
    return text


def strip_metadata_fields(text: str) -> str:
    """Remove identifying metadata fields from JSON blocks."""
    fields_to_remove = [
        "score", "importance_score", "confidence", "confidence_label",
        "suggestion_type", "mode_used", "auto_escalated", "intent",
        "query_enhanced", "total_candidates", "chunk_type", "enriched",
        "collection", "source", "mode", "is_test",
    ]
    for field in fields_to_remove:
        # "field": value, (with trailing comma)
        pattern = r'\s*"' + field + r'":\s*[^\n,\]})]+,?\s*\n'
        text = re.sub(pattern, '\n', text)

    # Clean up trailing commas before closing braces/brackets
    text = re.sub(r',(\s*[}\]])', r'\1', text)

    # Remove empty lines in JSON blocks
    text = re.sub(r'\n\n+(\s*["}{\[\]])', r'\n\1', text)

    return text


def normalize_paths(text: str) -> str:
    """Strip absolute paths to relative."""
    text = text.replace('/Users/albertgwo/Work/evvy/', '')
    text = text.replace('/Users/albertgwo/Repositories/clew/', '')
    text = text.replace('/Users/albertgwo/Work/evvy', '.')
    text = text.replace('/Users/albertgwo/Repositories/clew', '.')
    return text


def final_cleanup(text: str) -> str:
    """Final pass to catch any remaining tool identity leaks."""
    # Catch any remaining **[Tool Call N] Grep:** or **[Tool Call N] Glob:** headers
    text = re.sub(
        r'\*\*\[Tool Call (\d+)\] Grep:\*\*([^\n]*)',
        r'**[Tool Call \1] Search:**\2',
        text,
    )
    text = re.sub(
        r'\*\*\[Tool Call (\d+)\] Glob:\*\*([^\n]*)',
        r'**[Tool Call \1] Find:**\2',
        text,
    )

    # Catch "clew" in remaining contexts (error messages, paths, etc.)
    # But not inside words like "clew-eval"
    text = re.sub(r'\bclew\b(?!-eval)', 'the tool', text, flags=re.IGNORECASE)

    return text


def sanitize_code_blocks(text: str) -> str:
    """Sanitize grep/rg/find commands inside code blocks."""
    def replace_code_block(m):
        content = m.group(1)
        # Replace grep/rg commands with search()
        content = re.sub(r'grep\s+-[a-zA-Z]+\s+"([^"]+)"[^\n]*', r'search("\1")', content)
        content = re.sub(r"grep\s+-[a-zA-Z]+\s+'([^']+)'[^\n]*", r'search("\1")', content)
        content = re.sub(r'grep\s+-[a-zA-Z]+\s+(\S+)[^\n]*', r'search("\1")', content)
        content = re.sub(r'grep\s+"([^"]+)"[^\n]*', r'search("\1")', content)
        content = re.sub(r"grep\s+'([^']+)'[^\n]*", r'search("\1")', content)
        content = re.sub(r'\brg\s+"([^"]+)"[^\n]*', r'search("\1")', content)
        content = re.sub(r"\brg\s+'([^']+)'[^\n]*", r'search("\1")', content)
        content = re.sub(r'\brg\s+(\S+)\s+--[^\n]*', r'search("\1")', content)
        # Replace find commands
        content = re.sub(r'find\s+\.\s+-name\s+"([^"]+)"[^\n]*', r'find_files("\1")', content)
        content = re.sub(r'find\s+\.\s+-name\s+(\S+)[^\n]*', r'find_files("\1")', content)
        return f'```\n{content}\n```'

    text = re.sub(r'```(?:bash)?\n(.*?)\n```', replace_code_block, text, flags=re.DOTALL)
    return text


def strip_prose_leaks(text: str) -> str:
    """Remove tool-identifying language from assistant prose."""
    # Score/confidence mentions
    text = re.sub(r'\s*\(score:?\s*[\d.]+\)', '', text)
    text = re.sub(r'\s*\(relevance:?\s*[\d.]+\)', '', text)
    text = re.sub(r'\s*\(confidence:?\s*[\d.]+\)', '', text)
    text = re.sub(r'low confidence \([\d.]+\)', 'low confidence', text)
    text = re.sub(r'high confidence \([\d.]+\)', 'high confidence', text)

    # Mode mentions
    text = re.sub(r'\bexhaustive mode\b', 'search mode', text)
    text = re.sub(r'\bsemantic search\b', 'search', text, flags=re.IGNORECASE)
    text = re.sub(r'\bsemantic results?\b', 'search results', text, flags=re.IGNORECASE)

    # Tool name mentions in prose (not inside code blocks or tool headers)
    text = re.sub(r'\bripgrep\b', 'search', text, flags=re.IGNORECASE)
    text = re.sub(r'\bgrep tool\b', 'search tool', text, flags=re.IGNORECASE)
    text = re.sub(r"\bI'll grep\b", "I'll search", text, flags=re.IGNORECASE)
    text = re.sub(r"\blet me grep\b", "let me search", text, flags=re.IGNORECASE)
    text = re.sub(r"\blet's grep\b", "let's search", text, flags=re.IGNORECASE)
    text = re.sub(r'\busing grep\b', 'using search', text, flags=re.IGNORECASE)
    text = re.sub(r'\bwith grep\b', 'with search', text, flags=re.IGNORECASE)
    text = re.sub(r'\bvia grep\b', 'via search', text, flags=re.IGNORECASE)
    text = re.sub(r'\ba grep\b', 'a search', text, flags=re.IGNORECASE)
    text = re.sub(r'\bthe Grep\b', 'the search', text, flags=re.IGNORECASE)
    text = re.sub(r'\bthe Glob\b', 'the file finder', text, flags=re.IGNORECASE)
    text = re.sub(r'\bGrep\b(?!:)', 'search', text)
    text = re.sub(r'\bGlob\b(?!:)', 'file search', text)

    return text


def sanitize_clew_transcript(text: str) -> str:
    """Sanitize a clew-tool transcript."""
    text = strip_task_prompt(text)

    # Remove "Tool calls: N" header
    text = re.sub(r'^Tool calls: \d+\n\n', '', text, flags=re.MULTILINE)

    # Normalize **[Tool Call N] Bash:** to **[Tool Call N] Command:**
    # and sanitize the command inside
    def replace_bash_block(m):
        num = m.group(1)
        cmd = m.group(2)
        # Sanitize clew commands
        cmd = re.sub(
            r'clew search\s+"([^"]+)"[^\n]*',
            r'search("\1")',
            cmd,
        )
        cmd = re.sub(
            r'clew trace\s+"([^"]+)"[^\n]*',
            r'search("code related to \1")',
            cmd,
        )
        cmd = re.sub(
            r'clew trace\s+(\S+)[^\n]*',
            r'search("code related to \1")',
            cmd,
        )
        # Remove 2>/dev/null | head patterns
        cmd = re.sub(r'\s*2>/dev/null\s*', ' ', cmd)
        cmd = re.sub(r'\s*\|\s*head\s+-\d+', '', cmd)
        cmd = re.sub(r'\s*\|\s*python3\s+-c\s+.*', '', cmd)
        cmd = cmd.strip()
        return f'**[Tool Call {num}] Command:**\n```\n{cmd}\n```'

    text = re.sub(
        r'\*\*\[Tool Call (\d+)\] Bash:\*\*\n```bash\n(.*?)\n```',
        replace_bash_block,
        text,
        flags=re.DOTALL,
    )

    # Normalize Read tool calls (already in good format)
    text = re.sub(
        r'\*\*\[Tool Call (\d+)\] Read:\*\*',
        r'**[Tool Call \1] Read:**',
        text,
    )

    # Normalize context -> related
    text = re.sub(r'"context":', '"related":', text)

    # Remove clew mentions in prose
    text = re.sub(r'\bclew search\b', 'search', text, flags=re.IGNORECASE)
    text = re.sub(r'\bclew trace\b', 'search', text, flags=re.IGNORECASE)
    text = re.sub(r'\bclew\b', 'the search tool', text, flags=re.IGNORECASE)

    text = strip_metadata_fields(text)
    text = normalize_paths(text)
    text = sanitize_code_blocks(text)
    text = strip_prose_leaks(text)
    text = final_cleanup(text)

    return text


def sanitize_grep_transcript(text: str) -> str:
    """Sanitize a grep-tool transcript."""
    text = strip_task_prompt(text)

    # Remove "Tool calls: N" header
    text = re.sub(r'^Tool calls: \d+\n\n', '', text, flags=re.MULTILINE)

    # Normalize **[Tool Call N] Grep:** -> **[Tool Call N] Search:**
    # Handle various formats
    text = re.sub(
        r'\*\*\[Tool Call (\d+)\] Grep:\*\* pattern=`([^`]+)` path=`([^`]*)` mode=\S+',
        r'**[Tool Call \1] Search:** `\2`',
        text,
    )
    text = re.sub(
        r'\*\*\[Tool Call (\d+)\] Grep:\*\*([^\n]*)',
        r'**[Tool Call \1] Search:**\2',
        text,
    )

    # Normalize **[Tool Call N] Glob:** -> **[Tool Call N] Find:**
    text = re.sub(
        r'\*\*\[Tool Call (\d+)\] Glob:\*\* pattern=`([^`]+)` path=`([^`]*)`',
        r'**[Tool Call \1] Find:** `\2`',
        text,
    )
    text = re.sub(
        r'\*\*\[Tool Call (\d+)\] Glob:\*\*([^\n]*)',
        r'**[Tool Call \1] Find:**\2',
        text,
    )

    # Normalize Read (already fine)
    text = re.sub(
        r'\*\*\[Tool Call (\d+)\] Read:\*\*',
        r'**[Tool Call \1] Read:**',
        text,
    )

    text = strip_metadata_fields(text)
    text = normalize_paths(text)
    text = sanitize_code_blocks(text)
    text = strip_prose_leaks(text)

    return text


def process_test(
    test_id: str,
    raw_dir: Path,
    output_dir: Path,
    seed: int,
) -> dict:
    """Process a single test: sanitize both transcripts and assign labels."""
    clew_path = raw_dir / f"{test_id}-clew.md"
    grep_path = raw_dir / f"{test_id}-grep.md"

    if not clew_path.exists() or not grep_path.exists():
        print(f"  SKIP {test_id}: missing raw transcript(s)")
        return {}

    clew_text = clew_path.read_text()
    grep_text = grep_path.read_text()

    # Sanitize
    sanitized_clew = sanitize_clew_transcript(clew_text)
    sanitized_grep = sanitize_grep_transcript(grep_text)

    # Random Alpha/Beta assignment
    rng = random.Random(seed)
    if rng.random() < 0.5:
        alpha_text, alpha_tool = sanitized_clew, "clew"
        beta_text, beta_tool = sanitized_grep, "grep"
    else:
        alpha_text, alpha_tool = sanitized_grep, "grep"
        beta_text, beta_tool = sanitized_clew, "clew"

    # Add agent label headers
    alpha_text = alpha_text.replace("# Transcript", f"# Agent Alpha — Test {test_id}")
    beta_text = beta_text.replace("# Transcript", f"# Agent Beta — Test {test_id}")

    # Write files
    (output_dir / f"{test_id}-Alpha.md").write_text(alpha_text)
    (output_dir / f"{test_id}-Beta.md").write_text(beta_text)

    mapping = {"alpha": alpha_tool, "beta": beta_tool}
    print(f"  OK {test_id}: Alpha={alpha_tool}, Beta={beta_tool}")
    return {test_id: mapping}


def main():
    raw_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".clew-eval/v4.3-beta/raw-transcripts")
    output_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(".clew-eval/v4.3-beta/sanitized-transcripts")

    # Optional: specify which tests to process
    if len(sys.argv) > 3 and sys.argv[3] == "--tests":
        tests = sys.argv[4].split(",")
    else:
        tests = sorted(set(
            p.stem.rsplit("-", 1)[0]
            for p in raw_dir.glob("*-clew.md")
        ))

    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Sanitizing {len(tests)} tests: {', '.join(tests)}")
    print(f"Raw dir: {raw_dir}")
    print(f"Output dir: {output_dir}")
    print()

    # Fixed seed for reproducibility
    master_seed = 20260223
    all_mappings = {}

    for i, test_id in enumerate(tests):
        result = process_test(test_id, raw_dir, output_dir, seed=master_seed + i)
        all_mappings.update(result)

    # Write consolidated mapping
    consolidated_path = output_dir / "mapping.json"
    consolidated_path.write_text(json.dumps(all_mappings, indent=2) + "\n")
    print(f"\nConsolidated mapping written to {consolidated_path}")
    print(f"Total tests sanitized: {len(all_mappings)}")


if __name__ == "__main__":
    main()
