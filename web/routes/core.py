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

    return {
        function.__name__: function
        for function in (
            api_catalog,
            api_v1_auth_status,
            api_v1_auth_login,
            api_v1_auth_check,
            api_health,
            api_dashboard,
        )
    }
