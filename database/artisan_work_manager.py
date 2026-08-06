# database/artisan_work_manager.py
import logging

class ArtisanWorkManager:
    def __init__(self, db_instance):
        self.db = db_instance

    # ========================== ARTISANS (الحرفيين) ==========================
    def add_artisan(self, name: str, notes: str = "", phone: str = "") -> dict:
        """إضافة حرفي جديد"""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                query = "INSERT INTO Artisans (name, phone, notes) VALUES (%s, %s, %s)"
                cursor.execute(query, (name, phone, notes))
                conn.commit()
                return {"success": True, "id": cursor.lastrowid}
        except Exception as e:
            logging.error(f"Erreur add_artisan: {e}")
            return {"success": False, "message": str(e)}

    def update_artisan(self, artisan_id: int, name: str, notes: str = "", phone: str = "") -> bool:
        """تعديل بيانات حرفي"""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                query = "UPDATE Artisans SET name=%s, phone=%s, notes=%s WHERE id=%s"
                cursor.execute(query, (name, phone, notes, artisan_id))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Erreur update_artisan: {e}")
            return False

    def delete_artisan(self, artisan_id: int) -> dict:
        """حذف حرفي وجميع أعماله المرتبطة به (يتم حذف الأعمال أولاً ثم الحرفي)"""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                
                # 🟢 حذف جميع الأعمال المرتبطة بالحرفي أولاً لتجنب مشكلة المفتاح الأجنبي (Foreign Key)
                cursor.execute("DELETE FROM ArtisanWorkOrders WHERE artisan_id = %s", (artisan_id,))
                
                # ثم حذف الحرفي نفسه
                cursor.execute("DELETE FROM Artisans WHERE id = %s", (artisan_id,))
                conn.commit()
                return {"success": True}
        except Exception as e:
            logging.error(f"Erreur delete_artisan: {e}")
            return {"success": False, "message": str(e)}

    def get_all_artisans(self) -> list:
        """جلب كل الحرفيين"""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute("SELECT id, name, phone, notes FROM Artisans ORDER BY name ASC")
                return cursor.fetchall()
        except Exception as e:
            logging.error(f"Erreur get_all_artisans: {e}")
            return []

    # ========================== WORK ORDERS (الأعمال المربوطة بالزبائن والورشة) ==========================
    def add_order(self, artisan_id, client_id, numero, date_remis, obj, poid, date_recue, date_sortie, 
                  prix, vente, diff, status='RECEPTION', poids_entre_g=None, poids_retour_g=None, 
                  observations="", cout_artisan_da=None, prix_vente_da=None):
        """إضافة عمل/استقبال ورشة جديد"""
        try:
            try: artisan_id = int(artisan_id) if artisan_id not in (None, "", "None", 0, "0") else None
            except (ValueError, TypeError): artisan_id = None
            
            try: client_id = int(client_id) if client_id not in (None, "", "None", 0, "0") else None
            except (ValueError, TypeError): client_id = None

            if not date_remis:
                from datetime import datetime
                date_remis = datetime.now().strftime("%Y-%m-%d")

            poids_entre_g = poids_entre_g or poid
            cout_artisan_da = cout_artisan_da or prix
            prix_vente_da = prix_vente_da or vente

            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                query = """
                    INSERT INTO ArtisanWorkOrders 
                    (artisan_id, client_id, numero, date_remis, obj, poid, poids_entre_g, poids_retour_g, 
                     date_recue, date_sortie, prix, vente, diff, status, observations, cout_artisan_da, prix_vente_da) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                cursor.execute(query, (
                    artisan_id, client_id, numero, date_remis, obj, poid, poids_entre_g, poids_retour_g,
                    date_recue, date_sortie, prix, vente, diff, status, observations, cout_artisan_da, prix_vente_da
                ))
                conn.commit()
                return {"success": True, "id": cursor.lastrowid}
        except Exception as e:
            logging.error(f"Erreur add_order: {e}")
            return {"success": False, "message": str(e)}

    def update_order(self, order_id, artisan_id, client_id, numero, date_remis, obj, poid, date_recue, date_sortie, 
                     prix, vente, diff, status='RECEPTION', poids_entre_g=None, poids_retour_g=None, 
                     observations="", cout_artisan_da=None, prix_vente_da=None):
        """تعديل عمل/طلب ورشة"""
        try:
            try: artisan_id = int(artisan_id) if artisan_id not in (None, "", "None", 0, "0") else None
            except (ValueError, TypeError): artisan_id = None
            
            try: client_id = int(client_id) if client_id not in (None, "", "None", 0, "0") else None
            except (ValueError, TypeError): client_id = None

            poids_entre_g = poids_entre_g or poid
            cout_artisan_da = cout_artisan_da or prix
            prix_vente_da = prix_vente_da or vente

            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                query = """
                    UPDATE ArtisanWorkOrders 
                    SET artisan_id=%s, client_id=%s, numero=%s, date_remis=%s, obj=%s, 
                        poid=%s, poids_entre_g=%s, poids_retour_g=%s, date_recue=%s, date_sortie=%s, 
                        prix=%s, vente=%s, diff=%s, status=%s, observations=%s, 
                        cout_artisan_da=%s, prix_vente_da=%s 
                    WHERE id=%s
                """
                cursor.execute(query, (
                    artisan_id, client_id, numero, date_remis, obj, poid, poids_entre_g, poids_retour_g,
                    date_recue, date_sortie, prix, vente, diff, status, observations,
                    cout_artisan_da, prix_vente_da, order_id
                ))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Erreur update_order: {e}")
            return False

    def update_order_status(self, order_id: int, new_status: str, poids_retour_g: str = None) -> bool:
        """تحديث حالة العنصر بسرعة في الورشة"""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                if poids_retour_g is not None:
                    query = "UPDATE ArtisanWorkOrders SET status = %s, poids_retour_g = %s WHERE id = %s"
                    cursor.execute(query, (new_status, str(poids_retour_g), order_id))
                else:
                    query = "UPDATE ArtisanWorkOrders SET status = %s WHERE id = %s"
                    cursor.execute(query, (new_status, order_id))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Erreur update_order_status: {e}")
            return False

    def delete_order(self, order_id):
        """حذف عمل محدد"""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM ArtisanWorkOrders WHERE id = %s", (order_id,))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logging.error(f"Erreur delete_order: {e}")
            return False

    def get_orders_by_artisan(self, artisan_id):
        """جلب أعمال حرفي محدد مع الهاتف باسم العميل"""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = """
                    SELECT awo.*, c.name as client_name, c.phone as client_phone, a.name as artisan_name
                    FROM ArtisanWorkOrders awo
                    LEFT JOIN Clients c ON awo.client_id = c.id
                    LEFT JOIN Artisans a ON awo.artisan_id = a.id
                    WHERE awo.artisan_id = %s ORDER BY awo.id DESC
                """
                cursor.execute(query, (artisan_id,))
                return cursor.fetchall()
        except Exception as e:
            logging.error(f"Erreur get_orders_by_artisan: {e}")
            return []

    def get_all_atelier_orders(self, status_filter=None, artisan_id=None, date_from=None, date_to=None) -> list:
        """جلب جميع عناصر الورشة مع إمكانية الفلترة بالحالة، الحرفي أو النطاق الزمني"""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = """
                    SELECT awo.*, c.name as client_name, c.phone as client_phone, a.name as artisan_name
                    FROM ArtisanWorkOrders awo
                    LEFT JOIN Clients c ON awo.client_id = c.id
                    LEFT JOIN Artisans a ON awo.artisan_id = a.id
                    WHERE 1=1
                """
                params = []
                if status_filter and status_filter != 'ALL':
                    query += " AND awo.status = %s"
                    params.append(status_filter)
                if artisan_id:
                    query += " AND awo.artisan_id = %s"
                    params.append(artisan_id)
                if date_from:
                    query += " AND (awo.date_remis >= %s OR awo.date_remis = '' OR awo.date_remis IS NULL)"
                    params.append(str(date_from))
                if date_to:
                    query += " AND (awo.date_remis <= %s OR awo.date_remis = '' OR awo.date_remis IS NULL)"
                    params.append(str(date_to))

                query += " ORDER BY awo.id DESC"
                cursor.execute(query, tuple(params))
                return cursor.fetchall()
        except Exception as e:
            logging.error(f"Erreur get_all_atelier_orders: {e}")
            return []

    # ========================== REGLEMENTS & COMPTES ARTISANS (DA, OR, ARGENT) ==========================
    def add_artisan_transaction(self, artisan_id, transaction_type, direction='DEBIT', 
                                amount_da=0.0, weight_gold_g=0.0, weight_silver_g=0.0, 
                                date_trans=None, observations="", order_id=None, metal_type_id=None):
        """إضافة عملية تسديد/رصيد للحرفي (دينار، ذهب، فضة حسب العيار)"""
        try:
            if not date_trans:
                from datetime import datetime
                date_trans = datetime.now().strftime("%Y-%m-%d")

            try: metal_type_id = int(metal_type_id) if metal_type_id not in (None, "", "None", 0, "0") else None
            except (ValueError, TypeError): metal_type_id = None

            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                query = """
                    INSERT INTO ArtisanTransactions
                    (artisan_id, order_id, metal_type_id, transaction_type, direction, amount_da, weight_gold_g, weight_silver_g, date_trans, observations)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                cursor.execute(query, (
                    artisan_id, order_id, metal_type_id, transaction_type, direction,
                    float(amount_da or 0.0), float(weight_gold_g or 0.0), float(weight_silver_g or 0.0),
                    date_trans, observations
                ))
                conn.commit()
                return {"success": True, "id": cursor.lastrowid}
        except Exception as e:
            logging.error(f"Erreur add_artisan_transaction: {e}")
            return {"success": False, "message": str(e)}

    def get_artisan_balance(self, artisan_id):
        """حساب رصيد الحرفي الإجمالي وتفصيل الأرصدة حسب عيار المعدن (Titre / Carat)"""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)

                # 1. Sum transactions totals
                cursor.execute("""
                    SELECT 
                        SUM(CASE WHEN direction='CREDIT' THEN amount_da ELSE -amount_da END) as bal_da,
                        SUM(CASE WHEN direction='CREDIT' THEN weight_gold_g ELSE -weight_gold_g END) as bal_gold,
                        SUM(CASE WHEN direction='CREDIT' THEN weight_silver_g ELSE -weight_silver_g END) as bal_silver
                    FROM ArtisanTransactions WHERE artisan_id = %s
                """, (artisan_id,))
                trans_bal = cursor.fetchone() or {}

                # 2. Sum work orders cost/façon (Au crédit de l'artisan)
                cursor.execute("""
                    SELECT 
                        SUM(CAST(COALESCE(NULLIF(cout_artisan_da, ''), NULLIF(prix, ''), '0') AS DECIMAL(15,2))) as work_da
                    FROM ArtisanWorkOrders WHERE artisan_id = %s
                """, (artisan_id,))
                work_bal = cursor.fetchone() or {}

                total_da = float(trans_bal.get('bal_da') or 0.0) + float(work_bal.get('work_da') or 0.0)
                total_gold = float(trans_bal.get('bal_gold') or 0.0)
                total_silver = float(trans_bal.get('bal_silver') or 0.0)

                # 3. Sum itemized breakdown by MetalType / Karat
                cursor.execute("""
                    SELECT 
                        mt.id as metal_type_id,
                        mt.name as metal_name,
                        mt.purity_value,
                        mt.metal_category,
                        SUM(CASE WHEN at.direction='CREDIT' THEN (at.weight_gold_g + at.weight_silver_g) ELSE -(at.weight_gold_g + at.weight_silver_g) END) as bal_weight
                    FROM ArtisanTransactions at
                    JOIN MetalTypes mt ON at.metal_type_id = mt.id
                    WHERE at.artisan_id = %s
                    GROUP BY mt.id, mt.name, mt.purity_value, mt.metal_category
                """, (artisan_id,))
                breakdown = cursor.fetchall() or []

                total_equiv_24k = 0.0
                total_equiv_pure_silver = 0.0
                metal_list = []
                for b in breakdown:
                    w = float(b.get('bal_weight') or 0.0)
                    purity = float(b.get('purity_value') or 750.0)
                    cat = b.get('metal_category', 'GOLD')
                    equiv_pure = w * (purity / 1000.0)

                    if cat == 'GOLD':
                        total_equiv_24k += equiv_pure
                    else:
                        total_equiv_pure_silver += equiv_pure

                    metal_list.append({
                        "metal_type_id": b.get('metal_type_id'),
                        "metal_name": b.get('metal_name'),
                        "purity_value": purity,
                        "metal_category": cat,
                        "weight_g": w,
                        "equiv_pure_g": equiv_pure
                    })

                return {
                    "solde_da": total_da,
                    "solde_gold_g": total_gold,
                    "solde_silver_g": total_silver,
                    "total_equiv_24k": total_equiv_24k,
                    "total_equiv_pure_silver": total_equiv_pure_silver,
                    "metal_breakdown": metal_list
                }
        except Exception as e:
            logging.error(f"Erreur get_artisan_balance: {e}")
            return {
                "solde_da": 0.0, "solde_gold_g": 0.0, "solde_silver_g": 0.0,
                "total_equiv_24k": 0.0, "total_equiv_pure_silver": 0.0, "metal_breakdown": []
            }

    def get_artisan_ledger(self, artisan_id):
        """جلب كشف حساب تفصيلي وموحد للحرفي مع اسم العيار (أعمال ورشة + تسديدات وتوريد)"""
        try:
            ledger = []
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)

                # 1. Work orders
                cursor.execute("""
                    SELECT id, numero, date_remis as date_trans, obj, cout_artisan_da, prix, status
                    FROM ArtisanWorkOrders WHERE artisan_id = %s
                """, (artisan_id,))
                orders = cursor.fetchall()
                for o in orders:
                    cost = float(o.get('cout_artisan_da') or o.get('prix') or 0.0)
                    ledger.append({
                        "id": f"WO-{o['id']}",
                        "date_trans": o.get('date_trans') or "",
                        "type": "TRAVAIL_ATELIER",
                        "label": f"Travail N° {o.get('numero') or o['id']} ({o.get('obj') or ''})",
                        "direction": "CREDIT",
                        "amount_da": cost,
                        "weight_gold_g": 0.0,
                        "weight_silver_g": 0.0,
                        "metal_name": "",
                        "observations": f"Statut: {o.get('status')}"
                    })

                # 2. Transactions with MetalTypes
                cursor.execute("""
                    SELECT at.*, mt.name as metal_name, mt.purity_value 
                    FROM ArtisanTransactions at
                    LEFT JOIN MetalTypes mt ON at.metal_type_id = mt.id
                    WHERE at.artisan_id = %s
                """, (artisan_id,))
                trans = cursor.fetchall()
                for t in trans:
                    m_name = f" ({t.get('metal_name')})" if t.get('metal_name') else ""
                    t_label = "Règlement Espèces" if t['transaction_type'] == 'PAYMENT_DA' else \
                              f"Versement Or{m_name}" if t['transaction_type'] == 'SETTLEMENT_GOLD' else \
                              f"Versement Argent{m_name}" if t['transaction_type'] == 'SETTLEMENT_SILVER' else f"Ajustement{m_name}"
                    ledger.append({
                        "id": f"TR-{t['id']}",
                        "date_trans": t.get('date_trans') or "",
                        "type": t['transaction_type'],
                        "label": t_label,
                        "direction": t['direction'],
                        "amount_da": float(t.get('amount_da') or 0.0),
                        "weight_gold_g": float(t.get('weight_gold_g') or 0.0),
                        "weight_silver_g": float(t.get('weight_silver_g') or 0.0),
                        "metal_name": t.get('metal_name') or "",
                        "observations": t.get('observations') or ""
                    })

            # Sort by date
            ledger.sort(key=lambda x: x['date_trans'], reverse=True)
            return ledger
        except Exception as e:
            logging.error(f"Erreur get_artisan_ledger: {e}")
            return []

    def delete_artisan_transaction(self, trans_id):
        """حذف/إلغاء حركات التسديد"""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM ArtisanTransactions WHERE id = %s", (trans_id,))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logging.error(f"Erreur delete_artisan_transaction: {e}")
            return False