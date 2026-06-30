# database/coffre_manager.py
import logging

class CoffreManager:
    def __init__(self, db_instance):
        self.db = db_instance

    def add_operation(self, date_operation: str, montant_da: str = "0", 
                      tpe: str = "0", ccp: str = "0", 
                      euro: str = "0", dollar: str = "0", 
                      designation: str = "") -> dict:
        """Ajouter une nouvelle opération"""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                query = """
                    INSERT INTO CoffreMagasin 
                    (date_operation, montant_da, tpe, ccp, euro, dollar, designation) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """
                cursor.execute(query, (date_operation, montant_da, tpe, ccp, euro, dollar, designation))
                conn.commit()
                return {"success": True, "id": cursor.lastrowid}
        except Exception as e:
            logging.error(f"Erreur add_operation: {e}")
            return {"success": False, "message": str(e)}

    def update_operation(self, op_id: int, date_operation: str, montant_da: str, 
                         tpe: str, ccp: str, euro: str, dollar: str, 
                         designation: str = "") -> bool:
        """Modifier une opération"""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                query = """
                    UPDATE CoffreMagasin 
                    SET date_operation=%s, montant_da=%s, tpe=%s, ccp=%s, 
                        euro=%s, dollar=%s, designation=%s 
                    WHERE id=%s
                """
                cursor.execute(query, (date_operation, montant_da, tpe, ccp, euro, dollar, designation, op_id))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Erreur update_operation: {e}")
            return False

    def delete_operation(self, op_id: int) -> bool:
        """Supprimer une opération"""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM CoffreMagasin WHERE id = %s", (op_id,))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logging.error(f"Erreur delete_operation: {e}")
            return False

    def get_all_operations(self) -> list:
        """Récupérer toutes les opérations"""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute("""
                    SELECT id, date_operation, montant_da, tpe, ccp, euro, dollar, designation 
                    FROM CoffreMagasin 
                    ORDER BY id DESC
                """)
                return cursor.fetchall()
        except Exception as e:
            logging.error(f"Erreur get_all_operations: {e}")
            return []

    def get_operations_by_month(self, year: int, month: int) -> list:
        """Récupérer les opérations d'un mois spécifique"""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = """
                    SELECT id, date_operation, montant_da, tpe, ccp, euro, dollar, designation 
                    FROM CoffreMagasin 
                    WHERE date_operation LIKE %s
                    ORDER BY id DESC
                """
                # Cherche au format dd/MM/yyyy
                pattern = f"%/__/{year}"
                if month and month != 0:
                    pattern = f"%/{month:02d}/{year}"
                cursor.execute(query, (pattern,))
                return cursor.fetchall()
        except Exception as e:
            logging.error(f"Erreur get_operations_by_month: {e}")
            return []