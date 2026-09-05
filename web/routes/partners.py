# web/routes/partners.py

from web.routes.suppliers import register_suppliers_routes


def register_partner_routes(flask_app, api):
    """
    Backward compatibility adapter.
    Delegates supplier routes to web.routes.suppliers.
    """
    return register_suppliers_routes(flask_app, api)
