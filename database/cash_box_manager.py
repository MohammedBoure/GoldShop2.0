import logging
from datetime import date

class CashBoxManager:
    def __init__(self, db_instance):
        self.db = db_instance

    def get_or_create_today_session(self, user_id=None):
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                
                # استخدام fetchall لتفريغ الذاكرة المؤقتة بالكامل ومنع الخطأ
                cursor.execute("SELECT * FROM DailySessions WHERE DATE(opened_at) = CURDATE() ORDER BY id DESC")
                sessions = cursor.fetchall()
                while cursor.nextset(): pass
                
                if sessions:
                    return sessions[0] # إرجاع الجلسة الحالية
                
                cursor.execute(
                    "INSERT INTO DailySessions (starting_cash_da, opened_by_user_id) VALUES (%s, %s)",
                    (0.0, user_id)
                )
                conn.commit()
                new_id = cursor.lastrowid
                
                cursor.execute("SELECT * FROM DailySessions WHERE id = %s", (new_id,))
                new_sessions = cursor.fetchall()
                while cursor.nextset(): pass
                
                return new_sessions[0] if new_sessions else None
                
        except Exception as e:
            logging.error(f"Erreur get_or_create_today_session: {e}")
            return None

    def get_session_by_id(self, session_id: int):
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute("SELECT * FROM DailySessions WHERE id = %s", (session_id,))
                sessions = cursor.fetchall()
                while cursor.nextset(): pass
                return sessions[0] if sessions else None
        except Exception as e:
            logging.error(f"Erreur get_session_by_id: {e}")
            return None

    def get_session_by_date(self, year: int, month: int, day: int):
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute(
                    "SELECT * FROM DailySessions WHERE YEAR(opened_at) = %s AND MONTH(opened_at) = %s AND DAY(opened_at) = %s ORDER BY id DESC",
                    (year, month, day)
                )
                sessions = cursor.fetchall()
                while cursor.nextset(): pass
                return sessions[0] if sessions else None
        except Exception as e:
            logging.error(f"Erreur get_session_by_date: {e}")
            return None

    def update_starting_cash(self, session_id: int, amount: float) -> bool:
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                if session_id:
                    cursor.execute("UPDATE DailySessions SET starting_cash_da = %s WHERE id = %s", (amount, session_id))
                else:
                    cursor.execute("UPDATE DailySessions SET starting_cash_da = %s WHERE DATE(opened_at) = CURDATE()", (amount,))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Erreur update_starting_cash: {e}")
            return False