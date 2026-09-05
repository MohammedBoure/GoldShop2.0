# web/routes/ui.py

from datetime import date
import logging
from flask import render_template
from config import load_full_config
from web.security import web_password_configured

logger = logging.getLogger("JEWELLERY_SYS")


def register_ui_routes(flask_app, api):
    """Register mobile web interface routes for GoldShop 2.0."""

    def _get_common_context(active_tab):
        try:
            cfg = load_full_config()
            shop_name = cfg.get("shop_name", "Bijouterie GoldShop")
        except Exception:
            shop_name = "Bijouterie GoldShop"

        today = date.today()
        return {
            "shop_name": shop_name,
            "active_tab": active_tab,
            "today_date": today.isoformat(),
            "current_year": today.year,
            "current_month": today.month,
            "web_auth_configured": web_password_configured(),
        }

    @flask_app.route("/")
    def view_dashboard():
        """Render mobile home & quick navigation dashboard."""
        return render_template("index.html", **_get_common_context("dashboard"))

    @flask_app.route("/journal")
    def view_journal():
        """Render daily sales & cash journal matching excel_journal_view.py."""
        return render_template("journal.html", **_get_common_context("journal"))

    @flask_app.route("/monthly-summary")
    def view_monthly_summary():
        """Render monthly sales, revenue and profit summary matching monthly_summary_view.py."""
        return render_template("monthly_summary.html", **_get_common_context("monthly"))

    @flask_app.route("/versements")
    def view_versements():
        """Render layaways, reservations and payments matching versements_view.py."""
        return render_template("versements.html", **_get_common_context("versements"))

    @flask_app.route("/artisan-work")
    def view_artisan_work():
        """Render workshop production orders and artisan ledger matching artisan_work_view.py."""
        return render_template("artisan_work.html", **_get_common_context("artisan"))

    @flask_app.route("/suppliers")
    def view_suppliers():
        """Render French supplier Excel ledger and accounts matching suppliers_view.py."""
        return render_template("suppliers.html", **_get_common_context("suppliers"))

    return {
        function.__name__: function
        for function in (
            view_dashboard,
            view_journal,
            view_monthly_summary,
            view_versements,
            view_artisan_work,
            view_suppliers,
        )
    }
