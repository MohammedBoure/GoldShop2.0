# database/rh_manager.py
import logging

class RHManager:
    def __init__(self, db_instance):
        self.db = db_instance

    # ========================== ENTRÉES (حر) ==========================
    def add_entree(self, nom: str, date_debut: str, observations: str = "") -> dict:
        """إضافة سطر جديد بحرية تامة"""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                query = "INSERT INTO RH_Personnel (nom, date_debut, observations) VALUES (%s, %s, %s)"
                cursor.execute(query, (nom, date_debut, observations))
                conn.commit()
                return {"success": True, "id": cursor.lastrowid}
        except Exception as e:
            logging.error(f"Erreur add_entree: {e}")
            return {"success": False, "message": str(e)}

    def update_entree(self, p_id: int, nom: str, date_debut: str, observations: str = "") -> bool:
        """تعديل سطر بحرية"""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                query = "UPDATE RH_Personnel SET nom=%s, date_debut=%s, observations=%s WHERE id=%s"
                cursor.execute(query, (nom, date_debut, observations, p_id))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Erreur update_entree: {e}")
            return False

    def delete_entree(self, entree_id: int) -> bool:
        """حذف سطر واحد فقط - مستقل تماماً"""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM RH_Personnel WHERE id = %s", (entree_id,))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logging.error(f"Erreur delete_entree: {e}")
            return False

    def get_all_entrees(self) -> list:
        """جلب كل سطور الدخول"""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute("SELECT id, nom, date_debut, observations FROM RH_Personnel ORDER BY id DESC")
                return cursor.fetchall()
        except Exception as e:
            logging.error(f"Erreur get_all_entrees: {e}")
            return []

    # ========================== SORTIES (حر) ==========================
    def add_sortie(self, nom: str, date_sortie: str, duree: str = "") -> dict:
        """إضافة سطر خروج جديد بحرية"""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                # تم إضافة date_debut كقيمة فارغة لتجنب خطأ NOT NULL
                query = "INSERT INTO RH_Personnel (nom, date_debut, date_sortie, duree_travail) VALUES (%s, %s, %s, %s)"
                cursor.execute(query, (nom, "", date_sortie, duree))
                conn.commit()
                return {"success": True, "id": cursor.lastrowid}
        except Exception as e:
            logging.error(f"Erreur add_sortie: {e}")
            return {"success": False, "message": str(e)}

    def update_sortie(self, p_id: int, nom: str, date_sortie: str, duree: str = "") -> bool:
        """تعديل سطر خروج بحرية"""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                query = "UPDATE RH_Personnel SET nom=%s, date_sortie=%s, duree_travail=%s WHERE id=%s"
                cursor.execute(query, (nom, date_sortie, duree, p_id))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Erreur update_sortie: {e}")
            return False

    def delete_sortie(self, sortie_id: int) -> bool:
        """حذف سطر خروج واحد فقط"""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM RH_Personnel WHERE id = %s", (sortie_id,))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logging.error(f"Erreur delete_sortie: {e}")
            return False

    def get_all_sorties(self) -> list:
        """جلب كل سطور الخروج"""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute("SELECT id, nom, date_sortie, duree_travail FROM RH_Personnel WHERE date_sortie IS NOT NULL AND date_sortie != '' ORDER BY id DESC")
                return cursor.fetchall()
        except Exception as e:
            logging.error(f"Erreur get_all_sorties: {e}")
            return []

    # ========================== AVANCES (حر تماماً) ==========================
    def add_avance(self, nom_ouvrier: str, date_avance: str, montant_da: str, observations: str = "") -> dict:
        """إضافة سلفة بحرية - الاسم نص عادي وليس مرتبطاً بأي جدول"""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                query = "INSERT INTO RH_Avances (nom_ouvrier, date_avance, montant_da, observations) VALUES (%s, %s, %s, %s)"
                cursor.execute(query, (nom_ouvrier, date_avance, montant_da, observations))
                conn.commit()
                return {"success": True, "id": cursor.lastrowid}
        except Exception as e:
            logging.error(f"Erreur add_avance: {e}")
            return {"success": False, "message": str(e)}

    def update_avance(self, a_id: int, nom_ouvrier: str, date_avance: str, montant_da: str, observations: str = "") -> bool:
        """تعديل سلفة بحرية"""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                query = "UPDATE RH_Avances SET nom_ouvrier=%s, date_avance=%s, montant_da=%s, observations=%s WHERE id=%s"
                cursor.execute(query, (nom_ouvrier, date_avance, montant_da, observations, a_id))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Erreur update_avance: {e}")
            return False

    def delete_avance(self, avance_id: int) -> bool:
        """حذف سلفة واحدة فقط - مستقلة تماماً"""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM RH_Avances WHERE id = %s", (avance_id,))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logging.error(f"Erreur delete_avance: {e}")
            return False

    def get_all_avances(self) -> list:
        """جلب كل السلفات"""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute("SELECT id, nom_ouvrier, date_avance, montant_da, observations FROM RH_Avances ORDER BY id DESC")
                return cursor.fetchall()
        except Exception as e:
            logging.error(f"Erreur get_all_avances: {e}")
            return []

    def get_avances_by_name(self, nom: str) -> list:
        """جلب سلفات شخص محدد"""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute("SELECT id, nom_ouvrier, date_avance, montant_da, observations FROM RH_Avances WHERE nom_ouvrier = %s ORDER BY id DESC", (nom,))
                return cursor.fetchall()
        except Exception as e:
            logging.error(f"Erreur get_avances_by_name: {e}")
            return []

    def get_distinct_names_for_avances(self) -> list:
        """جلب الأسماء الموجودة في السلفات (للفلتر)"""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT DISTINCT nom_ouvrier FROM RH_Avances ORDER BY nom_ouvrier")
                return [row[0] for row in cursor.fetchall() if row[0]]
        except Exception as e:
            logging.error(f"Erreur get_distinct_names: {e}")
            return []