from database.base import Database
db = Database()
with db.get_db_connection() as conn:
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, status FROM Versements WHERE id = 2")
    print('Versement 2 status:', cursor.fetchone())
