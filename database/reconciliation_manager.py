# database/reconciliation_manager.py

import mysql.connector
import logging
from typing import List, Dict, Optional

class ReconciliationManager:
    """
    Manager spécialisé pour l'audit et l'analyse des écarts de caisse (SessionReconciliations).
    Utilisé par l'administrateur pour voir les déficits/excédents.
    """

    def __init__(self, db_instance):
        self.db = db_instance

    def get_discrepancies(self, start_date=None, end_date=None, only_problems: bool = True) -> List[Dict]:
        """
        Récupère la liste des réconciliations (avec filtres).
        - only_problems=True : Retourne uniquement les cas où il y a un écart (Différence != 0).
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                
                query = """
                    SELECT 
                        sr.id, sr.session_id, sr.difference,
                        sr.expected_amount, sr.counted_amount,
                        curr.code as currency_code, curr.symbol,
                        u.username as employee_name, rs.closed_at
                    FROM SessionReconciliations sr
                    JOIN Currencies curr ON sr.currency_id = curr.id
                    JOIN RegisterSessions rs ON sr.session_id = rs.id
                    JOIN Users u ON rs.user_id = u.id
                    WHERE 1=1
                """
                params = []

                if only_problems:
                    # نركز فقط على الحالات التي لا يساوي فيها الفرق صفراً (سواء عجز أو فائض)
                    query += " AND sr.difference != 0"

                if start_date and end_date:
                    query += " AND DATE(rs.closed_at) BETWEEN %s AND %s"
                    params.append(start_date)
                    params.append(end_date)
                
                query += " ORDER BY rs.closed_at DESC"

                cursor.execute(query, tuple(params))
                return cursor.fetchall()
        except Exception as e:
            logging.error(f"❌ Erreur rapport écarts : {e}")
            return []

    def get_total_shortage_by_user(self, user_id: int, currency_id: int) -> float:
        """
        Calcule le total du MANQUE (العجز) accumulé par un employé spécifique pour une devise donnée.
        Utile pour savoir combien l'employé doit rembourser.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                query = """
                    SELECT SUM(sr.difference)
                    FROM SessionReconciliations sr
                    JOIN RegisterSessions rs ON sr.session_id = rs.id
                    WHERE rs.user_id = %s 
                      AND sr.currency_id = %s 
                      AND sr.difference < 0  -- On ne compte que les déficits (valeurs négatives)
                """
                cursor.execute(query, (user_id, currency_id))
                result = cursor.fetchone()
                return float(result[0]) if result and result[0] else 0.0
        except Exception as e:
            logging.error(f"❌ Erreur calcul déficit utilisateur : {e}")
            return 0.0

    def get_session_details(self, session_id: int) -> List[Dict]:
        """
        Récupère les détails complets de réconciliation pour une session spécifique.
        (Affiche toutes les devises, même celles sans écart).
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = """
                    SELECT 
                        curr.name as currency_name,
                        curr.symbol,
                        sr.expected_amount,
                        sr.counted_amount,
                        sr.difference
                    FROM SessionReconciliations sr
                    JOIN Currencies curr ON sr.currency_id = curr.id
                    WHERE sr.session_id = %s
                """
                cursor.execute(query, (session_id,))
                return cursor.fetchall()
        except Exception as e:
            logging.error(f"❌ Erreur détails session {session_id} : {e}")
            return []
            
    def justify_discrepancy(self, reconciliation_id: int, note: str) -> bool:
        """
        (Optional) Allows Admin to add a note explaining the difference (e.g., 'Forgiven', 'Deducted from salary').
        Requires adding a 'notes' column to SessionReconciliations first if not exists.
        """
        # ملاحظة: الجدول الذي أرسلته سابقاً لا يحتوي على حقل notes في SessionReconciliations
        # إذا أردت هذه الميزة، يجب إضافة الحقل أولاً، أو استخدام حقل closing_note في الجلسة.
        pass