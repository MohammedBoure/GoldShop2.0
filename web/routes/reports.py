# web/routes/reports.py

import calendar
import logging
from datetime import date, datetime

logger = logging.getLogger("JEWELLERY_SYS")

FRENCH_DAYS = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
FRENCH_MONTHS = [
    "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
    "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"
]


def safe_float(val):
    try:
        return float(str(val).replace(" ", "").replace(",", "."))
    except (ValueError, TypeError):
        return 0.0


def format_french_date(date_obj) -> str:
    """Format a date object into a French date string: e.g. 'Lundi 25 Mai 2026'."""
    if not date_obj:
        return ""
    if isinstance(date_obj, str):
        try:
            date_obj = datetime.strptime(date_obj.split("T")[0].split(" ")[0], "%Y-%m-%d").date()
        except Exception:
            return date_obj
    if hasattr(date_obj, "date") and callable(date_obj.date):
        date_obj = date_obj.date()
    day_name = FRENCH_DAYS[date_obj.weekday()]
    month_name = FRENCH_MONTHS[date_obj.month - 1]
    return f"{day_name} {date_obj.day:02d} {month_name} {date_obj.year}"


def get_french_day_name(date_obj) -> str:
    """Get the French day name (e.g. 'Lundi', 'Mardi')."""
    if not date_obj:
        return ""
    if isinstance(date_obj, str):
        try:
            date_obj = datetime.strptime(date_obj.split("T")[0].split(" ")[0], "%Y-%m-%d").date()
        except Exception:
            return ""
    if hasattr(date_obj, "date") and callable(date_obj.date):
        date_obj = date_obj.date()
    return FRENCH_DAYS[date_obj.weekday()]


def register_reports_routes(flask_app, api):
    """
    Register reporting routes that provide complete data structures for:
    1. ui/widgets/reports/excel_journal_view.py (Excel Journal View)
    2. ui/widgets/reports/monthly_summary_view.py (Monthly Summary View)
    """

    # -------------------------------------------------------------------------
    # 1. EXCEL JOURNAL VIEW API (ui/widgets/reports/excel_journal_view.py)
    # -------------------------------------------------------------------------

    @flask_app.route("/api/v1/reports/journal/sellers")
    def api_v1_journal_sellers():
        """
        Return the list of sellers (Users) for the Excel Journal seller filter dropdown.
        Matches ExcelJournalView.load_sellers_combo.
        """
        try:
            sellers = api._fetch_rows(
                """
                SELECT id, username, COALESCE(full_name, username) AS full_name
                FROM Users
                ORDER BY username ASC
                """
            )
            return api._ok(sellers or [])
        except Exception as exc:
            logger.error("Error fetching journal sellers: %s", exc)
            return api._json_error(str(exc), status=500)

    @flask_app.route("/api/v1/reports/journal")
    def api_v1_reports_journal():
        """
        Comprehensive Daily Sales & Receipts Journal API.
        Powers ui/widgets/reports/excel_journal_view.py.

        Query Parameters:
        - year (int): Year filter (defaults to current year)
        - month (int): Month filter (defaults to current month)
        - day (int, optional): Day filter (1-31)
        - search (str, optional): Search across client name, receipt, designation, notes
        - seller_id (int, optional): Filter by seller ID
        - seller_name (str, optional): Filter by seller username
        """
        today = date.today()
        year = api._int_arg("year", today.year, min_value=2000, max_value=2100)
        month = api._int_arg("month", today.month, min_value=1, max_value=12)
        day = api._int_arg("day", None, min_value=1, max_value=31)
        search_text = api._str_arg("search", "").lower().strip()
        seller_id = api._int_arg("seller_id", 0)
        seller_name = api._str_arg("seller_name", "").strip()

        # If seller_id is given but not seller_name, resolve seller_name
        if seller_id > 0 and not seller_name:
            user_row = api._fetch_one("SELECT username FROM Users WHERE id = %s", (seller_id,))
            if user_row:
                seller_name = user_row.get("username", "")

        try:
            # 1. Fetch sessions for the requested period
            query_sessions = """
                SELECT id, opened_at, closed_at, starting_cash_da, status, notes
                FROM DailySessions
                WHERE YEAR(opened_at) = %s AND MONTH(opened_at) = %s
            """
            params = [year, month]
            if day and day > 0:
                query_sessions += " AND DAY(opened_at) = %s"
                params.append(day)
            query_sessions += " ORDER BY opened_at ASC"

            sessions = api._fetch_rows(query_sessions, params)
            if not sessions:
                return api._ok(
                    {
                        "year": year,
                        "month": month,
                        "day": day,
                        "month_name": FRENCH_MONTHS[month - 1],
                        "sessions": [],
                        "grand_totals": {
                            "ps_gold": 0.0,
                            "ps_silver": 0.0,
                            "recette": 0.0,
                            "oc_gold": 0.0,
                            "oc_silver": 0.0,
                            "tpe": 0.0,
                            "euro": 0.0,
                            "dollar": 0.0,
                        },
                    }
                )

            session_ids = [s["id"] for s in sessions]

            # 2. Fetch bulk receipts for all sessions (Sales, Versements, Repairs)
            all_bulk_receipts = {}
            if hasattr(api, "sales_manager") and hasattr(api.sales_manager, "get_bulk_sales_for_excel"):
                all_bulk_receipts = api.sales_manager.get_bulk_sales_for_excel(session_ids)
            elif hasattr(api, "data_manager") and hasattr(api.data_manager.sales, "get_bulk_sales_for_excel"):
                all_bulk_receipts = api.data_manager.sales.get_bulk_sales_for_excel(session_ids)

            result_sessions = []
            g_ps_gold = g_ps_silver = 0.0
            g_rec = g_oc_gold = g_oc_silver = g_tpe = g_euro = g_dollar = 0.0

            for session in sessions:
                journee_id = session["id"]
                opened_at = session["opened_at"]
                fc_amount = float(session.get("starting_cash_da") or 0.0)

                raw_receipts = all_bulk_receipts.get(journee_id, [])
                filtered_receipts = []

                for r in raw_receipts:
                    obs = str(r.get("Observation", "")).lower()
                    des = str(r.get("Designation", "")).lower()
                    c_name = str(r.get("client_name", "")).lower()
                    rec_num = str(r.get("receipt_number", "")).lower()
                    bc = str(r.get("barcode", "")).lower()
                    vend = str(r.get("Vendeur_Name") or r.get("Vendeur_Sofiane", ""))
                    v_id = r.get("vendeur_id")

                    if search_text and not any(
                        search_text in field for field in (obs, des, c_name, rec_num, bc)
                    ):
                        continue

                    if seller_id > 0 and v_id != seller_id and vend != seller_name:
                        continue

                    filtered_receipts.append(r)

                # If a search/filter was applied and this session had no matching receipts, skip it
                if not filtered_receipts and (search_text or seller_id > 0):
                    continue

                t_ps_gold = t_ps_silver = 0.0
                t_rec = t_oc_gold = t_oc_silver = t_tpe = t_euro = t_dollar = 0.0

                processed_receipts = []
                for r in filtered_receipts:
                    metal_cat = str(r.get("metal_category") or "GOLD").upper()
                    p_s_val = float(r.get("P_S") or 0.0)
                    if metal_cat == "SILVER":
                        t_ps_silver += p_s_val
                    else:
                        t_ps_gold += p_s_val

                    oc_gold_val = float(
                        r.get("OC_Gold") if "OC_Gold" in r else (r.get("OC") or 0.0)
                    )
                    oc_silver_val = float(r.get("OC_Silver") or 0.0)
                    t_oc_gold += oc_gold_val
                    t_oc_silver += oc_silver_val

                    rec_val = float(r.get("Recette") or 0.0)
                    tpe_val = float(r.get("TPE") or 0.0)
                    euro_val = float(r.get("Euro") or 0.0)
                    dollar_val = float(r.get("Dollar") or 0.0)

                    t_rec += rec_val
                    t_tpe += tpe_val
                    t_euro += euro_val
                    t_dollar += dollar_val

                    # Formatting helpers matching excel_journal_view
                    ps_str = f"{p_s_val:.2f} Ag" if (metal_cat == "SILVER" and p_s_val > 0) else f"{p_s_val:.2f}"
                    if oc_gold_val > 0 and oc_silver_val > 0:
                        oc_str = f"{oc_gold_val:.2f} / {oc_silver_val:.2f} Ag"
                    elif oc_silver_val > 0:
                        oc_str = f"{oc_silver_val:.2f} Ag"
                    elif oc_gold_val > 0:
                        oc_str = f"{oc_gold_val:.2f}"
                    else:
                        oc_str = "0"

                    rec_str = f"{rec_val:.0f}" if rec_val != 0 else ";"

                    processed_receipts.append(
                        {
                            "sale_id": r.get("sale_id"),
                            "item_id": r.get("item_id"),
                            "receipt_number": r.get("receipt_number"),
                            "barcode": r.get("barcode", ""),
                            "client_name": r.get("client_name", ""),
                            "designation": r.get("Designation", ""),
                            "metal_category": metal_cat,
                            "p_s": p_s_val,
                            "p_s_formatted": ps_str,
                            "recette": rec_val,
                            "recette_formatted": rec_str,
                            "oc_gold": oc_gold_val,
                            "oc_silver": oc_silver_val,
                            "oc_formatted": oc_str,
                            "tpe": tpe_val,
                            "euro": euro_val,
                            "dollar": dollar_val,
                            "impos": float(r.get("Impos") or 0.0),
                            "vendeur_name": r.get("Vendeur_Name") or r.get("Vendeur_Sofiane", ""),
                            "vendeur_id": r.get("vendeur_id"),
                            "observation": r.get("Observation", ""),
                            "raw_notes": r.get("raw_notes", ""),
                            "timestamp": r.get("timestamp"),
                        }
                    )

                g_ps_gold += t_ps_gold
                g_ps_silver += t_ps_silver
                g_rec += t_rec
                g_oc_gold += t_oc_gold
                g_oc_silver += t_oc_silver
                g_tpe += t_tpe
                g_euro += t_euro
                g_dollar += t_dollar

                date_formatted = format_french_date(opened_at)
                result_sessions.append(
                    {
                        "journee_id": journee_id,
                        "opened_at": opened_at,
                        "date_formatted": date_formatted,
                        "starting_cash_da": fc_amount,
                        "starting_cash_formatted": f"Fc : {fc_amount:,.0f} Da" if fc_amount % 1 == 0 else f"Fc : {fc_amount:,.2f} Da",
                        "receipts_count": len(processed_receipts),
                        "receipts": processed_receipts,
                        "totals": {
                            "ps_gold": round(t_ps_gold, 3),
                            "ps_silver": round(t_ps_silver, 3),
                            "recette": round(t_rec, 2),
                            "oc_gold": round(t_oc_gold, 3),
                            "oc_silver": round(t_oc_silver, 3),
                            "tpe": round(t_tpe, 2),
                            "euro": round(t_euro, 2),
                            "dollar": round(t_dollar, 2),
                        },
                    }
                )

            return api._ok(
                {
                    "year": year,
                    "month": month,
                    "day": day,
                    "month_name": FRENCH_MONTHS[month - 1],
                    "sessions_count": len(result_sessions),
                    "sessions": result_sessions,
                    "grand_totals": {
                        "fc": round(sum(safe_float(s.get("fc", s.get("fc_da", 0))) for s in result_sessions), 2),
                        "fc_da": round(sum(safe_float(s.get("fc", s.get("fc_da", 0))) for s in result_sessions), 2),
                        "ps_gold": round(g_ps_gold, 3),
                        "ps_gold_g": round(g_ps_gold, 3),
                        "ps_silver": round(g_ps_silver, 3),
                        "ps_silver_g": round(g_ps_silver, 3),
                        "recette": round(g_rec, 2),
                        "recette_da": round(g_rec, 2),
                        "oc_gold": round(g_oc_gold, 3),
                        "oc_gold_g": round(g_oc_gold, 3),
                        "oc_silver": round(g_oc_silver, 3),
                        "oc_silver_g": round(g_oc_silver, 3),
                        "tpe": round(g_tpe, 2),
                        "tpe_da": round(g_tpe, 2),
                        "euro": round(g_euro, 2),
                        "dollar": round(g_dollar, 2),
                    },
                    "totals": {
                        "fc": round(sum(safe_float(s.get("fc", s.get("fc_da", 0))) for s in result_sessions), 2),
                        "fc_da": round(sum(safe_float(s.get("fc", s.get("fc_da", 0))) for s in result_sessions), 2),
                        "ps_gold": round(g_ps_gold, 3),
                        "ps_gold_g": round(g_ps_gold, 3),
                        "ps_silver": round(g_ps_silver, 3),
                        "ps_silver_g": round(g_ps_silver, 3),
                        "recette": round(g_rec, 2),
                        "recette_da": round(g_rec, 2),
                        "oc_gold": round(g_oc_gold, 3),
                        "oc_gold_g": round(g_oc_gold, 3),
                        "oc_silver": round(g_oc_silver, 3),
                        "oc_silver_g": round(g_oc_silver, 3),
                        "tpe": round(g_tpe, 2),
                        "tpe_da": round(g_tpe, 2),
                        "euro": round(g_euro, 2),
                        "dollar": round(g_dollar, 2),
                    },
                }
            )
        except Exception as exc:
            logger.exception("Error loading Excel Journal report: %s", exc)
            return api._json_error(str(exc), status=500)

    # -------------------------------------------------------------------------
    # 2. MONTHLY SUMMARY VIEW API (ui/widgets/reports/monthly_summary_view.py)
    # -------------------------------------------------------------------------

    @flask_app.route("/api/v1/reports/monthly-summary")
    def api_v1_reports_monthly_summary():
        """
        Comprehensive Monthly Summary & Revenue Synthesis API.
        Powers ui/widgets/reports/monthly_summary_view.py.

        Returns daily aggregated records across:
        - Outgoing sales weights: P.S (Or) & P.S (Argent)
        - Cash revenues: Recettes DA (Sales + Versements + Repairs)
        - Scrap metals: O.C (Or) & O.C (Argent)
        - Electronic payments: TPE DA
        - Foreign currencies: Euro € & Dollar $
        - Profit analytics: Bénéfice / Faaida DA (Sales net profit + Workshop margin diff)
        """
        today = date.today()
        year = api._int_arg("year", today.year, min_value=2000, max_value=2100)
        month = api._int_arg("month", today.month, min_value=1, max_value=12)

        def to_date_key(val):
            if not val:
                return None
            if isinstance(val, datetime):
                return val.date()
            if isinstance(val, date):
                return val
            if isinstance(val, str):
                try:
                    return datetime.strptime(val.split("T")[0].split(" ")[0], "%Y-%m-%d").date()
                except Exception:
                    pass
            return None

        try:
            # 1. Weights from completed sales
            weight_results = api._fetch_rows(
                """
                SELECT 
                    DATE(s.created_at) AS sale_date,
                    SUM(CASE WHEN COALESCE(si.metal_category, mt.metal_category, 'GOLD') = 'GOLD' THEN si.sold_weight_g ELSE 0 END) AS total_ps_gold,
                    SUM(CASE WHEN COALESCE(si.metal_category, mt.metal_category, 'GOLD') = 'SILVER' THEN si.sold_weight_g ELSE 0 END) AS total_ps_silver
                FROM SaleItems si
                JOIN Sales s ON si.sale_id = s.id
                LEFT JOIN Inventory i ON si.inventory_id = i.id
                LEFT JOIN MetalTypes mt ON COALESCE(si.metal_type_id, i.metal_type_id) = mt.id
                WHERE YEAR(s.created_at) = %s AND MONTH(s.created_at) = %s AND s.status = 'COMPLETED'
                GROUP BY DATE(s.created_at)
                """,
                (year, month),
            )
            weights_by_date = {to_date_key(r["sale_date"]): r for r in weight_results if to_date_key(r.get("sale_date"))}

            # 2. Sales amounts (excluding pure layaway markers)
            sales_results = api._fetch_rows(
                """
                SELECT 
                    DATE(s.created_at) AS sale_date,
                    SUM(CASE WHEN s.receipt_number NOT LIKE 'VRS-%%' THEN s.cash_paid_da ELSE 0 END) AS total_recette,
                    SUM(CASE WHEN s.receipt_number NOT LIKE 'VRS-%%' THEN s.old_gold_weight_g ELSE 0 END) AS total_oc_gold,
                    SUM(CASE WHEN s.receipt_number NOT LIKE 'VRS-%%' THEN COALESCE(s.old_silver_weight_g, 0) ELSE 0 END) AS total_oc_silver,
                    SUM(CASE WHEN s.receipt_number NOT LIKE 'VRS-%%' THEN s.tpe_paid_da ELSE 0 END) AS total_tpe,
                    SUM(CASE WHEN s.receipt_number NOT LIKE 'VRS-%%' THEN s.euro_paid ELSE 0 END) AS total_euro,
                    SUM(CASE WHEN s.receipt_number NOT LIKE 'VRS-%%' THEN s.dollar_paid ELSE 0 END) AS total_dollar
                FROM Sales s
                WHERE YEAR(s.created_at) = %s AND MONTH(s.created_at) = %s AND s.status = 'COMPLETED'
                GROUP BY DATE(s.created_at)
                """,
                (year, month),
            )
            sales_by_date = {to_date_key(r["sale_date"]): r for r in sales_results if to_date_key(r.get("sale_date"))}

            # 3. Layaway payments (Versement_Payments)
            vp_results = api._fetch_rows(
                """
                SELECT 
                    DATE(vp.payment_date) AS pay_date,
                    SUM(vp.montant_da) AS total_vp_recette,
                    SUM(vp.tpe_da) AS total_vp_tpe,
                    SUM(vp.montant_euro) AS total_vp_euro,
                    SUM(vp.montant_dollar) AS total_vp_dollar,
                    SUM(vp.or_casse_g) AS total_vp_oc_gold,
                    SUM(COALESCE(vp.argent_casse_g, 0)) AS total_vp_oc_silver
                FROM Versement_Payments vp
                JOIN Versements v ON vp.versement_id = v.id
                WHERE YEAR(vp.payment_date) = %s AND MONTH(vp.payment_date) = %s AND v.status != 'ANNULE'
                GROUP BY DATE(vp.payment_date)
                """,
                (year, month),
            )
            vp_by_date = {to_date_key(r["pay_date"]): r for r in vp_results if to_date_key(r.get("pay_date"))}

            # 4. Workshop orders payments and profits (ArtisanWorkOrders)
            awo_results = api._fetch_rows(
                """
                SELECT 
                    DATE(awo.date_remis) AS awo_date,
                    SUM(COALESCE(awo.pay_cash_da, 0.0)) AS total_awo_recette,
                    SUM(COALESCE(awo.pay_tpe_da, 0.0)) AS total_awo_tpe,
                    SUM(COALESCE(awo.pay_oc_g, 0.0)) AS total_awo_oc_gold,
                    SUM(COALESCE(awo.pay_oc_silver_g, 0.0)) AS total_awo_oc_silver,
                    SUM(COALESCE(awo.diff, 0.0)) AS total_awo_benefice
                FROM ArtisanWorkOrders awo
                WHERE YEAR(awo.date_remis) = %s AND MONTH(awo.date_remis) = %s
                  AND (
                      COALESCE(awo.pay_cash_da, 0) != 0 
                      OR COALESCE(awo.pay_tpe_da, 0) != 0 
                      OR COALESCE(awo.pay_oc_g, 0) != 0
                      OR COALESCE(awo.pay_oc_silver_g, 0) != 0
                      OR COALESCE(awo.diff, 0) != 0
                  )
                GROUP BY DATE(awo.date_remis)
                """,
                (year, month),
            )
            awo_by_date = {to_date_key(r["awo_date"]): r for r in awo_results if to_date_key(r.get("awo_date"))}

            # 5. Daily profit calculator
            raw_profit_dict = {}
            if hasattr(api, "sales_manager") and hasattr(api.sales_manager, "get_monthly_profit_by_day"):
                raw_profit_dict = api.sales_manager.get_monthly_profit_by_day(year, month)
            profit_by_date = {to_date_key(k): v for k, v in (raw_profit_dict or {}).items() if to_date_key(k)}

            # 6. Build daily rows for the whole month
            num_days = calendar.monthrange(year, month)[1]
            daily_rows = []

            sum_ps_gold = sum_ps_silver = 0.0
            sum_recettes = sum_oc_gold = sum_oc_silver = sum_tpe = sum_euro = sum_dollar = 0.0
            sum_sales_profit = sum_awo_profit = sum_benefice = 0.0

            for d in range(1, num_days + 1):
                current_date = date(year, month, d)
                day_name = get_french_day_name(current_date)
                date_str = f"{d:02d}/{month:02d}/{year}"

                w_data = weights_by_date.get(current_date, {})
                s_data = sales_by_date.get(current_date, {})
                vp_data = vp_by_date.get(current_date, {})
                awo_data = awo_by_date.get(current_date, {})

                has_data = bool(
                    current_date in weights_by_date
                    or current_date in sales_by_date
                    or current_date in vp_by_date
                    or current_date in awo_by_date
                    or current_date in profit_by_date
                )

                ps_gold = float(w_data.get("total_ps_gold") or 0.0)
                ps_silver = float(w_data.get("total_ps_silver") or 0.0)

                recette = (
                    float(s_data.get("total_recette") or 0.0)
                    + float(vp_data.get("total_vp_recette") or 0.0)
                    + float(awo_data.get("total_awo_recette") or 0.0)
                )

                oc_gold = (
                    float(s_data.get("total_oc_gold") or 0.0)
                    + float(vp_data.get("total_vp_oc_gold") or 0.0)
                    + float(awo_data.get("total_awo_oc_gold") or 0.0)
                )

                oc_silver = (
                    float(s_data.get("total_oc_silver") or 0.0)
                    + float(vp_data.get("total_vp_oc_silver") or 0.0)
                    + float(awo_data.get("total_awo_oc_silver") or 0.0)
                )

                tpe = (
                    float(s_data.get("total_tpe") or 0.0)
                    + float(vp_data.get("total_vp_tpe") or 0.0)
                    + float(awo_data.get("total_awo_tpe") or 0.0)
                )

                euro = float(s_data.get("total_euro") or 0.0) + float(vp_data.get("total_vp_euro") or 0.0)
                dollar = float(s_data.get("total_dollar") or 0.0) + float(vp_data.get("total_vp_dollar") or 0.0)

                sales_profit = float(profit_by_date.get(current_date, {}).get("profit_da") or 0.0)
                awo_profit = float(awo_data.get("total_awo_benefice") or 0.0)
                benefice = sales_profit + awo_profit

                # Accumulate month totals
                sum_ps_gold += ps_gold
                sum_ps_silver += ps_silver
                sum_recettes += recette
                sum_oc_gold += oc_gold
                sum_oc_silver += oc_silver
                sum_tpe += tpe
                sum_euro += euro
                sum_dollar += dollar
                sum_sales_profit += sales_profit
                sum_awo_profit += awo_profit
                sum_benefice += benefice

                daily_rows.append(
                    {
                        "day_number": d,
                        "day_name": day_name,
                        "date": date_str,
                        "iso_date": current_date.isoformat(),
                        "has_data": has_data,
                        "ps_gold": round(ps_gold, 3),
                        "ps_silver": round(ps_silver, 3),
                        "recette_da": round(recette, 2),
                        "oc_gold": round(oc_gold, 3),
                        "oc_silver": round(oc_silver, 3),
                        "tpe_da": round(tpe, 2),
                        "euro": round(euro, 2),
                        "dollar": round(dollar, 2),
                        "sales_profit": round(sales_profit, 2),
                        "artisan_profit": round(awo_profit, 2),
                        "benefice": round(benefice, 2),
                    }
                )

            return api._ok(
                {
                    "year": year,
                    "month": month,
                    "month_name": FRENCH_MONTHS[month - 1],
                    "days_in_month": num_days,
                    "days": daily_rows,
                    "totals": {
                        "total_ps_gold": round(sum_ps_gold, 3),
                        "total_ps_silver": round(sum_ps_silver, 3),
                        "total_recette_da": round(sum_recettes, 2),
                        "total_oc_gold": round(sum_oc_gold, 3),
                        "total_oc_silver": round(sum_oc_silver, 3),
                        "total_tpe_da": round(sum_tpe, 2),
                        "total_euro": round(sum_euro, 2),
                        "total_dollar": round(sum_dollar, 2),
                        "total_sales_profit": round(sum_sales_profit, 2),
                        "total_artisan_profit": round(sum_awo_profit, 2),
                        "total_benefice": round(sum_benefice, 2),
                    },
                }
            )
        except Exception as exc:
            logger.exception("Error loading Monthly Summary report: %s", exc)
            return api._json_error(str(exc), status=500)

    # -------------------------------------------------------------------------
    # Backward compatibility reporting endpoints
    # -------------------------------------------------------------------------
    @flask_app.route("/api/v1/reports/daily")
    def api_v1_report_daily():
        day = api._str_arg("date") or date.today().isoformat()
        return api._ok(api.reports_manager.get_daily_summary(day), date=day)

    @flask_app.route("/api/v1/reports/range")
    def api_v1_report_range():
        start_date = api._str_arg("start_date") or date.today().isoformat()
        end_date = api._str_arg("end_date") or start_date
        return api._ok(
            api.reports_manager.get_custom_range_summary(start_date, end_date),
            start_date=start_date,
            end_date=end_date,
        )

    @flask_app.route("/api/v1/reports/monthly")
    def api_v1_report_monthly():
        today = date.today()
        year = api._int_arg("year", today.year, min_value=2000, max_value=2100)
        month = api._int_arg("month", today.month, min_value=1, max_value=12)
        return api._ok(api.reports_manager.get_monthly_summary(year, month), year=year, month=month)

    return {
        function.__name__: function
        for function in (
            api_v1_journal_sellers,
            api_v1_reports_journal,
            api_v1_reports_monthly_summary,
            api_v1_report_daily,
            api_v1_report_range,
            api_v1_report_monthly,
        )
    }
