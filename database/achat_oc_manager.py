import logging

class AchatOCManager:
    """
    مدير عمليات شراء الذهب الكسر (Achat OC) يدوياً.
    يدير إضافات السجل، التعديل، الحذف، وجلب البيانات للعرض.
    """
    def __init__(self, db_instance):
        self.db = db_instance

    def add_record(self, date_achat: str, weight_g: float, unit_price_da: float, total_amount_da: float, notes: str = "") -> dict:
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                query = """
                    INSERT INTO AchatOC (date_achat, weight_g, unit_price_da, total_amount_da, notes)
                    VALUES (%s, %s, %s, %s, %s)
                """
                cursor.execute(query, (date_achat, weight_g, unit_price_da, total_amount_da, notes))
                conn.commit()
                return {"success": True, "id": cursor.lastrowid}
        except Exception as e:
            logging.error(f"Erreur add_achat_oc_record: {e}")
            return {"success": False, "message": str(e)}

    def get_all_records(self) -> list:
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                # الجلب مرتب من الأحدث للأقدم
                query = "SELECT * FROM AchatOC ORDER BY date_achat DESC, id DESC"
                cursor.execute(query)
                records = cursor.fetchall()
                while cursor.nextset(): pass
                return records
        except Exception as e:
            logging.error(f"Erreur get_all_achat_oc_records: {e}")
            return []

    def update_record(self, record_id: int, date_achat: str, weight_g: float, unit_price_da: float, total_amount_da: float, notes: str) -> bool:
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                query = """
                    UPDATE AchatOC 
                    SET date_achat = %s, weight_g = %s, unit_price_da = %s, total_amount_da = %s, notes = %s
                    WHERE id = %s
                """
                cursor.execute(query, (date_achat, weight_g, unit_price_da, total_amount_da, notes, record_id))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Erreur update_achat_oc_record: {e}")
            return False

    def delete_record(self, record_id: int) -> bool:
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM AchatOC WHERE id = %s", (record_id,))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Erreur delete_achat_oc_record: {e}")
            return False
        
    def get_records_by_month(self, year: int, month: int) -> list:
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = """
                    SELECT * FROM AchatOC 
                    WHERE YEAR(date_achat) = %s AND MONTH(date_achat) = %s
                    ORDER BY date_achat DESC, id DESC
                """
                cursor.execute(query, (year, month))
                records = cursor.fetchall()
                while cursor.nextset(): pass
                return records
        except Exception as e:
            import logging
            logging.error(f"Erreur get_records_by_month (AchatOC): {e}")
            return []