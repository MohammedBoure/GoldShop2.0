def register_operation_routes(flask_app, api):
    """Register finance, service, reference, reporting, and search routes."""

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

    @flask_app.route("/api/v1/repairs")
    def api_v1_repairs():
        page, per_page, offset = api._page_args()
        status_filter = api._str_arg("status") or None
        start_date, end_date = api._date_range_args()
        total = api.repair_manager.get_repairs_count(
            status_filter=status_filter,
            start_date=start_date,
            end_date=end_date,
        )
        data = api.repair_manager.get_all_repairs(
            status_filter=status_filter,
            start_date=start_date,
            end_date=end_date,
            limit=per_page,
            offset=offset,
        )
        return api._ok(
            data,
            page=page,
            per_page=per_page,
            total=total,
            has_more=(page * per_page) < int(total or 0),
        )

    @flask_app.route("/api/v1/repairs/<int:repair_id>")
    def api_v1_repair(repair_id):
        repair = api.repair_manager.get_repair_by_id(repair_id)
        if not repair:
            return api._not_found("Repair")
        return api._ok(repair)

    @flask_app.route("/api/v1/repairs/stats")
    def api_v1_repair_stats():
        start_date, end_date = api._date_range_args()
        return api._ok(
            api.repair_manager.get_repair_statistics(
                start_date=start_date,
                end_date=end_date,
            )
        )

    @flask_app.route("/api/v1/treasury/locations")
    def api_v1_treasury_locations():
        data = api.treasury_manager.get_all_locations(
            type_filter=api._str_arg("type") or None,
            only_active=not api._bool_arg("include_inactive", False),
        )
        return api._ok(data, total=len(data))

    @flask_app.route("/api/v1/treasury/balances")
    def api_v1_treasury_balances():
        return api._ok(api.treasury_manager.get_all_balances())

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

    @flask_app.route("/api/v1/reports/daily")
    def api_v1_report_daily():
        day = api._str_arg("date") or api.date.today().isoformat()
        return api._ok(api.reports_manager.get_daily_summary(day), date=day)

    @flask_app.route("/api/v1/reports/range")
    def api_v1_report_range():
        start_date = api._str_arg("start_date") or api.date.today().isoformat()
        end_date = api._str_arg("end_date") or start_date
        return api._ok(
            api.reports_manager.get_custom_range_summary(start_date, end_date),
            start_date=start_date,
            end_date=end_date,
        )

    @flask_app.route("/api/v1/reports/monthly")
    def api_v1_report_monthly():
        today = api.date.today()
        year = api._int_arg("year", today.year, min_value=2000, max_value=2100)
        month = api._int_arg("month", today.month, min_value=1, max_value=12)
        return api._ok(api.reports_manager.get_monthly_summary(year, month), year=year, month=month)

    @flask_app.route("/api/v1/search")
    def api_v1_search():
        query = api._str_arg("q")
        if not query:
            return api._ok({"clients": [], "inventory": [], "suppliers": [], "sales": []})

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
            },
            q=query,
            limit=limit,
        )

    return {
        function.__name__: function
        for function in (
            api_v1_expenses,
            api_v1_repairs,
            api_v1_repair,
            api_v1_repair_stats,
            api_v1_treasury_locations,
            api_v1_treasury_balances,
            api_v1_treasury_transactions,
            api_v1_references,
            api_v1_reference,
            api_v1_report_daily,
            api_v1_report_range,
            api_v1_report_monthly,
            api_v1_search,
        )
    }
