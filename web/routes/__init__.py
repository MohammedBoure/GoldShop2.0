# web/routes/__init__.py
"""Flask route registration modules for GoldShop 2.0 Web API."""

from .core import register_core_routes
from .reports import register_reports_routes
from .versements import register_versements_routes
from .artisan_work import register_artisan_work_routes
from .suppliers import register_suppliers_routes
from .operations import register_operation_routes
from .partners import register_partner_routes
from .ui import register_ui_routes

__all__ = [
    "register_core_routes",
    "register_reports_routes",
    "register_versements_routes",
    "register_artisan_work_routes",
    "register_suppliers_routes",
    "register_operation_routes",
    "register_partner_routes",
    "register_ui_routes",
]
