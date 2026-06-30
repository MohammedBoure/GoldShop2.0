# database/category_manager.py

import mysql.connector
import logging
from typing import List, Dict, Optional

class CategoryManager:
    """
    Manages operations for the Categories table.
    Allows managing item classifications (e.g., Rings, Necklaces, Bracelets).
    """

    def __init__(self, db_instance):
        self.db = db_instance

    def add_category(self, name: str, invoice_display_name: str = None) -> Optional[int]:
        """
        Adds a new category (e.g., 'Solitaire Rings').
        Includes the optional invoice_display_name.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                query = "INSERT INTO Categories (name, invoice_display_name) VALUES (%s, %s)"
                cursor.execute(query, (name, invoice_display_name))
                conn.commit()
                
                new_id = cursor.lastrowid
                logging.info(f"Category '{name}' added successfully (ID: {new_id}).")
                return new_id

        except mysql.connector.Error as e:
            logging.error(f"Error adding category '{name}': {e}")
            return None

    def update_category(self, category_id: int, name: str, invoice_display_name: str = None) -> bool:
        """
        Updates an existing category's name and invoice display name.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                query = "UPDATE Categories SET name = %s, invoice_display_name = %s WHERE id = %s"
                cursor.execute(query, (name, invoice_display_name, category_id))
                conn.commit()
                
                logging.info(f"Category {category_id} updated successfully.")
                return True

        except mysql.connector.Error as e:
            logging.error(f"Error updating category {category_id}: {e}")
            return False

    def delete_category(self, category_id: int) -> bool:
        """
        Deletes a category.
        WARNING: Will fail if this category is used in Inventory (Foreign Key).
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Preventive check (optional)
                cursor.execute("SELECT COUNT(*) FROM Inventory WHERE category_id = %s", (category_id,))
                if cursor.fetchone()[0] > 0:
                    logging.warning(f"Cannot delete category {category_id}: It contains items.")
                    return False

                query = "DELETE FROM Categories WHERE id = %s"
                cursor.execute(query, (category_id,))
                conn.commit()
                
                logging.info(f"Category {category_id} deleted successfully.")
                return True

        except mysql.connector.Error as e:
            if e.errno == 1451: # Foreign key constraint fails
                logging.error(f"Cannot delete category {category_id} because it is linked to existing items.")
            else:
                logging.error(f"Error deleting category {category_id}: {e}")
            return False

    def get_all_categories(self) -> List[Dict]:
        """
        Retrieves all categories sorted by name.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = "SELECT * FROM Categories ORDER BY name ASC"
                cursor.execute(query)
                return cursor.fetchall()
        except Exception as e:
            logging.error(f"Error retrieving categories: {e}")
            return []

    def get_category_by_id(self, category_id: int) -> Optional[Dict]:
        """
        Retrieves a specific category by its ID.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = "SELECT * FROM Categories WHERE id = %s"
                cursor.execute(query, (category_id,))
                return cursor.fetchone()
        except Exception as e:
            logging.error(f"Error retrieving category {category_id}: {e}")
            return None