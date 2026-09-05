# web/routes/operations.py

import logging
from datetime import date, datetime

logger = logging.getLogger("JEWELLERY_SYS")


def register_operation_routes(flask_app, api):
    """Register sales, inventory, clients, treasury, coffre, expenses, references, and search routes."""

    # -------------------------------------------------------------------------
    # Sales
    # -------------------------------------------------------------------------
    @flask_app.route("/api/sales")
    @flask_app.route("/api/v1/sales")
    def api_v1_sales():
        page, per_page, offset = api._page_args(default_per_page=30)
        start_date, end_date = api._date_range_args()
        search = api._str_arg("search")
        payment_status = api._str_arg("payment_status")

        base_query = """
            FROM Sales s
            LEFT JOIN Clients c ON s.client_id = c.id
            LEFT JOIN Users u ON s.user_id = u.id
            WHERE 1=1
        """
        params = []
        if start_date:
            base_query += " AND DATE(s.created_at) >= %s"
            params.append(start_date)
        if end_date:
            base_query += " AND DATE(s.created_at) <= %s"
            params.append(end_date)
        if payment_status and payment_status.upper() != "ALL":
            base_query += " AND s.payment_status = %s"
            params.append(payment_status)
        if search:
            base_query += " AND (s.receipt_number LIKE %s OR c.name LIKE %s OR c.phone LIKE %s OR s.notes LIKE %s)"
            params.extend([f"%{search}%", f"%{search}%", f"%{search}%", f"%{search}%"])

        total_row = api._fetch_one(f"SELECT COUNT(*) AS total {base_query}", params)
        total = int(total_row["total"] or 0) if total_row else 0

        rows = api._fetch_rows(
            f"""
            SELECT s.*, c.name AS client_name, c.phone AS client_phone,
                   u.username AS seller_name
            {base_query}
            ORDER BY s.created_at DESC, s.id DESC
            LIMIT %s OFFSET %s
            """,
            [*params, per_page, offset],
        )
        return api._ok(
            rows,
            page=page,
            per_page=per_page,
            total=total,
            returned=len(rows),
            has_more=(page * per_page) < total,
        )

    @flask_app.route("/api/v1/sales/<int:sale_id>")
    def api_v1_sale_details(sale_id):
        sale = None
        if hasattr(api, "sales_manager"):
            sale = api.sales_manager.get_sale_details(sale_id)
        elif hasattr(api, "data_manager"):
            sale = api.data_manager.sales.get_sale_details(sale_id)
        if not sale:
            return api._not_found("Sale")
        return api._ok(sale)

    # -------------------------------------------------------------------------
    # Inventory
    # -------------------------------------------------------------------------
    @flask_app.route("/api/v1/inventory")
    def api_v1_inventory():
        page, per_page, offset = api._page_args()
        items, total_count, total_weight = api.inventory_manager.get_inventory_paginated(
            limit=per_page,
            offset=offset,
            search_text=api._str_arg("search") or None,
            show_zero_stock=api._bool_arg("show_zero_stock", False),
            category_id=api._int_arg("category_id"),
            metal_type_id=api._int_arg("metal_type_id"),
            location_id=api._int_arg("location_id"),
            sort_col=api._int_arg("sort_col", 0, min_value=0),
            sort_dir=api._str_arg("sort_dir", "DESC") or "DESC",
            status_filter=api._str_arg("status", "ALL") or "ALL",
            min_weight=api._float_arg("min_weight"),
            max_weight=api._float_arg("max_weight"),
        )
        return api._ok(
            items,
            page=page,
            per_page=per_page,
            total=total_count,
            total_weight=total_weight,
            has_more=(page * per_page) < int(total_count or 0),
        )

    @flask_app.route("/api/v1/inventory/<int:item_id>")
    def api_v1_inventory_item(item_id):
        item = api.inventory_manager.get_item_by_id(item_id)
        if not item:
            return api._not_found("Inventory item")
        return api._ok(item)

    @flask_app.route("/api/v1/inventory/barcode/<path:barcode>")
    def api_v1_inventory_barcode(barcode):
        item = api.inventory_manager.get_item_by_barcode(barcode)
        if not item:
            return api._not_found("Inventory item")
        return api._ok(item)

    # -------------------------------------------------------------------------
    # Clients
    # -------------------------------------------------------------------------
    @flask_app.route("/api/v1/clients")
    def api_v1_clients():
        page, per_page, offset = api._page_args()
        search = api._str_arg("search")
        data = api.client_manager.get_clients_paginated(
            search_text=search,
            limit=per_page,
            offset=offset,
        )

        params = []
        where = ""
        if search:
            where = "WHERE c.name LIKE %s OR c.phone LIKE %s"
            params.extend([f"%{search}%", f"%{search}%"])
        total_row = api._fetch_one(f"SELECT COUNT(*) AS total FROM Clients c {where}", params)
        total = int(total_row["total"] or 0) if total_row else 0

        return api._ok(
            data,
            page=page,
            per_page=per_page,
            total=total,
            has_more=(page * per_page) < total,
        )

    @flask_app.route("/api/v1/clients/<int:client_id>")
    def api_v1_client(client_id):
        client = api.client_manager.get_client_by_id(client_id)
        if not client:
            return api._not_found("Client")
        return api._ok(client)

    @flask_app.route("/api/v1/clients/<int:client_id>/balances")
    def api_v1_client_balances(client_id):
        if not api.client_manager.get_client_by_id(client_id):
            return api._not_found("Client")
        return api._ok(api.client_manager.get_client_current_balances(client_id))

    @flask_app.route("/api/v1/clients/<int:client_id>/sales")
    def api_v1_client_sales(client_id):
        page, per_page, offset = api._page_args()
        if not api.client_manager.get_client_by_id(client_id):
            return api._not_found("Client")
        rows = api._fetch_rows(
            """
            SELECT s.*, c.name AS client_name
            FROM Sales s
            LEFT JOIN Clients c ON s.client_id = c.id
            WHERE s.client_id = %s
            ORDER BY s.sale_date DESC
            LIMIT %s OFFSET %s
            """,
            (client_id, per_page, offset),
        )
        total_row = api._fetch_one(
            "SELECT COUNT(*) AS total FROM Sales WHERE client_id = %s",
            (client_id,),
        )
        total = int(total_row["total"] or 0) if total_row else 0
        return api._ok(
            rows,
            page=page,
            per_page=per_page,
            total=total,
            has_more=(page * per_page) < total,
        )

    # -------------------------------------------------------------------------
    # Expenses
    # -------------------------------------------------------------------------
    @flask_app.route("/api/v1/expenses")
    def api_v1_expenses():
        page, per_page, offset = api._page_args()
        base_query = """
            FROM Expenses e
            LEFT JOIN ExpenseCategories ec ON e.expense_category_id = ec.id
            LEFT JOIN TreasuryLocations l ON e.location_id = l.id
            LEFT JOIN Currencies c ON e.currency_id = c.id
            WHERE 1=1
        """
        params = []
        start_date = api._str_arg("start_date")
        end_date = api._str_arg("end_date")
        expense_type = api._str_arg("expense_type")
        category_id = api._int_arg("category_id")
        location_id = api._int_arg("location_id")
        currency_id = api._int_arg("currency_id")
        search = api._str_arg("search")

        if start_date:
            base_query += " AND DATE(e.expense_date) >= %s"
            params.append(start_date)
        if end_date:
            base_query += " AND DATE(e.expense_date) <= %s"
            params.append(end_date)
        if expense_type and expense_type.lower() != "all":
            base_query += " AND e.expense_type = %s"
            params.append(expense_type)
        if category_id:
            base_query += " AND e.expense_category_id = %s"
            params.append(category_id)
        if location_id:
            base_query += " AND e.location_id = %s"
            params.append(location_id)
        if currency_id:
            base_query += " AND e.currency_id = %s"
            params.append(currency_id)
        if search:
            base_query += " AND (e.description LIKE %s OR e.beneficiary_name LIKE %s OR ec.name LIKE %s)"
            params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])

        total_row = api._fetch_one(f"SELECT COUNT(*) AS total {base_query}", params)
        total = int(total_row["total"] or 0) if total_row else 0
        data = api._fetch_rows(
            f"""
            SELECT e.*, ec.name AS category_name, l.name AS location_name,
                   c.code AS currency_code, c.symbol AS currency_symbol
            {base_query}
            ORDER BY e.expense_date DESC
            LIMIT %s OFFSET %s
            """,
            [*params, per_page, offset],
        )
        return api._ok(
            data,
            page=page,
            per_page=per_page,
            total=total,
            has_more=(page * per_page) < total,
        )

    # -------------------------------------------------------------------------
    # Treasury Locations & Balances
    # -------------------------------------------------------------------------
    @flask_app.route("/api/v1/treasury/locations")
    def api_v1_treasury_locations():
        type_filter = api._str_arg("type")
        include_inactive = api._bool_arg("include_inactive", False)
        query = "SELECT * FROM TreasuryLocations WHERE 1=1"
        params = []
        if type_filter:
            query += " AND type = %s"
            params.append(type_filter)
        if not include_inactive:
            query += " AND is_active = 1"
        query += " ORDER BY type ASC, name ASC"
        data = api._fetch_rows(query, params)
        return api._ok(data, total=len(data))

    @flask_app.route("/api/v1/treasury/balances")
    def api_v1_treasury_balances():
        query = """
            SELECT l.id AS location_id, l.name AS location_name, l.type AS location_type,
                   c.id AS currency_id, c.code AS currency_code, c.symbol AS currency_symbol,
                   COALESCE(SUM(CASE WHEN mt.transaction_type = 'IN' THEN mt.amount ELSE -mt.amount END), 0) AS balance
            FROM TreasuryLocations l
            CROSS JOIN Currencies c
            LEFT JOIN MoneyTransactions mt ON mt.location_id = l.id AND mt.currency_id = c.id
            WHERE l.is_active = 1
            GROUP BY l.id, l.name, l.type, c.id, c.code, c.symbol
            ORDER BY l.name ASC, c.code ASC
        """
        data = api._fetch_rows(query)
        return api._ok(data)

    @flask_app.route("/api/v1/treasury/transactions")
    def api_v1_treasury_transactions():
        page, per_page, offset = api._page_args()
        base_query = """
            FROM MoneyTransactions mt
            LEFT JOIN TreasuryLocations l ON mt.location_id = l.id
            LEFT JOIN Currencies c ON mt.currency_id = c.id
            LEFT JOIN Clients cl ON mt.client_id = cl.id
            WHERE 1=1
        """
        params = []
        location_id = api._int_arg("location_id")
        currency_id = api._int_arg("currency_id")
        start_date = api._str_arg("start_date")
        end_date = api._str_arg("end_date")
        transaction_type = api._str_arg("transaction_type")

        if location_id:
            base_query += " AND mt.location_id = %s"
            params.append(location_id)
        if currency_id:
            base_query += " AND mt.currency_id = %s"
            params.append(currency_id)
        if transaction_type:
            base_query += " AND mt.transaction_type = %s"
            params.append(transaction_type)
        if start_date:
            base_query += " AND DATE(mt.transaction_date) >= %s"
            params.append(start_date)
        if end_date:
            base_query += " AND DATE(mt.transaction_date) <= %s"
            params.append(end_date)

        total_row = api._fetch_one(f"SELECT COUNT(*) AS total {base_query}", params)
        total = int(total_row["total"] or 0) if total_row else 0
        data = api._fetch_rows(
            f"""
            SELECT mt.*, l.name AS location_name, c.code AS currency_code,
                   c.symbol AS currency_symbol, cl.name AS client_name
            {base_query}
            ORDER BY mt.transaction_date DESC, mt.id DESC
            LIMIT %s OFFSET %s
            """,
            [*params, per_page, offset],
        )
        return api._ok(
            data,
            page=page,
            per_page=per_page,
            total=total,
            has_more=(page * per_page) < total,
        )

    # -------------------------------------------------------------------------
    # Coffre Magasin (Central Vault)
    # -------------------------------------------------------------------------
    @flask_app.route("/api/v1/coffre/operations")
    def api_v1_coffre_operations():
        """Retrieve operations from CoffreMagasin with 9 columns matching CoffreMagasinView."""
        page, per_page, offset = api._page_args(default_per_page=100)
        year = api._int_arg("year")
        month = api._int_arg("month")
        search = api._str_arg("search", "").lower().strip()

        base_query = "FROM CoffreMagasin WHERE 1=1"
        params = []
        if year:
            base_query += " AND YEAR(date_operation) = %s"
            params.append(year)
        if month:
            base_query += " AND MONTH(date_operation) = %s"
            params.append(month)
        if search:
            base_query += " AND (designation LIKE %s OR date_operation LIKE %s OR montant_da LIKE %s)"
            params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])

        total_row = api._fetch_one(f"SELECT COUNT(*) AS total {base_query}", params)
        total = int(total_row["total"] or 0) if total_row else 0

        rows = api._fetch_rows(
            f"""
            SELECT id, date_operation, montant_da, oc_or, oc_argent, tpe, ccp, euro, dollar, designation
            {base_query}
            ORDER BY date_operation DESC, id DESC
            LIMIT %s OFFSET %s
            """,
            [*params, per_page, offset],
        )
        return api._ok(
            rows,
            page=page,
            per_page=per_page,
            total=total,
            has_more=(page * per_page) < total,
        )

    @flask_app.route("/api/v1/coffre/balances")
    def api_v1_coffre_balances():
        """Aggregated total balances in the store vault (CoffreMagasin)."""
        row = api._fetch_one(
            """
            SELECT 
                SUM(CAST(montant_da AS DECIMAL(15,2))) AS total_especes_da,
                SUM(CAST(oc_or AS DECIMAL(15,3))) AS total_oc_or_g,
                SUM(CAST(oc_argent AS DECIMAL(15,3))) AS total_oc_argent_g,
                SUM(CAST(tpe AS DECIMAL(15,2))) AS total_tpe_da,
                SUM(CAST(ccp AS DECIMAL(15,2))) AS total_ccp_da,
                SUM(CAST(euro AS DECIMAL(15,2))) AS total_euro,
                SUM(CAST(dollar AS DECIMAL(15,2))) AS total_dollar
            FROM CoffreMagasin
            """
        )
        return api._ok(row or {})

    # -------------------------------------------------------------------------
    # References & Search
    # -------------------------------------------------------------------------
    @flask_app.route("/api/v1/references")
    def api_v1_references():
        return api._ok({name: api._reference_rows(name) for name in sorted(api.REFERENCE_TABLES)})

    @flask_app.route("/api/v1/references/<path:name>")
    def api_v1_reference(name):
        limit = api._int_arg("limit", None, min_value=1, max_value=1000)
        rows = api._reference_rows(name, limit=limit)
        if rows is None:
            return api._not_found("Reference set")
        return api._ok(rows, name=api._reference_key(name), total=len(rows))

    @flask_app.route("/api/v1/search")
    def api_v1_search():
        query = api._str_arg("q")
        if not query:
            return api._ok({"clients": [], "inventory": [], "suppliers": [], "sales": [], "versements": [], "artisan_orders": []})

        limit = api._int_arg("limit", 10, min_value=1, max_value=50)
        pattern = f"%{query}%"
        return api._ok(
            {
                "clients": api._fetch_rows(
                    """
                    SELECT id, name, phone, address
                    FROM Clients
                    WHERE name LIKE %s OR phone LIKE %s
                    ORDER BY name ASC
                    LIMIT %s
                    """,
                    (pattern, pattern, limit),
                ),
                "inventory": api._fetch_rows(
                    """
                    SELECT i.id, i.barcode, i.name, i.status, i.selling_price,
                           c.name AS category_name, mt.name AS metal_type_name
                    FROM Inventory i
                    LEFT JOIN Categories c ON i.category_id = c.id
                    LEFT JOIN MetalTypes mt ON i.metal_type_id = mt.id
                    WHERE i.name LIKE %s OR i.barcode LIKE %s
                    ORDER BY i.id DESC
                    LIMIT %s
                    """,
                    (pattern, pattern, limit),
                ),
                "suppliers": api._fetch_rows(
                    """
                    SELECT id, name, phone, supplier_type, is_active
                    FROM Suppliers
                    WHERE name LIKE %s OR phone LIKE %s
                    ORDER BY name ASC
                    LIMIT %s
                    """,
                    (pattern, pattern, limit),
                ),
                "sales": api._fetch_rows(
                    """
                    SELECT s.id, s.sale_date, s.final_amount, s.payment_status,
                           c.name AS client_name
                    FROM Sales s
                    LEFT JOIN Clients c ON s.client_id = c.id
                    WHERE CAST(s.id AS CHAR) LIKE %s OR c.name LIKE %s
                    ORDER BY s.sale_date DESC
                    LIMIT %s
                    """,
                    (pattern, pattern, limit),
                ),
                "versements": api._fetch_rows(
                    """
                    SELECT v.id, v.status, v.total_weight_g, v.reste_poids_g, c.name AS client_name, c.phone AS client_phone
                    FROM Versements v
                    LEFT JOIN Clients c ON v.client_id = c.id
                    WHERE CAST(v.id AS CHAR) LIKE %s OR c.name LIKE %s OR c.phone LIKE %s
                    ORDER BY v.id DESC
                    LIMIT %s
                    """,
                    (pattern, pattern, pattern, limit),
                ),
                "artisan_orders": api._fetch_rows(
                    """
                    SELECT awo.id, awo.numero, awo.obj, awo.status, c.name AS client_name, a.name AS artisan_name
                    FROM ArtisanWorkOrders awo
                    LEFT JOIN Clients c ON awo.client_id = c.id
                    LEFT JOIN Artisans a ON awo.artisan_id = a.id
                    WHERE awo.numero LIKE %s OR awo.obj LIKE %s OR c.name LIKE %s OR a.name LIKE %s
                    ORDER BY awo.id DESC
                    LIMIT %s
                    """,
                    (pattern, pattern, pattern, pattern, limit),
                ),
            },
            q=query,
            limit=limit,
        )

    return {
        function.__name__: function
        for function in (
            api_v1_sales,
            api_v1_sale_details,
            api_v1_inventory,
            api_v1_inventory_item,
            api_v1_inventory_barcode,
            api_v1_clients,
            api_v1_client,
            api_v1_client_balances,
            api_v1_client_sales,
            api_v1_expenses,
            api_v1_treasury_locations,
            api_v1_treasury_balances,
            api_v1_treasury_transactions,
            api_v1_coffre_operations,
            api_v1_coffre_balances,
            api_v1_references,
            api_v1_reference,
            api_v1_search,
        )
    }
