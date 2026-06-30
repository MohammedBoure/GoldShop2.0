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

    # ========================== WORK ORDERS (الأعمال المربوطة بالزبائن) ==========================
    def add_order(self, artisan_id, client_id, numero, date_remis, obj, poid, date_recue, date_sortie, prix, vente, diff):
        """إضافة عمل جديد (مربوط بـ client_id بدلاً من nom و tel)"""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                query = """
                    INSERT INTO ArtisanWorkOrders 
                    (artisan_id, client_id, numero, date_remis, obj, poid, date_recue, date_sortie, prix, vente, diff) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                cursor.execute(query, (artisan_id, client_id, numero, date_remis, obj, poid, date_recue, date_sortie, prix, vente, diff))
                conn.commit()
                return {"success": True, "id": cursor.lastrowid}
        except Exception as e:
            logging.error(f"Erreur add_order: {e}")
            return {"success": False, "message": str(e)}

    def update_order(self, order_id, artisan_id, client_id, numero, date_remis, obj, poid, date_recue, date_sortie, prix, vente, diff):
        """تعديل عمل (مربوط بـ client_id)"""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                query = """
                    UPDATE ArtisanWorkOrders 
                    SET artisan_id=%s, client_id=%s, numero=%s, date_remis=%s, obj=%s, 
                        poid=%s, date_recue=%s, date_sortie=%s, prix=%s, vente=%s, diff=%s 
                    WHERE id=%s
                """
                cursor.execute(query, (artisan_id, client_id, numero, date_remis, obj, poid, date_recue, date_sortie, prix, vente, diff, order_id))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Erreur update_order: {e}")
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
        """جلب أعمال حرفي محدد (يتضمن client_id لجلب اسم الزبون لاحقاً في الواجهة)"""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = """
                    SELECT id, artisan_id, client_id, numero, date_remis, obj, poid, 
                           date_recue, date_sortie, prix, vente, diff 
                    FROM ArtisanWorkOrders 
                    WHERE artisan_id = %s ORDER BY id ASC
                """
                cursor.execute(query, (artisan_id,))
                return cursor.fetchall()
        except Exception as e:
            logging.error(f"Erreur get_orders_by_artisan: {e}")
            return []