#!/usr/bin/env python3
import json, subprocess, sys

FRIENDLY = {
    "permission_prompt": "Claude needs your permission to continue",
    "idle_prompt": "Claude is waiting for your input",
    "elicitation_dialog": "Claude needs additional input",
}

# These types fire mid-turn while Claude is waiting on the user for something
# other than the next prompt (a permission grant, extra tool input) — that's
# exactly the "blocked" state, so set it deterministically instead of relying
# on the casper-status skill's judgment call. idle_prompt is excluded: it's
# just the ordinary between-turns wait that stop.sh already marks "idle".
BLOCKING_TYPES = {"permission_prompt", "elicitation_dialog"}

def main():
    payload = json.load(sys.stdin)
    notification_type = payload.get("notification_type", "")
    if notification_type == "auth_success":
        return
    if notification_type in BLOCKING_TYPES:
        try:
            subprocess.run(
                ["casper", "status", "set", "blocked"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2,
            )
        except Exception:
            pass
    message = payload.get("message") or FRIENDLY.get(notification_type, "Claude needs your attention")
    try:
        subprocess.run(
            ["casper", "notify", "--message", message],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2,
        )
    except Exception:
        pass

if __name__ == "__main__":
    main()
