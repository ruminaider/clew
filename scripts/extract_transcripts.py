"""Extract agent transcripts from JSONL output files for evaluation.

Reads the raw JSONL conversation logs and produces readable markdown transcripts
that capture the agent's search strategy and final answer.
"""

import json
import sys
from pathlib import Path


AGENT_MAP = {
    # A1: subscription renewal -> PrescriptionFill
    "a743d4d184f27de03": "A1-clew",
    "a8f70b3b8ac593ce3": "A1-grep",
    # A2: new checkout source type
    "aea7f51e2e6f5da23": "A2-clew",
    "a0fda687e0c1cb67d": "A2-grep",
    # A3: pharmacy API errors
    "a29d5297c698c6246": "A3-clew",
    "a8349035b556d5f0d": "A3-grep",
    # A4: order type determination
    "a8223222ad5d045f7": "A4-clew",
    "a5da3807762891c16": "A4-grep",
    # B1: shopify refill function signature change
    "a7cbb9464388b72a1": "B1-clew",
    "a68abd4707257e084": "B1-grep",
    # B2: Order/PrescriptionFill/Prescription relationships
    "a9f0cc0e3c8fd69a3": "B2-clew",
    "ac5c7bed797058e2b": "B2-grep",
    # C1: Django URL patterns
    "ab45fa9a67c6767c3": "C1-clew",
    "a74bb369401d99081": "C1-grep",
    # C2: Stripe API calls
    "ab9761e823d3835e2": "C2-clew",
    "a4268dd56f6b5f6b8": "C2-grep",
    # E1: middleware audit
    "a7219cc82a048c0ad": "E1-clew",
    "a81183234d9eddeea": "E1-grep",
    # E2: Celery task inventory
    "a1289f8c995ff6b50": "E2-clew",
    "a9b5b3f76bde91d97": "E2-grep",
    # E3: model dependency chain
    "ac7559460d05821c1": "E3-clew",
    "adf65e4ca2e5ac6bc": "E3-grep",
    # E4: email confirmation debugging
    "afd7d7eddd34a748b": "E4-clew",
    "a763b822b6b522a8d": "E4-grep",
}

TASKS_DIR = Path("/private/tmp/claude-501/-Users-albertgwo-Repositories-clew/tasks")
OUTPUT_DIR = Path("/Users/albertgwo/Repositories/clew/.clew-eval/v4.2-eval/raw-transcripts")


def extract_transcript_from_messages(messages: list[dict]) -> str:
    """Extract a readable transcript from a list of parsed message dicts.

    Works with the output of `claude -p --output-format json`, where the
    JSON contains a list of message objects with role and content fields.
    Also accepts the top-level JSON object with a "result" field.
    """
    lines: list[str] = []
    tool_call_count = 0

    for msg in messages:
        role = msg.get("role")
        content = msg.get("content")

        if role == "assistant":
            if isinstance(content, str):
                lines.append(f"\n### Assistant\n\n{content}\n")
            elif isinstance(content, list):
                text_parts = []
                tool_parts = []
                for block in content:
                    if block.get("type") == "text":
                        text_parts.append(block["text"])
                    elif block.get("type") == "tool_use":
                        tool_call_count += 1
                        tool_name = block.get("name", "unknown")
                        tool_input = block.get("input", {})
                        tool_parts.append(
                            format_tool_call(tool_name, tool_input, tool_call_count)
                        )
                if text_parts:
                    lines.append(f"\n### Assistant\n\n{''.join(text_parts)}\n")
                if tool_parts:
                    lines.append("\n".join(tool_parts))

        elif role == "user":
            if isinstance(content, str) and not lines:
                lines.append(f"## Task Prompt\n\n{content}\n")
            elif isinstance(content, list):
                for block in content:
                    if block.get("type") == "tool_result":
                        result_content = block.get("content", "")
                        if isinstance(result_content, list):
                            text_items = [
                                item.get("text", "")
                                for item in result_content
                                if item.get("type") == "text"
                            ]
                            result_content = "\n".join(text_items)
                        if len(result_content) > 3000:
                            result_content = result_content[:3000] + "\n... [truncated]"
                        lines.append(
                            f"\n**Tool Result:**\n```\n{result_content}\n```\n"
                        )

    return f"# Transcript\n\nTool calls: {tool_call_count}\n\n" + "\n".join(lines)


def extract_transcript_from_json(json_output: str) -> str:
    """Extract transcript from `claude -p --output-format json` output.

    The JSON output is a single object with a "messages" array (conversation
    turns) and optionally a "result" field with the final text.
    """
    data = json.loads(json_output)

    # claude -p --output-format json returns {"result": "...", "messages": [...]}
    # or just the messages array depending on version
    if isinstance(data, list):
        messages = data
    elif isinstance(data, dict):
        messages = data.get("messages", [])
    else:
        return "# Transcript\n\nTool calls: 0\n\n(empty output)\n"

    return extract_transcript_from_messages(messages)


def extract_transcript(jsonl_path: Path) -> str:
    """Extract a readable transcript from a JSONL agent output file."""
    lines = []
    tool_call_count = 0

    with open(jsonl_path) as f:
        for raw_line in f:
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            try:
                entry = json.loads(raw_line)
            except json.JSONDecodeError:
                continue

            msg = entry.get("message", {})
            role = msg.get("role")
            content = msg.get("content")

            if role == "assistant":
                if isinstance(content, str):
                    lines.append(f"\n### Assistant\n\n{content}\n")
                elif isinstance(content, list):
                    text_parts = []
                    tool_parts = []
                    for block in content:
                        if block.get("type") == "text":
                            text_parts.append(block["text"])
                        elif block.get("type") == "tool_use":
                            tool_call_count += 1
                            tool_name = block.get("name", "unknown")
                            tool_input = block.get("input", {})
                            tool_parts.append(
                                format_tool_call(tool_name, tool_input, tool_call_count)
                            )
                    if text_parts:
                        lines.append(f"\n### Assistant\n\n{''.join(text_parts)}\n")
                    if tool_parts:
                        lines.append("\n".join(tool_parts))

            elif role == "user" and entry.get("userType") == "external":
                # Only include the initial prompt (first user message)
                if isinstance(content, str) and not lines:
                    lines.append(f"## Task Prompt\n\n{content}\n")
                elif isinstance(content, list):
                    # Tool results
                    for block in content:
                        if block.get("type") == "tool_result":
                            result_content = block.get("content", "")
                            if isinstance(result_content, list):
                                text_items = [
                                    item.get("text", "")
                                    for item in result_content
                                    if item.get("type") == "text"
                                ]
                                result_content = "\n".join(text_items)
                            # Truncate very long results
                            if len(result_content) > 3000:
                                result_content = result_content[:3000] + "\n... [truncated]"
                            lines.append(
                                f"\n**Tool Result:**\n```\n{result_content}\n```\n"
                            )

    return f"# Transcript\n\nTool calls: {tool_call_count}\n\n" + "\n".join(lines)


def format_tool_call(name: str, inp: dict, count: int) -> str:
    """Format a tool call for the transcript."""
    if name == "Bash":
        cmd = inp.get("command", "")
        return f"\n**[Tool Call {count}] Bash:**\n```bash\n{cmd}\n```\n"
    elif name == "Read":
        path = inp.get("file_path", "")
        offset = inp.get("offset", "")
        limit = inp.get("limit", "")
        extra = ""
        if offset:
            extra += f" (offset={offset}"
            if limit:
                extra += f", limit={limit}"
            extra += ")"
        return f"\n**[Tool Call {count}] Read:** `{path}`{extra}\n"
    elif name == "Grep":
        pattern = inp.get("pattern", "")
        path = inp.get("path", "")
        mode = inp.get("output_mode", "files_with_matches")
        return f"\n**[Tool Call {count}] Grep:** pattern=`{pattern}` path=`{path}` mode={mode}\n"
    elif name == "Glob":
        pattern = inp.get("pattern", "")
        path = inp.get("path", "")
        return f"\n**[Tool Call {count}] Glob:** pattern=`{pattern}` path=`{path}`\n"
    else:
        return f"\n**[Tool Call {count}] {name}:** {json.dumps(inp)[:500]}\n"


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Skip already-extracted transcripts
    skip = set()
    for existing in OUTPUT_DIR.glob("*.md"):
        skip.add(existing.stem)

    extracted = 0
    skipped = 0
    errors = []

    for agent_id, name in sorted(AGENT_MAP.items(), key=lambda x: x[1]):
        if name in skip:
            print(f"  SKIP {name} (already exists)")
            skipped += 1
            continue

        output_file = TASKS_DIR / f"{agent_id}.output"
        if not output_file.exists():
            errors.append(f"  MISSING {name}: {output_file}")
            continue

        # Resolve symlink
        real_path = output_file.resolve()
        if not real_path.exists():
            errors.append(f"  BROKEN SYMLINK {name}: {real_path}")
            continue

        try:
            transcript = extract_transcript(real_path)
            out_path = OUTPUT_DIR / f"{name}.md"
            out_path.write_text(transcript)
            extracted += 1
            print(f"  OK {name} -> {out_path.name}")
        except Exception as e:
            errors.append(f"  ERROR {name}: {e}")

    print(f"\nExtracted: {extracted}, Skipped: {skipped}, Errors: {len(errors)}")
    if errors:
        print("\nErrors:")
        for e in errors:
            print(e)


if __name__ == "__main__":
    main()
