#!/usr/bin/env python3
"""
Zoom API CLI — meetings, recordings, chat, users, phone.
Uses Server-to-Server OAuth for authentication.

Environment variables:
  ZOOM_ACCOUNT_ID    — Zoom Account ID
  ZOOM_CLIENT_ID     — OAuth Client ID
  ZOOM_CLIENT_SECRET — OAuth Client Secret
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

try:
    import requests
except ImportError:
    print("ERROR: requests not installed. Run: pip3 install requests --break-system-packages", file=sys.stderr)
    sys.exit(1)

BASE_URL = "https://api.zoom.us/v2"
TOKEN_URL = "https://zoom.us/oauth/token"
TOKEN_CACHE = "/tmp/zoom_token.json"
ENV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".env")


def _user_id():
    """Get the user ID (email or 'me') from env."""
    _load_env()
    return os.environ.get("ZOOM_USER_EMAIL", "me")


def _load_env():
    """Load .env file from workspace root."""
    env_path = os.path.normpath(ENV_FILE)
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())


def get_token():
    """Get or refresh Server-to-Server OAuth token."""
    _load_env()
    account_id = os.environ.get("ZOOM_ACCOUNT_ID")
    client_id = os.environ.get("ZOOM_CLIENT_ID")
    client_secret = os.environ.get("ZOOM_CLIENT_SECRET")

    if not all([account_id, client_id, client_secret]):
        print("ERROR: ZOOM_ACCOUNT_ID, ZOOM_CLIENT_ID, and ZOOM_CLIENT_SECRET must be set", file=sys.stderr)
        sys.exit(1)

    # Check cache
    if os.path.exists(TOKEN_CACHE):
        try:
            with open(TOKEN_CACHE) as f:
                cached = json.load(f)
            if cached.get("expires_at", 0) > time.time() + 60:
                return cached["access_token"]
        except (json.JSONDecodeError, KeyError):
            pass

    # Request new token
    resp = requests.post(
        TOKEN_URL,
        params={"grant_type": "account_credentials", "account_id": account_id},
        auth=(client_id, client_secret),
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    data["expires_at"] = time.time() + data.get("expires_in", 3600)

    with open(TOKEN_CACHE, "w") as f:
        json.dump(data, f)

    return data["access_token"]


def api(method, path, **kwargs):
    """Make an authenticated Zoom API request with retry on 429."""
    token = get_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    for attempt in range(3):
        resp = requests.request(method, f"{BASE_URL}{path}", headers=headers, timeout=30, **kwargs)
        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", 5))
            print(f"Rate limited, retrying in {retry_after}s...", file=sys.stderr)
            time.sleep(retry_after)
            continue
        if resp.status_code == 204:
            return None
        if not resp.ok:
            try:
                err = resp.json()
                code = err.get("code", resp.status_code)
                msg = err.get("message", resp.reason)
                print(f"ERROR {code}: {msg}", file=sys.stderr)
                if resp.status_code == 401 or "scope" in msg.lower() or "access token" in msg.lower():
                    print("HINT: Add the required scope to your Zoom Marketplace S2S app at https://marketplace.zoom.us/", file=sys.stderr)
                if resp.status_code == 403 and "not been enabled" in msg.lower():
                    print("HINT: This feature is not enabled on your Zoom account. Check your Zoom plan/settings.", file=sys.stderr)
            except Exception:
                print(f"ERROR {resp.status_code}: {resp.text}", file=sys.stderr)
            sys.exit(1)
        return resp.json()

    print("ERROR: Max retries exceeded", file=sys.stderr)
    sys.exit(1)


def _require(value, name):
    """Exit with a helpful message if a required value is missing."""
    if not value:
        print(f"ERROR: Missing required parameter: {name}", file=sys.stderr)
        sys.exit(1)
    return value


# === Meetings ===

def cmd_meetings_list(args):
    """List upcoming meetings."""
    params = {"type": "upcoming", "page_size": 30}
    data = api("GET", f"/users/{_user_id()}/meetings", params=params)
    meetings = data.get("meetings", [])
    if not meetings:
        print("No upcoming meetings.")
        return
    for m in meetings:
        start = m.get("start_time", "TBD")
        duration = m.get("duration", "?")
        topic = m.get("topic", "Untitled")
        mid = m.get("id", "?")
        print(f"  [{mid}] {topic}")
        print(f"    Start: {start} | Duration: {duration}min")
        join = m.get("join_url", "")
        if join:
            print(f"    Join: {join}")
        print()


def cmd_meetings_get(args):
    """Get meeting details."""
    _require(args.meeting_id, "meeting_id")
    data = api("GET", f"/meetings/{args.meeting_id}")
    print(json.dumps(data, indent=2))


def cmd_meetings_create(args):
    """Schedule a new meeting."""
    _require(args.topic, "--topic")
    _require(args.start, "--start")
    body = {
        "topic": args.topic,
        "type": 2,  # Scheduled
        "start_time": args.start,
        "duration": args.duration,
        "timezone": os.environ.get("TZ", "Asia/Singapore"),
    }
    if args.agenda:
        body["agenda"] = args.agenda
    if args.password:
        body["password"] = args.password

    data = api("POST", f"/users/{_user_id()}/meetings", json=body)
    print(f"Meeting created!")
    print(f"  ID: {data.get('id')}")
    print(f"  Topic: {data.get('topic')}")
    print(f"  Start: {data.get('start_time')}")
    print(f"  Join URL: {data.get('join_url')}")
    print(f"  Password: {data.get('password', 'N/A')}")


def cmd_meetings_delete(args):
    """Delete a meeting."""
    _require(args.meeting_id, "meeting_id")
    api("DELETE", f"/meetings/{args.meeting_id}")
    print(f"Meeting {args.meeting_id} deleted.")


def cmd_meetings_update(args):
    """Update a meeting."""
    _require(args.meeting_id, "meeting_id")
    body = {}
    if args.topic:
        body["topic"] = args.topic
    if args.start:
        body["start_time"] = args.start
    if args.duration:
        body["duration"] = args.duration
    if not body:
        print("Nothing to update.")
        return
    api("PATCH", f"/meetings/{args.meeting_id}", json=body)
    print(f"Meeting {args.meeting_id} updated.")


# === Recordings ===

def cmd_recordings_list(args):
    """List cloud recordings."""
    params = {"page_size": 30}
    if args.from_date:
        params["from"] = args.from_date
    if args.to_date:
        params["to"] = args.to_date
    data = api("GET", f"/users/{_user_id()}/recordings", params=params)
    meetings = data.get("meetings", [])
    if not meetings:
        print("No recordings found.")
        return
    for m in meetings:
        topic = m.get("topic", "Untitled")
        start = m.get("start_time", "?")
        mid = m.get("id", "?")
        files = m.get("recording_files", [])
        print(f"  [{mid}] {topic} ({start})")
        for f in files:
            print(f"    {f.get('recording_type', '?')}: {f.get('download_url', '?')}")
        print()


def cmd_recordings_get(args):
    """Get recording details."""
    data = api("GET", f"/meetings/{args.meeting_id}/recordings")
    print(json.dumps(data, indent=2))


def cmd_recordings_delete(args):
    """Delete a recording."""
    api("DELETE", f"/meetings/{args.meeting_id}/recordings")
    print(f"Recordings for meeting {args.meeting_id} deleted.")


# === Users ===

def cmd_users_me(args):
    """Get my profile."""
    data = api("GET", f"/users/{_user_id()}")
    print(f"Name: {data.get('first_name')} {data.get('last_name')}")
    print(f"Email: {data.get('email')}")
    print(f"Type: {data.get('type')} (1=Basic, 2=Licensed, 3=On-Prem)")
    print(f"PMI: {data.get('pmi')}")
    print(f"Timezone: {data.get('timezone')}")
    print(f"Status: {data.get('status')}")


def cmd_users_list(args):
    """List users (admin)."""
    data = api("GET", "/users", params={"page_size": 30})
    for u in data.get("users", []):
        print(f"  {u.get('email')} — {u.get('first_name')} {u.get('last_name')} (type={u.get('type')})")


# === Chat ===

def cmd_chat_channels(args):
    """List chat channels."""
    data = api("GET", f"/chat/users/{_user_id()}/channels", params={"page_size": 50})
    for ch in data.get("channels", []):
        print(f"  [{ch.get('id')}] {ch.get('name')} (type={ch.get('type')})")


def cmd_chat_messages(args):
    """List messages in a channel."""
    params = {"page_size": 20}
    data = api("GET", f"/chat/users/{_user_id()}/messages", params={**params, "to_channel": args.channel_id})
    for msg in data.get("messages", []):
        sender = msg.get("sender", "?")
        text = msg.get("message", "")
        ts = msg.get("date_time", "?")
        print(f"  [{ts}] {sender}: {text}")


def cmd_chat_send(args):
    """Send a message to a channel."""
    body = {"message": args.message, "to_channel": args.channel_id}
    api("POST", f"/chat/users/{_user_id()}/messages", json=body)
    print(f"Message sent to channel {args.channel_id}.")


def cmd_chat_dm(args):
    """Send a direct message."""
    body = {"message": args.message, "to_contact": args.email}
    api("POST", f"/chat/users/{_user_id()}/messages", json=body)
    print(f"DM sent to {args.email}.")


def cmd_chat_contacts(args):
    """List chat contacts."""
    data = api("GET", "/contacts", params={"page_size": 50, "type": "company"})
    for c in data.get("contacts", []):
        print(f"  {c.get('email', '?')} — {c.get('first_name', '')} {c.get('last_name', '')}")


# === Phone ===

def cmd_phone_calls(args):
    """List call logs."""
    params = {"page_size": 30}
    if args.from_date:
        params["from"] = args.from_date
    if args.to_date:
        params["to"] = args.to_date
    data = api("GET", f"/phone/users/{_user_id()}/call_logs", params=params)
    for c in data.get("call_logs", []):
        direction = c.get("direction", "?")
        number = c.get("caller_number") or c.get("callee_number", "?")
        duration = c.get("duration", "?")
        ts = c.get("date_time", "?")
        print(f"  [{ts}] {direction} {number} ({duration}s)")


# === Main ===

def main():
    parser = argparse.ArgumentParser(description="Zoom API CLI")
    sub = parser.add_subparsers(dest="group", required=True)

    # Meetings
    meetings = sub.add_parser("meetings")
    msub = meetings.add_subparsers(dest="action", required=True)

    msub.add_parser("list")
    p = msub.add_parser("get")
    p.add_argument("meeting_id")
    p = msub.add_parser("create")
    p.add_argument("--topic", required=True)
    p.add_argument("--start", required=True, help="ISO datetime")
    p.add_argument("--duration", type=int, default=30, help="Minutes")
    p.add_argument("--agenda")
    p.add_argument("--password")
    p = msub.add_parser("delete")
    p.add_argument("meeting_id")
    p = msub.add_parser("update")
    p.add_argument("meeting_id")
    p.add_argument("--topic")
    p.add_argument("--start")
    p.add_argument("--duration", type=int)

    # Recordings
    recordings = sub.add_parser("recordings")
    rsub = recordings.add_subparsers(dest="action", required=True)
    p = rsub.add_parser("list")
    p.add_argument("--from", dest="from_date")
    p.add_argument("--to", dest="to_date")
    p = rsub.add_parser("get")
    p.add_argument("meeting_id")
    p = rsub.add_parser("delete")
    p.add_argument("meeting_id")

    # Users
    users = sub.add_parser("users")
    usub = users.add_subparsers(dest="action", required=True)
    usub.add_parser("me")
    usub.add_parser("list")

    # Chat
    chat = sub.add_parser("chat")
    csub = chat.add_subparsers(dest="action", required=True)
    csub.add_parser("channels")
    p = csub.add_parser("messages")
    p.add_argument("channel_id")
    p = csub.add_parser("send")
    p.add_argument("channel_id")
    p.add_argument("message")
    p = csub.add_parser("dm")
    p.add_argument("email")
    p.add_argument("message")
    csub.add_parser("contacts")

    # Phone
    phone = sub.add_parser("phone")
    psub = phone.add_subparsers(dest="action", required=True)
    p = psub.add_parser("calls")
    p.add_argument("--from", dest="from_date")
    p.add_argument("--to", dest="to_date")

    args = parser.parse_args()

    cmd_map = {
        ("meetings", "list"): cmd_meetings_list,
        ("meetings", "get"): cmd_meetings_get,
        ("meetings", "create"): cmd_meetings_create,
        ("meetings", "delete"): cmd_meetings_delete,
        ("meetings", "update"): cmd_meetings_update,
        ("recordings", "list"): cmd_recordings_list,
        ("recordings", "get"): cmd_recordings_get,
        ("recordings", "delete"): cmd_recordings_delete,
        ("users", "me"): cmd_users_me,
        ("users", "list"): cmd_users_list,
        ("chat", "channels"): cmd_chat_channels,
        ("chat", "messages"): cmd_chat_messages,
        ("chat", "send"): cmd_chat_send,
        ("chat", "dm"): cmd_chat_dm,
        ("chat", "contacts"): cmd_chat_contacts,
        ("phone", "calls"): cmd_phone_calls,
    }

    func = cmd_map.get((args.group, args.action))
    if func:
        func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
