import logging
from datetime import datetime

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
                
                custom_note = item.get('custom_note', '') # 🟢 سحب الملاحظة من السلة

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
                            SET remaining_weight = GREATEST(0, remaining_weight - %s),
                                status = IF(remaining_weight - %s <= 0.005, 'Sold', 'Partially_Sold')
                            WHERE id = %s
                        """, (sold_w, sold_w, inv_id))
                    else:
                        cursor.execute("""
                            UPDATE Inventory 
                            SET remaining_quantity = GREATEST(0, remaining_quantity - %s),
                                status = IF(remaining_quantity - %s <= 0, 'Sold', 'Partially_Sold')
                            WHERE id = %s
                        """, (sold_q, sold_q, inv_id))

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
                        SET remaining_weight = remaining_weight + %s,
                            status = IF(remaining_weight + %s >= weight, 'Available', 'Partially_Sold')
                        WHERE id = %s
                    """, (item['sold_weight_g'], item['sold_weight_g'], inv_id))
                else:
                    cursor.execute("""
                        UPDATE Inventory 
                        SET remaining_quantity = remaining_quantity + %s,
                            status = IF(remaining_quantity + %s >= quantity, 'Available', 'Partially_Sold')
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
                        IF((SELECT id FROM SaleItems WHERE sale_id = s.id ORDER BY id ASC LIMIT 1) = si.id, s.cash_paid_da, 0) as Recette,
                        IF((SELECT id FROM SaleItems WHERE sale_id = s.id ORDER BY id ASC LIMIT 1) = si.id, s.old_gold_weight_g, 0) as OC,
                        IF((SELECT id FROM SaleItems WHERE sale_id = s.id ORDER BY id ASC LIMIT 1) = si.id, s.tpe_paid_da, 0) as TPE,
                        IF((SELECT id FROM SaleItems WHERE sale_id = s.id ORDER BY id ASC LIMIT 1) = si.id, s.impos_weight_g, 0) as Impos,
                        0 as Euro,
                        0 as Dollar,
                        u.username as Vendeur_Sofiane,
                        COALESCE(NULLIF(s.notes, ''), CONCAT('Fac: ', s.receipt_number, ' - ', COALESCE(c.name, ''))) as Observation,
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
                        0.0 as TPE,
                        0.0 as Impos,
                        vp.montant_euro as Euro,
                        vp.montant_dollar as Dollar,
                        '' as Vendeur_Sofiane,
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
                        SUM(cash_paid_da) as total_recette,
                        SUM(tpe_paid_da) as total_tpe,
                        SUM(old_gold_weight_g) as total_oc,
                        SUM(impos_weight_g) as total_impos
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
                        SUM(CASE WHEN montant_da > 0 AND COALESCE(montant_euro, 0) = 0 AND COALESCE(montant_dollar, 0) = 0 AND COALESCE(or_casse_g, 0) = 0 THEN montant_da ELSE 0 END) as total_recette,
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
                    'total_tpe': float(sales_totals['total_tpe'] or 0),
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
                while cursor.nextset(): pass
                
                if not sale: return None

                cursor.execute("SELECT * FROM SaleItems WHERE sale_id = %s", (sale_id,))
                items = cursor.fetchall()
                while cursor.nextset(): pass
                
                sale['items'] = items
                return sale
        except Exception as e:
            logging.error(f"Erreur get_sale_details: {e}")
            return None
