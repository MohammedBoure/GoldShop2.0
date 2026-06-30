import json
import logging
import os
import sys
from datetime import date, datetime
from decimal import Decimal
from functools import lru_cache
from urllib.parse import urlencode

from flask import Flask, Response, g, render_template, request
from werkzeug.exceptions import HTTPException

from database.base import Database
from database.client_manager import ClientManager
# تمت إزالة استدعاء ClientPaymentManager من هنا
from database.inventory_manager import InventoryManager
from database.repair_manager import RepairManager
from database.reports_manager import ReportsManager
from database.sales_manager.sale_reader import SaleReader
from database.statistics_manager import StatisticsManager
from database.supplier_manager import SupplierManager
from database.treasury_manager import TreasuryManager
from web.security import (
    clear_failed_logins,
    login_is_rate_limited,
    record_failed_login,
    verify_web_password,
    web_password_configured,
)
from web.routes.core import register_core_routes
from web.routes.operations import register_operation_routes
from web.routes.partners import register_partner_routes
from services.runtime_control import (
    DEFAULT_FORCE_LOGOUT_URL,
    create_force_logout_command,
    execute_force_logout_command,
)

logger = logging.getLogger("JEWELLERY_SYS")

flask_app = Flask(__name__)
flask_app.url_map.strict_slashes = False

db = Database()
sale_reader = SaleReader(db)
# payment_manager = ClientPaymentManager(db) # تم التعطيل مؤقتاً
inventory_manager = InventoryManager(db)
client_manager = ClientManager(db)
supplier_manager = SupplierManager(db)
stats_manager = StatisticsManager(db)
repair_manager = RepairManager(db)
treasury_manager = TreasuryManager(db)
reports_manager = ReportsManager(db)

READ_ONLY_METHODS = {"GET", "HEAD", "OPTIONS"}
WRITE_POST_PATHS = {"/api/v1/market-price/gold", "/api/v1/runtime/force-logout"}
WEB_PASSWORD_HEADER = "X-GoldShop-Password"
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200
DEFAULT_LANGUAGE = "ar"
LANGUAGE_COOKIE = "goldshop_lang"
TRANSLATIONS_DIR = os.path.join(os.path.dirname(__file__), "translations")
SUPPORTED_LANGUAGES = {
    "ar": {"name": "العربية", "dir": "rtl"},
    "fr": {"name": "Français", "dir": "ltr"},
}

REFERENCE_TABLES = {
    "categories": {
        "table": "Categories",
        "columns": "id, name, invoice_display_name",
        "order": "name ASC",
    },
    "metal-types": {
        "table": "MetalTypes",
        "columns": "id, name, purity_value, metal_category, description, invoice_display_name",
        "order": "purity_value DESC, name ASC",
    },
    "product-names": {
        "table": "ProductNames",
        "columns": "id, name",
        "order": "name ASC",
    },
    "storage-locations": {
        "table": "StorageLocations",
        "columns": "id, name",
        "order": "name ASC",
    },
    "currencies": {
        "table": "Currencies",
        "columns": "id, code, name, symbol, exchange_rate, is_base",
        "order": "is_base DESC, id ASC",
    },
    "treasury-locations": {
        "table": "TreasuryLocations",
        "columns": "id, name, type, description, is_active, created_at",
        "order": "type ASC, name ASC",
    },
    "expense-categories": {
        "table": "ExpenseCategories",
        "columns": "id, name",
        "order": "name ASC",
    },
    "invoice-notes": {
        "table": "InvoiceNotes",
        "columns": "id, note_text",
        "order": "note_text ASC",
    },
    "black-market-rates": {
        "table": "BlackMarketRates",
        "columns": "id, currency_name, buy_price, sell_price, retrieved_at, source",
        "order": "retrieved_at DESC, id DESC",
        "limit": 50,
    },
}

def _normalize_language(value):
    lang = str(value or "").strip().lower().replace("_", "-").split("-", 1)[0]
    return lang if lang in SUPPORTED_LANGUAGES else None

def _deep_merge(base, override):
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged

@lru_cache(maxsize=None)
def _load_language(lang):
    path = os.path.join(TRANSLATIONS_DIR, f"{lang}.json")
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        logger.warning("Missing translation file: %s", path)
    except json.JSONDecodeError as error:
        logger.warning("Invalid translation file %s: %s", path, error)
    return {}

@lru_cache(maxsize=None)
def _translation_bundle(lang):
    selected = _normalize_language(lang) or DEFAULT_LANGUAGE
    base = _load_language(DEFAULT_LANGUAGE)
    if selected == DEFAULT_LANGUAGE:
        return base
    return _deep_merge(base, _load_language(selected))

def _resolve_language():
    explicit = _normalize_language(request.args.get("lang"))
    if explicit:
        return explicit
    cookie_lang = _normalize_language(request.cookies.get(LANGUAGE_COOKIE))
    if cookie_lang:
        return cookie_lang
    accepted = request.accept_languages.best_match(list(SUPPORTED_LANGUAGES.keys()))
    return _normalize_language(accepted) or DEFAULT_LANGUAGE

def _current_language():
    return getattr(g, "lang", DEFAULT_LANGUAGE)

def _current_direction():
    return SUPPORTED_LANGUAGES[_current_language()]["dir"]

def _translate_key(key, lang=None, default=None, **kwargs):
    value = _translation_bundle(lang or _current_language())
    for part in str(key).split("."):
        if not isinstance(value, dict) or part not in value:
            value = default if default is not None else key
            break
        value = value[part]

    if not isinstance(value, str):
        value = default if default is not None else str(value)

    if kwargs:
        try:
            return value.format(**kwargs)
        except (KeyError, ValueError):
            return value
    return value

def _url_with_lang(lang):
    target_lang = _normalize_language(lang) or DEFAULT_LANGUAGE
    args = request.args.to_dict(flat=True)
    args["lang"] = target_lang
    return f"{request.path}?{urlencode(args)}"

def _to_jsonable(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, dict):
        return {str(k): _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_to_jsonable(item) for item in value]
    return value

def _json_response(payload, status=200):
    return Response(
        json.dumps(_to_jsonable(payload), ensure_ascii=False),
        status=status,
        mimetype="application/json; charset=utf-8",
    )

def _ok(data=None, status=200, **meta):
    payload = {"success": True, "data": data if data is not None else {}}
    if meta:
        payload["meta"] = meta
    return _json_response(payload, status=status)

def _json_error(message, status=400, **extra):
    payload = {"success": False, "error": message}
    if extra:
        payload.update(extra)
    return _json_response(payload, status=status)

def _int_arg(name, default=None, min_value=None, max_value=None):
    raw = request.args.get(name)
    if raw in (None, ""):
        value = default
    else:
        try:
            value = int(raw)
        except (TypeError, ValueError):
            value = default
    if value is None:
        return value
    if min_value is not None:
        value = max(min_value, value)
    if max_value is not None:
        value = min(max_value, value)
    return value

def _float_arg(name, default=None):
    raw = request.args.get(name)
    if raw in (None, ""):
        return default
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default

def _str_arg(name, default=""):
    raw = request.args.get(name, default)
    if raw is None:
        return default
    return str(raw).strip()

def _bool_arg(name, default=False):
    raw = request.args.get(name)
    if raw in (None, ""):
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}

def _page_args(default_per_page=DEFAULT_PAGE_SIZE):
    page = _int_arg("page", 1, min_value=1)
    per_page = _int_arg("per_page", default_per_page, min_value=1, max_value=MAX_PAGE_SIZE)
    return page, per_page, (page - 1) * per_page

def _date_range_args():
    start_date = _str_arg("start_date") or None
    end_date = _str_arg("end_date") or None
    if start_date and not end_date:
        end_date = date.today().isoformat()
    elif end_date and not start_date:
        start_date = "1900-01-01"
    return start_date, end_date

def _fetch_rows(query, params=()):
    with db.get_db_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(query, tuple(params))
        return cursor.fetchall()

def _fetch_one(query, params=()):
    with db.get_db_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(query, tuple(params))
        return cursor.fetchone()

def _not_found(resource_name="Resource"):
    return _json_error(_translate_key("api.errors.not_found", resource=resource_name), status=404)

def _reference_key(name):
    return str(name or "").strip().lower().replace("_", "-")

def _reference_rows(name, limit=None):
    key = _reference_key(name)
    config = REFERENCE_TABLES.get(key)
    if not config:
        return None
    requested_limit = limit if limit is not None else config.get("limit")
    query = f"SELECT {config['columns']} FROM {config['table']} ORDER BY {config['order']}"
    params = []
    if requested_limit:
        query += " LIMIT %s"
        params.append(int(requested_limit))
    return _fetch_rows(query, params)

@flask_app.before_request
def set_request_language():
    g.lang = _resolve_language()
    return None

@flask_app.context_processor
def inject_i18n():
    lang = _current_language()
    return {
        "available_languages": SUPPORTED_LANGUAGES,
        "current_dir": _current_direction(),
        "current_lang": lang,
        "current_translations": _translation_bundle(lang),
        "t": _translate_key,
        "url_with_lang": _url_with_lang,
    }

@flask_app.before_request
def require_api_password():
    if not request.path.startswith("/api") or request.method == "OPTIONS":
        return None
    if not web_password_configured():
        return _json_error(_translate_key("auth.not_configured"), status=503)

    client_key = request.remote_addr or "unknown"
    if login_is_rate_limited(client_key):
        return _json_error(_translate_key("auth.rate_limited"), status=429)
    if not verify_web_password(request.headers.get(WEB_PASSWORD_HEADER, "")):
        record_failed_login(client_key)
        return _json_error(_translate_key("auth.invalid_password"), status=401)

    clear_failed_logins(client_key)
    return None

@flask_app.before_request
def enforce_read_only_api():
    if not request.path.startswith("/api"):
        return None
    if request.method == "OPTIONS":
        return _json_response({}, status=204)
    if request.method == "POST" and request.path.rstrip("/") in WRITE_POST_PATHS:
        return None
    if request.method not in READ_ONLY_METHODS:
        return _json_error(_translate_key("api.errors.read_only"), status=405)
    return None

@flask_app.route("/api/v1/runtime/force-logout", methods=["POST"])
def api_v1_runtime_force_logout():
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return _json_error(_translate_key("api.errors.invalid_payload"), status=400)

    command = create_force_logout_command(
        db,
        url=DEFAULT_FORCE_LOGOUT_URL,
        issued_by=request.remote_addr or "api",
    )
    execute_force_logout_command(command, exit_delay_seconds=0.5)
    logger.warning("Runtime force logout command issued by %s: %s", request.remote_addr or "api", command.get("id"))
    return _ok({"command_id": command.get("id"), "target": "all_running_devices", "url": command.get("url") or DEFAULT_FORCE_LOGOUT_URL})

@flask_app.after_request
def add_api_headers(response):
    requested_lang = _normalize_language(request.args.get("lang"))
    if requested_lang:
        response.set_cookie(LANGUAGE_COOKIE, requested_lang, max_age=60 * 60 * 24 * 365, samesite="Lax")

    if request.path.startswith("/api"):
        if request.path.rstrip("/") in WRITE_POST_PATHS:
            response.headers["X-API-Mode"] = "password-protected-write"
            response.headers["Allow"] = "POST, OPTIONS"
        else:
            response.headers["X-API-Mode"] = "password-protected-read"
            response.headers["Allow"] = "GET, HEAD, OPTIONS"

        allowed_origins = [origin.strip() for origin in os.getenv("READ_API_ALLOWED_ORIGINS", "").split(",") if origin.strip()]
        request_origin = request.headers.get("Origin")
        if "*" in allowed_origins:
            response.headers["Access-Control-Allow-Origin"] = "*"
        elif request_origin and request_origin in allowed_origins:
            response.headers["Access-Control-Allow-Origin"] = request_origin
        if allowed_origins:
            response.headers["Access-Control-Allow-Methods"] = "GET, HEAD, POST, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = f"Content-Type, {WEB_PASSWORD_HEADER}"
    return response

@flask_app.errorhandler(HTTPException)
def handle_http_exception(error):
    if request.path.startswith("/api"):
        return _json_error(error.description or error.name, status=error.code or 500)
    return error

@flask_app.errorhandler(Exception)
def handle_unexpected_exception(error):
    if request.path.startswith("/api"):
        logger.exception("Read API error: %s", error)
        return _json_error(_translate_key("api.errors.internal"), status=500)
    raise error

_route_context = sys.modules[__name__]
for _register_routes in (register_core_routes, register_partner_routes, register_operation_routes):
    globals().update(_register_routes(flask_app, _route_context))

if __name__ == "__main__":
    flask_app.run(debug=True, host="0.0.0.0", port=8000)