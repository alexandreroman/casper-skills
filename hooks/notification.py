#!/usr/bin/env python3
import json, subprocess, sys

FRIENDLY = {
    "permission_prompt": "Claude needs your permission to continue",
    "idle_prompt": "Claude is waiting for your input",
    "elicitation_dialog": "Claude needs additional input",
}

def main():
    payload = json.load(sys.stdin)
    notification_type = payload.get("notification_type", "")
    if notification_type == "auth_success":
        return
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
