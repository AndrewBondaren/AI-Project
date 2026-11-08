"""Keep shell commands inside the project's read-only sandbox."""

import json

print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "PermissionRequest",
        "decision": {
            "behavior": "deny",
            "message": "Shell commands must stay read-only. Submit edits with apply_patch.",
        },
    },
}))
