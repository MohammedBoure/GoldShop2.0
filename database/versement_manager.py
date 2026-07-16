import logging
from datetime import datetime

class VersementManager:
    """
    مدير عمليات العربون (Versements):
    يدير الإيداعات الحرة (A Vide) وحجوزات القطع (Produits) مع تتبع الوزن المتبقي وتحديث المخزون آلياً.
    """
    def __init__(self, db_instance):
        self.db = db_instance

    # ============================================================
    # 1. فتح ملف عربون جديد
    # ============================================================
    def create_versement(self, client_id: int, journee_id: int, type_versement: str,
                         items_list: list, montant_da: float, or_casse_g: float, 
                         prix_gramme_jour_da: float, notes: str = "",
                         montant_euro: float = 0.0, taux_change_euro: float = 0.0,
                         poids_deduit_g: float = 0.0, montant_dollar: float = 0.0,
                         taux_change_dollar: float = 0.0, remise_da: float = 0.0,
                         tpe_da: float = 0.0) -> dict:
        conn = None
        cursor = None
        try:
            conn = self.db.get_raw_connection()
            cursor = conn.cursor(dictionary=True)
            conn.autocommit = False

            cursor.execute("""
                INSERT INTO Versements (client_id, type_versement, status) 
                VALUES (%s, %s, 'EN_COURS')
            """, (client_id, type_versement))
            versement_id = cursor.lastrowid

            if type_versement == 'PRODUITS' and items_list:
                for item in items_list:
                    inv_id = item.get('inventory_id')
                    designation = item.get('designation', 'Article inconnu')
                    
                    cursor.execute("""
                        INSERT INTO Versement_Items (versement_id, inventory_id, designation, item_status)
                        VALUES (%s, %s, %s, 'EN_COURS')
                    """, (versement_id, inv_id, designation))
                    
                    if inv_id:
                        cursor.execute("UPDATE Inventory SET status = 'Reserved' WHERE id = %s", (inv_id,))

            if montant_da != 0 or tpe_da != 0 or or_casse_g != 0 or montant_euro != 0 or poids_deduit_g != 0 or montant_dollar != 0 or remise_da != 0:
                cursor.execute("""
                    INSERT INTO Versement_Payments 
                    (versement_id, journee_id, montant_da, tpe_da, montant_euro, taux_change_euro, montant_dollar, taux_change_dollar, remise_da, or_casse_g, poids_deduit_g, prix_gramme_jour_da, notes)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (versement_id, journee_id, montant_da, tpe_da, montant_euro, taux_change_euro, montant_dollar, taux_change_dollar, remise_da, or_casse_g, poids_deduit_g, prix_gramme_jour_da, notes))

            conn.commit()
            return {"success": True, "versement_id": versement_id}

        except Exception as e:
            if conn: conn.rollback()
            logging.error(f"Erreur création versement: {e}")
            return {"success": False, "message": str(e)}
        finally:
            if cursor: cursor.close()
            if conn: conn.close()

    # ============================================================
    # 2. إضافة وتعديل الدفعات (مع دعم الدفع لقطعة محددة)
    # ============================================================
    def add_payment(self, versement_id: int, journee_id: int, montant_da: float, 
                    or_casse_g: float, prix_gramme_jour_da: float, notes: str = "",
                    montant_euro: float = 0.0, taux_change_euro: float = 0.0,
                    poids_deduit_g: float = 0.0, versement_item_id: int = None,
                    montant_dollar: float = 0.0, taux_change_dollar: float = 0.0,
                    remise_da: float = 0.0, tpe_da: float = 0.0) -> bool:
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO Versement_Payments 
                    (versement_id, versement_item_id, journee_id, montant_da, tpe_da, montant_euro, taux_change_euro, montant_dollar, taux_change_dollar, remise_da, or_casse_g, poids_deduit_g, prix_gramme_jour_da, notes)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (versement_id, versement_item_id, journee_id, montant_da, tpe_da, montant_euro, taux_change_euro, montant_dollar, taux_change_dollar, remise_da, or_casse_g, poids_deduit_g, prix_gramme_jour_da, notes))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Erreur add_payment: {e}")
            return False

    def delete_payment(self, payment_id: int) -> bool:
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM Versement_Payments WHERE id = %s", (payment_id,))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Erreur delete_payment: {e}")
            return False

    # ============================================================
    # 3. إدارة القطع المنفصلة (الإلغاء والسحب)
    # ============================================================
    def cancel_versement_item(self, item_id: int) -> bool:
        """إلغاء قطعة معينة من العربون وإرجاعها للواجهة (المخزون)"""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("UPDATE Versement_Items SET item_status = 'ANNULE' WHERE id = %s", (item_id,))
                cursor.execute("""
                    UPDATE Inventory 
                    SET status = 'Available' 
                    WHERE id = (SELECT inventory_id FROM Versement_Items WHERE id = %s)
                """, (item_id,))
                
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Erreur cancel_versement_item: {e}")
            return False

    def retirer_versement_item(self, item_id: int) -> bool:
        """تأكيد سحب قطعة معينة (الزبون استلمها)"""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("UPDATE Versement_Items SET item_status = 'RETIRE' WHERE id = %s", (item_id,))
                cursor.execute("""
                    UPDATE Inventory 
                    SET status = 'Sold', remaining_weight = 0, remaining_quantity = 0 
                    WHERE id = (SELECT inventory_id FROM Versement_Items WHERE id = %s)
                """, (item_id,))
                
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Erreur retirer_versement_item: {e}")
            return False

    # ============================================================
    # 4. إنهاء أو إلغاء الملف بالكامل
    # ============================================================
    def cloture_versement(self, versement_id: int, journee_id: int = 1) -> bool:
        conn = None
        cursor = None
        try:
            conn = self.db.get_raw_connection()
            cursor = conn.cursor(dictionary=True)
            conn.autocommit = False

            cursor.execute("SELECT client_id FROM Versements WHERE id = %s", (versement_id,))
            v_data = cursor.fetchone()
            client_id = v_data['client_id'] if v_data else 1

            cursor.execute("""
                SELECT vi.inventory_id, vi.designation, i.weight, i.barcode 
                FROM Versement_Items vi 
                LEFT JOIN Inventory i ON vi.inventory_id = i.id 
                WHERE vi.versement_id = %s AND vi.item_status = 'EN_COURS'
            """, (versement_id,))
            items_to_retire = cursor.fetchall()

            cursor.execute("UPDATE Versements SET status = 'CLOTURE' WHERE id = %s", (versement_id,))
            cursor.execute("UPDATE Versement_Items SET item_status = 'RETIRE' WHERE versement_id = %s AND item_status = 'EN_COURS'", (versement_id,))
            cursor.execute("""
                UPDATE Inventory 
                SET status = 'Sold', remaining_weight = 0, remaining_quantity = 0 
                WHERE id IN (SELECT inventory_id FROM Versement_Items WHERE versement_id = %s AND item_status = 'RETIRE' AND inventory_id IS NOT NULL)
            """, (versement_id,))

            if items_to_retire:
                cursor.execute("""
                    INSERT INTO Sales (receipt_number, journee_id, client_id, user_id, total_amount_da, discount_da, net_to_pay_da, cash_paid_da, tpe_paid_da, old_gold_weight_g, impos_weight_g, status, notes, created_at)
                    VALUES (%s, %s, %s, 1, 0, 0, 0, 0, 0, 0, 0, 'COMPLETED', %s, NOW())
                """, (f"VRS-{versement_id:05d}", journee_id, client_id, f"Clôture Versement N° VRS-{versement_id:05d}"))
                sale_id = cursor.lastrowid

                for it in items_to_retire:
                    w = float(it['weight'] or 0)
                    barcode = str(it['barcode'] or '')
                    desig = str(it['designation'] or 'Article Versement')
                    cursor.execute("""
                        INSERT INTO SaleItems (sale_id, inventory_id, barcode, name, item_type, sold_weight_g, sold_quantity, unit_price_da, total_price_da, custom_note)
                        VALUES (%s, %s, %s, %s, 'WEIGHT', %s, 1, 0, 0, %s)
                    """, (sale_id, it['inventory_id'], barcode, desig, w, f"Clôture Versement N° VRS-{versement_id:05d}"))

            conn.commit()
            return True
        except Exception as e:
            if conn: conn.rollback()
            logging.error(f"Erreur cloture_versement: {e}")
            return False
        finally:
            if cursor: cursor.close()
            if conn: conn.close()

    def cancel_versement(self, versement_id: int) -> bool:
        conn = None
        cursor = None
        try:
            conn = self.db.get_raw_connection()
            cursor = conn.cursor()
            conn.autocommit = False

            cursor.execute("UPDATE Versements SET status = 'ANNULE' WHERE id = %s", (versement_id,))
            cursor.execute("UPDATE Versement_Items SET item_status = 'ANNULE' WHERE versement_id = %s AND item_status != 'RETIRE'", (versement_id,))
            
            cursor.execute("""
                UPDATE Inventory 
                SET status = 'Available' 
                WHERE id IN (SELECT inventory_id FROM Versement_Items WHERE versement_id = %s AND item_status = 'ANNULE' AND inventory_id IS NOT NULL)
            """, (versement_id,))

            conn.commit()
            return True
        except Exception as e:
            if conn: conn.rollback()
            logging.error(f"Erreur cancel_versement: {e}")
            return False
        finally:
            if cursor: cursor.close()
            if conn: conn.close()

    def change_versement_status(self, versement_id: int, target_status: str, journee_id: int = 1) -> tuple[bool, str]:
        """Change l'etat du dossier en gardant les pieces et la facture de cloture coherentes."""
        if target_status not in {'EN_COURS', 'CLOTURE', 'ANNULE'}:
            return False, "Statut cible invalide."

        conn = None
        cursor = None
        try:
            conn = self.db.get_raw_connection()
            cursor = conn.cursor(dictionary=True)
            conn.autocommit = False

            cursor.execute("SELECT status FROM Versements WHERE id = %s", (versement_id,))
            versement = cursor.fetchone()
            if not versement:
                return False, "Dossier introuvable."

            current_status = versement.get('status')
            if current_status == target_status:
                return False, "Le dossier est deja dans ce statut."

            conn.rollback()
            cursor.close()
            conn.close()
            conn = cursor = None

            if current_status == 'EN_COURS' and target_status == 'CLOTURE':
                return (True, "Succes") if self.cloture_versement(versement_id, journee_id) else (False, "Impossible de cloturer le dossier.")
            if current_status == 'EN_COURS' and target_status == 'ANNULE':
                return (True, "Succes") if self.cancel_versement(versement_id) else (False, "Impossible d'annuler le dossier.")
            if target_status == 'EN_COURS':
                return self._reopen_versement(versement_id, current_status)

            return False, "Transition de statut non autorisee."
        except Exception as e:
            if conn: conn.rollback()
            logging.error(f"Erreur change_versement_status: {e}")
            return False, str(e)
        finally:
            if cursor: cursor.close()
            if conn: conn.close()

    def _reopen_versement(self, versement_id: int, current_status: str) -> tuple[bool, str]:
        conn = None
        cursor = None
        try:
            conn = self.db.get_raw_connection()
            cursor = conn.cursor(dictionary=True)
            conn.autocommit = False

            receipt_number = f"VRS-{versement_id:05d}"
            closure_inventory_ids = []

            if current_status == 'CLOTURE':
                cursor.execute("SELECT id FROM Sales WHERE receipt_number = %s", (receipt_number,))
                sale = cursor.fetchone()
                if sale:
                    cursor.execute("SELECT inventory_id FROM SaleItems WHERE sale_id = %s AND inventory_id IS NOT NULL", (sale['id'],))
                    closure_inventory_ids = [row['inventory_id'] for row in cursor.fetchall()]
                    cursor.execute("DELETE FROM Sales WHERE id = %s", (sale['id'],))

                if closure_inventory_ids:
                    placeholders = ", ".join(["%s"] * len(closure_inventory_ids))
                    cursor.execute(f"""
                        UPDATE Versement_Items
                        SET item_status = 'EN_COURS'
                        WHERE versement_id = %s AND inventory_id IN ({placeholders}) AND item_status = 'RETIRE'
                    """, tuple([versement_id] + closure_inventory_ids))
                    cursor.execute(f"""
                        UPDATE Inventory
                        SET status = 'Reserved', remaining_weight = weight, remaining_quantity = quantity
                        WHERE id IN ({placeholders})
                    """, tuple(closure_inventory_ids))

            elif current_status == 'ANNULE':
                cursor.execute("""
                    SELECT vi.id, vi.inventory_id, i.status as inventory_status
                    FROM Versement_Items vi
                    LEFT JOIN Inventory i ON vi.inventory_id = i.id
                    WHERE vi.versement_id = %s AND vi.item_status = 'ANNULE'
                """, (versement_id,))
                items = cursor.fetchall()
                blocked = [
                    str(row['inventory_id']) for row in items
                    if row.get('inventory_id') and row.get('inventory_status') not in (None, 'Available')
                ]
                if blocked:
                    conn.rollback()
                    return False, "Impossible de remettre en cours: des articles ne sont plus disponibles."

                cursor.execute("""
                    UPDATE Inventory
                    SET status = 'Reserved'
                    WHERE id IN (
                        SELECT inventory_id FROM Versement_Items
                        WHERE versement_id = %s AND item_status = 'ANNULE' AND inventory_id IS NOT NULL
                    )
                """, (versement_id,))
                cursor.execute("UPDATE Versement_Items SET item_status = 'EN_COURS' WHERE versement_id = %s AND item_status = 'ANNULE'", (versement_id,))

            else:
                conn.rollback()
                return False, "Seuls les dossiers clotures ou annules peuvent etre remis en cours."

            cursor.execute("UPDATE Versements SET status = 'EN_COURS' WHERE id = %s", (versement_id,))
            conn.commit()
            return True, "Succes"
        except Exception as e:
            if conn: conn.rollback()
            logging.error(f"Erreur reopen_versement: {e}")
            return False, str(e)
        finally:
            if cursor: cursor.close()
            if conn: conn.close()

    # ============================================================
    # 5. جلب البيانات بحسابات دقيقة
    # ============================================================
    def get_versements(self, status_filter: str = 'EN_COURS', client_id: int = None) -> list:
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                
                query = """
                    SELECT v.*, c.name as client_name, c.phone 
                    FROM Versements v
                    LEFT JOIN Clients c ON v.client_id = c.id
                    WHERE 1=1
                """
                params = []
                if status_filter:
                    query += " AND v.status = %s"
                    params.append(status_filter)
                if client_id:
                    query += " AND v.client_id = %s"
                    params.append(client_id)
                    
                query += " ORDER BY v.created_at DESC"
                cursor.execute(query, tuple(params))
                versements = cursor.fetchall()

                for v in versements:
                    v_id = v['id']
                    
                    # جلب القطع مع حالتها وسعرها التقديري
                    cursor.execute("""
                        SELECT vi.id as item_id, vi.inventory_id, vi.designation, vi.item_status, i.weight, i.barcode, i.selling_price 
                        FROM Versement_Items vi
                        LEFT JOIN Inventory i ON vi.inventory_id = i.id
                        WHERE vi.versement_id = %s
                    """, (v_id,))
                    items = cursor.fetchall()
                    v['items'] = items
                    
                    total_active_weight = sum(float(i['weight'] or 0) for i in items if i['item_status'] != 'ANNULE')
                    total_estimated_price = sum(float(i['selling_price'] or 0) for i in items if i['item_status'] != 'ANNULE')
                    
                    cursor.execute("""
                        SELECT p.*, vi.designation as item_designation 
                        FROM Versement_Payments p
                        LEFT JOIN Versement_Items vi ON p.versement_item_id = vi.id
                        WHERE p.versement_id = %s ORDER BY p.payment_date ASC
                    """, (v_id,))
                    payments = cursor.fetchall()
                    v['payments'] = payments
                    
                    total_paid_money = 0.0
                    total_deducted_weight = 0.0
                    total_remise = 0.0
                    total_tpe = 0.0
                    total_dollar = 0.0
                    
                    for p in payments:
                        money_da = float(p['montant_da'] or 0)
                        money_tpe = float(p.get('tpe_da') or 0)
                        money_eu = float(p['montant_euro'] or 0)
                        taux = float(p['taux_change_euro'] or 0)
                        money_dl = float(p.get('montant_dollar') or 0)
                        taux_dl = float(p.get('taux_change_dollar') or 0)
                        remise = float(p.get('remise_da') or 0)
                        oc = float(p['or_casse_g'] or 0)
                        p_deduit = float(p['poids_deduit_g'] or 0)
                        
                        total_paid_money += money_da + money_tpe
                        total_tpe += money_tpe
                        total_deducted_weight += p_deduit
                        total_remise += remise
                        total_dollar += money_dl
                            
                    v['total_weight_g'] = total_active_weight
                    v['total_estimated_price_da'] = total_estimated_price
                    v['total_paid_money_da'] = total_paid_money
                    v['total_tpe_da'] = total_tpe
                    v['total_paid_weight_g'] = total_deducted_weight
                    v['total_remise_da'] = total_remise
                    v['total_dollar'] = total_dollar
                    
                    # الباقي = الوزن الفعال المتبقي ناقص ما تم خصمه
                    v['reste_poids_g'] = max(0.0, total_active_weight - total_deducted_weight)

                return versements
        except Exception as e:
            logging.error(f"Erreur get_versements: {e}")
            return []

    def update_payment(self, payment_id: int, montant_da: float, montant_euro: float, 
                       taux_change_euro: float, or_casse_g: float, poids_deduit_g: float, notes: str,
                       versement_item_id: int = None, montant_dollar: float = 0.0, 
                       taux_change_dollar: float = 0.0, remise_da: float = 0.0,
                       tpe_da: float = 0.0) -> bool:
        """تحديث بيانات دفعة مالية تم إدخالها بالخطأ أو إعادة توجيهها لمنتج محدد"""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE Versement_Payments 
                    SET montant_da = %s, tpe_da = %s, montant_euro = %s, taux_change_euro = %s,
                        montant_dollar = %s, taux_change_dollar = %s, remise_da = %s,
                        or_casse_g = %s, poids_deduit_g = %s, notes = %s, versement_item_id = %s
                    WHERE id = %s
                """, (montant_da, tpe_da, montant_euro, taux_change_euro, montant_dollar, taux_change_dollar, remise_da, or_casse_g, poids_deduit_g, notes, versement_item_id, payment_id))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Erreur update_payment: {e}")
            return False

    def add_item_to_versement(self, versement_id: int, inventory_id: int, designation: str) -> bool:
        """إضافة قطعة جديدة من المخزون إلى ملف عربون مفتوح مسبقاً"""
        conn = None
        cursor = None
        try:
            conn = self.db.get_raw_connection()
            cursor = conn.cursor()
            conn.autocommit = False

            # 1. إضافة القطعة لجدول منتجات العربون
            cursor.execute("""
                INSERT INTO Versement_Items (versement_id, inventory_id, designation, item_status)
                VALUES (%s, %s, %s, 'EN_COURS')
            """, (versement_id, inventory_id, designation))
            
            # 2. تغيير حالة القطعة في المخزون إلى "محجوزة"
            if inventory_id:
                cursor.execute("UPDATE Inventory SET status = 'Reserved' WHERE id = %s", (inventory_id,))
                
            # 3. تحويل نوع الملف من فارغ إلى منتجات (إذا كان فارغاً)
            cursor.execute("UPDATE Versements SET type_versement = 'PRODUITS' WHERE id = %s", (versement_id,))

            conn.commit()
            return True
        except Exception as e:
            if conn: conn.rollback()
            logging.error(f"Erreur add_item_to_versement: {e}")
            return False
        finally:
            if cursor: cursor.close()
            if conn: conn.close()

    def revert_versement_item_status(self, item_id: int) -> tuple[bool, str]:
        """إرجاع حالة القطعة إلى EN_COURS من حالة RETIRE أو ANNULE (تراجع عن الخطأ)"""
        conn = None
        cursor = None
        try:
            conn = self.db.get_raw_connection()
            cursor = conn.cursor(dictionary=True)
            conn.autocommit = False

            cursor.execute("SELECT versement_id, inventory_id, item_status FROM Versement_Items WHERE id = %s", (item_id,))
            item = cursor.fetchone()
            if not item: return False, "Article introuvable."
                
            versement_id = item['versement_id']
            inv_id = item['inventory_id']
            current_status = item['item_status']
            
            if current_status == 'EN_COURS': return False, "L'article est déjà en cours."

            # التراجع عن الإلغاء
            if current_status == 'ANNULE' and inv_id:
                cursor.execute("SELECT status FROM Inventory WHERE id = %s", (inv_id,))
                inv = cursor.fetchone()
                if inv and inv['status'] != 'Available':
                    return False, "Impossible de restaurer : l'article a déjà été vendu ou réservé ailleurs."
                cursor.execute("UPDATE Inventory SET status = 'Reserved' WHERE id = %s", (inv_id,))

            # التراجع عن التسليم
            elif current_status == 'RETIRE' and inv_id:
                cursor.execute("SELECT weight, quantity FROM Inventory WHERE id = %s", (inv_id,))
                inv = cursor.fetchone()
                if inv:
                    cursor.execute("""
                        UPDATE Inventory 
                        SET status = 'Reserved', remaining_weight = %s, remaining_quantity = %s
                        WHERE id = %s
                    """, (inv['weight'], inv['quantity'], inv_id))
                cursor.execute("""
                    UPDATE Sales s
                    JOIN SaleItems si ON si.sale_id = s.id
                    SET s.status = 'CANCELLED'
                    WHERE si.inventory_id = %s
                      AND s.status = 'COMPLETED'
                      AND s.notes LIKE %s
                """, (inv_id, f"%VRS-{versement_id:05d}%"))

            cursor.execute("UPDATE Versement_Items SET item_status = 'EN_COURS' WHERE id = %s", (item_id,))
            
            # إعادة فتح الملف إذا كان مغلقاً أو ملغى
            cursor.execute("""
                UPDATE Versements 
                SET status = 'EN_COURS' 
                WHERE id = (SELECT versement_id FROM Versement_Items WHERE id = %s)
            """, (item_id,))

            conn.commit()
            return True, "Succès"
        except Exception as e:
            if conn: conn.rollback()
            logging.error(f"Erreur revert_versement_item_status: {e}")
            return False, str(e)
        finally:
            if cursor: cursor.close()
            if conn: conn.close()

    def delete_versement_item(self, item_id: int) -> tuple[bool, str]:
        """حذف القطعة تماماً من الملف (في حال إضافتها بالخطأ تماماً)"""
        conn = None
        cursor = None
        try:
            conn = self.db.get_raw_connection()
            cursor = conn.cursor(dictionary=True)
            conn.autocommit = False

            cursor.execute("SELECT inventory_id FROM Versement_Items WHERE id = %s", (item_id,))
            item = cursor.fetchone()
            if not item: return False, "Article introuvable."
            
            cursor.execute("SELECT id FROM Versement_Payments WHERE versement_item_id = %s", (item_id,))
            if cursor.fetchone():
                return False, "Impossible : il y a des paiements liés spécifiquement à cet article."

            if item['inventory_id']:
                cursor.execute("UPDATE Inventory SET status = 'Available' WHERE id = %s", (item['inventory_id'],))
                
            cursor.execute("DELETE FROM Versement_Items WHERE id = %s", (item_id,))
            conn.commit()
            return True, "Succès"
        except Exception as e:
            if conn: conn.rollback()
            logging.error(f"Erreur delete_versement_item: {e}")
            return False, str(e)
        finally:
            if cursor: cursor.close()
            if conn: conn.close()
