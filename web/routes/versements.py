# web/routes/versements.py

import logging
import re
from datetime import date, datetime

from database.versement.versement_pricing import calculate_versement_item_balances

logger = logging.getLogger("JEWELLERY_SYS")


def register_versements_routes(flask_app, api):
    """
    Register routes for customer reservations and installments (Versements / Acomptes).
    Powers ui/widgets/versements/versements_view.py.
    """

    @flask_app.route("/api/v1/versements")
    def api_v1_versements():
        """
        List all customer layaway / versement dossiers with full items,
        calculated item balances, and payment records.
        Powers ui/widgets/versements/versements_view.py.

        Query Parameters:
        - status (str, optional): 'EN_COURS', 'CLOTURE', 'ANNULE', or 'ALL' (default 'ALL')
        - search (str, optional): Client name, phone, VRS-xxxxx, barcode, designation, notes
        - client_id (int, optional): Filter by client ID
        - page (int, optional): Page number (default 1)
        - per_page (int, optional): Number of dossiers per page (default 50)
        """
        status_param = api._str_arg("status", "ALL").upper()
        status_filter = None if status_param in ("ALL", "", "TOUS") else status_param
        search_text = api._str_arg("search", "").lower().strip()
        client_id = api._int_arg("client_id")
        page, per_page, offset = api._page_args(default_per_page=50)

        try:
            versements_mgr = getattr(api, "versement_manager", None)
            if not versements_mgr and hasattr(api, "data_manager"):
                versements_mgr = api.data_manager.versements

            if not versements_mgr:
                from database.versement.versement_manager import VersementManager
                versements_mgr = VersementManager(api.db)

            raw_versements = versements_mgr.get_versements(
                status_filter=status_filter,
                client_id=client_id,
            )

            filtered_versements = []
            for v in raw_versements:
                v_id = v["id"]
                client_name = str(v.get("client_name") or "Inconnu")
                client_phone = str(v.get("phone") or "")
                v_code = f"vrs-{v_id:05d}"
                v_code_short = f"vrs-{v_id}"

                items = v.get("items", [])
                payments = v.get("payments", [])

                if search_text:
                    match_found = False
                    if (
                        search_text in client_name.lower()
                        or search_text in client_phone
                        or search_text in v_code
                        or search_text in v_code_short
                        or search_text in str(v_id)
                    ):
                        match_found = True

                    if not match_found:
                        for item in items:
                            desig = str(item.get("designation") or "").lower()
                            barcode = str(item.get("barcode") or "").lower()
                            c_note = str(item.get("custom_note") or item.get("notes") or "").lower()
                            obs = str(item.get("observation") or "").lower()
                            if any(search_text in s for s in (desig, barcode, c_note, obs)):
                                match_found = True
                                break

                    if not match_found:
                        for p in payments:
                            p_notes = str(p.get("notes") or "").lower()
                            p_desig = str(p.get("item_designation") or "").lower()
                            if search_text in p_notes or search_text in p_desig:
                                match_found = True
                                break

                    if not match_found:
                        continue

                filtered_versements.append(v)

            total_records = len(filtered_versements)
            paged_slice = filtered_versements[offset : offset + per_page]

            # Format each dossier matching VersementsView data structures
            formatted_list = []
            for v in paged_slice:
                v_id = v["id"]
                statut = v.get("status", "EN_COURS")
                is_annule = (statut == "ANNULE")
                items = v.get("items", [])
                payments = v.get("payments", [])

                # Calculate item-level balances (deducted grams vs remaining grams)
                item_balances = calculate_versement_item_balances(items, payments)

                formatted_items = []
                for item in items:
                    item_id = item["item_id"]
                    i_statut = item.get("item_status", "EN_COURS")
                    is_item_annule = (i_statut == "ANNULE")
                    item_type = str(item.get("item_type") or "WEIGHT").upper()
                    reserved_qty = (
                        0 if is_item_annule
                        else (max(1, int(item.get("reserved_quantity") or 1)) if item_type == "PIECE" else 1)
                    )
                    weight = 0.0 if is_item_annule else float(item.get("display_weight") or item.get("weight") or 0.0)

                    balance = item_balances.get(
                        item_id,
                        {"deducted_g": 0.0, "remaining_g": 0.0 if is_item_annule else weight, "has_shared": False},
                    )

                    custom_note = str(item.get("custom_note") or item.get("notes") or "").strip()
                    observation = str(item.get("observation") or "").strip()

                    formatted_items.append(
                        {
                            "item_id": item_id,
                            "inventory_id": item.get("inventory_id"),
                            "designation": item.get("designation", "Inconnu"),
                            "barcode": item.get("barcode", ""),
                            "item_type": item_type,
                            "reserved_quantity": reserved_qty,
                            "weight": float(item.get("weight") or 0.0),
                            "display_weight": weight,
                            "selling_price": float(item.get("selling_price") or 0.0),
                            "display_price": float(item.get("display_price") or 0.0),
                            "item_status": i_statut,
                            "custom_note": custom_note,
                            "observation": observation,
                            "deducted_g": round(float(balance.get("deducted_g", 0.0)), 3),
                            "remaining_g": round(float(balance.get("remaining_g", 0.0)), 3),
                        }
                    )

                formatted_payments = []
                for idx, p in enumerate(payments, 1):
                    p_id = p.get("id")
                    m_da = float(p.get("montant_da") or 0.0)
                    m_tpe = float(p.get("tpe_da") or 0.0)
                    m_eu = float(p.get("montant_euro") or 0.0)
                    taux_eu = float(p.get("taux_change_euro") or 0.0)
                    m_dl = float(p.get("montant_dollar") or 0.0)
                    taux_dl = float(p.get("taux_change_dollar") or 0.0)
                    o_c = float(p.get("or_casse_g") or 0.0)
                    o_c_ag = float(p.get("argent_casse_g") or 0.0)
                    prix_g_ag = float(p.get("prix_gramme_argent_jour_da") or 0.0)
                    deduit = float(p.get("poids_deduit_g") or 0.0)
                    remise = float(p.get("remise_da") or 0.0)
                    p_notes = p.get("notes") or ""

                    d = p.get("payment_date", v["created_at"])
                    date_str = d.strftime("%d/%m/%Y") if hasattr(d, "strftime") else str(d)

                    formatted_payments.append(
                        {
                            "id": p_id,
                            "payment_number": idx,
                            "versement_item_id": p.get("versement_item_id"),
                            "item_designation": p.get("item_designation", ""),
                            "payment_date": d.isoformat() if hasattr(d, "isoformat") else str(d),
                            "date_formatted": date_str,
                            "montant_da": m_da,
                            "tpe_da": m_tpe,
                            "montant_euro": m_eu,
                            "taux_change_euro": taux_eu,
                            "montant_dollar": m_dl,
                            "taux_change_dollar": taux_dl,
                            "or_casse_g": o_c,
                            "argent_casse_g": o_c_ag,
                            "prix_gramme_argent_jour_da": prix_g_ag,
                            "poids_deduit_g": deduit,
                            "remise_da": remise,
                            "notes": p_notes,
                        }
                    )

                total_paid_da = float(v.get("total_paid_money_da") or 0.0)
                total_tpe = float(v.get("total_tpe_da") or 0.0)
                total_euro = float(v.get("total_euro") or 0.0)
                total_dollar = float(v.get("total_dollar") or 0.0)
                total_remise = float(v.get("total_remise_da") or 0.0)
                total_deducted = float(v.get("total_paid_weight_g") or 0.0)
                reste_poids = float(v.get("reste_poids_g") or 0.0)
                total_or_casse = float(v.get("total_or_casse_g") or 0.0)
                total_argent_casse = float(v.get("total_argent_casse_g") or 0.0)

                sum_parts_1 = [f"💰 Payé: {total_paid_da:,.0f} DA"]
                if total_tpe != 0:
                    sum_parts_1.append(f"TPE: {total_tpe:,.0f} DA")
                if total_euro > 0:
                    sum_parts_1.append(f"💶 {total_euro:,.0f} €")
                if total_dollar > 0:
                    sum_parts_1.append(f"💵 {total_dollar:,.0f} $")
                if total_remise > 0:
                    sum_parts_1.append(f"🎁 Remise: {total_remise:,.0f} DA")
                sum_parts_1.append(f"⚖️ Déduit: - {total_deducted:.2f} g")

                sum_text_1 = "  |  ".join(sum_parts_1)
                sum_text_2 = f"STATUT: {statut}  |  ⚖️ RESTE: {reste_poids:.3f} g"
                is_complete = (reste_poids <= 0) or (statut == "CLOTURE")

                formatted_list.append(
                    {
                        "id": v_id,
                        "code": f"VRS-{v_id:05d}",
                        "status": statut,
                        "is_annule": is_annule,
                        "is_complete": is_complete,
                        "client_id": v.get("client_id"),
                        "client_name": v.get("client_name") or "Inconnu",
                        "client_phone": str(v.get("phone") or ""),
                        "created_at": v["created_at"].isoformat() if hasattr(v["created_at"], "isoformat") else str(v["created_at"]),
                        "total_weight_g": round(float(v.get("total_weight_g") or 0.0), 3),
                        "total_paid_money_da": round(total_paid_da, 2),
                        "total_tpe_da": round(total_tpe, 2),
                        "total_euro": round(total_euro, 2),
                        "total_dollar": round(total_dollar, 2),
                        "total_remise_da": round(total_remise, 2),
                        "total_paid_weight_g": round(total_deducted, 3),
                        "reste_poids_g": round(reste_poids, 3),
                        "total_or_casse_g": round(total_or_casse, 3),
                        "total_argent_casse_g": round(total_argent_casse, 3),
                        "summary_text_1": sum_text_1,
                        "summary_text_2": sum_text_2,
                        "items_count": len(formatted_items),
                        "payments_count": len(formatted_payments),
                        "items": formatted_items,
                        "payments": formatted_payments,
                    }
                )

            return api._ok(
                formatted_list,
                page=page,
                per_page=per_page,
                total=total_records,
                has_more=(page * per_page) < total_records,
            )
        except Exception as exc:
            logger.exception("Error loading Versements: %s", exc)
            return api._json_error(str(exc), status=500)

    @flask_app.route("/api/v1/versements/<int:versement_id>")
    def api_v1_versement_detail(versement_id):
        """
        Get comprehensive details for a single Versement dossier.
        """
        try:
            versements_mgr = getattr(api, "versement_manager", None)
            if not versements_mgr and hasattr(api, "data_manager"):
                versements_mgr = api.data_manager.versements

            if not versements_mgr:
                from database.versement.versement_manager import VersementManager
                versements_mgr = VersementManager(api.db)

            records = versements_mgr.get_versements(status_filter=None)
            found = next((v for v in records if v["id"] == versement_id), None)
            if not found:
                return api._not_found("Versement")

            items = found.get("items", [])
            payments = found.get("payments", [])
            item_balances = calculate_versement_item_balances(items, payments)

            for item in items:
                item_id = item["item_id"]
                bal = item_balances.get(item_id, {"deducted_g": 0.0, "remaining_g": 0.0})
                item["deducted_g"] = round(float(bal.get("deducted_g", 0.0)), 3)
                item["remaining_g"] = round(float(bal.get("remaining_g", 0.0)), 3)

            return api._ok(found)
        except Exception as exc:
            logger.exception("Error loading Versement detail: %s", exc)
            return api._json_error(str(exc), status=500)

    @flask_app.route("/api/v1/versements/stats")
    def api_v1_versements_stats():
        """
        Summary KPI statistics for active, closed, and cancelled layaways.
        """
        try:
            versements_mgr = getattr(api, "versement_manager", None)
            if not versements_mgr and hasattr(api, "data_manager"):
                versements_mgr = api.data_manager.versements

            if not versements_mgr:
                from database.versement.versement_manager import VersementManager
                versements_mgr = VersementManager(api.db)

            all_versements = versements_mgr.get_versements(status_filter=None)
            total_count = len(all_versements)
            active_count = sum(1 for v in all_versements if v.get("status") == "EN_COURS")
            closed_count = sum(1 for v in all_versements if v.get("status") == "CLOTURE")
            cancelled_count = sum(1 for v in all_versements if v.get("status") == "ANNULE")

            active_versements = [v for v in all_versements if v.get("status") == "EN_COURS"]
            active_weight = sum(float(v.get("total_weight_g") or 0.0) for v in active_versements)
            deducted_weight = sum(float(v.get("total_paid_weight_g") or 0.0) for v in active_versements)
            remaining_weight = sum(float(v.get("reste_poids_g") or 0.0) for v in active_versements)
            paid_money = sum(float(v.get("total_paid_money_da") or 0.0) for v in active_versements)
            paid_tpe = sum(float(v.get("total_tpe_da") or 0.0) for v in active_versements)
            paid_euro = sum(float(v.get("total_euro") or 0.0) for v in active_versements)
            paid_dollar = sum(float(v.get("total_dollar") or 0.0) for v in active_versements)
            paid_or_casse = sum(float(v.get("total_or_casse_g") or 0.0) for v in active_versements)
            paid_argent_casse = sum(float(v.get("total_argent_casse_g") or 0.0) for v in active_versements)

            return api._ok(
                {
                    "total_dossiers": total_count,
                    "active_count": active_count,
                    "closed_count": closed_count,
                    "cancelled_count": cancelled_count,
                    "active_weight_g": round(active_weight, 3),
                    "deducted_weight_g": round(deducted_weight, 3),
                    "remaining_weight_g": round(remaining_weight, 3),
                    "total_paid_money_da": round(paid_money, 2),
                    "total_tpe_da": round(paid_tpe, 2),
                    "total_euro": round(paid_euro, 2),
                    "total_dollar": round(paid_dollar, 2),
                    "total_or_casse_g": round(paid_or_casse, 3),
                    "total_argent_casse_g": round(paid_argent_casse, 3),
                }
            )
        except Exception as exc:
            logger.exception("Error loading Versement stats: %s", exc)
            return api._json_error(str(exc), status=500)

    return {
        function.__name__: function
        for function in (
            api_v1_versements,
            api_v1_versement_detail,
            api_v1_versements_stats,
        )
    }
