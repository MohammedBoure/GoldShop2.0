def register_core_routes(flask_app, api):
    """Register HTML pages and the central sales and inventory API routes."""

    @flask_app.route("/")
    def index():
        return sales_page()

    @flask_app.route("/sales")
    def sales_page():
        return api.render_template("sales.html")

    @flask_app.route("/versements")
    def versements():
        return api.render_template("versements.html")

    @flask_app.route("/inventory")
    def inventory_page():
        return api.render_template("inventory.html")

    @flask_app.route("/finance")
    def finance_page():
        return api.render_template("finance.html")

    @flask_app.route("/api")
    @flask_app.route("/api/v1")
    def api_catalog():
        return api._ok(api._catalog_payload())

    @flask_app.route("/api/v1/auth/check")
    def api_v1_auth_check():
        return api._ok({"authenticated": True})

    @flask_app.route("/api/health")
    @flask_app.route("/api/v1/health")
    def api_health():
        api._fetch_one("SELECT 1 AS ok")
        return api._ok(
            {
                "status": "ok",
                "api_mode": "password-protected-api",
                "database": "connected",
            }
        )

    @flask_app.route("/api/sales")
    def api_sales():
        page = api._int_arg("page", 1, min_value=1)
        per_page = api._int_arg("per_page", 30, min_value=1, max_value=api.MAX_PAGE_SIZE)
        offset = (page - 1) * per_page
        start_date, end_date = api._date_range_args()

        sales_data = api.sale_reader.get_excel_style_transactions_paginated(
            search_text=api._str_arg("search"),
            debt_status=api._str_arg("debt_status", "ALL") or "ALL",
            payment_type=api._str_arg("payment_type", "ALL") or "ALL",
            start_date=start_date,
            end_date=end_date,
            limit=per_page,
            offset=offset,
            source_filter=api._str_arg("source_filter", "ALL") or "ALL",
        )
        return api._json_response(sales_data)

    @flask_app.route("/api/v1/dashboard")
    def api_dashboard():
        days = api._int_arg("days", 30, min_value=1, max_value=365)
        return api._ok(
            {
                "metrics": api.stats_manager.get_dashboard_metrics(),
                "sales_trend": api.stats_manager.get_sales_trend(days=days),
                "purchases_trend": api.stats_manager.get_purchases_trend(days=days),
                "alerts": api.stats_manager.get_active_alerts(),
            },
            days=days,
        )

    @flask_app.route("/api/v1/sales")
    def api_v1_sales():
        page, per_page, offset = api._page_args(default_per_page=30)
        start_date, end_date = api._date_range_args()
        data = api.sale_reader.get_excel_style_transactions_paginated(
            search_text=api._str_arg("search"),
            debt_status=api._str_arg("debt_status", "ALL") or "ALL",
            payment_type=api._str_arg("payment_type", "ALL") or "ALL",
            start_date=start_date,
            end_date=end_date,
            limit=per_page,
            offset=offset,
            source_filter=api._str_arg("source_filter", "ALL") or "ALL",
        )
        return api._ok(
            data,
            page=page,
            per_page=per_page,
            returned=len(data),
            has_more=len(data) == per_page,
        )

    @flask_app.route("/api/v1/sales/<int:sale_id>")
    def api_v1_sale_details(sale_id):
        sale = api.sale_reader.get_sale_details(sale_id)
        if not sale:
            return api._not_found("Sale")
        return api._ok(sale)

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

    @flask_app.route("/api/v1/market-price/gold", methods=["POST"])
    def api_v1_gold_price_update():
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
            index,
            sales_page,
            versements,
            inventory_page,
            finance_page,
            api_catalog,
            api_v1_auth_check,
            api_health,
            api_sales,
            api_dashboard,
            api_v1_sales,
            api_v1_sale_details,
            api_v1_inventory,
            api_v1_inventory_item,
            api_v1_inventory_barcode,
            api_v1_gold_price_update,
        )
    }
