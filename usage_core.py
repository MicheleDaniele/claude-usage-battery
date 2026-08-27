"""
usage_core.py — Shared Mac/Windows core for Claude Usage Battery.

Reads the local Claude Code login token, calls the official usage endpoint
(the same one used by the /usage command), and returns the remaining percentage
for the 5-hour and weekly windows.

The token never leaves your machine: it is only used to talk to
api.anthropic.com, exactly as Claude Code itself does.
"""

import json
import os
import platform
import subprocess
import time
from datetime import datetime, timezone

import requests

# --- Constants discovered from the Claude Code CLI --------------------------
USAGE_URL = "https://api.anthropic.com/api/oauth/usage"
TOKEN_URL = "https://platform.claude.com/v1/oauth/token"
CLIENT_ID = "9d1c250a-e61b-44d9-88ed-5944d1962f5e"
OAUTH_BETA = "oauth-2025-04-20"
KEYCHAIN_SERVICE = "Claude Code-credentials"
CRED_FILE = os.path.expanduser("~/.claude/.credentials.json")

IS_MAC = platform.system() == "Darwin"


class AuthError(Exception):
    """No valid login found (user must log in to Claude Code)."""


# --- Credential read / write ------------------------------------------------
def _read_raw_credentials() -> dict:
    """
    Return the {"claudeAiOauth": {...}} dict from the Keychain (macOS)
    or from ~/.claude/.credentials.json (Windows/Linux, and macOS fallback).
    """
    # 1) macOS Keychain
    if IS_MAC:
        try:
            out = subprocess.run(
                ["security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-w"],
                capture_output=True, text=True, timeout=10,
            )
            if out.returncode == 0 and out.stdout.strip():
                return json.loads(out.stdout.strip())
        except Exception:
            pass  # fall through to file

    # 2) Credentials file (Windows/Linux, or macOS if Keychain is unavailable)
    if os.path.exists(CRED_FILE):
        with open(CRED_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    raise AuthError(
        "Claude credentials not found. Log in to Claude Code at least once."
    )


def _write_raw_credentials(data: dict) -> None:
    """Persist updated credentials (after a token refresh)."""
    payload = json.dumps(data)
    if IS_MAC:
        try:
            # -U updates the entry if it already exists.
            subprocess.run(
                ["security", "add-generic-password", "-U",
                 "-s", KEYCHAIN_SERVICE, "-a", KEYCHAIN_SERVICE, "-w", payload],
                capture_output=True, text=True, timeout=10,
            )
            return
        except Exception:
            pass
    # File fallback (Windows/Linux)
    os.makedirs(os.path.dirname(CRED_FILE), exist_ok=True)
    with open(CRED_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f)
    try:
        os.chmod(CRED_FILE, 0o600)
    except Exception:
        pass


def _refresh_token(raw: dict) -> dict:
    """Obtain a new access token using the OAuth refresh token."""
    oauth = raw.get("claudeAiOauth", {})
    refresh = oauth.get("refreshToken")
    if not refresh:
        raise AuthError("Refresh token missing: please log in to Claude Code again.")

    resp = requests.post(
        TOKEN_URL,
        json={
            "grant_type": "refresh_token",
            "refresh_token": refresh,
            "client_id": CLIENT_ID,
        },
        headers={"Content-Type": "application/json"},
        timeout=15,
    )
    if not resp.ok:
        raise AuthError(f"Token refresh failed ({resp.status_code}). Please log in again.")
    tok = resp.json()

    oauth["accessToken"] = tok["access_token"]
    if tok.get("refresh_token"):
        oauth["refreshToken"] = tok["refresh_token"]
    if tok.get("expires_in"):
        oauth["expiresAt"] = int(time.time() * 1000) + int(tok["expires_in"]) * 1000
    raw["claudeAiOauth"] = oauth
    _write_raw_credentials(raw)
    return raw


def _valid_access_token() -> str:
    """Return a valid access token, refreshing it if expired or about to expire."""
    raw = _read_raw_credentials()
    oauth = raw.get("claudeAiOauth", {})
    token = oauth.get("accessToken")
    expires_at = oauth.get("expiresAt", 0)  # milliseconds

    # Refresh if missing or expiring within 60 s.
    if not token or (expires_at and expires_at < time.time() * 1000 + 60_000):
        raw = _refresh_token(raw)
        token = raw["claudeAiOauth"]["accessToken"]
    return token


# --- Usage endpoint call ----------------------------------------------------
def _get_usage(token: str) -> dict:
    resp = requests.get(
        USAGE_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "anthropic-beta": OAUTH_BETA,
            "anthropic-version": "2023-06-01",
        },
        timeout=10,
    )
    return resp


def _parse_reset(resets_at) -> datetime | None:
    """resets_at can be an ISO 8601 string or a Unix timestamp (seconds)."""
    if not resets_at:
        return None
    if isinstance(resets_at, (int, float)):
        return datetime.fromtimestamp(int(resets_at), tz=timezone.utc)
    try:
        return datetime.fromisoformat(str(resets_at).replace("Z", "+00:00"))
    except ValueError:
        return None


def _window(obj: dict | None) -> dict | None:
    """Normalize a {utilization, resets_at} window into percentage / datetime."""
    if not obj:
        return None
    # utilization is already a 0..100 percentage (e.g. 79.0 = 79 % used).
    util = float(obj.get("utilization", 0.0))
    used_pct = max(0, min(100, round(util)))
    remaining_pct = 100 - used_pct
    reset_dt = _parse_reset(obj.get("resets_at"))
    return {"used_pct": used_pct, "remaining_pct": remaining_pct, "reset": reset_dt}


def fetch_status() -> dict:
    """
    Return:
      {
        "five_hour":  {"used_pct", "remaining_pct", "reset"} | None,
        "seven_day":  {...} | None,
        "updated": datetime,
      }
    Raises AuthError if no valid login is available.
    """
    token = _valid_access_token()
    resp = _get_usage(token)

    # A 401 can happen if the token just expired: refresh and retry once.
    if resp.status_code == 401:
        raw = _refresh_token(_read_raw_credentials())
        resp = _get_usage(raw["claudeAiOauth"]["accessToken"])

    resp.raise_for_status()
    data = resp.json()

    return {
        "five_hour": _window(data.get("five_hour")),
        "seven_day": _window(data.get("seven_day")),
        "updated": datetime.now(timezone.utc),
    }


# --- Formatting helpers ------------------------------------------------------
def human_reset(reset_dt) -> str:
    """Return a human-readable time until reset, e.g. 'in 2h 13m' or 'now'."""
    if reset_dt is None:
        return "n/a"
    delta = (reset_dt - datetime.now(timezone.utc)).total_seconds()
    if delta <= 0:
        return "now"
    h = int(delta // 3600)
    m = int((delta % 3600) // 60)
    if h > 24:
        d = h // 24
        h = h % 24
        return f"in {d}d {h}h"
    if h:
        return f"in {h}h {m:02d}m"
    return f"in {m}m"


def level_color(remaining_pct: int) -> tuple:
    """Return an RGBA color based on remaining charge (green / orange / red)."""
    if remaining_pct >= 50:
        return (52, 199, 89, 255)     # green
    if remaining_pct >= 20:
        return (255, 159, 10, 255)    # orange
    return (255, 59, 48, 255)         # red
