import logging
import threading
import time

from werkzeug.security import check_password_hash, generate_password_hash

from config import get_config_path, load_full_config


logger = logging.getLogger("JEWELLERY_SYS")

MIN_WEB_PASSWORD_LENGTH = 8
_WEB_ACCESS_KEY = "web_access"
_PASSWORD_METHOD = "pbkdf2:sha256:600000"
_CONFIG_LOCK = threading.Lock()
_CACHED_STAMP = None
_CACHED_WEB_ACCESS = {}
_ATTEMPT_LOCK = threading.Lock()
_FAILED_ATTEMPTS = {}
_MAX_ATTEMPTS = 5
_ATTEMPT_WINDOW_SECONDS = 300


def _web_access_section(config):
    section = config.get(_WEB_ACCESS_KEY)
    return section if isinstance(section, dict) else {}


def _load_web_access():
    global _CACHED_STAMP, _CACHED_WEB_ACCESS
    path = get_config_path()
    try:
        stat = path.stat()
        stamp = (stat.st_mtime_ns, stat.st_size)
    except OSError:
        stamp = None

    with _CONFIG_LOCK:
        if stamp == _CACHED_STAMP:
            return dict(_CACHED_WEB_ACCESS)
        section = dict(_web_access_section(load_full_config()))
        _CACHED_STAMP = stamp
        _CACHED_WEB_ACCESS = section
        return dict(section)


def web_password_configured(config=None):
    section = _web_access_section(config) if isinstance(config, dict) else _load_web_access()
    return bool(str(section.get("password_hash") or "").strip())


def verify_web_password(password):
    password_hash = str(_load_web_access().get("password_hash") or "")
    if not password_hash or not isinstance(password, str):
        return False
    try:
        return check_password_hash(password_hash, password)
    except (ValueError, TypeError):
        logger.warning("Invalid stored web password hash.")
        return False


def set_web_password(config, password):
    if not isinstance(password, str) or len(password) < MIN_WEB_PASSWORD_LENGTH:
        raise ValueError(f"Le mot de passe Web doit contenir au moins {MIN_WEB_PASSWORD_LENGTH} caracteres.")
    section = config.setdefault(_WEB_ACCESS_KEY, {})
    section["password_hash"] = generate_password_hash(password, method=_PASSWORD_METHOD)


def clear_web_password(config):
    section = config.setdefault(_WEB_ACCESS_KEY, {})
    section.pop("password_hash", None)


def _recent_attempts(identifier):
    cutoff = time.monotonic() - _ATTEMPT_WINDOW_SECONDS
    attempts = [moment for moment in _FAILED_ATTEMPTS.get(identifier, []) if moment >= cutoff]
    if attempts:
        _FAILED_ATTEMPTS[identifier] = attempts
    else:
        _FAILED_ATTEMPTS.pop(identifier, None)
    return attempts


def login_is_rate_limited(identifier):
    with _ATTEMPT_LOCK:
        return len(_recent_attempts(identifier)) >= _MAX_ATTEMPTS


def record_failed_login(identifier):
    with _ATTEMPT_LOCK:
        attempts = _recent_attempts(identifier)
        attempts.append(time.monotonic())
        _FAILED_ATTEMPTS[identifier] = attempts


def clear_failed_logins(identifier):
    with _ATTEMPT_LOCK:
        _FAILED_ATTEMPTS.pop(identifier, None)
