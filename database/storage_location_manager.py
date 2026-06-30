# database/storage_location_manager.py

import mysql.connector
import logging
from typing import List, Dict, Optional

class StorageLocationManager:
    """
    Gère les opérations pour la table StorageLocations.
    Permet de gérer les emplacements physiques de stockage (ex: Coffre-fort, Vitrine, Plateau 1).
    """

    def __init__(self, db_instance):
        self.db = db_instance

    def add_location(self, name: str) -> Optional[int]:
        """
        Ajoute un nouvel emplacement de stockage.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                query = "INSERT INTO StorageLocations (name) VALUES (%s)"
                cursor.execute(query, (name,))
                conn.commit()
                
                new_id = cursor.lastrowid
                logging.info(f"Emplacement '{name}' ajouté avec succès (ID: {new_id}).")
                return new_id

        except mysql.connector.Error as e:
            logging.error(f"Erreur lors de l'ajout de l'emplacement '{name}': {e}")
            return None

    def update_location(self, location_id: int, name: str) -> bool:
        """
        Met à jour le nom d'un emplacement existant.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                query = "UPDATE StorageLocations SET name = %s WHERE id = %s"
                cursor.execute(query, (name, location_id))
                conn.commit()
                
                logging.info(f"Emplacement {location_id} mis à jour avec succès.")
                return True

        except mysql.connector.Error as e:
            logging.error(f"Erreur lors de la mise à jour de l'emplacement {location_id}: {e}")
            return False

    def delete_location(self, location_id: int) -> bool:
        """
        Supprime un emplacement.
        ATTENTION : Échouera si cet emplacement contient des articles (Foreign Key).
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Vérification préventive : est-ce que cet emplacement contient des objets ?
                cursor.execute("SELECT COUNT(*) FROM Inventory WHERE location_id = %s", (location_id,))
                if cursor.fetchone()[0] > 0:
                    logging.warning(f"Impossible de supprimer l'emplacement {location_id}: Il contient des articles en stock.")
                    return False

                query = "DELETE FROM StorageLocations WHERE id = %s"
                cursor.execute(query, (location_id,))
                conn.commit()
                
                logging.info(f"Emplacement {location_id} supprimé avec succès.")
                return True

        except mysql.connector.Error as e:
            if e.errno == 1451: # Foreign key constraint fails
                logging.error(f"Impossible de supprimer l'emplacement {location_id} car il est lié à des articles existants.")
            else:
                logging.error(f"Erreur lors de la suppression de l'emplacement {location_id}: {e}")
            return False

    def get_all_locations(self) -> List[Dict]:
        """
        Récupère tous les emplacements triés par nom.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = "SELECT * FROM StorageLocations ORDER BY name ASC"
                cursor.execute(query)
                return cursor.fetchall()
        except Exception as e:
            logging.error(f"Erreur lors de la récupération des emplacements: {e}")
            return []

    def get_location_by_id(self, location_id: int) -> Optional[Dict]:
        """
        Récupère un emplacement spécifique par son ID.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = "SELECT * FROM StorageLocations WHERE id = %s"
                cursor.execute(query, (location_id,))
                return cursor.fetchone()
        except Exception as e:
            logging.error(f"Erreur lors de la récupération de l'emplacement {location_id}: {e}")
            return None