import copy
import datetime
import ipaddress
import re
import time
from urllib.parse import urlparse

import requests


DUCKDNS_UPDATE_URL = "https://www.duckdns.org/update"
PUBLIC_IP_URL = "https://api.ipify.org"
RETRYABLE_HTTP_STATUSES = {429, 500, 502, 503, 504}
DEFAULT_MAX_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 1.0

DEFAULT_DUCKDNS_CONFIG = {
    "enabled": False,
    "domain": "",
    "token": "",
    "interval_minutes": 30.0,
    "last_ip": "",
    "last_status": "never",
    "last_message": "",
    "last_update_at": "",
}


def default_duckdns_config():
    return copy.deepcopy(DEFAULT_DUCKDNS_CONFIG)


def _compact_message(message, max_length=240):
    text = " ".join(str(message or "").split())
    if not text:
        return ""

    if "<html" in text.lower() or "<!doctype" in text.lower():
        error = re.search(r"HTTP ERROR\s+(\d+)\s+([^<]+)", text, flags=re.IGNORECASE)
        if error:
            status_code, reason = error.groups()
            if status_code == "503":
                return "DuckDNS service is temporarily unavailable (HTTP 503). Retry later."
            return f"DuckDNS service returned HTTP {status_code} ({reason.strip()})."
        return "DuckDNS service returned an HTML error page."

    if len(text) > max_length:
        return f"{text[:max_length - 3]}..."
    return text


def normalize_duckdns_config(config):
    normalized = default_duckdns_config()
    if isinstance(config, dict):
        normalized.update(config)

    normalized["enabled"] = bool(normalized.get("enabled"))
    normalized["domain"] = clean_domains(normalized.get("domain", ""))
    normalized["token"] = str(normalized.get("token") or "").strip()
    try:
        normalized["interval_minutes"] = max(5.0, float(normalized.get("interval_minutes", 30.0)))
    except (TypeError, ValueError):
        normalized["interval_minutes"] = 30.0
    normalized["last_message"] = _compact_message(normalized.get("last_message", ""))
    return normalized


def clean_domains(value):
    domains = []
    for part in str(value or "").split(","):
        raw = part.strip().lower()
        if not raw:
            continue
        if "://" in raw:
            parsed = urlparse(raw)
            raw = parsed.netloc or parsed.path
        raw = raw.split("/", 1)[0].strip()
        if raw.endswith(".duckdns.org"):
            raw = raw[: -len(".duckdns.org")]
        raw = "".join(ch for ch in raw if ch.isalnum() or ch == "-").strip("-")
        if raw and raw not in domains:
            domains.append(raw)
    return ",".join(domains)


def detect_public_ip(timeout=12):
    response = requests.get(PUBLIC_IP_URL, timeout=timeout)
    response.raise_for_status()
    detected_ip = response.text.strip()
    ipaddress.ip_address(detected_ip)
    return detected_ip


def _failed_update_result(settings, status, message, now, detected_ip=""):
    return {
        "success": False,
        "status": status,
        # Keep the last successful registered IP on failed updates.
        "ip": settings.get("last_ip", ""),
        "detected_ip": detected_ip,
        "message": _compact_message(message),
        "updated_at": now,
    }


def _failure_message(response):
    if response.status_code == 503:
        return "DuckDNS service is temporarily unavailable (HTTP 503). Retry later."
    if response.status_code in RETRYABLE_HTTP_STATUSES:
        return f"DuckDNS service returned a temporary HTTP {response.status_code} error. Retry later."

    response_text = _compact_message(response.text)
    if response_text.upper() == "KO":
        return "DuckDNS rejected the update. Verify the domain and token."

    detail = response_text or response.reason or "empty response"
    return f"DuckDNS update failed (HTTP {response.status_code}): {detail}"


def update_duckdns_record(config, timeout=15, force=False, max_attempts=DEFAULT_MAX_ATTEMPTS):
    settings = normalize_duckdns_config(config)
    now = datetime.datetime.now().isoformat(timespec="seconds")

    if not force and not settings["enabled"]:
        return _failed_update_result(settings, "disabled", "DuckDNS is disabled.", now)
    if not settings["domain"]:
        return _failed_update_result(settings, "missing_domain", "DuckDNS domain is missing.", now)
    if not settings["token"]:
        return _failed_update_result(settings, "missing_token", "DuckDNS token is missing.", now)

    try:
        current_ip = detect_public_ip(timeout=timeout)
    except Exception as exc:
        return _failed_update_result(settings, "ip_detection_error", f"Public IP detection failed: {exc}", now)

    try:
        attempts = max(1, int(max_attempts))
    except (TypeError, ValueError):
        attempts = DEFAULT_MAX_ATTEMPTS

    for attempt in range(attempts):
        try:
            response = requests.get(
                DUCKDNS_UPDATE_URL,
                params={
                    "domains": settings["domain"],
                    "token": settings["token"],
                    "ip": current_ip,
                },
                timeout=timeout,
            )
        except requests.RequestException as exc:
            if attempt + 1 < attempts:
                time.sleep(RETRY_DELAY_SECONDS * (2 ** attempt))
                continue
            return _failed_update_result(
                settings,
                "network_error",
                f"DuckDNS request failed: {exc}",
                now,
                detected_ip=current_ip,
            )

        response_text = response.text.strip()
        first_line = response_text.splitlines()[0].strip() if response_text else ""
        if response.ok and first_line == "OK":
            return {
                "success": True,
                "status": "ok",
                "ip": current_ip,
                "detected_ip": current_ip,
                "message": "DuckDNS updated successfully.",
                "updated_at": now,
            }

        if response.status_code in RETRYABLE_HTTP_STATUSES and attempt + 1 < attempts:
            time.sleep(RETRY_DELAY_SECONDS * (2 ** attempt))
            continue

        status = "service_unavailable" if response.status_code == 503 else "failed"
        return _failed_update_result(
            settings,
            status,
            _failure_message(response),
            now,
            detected_ip=current_ip,
        )

    return _failed_update_result(settings, "error", "DuckDNS update failed.", now, detected_ip=current_ip)
