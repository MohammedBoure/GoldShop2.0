# database/coffre_manager.py
import logging

class CoffreManager:
    def __init__(self, db_instance):
        self.db = db_instance
        self._ensure_columns()

    def _ensure_columns(self):
        """Vérifie et ajoute dynamiquement les colonnes oc_or et oc_argent si nécessaire."""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SHOW COLUMNS FROM CoffreMagasin LIKE 'oc_or'")
                if not cursor.fetchone():
                    cursor.execute("ALTER TABLE CoffreMagasin ADD COLUMN oc_or VARCHAR(50) NOT NULL DEFAULT '0'")
                cursor.execute("SHOW COLUMNS FROM CoffreMagasin LIKE 'oc_argent'")
                if not cursor.fetchone():
                    cursor.execute("ALTER TABLE CoffreMagasin ADD COLUMN oc_argent VARCHAR(50) NOT NULL DEFAULT '0'")
                conn.commit()
        except Exception as e:
            logging.debug(f"Info _ensure_columns CoffreMagasin: {e}")

    def add_operation(self, date_operation: str, montant_da: str = "0", 
                      tpe: str = "0", ccp: str = "0", 
                      euro: str = "0", dollar: str = "0", 
                      designation: str = "",
                      oc_or: str = "0", oc_argent: str = "0", **kwargs) -> dict:
        """Ajouter une nouvelle opération dans le Coffre"""
        # Support flexible kwargs or positional shifts
        if "oc_gold" in kwargs:
            oc_or = kwargs["oc_gold"]
        if "oc_silver" in kwargs:
            oc_argent = kwargs["oc_silver"]

        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                query = """
                    INSERT INTO CoffreMagasin 
                    (date_operation, montant_da, oc_or, oc_argent, tpe, ccp, euro, dollar, designation) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                cursor.execute(query, (
                    str(date_operation).strip(),
                    str(montant_da or "0").strip(),
                    str(oc_or or "0").strip(),
                    str(oc_argent or "0").strip(),
                    str(tpe or "0").strip(),
                    str(ccp or "0").strip(),
                    str(euro or "0").strip(),
                    str(dollar or "0").strip(),
                    str(designation or "").strip()
                ))
                conn.commit()
                return {"success": True, "id": cursor.lastrowid}
        except Exception as e:
            logging.error(f"Erreur add_operation: {e}")
            return {"success": False, "message": str(e)}

    def update_operation(self, op_id: int, date_operation: str, montant_da: str, 
                         tpe: str, ccp: str, euro: str, dollar: str, 
                         designation: str = "",
                         oc_or: str = "0", oc_argent: str = "0", **kwargs) -> bool:
        """Modifier une opération"""
        if "oc_gold" in kwargs:
            oc_or = kwargs["oc_gold"]
        if "oc_silver" in kwargs:
            oc_argent = kwargs["oc_silver"]

        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                query = """
                    UPDATE CoffreMagasin 
                    SET date_operation=%s, montant_da=%s, oc_or=%s, oc_argent=%s, 
                        tpe=%s, ccp=%s, euro=%s, dollar=%s, designation=%s 
                    WHERE id=%s
                """
                cursor.execute(query, (
                    str(date_operation).strip(),
                    str(montant_da or "0").strip(),
                    str(oc_or or "0").strip(),
                    str(oc_argent or "0").strip(),
                    str(tpe or "0").strip(),
                    str(ccp or "0").strip(),
                    str(euro or "0").strip(),
                    str(dollar or "0").strip(),
                    str(designation or "").strip(),
                    op_id
                ))
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
                    SELECT id, date_operation, montant_da, 
                           COALESCE(oc_or, '0') as oc_or, 
                           COALESCE(oc_argent, '0') as oc_argent, 
                           tpe, ccp, euro, dollar, designation 
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
                    SELECT id, date_operation, montant_da, 
                           COALESCE(oc_or, '0') as oc_or, 
                           COALESCE(oc_argent, '0') as oc_argent, 
                           tpe, ccp, euro, dollar, designation 
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

    def check_existing_transfer(self, date_str: str) -> list:
        """Vérifie si des opérations pour cette date existent déjà dans le coffre"""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                clean_date = str(date_str).strip()
                query = """
                    SELECT id, date_operation, montant_da, 
                           COALESCE(oc_or, '0') as oc_or, 
                           COALESCE(oc_argent, '0') as oc_argent, 
                           tpe, ccp, euro, dollar, designation 
                    FROM CoffreMagasin 
                    WHERE date_operation = %s OR date_operation LIKE %s
                    ORDER BY id DESC
                """
                cursor.execute(query, (clean_date, f"%{clean_date}%"))
                return cursor.fetchall()
        except Exception as e:
            logging.error(f"Erreur check_existing_transfer: {e}")
            return []