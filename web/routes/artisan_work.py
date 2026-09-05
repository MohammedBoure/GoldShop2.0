# web/routes/artisan_work.py

import logging
from datetime import date, datetime, timedelta

logger = logging.getLogger("JEWELLERY_SYS")

STATUS_MAP = {
    "RECEPTION": ("🟢 Au Réceptionniste", "#27ae60", "#d5f5e3"),
    "CHEZ_ARTISAN": ("🟡 Chez l'Artisan", "#d68910", "#fef9e7"),
    "RETOUR_ARTISAN": ("🔵 Retourné au Magasin", "#2980b9", "#ebf5fb"),
    "LIVRE": ("✅ Livré au Client", "#7f8c8d", "#eaecee"),
}


def safe_float(val):
    try:
        return float(str(val).replace(" ", "").replace(",", "."))
    except (ValueError, TypeError):
        return 0.0


def register_artisan_work_routes(flask_app, api):
    """
    Register routes for Workshop, Repairs & Artisan production orders.
    Powers ui/widgets/artisan_work/artisan_work_view.py.
    """

    @flask_app.route("/api/v1/artisan-work/orders")
    def api_v1_artisan_orders():
        """
        Atelier Production Orders API matching the desktop Excel production model:
        numero | Nom | Tel | date remis | Obj | Poid | Date Reçue | Date Sortie | Prix (Façon) | Prix (Client) | Diff | Statut | Artisan
        Powers ui/widgets/artisan_work/artisan_work_view.py.

        Query Parameters:
        - status (str, optional): 'ALL', 'RECEPTION', 'CHEZ_ARTISAN', 'RETOUR_ARTISAN', 'LIVRE'
        - days (str or int, optional): '7', '30', '90', '365', or 'ALL' (default '30')
        - date_from (str, optional): YYYY-MM-DD
        - date_to (str, optional): YYYY-MM-DD
        - artisan_id (int, optional): Filter by artisan
        - search (str, optional): Search by numero, client name, phone, object, observations
        - page (int, optional): Page number
        - per_page (int, optional): Orders per page
        """
        status_filter = api._str_arg("status", "ALL").upper()
        if status_filter in ("ALL", "", "TOUS"):
            status_filter = None

        days_param = api._str_arg("days", "ALL").upper()
        date_from = api._str_arg("date_from")
        date_to = api._str_arg("date_to")

        if not date_from and days_param not in ("ALL", ""):
            try:
                days = int(days_param)
                date_from = (date.today() - timedelta(days=days)).isoformat()
            except ValueError:
                pass

        artisan_id = api._int_arg("artisan_id")
        search_text = api._str_arg("search", "").lower().strip()
        page, per_page, offset = api._page_args(default_per_page=50)

        try:
            artisan_mgr = getattr(api, "artisan_work_manager", None)
            if not artisan_mgr and hasattr(api, "data_manager"):
                artisan_mgr = api.data_manager.artisan_work

            if not artisan_mgr:
                from database.artisan_work_manager import ArtisanWorkManager
                artisan_mgr = ArtisanWorkManager(api.db)

            raw_orders = artisan_mgr.get_all_atelier_orders(
                status_filter=status_filter,
                artisan_id=artisan_id,
                date_from=date_from,
                date_to=date_to,
            )

            filtered_orders = []
            for r in raw_orders:
                num = str(r.get("numero") or r.get("id", "")).lower()
                client = str(r.get("client_name") or "").lower()
                phone = str(r.get("client_phone") or "").lower()
                obj = str(r.get("obj") or "").lower()
                obs = str(r.get("observations") or "").lower()
                art_name = str(r.get("artisan_name") or "").lower()

                if search_text and not any(
                    search_text in field for field in (num, client, phone, obj, obs, art_name)
                ):
                    continue

                filtered_orders.append(r)

            total_records = len(filtered_orders)

            # Calculate grand totals across all matching records
            tot_prix_artisan = sum(safe_float(r.get("cout_artisan_da") or r.get("prix") or 0.0) for r in filtered_orders)
            tot_prix_client = sum(safe_float(r.get("prix_vente_da") or r.get("vente") or 0.0) for r in filtered_orders)
            tot_diff = sum(safe_float(r.get("diff") or (safe_float(r.get("prix_vente_da") or 0) - safe_float(r.get("cout_artisan_da") or 0))) for r in filtered_orders)

            paged_slice = filtered_orders[offset : offset + per_page]

            formatted_records = []
            for r in paged_slice:
                cout_artisan = safe_float(r.get("cout_artisan_da") or r.get("prix") or 0.0)
                prix_client = safe_float(r.get("prix_vente_da") or r.get("vente") or 0.0)
                diff = safe_float(r.get("diff") or (prix_client - cout_artisan))

                st_key = r.get("status", "RECEPTION")
                st_label, st_fg, st_bg = STATUS_MAP.get(st_key, ("🟢 Au Réceptionniste", "#27ae60", "#d5f5e3"))

                formatted_records.append(
                    {
                        "id": r.get("id"),
                        "numero": str(r.get("numero") or r.get("id", "")),
                        "client_id": r.get("client_id"),
                        "client_name": r.get("client_name") or "Passager",
                        "client_phone": r.get("client_phone") or "",
                        "date_remis": r.get("date_remis") or "",
                        "obj": r.get("obj") or "",
                        "poids_entre_g": safe_float(r.get("poid") or r.get("poids_entre_g") or 0.0),
                        "poids_retour_g": safe_float(r.get("poids_retour_g") or 0.0),
                        "date_recue": r.get("date_recue") or "",
                        "date_sortie": r.get("date_sortie") or "",
                        "cout_artisan_da": cout_artisan,
                        "prix_vente_da": prix_client,
                        "diff": diff,
                        "status": st_key,
                        "status_label": st_label,
                        "status_color": st_fg,
                        "status_bg": st_bg,
                        "artisan_id": r.get("artisan_id"),
                        "artisan_name": r.get("artisan_name") or "Non assigné",
                        "pay_cash_da": safe_float(r.get("pay_cash_da") or 0.0),
                        "pay_tpe_da": safe_float(r.get("pay_tpe_da") or 0.0),
                        "pay_oc_g": safe_float(r.get("pay_oc_g") or 0.0),
                        "pay_oc_silver_g": safe_float(r.get("pay_oc_silver_g") or 0.0),
                        "journee_id": r.get("journee_id"),
                        "observations": r.get("observations") or "",
                    }
                )

            return api._ok(
                formatted_records,
                page=page,
                per_page=per_page,
                total=total_records,
                has_more=(page * per_page) < total_records,
                totals={
                    "total_cout_artisan_da": round(tot_prix_artisan, 2),
                    "total_prix_client_da": round(tot_prix_client, 2),
                    "total_diff_da": round(tot_diff, 2),
                },
            )
        except Exception as exc:
            logger.exception("Error loading atelier orders: %s", exc)
            return api._json_error(str(exc), status=500)

    @flask_app.route("/api/v1/artisan-work/orders/<int:order_id>")
    def api_v1_artisan_order_detail(order_id):
        """
        Get full details for a single workshop / repair order.
        """
        try:
            row = api._fetch_one(
                """
                SELECT awo.*, c.name AS client_name, c.phone AS client_phone,
                       a.name AS artisan_name, a.phone AS artisan_phone
                FROM ArtisanWorkOrders awo
                LEFT JOIN Clients c ON awo.client_id = c.id
                LEFT JOIN Artisans a ON awo.artisan_id = a.id
                WHERE awo.id = %s
                """,
                (order_id,),
            )
            if not row:
                return api._not_found("Order")

            st_key = row.get("status", "RECEPTION")
            st_label, st_fg, st_bg = STATUS_MAP.get(st_key, ("🟢 Au Réceptionniste", "#27ae60", "#d5f5e3"))
            row["status_label"] = st_label
            row["status_color"] = st_fg
            row["status_bg"] = st_bg

            return api._ok(row)
        except Exception as exc:
            logger.exception("Error loading order detail: %s", exc)
            return api._json_error(str(exc), status=500)

    @flask_app.route("/api/v1/artisan-work/artisans")
    def api_v1_artisans():
        """
        List all artisans from the directory with pure gold and labor fee balances.
        Matches the 'Répertoire Artisans' tab of ArtisanWorkView.
        """
        try:
            artisan_mgr = getattr(api, "artisan_work_manager", None)
            if not artisan_mgr and hasattr(api, "data_manager"):
                artisan_mgr = api.data_manager.artisan_work

            if not artisan_mgr:
                from database.artisan_work_manager import ArtisanWorkManager
                artisan_mgr = ArtisanWorkManager(api.db)

            artisans = artisan_mgr.get_all_artisans()
            result = []
            for a in artisans:
                a_id = a["id"]
                bal = artisan_mgr.get_artisan_balance(a_id) or {}
                result.append(
                    {
                        "id": a_id,
                        "name": a.get("name", ""),
                        "phone": a.get("phone", ""),
                        "notes": a.get("notes", ""),
                        "gold_balance_g": round(safe_float(bal.get("solde_or_fin_g", 0.0)), 3),
                        "facon_balance_da": round(safe_float(bal.get("solde_facon_da", 0.0)), 2),
                        "orders_count": int(bal.get("orders_count", 0)),
                    }
                )
            return api._ok(result, total=len(result))
        except Exception as exc:
            logger.exception("Error loading artisans: %s", exc)
            return api._json_error(str(exc), status=500)

    @flask_app.route("/api/v1/artisan-work/artisans/<int:artisan_id>/ledger")
    def api_v1_artisan_ledger(artisan_id):
        """
        Get the complete movement statement / ledger for an artisan.
        """
        try:
            artisan_mgr = getattr(api, "artisan_work_manager", None)
            if not artisan_mgr and hasattr(api, "data_manager"):
                artisan_mgr = api.data_manager.artisan_work

            if not artisan_mgr:
                from database.artisan_work_manager import ArtisanWorkManager
                artisan_mgr = ArtisanWorkManager(api.db)

            artisan = api._fetch_one("SELECT * FROM Artisans WHERE id = %s", (artisan_id,))
            if not artisan:
                return api._not_found("Artisan")

            balance = artisan_mgr.get_artisan_balance(artisan_id) or {}
            ledger = artisan_mgr.get_artisan_ledger(artisan_id) or []

            return api._ok(
                {
                    "artisan": artisan,
                    "balance": balance,
                    "ledger": ledger,
                    "total_movements": len(ledger),
                }
            )
        except Exception as exc:
            logger.exception("Error loading artisan ledger: %s", exc)
            return api._json_error(str(exc), status=500)

    return {
        function.__name__: function
        for function in (
            api_v1_artisan_orders,
            api_v1_artisan_order_detail,
            api_v1_artisans,
            api_v1_artisan_ledger,
        )
    }
