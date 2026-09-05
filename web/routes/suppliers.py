# web/routes/suppliers.py

import logging
from datetime import date, datetime

logger = logging.getLogger("JEWELLERY_SYS")


def safe_float(val):
    try:
        return float(str(val).replace(" ", "").replace(",", "."))
    except (ValueError, TypeError):
        return 0.0


def format_excel_date(raw_date):
    """Format date to dd/MM/yyyy matching suppliers_view.py."""
    if not raw_date:
        return ""
    if hasattr(raw_date, "strftime"):
        return raw_date.strftime("%d/%m/%Y")
    s_date = str(raw_date).strip()
    if " " in s_date:
        s_date = s_date.split(" ")[0]
    if "T" in s_date:
        s_date = s_date.split("T")[0]
    if "-" in s_date:
        parts = s_date.split("-")
        if len(parts) == 3:
            return f"{parts[2]}/{parts[1]}/{parts[0]}"
    return s_date


def register_suppliers_routes(flask_app, api):
    """
    Register routes for Suppliers and the French Supplier Excel Ledger.
    Powers ui/widgets/suppliers/suppliers_view.py.
    """

    @flask_app.route("/api/v1/suppliers")
    def api_v1_suppliers_list():
        """
        List all suppliers with their metadata and current balances (Poids Net g and Solde DA).
        Powers the supplier selection dropdown and directory view in SuppliersView.

        Query Parameters:
        - search (str, optional): Search by name or phone
        - active_only (bool, optional): Include only active suppliers (default true)
        - page (int, optional): Page number
        - per_page (int, optional): Items per page
        """
        search_text = api._str_arg("search", "").lower().strip()
        active_only = not api._bool_arg("include_inactive", False)
        page, per_page, offset = api._page_args(default_per_page=50)

        try:
            supplier_mgr = getattr(api, "supplier_manager", None)
            if not supplier_mgr and hasattr(api, "data_manager"):
                supplier_mgr = api.data_manager.suppliers

            if not supplier_mgr:
                from database.supplier_manager import SupplierManager
                supplier_mgr = SupplierManager(api.db)

            suppliers = supplier_mgr.list_suppliers(active_only=active_only, limit=1000)

            filtered_suppliers = []
            for s in suppliers:
                s_name = str(s.get("name") or "").lower()
                s_phone = str(s.get("phone") or "").lower()
                if search_text and search_text not in s_name and search_text not in s_phone:
                    continue

                s_id = s["id"]
                bal_tuple = supplier_mgr.get_supplier_balance(s_id)
                poids_net = float(bal_tuple[0]) if bal_tuple else 0.0
                solde_da = float(bal_tuple[1]) if bal_tuple else 0.0

                s_copy = dict(s)
                s_copy["poids_net"] = round(poids_net, 3)
                s_copy["solde_da"] = round(solde_da, 2)
                s_copy["poids_net_formatted"] = f"{poids_net:,.2f} g"
                s_copy["solde_da_formatted"] = f"{int(round(solde_da)):,} DA".replace(",", " ")
                filtered_suppliers.append(s_copy)

            total_records = len(filtered_suppliers)
            paged_slice = filtered_suppliers[offset : offset + per_page]

            return api._ok(
                paged_slice,
                page=page,
                per_page=per_page,
                total=total_records,
                has_more=(page * per_page) < total_records,
            )
        except Exception as exc:
            logger.exception("Error loading suppliers list: %s", exc)
            return api._json_error(str(exc), status=500)

    @flask_app.route("/api/v1/suppliers/<int:supplier_id>")
    def api_v1_supplier_detail(supplier_id):
        """
        Get supplier profile and header card KPI statistics (Poids Net & Solde DA).
        Matches the header card of SuppliersView.
        """
        try:
            supplier = api._fetch_one(
                """
                SELECT s.*, mt.name AS base_metal_name
                FROM Suppliers s
                LEFT JOIN MetalTypes mt ON s.base_metal_type_id = mt.id
                WHERE s.id = %s
                """,
                (supplier_id,),
            )
            if not supplier:
                return api._not_found("Supplier")

            supplier_mgr = getattr(api, "supplier_manager", None)
            if not supplier_mgr and hasattr(api, "data_manager"):
                supplier_mgr = api.data_manager.suppliers

            if not supplier_mgr:
                from database.supplier_manager import SupplierManager
                supplier_mgr = SupplierManager(api.db)

            bal_tuple = supplier_mgr.get_supplier_balance(supplier_id)
            poids_net = float(bal_tuple[0]) if bal_tuple else 0.0
            solde_da = float(bal_tuple[1]) if bal_tuple else 0.0

            supplier["poids_net"] = round(poids_net, 3)
            supplier["solde_da"] = round(solde_da, 2)
            supplier["header_poids_text"] = f"Poids Net: {poids_net:,.2f} g"
            supplier["header_solde_text"] = f"Solde: {int(round(solde_da)):,} DA".replace(",", " ")

            return api._ok(supplier)
        except Exception as exc:
            logger.exception("Error loading supplier detail: %s", exc)
            return api._json_error(str(exc), status=500)

    @flask_app.route("/api/v1/suppliers/<int:supplier_id>/ledger")
    def api_v1_supplier_ledger(supplier_id):
        """
        100% French Suppliers Ledger matching the Excel spreadsheet structure:
        Date | Poids | Afaçon | Montant | Obs / Libellé
        Powers the operations table and running totals in SuppliersView.

        Query Parameters:
        - search (str, optional): Search description or date
        - start_date (str, optional): YYYY-MM-DD
        - end_date (str, optional): YYYY-MM-DD
        - page (int, optional): Page number
        - per_page (int, optional): Operations per page
        """
        search_text = api._str_arg("search", "").lower().strip()
        start_date = api._str_arg("start_date")
        end_date = api._str_arg("end_date")
        page, per_page, offset = api._page_args(default_per_page=100)

        try:
            supplier = api._fetch_one("SELECT id, name FROM Suppliers WHERE id = %s", (supplier_id,))
            if not supplier:
                return api._not_found("Supplier")

            supplier_mgr = getattr(api, "supplier_manager", None)
            if not supplier_mgr and hasattr(api, "data_manager"):
                supplier_mgr = api.data_manager.suppliers

            if not supplier_mgr:
                from database.supplier_manager import SupplierManager
                supplier_mgr = SupplierManager(api.db)

            raw_ops = supplier_mgr.list_operations(supplier_id=supplier_id, limit=3000)

            filtered_ops = []
            for op in raw_ops:
                raw_date = op.get("transaction_date") or op.get("operation_date") or ""
                op_date = format_excel_date(raw_date)
                iso_date = str(raw_date).split(" ")[0].split("T")[0] if raw_date else ""

                if start_date and iso_date and iso_date < start_date:
                    continue
                if end_date and iso_date and iso_date > end_date:
                    continue

                description = str(op.get("description") or op.get("notes") or "")

                if search_text and (search_text not in description.lower() and search_text not in op_date):
                    continue

                op_type = str(op.get("operation_type") or op.get("type") or "INCOMING").upper()

                raw_w = (
                    op.get("weight_g")
                    if op.get("weight_g") is not None
                    else (op.get("weight_delta") if op.get("weight_delta") is not None else op.get("weight"))
                )
                weight_val = float(raw_w or 0.0)

                raw_m = (
                    op.get("amount_da")
                    if op.get("amount_da") is not None
                    else (op.get("money_delta") if op.get("money_delta") is not None else op.get("amount"))
                )
                amount_val = float(raw_m or 0.0)

                if op_type == "OUTGOING":
                    signed_weight = -abs(weight_val)
                    signed_amount = -abs(amount_val)
                else:
                    signed_weight = weight_val
                    signed_amount = amount_val

                # Color highlight detection matching suppliers_view.py
                is_red = False
                is_blue = False
                clean_desc = description
                if "[COLOR:RED]" in clean_desc:
                    is_red = True
                    clean_desc = clean_desc.replace("[COLOR:RED]", "").strip()
                elif "régler" in clean_desc.lower() or "regler" in clean_desc.lower():
                    is_red = True

                if "alliage" in clean_desc.lower():
                    is_blue = True

                afacon_val = op.get("afacon") or op.get("labor_price_per_gram") or ""
                afacon_str = str(afacon_val) if afacon_val and str(afacon_val) not in ("0", "0.00", "0.0") else "0"

                poids_str = f"{signed_weight:,.2f}".replace(",", " ").replace(".", ",") if abs(signed_weight) > 0.0001 else "0,00"
                montant_str = f"{int(round(signed_amount)):,}".replace(",", " ") if abs(signed_amount) > 0.01 else "0"
                if signed_amount < 0 and not montant_str.startswith("-"):
                    montant_str = "-" + montant_str

                filtered_ops.append(
                    {
                        "id": op.get("id"),
                        "operation_number": op.get("operation_number") or f"OP-{op.get('id')}",
                        "date": op_date,
                        "iso_date": iso_date,
                        "operation_type": op_type,
                        "raw_weight_g": weight_val,
                        "signed_weight_g": round(signed_weight, 3),
                        "poids_formatted": poids_str,
                        "afacon": afacon_str,
                        "raw_amount_da": amount_val,
                        "signed_amount_da": round(signed_amount, 2),
                        "montant_formatted": montant_str,
                        "obs": clean_desc,
                        "is_red": is_red,
                        "is_blue": is_blue,
                    }
                )

            total_records = len(filtered_ops)
            tot_poids = sum(o["signed_weight_g"] for o in filtered_ops)
            tot_montant = sum(o["signed_amount_da"] for o in filtered_ops)

            paged_slice = filtered_ops[offset : offset + per_page]

            return api._ok(
                paged_slice,
                supplier_id=supplier_id,
                supplier_name=supplier["name"],
                page=page,
                per_page=per_page,
                total=total_records,
                has_more=(page * per_page) < total_records,
                totals={
                    "total_poids_net": round(tot_poids, 3),
                    "total_solde_da": round(tot_montant, 2),
                    "poids_net_formatted": f"Poids Net: {tot_poids:,.2f} g",
                    "solde_formatted": f"Solde: {int(round(tot_montant)):,} DA".replace(",", " "),
                },
            )
        except Exception as exc:
            logger.exception("Error loading supplier ledger: %s", exc)
            return api._json_error(str(exc), status=500)

    return {
        function.__name__: function
        for function in (
            api_v1_suppliers_list,
            api_v1_supplier_detail,
            api_v1_supplier_ledger,
        )
    }
