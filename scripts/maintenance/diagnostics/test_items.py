from database.base import Database

db = Database()
with db.get_db_connection() as conn:
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, versement_id, item_status FROM Versement_Items WHERE inventory_id = 1909")
    print(cursor.fetchall())
