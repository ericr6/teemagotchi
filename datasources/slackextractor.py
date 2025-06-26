#!/usr/bin/env python3
import os, json, time, datetime as dt
import sys
from pathlib import Path
import subprocess
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from dotenv import load_dotenv

load_dotenv()

TOKEN        = os.environ["SLACK_BOT_TOKEN"]
CHANNELS_TXT = sys.argv[1]        # plain-text list of channel names or IDs
HISTORY_FILE = sys.argv[2]
POLL_EVERY   = 60 * 60            # seconds between runs (10 min)
STATE_DIR    = Path(".state")     # stores <CID>.ts   (last seen timestamp)
STATE_DIR.mkdir(exist_ok=True)
LOOKBACK_MINUTES = 60 * 24 * 30

client = WebClient(token=TOKEN)

# ── helpers ────────────────────────────────────────────────────────────────
def read_channel_whitelist(path) -> list[str]:
    """Return a list of names/IDs from file (ignore blank / comment lines)."""
    with open(path) as f:
        return [l.strip().lstrip("#") for l in f if l.strip()]

def load_ts(cid: str) -> float:
    """
    Return the last stored Slack timestamp for this channel.

    • If the state file exists → read & parse it.
    • If not (first execution) → start at *now - LOOKBACK* so we only
      download recent history.
    """
    path = STATE_DIR / f"{cid}.ts"

    if path.exists():
        try:
            return float(path.read_text().strip())
        except ValueError:
            # Corrupted file: treat as first run
            pass

    # First run → look back N minutes
    return time.time() - LOOKBACK_MINUTES * 60

def save_ts(cid: str, ts: float) -> None:
    if ts and ts == ts and ts > 0:      # not NaN, not negative
        (STATE_DIR / f"{cid}.ts").write_text(f"{ts:.6f}")

def resolve_channels(requested: list[str]) -> dict[str, str | None]:
    """
    Build a mapping <whitelist entry> -> <channel ID or None> limited to
    the channels *you* have access to (uses users.conversations).

    Entries accepted in channels.txt:
      - public / private channel names  (e.g. general, random)
      - any channel ID                  (C…, G…, D…)
      - a user ID for a direct message  (U…)
    """
    mapping: dict[str, str | None] = {}
    name_or_uid_to_id: dict[str, str] = {}

    cursor = None
    while True:
        resp = client.users_conversations(
            types="public_channel,private_channel,mpim,im",
            limit=200,
            cursor=cursor,
        )
        for ch in resp["channels"]:
            cid = ch["id"]
            # Map the channel ID to itself
            name_or_uid_to_id[cid] = cid

            # Public / private channels + MPIM have a "name"
            if "name" in ch:
                name_or_uid_to_id[ch["name"]] = cid

            # Direct messages: map the teammate's user-ID
            if ch.get("is_im") and "user" in ch:
                name_or_uid_to_id[ch["user"]] = cid

        cursor = resp.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break

    # Build the final whitelist → id map
    for entry in requested:
        mapping[entry] = name_or_uid_to_id.get(entry)

    return mapping


def fetch_history(cid: str, oldest: float | None) -> list[dict]:
    """
    Fetch messages more recent than `oldest`.

    If `oldest` is falsy (0 or None) we omit the parameter entirely to
    avoid Slack's `invalid_ts_oldest` error on first run.
    """
    cursor, collected = None, []
    while True:
        params = dict(channel=cid, limit=15, cursor=cursor)
        if oldest:                         # ← only include when > 0
            params["oldest"] = f"{oldest:.6f}"

        try:
            resp = client.conversations_history(**params)
        except SlackApiError as e:
            if e.response["error"] == "ratelimited":
                wait = int(e.response.headers.get("Retry-After", 60))
                print(f"⏳ rate-limited on {cid} — sleeping {wait}s")
                time.sleep(wait + 1)
                continue
            raise                         # propagate other errors

        collected.extend(resp["messages"])
        cursor = resp.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break
    return collected

# ── iExec ────────────────────────────────────────────────────────────────
def publish_to_iexec(file_path: str) -> str | None:
    """
    Protect <file_path> using iExec DataProtector and return the dataset address.
    """

    script_path = Path("datasources") / "protectData.js" 
    try:
        result = subprocess.run(
            ['node', script_path, file_path],
            capture_output=True,
            text=True,
            check=True
        )
        address = result.stdout.strip()
        print(f"📦  New iExec dataset deployed → {address}")
        return address
    except subprocess.CalledProcessError as e:
        print("❌ Error during DataProtector execution:", e.stderr)
        return None

# ── main loop ──────────────────────────────────────────────────────────────
def run_once(ch_map: dict[str, str | None]) -> None:
    now = time.time()
    with open(HISTORY_FILE, "a") as out:
        for raw, cid in ch_map.items():
            if cid is None:
                print(f"❌ {raw}: not found or you are not a member")
                continue

            oldest = load_ts(cid)
            latest = oldest
            msgs   = fetch_history(cid, oldest)

            for m in msgs:
                json.dump({"cid": cid, **m}, out)
                out.write("\n")
                latest = max(latest, float(m["ts"]))

            if latest > oldest:
                save_ts(cid, latest)
            print(f"✅ {raw}: +{len(msgs)} msgs (up to {dt.datetime.utcfromtimestamp(latest)})")

if __name__ == "__main__":
    whitelist   = read_channel_whitelist(CHANNELS_TXT)
    channel_map = resolve_channels(whitelist)

    while True:
        run_once(channel_map)
        publish_to_iexec(HISTORY_FILE)
        print("Done, sleeping")
        time.sleep(POLL_EVERY)