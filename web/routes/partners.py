def register_partner_routes(flask_app, api):
    """Register client, supplier, and client payment query routes."""

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

    @flask_app.route("/api/v1/clients/<int:client_id>/payments")
    def api_v1_client_payments(client_id):
        if not api.client_manager.get_client_by_id(client_id):
            return api._not_found("Client")
        return api._ok(api.payment_manager.get_payments_by_client(client_id))

    @flask_app.route("/api/v1/clients/<int:client_id>/unpaid-sales")
    def api_v1_client_unpaid_sales(client_id):
        if not api.client_manager.get_client_by_id(client_id):
            return api._not_found("Client")
        return api._ok(api.sale_reader.get_unpaid_items_for_client(client_id))

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

    @flask_app.route("/api/v1/suppliers")
    def api_v1_suppliers():
        page, per_page, offset = api._page_args()
        search = api._str_arg("search").lower()
        suppliers = api.supplier_manager.get_all_suppliers()
        if search:
            suppliers = [
                item
                for item in suppliers
                if search in str(item.get("name", "")).lower()
                or search in str(item.get("phone", "")).lower()
            ]
        total = len(suppliers)
        data = suppliers[offset : offset + per_page]
        return api._ok(
            data,
            page=page,
            per_page=per_page,
            total=total,
            has_more=(page * per_page) < total,
        )

    @flask_app.route("/api/v1/suppliers/<int:supplier_id>")
    def api_v1_supplier(supplier_id):
        supplier = api._fetch_one(
            """
            SELECT s.*, mt.name AS base_metal_type_name
            FROM Suppliers s
            LEFT JOIN MetalTypes mt ON s.base_metal_type_id = mt.id
            WHERE s.id = %s
            """,
            (supplier_id,),
        )
        if not supplier:
            return api._not_found("Supplier")
        return api._ok(supplier)

    @flask_app.route("/api/v1/suppliers/<int:supplier_id>/balances")
    def api_v1_supplier_balances(supplier_id):
        if not api._fetch_one("SELECT id FROM Suppliers WHERE id = %s", (supplier_id,)):
            return api._not_found("Supplier")
        return api._ok(api.supplier_manager.get_supplier_current_balances(supplier_id))

    @flask_app.route("/api/v1/suppliers/<int:supplier_id>/history")
    def api_v1_supplier_history(supplier_id):
        if not api._fetch_one("SELECT id FROM Suppliers WHERE id = %s", (supplier_id,)):
            return api._not_found("Supplier")
        start_date, end_date = api._date_range_args()
        data = api.supplier_manager.get_supplier_history(
            supplier_id,
            start_date=start_date,
            end_date=end_date,
        )
        return api._ok(data, total=len(data))

    @flask_app.route("/api/v1/payments")
    def api_v1_payments():
        page, per_page, offset = api._page_args()
        base_query = """
            FROM ClientPayments cp
            JOIN Clients c ON cp.client_id = c.id
            LEFT JOIN Inventory i ON cp.inventory_id = i.id
            LEFT JOIN VersementOperations vo ON cp.versement_operation_id = vo.id
            WHERE 1=1
        """
        params = []
        search = api._str_arg("search")
        client_id = api._int_arg("client_id")
        sale_id = api._int_arg("sale_id")
        payment_type = api._str_arg("payment_type")
        start_date = api._str_arg("start_date")
        end_date = api._str_arg("end_date")

        if search:
            base_query += " AND (c.name LIKE %s OR cp.notes LIKE %s OR i.name LIKE %s)"
            params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
        if client_id:
            base_query += " AND cp.client_id = %s"
            params.append(client_id)
        if sale_id:
            base_query += " AND cp.sale_id = %s"
            params.append(sale_id)
        if payment_type:
            base_query += " AND cp.payment_type = %s"
            params.append(payment_type)
        if start_date:
            base_query += " AND DATE(cp.payment_date) >= %s"
            params.append(start_date)
        if end_date:
            base_query += " AND DATE(cp.payment_date) <= %s"
            params.append(end_date)

        total_row = api._fetch_one(f"SELECT COUNT(*) AS total {base_query}", params)
        total = int(total_row["total"] or 0) if total_row else 0

        data = api._fetch_rows(
            f"""
            SELECT cp.*, c.name AS client_name, i.name AS product_name,
                   COALESCE(
                       vo.operation_number,
                       CONCAT('VRS-', LPAD(cp.versement_operation_id, 6, '0'))
                   ) AS operation_number
            {base_query}
            ORDER BY cp.payment_date DESC
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

    return {
        function.__name__: function
        for function in (
            api_v1_clients,
            api_v1_client,
            api_v1_client_balances,
            api_v1_client_payments,
            api_v1_client_unpaid_sales,
            api_v1_client_sales,
            api_v1_suppliers,
            api_v1_supplier,
            api_v1_supplier_balances,
            api_v1_supplier_history,
            api_v1_payments,
        )
    }
