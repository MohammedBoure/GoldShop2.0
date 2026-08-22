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
                    old_gold_weight: float = 0.0, impos_weight: float = 0.0,
                    euro_paid: float = 0.0, taux_change_euro: float = 0.0,
                    dollar_paid: float = 0.0, taux_change_dollar: float = 0.0,
                    notes: str = "",
                    old_silver_weight: float = 0.0, old_silver_price: float = 0.0) -> dict:
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
                    cash_paid_da, tpe_paid_da, old_gold_weight_g, old_silver_weight_g, old_silver_price_da, impos_weight_g,
                    euro_paid, taux_change_euro, dollar_paid, taux_change_dollar,
                    notes
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(sale_query, (
                receipt_number, journee_id, client_id, user_id,
                total_amount, discount, net_to_pay, cash_paid, tpe_paid,
                old_gold_weight, old_silver_weight, old_silver_price, impos_weight,
                euro_paid, taux_change_euro, dollar_paid, taux_change_dollar,
                notes
            ))
            sale_id = cursor.lastrowid

            for item in cart_items:
                inv_id = item.get('inventory_id') or item.get('id')
                item_type = str(item.get('item_type') or 'WEIGHT').upper()
                barcode = item.get('barcode', '')
                name = item.get('name', 'Article inconnu')
                
                sold_w = float(item.get('cart_sold_weight', 0))
                sold_q = int(item.get('cart_sold_qty', 1))
                unit_price = float(item.get('cart_unit_price', 0))
                total_price = float(item.get('cart_line_total', 0))
                
                custom_note = str(item.get('custom_note') or '').strip()[:255]
                metal_type_id = item.get('metal_type_id')
                metal_category = str(item.get('metal_category') or '').upper()

                if inv_id:
                    cursor.execute("""
                        SELECT id, item_type, weight, remaining_weight, quantity, remaining_quantity,
                               status, reserved_for_client_id, metal_type_id
                        FROM Inventory WHERE id = %s FOR UPDATE
                    """, (inv_id,))
                    inventory = cursor.fetchone()
                    if not inventory:
                        raise ValueError("Article d'inventaire introuvable.")

                    cursor.execute("""
                        SELECT
                            COALESCE(SUM(COALESCE(reserved_quantity, 1)), 0) AS active_reserved_quantity,
                            COUNT(*) AS active_versement_count
                        FROM Versement_Items
                        WHERE inventory_id = %s AND item_status = 'EN_COURS'
                    """, (inv_id,))
                    reservation = cursor.fetchone() or {}
                    active_reserved_quantity = int(reservation.get("active_reserved_quantity") or 0)
                    active_versement_count = int(reservation.get("active_versement_count") or 0)

                    db_item_type = str(inventory.get("item_type") or item_type).upper()
                    status = inventory.get("status")
                    reserved_for_client_id = inventory.get("reserved_for_client_id")
                    if reserved_for_client_id and str(reserved_for_client_id) != str(client_id):
                        raise ValueError("Cet article est réservé à un autre client.")

                    if not metal_type_id:
                        metal_type_id = inventory.get('metal_type_id')
                    if not metal_category or metal_category not in ('GOLD', 'SILVER'):
                        metal_category = inventory.get('metal_category') or 'GOLD'

                    if db_item_type in ("PIECE", "UNIT"):
                        remaining_quantity = int(inventory.get("remaining_quantity") if inventory.get("remaining_quantity") is not None else inventory.get("quantity") or 1)
                        sellable_quantity = max(0, remaining_quantity - active_reserved_quantity)
                        if sold_q <= 0 or sold_q > sellable_quantity:
                            raise ValueError(
                                f"Quantité demandée ({sold_q}) supérieure à la quantité disponible ({sellable_quantity})."
                            )
                        if status == 'Sold' and remaining_quantity <= 0:
                            raise ValueError("Cet article est déjà totalement vendu.")
                    else:
                        remaining_weight = float(inventory.get("remaining_weight") if inventory.get("remaining_weight") is not None else inventory.get("weight") or 0.0)
                        if active_versement_count > 0:
                            raise ValueError("Cet article pondéré est actuellement réservé dans un versement.")
                        if sold_w <= 0 or sold_w > remaining_weight + 0.005:
                            raise ValueError("Le poids demandé dépasse le poids disponible.")
                        if status == 'Sold' and remaining_weight <= 0.005:
                            raise ValueError("Cet article est déjà totalement vendu.")

                if not metal_category or metal_category not in ('GOLD', 'SILVER'):
                    metal_category = 'GOLD'

                item_query = """
                    INSERT INTO SaleItems (
                        sale_id, inventory_id, metal_type_id, metal_category, barcode, name, item_type, 
                        sold_weight_g, sold_quantity, unit_price_da, total_price_da, custom_note
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                cursor.execute(item_query, (
                    sale_id, inv_id, metal_type_id, metal_category, barcode, name, item_type,
                    sold_w, sold_q, unit_price, total_price, custom_note # 🟢 إرسال الملاحظة هنا
                ))

                if inv_id:
                    # Fetch actual item_type from DB to ensure correct update logic
                    cursor.execute("SELECT item_type FROM Inventory WHERE id = %s", (inv_id,))
                    db_row = cursor.fetchone()
                    db_item_type = str((db_row or {}).get('item_type') or item_type).upper()

                    if db_item_type == 'WEIGHT':
                        cursor.execute("""
                            UPDATE Inventory 
                            SET status = IF(COALESCE(remaining_weight, weight) - %s <= 0.005 OR COALESCE(remaining_quantity, quantity) - %s <= 0, 'Sold', 'Partially_Sold'),
                                remaining_weight = GREATEST(0, COALESCE(remaining_weight, weight) - %s),
                                remaining_quantity = GREATEST(0, COALESCE(remaining_quantity, quantity) - %s)
                            WHERE id = %s
                        """, (sold_w, sold_q, sold_w, sold_q, inv_id))
                    else:
                        # PIECE / UNIT: evaluate status BEFORE modifying remaining_quantity
                        cursor.execute("""
                            UPDATE Inventory 
                            SET status = IF(COALESCE(remaining_quantity, quantity) - %s <= 0, 'Sold',
                                        IF(COALESCE(remaining_quantity, quantity) - %s < COALESCE(quantity, 1), 'Partially_Sold', 'Available')),
                                remaining_quantity = GREATEST(0, COALESCE(remaining_quantity, quantity) - %s)
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

            cursor.execute("SELECT status, receipt_number, notes FROM Sales WHERE id = %s FOR UPDATE", (sale_id,))
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
                                    IF(LEAST(weight, COALESCE(remaining_weight, 0) + %s) >= weight, 'Available', 'Partially_Sold')),
                            remaining_weight = LEAST(weight, COALESCE(remaining_weight, 0) + %s)
                        WHERE id = %s
                    """, (float(item['sold_weight_g'] or 0), float(item['sold_weight_g'] or 0), inv_id))
                else:
                    cursor.execute("""
                        UPDATE Inventory 
                        SET status = IF(reserved_for_client_id IS NOT NULL, 'Reserved',
                                    IF(LEAST(quantity, COALESCE(remaining_quantity, 0) + %s) >= quantity, 'Available', 'Partially_Sold')),
                            remaining_quantity = LEAST(quantity, COALESCE(remaining_quantity, 0) + %s)
                        WHERE id = %s
                    """, (int(item['sold_quantity'] or 1), int(item['sold_quantity'] or 1), inv_id))

            cursor.execute("UPDATE Sales SET status = 'CANCELLED' WHERE id = %s", (sale_id,))

            v_id = source_versement_id(sale.get("receipt_number"), sale.get("notes"))
            if v_id:
                cursor.execute("SELECT status FROM Versements WHERE id = %s", (v_id,))
                v_row = cursor.fetchone()
                if v_row and v_row.get("status") == "CLOTURE":
                    cursor.execute("UPDATE Versements SET status = 'EN_COURS' WHERE id = %s", (v_id,))
                    cursor.execute(
                        "UPDATE Versement_Items SET item_status = 'EN_COURS' WHERE versement_id = %s AND item_status = 'RETIRE'",
                        (v_id,)
                    )

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
    def get_bulk_sales_for_excel(self, journee_ids: list) -> dict:
        """
        جلب جميع بيانات المبيعات والدفعات لعدة جلسات يومية في استعلام واحد مجمع 
        لتحقيق أقصى سرعة وأداء، مع تمييز دقيق بين الذهب والفضة في الوزن والكسر.
        """
        if not journee_ids:
            return {}
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                format_strings = ','.join(['%s'] * len(journee_ids))
                query = f"""
                    SELECT 
                        s.journee_id,
                        s.id as sale_id,
                        s.receipt_number as receipt_number,
                        si.id as item_id,
                        COALESCE(NULLIF(si.barcode, ''), i.barcode, '') as barcode,
                        c.name as client_name,
                        CONCAT(si.name, 
                               IF(cat.name IS NOT NULL AND cat.name != '', CONCAT(' | Cat: ', cat.name), ''),
                               IF(sup.name IS NOT NULL AND sup.name != '', CONCAT(' | Fourn: ', sup.name), '')
                        ) as Designation,
                        si.sold_weight_g as P_S,
                        COALESCE(si.metal_category, mt.metal_category, 'GOLD') as metal_category,
                        IF(COALESCE(si.metal_category, mt.metal_category, 'GOLD') = 'SILVER', si.sold_weight_g, 0) as P_S_Silver,
                        IF(COALESCE(si.metal_category, mt.metal_category, 'GOLD') = 'GOLD', si.sold_weight_g, 0) as P_S_Gold,
                        IF(s.receipt_number NOT LIKE 'VRS-%' AND (SELECT id FROM SaleItems WHERE sale_id = s.id ORDER BY id ASC LIMIT 1) = si.id, s.cash_paid_da, 0) as Recette,
                        IF(s.receipt_number NOT LIKE 'VRS-%' AND (SELECT id FROM SaleItems WHERE sale_id = s.id ORDER BY id ASC LIMIT 1) = si.id, s.old_gold_weight_g, 0) as OC,
                        IF(s.receipt_number NOT LIKE 'VRS-%' AND (SELECT id FROM SaleItems WHERE sale_id = s.id ORDER BY id ASC LIMIT 1) = si.id, s.old_gold_weight_g, 0) as OC_Gold,
                        IF(s.receipt_number NOT LIKE 'VRS-%' AND (SELECT id FROM SaleItems WHERE sale_id = s.id ORDER BY id ASC LIMIT 1) = si.id, COALESCE(s.old_silver_weight_g, 0), 0) as OC_Silver,
                        IF(s.receipt_number NOT LIKE 'VRS-%' AND (SELECT id FROM SaleItems WHERE sale_id = s.id ORDER BY id ASC LIMIT 1) = si.id, s.tpe_paid_da, 0) as TPE,
                        IF(s.receipt_number NOT LIKE 'VRS-%' AND (SELECT id FROM SaleItems WHERE sale_id = s.id ORDER BY id ASC LIMIT 1) = si.id, s.impos_weight_g, 0) as Impos,
                        IF(s.receipt_number NOT LIKE 'VRS-%' AND (SELECT id FROM SaleItems WHERE sale_id = s.id ORDER BY id ASC LIMIT 1) = si.id, COALESCE(s.euro_paid, 0), 0) as Euro,
                        IF(s.receipt_number NOT LIKE 'VRS-%' AND (SELECT id FROM SaleItems WHERE sale_id = s.id ORDER BY id ASC LIMIT 1) = si.id, COALESCE(s.dollar_paid, 0), 0) as Dollar,
                        u.username as Vendeur_Name,
                        s.user_id as vendeur_id,
                        COALESCE(NULLIF(s.notes, ''), NULLIF(si.custom_note, ''), CONCAT('Fac: ', s.receipt_number)) as raw_notes,
                        s.created_at as timestamp
                    FROM SaleItems si
                    JOIN Sales s ON si.sale_id = s.id
                    LEFT JOIN Users u ON s.user_id = u.id
                    LEFT JOIN Clients c ON s.client_id = c.id
                    LEFT JOIN Inventory i ON si.inventory_id = i.id
                    LEFT JOIN MetalTypes mt ON COALESCE(si.metal_type_id, i.metal_type_id) = mt.id
                    LEFT JOIN Categories cat ON i.category_id = cat.id
                    LEFT JOIN Suppliers sup ON i.supplier_id = sup.id
                    WHERE s.journee_id IN ({format_strings}) AND s.status = 'COMPLETED'
                """
                cursor.execute(query, tuple(journee_ids))
                sales_results = cursor.fetchall()
                while cursor.nextset(): pass
                
                query_vp = f"""
                    SELECT 
                        vp.journee_id,
                        CONCAT('VRS_', vp.versement_id) as sale_id,
                        CONCAT('VRS-', LPAD(vp.versement_id, 5, '0')) as receipt_number,
                        vp.id as item_id,
                        COALESCE(vi_inv.barcode, '') as barcode,
                        c.name as client_name,
                        CONCAT('Versement N° VRS-', LPAD(vp.versement_id, 5, '0'), IF(vi.designation IS NOT NULL AND vi.designation != '', CONCAT(' | ', vi.designation), '')) as Designation,
                        0.0 as P_S,
                        'GOLD' as metal_category,
                        0.0 as P_S_Silver,
                        0.0 as P_S_Gold,
                        IF(COALESCE(vp.montant_euro, 0) > 0 OR COALESCE(vp.montant_dollar, 0) > 0 OR COALESCE(vp.or_casse_g, 0) > 0 OR COALESCE(vp.argent_casse_g, 0) > 0, 0.0, vp.montant_da) as Recette,
                        vp.or_casse_g as OC,
                        vp.or_casse_g as OC_Gold,
                        COALESCE(vp.argent_casse_g, 0) as OC_Silver,
                        vp.tpe_da as TPE,
                        0.0 as Impos,
                        vp.montant_euro as Euro,
                        vp.montant_dollar as Dollar,
                        '' as Vendeur_Name,
                        NULL as vendeur_id,
                        COALESCE(NULLIF(vp.notes, ''), CONCAT('Versement N° VRS-', LPAD(vp.versement_id, 5, '0'))) as raw_notes,
                        vp.payment_date as timestamp
                    FROM Versement_Payments vp
                    JOIN Versements v ON vp.versement_id = v.id
                    LEFT JOIN Clients c ON v.client_id = c.id
                    LEFT JOIN Versement_Items vi ON vp.versement_item_id = vi.id
                    LEFT JOIN Inventory vi_inv ON vi.inventory_id = vi_inv.id
                    WHERE vp.journee_id IN ({format_strings})
                """
                cursor.execute(query_vp, tuple(journee_ids))
                vp_results = cursor.fetchall()
                while cursor.nextset(): pass
                
                results_by_session = {jid: [] for jid in journee_ids}
                from datetime import datetime
                for r in sales_results + vp_results:
                    jid = r.get('journee_id')
                    c_name = r.get('client_name')
                    r_notes = str(r.get('raw_notes') or r.get('Observation') or '').strip()
                    obs_parts = []
                    if c_name and str(c_name).strip() and str(c_name).strip() != 'Passager':
                        obs_parts.append(f"Client: {str(c_name).strip()}")
                    if r_notes:
                        if c_name and f" - {c_name}" in r_notes:
                            r_notes = r_notes.replace(f" - {c_name}", "").strip()
                        if r_notes and r_notes not in obs_parts:
                            obs_parts.append(r_notes)
                    r['Observation'] = " | ".join(obs_parts) if obs_parts else (r_notes or "-")
                    if jid in results_by_session:
                        results_by_session[jid].append(r)

                for jid in results_by_session:
                    results_by_session[jid].sort(key=lambda x: (x['timestamp'] if x['timestamp'] else datetime.min, str(x['sale_id']), x['item_id']))
                
                return results_by_session
        except Exception as e:
            logging.error(f"Erreur get_bulk_sales_for_excel: {e}")
            return {jid: [] for jid in journee_ids}

    def get_daily_sales_for_excel(self, journee_id: int) -> list:
        res = self.get_bulk_sales_for_excel([journee_id])
        return res.get(journee_id, [])

    def get_daily_totals(self, journee_id: int) -> dict:
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = """
                    SELECT 
                        SUM(CASE WHEN receipt_number NOT LIKE 'VRS-%' THEN cash_paid_da ELSE 0 END) as total_recette,
                        SUM(CASE WHEN receipt_number NOT LIKE 'VRS-%' THEN tpe_paid_da ELSE 0 END) as total_tpe,
                        SUM(CASE WHEN receipt_number NOT LIKE 'VRS-%' THEN old_gold_weight_g ELSE 0 END) as total_oc_gold,
                        SUM(CASE WHEN receipt_number NOT LIKE 'VRS-%' THEN COALESCE(old_silver_weight_g, 0) ELSE 0 END) as total_oc_silver,
                        SUM(CASE WHEN receipt_number NOT LIKE 'VRS-%' THEN COALESCE(euro_paid, 0) ELSE 0 END) as total_euro,
                        SUM(CASE WHEN receipt_number NOT LIKE 'VRS-%' THEN COALESCE(dollar_paid, 0) ELSE 0 END) as total_dollar,
                        SUM(CASE WHEN receipt_number NOT LIKE 'VRS-%' THEN impos_weight_g ELSE 0 END) as total_impos
                    FROM Sales 
                    WHERE journee_id = %s AND status = 'COMPLETED'
                """
                cursor.execute(query, (journee_id,))
                sales_totals = cursor.fetchone() or {}

                cursor.execute("""
                    SELECT 
                        SUM(CASE WHEN COALESCE(si.metal_category, mt.metal_category, 'GOLD') = 'GOLD' THEN si.sold_weight_g ELSE 0 END) as total_p_s_gold,
                        SUM(CASE WHEN COALESCE(si.metal_category, mt.metal_category, 'GOLD') = 'SILVER' THEN si.sold_weight_g ELSE 0 END) as total_p_s_silver,
                        SUM(si.sold_weight_g) as total_p_s 
                    FROM SaleItems si 
                    JOIN Sales s ON si.sale_id = s.id 
                    LEFT JOIN Inventory i ON si.inventory_id = i.id
                    LEFT JOIN MetalTypes mt ON COALESCE(si.metal_type_id, i.metal_type_id) = mt.id
                    WHERE s.journee_id = %s AND s.status = 'COMPLETED'
                """, (journee_id,))
                weight_totals = cursor.fetchone() or {}
                
                cursor.execute("""
                    SELECT 
                        SUM(montant_da) as total_recette,
                        SUM(tpe_da) as total_tpe,
                        SUM(or_casse_g) as total_oc_gold,
                        SUM(COALESCE(argent_casse_g, 0)) as total_oc_silver,
                        SUM(montant_euro) as total_euro,
                        SUM(montant_dollar) as total_dollar,
                        0.0 as total_p_s,
                        0.0 as total_p_s_gold,
                        0.0 as total_p_s_silver
                    FROM Versement_Payments 
                    WHERE journee_id = %s
                """, (journee_id,))
                vp_totals = cursor.fetchone() or {}

                total_oc_gold = float((sales_totals.get('total_oc_gold') or 0) + (vp_totals.get('total_oc_gold') or 0))
                total_oc_silver = float((sales_totals.get('total_oc_silver') or 0) + (vp_totals.get('total_oc_silver') or 0))
                total_ps_gold = float(weight_totals.get('total_p_s_gold') or 0)
                total_ps_silver = float(weight_totals.get('total_p_s_silver') or 0)
                total_ps = float((weight_totals.get('total_p_s') or 0) + (vp_totals.get('total_p_s') or 0))

                return {
                    'total_recette': float((sales_totals.get('total_recette') or 0) + (vp_totals.get('total_recette') or 0)),
                    'total_tpe': float((sales_totals.get('total_tpe') or 0) + (vp_totals.get('total_tpe') or 0)),
                    'total_oc': total_oc_gold,
                    'total_oc_gold': total_oc_gold,
                    'total_oc_silver': total_oc_silver,
                    'total_euro': float((sales_totals.get('total_euro') or 0) + (vp_totals.get('total_euro') or 0)),
                    'total_dollar': float((sales_totals.get('total_dollar') or 0) + (vp_totals.get('total_dollar') or 0)),
                    'total_p_s': total_ps,
                    'total_p_s_gold': total_ps_gold,
                    'total_p_s_silver': total_ps_silver,
                    'total_impos': float(sales_totals.get('total_impos') or 0)
                }
        except Exception as e:
            logging.error(f"Erreur get_daily_totals: {e}")
            return {}

    # ============================================================
    # 4. تعديل المبالغ المالية لفاتورة منجزة
    # ============================================================
    def update_sale_financials(self, sale_id: int, cash: float, tpe: float, oc: float, 
                               euro: float = 0.0, dollar: float = 0.0, impos: float = 0.0, 
                               oc_silver: float = 0.0, *args, **kwargs) -> bool:
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                query = """
                    UPDATE Sales 
                    SET cash_paid_da = %s, tpe_paid_da = %s, old_gold_weight_g = %s, 
                        euro_paid = %s, dollar_paid = %s, impos_weight_g = %s,
                        old_silver_weight_g = %s
                    WHERE id = %s
                """
                cursor.execute(query, (cash, tpe, oc, euro, dollar, impos, oc_silver, sale_id))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Erreur update_sale_financials: {e}")
            return False

    def update_sale_notes(self, sale_id: int, notes: str) -> bool:
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                clean_note = str(notes or '').strip()
                cursor.execute("UPDATE Sales SET notes = %s WHERE id = %s", (clean_note, sale_id))
                cursor.execute("UPDATE SaleItems SET custom_note = %s WHERE sale_id = %s", (clean_note, sale_id))
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
                cursor.execute("SELECT sale_id FROM SaleItems WHERE id = %s", (sale_item_id,))
                row = cursor.fetchone()
                if row and row[0]:
                    cursor.execute("UPDATE Sales SET notes = %s WHERE id = %s", (custom_note, row[0]))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Erreur update_sale_item_notes: {e}")
            return False

    def update_sale_item_weight(self, sale_item_id: int, new_weight: float) -> bool:
        """تعديل وزن بند البيع (P.S) وتحديث إجمالي وزن البيع إذا لزم الأمر"""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE SaleItems SET sold_weight_g = %s WHERE id = %s", (new_weight, sale_item_id))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Erreur update_sale_item_weight: {e}")
            return False

    def _enrich_versement_closure_sale(self, cursor, sale: dict) -> None:
        """Attach the payment source to final and individual Versement sales."""
        from database.versement import build_versement_payment_summary

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
        summary = build_versement_payment_summary(payments)
        sale["versement_payment_summary"] = summary
        sale["payments_history"] = summary.get("payment_history", [])

        versement_remise = float(summary.get("total_remise_da") or 0.0)
        current_discount = float(sale.get("discount_da") or 0.0)
        final_discount = max(current_discount, versement_remise)
        sale["discount_da"] = final_discount

        if is_final_versement_invoice:
            sale["total_amount_da"] = summary["total_brut_da"]
            sale["net_to_pay_da"] = summary["net_to_pay_da"]
            sale["cash_paid_da"] = summary["cash_paid_da"]
            sale["tpe_paid_da"] = summary["tpe_paid_da"]
            sale["old_gold_weight_g"] = summary["old_gold_weight_g"]
            sale["impos_weight_g"] = summary["deducted_weight_g"]
        else:
            if final_discount > 0:
                cur_net = float(sale.get("net_to_pay_da") or sale.get("total_amount_da") or 0.0)
                cur_brut = float(sale.get("total_amount_da") or 0.0)
                if cur_brut <= cur_net:
                    sale["total_amount_da"] = cur_net + final_discount

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

    def update_sale_notes(self, sale_id: int, notes: str) -> bool:
        """Mettre à jour la note / observation globale de la vente"""
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

    def update_sale_item_notes(self, item_id: int, notes: str) -> bool:
        """Mettre à jour la note / observation d'un article de vente"""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                query = "UPDATE SaleItems SET custom_note = %s WHERE id = %s"
                cursor.execute(query, (notes, item_id))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Erreur update_sale_item_notes: {e}")
            return False

    def update_sale_seller(self, sale_id: int, user_id: int) -> bool:
        """Mettre à jour le vendeur d'une vente"""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                query = "UPDATE Sales SET user_id = %s WHERE id = %s"
                cursor.execute(query, (user_id, sale_id))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Erreur update_sale_seller: {e}")
            return False
