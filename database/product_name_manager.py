# database/product_name_manager.py

import mysql.connector
import logging
from typing import List, Dict, Optional

class ProductNameManager:
    """
    Gère les opérations pour la table ProductNames (Désignations prédéfinies).
    Permet de gérer une liste de noms de produits pour la saisie rapide.
    """

    def __init__(self, db_instance):
        self.db = db_instance

    def add_product_name(self, name: str) -> Optional[int]:
        """
        Ajoute un nouveau nom de produit (Désignation) au dictionnaire.
        Ignore automatiquement si le nom existe déjà.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                # استخدمنا INSERT IGNORE لتفادي الخطأ إذا كان الاسم موجوداً مسبقاً
                query = "INSERT IGNORE INTO ProductNames (name) VALUES (%s)"
                cursor.execute(query, (name.strip(),))
                conn.commit()
                
                new_id = cursor.lastrowid
                if new_id:
                    logging.info(f"Nom de produit '{name}' ajouté avec succès (ID: {new_id}).")
                    return new_id
                else:
                    logging.info(f"Le nom '{name}' existe déjà dans le dictionnaire.")
                    return None

        except mysql.connector.Error as e:
            logging.error(f"Erreur lors de l'ajout du nom '{name}': {e}")
            return None

    def update_product_name(self, name_id: int, new_name: str) -> bool:
        """
        Met à jour un nom de produit existant dans le dictionnaire.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                query = "UPDATE ProductNames SET name = %s WHERE id = %s"
                cursor.execute(query, (new_name.strip(), name_id))
                conn.commit()
                
                logging.info(f"Nom de produit {name_id} mis à jour avec succès.")
                return True

        except mysql.connector.Error as e:
            logging.error(f"Erreur lors de la mise à jour du nom {name_id}: {e}")
            return False

    def delete_product_name(self, name_id: int) -> bool:
        """
        Supprime un nom du dictionnaire de saisie rapide.
        (N'affecte pas l'inventaire car ce n'est qu'un dictionnaire texte).
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                query = "DELETE FROM ProductNames WHERE id = %s"
                cursor.execute(query, (name_id,))
                conn.commit()
                
                logging.info(f"Nom de produit {name_id} supprimé avec succès.")
                return True

        except mysql.connector.Error as e:
            logging.error(f"Erreur lors de la suppression du nom {name_id}: {e}")
            return False

    def get_all_product_names(self) -> List[Dict]:
        """
        Récupère tous les noms de produits triés par ordre alphabétique.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = "SELECT * FROM ProductNames ORDER BY name ASC"
                cursor.execute(query)
                return cursor.fetchall()
        except Exception as e:
            logging.error(f"Erreur lors de la récupération des noms de produits: {e}")
            return []

    def get_product_name_by_id(self, name_id: int) -> Optional[Dict]:
        """
        Récupère un nom spécifique par son ID.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = "SELECT * FROM ProductNames WHERE id = %s"
                cursor.execute(query, (name_id,))
                return cursor.fetchone()
        except Exception as e:
            logging.error(f"Erreur lors de la récupération du nom {name_id}: {e}")
            return None