import mysql.connector
import logging
from typing import List, Dict, Optional

class CustomerManager:
    """
    مدير الزبائن المحدث والمبسط (يتوافق مع نظام الإكسيل السريع).
    """
    def __init__(self, db_instance):
        self.db = db_instance

    def add_customer(self, name: str, phone: str = None, address: str = None, notes: str = None) -> Optional[int]:
        """إضافة زبون جديد"""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                query = """
                    INSERT INTO Clients (name, phone, address, notes)
                    VALUES (%s, %s, %s, %s)
                """
                cursor.execute(query, (name, phone, address, notes))
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            logging.error(f"Erreur ajout client: {e}")
            return None

    def update_customer(self, client_id: int, name: str, phone: str = None, address: str = None, notes: str = None) -> bool:
        """تعديل بيانات زبون"""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                query = """
                    UPDATE Clients 
                    SET name = %s, phone = %s, address = %s, notes = %s
                    WHERE id = %s
                """
                cursor.execute(query, (name, phone, address, notes, client_id))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Erreur maj client: {e}")
            return False

    def get_customer_by_id(self, client_id: int) -> Optional[Dict]:
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = "SELECT * FROM Clients WHERE id = %s"
                cursor.execute(query, (client_id,))
                res = cursor.fetchone()
                while cursor.nextset(): pass
                return res
        except Exception as e:
            logging.error(f"Erreur get client by id: {e}")
            return None

    def get_all_customers_with_balances(self) -> List[Dict]:
        """جلب كل الزبائن لواجهة البيع (POS) بأرصدة صفرية مؤقتة لمنع الانهيار"""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = """
                    SELECT 
                        id, name, phone, address, notes,
                        0.0 as total_debt_da,
                        0.0 as total_gold_debt,
                        0.0 as current_balance,
                        0.0 as balance_dzd
                    FROM Clients
                    ORDER BY name ASC
                """
                cursor.execute(query)
                res = cursor.fetchall()
                while cursor.nextset(): pass
                return res
        except Exception as e:
            logging.error(f"Erreur get customers: {e}")
            return []

    def get_clients_paginated(self, limit: int = 50, offset: int = 0, search_text: str = None) -> List[Dict]:
        """جلب الزبائن مع دعم البحث وتجاوز نظام الديون المعقد"""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = """
                    SELECT 
                        c.id, c.name, c.phone, c.address, c.notes,
                        0.0 AS total_debt,
                        0.0 AS total_gold_debt
                    FROM Clients c
                """
                params = []

                if search_text:
                    query += " WHERE c.name LIKE %s OR c.phone LIKE %s"
                    search_pattern = f"%{search_text}%"
                    params.extend([search_pattern, search_pattern])

                query += f" ORDER BY c.name ASC LIMIT {int(limit)} OFFSET {int(offset)}"

                cursor.execute(query, tuple(params))
                res = cursor.fetchall()
                while cursor.nextset(): pass
                return res
                
        except Exception as e:
            logging.error(f"Erreur get clients paginated: {e}")
            return []