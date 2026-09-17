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
import re
import subprocess
import tempfile
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
# Stores the user-preferred keychain service (None = auto-detect)
ACCOUNT_PREF_FILE = os.path.join(tempfile.gettempdir(), "claude_battery_account")

IS_MAC = platform.system() == "Darwin"

# Tracks which keychain service was last used (for consistent write-back)
_active_service: str = KEYCHAIN_SERVICE


class AuthError(Exception):
    """No valid login found (user must log in to Claude Code)."""


# --- Multi-account helpers --------------------------------------------------
def _list_keychain_services() -> list[str]:
    """Return all 'Claude Code-credentials*' service names found in the Keychain."""
    if not IS_MAC:
        return [KEYCHAIN_SERVICE]
    try:
        out = subprocess.run(
            ["security", "dump-keychain"],
            capture_output=True, text=True, timeout=10,
        )
        seen: list[str] = []
        for line in out.stdout.splitlines():
            m = re.search(r'"svce"<blob>="(Claude Code-credentials[^"]*)"', line)
            if m and m.group(1) not in seen:
                seen.append(m.group(1))
        if not seen:
            return [KEYCHAIN_SERVICE]
        others = sorted(s for s in seen if s != KEYCHAIN_SERVICE)
        return ([KEYCHAIN_SERVICE] if KEYCHAIN_SERVICE in seen else []) + others
    except Exception:
        return [KEYCHAIN_SERVICE]


def get_preferred_service() -> str | None:
    """Return the user-selected keychain service, or None for auto-detect."""
    try:
        with open(ACCOUNT_PREF_FILE) as f:
            return f.read().strip() or None
    except OSError:
        return None


def set_preferred_service(service: str | None) -> None:
    """Persist the preferred keychain service (None = auto-detect)."""
    if service is None:
        try:
            os.remove(ACCOUNT_PREF_FILE)
        except OSError:
            pass
    else:
        with open(ACCOUNT_PREF_FILE, "w") as f:
            f.write(service)


def service_label(service: str) -> str:
    """Return a human-readable label for a keychain service name."""
    try:
        out = subprocess.run(
            ["security", "find-generic-password", "-s", service, "-w"],
            capture_output=True, text=True, timeout=5,
        )
        if out.returncode == 0 and out.stdout.strip():
            d = json.loads(out.stdout.strip())
            sub = d.get("claudeAiOauth", {}).get("subscriptionType", "")
            if sub:
                return sub.replace("_", " ").title()
    except Exception:
        pass
    suffix = service.removeprefix(KEYCHAIN_SERVICE).lstrip("-")
    return suffix[:8] if suffix else "Default"


# --- Credential read / write ------------------------------------------------
def _read_raw_credentials(service: str | None = None) -> dict:
    """
    Return the {"claudeAiOauth": {...}} dict for the given service.

    If service is None: auto-detects, preferring entries with a valid token.
    On macOS reads from the Keychain; falls back to the credentials file.
    """
    global _active_service

    if IS_MAC:
        if service:
            candidates = [service]
        else:
            pref = get_preferred_service()
            candidates = [pref] if pref else _list_keychain_services()

        valid: list[tuple[str, dict]] = []
        expired: list[tuple[str, dict]] = []
        for svc in candidates:
            try:
                out = subprocess.run(
                    ["security", "find-generic-password", "-s", svc, "-w"],
                    capture_output=True, text=True, timeout=10,
                )
                if out.returncode != 0 or not out.stdout.strip():
                    continue
                data = json.loads(out.stdout.strip())
                exp = data.get("claudeAiOauth", {}).get("expiresAt", 0)
                if exp > time.time() * 1000 + 60_000:
                    valid.append((svc, data))
                else:
                    expired.append((svc, data))
            except Exception:
                continue

        chosen = valid or expired
        if chosen:
            _active_service = chosen[0][0]
            return chosen[0][1]

    # Credentials file fallback (Windows/Linux, or macOS if Keychain unavailable)
    if os.path.exists(CRED_FILE):
        _active_service = "file"
        with open(CRED_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    raise AuthError(
        "Claude credentials not found. Log in to Claude Code at least once."
    )


def _write_raw_credentials(data: dict) -> None:
    """Persist updated credentials — only used on Windows/Linux (file-based storage).
    On macOS the Keychain is managed exclusively by Claude Code; this plugin
    only reads from it and refreshes tokens in-memory to avoid corrupting entries."""
    if IS_MAC:
        return  # never touch the macOS Keychain
    os.makedirs(os.path.dirname(CRED_FILE), exist_ok=True)
    with open(CRED_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f)
    try:
        os.chmod(CRED_FILE, 0o600)
    except Exception:
        pass


def _refresh_token(raw: dict) -> dict:
    """Obtain a new access token using the OAuth refresh token (in-memory only on macOS)."""
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
    _write_raw_credentials(raw)  # no-op on macOS, writes file on Windows/Linux
    return raw


def _valid_access_token(service: str | None = None) -> str:
    """Return a valid access token for the given service (or auto-detected)."""
    raw = _read_raw_credentials(service)
    oauth = raw.get("claudeAiOauth", {})
    token = oauth.get("accessToken")
    expires_at = oauth.get("expiresAt", 0)  # milliseconds

    if not token or (expires_at and expires_at < time.time() * 1000 + 60_000):
        raw = _refresh_token(raw)
        token = raw["claudeAiOauth"]["accessToken"]
    return token


ACCOUNT_URL = "https://api.anthropic.com/api/oauth/account"
_HEADERS_BASE = {"anthropic-beta": OAUTH_BETA, "anthropic-version": "2023-06-01"}


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", **_HEADERS_BASE}


# --- Usage endpoint call ----------------------------------------------------
def _get_usage(token: str) -> dict:
    return requests.get(USAGE_URL, headers=_auth_headers(token), timeout=10)


def fetch_account_info(service: str | None = None) -> dict:
    """Return {"email", "subscription_type"} for the given service."""
    token = _valid_access_token(service)
    resp = requests.get(ACCOUNT_URL, headers=_auth_headers(token), timeout=10)
    if not resp.ok:
        return {"email": "", "subscription_type": service_label(service or KEYCHAIN_SERVICE)}
    data = resp.json()
    return {
        "email": data.get("email_address", ""),
        "subscription_type": service_label(service or KEYCHAIN_SERVICE),
    }


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


def fetch_status(service: str | None = None) -> dict:
    """
    Return:
      {
        "five_hour":  {"used_pct", "remaining_pct", "reset"} | None,
        "seven_day":  {...} | None,
        "updated": datetime,
      }
    Raises AuthError if no valid login is available.
    """
    token = _valid_access_token(service)
    resp = _get_usage(token)

    # A 401 can happen if the token just expired: refresh and retry once.
    if resp.status_code == 401:
        raw = _refresh_token(_read_raw_credentials(service))
        resp = _get_usage(raw["claudeAiOauth"]["accessToken"])

    resp.raise_for_status()
    data = resp.json()

    return {
        "five_hour": _window(data.get("five_hour")),
        "seven_day": _window(data.get("seven_day")),
        "updated": datetime.now(timezone.utc),
    }


def fetch_all_accounts() -> list[dict]:
    """
    Fetch usage for every account that has a working session (valid or refreshable token).

    Returns a list of dicts, each with:
      {"service", "label", "five_hour", "seven_day", "updated", "error"}
    - Accounts with no credentials or an invalid refresh token are excluded.
    - Accounts that fail with a transient error (429, network) are included
      with error="rate_limited" so the caller can show cached data instead.
    """
    results = []
    for svc in _list_keychain_services():
        try:
            st = fetch_status(svc)
            st["service"] = svc
            st["label"] = service_label(svc)
            st["error"] = None
            results.append(st)
        except AuthError:
            pass  # no valid session → exclude
        except Exception as e:
            error_type = "rate_limited" if "429" in str(e) else "error"
            results.append({
                "service": svc,
                "label": service_label(svc),
                "five_hour": None,
                "seven_day": None,
                "updated": None,
                "error": error_type,
            })
    return results


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
