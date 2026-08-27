"""
usage_core.py — Nucleo condiviso Mac/Windows per "Claude Usage Battery".

Legge il token di login locale di Claude Code, interroga l'endpoint ufficiale
di utilizzo (lo stesso usato dal comando /usage) e restituisce la percentuale
rimasta per la finestra di 5 ore e per quella settimanale.

Il token resta SEMPRE sul tuo computer: viene usato solo per parlare con
api.anthropic.com, esattamente come fa Claude Code.
"""

import json
import os
import platform
import subprocess
import time
from datetime import datetime, timezone

import requests

# --- Costanti scoperte dalla CLI di Claude Code -----------------------------
USAGE_URL = "https://api.anthropic.com/api/oauth/usage"
TOKEN_URL = "https://platform.claude.com/v1/oauth/token"
CLIENT_ID = "9d1c250a-e61b-44d9-88ed-5944d1962f5e"
OAUTH_BETA = "oauth-2025-04-20"
KEYCHAIN_SERVICE = "Claude Code-credentials"
CRED_FILE = os.path.expanduser("~/.claude/.credentials.json")

IS_MAC = platform.system() == "Darwin"


class AuthError(Exception):
    """Nessun login valido trovato (l'utente deve loggarsi in Claude Code)."""


# --- Lettura / scrittura credenziali ----------------------------------------
def _read_raw_credentials() -> dict:
    """
    Restituisce il dict {"claudeAiOauth": {...}} dal Portachiavi (Mac)
    o dal file ~/.claude/.credentials.json (Windows/Linux, e fallback Mac).
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
            pass  # ricadiamo sul file

    # 2) File credenziali (Windows/Linux, o Mac se il portachiavi non risponde)
    if os.path.exists(CRED_FILE):
        with open(CRED_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    raise AuthError(
        "Credenziali Claude non trovate. Accedi con Claude Code almeno una volta."
    )


def _write_raw_credentials(data: dict) -> None:
    """Salva le credenziali aggiornate (dopo un refresh del token)."""
    payload = json.dumps(data)
    if IS_MAC:
        try:
            # -U aggiorna la voce se esiste già.
            subprocess.run(
                ["security", "add-generic-password", "-U",
                 "-s", KEYCHAIN_SERVICE, "-a", KEYCHAIN_SERVICE, "-w", payload],
                capture_output=True, text=True, timeout=10,
            )
            return
        except Exception:
            pass
    # File (Windows/Linux)
    os.makedirs(os.path.dirname(CRED_FILE), exist_ok=True)
    with open(CRED_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f)
    try:
        os.chmod(CRED_FILE, 0o600)
    except Exception:
        pass


def _refresh_token(raw: dict) -> dict:
    """Rinnova l'access token usando il refresh token OAuth."""
    oauth = raw.get("claudeAiOauth", {})
    refresh = oauth.get("refreshToken")
    if not refresh:
        raise AuthError("Refresh token assente: rifai il login in Claude Code.")

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
        raise AuthError(f"Refresh fallito ({resp.status_code}). Rifai il login.")
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
    """Access token valido, rinnovandolo se scaduto o quasi."""
    raw = _read_raw_credentials()
    oauth = raw.get("claudeAiOauth", {})
    token = oauth.get("accessToken")
    expires_at = oauth.get("expiresAt", 0)  # millisecondi

    # Rinnova se manca o scade entro 60s.
    if not token or (expires_at and expires_at < time.time() * 1000 + 60_000):
        raw = _refresh_token(raw)
        token = raw["claudeAiOauth"]["accessToken"]
    return token


# --- Chiamata all'endpoint usage --------------------------------------------
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
    """resets_at può essere una stringa ISO 8601 o un timestamp unix (sec)."""
    if not resets_at:
        return None
    if isinstance(resets_at, (int, float)):
        return datetime.fromtimestamp(int(resets_at), tz=timezone.utc)
    try:
        # Formato ISO, es. '2026-08-27T12:39:59.645837+00:00' (o con 'Z').
        return datetime.fromisoformat(str(resets_at).replace("Z", "+00:00"))
    except ValueError:
        return None


def _window(obj: dict | None) -> dict | None:
    """Normalizza una finestra {utilization, resets_at} in percentuali/orari."""
    if not obj:
        return None
    # utilization è già una percentuale 0..100 (es. 79.0 = 79% usato).
    util = float(obj.get("utilization", 0.0))
    used_pct = max(0, min(100, round(util)))
    remaining_pct = 100 - used_pct
    reset_dt = _parse_reset(obj.get("resets_at"))
    return {"used_pct": used_pct, "remaining_pct": remaining_pct, "reset": reset_dt}


def fetch_status() -> dict:
    """
    Ritorna:
      {
        "five_hour":  {"used_pct", "remaining_pct", "reset"} | None,
        "seven_day":  {...} | None,
        "updated": datetime,
      }
    Solleva AuthError se il login non è disponibile.
    """
    token = _valid_access_token()
    resp = _get_usage(token)

    # Un 401 può capitare se il token è appena scaduto: rinnova e riprova una volta.
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


# --- Utility di formattazione ------------------------------------------------
def human_reset(reset_dt) -> str:
    """'tra 2h 13m' oppure 'ora'."""
    if reset_dt is None:
        return "n/d"
    delta = (reset_dt - datetime.now(timezone.utc)).total_seconds()
    if delta <= 0:
        return "ora"
    h = int(delta // 3600)
    m = int((delta % 3600) // 60)
    if h > 24:
        d = h // 24
        h = h % 24
        return f"tra {d}g {h}h"
    if h:
        return f"tra {h}h {m:02d}m"
    return f"tra {m}m"


def level_color(remaining_pct: int) -> tuple:
    """Colore RGBA in base alla carica rimasta (verde/arancio/rosso)."""
    if remaining_pct >= 50:
        return (52, 199, 89, 255)     # verde
    if remaining_pct >= 20:
        return (255, 159, 10, 255)    # arancio
    return (255, 59, 48, 255)         # rosso
