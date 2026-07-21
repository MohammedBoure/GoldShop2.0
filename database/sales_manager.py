import logging
from datetime import datetime
from database.profit_calculator import (
    direct_sale_revenues,
    item_cost_da,
    number,
    source_versement_id,
    versement_revenues_by_inventory,
)

class SalesManager:
    """
    مدير المبيعات الشامل:
    يدير عمليات البيع (إنشاء فواتير، خصم المخزون، الاسترجاع/الإلغاء، وتقارير اليومية، وتعديل المبالغ).
    """
    def __init__(self, db_instance):
        self.db = db_instance

    # ============================================================
    # 1. إنشاء عملية البيع (تسجيل الفاتورة + خصم المخزون)
    # ============================================================
    def create_sale(self, journee_id: int, client_id: int, user_id: int, 
                    cart_items: list, total_amount: float, discount: float, 
                    net_to_pay: float, cash_paid: float, tpe_paid: float, 
                    old_gold_weight: float = 0.0, impos_weight: float = 0.0, notes: str = "") -> dict:
        conn = None
        cursor = None
        try:
            conn = self.db.get_raw_connection()
            cursor = conn.cursor(dictionary=True)
            conn.autocommit = False

            date_str = datetime.now().strftime("%Y%m%d")
            cursor.execute("SELECT COUNT(*) as cnt FROM Sales WHERE DATE(created_at) = CURDATE()")
            count_today = cursor.fetchone()['cnt'] + 1
            receipt_number = f"FAC-{date_str}-{count_today:04d}"

            sale_query = """
                INSERT INTO Sales (
                    receipt_number, journee_id, client_id, user_id, 
                    total_amount_da, discount_da, net_to_pay_da, 
                    cash_paid_da, tpe_paid_da, old_gold_weight_g, impos_weight_g, notes
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(sale_query, (
                receipt_number, journee_id, client_id, user_id,
                total_amount, discount, net_to_pay, cash_paid, tpe_paid, old_gold_weight, impos_weight, notes
            ))
            sale_id = cursor.lastrowid

            for item in cart_items:
                inv_id = item.get('id')
                item_type = item.get('item_type', 'WEIGHT')
                barcode = item.get('barcode', '')
                name = item.get('name', 'Article inconnu')
                
                sold_w = float(item.get('cart_sold_weight', 0))
                sold_q = int(item.get('cart_sold_qty', 1))
                unit_price = float(item.get('cart_unit_price', 0))
                total_price = float(item.get('cart_line_total', 0))
                
                custom_note = str(item.get('custom_note') or '').strip()[:255]

                if inv_id:
                    cursor.execute("""
                        SELECT item_type, remaining_weight, remaining_quantity,
                               status, reserved_for_client_id
                        FROM Inventory WHERE id = %s FOR UPDATE
                    """, (inv_id,))
                    inventory = cursor.fetchone()
                    if not inventory:
                        raise ValueError("Article d'inventaire introuvable.")

                    reserved_client_id = inventory.get("reserved_for_client_id")
                    client_reserved_for_sale = False
                    if reserved_client_id and str(reserved_client_id) != "1":
                        if client_id is None or int(reserved_client_id) != int(client_id):
                            raise ValueError("Cet article est réservé à un autre client.")
                        client_reserved_for_sale = True

                    cursor.execute("""
                        SELECT COALESCE(SUM(COALESCE(reserved_quantity, 1)), 0) AS reserved_quantity,
                               COUNT(*) AS reservation_count
                        FROM Versement_Items
                        WHERE inventory_id = %s AND item_status = 'EN_COURS'
                    """, (inv_id,))
                    reservation = cursor.fetchone() or {}
                    active_reserved = int(reservation.get("reserved_quantity") or 0)
                    active_count = int(reservation.get("reservation_count") or 0)
                    status = inventory.get("status")

                    if item_type == "PIECE":
                        remaining_quantity = int(inventory.get("remaining_quantity") or 0)
                        sellable_quantity = max(0, remaining_quantity - active_reserved)
                        if sold_q <= 0 or sold_q > sellable_quantity:
                            raise ValueError(
                                f"Quantité vendue ({sold_q}) supérieure au stock vendable "
                                f"({sellable_quantity})."
                            )
                        legacy_reserved = status == "Reserved" and active_count > 0
                        if status not in ("Available", "Partially_Sold") and not (legacy_reserved or client_reserved_for_sale):
                            raise ValueError("Cet article n'est pas disponible pour la vente.")
                    else:
                        remaining_weight = float(inventory.get("remaining_weight") or 0.0)
                        if sold_w <= 0 or sold_w > remaining_weight + 0.0001:
                            raise ValueError("Le poids vendu dépasse le stock restant.")
                        if active_count > 0:
                            raise ValueError("Cet article pondéré est réservé par un versement.")
                        if status not in ("Available", "Partially_Sold", "Reserved"):
                            raise ValueError("Cet article n'est pas disponible pour la vente.")

                item_query = """
                    INSERT INTO SaleItems (
                        sale_id, inventory_id, barcode, name, item_type, 
                        sold_weight_g, sold_quantity, unit_price_da, total_price_da, custom_note
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                cursor.execute(item_query, (
                    sale_id, inv_id, barcode, name, item_type,
                    sold_w, sold_q, unit_price, total_price, custom_note # 🟢 إرسال الملاحظة هنا
                ))

                if inv_id:
                    if item_type == 'WEIGHT':
                        cursor.execute("""
                            UPDATE Inventory 
                            SET status = IF(remaining_weight - %s <= 0.005, 'Sold', 'Partially_Sold'),
                                remaining_weight = GREATEST(0, remaining_weight - %s)
                            WHERE id = %s
                        """, (sold_w, sold_w, inv_id))
                    else:
                        cursor.execute("""
                            UPDATE Inventory 
                            SET status = IF(remaining_quantity - %s <= 0, 'Sold',
                                        IF(remaining_quantity - %s < quantity, 'Partially_Sold', 'Available')),
                                remaining_quantity = GREATEST(0, remaining_quantity - %s)
                            WHERE id = %s
                        """, (sold_q, sold_q, sold_q, inv_id))

            conn.commit()
            return {"success": True, "sale_id": sale_id, "receipt_number": receipt_number}

        except Exception as e:
            if conn: conn.rollback()
            logging.error(f"Erreur création vente: {e}")
            return {"success": False, "message": str(e)}
        finally:
            if cursor: cursor.close()
            if conn: conn.close()

    # ============================================================
    # 2. إلغاء عملية البيع (استرجاع المخزون)
    # ============================================================
    def cancel_sale(self, sale_id: int) -> bool:
        conn = None
        cursor = None
        try:
            conn = self.db.get_raw_connection()
            cursor = conn.cursor(dictionary=True)
            conn.autocommit = False

            cursor.execute("SELECT status FROM Sales WHERE id = %s", (sale_id,))
            sale = cursor.fetchone()
            if not sale or sale['status'] == 'CANCELLED':
                return False

            cursor.execute("SELECT * FROM SaleItems WHERE sale_id = %s", (sale_id,))
            items = cursor.fetchall()

            for item in items:
                inv_id = item['inventory_id']
                if not inv_id: continue

                if item['item_type'] == 'WEIGHT':
                    cursor.execute("""
                        UPDATE Inventory 
                        SET status = IF(reserved_for_client_id IS NOT NULL, 'Reserved',
                                    IF(remaining_weight + %s >= weight, 'Available', 'Partially_Sold')),
                            remaining_weight = remaining_weight + %s
                        WHERE id = %s
                    """, (item['sold_weight_g'], item['sold_weight_g'], inv_id))
                else:
                    cursor.execute("""
                        UPDATE Inventory 
                        SET status = IF(reserved_for_client_id IS NOT NULL, 'Reserved',
                                    IF(remaining_quantity + %s >= quantity, 'Available', 'Partially_Sold')),
                            remaining_quantity = remaining_quantity + %s
                        WHERE id = %s
                    """, (item['sold_quantity'], item['sold_quantity'], inv_id))

            cursor.execute("UPDATE Sales SET status = 'CANCELLED' WHERE id = %s", (sale_id,))
            conn.commit()
            return True

        except Exception as e:
            if conn: conn.rollback()
            logging.error(f"Erreur annulation vente: {e}")
            return False
        finally:
            if cursor: cursor.close()
            if conn: conn.close()

    # ============================================================
    # 3. تقارير الإكسيل والمجاميع
    # ============================================================
    def get_daily_sales_for_excel(self, journee_id: int) -> list:
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = """
                    SELECT 
                        s.id as sale_id,
                        si.id as item_id,
                        CONCAT(si.name, 
                               IF(cat.name IS NOT NULL AND cat.name != '', CONCAT(' | Cat: ', cat.name), ''),
                               IF(sup.name IS NOT NULL AND sup.name != '', CONCAT(' | Fourn: ', sup.name), '')
                        ) as Designation,
                        si.sold_weight_g as P_S,
                        IF(s.receipt_number NOT LIKE 'VRS-%' AND (SELECT id FROM SaleItems WHERE sale_id = s.id ORDER BY id ASC LIMIT 1) = si.id, s.cash_paid_da, 0) as Recette,
                        IF(s.receipt_number NOT LIKE 'VRS-%' AND (SELECT id FROM SaleItems WHERE sale_id = s.id ORDER BY id ASC LIMIT 1) = si.id, s.old_gold_weight_g, 0) as OC,
                        IF(s.receipt_number NOT LIKE 'VRS-%' AND (SELECT id FROM SaleItems WHERE sale_id = s.id ORDER BY id ASC LIMIT 1) = si.id, s.tpe_paid_da, 0) as TPE,
                        IF(s.receipt_number NOT LIKE 'VRS-%' AND (SELECT id FROM SaleItems WHERE sale_id = s.id ORDER BY id ASC LIMIT 1) = si.id, s.impos_weight_g, 0) as Impos,
                        0 as Euro,
                        0 as Dollar,
                        u.username as Vendeur_Sofiane,
                        s.user_id as vendeur_id,
                        COALESCE(NULLIF(si.custom_note, ''), NULLIF(s.notes, ''), CONCAT('Fac: ', s.receipt_number, ' - ', COALESCE(c.name, ''))) as Observation,
                        s.created_at as timestamp
                    FROM SaleItems si
                    JOIN Sales s ON si.sale_id = s.id
                    LEFT JOIN Users u ON s.user_id = u.id
                    LEFT JOIN Clients c ON s.client_id = c.id
                    LEFT JOIN Inventory i ON si.inventory_id = i.id
                    LEFT JOIN Categories cat ON i.category_id = cat.id
                    LEFT JOIN Suppliers sup ON i.supplier_id = sup.id
                    WHERE s.journee_id = %s AND s.status = 'COMPLETED'
                """
                cursor.execute(query, (journee_id,))
                sales_results = cursor.fetchall()
                
                query_vp = """
                    SELECT 
                        CONCAT('VRS_', vp.versement_id) as sale_id,
                        vp.id as item_id,
                        CONCAT('Versement Client: ', COALESCE(c.name, '')) as Designation,
                        0.0 as P_S,
                        IF(COALESCE(vp.montant_euro, 0) > 0 OR COALESCE(vp.montant_dollar, 0) > 0 OR COALESCE(vp.or_casse_g, 0) > 0, 0.0, vp.montant_da) as Recette,
                        vp.or_casse_g as OC,
                        vp.tpe_da as TPE,
                        0.0 as Impos,
                        vp.montant_euro as Euro,
                        vp.montant_dollar as Dollar,
                        '' as Vendeur_Sofiane,
                        NULL as vendeur_id,
                        COALESCE(NULLIF(vp.notes, ''), CONCAT('Versement N° VRS-', vp.versement_id)) as Observation,
                        vp.payment_date as timestamp
                    FROM Versement_Payments vp
                    JOIN Versements v ON vp.versement_id = v.id
                    LEFT JOIN Clients c ON v.client_id = c.id
                    WHERE vp.journee_id = %s
                """
                cursor.execute(query_vp, (journee_id,))
                vp_results = cursor.fetchall()
                
                all_results = sales_results + vp_results
                from datetime import datetime
                all_results.sort(key=lambda x: (x['timestamp'] if x['timestamp'] else datetime.min, str(x['sale_id']), x['item_id']))
                
                return all_results
        except Exception as e:
            logging.error(f"Erreur get_daily_sales_for_excel: {e}")
            return []

    def get_daily_totals(self, journee_id: int) -> dict:
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = """
                    SELECT 
                        SUM(CASE WHEN receipt_number NOT LIKE 'VRS-%' THEN cash_paid_da ELSE 0 END) as total_recette,
                        SUM(CASE WHEN receipt_number NOT LIKE 'VRS-%' THEN tpe_paid_da ELSE 0 END) as total_tpe,
                        SUM(CASE WHEN receipt_number NOT LIKE 'VRS-%' THEN old_gold_weight_g ELSE 0 END) as total_oc,
                        SUM(CASE WHEN receipt_number NOT LIKE 'VRS-%' THEN impos_weight_g ELSE 0 END) as total_impos
                    FROM Sales 
                    WHERE journee_id = %s AND status = 'COMPLETED'
                """
                cursor.execute(query, (journee_id,))
                sales_totals = cursor.fetchone()

                cursor.execute("""
                    SELECT SUM(sold_weight_g) as total_p_s 
                    FROM SaleItems si 
                    JOIN Sales s ON si.sale_id = s.id 
                    WHERE s.journee_id = %s AND s.status = 'COMPLETED'
                """, (journee_id,))
                weight_totals = cursor.fetchone()
                
                cursor.execute("""
                    SELECT 
                        SUM(montant_da) as total_recette,
                        SUM(tpe_da) as total_tpe,
                        SUM(or_casse_g) as total_oc,
                        SUM(montant_euro) as total_euro,
                        SUM(montant_dollar) as total_dollar,
                        0.0 as total_p_s
                    FROM Versement_Payments 
                    WHERE journee_id = %s
                """, (journee_id,))
                vp_totals = cursor.fetchone()

                return {
                    'total_recette': float((sales_totals['total_recette'] or 0) + (vp_totals['total_recette'] or 0)),
                    'total_tpe': float((sales_totals['total_tpe'] or 0) + (vp_totals['total_tpe'] or 0)),
                    'total_oc': float((sales_totals['total_oc'] or 0) + (vp_totals['total_oc'] or 0)),
                    'total_euro': float(vp_totals['total_euro'] or 0),
                    'total_dollar': float(vp_totals['total_dollar'] or 0),
                    'total_p_s': float((weight_totals['total_p_s'] or 0) + (vp_totals['total_p_s'] or 0)),
                    'total_impos': float(sales_totals['total_impos'] or 0)
                }
        except Exception as e:
            logging.error(f"Erreur get_daily_totals: {e}")
            return {}

    # ============================================================
    # 4. تعديل المبالغ المالية لفاتورة منجزة
    # ============================================================
    def update_sale_financials(self, sale_id: int, cash: float, tpe: float, oc: float, impos: float) -> bool:
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                query = """
                    UPDATE Sales 
                    SET cash_paid_da = %s, tpe_paid_da = %s, old_gold_weight_g = %s, impos_weight_g = %s
                    WHERE id = %s
                """
                cursor.execute(query, (cash, tpe, oc, impos, sale_id))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Erreur update_sale_financials: {e}")
            return False

    def update_sale_notes(self, sale_id: int, notes: str) -> bool:
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                query = "UPDATE Sales SET notes = %s WHERE id = %s"
                cursor.execute(query, (notes, sale_id))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Erreur update_sale_notes: {e}")
            return False
    
    # ============================================================
    # 6. جلب تفاصيل فاتورة محددة (للطباعة والتفاصيل)
    # ============================================================
    def update_sale_seller(self, sale_id: int, seller_id: int) -> bool:
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE Sales SET user_id = %s WHERE id = %s", (seller_id, sale_id))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Erreur update_sale_seller: {e}")
            return False
    def update_sale_item_notes(self, sale_item_id: int, notes: str) -> bool:
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                custom_note = str(notes or '').strip()[:255]
                cursor.execute("UPDATE SaleItems SET custom_note = %s WHERE id = %s", (custom_note, sale_item_id))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Erreur update_sale_item_notes: {e}")
            return False

    def _enrich_versement_closure_sale(self, cursor, sale: dict) -> None:
        """Attach the payment source to final and individual Versement sales."""
        from database.versement_invoice_summary import build_versement_payment_summary

        versement_id = source_versement_id(sale.get("receipt_number"), sale.get("notes"))
        if versement_id is None:
            return

        cursor.execute("""
            SELECT p.*, vi.designation AS item_designation,
                   vi.inventory_id AS payment_inventory_id
            FROM Versement_Payments p
            LEFT JOIN Versement_Items vi ON vi.id = p.versement_item_id
            WHERE p.versement_id = %s
            ORDER BY p.payment_date ASC, p.id ASC
        """, (versement_id,))
        payments = cursor.fetchall()
        is_final_versement_invoice = str(sale.get("receipt_number") or "").upper().startswith("VRS-")
        if not is_final_versement_invoice:
            cutoff = sale.get("created_at")
            cutoff_day = str(cutoff.date() if hasattr(cutoff, "date") else cutoff or "")[:10]
            if cutoff_day:
                def paid_on_or_before_delivery(payment):
                    payment_date = payment.get("payment_date")
                    payment_day = str(payment_date.date() if hasattr(payment_date, "date") else payment_date or "")[:10]
                    return not payment_day or payment_day <= cutoff_day

                payments = [payment for payment in payments if paid_on_or_before_delivery(payment)]

        sale["source_versement_id"] = versement_id

        if is_final_versement_invoice:
            summary = build_versement_payment_summary(payments)
            sale["total_amount_da"] = summary["total_brut_da"]
            sale["discount_da"] = summary["total_remise_da"]
            sale["net_to_pay_da"] = summary["net_to_pay_da"]
            sale["cash_paid_da"] = summary["cash_paid_da"]
            sale["tpe_paid_da"] = summary["tpe_paid_da"]
            sale["old_gold_weight_g"] = summary["old_gold_weight_g"]
            sale["impos_weight_g"] = summary["deducted_weight_g"]
            sale["versement_payment_summary"] = summary
            sale["payments_history"] = summary["payment_history"]

        cursor.execute("""
            SELECT vi.inventory_id,
                   COALESCE(i.weight, 0) AS inventory_weight,
                   COALESCE(i.quantity, 0) AS inventory_quantity
            FROM Versement_Items vi
            LEFT JOIN Inventory i ON i.id = vi.inventory_id
            WHERE vi.versement_id = %s AND vi.item_status != 'ANNULE'
        """, (versement_id,))
        source_items = cursor.fetchall()
        revenue_by_inventory = versement_revenues_by_inventory(source_items, payments)
        for item in sale.get("items") or []:
            item["paid_amount_da"] = number(revenue_by_inventory.get(item.get("inventory_id")))

    def _attach_profit_metrics(self, sale: dict) -> None:
        """Attach net realised revenue, historical cost and profit per item."""
        items = sale.get("items") or []
        if not items:
            sale["total_profit_da"] = 0.0
            sale["total_realized_revenue_da"] = 0.0
            sale["total_cost_da"] = 0.0
            return

        has_versement_source = source_versement_id(sale.get("receipt_number"), sale.get("notes")) is not None
        revenues = (
            [number(item.get("paid_amount_da")) for item in items]
            if has_versement_source
            else direct_sale_revenues(items, sale.get("discount_da"))
        )
        total_profit = total_cost = total_revenue = 0.0
        for item, revenue in zip(items, revenues):
            cost = item_cost_da(item)
            profit = revenue - cost
            item["realized_revenue_da"] = revenue
            item["cost_da"] = cost
            item["profit_da"] = profit
            total_revenue += revenue
            total_cost += cost
            total_profit += profit

        sale["total_realized_revenue_da"] = total_revenue
        sale["total_cost_da"] = total_cost
        sale["total_profit_da"] = total_profit

    def get_sale_details(self, sale_id: int) -> dict:
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query_sale = """
                    SELECT s.*, c.name as client_name, u.username as user_name
                    FROM Sales s
                    LEFT JOIN Clients c ON s.client_id = c.id
                    LEFT JOIN Users u ON s.user_id = u.id
                    WHERE s.id = %s
                """
                cursor.execute(query_sale, (sale_id,))
                sale = cursor.fetchone()
                while cursor.nextset():
                    pass
                if not sale:
                    return None

                cursor.execute("""
                    SELECT si.*,
                           COALESCE(i.initial_cost, i.total_cost, 0) AS inventory_initial_cost,
                           COALESCE(i.weight, 0) AS inventory_weight,
                           COALESCE(i.quantity, 0) AS inventory_quantity,
                           COALESCE(i.metal_cost_per_gram, 0) AS metal_cost_per_gram,
                           COALESCE(i.labor_cost_per_gram, 0) AS labor_cost_per_gram
                    FROM SaleItems si
                    LEFT JOIN Inventory i ON i.id = si.inventory_id
                    WHERE si.sale_id = %s
                """, (sale_id,))
                sale["items"] = cursor.fetchall()
                while cursor.nextset():
                    pass

                self._enrich_versement_closure_sale(cursor, sale)
                self._attach_profit_metrics(sale)
                return sale
        except Exception as e:
            logging.error(f"Erreur get_sale_details: {e}")
            return None

    def get_sale_profit_details(self, sale_id: int) -> dict:
        """Return a sale with report-safe revenue, cost and profit metrics."""
        return self.get_sale_details(sale_id)

    def get_monthly_profit_by_day(self, year: int, month: int) -> dict:
        """Aggregate realised profit by the date on which each sale was delivered."""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute("""
                    SELECT id, DATE(created_at) AS sale_date
                    FROM Sales
                    WHERE YEAR(created_at) = %s AND MONTH(created_at) = %s
                      AND status = 'COMPLETED'
                    ORDER BY created_at, id
                """, (year, month))
                sales = cursor.fetchall()
                while cursor.nextset():
                    pass

            by_day = {}
            for row in sales:
                sale = self.get_sale_profit_details(row["id"])
                if not sale:
                    continue
                day = row["sale_date"]
                entry = by_day.setdefault(day, {"profit_da": 0.0, "revenue_da": 0.0, "cost_da": 0.0})
                entry["profit_da"] += number(sale.get("total_profit_da"))
                entry["revenue_da"] += number(sale.get("total_realized_revenue_da"))
                entry["cost_da"] += number(sale.get("total_cost_da"))
            return by_day
        except Exception as e:
            logging.error(f"Erreur get_monthly_profit_by_day: {e}")
            return {}
