from database.base import Database
db = Database()
with db.get_db_connection() as conn:
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, inventory_id, item_status FROM Versement_Items WHERE item_status = 'ANNULE'")
    print(cursor.fetchall())
