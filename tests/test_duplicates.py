from database.base import Database
db = Database()
with db.get_db_connection() as conn:
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT inventory_id, COUNT(*) as c FROM Versement_Items WHERE item_status = 'EN_COURS' GROUP BY inventory_id HAVING c > 1")
    print('Duplicates active:', cursor.fetchall())
