import base64
import hashlib
import hmac
import json
import os
import platform
import socket
import sys
import uuid
import ctypes
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv


PRODUCT_NAME = "GoldShop"
PRODUCT_TOKEN_NAME = "Jewelry"
TRIAL_DAYS = 7
STATE_VERSION = 1
SIGNATURE_SALT = "GoldShop local license state v1"
SECRET_ENV_NAMES = ("GOLDSHOP_ACTIVATION_SECRET", "KEYGEN_TOKEN_JEWELRY_SECRET")


@dataclass(frozen=True)
class LicenseStatus:
    request_code: str
    activated: bool
    trial_active: bool
    days_remaining: int
    reason: str = ""

    @property
    def can_run(self) -> bool:
        return self.activated or self.trial_active


class LicenseError(ValueError):
    pass


def app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def load_private_environment() -> None:
    load_dotenv(app_root() / ".env")


def activation_secret() -> str:
    load_private_environment()
    for name in SECRET_ENV_NAMES:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


def license_state_path() -> Path:
    override = os.getenv("GOLDSHOP_LICENSE_PATH", "").strip()
    if override:
        return Path(override)

    base = (
        os.getenv("LOCALAPPDATA")
        or os.getenv("APPDATA")
        or os.getenv("PROGRAMDATA")
    )
    if base:
        return Path(base) / PRODUCT_NAME / "license.json"
    return app_root() / "runtime" / "license.json"


def machine_fingerprint() -> str:
    parts = [PRODUCT_NAME, platform.system(), platform.machine()]

    disk_serial = _windows_system_drive_serial()
    if disk_serial:
        parts.append(f"disk:{disk_serial}")
        return "|".join(str(part or "").strip().lower() for part in parts)

    machine_guid = _windows_machine_guid()
    if machine_guid:
        parts.append(f"guid:{machine_guid}")
        return "|".join(str(part or "").strip().lower() for part in parts)

    parts.extend([platform.node(), socket.gethostname(), str(uuid.getnode())])
    return "|".join(str(part or "").strip().lower() for part in parts)


def _legacy_machine_fingerprints() -> list[str]:
    parts = [
        PRODUCT_NAME,
        platform.system(),
        platform.machine(),
        platform.node(),
        socket.gethostname(),
        str(uuid.getnode()),
    ]
    machine_guid = _windows_machine_guid()
    if machine_guid:
        parts.append(machine_guid)
    legacy = "|".join(str(part or "").strip().lower() for part in parts)
    current = machine_fingerprint()
    return [legacy] if legacy and legacy != current else []


def _windows_system_drive_serial() -> str:
    if platform.system().lower() != "windows":
        return ""
    root = os.getenv("SystemDrive", "C:").rstrip("\\/") + "\\"
    volume_serial = ctypes.c_ulong()
    try:
        ok = ctypes.windll.kernel32.GetVolumeInformationW(
            ctypes.c_wchar_p(root),
            None,
            0,
            ctypes.byref(volume_serial),
            None,
            None,
            None,
            0,
        )
    except Exception:
        return ""
    if not ok:
        return ""
    return f"{volume_serial.value:08X}"


def _windows_machine_guid() -> str:
    if platform.system().lower() != "windows":
        return ""
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Cryptography",
        ) as key:
            value, _kind = winreg.QueryValueEx(key, "MachineGuid")
            return str(value)
    except Exception:
        return ""


def request_code() -> str:
    digest = hashlib.sha256(machine_fingerprint().encode("utf-8")).hexdigest().upper()
    code = digest[:12]
    return "-".join(code[index:index + 4] for index in range(0, 12, 4))


def expected_activation_key(code: str, secret: str) -> str:
    digest = hashlib.sha256(f"{normalise_code(code)}::{secret}".encode("utf-8")).hexdigest().upper()
    key = digest[:16]
    return "-".join(key[index:index + 4] for index in range(0, 16, 4))


def normalise_code(value: str) -> str:
    return str(value or "").strip().upper()


def normalise_activation_key(value: str) -> str:
    compact = "".join(char for char in str(value or "").upper() if char.isalnum())
    if len(compact) != 16:
        return str(value or "").strip().upper()
    return "-".join(compact[index:index + 4] for index in range(0, 16, 4))


def verify_activation_key(code: str, key: str, secret: str | None = None) -> bool:
    secret = secret if secret is not None else activation_secret()
    if not secret:
        return False
    expected = expected_activation_key(code, secret)
    return hmac.compare_digest(expected, normalise_activation_key(key))


def check_license(now: datetime | None = None) -> LicenseStatus:
    now = _normalise_datetime(now)
    code = request_code()
    state = _read_state()

    if _state_has_valid_activation(state, code):
        _touch_state(state, now)
        return LicenseStatus(code, activated=True, trial_active=False, days_remaining=0)

    if not state:
        state = _new_trial_state(code, now)
        _write_state(state)

    if not _valid_state_signature(state):
        return LicenseStatus(code, False, False, 0, "license_state_invalid")

    if state.get("request_code") != code:
        return LicenseStatus(code, False, False, 0, "different_machine")

    first_seen = _parse_datetime(state.get("first_seen"))
    last_seen = _parse_datetime(state.get("last_seen"))
    if first_seen is None or last_seen is None:
        return LicenseStatus(code, False, False, 0, "license_state_invalid")

    if now + timedelta(minutes=5) < last_seen:
        return LicenseStatus(code, False, False, 0, "clock_rollback")

    expires_at = first_seen + timedelta(days=TRIAL_DAYS)
    if now >= expires_at:
        _touch_state(state, now)
        return LicenseStatus(code, False, False, 0, "trial_expired")

    _touch_state(state, now)
    remaining = max(1, (expires_at.date() - now.date()).days)
    return LicenseStatus(code, False, True, remaining)


def activate_license(key: str, now: datetime | None = None) -> LicenseStatus:
    now = _normalise_datetime(now)
    code = request_code()
    secret = activation_secret()
    if not secret:
        raise LicenseError(
            "GOLDSHOP_ACTIVATION_SECRET is missing from the local .env file."
        )
    if not verify_activation_key(code, key, secret):
        raise LicenseError("Invalid activation key for this computer.")

    state = _read_state() or _new_trial_state(code, now)
    state.update(
        {
            "version": STATE_VERSION,
            "request_code": code,
            "activated": True,
            "activation_key": normalise_activation_key(key),
            "activated_at": _format_datetime(now),
            "last_seen": _format_datetime(now),
        }
    )
    _write_state(state)
    return LicenseStatus(code, activated=True, trial_active=False, days_remaining=0)


def _state_has_valid_activation(state: dict, code: str) -> bool:
    if not state or not state.get("activated"):
        return False
    if not _valid_state_signature(state):
        return False
    stored_code = normalise_code(state.get("request_code", ""))
    return bool(stored_code) and verify_activation_key(stored_code, state.get("activation_key", ""))


def _read_state() -> dict:
    path = license_state_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _write_state(state: dict) -> None:
    state["signature"] = _state_signature(state)
    path = license_state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")


def _touch_state(state: dict, now: datetime) -> None:
    last_seen = _parse_datetime(state.get("last_seen"))
    if last_seen is None or now > last_seen:
        state["last_seen"] = _format_datetime(now)
        _write_state(state)


def _new_trial_state(code: str, now: datetime) -> dict:
    timestamp = _format_datetime(now)
    return {
        "version": STATE_VERSION,
        "product": PRODUCT_NAME,
        "token_name": PRODUCT_TOKEN_NAME,
        "request_code": code,
        "activated": False,
        "first_seen": timestamp,
        "last_seen": timestamp,
    }


def _state_signature(state: dict, fingerprint: str | None = None) -> str:
    payload = {key: value for key, value in state.items() if key != "signature"}
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    fingerprint = fingerprint or machine_fingerprint()
    key = hashlib.sha256(f"{fingerprint}::{SIGNATURE_SALT}".encode("utf-8")).digest()
    return base64.urlsafe_b64encode(hmac.new(key, raw, hashlib.sha256).digest()).decode("ascii")


def _valid_state_signature(state: dict) -> bool:
    signature = str(state.get("signature", ""))
    if not signature:
        return False
    fingerprints = [machine_fingerprint(), *_legacy_machine_fingerprints()]
    return any(
        hmac.compare_digest(signature, _state_signature(state, fingerprint))
        for fingerprint in fingerprints
    )


def _normalise_datetime(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _format_datetime(value: datetime) -> str:
    return _normalise_datetime(value).isoformat(timespec="seconds")


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return _normalise_datetime(datetime.fromisoformat(value))
    except ValueError:
        return None
