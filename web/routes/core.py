# web/routes/core.py

import logging

logger = logging.getLogger("JEWELLERY_SYS")


def get_api_catalog():
    """Return an extensive map of all available REST endpoints in the system."""
    return {
        "version": "2.0",
        "system": "GoldShop 2.0 Web API",
        "status": "active",
        "documentation": {
            "reports": {
                "journal": {
                    "url": "/api/v1/reports/journal",
                    "method": "GET",
                    "description": "Daily Sales & Receipts Journal matching ui/widgets/reports/excel_journal_view.py.",
                    "params": ["year", "month", "day", "search", "seller_id", "seller_name"],
                },
                "journal_sellers": {
                    "url": "/api/v1/reports/journal/sellers",
                    "method": "GET",
                    "description": "List of sellers for filtering the journal table.",
                },
                "monthly_summary": {
                    "url": "/api/v1/reports/monthly-summary",
                    "method": "GET",
                    "description": "Monthly revenue, sales weights, cash, TPE, scrap metal, and profit synthesis matching ui/widgets/reports/monthly_summary_view.py.",
                    "params": ["year", "month"],
                },
            },
            "versements": {
                "list": {
                    "url": "/api/v1/versements",
                    "method": "GET",
                    "description": "Customer reservations / layaway dossiers with items, deducted/remaining weights, notes, and payments matching ui/widgets/versements/versements_view.py.",
                    "params": ["status", "search", "client_id", "page", "per_page"],
                },
                "detail": {
                    "url": "/api/v1/versements/<id>",
                    "method": "GET",
                    "description": "Full details for a single layaway dossier.",
                },
                "stats": {
                    "url": "/api/v1/versements/stats",
                    "method": "GET",
                    "description": "KPI summary statistics for layaways.",
                },
            },
            "artisan_work": {
                "orders": {
                    "url": "/api/v1/artisan-work/orders",
                    "method": "GET",
                    "description": "Atelier Production Orders matching ui/widgets/artisan_work/artisan_work_view.py.",
                    "params": ["status", "days", "date_from", "date_to", "artisan_id", "search", "page", "per_page"],
                },
                "order_detail": {
                    "url": "/api/v1/artisan-work/orders/<id>",
                    "method": "GET",
                    "description": "Single workshop/repair order details with payment information.",
                },
                "artisans": {
                    "url": "/api/v1/artisan-work/artisans",
                    "method": "GET",
                    "description": "Artisans directory with pure gold and labor balances.",
                },
                "artisan_ledger": {
                    "url": "/api/v1/artisan-work/artisans/<id>/ledger",
                    "method": "GET",
                    "description": "Account movement ledger and statement for an artisan.",
                },
            },
            "suppliers": {
                "list": {
                    "url": "/api/v1/suppliers",
                    "method": "GET",
                    "description": "Suppliers directory with Poids Net (g) and Solde (DA) balances matching ui/widgets/suppliers/suppliers_view.py.",
                    "params": ["search", "include_inactive", "page", "per_page"],
                },
                "detail": {
                    "url": "/api/v1/suppliers/<id>",
                    "method": "GET",
                    "description": "Supplier profile and header card KPI summary data.",
                },
                "ledger": {
                    "url": "/api/v1/suppliers/<id>/ledger",
                    "method": "GET",
                    "description": "100% French Suppliers Ledger matching the Excel spreadsheet (Date, Poids, Afaçon, Montant, Obs).",
                    "params": ["search", "start_date", "end_date", "page", "per_page"],
                },
            },
            "core_and_operations": {
                "sales": "/api/v1/sales",
                "inventory": "/api/v1/inventory",
                "clients": "/api/v1/clients",
                "treasury": "/api/v1/treasury/balances",
                "coffre": "/api/v1/coffre/operations",
                "expenses": "/api/v1/expenses",
                "references": "/api/v1/references",
                "search": "/api/v1/search",
                "gold_price_update": "/api/v1/market-price/gold (POST)",
            },
        },
    }


def register_core_routes(flask_app, api):
    """Register core utility, authentication, catalog, dashboard, and gold price routes."""

    @flask_app.route("/api")
    @flask_app.route("/api/v1")
    def api_catalog():
        """Return the API catalog and documentation overview."""
        return api._ok(get_api_catalog())

    @flask_app.route("/api/v1/auth/status")
    def api_v1_auth_status():
        """Check whether password is required and if the current request is already authenticated."""
        is_configured = api.web_password_configured()
        token = api.request.headers.get(api.WEB_PASSWORD_HEADER, "") or api.request.cookies.get("goldshop_web_password", "")
        is_authenticated = api.verify_web_password(token) if is_configured else True
        return api._ok({
            "password_required": is_configured,
            "authenticated": is_authenticated,
        })

    @flask_app.route("/api/v1/auth/login", methods=["POST"])
    def api_v1_auth_login():
        """Authenticate with password and set session cookie."""
        if not api.web_password_configured():
            return api._json_error(api._translate_key("auth.not_configured"), status=503)

        client_key = api.request.remote_addr or "unknown"
        if api.login_is_rate_limited(client_key):
            return api._json_error(api._translate_key("auth.rate_limited"), status=429)

        payload = api.request.get_json(silent=True) or {}
        password = payload.get("password") or api.request.headers.get(api.WEB_PASSWORD_HEADER, "")

        if not api.verify_web_password(str(password)):
            api.record_failed_login(client_key)
            return api._json_error(api._translate_key("auth.invalid_password"), status=401)

        api.clear_failed_logins(client_key)
        resp = api._ok({"authenticated": True, "message": "Authentication successful"})
        resp.set_cookie(
            "goldshop_web_password",
            str(password),
            max_age=60 * 60 * 24 * 30,
            httponly=False,
            samesite="Lax",
        )
        return resp

    @flask_app.route("/api/v1/auth/check")
    def api_v1_auth_check():
        """Verify that the provided X-GoldShop-Password header is valid."""
        return api._ok({"authenticated": True, "message": "Authentication successful"})

    @flask_app.route("/api/health")
    @flask_app.route("/api/v1/health")
    def api_health():
        """System health and database connectivity check."""
        try:
            api._fetch_one("SELECT 1 AS ok")
            db_status = "connected"
        except Exception as e:
            logger.error("Health check DB error: %s", e)
            db_status = f"error: {e}"

        return api._ok(
            {
                "status": "ok" if db_status == "connected" else "degraded",
                "api_mode": "password-protected-api",
                "database": db_status,
            }
        )

    @flask_app.route("/api/v1/dashboard")
    def api_dashboard():
        """Get high-level dashboard metrics, sales trends, and active alerts."""
        days = api._int_arg("days", 30, min_value=1, max_value=365)
        metrics = {}
        sales_trend = []
        purchases_trend = []
        alerts = []

        if hasattr(api, "stats_manager"):
            try:
                metrics = api.stats_manager.get_dashboard_metrics()
                sales_trend = api.stats_manager.get_sales_trend(days=days)
                purchases_trend = api.stats_manager.get_purchases_trend(days=days)
                alerts = api.stats_manager.get_active_alerts()
            except Exception as e:
                logger.warning("Error fetching dashboard metrics: %s", e)

        return api._ok(
            {
                "metrics": metrics,
                "sales_trend": sales_trend,
                "purchases_trend": purchases_trend,
                "alerts": alerts,
            },
            days=days,
        )

    @flask_app.route("/api/v1/market-price/gold", methods=["POST"])
    def api_v1_gold_price_update():
        """Update market gold price by reference metal and recalculate inventory items."""
        payload = api.request.get_json(silent=True)
        if not isinstance(payload, dict):
            return api._json_error(api._translate_key("api.errors.invalid_payload"), status=400)

        try:
            reference_metal_id = int(payload.get("reference_metal_id"))
            new_price = float(payload.get("new_price"))
            raw_target_ids = payload.get("target_metal_ids")
            if not isinstance(raw_target_ids, list):
                raise ValueError
            target_metal_ids = list(dict.fromkeys(int(value) for value in raw_target_ids))
        except (TypeError, ValueError):
            return api._json_error(api._translate_key("api.errors.invalid_price_update"), status=400)

        if new_price <= 0 or new_price > 1000000 or not target_metal_ids:
            return api._json_error(api._translate_key("api.errors.invalid_price_update"), status=400)

        reference_metal = api._fetch_one(
            """
            SELECT id, name, purity_value, metal_category
            FROM MetalTypes
            WHERE id = %s AND metal_category = 'GOLD'
            """,
            (reference_metal_id,),
        )
        placeholders = ",".join(["%s"] * len(target_metal_ids))
        target_metals = api._fetch_rows(
            f"""
            SELECT id, name, purity_value, metal_category
            FROM MetalTypes
            WHERE id IN ({placeholders}) AND metal_category = 'GOLD'
            ORDER BY purity_value DESC, name ASC
            """,
            target_metal_ids,
        )
        if not reference_metal or len(target_metals) != len(target_metal_ids):
            return api._json_error(api._translate_key("api.errors.gold_metals_only"), status=400)

        raw_update_currency = payload.get("update_currency", True)
        update_currency = (
            str(raw_update_currency).strip().lower() in {"1", "true", "yes", "on"}
            if isinstance(raw_update_currency, str)
            else bool(raw_update_currency)
        )
        affected = api.inventory_manager.update_market_price_by_reference(
            reference_purity=float(reference_metal["purity_value"]),
            new_price=new_price,
            target_metal_ids=target_metal_ids,
            currency_code="OR" if update_currency else None,
        )
        if affected < 0:
            return api._json_error(api._translate_key("api.errors.price_update_failed"), status=500)

        api.logger.info(
            "Web gold price update completed: reference_metal_id=%s new_price=%s affected=%s",
            reference_metal_id,
            new_price,
            affected,
        )
        return api._ok(
            {
                "affected": affected,
                "new_price": new_price,
                "reference_metal": reference_metal,
                "target_metals": target_metals,
                "currency_updated": update_currency,
            }
        )

    return {
        function.__name__: function
        for function in (
            api_catalog,
            api_v1_auth_status,
            api_v1_auth_login,
            api_v1_auth_check,
            api_health,
            api_dashboard,
            api_v1_gold_price_update,
        )
    }
