from database.base import Database

db = Database()
with db.get_db_connection() as conn:
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT COUNT(*) as c FROM Inventory WHERE remaining_weight IS NULL OR remaining_weight <= 0")
    print("Zero weight items:", cursor.fetchone()['c'])
