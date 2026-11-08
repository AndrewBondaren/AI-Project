"""Reject explicit patch CLI calls in shell tool input before execution."""

import json
import re
import sys


def main() -> None:
    try:
        command = json.load(sys.stdin)["tool_input"]["command"]
        if not isinstance(command, str) or not command.strip():
            raise ValueError("missing shell command")
    except (ValueError, KeyError, TypeError):
        reason = "Cannot inspect shell command."
    else:
        if not re.search(
            r"--codex-run-as-apply-patch|(?<![\w-])(?:apply_patch|applypatch)(?![\w-])",
            command,
            re.IGNORECASE,
        ):
            return
        reason = "Submit the edit through the built-in apply_patch tool."

    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason,
    }}))


if __name__ == "__main__":
    main()
