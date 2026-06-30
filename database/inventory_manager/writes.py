import logging
from typing import Optional

import mysql.connector


class InventoryWriteMixin:
    def _insert_item_in_transaction(
        self,
        cursor,
        name: str,
        metal_type_id: int = None,
        weight: float = None,
        quantity: int = 1,
        category_id: int = None,
        barcode: str = None,
        metal_cost_per_gram: float = 0.0,
        labor_cost_per_gram: float = 0.0,
        profit_margin: float = 0.0,
        margin_type: str = 'FIXED',
        total_cost: float = 0.0,
        selling_price: float = 0.0,
        item_type: str = 'WEIGHT',
        location_id: int = None,
        supplier_id: int = None,
        image_url: str = None,
    ) -> int:
        if item_type == 'WEIGHT':
            w = weight if weight else 0.0
            calculated_total_cost = (metal_cost_per_gram + labor_cost_per_gram) * w
            if margin_type == 'PERCENTAGE':
                profit_per_gram = (metal_cost_per_gram + labor_cost_per_gram) * (profit_margin / 100.0)
            else:
                profit_per_gram = profit_margin
            calculated_selling_price = calculated_total_cost + (profit_per_gram * w)
        else:
            calculated_total_cost = total_cost
            calculated_selling_price = selling_price

        cursor.execute(
            """
                INSERT INTO Inventory
                (barcode, name, category_id, metal_type_id, item_type, weight, remaining_weight, quantity, remaining_quantity,
                 metal_cost_per_gram, labor_cost_per_gram, total_cost, initial_cost, profit_margin, margin_type, selling_price,
                 location_id, supplier_id, image_url, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'Available')
            """,
            (
                barcode, name, category_id, metal_type_id, item_type, weight, weight, quantity, quantity,
                metal_cost_per_gram, labor_cost_per_gram, calculated_total_cost, calculated_total_cost,
                profit_margin, margin_type, calculated_selling_price, location_id, supplier_id, image_url,
            ),
        )
        return int(cursor.lastrowid)

    def add_item(self, name: str, metal_type_id: int = None, weight: float = None,
                 quantity: int = 1, category_id: int = None, barcode: str = None,
                 metal_cost_per_gram: float = 0.0, labor_cost_per_gram: float = 0.0, 
                 profit_margin: float = 0.0, margin_type: str = 'FIXED', total_cost: float = 0.0, selling_price: float = 0.0,
                 item_type: str = 'WEIGHT',
                 location_id: int = None, supplier_id: int = None, image_url: str = None) -> Optional[int]:
        """
        Ajoute une nouvelle pièce au stock avec calcul automatique et enregistrement du coût initial.
        """
        if item_type == 'WEIGHT':
            w = weight if weight else 0.0
            calculated_total_cost = (metal_cost_per_gram + labor_cost_per_gram) * w
            
            # 🟢 حساب الفائدة بناءً على نوعها (ثابت أو نسبة مئوية)
            if margin_type == 'PERCENTAGE':
                profit_per_gram = (metal_cost_per_gram + labor_cost_per_gram) * (profit_margin / 100.0)
            else:
                profit_per_gram = profit_margin
                
            calculated_selling_price = calculated_total_cost + (profit_per_gram * w)
        else:
            calculated_total_cost = total_cost
            calculated_selling_price = selling_price

        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                query = """
                    INSERT INTO Inventory 
                    (barcode, name, category_id, metal_type_id, item_type, weight, remaining_weight, quantity, remaining_quantity,
                     metal_cost_per_gram, labor_cost_per_gram, total_cost, initial_cost, profit_margin, margin_type, selling_price, 
                     location_id, supplier_id, image_url, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'Available')
                """
                params = (barcode, name, category_id, metal_type_id, item_type, weight, weight, quantity, quantity,
                          metal_cost_per_gram, labor_cost_per_gram, calculated_total_cost, calculated_total_cost, 
                          profit_margin, margin_type, calculated_selling_price, location_id, supplier_id, image_url)
                
                cursor.execute(query, params)
                conn.commit()
                
                new_id = cursor.lastrowid
                logging.info(f"Article '{name}' ajouté au stock avec succès (ID: {new_id}, Type: {item_type}, Qté: {quantity}).")
                return new_id

        except mysql.connector.Error as e:
            logging.error(f"Erreur lors de l'ajout de l'article '{name}': {e}")
            return None

    def update_item(self, item_id: int, name: str, metal_type_id: int = None, weight: float = None,
                    quantity: int = 1, category_id: int = None, barcode: str = None,
                    metal_cost_per_gram: float = 0.0, labor_cost_per_gram: float = 0.0, 
                    profit_margin: float = 0.0, margin_type: str = 'FIXED', total_cost: float = 0.0, selling_price: float = 0.0,
                    item_type: str = 'WEIGHT',
                    location_id: int = None, supplier_id: int = None, image_url: str = None) -> bool:
        """
        Met à jour les informations d'une pièce avec recalcul automatique.
        """
        if item_type == 'WEIGHT':
            w = weight if weight else 0.0
            calculated_total_cost = (metal_cost_per_gram + labor_cost_per_gram) * w
            
            # 🟢 حساب الفائدة بناءً على نوعها
            if margin_type == 'PERCENTAGE':
                profit_per_gram = (metal_cost_per_gram + labor_cost_per_gram) * (profit_margin / 100.0)
            else:
                profit_per_gram = profit_margin
                
            calculated_selling_price = calculated_total_cost + (profit_per_gram * w)
        else:
            calculated_total_cost = total_cost
            calculated_selling_price = selling_price

        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                query = """
                    UPDATE Inventory 
                    SET barcode = %s, name = %s, category_id = %s, metal_type_id = %s, item_type = %s,
                        weight = %s, quantity = %s, 
                        metal_cost_per_gram = %s, labor_cost_per_gram = %s, total_cost = %s, 
                        profit_margin = %s, margin_type = %s, selling_price = %s,
                        location_id = %s, supplier_id = %s, image_url = %s,
                        remaining_weight = IF(status = 'Available', %s, remaining_weight),
                        remaining_quantity = IF(status = 'Available', %s, remaining_quantity)
                    WHERE id = %s
                """
                params = (barcode, name, category_id, metal_type_id, item_type, weight, quantity,
                          metal_cost_per_gram, labor_cost_per_gram, calculated_total_cost, 
                          profit_margin, margin_type, calculated_selling_price,
                          location_id, supplier_id, image_url, 
                          weight, quantity, item_id)
                
                cursor.execute(query, params)
                conn.commit()
                
                logging.info(f"Article {item_id} mis à jour avec succès.")
                return True

        except mysql.connector.Error as e:
            logging.error(f"Erreur lors de la mise à jour de l'article {item_id}: {e}")
            return False

    def update_item_status(self, item_id: int, new_status: str) -> bool:
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE Inventory SET status = %s WHERE id = %s", (new_status, item_id))
                conn.commit()
                return True
        except mysql.connector.Error as e:
            logging.error(f"Erreur update status {item_id}: {e}")
            return False

    def update_remaining_stock(self, item_id: int, sold_weight: float = 0.0, sold_qty: int = 0) -> bool:
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT item_type, remaining_weight, remaining_quantity FROM Inventory WHERE id = %s", (item_id,))
                res = cursor.fetchone()
                if not res: return False

                item_type, rem_w, rem_q = res
                new_status = 'Partially_Sold'
                
                if item_type == 'WEIGHT':
                    new_rem_w = float(rem_w or 0.0) - sold_weight
                    if new_rem_w <= 0:
                        new_rem_w = 0
                        new_status = 'Sold'
                    cursor.execute("UPDATE Inventory SET remaining_weight = %s, status = %s WHERE id = %s", 
                                 (new_rem_w, new_status, item_id))
                else:
                    new_rem_q = int(rem_q or 0) - sold_qty
                    if new_rem_q <= 0:
                        new_rem_q = 0
                        new_status = 'Sold'
                    cursor.execute("UPDATE Inventory SET remaining_quantity = %s, status = %s WHERE id = %s", 
                                 (new_rem_q, new_status, item_id))
                
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Error updating remaining stock for item {item_id}: {e}")
            return False

    def delete_item(self, item_id: int) -> bool:
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT COUNT(*) FROM SupplierOperationLines WHERE inventory_id = %s",
                    (item_id,),
                )
                linked = cursor.fetchone()
                if linked and int(linked[0] or 0) > 0:
                    logging.warning(
                        "Rejected deletion of inventory item %s linked to a supplier receipt.",
                        item_id,
                    )
                    return False
                cursor.execute(
                    "UPDATE InventoryCountItems SET inventory_id = NULL WHERE inventory_id = %s",
                    (item_id,),
                )
                cursor.execute(
                    "UPDATE InventoryCountExtraItems SET linked_inventory_id = NULL WHERE linked_inventory_id = %s",
                    (item_id,),
                )
                cursor.execute(
                    "UPDATE InventoryCountAdjustments SET inventory_id = NULL WHERE inventory_id = %s",
                    (item_id,),
                )
                cursor.execute("DELETE FROM Inventory WHERE id = %s", (item_id,))
                conn.commit()
                logging.info(f"Article {item_id} supprimé.")
                return True
        except mysql.connector.Error as e:
            logging.error(f"Erreur lors de la suppression de l'article {item_id}: {e}")
            return False

    def reserve_item(self, item_id: int, client_id: int) -> bool:
        """
        يحجز القطعة للزبون دون إنقاص الكمية أو إنشاء فاتورة بيع.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                # 🟢 نتحقق أولاً أن القطعة متوفرة
                cursor.execute("SELECT status FROM Inventory WHERE id = %s", (item_id,))
                res = cursor.fetchone()
                
                if res and res[0] in ('Available', 'Partially_Sold'):
                    query = """
                        UPDATE Inventory 
                        SET status = 'Reserved', reserved_for_client_id = %s
                        WHERE id = %s
                    """
                    cursor.execute(query, (client_id, item_id))
                    conn.commit()
                    logging.info(f"Article {item_id} réservé pour le client {client_id}.")
                    return True
                return False
        except mysql.connector.Error as e:
            logging.error(f"Erreur lors de la réservation de l'article {item_id}: {e}")
            return False

    def release_item(self, item_id: int) -> bool:
        """
        يلغي حجز القطعة ويعيدها لحالتها المتاحة.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                query = """
                    UPDATE Inventory 
                    SET status = 'Available', reserved_for_client_id = NULL
                    WHERE id = %s AND status = 'Reserved'
                """
                cursor.execute(query, (item_id,))
                conn.commit()
                logging.info(f"Réservation annulée pour l'article {item_id}.")
                return True
        except mysql.connector.Error as e:
            logging.error(f"Erreur lors de l'annulation de la réservation {item_id}: {e}")
            return False

    def update_item_extended(self, item_id: int, barcode: str, name: str, item_type: str, 
                             category_id: int, metal_type_id: int, weight: float, quantity: int, 
                             metal_cost_per_gram: float, labor_cost_per_gram: float, 
                             profit_margin: float, margin_type: str, total_cost: float, 
                             selling_price: float, location_id: int, supplier_id: int,
                             remaining_weight: float, remaining_quantity: int, 
                             status: str, reserved_for_client_id: int) -> bool:
        """
        تحديث شامل للمنتج يشمل الحقول الأساسية والحقول الإضافية (الوزن المتبقي، الحالة، حجز العميل).
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                query = """
                    UPDATE Inventory 
                    SET barcode = %s, name = %s, item_type = %s, category_id = %s, 
                        metal_type_id = %s, weight = %s, quantity = %s, 
                        metal_cost_per_gram = %s, labor_cost_per_gram = %s, 
                        profit_margin = %s, margin_type = %s, total_cost = %s, 
                        selling_price = %s, location_id = %s, supplier_id = %s,
                        remaining_weight = %s, remaining_quantity = %s, 
                        status = %s, reserved_for_client_id = %s
                    WHERE id = %s
                """
                cursor.execute(query, (
                    barcode, name, item_type, category_id, metal_type_id, 
                    weight, quantity, metal_cost_per_gram, labor_cost_per_gram, 
                    profit_margin, margin_type, total_cost, selling_price, 
                    location_id, supplier_id,
                    remaining_weight, remaining_quantity, status, reserved_for_client_id,
                    item_id
                ))
                conn.commit()
                return True
        except Exception as e:
            import logging
            logging.error(f"Erreur update_item_extended: {e}")
            return False
