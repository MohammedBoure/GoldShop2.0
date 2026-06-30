import mysql.connector
import logging
from typing import List, Dict, Optional

class MetalTypeManager:
    """
    Gère les opérations pour la table MetalTypes.
    Permet de gérer les différents titres de métaux (Or 18k, 21k, Argent, etc.)
    avec type (GOLD / SILVER) et leurs valeurs de pureté associées.
    """

    def __init__(self, db_instance):
        self.db = db_instance

    def add_metal_type(self, name: str, purity_value: float, metal_category: str, description: str = "", invoice_display_name: str = None) -> Optional[int]:
        """
        Ajoute un nouveau type de métal (ex: 'Or 18k', 750.0, 'GOLD') avec le nom affiché sur la facture.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                query = """
                    INSERT INTO MetalTypes (name, purity_value, metal_category, description, invoice_display_name)
                    VALUES (%s, %s, %s, %s, %s)
                """
                cursor.execute(query, (name, purity_value, metal_category, description, invoice_display_name))
                conn.commit()
                
                new_id = cursor.lastrowid
                logging.info(f"MetalType '{name}' ajouté avec succès (ID: {new_id}, Type: {metal_category}).")
                return new_id

        except mysql.connector.Error as e:
            logging.error(f"Erreur lors de l'ajout du MetalType '{name}': {e}")
            return None

    def update_metal_type(self, metal_id: int, name: str, purity_value: float, metal_category: str, description: str = "", invoice_display_name: str = None) -> bool:
        """
        Met à jour les informations d'un type de métal existant, y compris le nom pour la facture.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                query = """
                    UPDATE MetalTypes
                    SET name = %s, purity_value = %s, metal_category = %s, description = %s, invoice_display_name = %s
                    WHERE id = %s
                """
                cursor.execute(query, (name, purity_value, metal_category, description, invoice_display_name, metal_id))
                conn.commit()
                
                logging.info(f"MetalType {metal_id} mis à jour avec succès.")
                return True

        except mysql.connector.Error as e:
            logging.error(f"Erreur lors de la mise à jour du MetalType {metal_id}: {e}")
            return False

    def delete_metal_type(self, metal_id: int) -> bool:
        """
        Supprime un type de métal.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("SELECT COUNT(*) FROM Inventory WHERE metal_type_id = %s", (metal_id,))
                if cursor.fetchone()[0] > 0:
                    logging.warning(f"Impossible de supprimer MetalType {metal_id}: Utilisé dans l'inventaire.")
                    return False

                query = "DELETE FROM MetalTypes WHERE id = %s"
                cursor.execute(query, (metal_id,))
                conn.commit()
                
                logging.info(f"MetalType {metal_id} supprimé avec succès.")
                return True

        except mysql.connector.Error as e:
            if e.errno == 1451:
                logging.error(f"Impossible de supprimer le métal {metal_id} car il est lié à des données existantes.")
            else:
                logging.error(f"Erreur lors de la suppression du MetalType {metal_id}: {e}")
            return False

    def get_all_metal_types(self) -> List[Dict]:
        """
        Récupère tous les types de métaux triés par valeur de pureté.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = "SELECT * FROM MetalTypes ORDER BY purity_value DESC"
                cursor.execute(query)
                return cursor.fetchall()
        except Exception as e:
            logging.error(f"Erreur lors de la récupération des MetalTypes: {e}")
            return []

    def get_metal_type_by_id(self, metal_id: int) -> Optional[Dict]:
        """
        Récupère un type de métal spécifique par son ID.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = "SELECT * FROM MetalTypes WHERE id = %s"
                cursor.execute(query, (metal_id,))
                return cursor.fetchone()
        except Exception as e:
            logging.error(f"Erreur lors de la récupération du MetalType {metal_id}: {e}")
            return None