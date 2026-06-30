# database/gold_deposit_manager.py

import mysql.connector
import logging
from typing import List, Dict, Optional

class GoldDepositManager:
    """
    Manager to handle Client Gold Deposits (Amanat).
    Manages the 'ClientGoldDeposits' table.
    """

    def __init__(self, db_instance):
        self.db = db_instance

    def add_deposit(self, 
                    depositor_name: str, 
                    metal_type_id: int, 
                    weight: float, 
                    user_id: int,
                    depositor_phone: str = None, 
                    depositor_card: str = None, 
                    description: str = "", 
                    image_url: str = None) -> bool:
        """
        Register a new gold deposit (Receive gold from client).
        Sets transaction_type='DEPOSIT' and status='ACTIVE'.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                query = """
                    INSERT INTO ClientGoldDeposits 
                    (depositor_name, depositor_phone, depositor_identity_card, 
                     metal_type_id, weight, transaction_type, status, 
                     item_description, image_url, created_by_user_id, transaction_date)
                    VALUES (%s, %s, %s, %s, %s, 'DEPOSIT', 'ACTIVE', %s, %s, %s, NOW())
                """
                params = (depositor_name, depositor_phone, depositor_card, 
                          metal_type_id, weight, description, image_url, user_id)
                
                cursor.execute(query, params)
                deposit_id = cursor.lastrowid
                conn.commit()
                logging.info(f"✅ Gold Deposit added for {depositor_name} (ID: {deposit_id})")
                return True
        except mysql.connector.Error as e:
            logging.error(f"❌ Error adding gold deposit: {e}")
            return False

    def mark_as_returned(self, deposit_id: int, notes: str = "") -> bool:
        """
        Mark a deposit as returned to the client.
        Updates status to 'RETURNED'.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                # نحدث الحالة ونضيف ملاحظة في خانة الملاحظات
                query = """
                    UPDATE ClientGoldDeposits 
                    SET status = 'RETURNED', notes = CONCAT(COALESCE(notes, ''), ' [Returned on ', NOW(), '] ', %s)
                    WHERE id = %s
                """
                cursor.execute(query, (notes, deposit_id))
                conn.commit()
                logging.info(f"🔄 Deposit {deposit_id} marked as RETURNED.")
                return True
        except mysql.connector.Error as e:
            logging.error(f"❌ Error returning deposit: {e}")
            return False

    def get_active_deposits(self) -> List[Dict]:
        """
        Get all gold items currently held in the shop (Status = ACTIVE).
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = """
                    SELECT 
                        cgd.*,
                        mt.name as metal_name,
                        u.username as created_by
                    FROM ClientGoldDeposits cgd
                    JOIN MetalTypes mt ON cgd.metal_type_id = mt.id
                    LEFT JOIN Users u ON cgd.created_by_user_id = u.id
                    WHERE cgd.status = 'ACTIVE'
                    ORDER BY cgd.transaction_date DESC
                """
                cursor.execute(query)
                return cursor.fetchall()
        except Exception as e:
            logging.error(f"❌ Error fetching active deposits: {e}")
            return []

    def search_deposits(self, search_term: str) -> List[Dict]:
        """
        Search deposits by client name or phone (Active and Returned).
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = """
                    SELECT 
                        cgd.*,
                        mt.name as metal_name
                    FROM ClientGoldDeposits cgd
                    JOIN MetalTypes mt ON cgd.metal_type_id = mt.id
                    WHERE cgd.depositor_name LIKE %s OR cgd.depositor_phone LIKE %s
                    ORDER BY cgd.transaction_date DESC
                """
                term = f"%{search_term}%"
                cursor.execute(query, (term, term))
                return cursor.fetchall()
        except Exception as e:
            logging.error(f"❌ Error searching deposits: {e}")
            return []

    def get_total_held_gold(self) -> List[Dict]:
        """
        Calculate total weight of gold held in trust (Amanat) grouped by Metal Type.
        Useful for insurance or daily checks.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = """
                    SELECT 
                        mt.name as metal_name,
                        SUM(cgd.weight) as total_weight
                    FROM ClientGoldDeposits cgd
                    JOIN MetalTypes mt ON cgd.metal_type_id = mt.id
                    WHERE cgd.status = 'ACTIVE'
                    GROUP BY mt.id, mt.name
                """
                cursor.execute(query)
                return cursor.fetchall()
        except Exception as e:
            logging.error(f"❌ Error calculating held gold stats: {e}")
            return []