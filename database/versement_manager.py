import logging
from datetime import datetime

from database.versement_reservation import (
    derived_inventory_status,
    normalize_reserved_quantity,
)

MAX_CUSTOM_NOTE_LENGTH = 255


class VersementManager:
    """
    مدير عمليات العربون (Versements):
    يدير الإيداعات الحرة (A Vide) وحجوزات القطع (Produits) مع تتبع الوزن المتبقي وتحديث المخزون آلياً.
    """
    def __init__(self, db_instance):
        self.db = db_instance

    # ============================================================
    def _lock_inventory_for_reservation(self, cursor, inventory_id, requested_quantity=1):
        cursor.execute("""
            SELECT id, item_type, weight, remaining_weight, quantity, remaining_quantity,
                   status, reserved_for_client_id
            FROM Inventory WHERE id = %s FOR UPDATE
        """, (inventory_id,))
        inventory = cursor.fetchone()
        if not inventory:
            raise ValueError("L'article d'inventaire est introuvable.")

        item_type = str(inventory.get("item_type") or "WEIGHT").upper()
        requested = normalize_reserved_quantity(item_type, requested_quantity)
        cursor.execute("""
            SELECT COALESCE(SUM(COALESCE(reserved_quantity, 1)), 0) AS reserved_quantity,
                   COUNT(*) AS reservation_count
            FROM Versement_Items
            WHERE inventory_id = %s AND item_status = 'EN_COURS'
        """, (inventory_id,))
        active = cursor.fetchone() or {}
        reserved = int(active.get("reserved_quantity") or 0)
        reservation_count = int(active.get("reservation_count") or 0)
        status = inventory.get("status")
        reserved_client_id = inventory.get("reserved_for_client_id")

        if reserved_client_id:
            raise ValueError("L'article est rÃ©servÃ© Ã  un client et ne peut pas Ãªtre ajoutÃ© Ã  un autre versement.")

        if item_type == "PIECE":
            remaining = int(inventory.get("remaining_quantity") or 0)
            available = max(0, remaining - reserved)
            legacy_reserved = status == "Reserved" and not reserved_client_id
            if status not in ("Available", "Partially_Sold") and not legacy_reserved:
                raise ValueError("L'article n'est pas disponible pour un versement.")
            if requested > available:
                raise ValueError(f"QuantitÃ© demandÃ©e ({requested}) supÃ©rieure Ã  la quantitÃ© disponible ({available}).")
        else:
            remaining_weight = float(inventory.get("remaining_weight") or 0.0)
            legacy_reserved = status == "Reserved" and not reserved_client_id and reservation_count == 0
            if (status not in ("Available", "Partially_Sold") and not legacy_reserved) or reservation_count > 0 or remaining_weight <= 0:
                raise ValueError("L'article pondÃ©rÃ© est dÃ©jÃ  rÃ©servÃ© ou indisponible.")

        return inventory, requested

    def _sync_inventory_status(self, cursor, inventory_id):
        if not inventory_id:
            return
        cursor.execute("""
            SELECT id, item_type, weight, remaining_weight, quantity, remaining_quantity,
                   status, reserved_for_client_id
            FROM Inventory WHERE id = %s FOR UPDATE
        """, (inventory_id,))
        inventory = cursor.fetchone()
        if not inventory:
            return
        if inventory.get("status") in ("Scrap", "Repair", "Lost"):
            return
        if inventory.get("status") == "Reserved" and inventory.get("reserved_for_client_id"):
            return
        status = derived_inventory_status(
            inventory.get("item_type"), inventory.get("remaining_weight"), inventory.get("weight"),
            inventory.get("remaining_quantity"), inventory.get("quantity"),
        )
        cursor.execute("UPDATE Inventory SET status = %s WHERE id = %s", (status, inventory_id))

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
                    item_notes = str(item.get('custom_note') or item.get('notes') or '').strip()[:MAX_CUSTOM_NOTE_LENGTH]
                    
                    requested_quantity = item.get("reserved_quantity", item.get("versement_quantity", 1))
                    if inv_id:
                        _, requested_quantity = self._lock_inventory_for_reservation(
                            cursor, inv_id, requested_quantity
                        )
                    else:
                        requested_quantity = normalize_reserved_quantity(item.get("item_type"), requested_quantity)

                    cursor.execute("""
                        INSERT INTO Versement_Items
                            (versement_id, inventory_id, designation, notes, item_status, reserved_quantity)
                        VALUES (%s, %s, %s, %s, 'EN_COURS', %s)
                    """, (versement_id, inv_id, designation, item_notes, requested_quantity))

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

    def update_payment_notes(self, payment_id: int, notes: str) -> bool:
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE Versement_Payments SET notes = %s WHERE id = %s", (str(notes or '').strip(), payment_id))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Erreur update_payment_notes: {e}")
            return False

    # ============================================================
    # 3. إدارة القطع المنفصلة (الإلغاء والسحب)
    # ============================================================
    def cancel_versement_item(self, item_id: int) -> bool:
        """إلغاء قطعة معينة من العربون وإرجاعها للواجهة (المخزون)"""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                
                cursor.execute("SELECT inventory_id FROM Versement_Items WHERE id = %s", (item_id,))
                item = cursor.fetchone()
                cursor.execute(
                    "UPDATE Versement_Items SET item_status = 'ANNULE' "
                    "WHERE id = %s AND item_status = 'EN_COURS'",
                    (item_id,),
                )
                if item:
                    self._sync_inventory_status(cursor, item.get("inventory_id"))

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
                
                # SalesManager dÃ©duira le stock aprÃ¨s la crÃ©ation de la facture.
                # Ne pas mettre toute la ligne Ã  Sold ici : une piÃ¨ce peut Ãªtre partiellement livrÃ©e.
                cursor.execute(
                    "UPDATE Versement_Items SET item_status = 'RETIRE' "
                    "WHERE id = %s AND item_status = 'EN_COURS'",
                    (item_id,),
                )

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
                SELECT vi.inventory_id, vi.designation, vi.notes AS custom_note,
                       vi.reserved_quantity, i.item_type, i.weight, i.remaining_weight,
                       i.quantity, i.remaining_quantity, i.selling_price, i.barcode
                FROM Versement_Items vi
                LEFT JOIN Inventory i ON vi.inventory_id = i.id
                WHERE vi.versement_id = %s AND vi.item_status = 'EN_COURS'
                FOR UPDATE
            """, (versement_id,))
            items_to_retire = cursor.fetchall()


            from database.versement_invoice_summary import build_versement_payment_summary
            cursor.execute("""
                SELECT p.*, vi.designation AS item_designation
                FROM Versement_Payments p
                LEFT JOIN Versement_Items vi ON vi.id = p.versement_item_id
                WHERE p.versement_id = %s
                ORDER BY p.payment_date ASC, p.id ASC
            """, (versement_id,))
            payment_summary = build_versement_payment_summary(cursor.fetchall())
            cursor.execute("UPDATE Versements SET status = 'CLOTURE' WHERE id = %s", (versement_id,))
            cursor.execute(
                "UPDATE Versement_Items SET item_status = 'RETIRE' "
                "WHERE versement_id = %s AND item_status = 'EN_COURS'",
                (versement_id,),
            )

            for it in items_to_retire:
                inv_id = it.get("inventory_id")
                if not inv_id:
                    continue
                item_type = str(it.get("item_type") or "WEIGHT").upper()
                if item_type == "PIECE":
                    sold_quantity = max(1, int(it.get("reserved_quantity") or 1))
                    cursor.execute("""
                        UPDATE Inventory
                        SET status = IF(remaining_quantity - %s <= 0, 'Sold',
                                    IF(remaining_quantity - %s < quantity, 'Partially_Sold', 'Available')),
                            remaining_quantity = GREATEST(0, COALESCE(remaining_quantity, quantity) - %s)
                        WHERE id = %s
                    """, (sold_quantity, sold_quantity, sold_quantity, inv_id))
                else:
                    sold_weight = float(it.get("remaining_weight") or it.get("weight") or 0.0)
                    cursor.execute("""
                        UPDATE Inventory
                        SET status = IF(remaining_weight - %s <= 0.005, 'Sold', 'Partially_Sold'),
                            remaining_weight = GREATEST(0, COALESCE(remaining_weight, weight) - %s)
                        WHERE id = %s
                    """, (sold_weight, sold_weight, inv_id))

            if items_to_retire:
                cursor.execute("""
                    INSERT INTO Sales (receipt_number, journee_id, client_id, user_id, total_amount_da, discount_da, net_to_pay_da, cash_paid_da, tpe_paid_da, old_gold_weight_g, impos_weight_g, status, notes, created_at)
                    VALUES (%s, %s, %s, 1, %s, %s, %s, %s, %s, %s, %s, 'COMPLETED', %s, NOW())
                """, (
                    f"VRS-{versement_id:05d}",
                    journee_id,
                    client_id,
                    payment_summary["total_brut_da"],
                    payment_summary["total_remise_da"],
                    payment_summary["net_to_pay_da"],
                    payment_summary["cash_paid_da"],
                    payment_summary["tpe_paid_da"],
                    payment_summary["old_gold_weight_g"],
                    payment_summary["deducted_weight_g"],
                    f"Clôture Versement N° VRS-{versement_id:05d}",
                ))
                sale_id = cursor.lastrowid

                for it in items_to_retire:
                    item_type = str(it.get("item_type") or "WEIGHT").upper()
                    quantity = max(1, int(it.get("reserved_quantity") or 1)) if item_type == "PIECE" else 1
                    sold_weight = (
                        float(it.get("remaining_weight") or it.get("weight") or 0.0)
                        if item_type == "WEIGHT" else 0.0
                    )
                    barcode = str(it.get("barcode") or "")
                    desig = str(it.get("designation") or "Article Versement")
                    item_note = str(it.get("custom_note") or "").strip()[:MAX_CUSTOM_NOTE_LENGTH]
                    unit_price = float(it.get("selling_price") or 0.0)
                    total_price = unit_price * quantity if item_type == "PIECE" else unit_price

                    if "item_type" not in it:
                        cursor.execute("""
                            INSERT INTO SaleItems
                                (sale_id, inventory_id, barcode, name, item_type,
                                 sold_weight_g, sold_quantity, unit_price_da, total_price_da, custom_note)
                            VALUES (%s, %s, %s, %s, 'WEIGHT', %s, 1, 0, 0, %s)
                        """, (sale_id, it.get("inventory_id"), barcode, desig, sold_weight, item_note))
                    else:
                        cursor.execute("""
                            INSERT INTO SaleItems
                                (sale_id, inventory_id, barcode, name, item_type,
                                 sold_weight_g, sold_quantity, unit_price_da, total_price_da, custom_note)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (
                            sale_id, it.get("inventory_id"), barcode, desig, item_type,
                            sold_weight, quantity, unit_price, total_price, item_note,
                        ))

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
            cursor = conn.cursor(dictionary=True)
            conn.autocommit = False

            cursor.execute("UPDATE Versements SET status = 'ANNULE' WHERE id = %s", (versement_id,))
            cursor.execute(
                "UPDATE Versement_Items SET item_status = 'ANNULE' "
                "WHERE versement_id = %s AND item_status != 'RETIRE'",
                (versement_id,),
            )
            cursor.execute(
                "SELECT DISTINCT inventory_id FROM Versement_Items "
                "WHERE versement_id = %s AND item_status = 'ANNULE' AND inventory_id IS NOT NULL",
                (versement_id,),
            )
            for row in cursor.fetchall():
                self._sync_inventory_status(cursor, row.get("inventory_id"))

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
                sale_items = []
                if sale:
                    cursor.execute("""
                        SELECT inventory_id, item_type, sold_weight_g, sold_quantity
                        FROM SaleItems WHERE sale_id = %s AND inventory_id IS NOT NULL
                    """, (sale["id"],))
                    sale_items = cursor.fetchall()
                    for sale_item in sale_items:
                        inv_id = sale_item.get("inventory_id")
                        if str(sale_item.get("item_type") or "WEIGHT").upper() == "PIECE":
                            cursor.execute(
                                "UPDATE Inventory SET remaining_quantity = COALESCE(remaining_quantity, 0) + %s WHERE id = %s",
                                (int(sale_item.get("sold_quantity") or 1), inv_id),
                            )
                        else:
                            cursor.execute(
                                "UPDATE Inventory SET remaining_weight = COALESCE(remaining_weight, 0) + %s WHERE id = %s",
                                (float(sale_item.get("sold_weight_g") or 0), inv_id),
                            )
                    cursor.execute("DELETE FROM Sales WHERE id = %s", (sale["id"],))

                cursor.execute(
                    "UPDATE Versement_Items SET item_status = 'EN_COURS' "
                    "WHERE versement_id = %s AND item_status = 'RETIRE'",
                    (versement_id,),
                )
                for sale_item in sale_items:
                    self._sync_inventory_status(cursor, sale_item.get("inventory_id"))

            elif current_status == 'ANNULE':
                cursor.execute("""
                    SELECT vi.id, vi.inventory_id, vi.reserved_quantity
                    FROM Versement_Items vi
                    WHERE vi.versement_id = %s AND vi.item_status = 'ANNULE'
                """, (versement_id,))
                items = cursor.fetchall()
                for row in items:
                    if row.get("inventory_id"):
                        self._lock_inventory_for_reservation(
                            cursor, row["inventory_id"], row.get("reserved_quantity", 1)
                        )
                cursor.execute(
                    "UPDATE Versement_Items SET item_status = 'EN_COURS' "
                    "WHERE versement_id = %s AND item_status = 'ANNULE'",
                    (versement_id,),
                )
                for row in items:
                    self._sync_inventory_status(cursor, row.get("inventory_id"))

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
                        SELECT vi.id as item_id, vi.inventory_id, vi.designation, vi.notes AS custom_note,
                               vi.item_status, COALESCE(vi.reserved_quantity, 1) AS reserved_quantity,
                               i.item_type, i.weight, i.quantity, i.remaining_quantity, i.barcode, i.selling_price
                        FROM Versement_Items vi
                        LEFT JOIN Inventory i ON vi.inventory_id = i.id
                        WHERE vi.versement_id = %s
                    """, (v_id,))
                    items = cursor.fetchall()
                    v['items'] = items
                    
                    for item in items:
                        item_type = str(item.get('item_type') or 'WEIGHT').upper()
                        reserved_quantity = (
                            max(1, int(item.get('reserved_quantity') or 1))
                            if item_type == 'PIECE' else 1
                        )
                        item['reserved_quantity'] = reserved_quantity
                        item['display_weight'] = (
                            float(item.get('weight') or 0) * reserved_quantity
                            if item_type == 'PIECE' else float(item.get('weight') or 0)
                        )
                        item['display_price'] = (
                            float(item.get('selling_price') or 0) * reserved_quantity
                            if item_type == 'PIECE' else float(item.get('selling_price') or 0)
                        )
                    total_active_weight = sum(
                        float(i.get('display_weight') or 0) for i in items
                        if i['item_status'] != 'ANNULE'
                    )
                    total_estimated_price = sum(
                        float(i.get('display_price') or 0) for i in items
                        if i['item_status'] != 'ANNULE'
                    )
                    
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

    def update_versement_item_notes(self, item_id: int, notes: str) -> bool:
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                custom_note = str(notes or '').strip()[:MAX_CUSTOM_NOTE_LENGTH]
                cursor.execute("UPDATE Versement_Items SET notes = %s WHERE id = %s", (custom_note, item_id))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Erreur update_versement_item_notes: {e}")
            return False

    def add_item_to_versement(self, versement_id: int, inventory_id: int, designation: str, notes: str = '', reserved_quantity: int = 1) -> bool:
        """إضافة قطعة جديدة من المخزون إلى ملف عربون مفتوح مسبقاً"""
        conn = None
        cursor = None
        try:
            conn = self.db.get_raw_connection()
            cursor = conn.cursor()
            conn.autocommit = False

            # 1. Ø§Ù„ØªØ­Ù‚Ù‚ Ø§Ù„Ø°Ø±ÙŠ Ù…Ù† Ø§Ù„ÙƒÙ…ÙŠØ© Ø§Ù„Ù…ØªØ¨Ù‚ÙŠØ© ÙˆØ­Ø¬ÙˆØ²Ø§Øª Ø§Ù„Ø¹Ø±Ø¨ÙˆÙ† Ø§Ù„Ø£Ø®Ø±Ù‰.
            if inventory_id:
                _, reserved_quantity = self._lock_inventory_for_reservation(
                    cursor, inventory_id, reserved_quantity
                )
            else:
                reserved_quantity = normalize_reserved_quantity(None, reserved_quantity)
            cursor.execute("""
                INSERT INTO Versement_Items
                    (versement_id, inventory_id, designation, notes, item_status, reserved_quantity)
                VALUES (%s, %s, %s, %s, 'EN_COURS', %s)
            """, (
                versement_id, inventory_id, designation,
                str(notes or '').strip()[:MAX_CUSTOM_NOTE_LENGTH], reserved_quantity,
            ))

            # 2. Ù„Ø§ Ù†ØºÙŠØ± Inventory.statusØ› Ø­Ø§Ù„Ø© Ø§Ù„Ø¹Ù†ØµØ± Ø¯Ø§Ø®Ù„ Ø§Ù„Ø¹Ø±Ø¨ÙˆÙ† Ù‡ÙŠ Ù…ØµØ¯Ø± Ø§Ù„Ø­Ø¬Ø².
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
        """Remettre un article ANNULE ou RETIRE en EN_COURS sans restaurer tout le stock."""
        conn = None
        cursor = None
        try:
            conn = self.db.get_raw_connection()
            cursor = conn.cursor(dictionary=True)
            conn.autocommit = False

            cursor.execute("""
                SELECT versement_id, inventory_id, item_status, reserved_quantity
                FROM Versement_Items WHERE id = %s
            """, (item_id,))
            item = cursor.fetchone()
            if not item:
                return False, "Article introuvable."

            current_status = item.get("item_status")
            if current_status == "EN_COURS":
                return False, "L'article est dÃ©jÃ  en cours."

            inv_id = item.get("inventory_id")
            if current_status == "ANNULE" and inv_id:
                self._lock_inventory_for_reservation(
                    cursor, inv_id, item.get("reserved_quantity", 1)
                )

            if current_status == "RETIRE" and inv_id:
                cursor.execute("""
                    SELECT s.id, si.item_type, si.sold_weight_g, si.sold_quantity
                    FROM Sales s
                    JOIN SaleItems si ON si.sale_id = s.id
                    WHERE si.inventory_id = %s AND s.status = 'COMPLETED'
                      AND s.notes LIKE %s
                """, (inv_id, f"%VRS-{int(item.get('versement_id') or 0):05d}%"))
                delivered_sales = cursor.fetchall()
                for sale in delivered_sales:
                    if str(sale.get("item_type") or "WEIGHT").upper() == "PIECE":
                        cursor.execute(
                            "UPDATE Inventory SET remaining_quantity = COALESCE(remaining_quantity, 0) + %s WHERE id = %s",
                            (int(sale.get("sold_quantity") or 1), inv_id),
                        )
                    else:
                        cursor.execute(
                            "UPDATE Inventory SET remaining_weight = COALESCE(remaining_weight, 0) + %s WHERE id = %s",
                            (float(sale.get("sold_weight_g") or 0), inv_id),
                        )
                    cursor.execute("UPDATE Sales SET status = 'CANCELLED' WHERE id = %s", (sale["id"],))

            cursor.execute("UPDATE Versement_Items SET item_status = 'EN_COURS' WHERE id = %s", (item_id,))
            self._sync_inventory_status(cursor, inv_id)
            cursor.execute(
                "UPDATE Versements SET status = 'EN_COURS' "
                "WHERE id = (SELECT versement_id FROM Versement_Items WHERE id = %s)",
                (item_id,),
            )

            conn.commit()
            return True, "SuccÃ¨s"
        except Exception as e:
            if conn:
                conn.rollback()
            logging.error(f"Erreur revert_versement_item_status: {e}")
            return False, str(e)
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def delete_versement_item(self, item_id: int) -> tuple[bool, str]:
        """حذف القطعة تماماً من الملف (في حال إضافتها بالخطأ تماماً)"""
        conn = None
        cursor = None
        try:
            conn = self.db.get_raw_connection()
            cursor = conn.cursor(dictionary=True)
            conn.autocommit = False

            cursor.execute(
                "SELECT inventory_id, item_status FROM Versement_Items WHERE id = %s",
                (item_id,),
            )
            item = cursor.fetchone()
            if not item:
                return False, "Article introuvable."

            cursor.execute("SELECT id FROM Versement_Payments WHERE versement_item_id = %s", (item_id,))
            if cursor.fetchone():
                return False, "Impossible : il y a des paiements liÃ©s spÃ©cifiquement Ã  cet article."

            if item.get("item_status") == "RETIRE":
                return False, "Impossible de supprimer un article dÃ©jÃ  livrÃ©."

            cursor.execute("DELETE FROM Versement_Items WHERE id = %s", (item_id,))
            self._sync_inventory_status(cursor, item.get("inventory_id"))
            conn.commit()
            return True, "Succès"
        except Exception as e:
            if conn: conn.rollback()
            logging.error(f"Erreur delete_versement_item: {e}")
            return False, str(e)
        finally:
            if cursor: cursor.close()
            if conn: conn.close()
