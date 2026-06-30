# database/invoice_note_manager.py

import mysql.connector
import logging
from typing import List, Dict

class InvoiceNoteManager:
    """
    Gestionnaire des notes/phrases personnalisées pour les factures.
    """

    def __init__(self, db_instance):
        self.db = db_instance

    def get_all_notes(self) -> List[str]:
        """Récupère toutes les notes sous forme de liste de textes."""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT note_text FROM InvoiceNotes ORDER BY note_text ASC")
                return [row[0] for row in cursor.fetchall()]
        except mysql.connector.Error as e:
            logging.error(f"❌ Erreur lors de la récupération des notes de facture: {e}")
            return []

    def get_all_notes_with_ids(self) -> List[Dict]:
        """Récupère toutes les notes avec leurs IDs (utile pour une interface de gestion)."""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute("SELECT * FROM InvoiceNotes ORDER BY note_text ASC")
                return cursor.fetchall()
        except mysql.connector.Error as e:
            logging.error(f"❌ Erreur lors de la récupération des notes avec IDs: {e}")
            return []

    def add_note(self, text: str) -> bool:
        """Ajoute une nouvelle note (ignore si elle existe déjà)."""
        if not text or not text.strip():
            return False
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT IGNORE INTO InvoiceNotes (note_text) VALUES (%s)", (text.strip(),))
                conn.commit()
                return cursor.rowcount > 0
        except mysql.connector.Error as e:
            logging.error(f"❌ Erreur lors de l'ajout de la note: {e}")
            return False

    def add_notes_bulk(self, notes: List[str]) -> bool:
        """Ajoute plusieurs notes d'un coup (Optimisé pour les listes)."""
        valid_notes = [n.strip() for n in notes if n and n.strip()]
        if not valid_notes:
            return False
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                sql = "INSERT IGNORE INTO InvoiceNotes (note_text) VALUES (%s)"
                data = [(n,) for n in valid_notes]
                cursor.executemany(sql, data)
                conn.commit()
                return True
        except mysql.connector.Error as e:
            logging.error(f"❌ Erreur lors de l'ajout multiple de notes: {e}")
            return False

    def update_note(self, note_id: int, new_text: str) -> bool:
        """Met à jour une note existante."""
        if not new_text or not new_text.strip():
            return False
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE InvoiceNotes SET note_text = %s WHERE id = %s", (new_text.strip(), note_id))
                conn.commit()
                return True
        except mysql.connector.Error as e:
            logging.error(f"❌ Erreur lors de la mise à jour de la note {note_id}: {e}")
            return False

    def delete_note(self, note_id: int) -> bool:
        """Supprime une note par son ID."""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM InvoiceNotes WHERE id = %s", (note_id,))
                conn.commit()
                return True
        except mysql.connector.Error as e:
            logging.error(f"❌ Erreur lors de la suppression de la note {note_id}: {e}")
            return False