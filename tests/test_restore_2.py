from database.base import Database
from database.versement import VersementManager

db = Database()
vm = VersementManager(db)
with db.get_db_connection() as conn:
    cursor = conn.cursor(dictionary=True)
    # Find an ANNULE item that has NO EN_COURS items
    cursor.execute("""
        SELECT v1.id, v1.inventory_id 
        FROM Versement_Items v1
        WHERE v1.item_status = 'ANNULE'
        AND NOT EXISTS (
            SELECT 1 FROM Versement_Items v2
            WHERE v2.inventory_id = v1.inventory_id AND v2.item_status = 'EN_COURS'
        )
        ORDER BY v1.id DESC LIMIT 1
    """)
    item = cursor.fetchone()
    
    if item:
        print(f"Testing restore for ANNULE item {item['id']} with inventory_id {item['inventory_id']}")
        
        # Manually run the checks
        cursor.execute("SELECT status, item_type, remaining_weight FROM Inventory WHERE id = %s", (item['inventory_id'],))
        inv = cursor.fetchone()
        print("Inventory:", inv)
        
        result = vm.revert_versement_item_status(item['id'])
        print("Result of revert:", result)
        
        if result[0]:
            print("IT WORKS! The issue was just that the item I picked previously was already EN_COURS elsewhere.")
        else:
            print("IT STILL FAILS! The issue is somewhere else.")
    else:
        print("No suitable ANNULE item found.")
