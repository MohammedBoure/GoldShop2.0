import sys
import os

from database.base import Database
from database.versement import VersementManager

db = Database()
vm = VersementManager(db)

with db.get_db_connection() as conn:
    cursor = conn.cursor(dictionary=True)
    
    # Let's find the last ANNULE item
    cursor.execute("SELECT id, inventory_id FROM Versement_Items WHERE item_status = 'ANNULE' ORDER BY id DESC LIMIT 1")
    item = cursor.fetchone()
    
    if item:
        print(f"Testing restore for ANNULE item {item['id']} with inventory_id {item['inventory_id']}")
        
        # Manually run the checks that _lock_inventory_for_reservation does
        cursor.execute("""
            SELECT id, item_type, weight, remaining_weight, quantity, remaining_quantity,
                   status, reserved_for_client_id
            FROM Inventory WHERE id = %s
        """, (item['inventory_id'],))
        inv = cursor.fetchone()
        print("Inventory:", inv)
        
        cursor.execute("""
            SELECT COALESCE(SUM(COALESCE(reserved_quantity, 1)), 0) AS reserved_quantity,
                   COUNT(*) AS reservation_count
            FROM Versement_Items
            WHERE inventory_id = %s AND item_status = 'EN_COURS'
        """, (item['inventory_id'],))
        active = cursor.fetchone()
        print("Active EN_COURS for this inventory:", active)
        
        status = inv.get("status")
        reserved_client_id = inv.get("reserved_for_client_id")
        item_type = str(inv.get("item_type") or "WEIGHT").upper()
        remaining_weight = float(inv.get("remaining_weight") or 0.0)
        reservation_count = int(active.get("reservation_count") or 0)
        
        legacy_reserved = status == "Reserved" and not reserved_client_id and reservation_count == 0
        
        print("Condition variables:")
        print(f"status: {status}")
        print(f"reserved_client_id: {reserved_client_id}")
        print(f"item_type: {item_type}")
        print(f"remaining_weight: {remaining_weight}")
        print(f"reservation_count: {reservation_count}")
        print(f"legacy_reserved: {legacy_reserved}")
        
        if item_type != "PIECE":
            cond1 = (status not in ("Available", "Partially_Sold") and not legacy_reserved)
            cond2 = reservation_count > 0
            cond3 = remaining_weight <= 0
            print(f"Condition 1 (status issues): {cond1}")
            print(f"Condition 2 (reservation_count > 0): {cond2}")
            print(f"Condition 3 (remaining_weight <= 0): {cond3}")
            
            if cond1 or cond2 or cond3:
                print("=> WOULD RAISE ERROR: L'article pondéré est déjà réservé ou indisponible.")
            else:
                print("=> WOULD PASS without error.")
                
        # Now let's try the actual revert
        print("Calling revert_versement_item_status...")
        result = vm.revert_versement_item_status(item['id'])
        print("Result:", result)
    else:
        print("No ANNULE item found in Versement_Items.")
