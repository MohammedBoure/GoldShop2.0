import base64
import json
import logging
import os
from typing import Dict, List, Optional

from database.base import get_external_path


ACCOUNTS_FILE = os.path.join(get_external_path("runtime"), "saved_accounts.json")


def _protect_password(password: str) -> str:
    raw = (password or "").encode("utf-8")
    try:
        import win32crypt

        encrypted = win32crypt.CryptProtectData(raw, "GoldShop saved account", None, None, None, 0)
        return "dpapi:" + base64.b64encode(encrypted).decode("ascii")
    except Exception:
        logging.warning("DPAPI is unavailable; saved account password will use compatibility encoding.")
        return "b64:" + base64.b64encode(raw).decode("ascii")


def _unprotect_password(token: str) -> str:
    if not token:
        return ""
    if token.startswith("dpapi:"):
        import win32crypt

        encrypted = base64.b64decode(token[6:].encode("ascii"))
        return win32crypt.CryptUnprotectData(encrypted, None, None, None, 0)[1].decode("utf-8")
    if token.startswith("b64:"):
        return base64.b64decode(token[4:].encode("ascii")).decode("utf-8")
    return base64.b64decode(token.encode("ascii")).decode("utf-8")


def load_saved_accounts() -> List[Dict]:
    if not os.path.exists(ACCOUNTS_FILE):
        return []
    try:
        with open(ACCOUNTS_FILE, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        accounts = data.get("accounts", []) if isinstance(data, dict) else data
        return [account for account in accounts if account.get("username") and account.get("token")]
    except Exception as exc:
        logging.exception("Could not load saved accounts: %s", exc)
        return []


def save_saved_account(username: str, password: str, full_name: str = "", role: str = "") -> None:
    username = str(username or "").strip()
    if not username or not password:
        return

    accounts = [account for account in load_saved_accounts() if account.get("username") != username]
    accounts.append(
        {
            "username": username,
            "full_name": str(full_name or "").strip(),
            "role": str(role or "").strip(),
            "token": _protect_password(password),
        }
    )
    os.makedirs(os.path.dirname(ACCOUNTS_FILE), exist_ok=True)
    with open(ACCOUNTS_FILE, "w", encoding="utf-8") as handle:
        json.dump({"accounts": accounts}, handle, indent=2, ensure_ascii=False)


def remove_saved_account(username: str) -> None:
    username = str(username or "").strip()
    accounts = [account for account in load_saved_accounts() if account.get("username") != username]
    os.makedirs(os.path.dirname(ACCOUNTS_FILE), exist_ok=True)
    with open(ACCOUNTS_FILE, "w", encoding="utf-8") as handle:
        json.dump({"accounts": accounts}, handle, indent=2, ensure_ascii=False)


def get_saved_account_password(username: str) -> Optional[str]:
    username = str(username or "").strip()
    for account in load_saved_accounts():
        if account.get("username") != username:
            continue
        try:
            return _unprotect_password(account.get("token", ""))
        except Exception as exc:
            logging.exception("Could not read saved password for %s: %s", username, exc)
            return None
    return None
