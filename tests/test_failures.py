from database.base import Database
from database.versement import VersementManager, normalize_reserved_quantity

db = Database()
vm = VersementManager(db)

failures = []

with db.get_db_connection() as conn:
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, inventory_id FROM Versement_Items WHERE item_status = 'ANNULE' ORDER BY id DESC LIMIT 50")
    items = cursor.fetchall()
    
    for item in items:
        inv_id = item['inventory_id']
        cursor.execute("SELECT status, item_type, remaining_weight, reserved_for_client_id FROM Inventory WHERE id = %s", (inv_id,))
        inv = cursor.fetchone()
        if not inv:
            continue
            
        cursor.execute("""
            SELECT COALESCE(SUM(COALESCE(reserved_quantity, 1)), 0) AS reserved_quantity,
                   COUNT(*) AS reservation_count
            FROM Versement_Items
            WHERE inventory_id = %s AND item_status = 'EN_COURS'
        """, (inv_id,))
        active = cursor.fetchone()
        
        status = inv.get("status")
        item_type = str(inv.get("item_type") or "WEIGHT").upper()
        remaining_weight = float(inv.get("remaining_weight") or 0.0)
        reservation_count = int(active.get("reservation_count") or 0)
        reserved_client_id = inv.get("reserved_for_client_id")
        
        legacy_reserved = status == "Reserved" and not reserved_client_id and reservation_count == 0
        
        if item_type != "PIECE":
            if (status not in ("Available", "Partially_Sold") and not legacy_reserved) or reservation_count > 0 or remaining_weight <= 0:
                failures.append({
                    "item_id": item['id'],
                    "inv_id": inv_id,
                    "reason": "WEIGHT rules failed",
                    "status": status,
                    "reservation_count": reservation_count,
                    "remaining_weight": remaining_weight,
                    "legacy_reserved": legacy_reserved
                })
        else:
            remaining = int(inv.get("remaining_quantity") or 0)
            reserved = int(active.get("reserved_quantity") or 0)
            available = max(0, remaining - reserved)
            legacy_reserved_piece = status == "Reserved" and not reserved_client_id
            
            if status not in ("Available", "Partially_Sold") and not legacy_reserved_piece:
                failures.append({"item_id": item['id'], "inv_id": inv_id, "reason": "PIECE status not available"})
            elif 1 > available: # requested = 1
                failures.append({"item_id": item['id'], "inv_id": inv_id, "reason": "PIECE available <= 0", "available": available})

print(f"Out of {len(items)} ANNULE items checked, {len(failures)} would FAIL to restore.")
for f in failures[:10]:
    print(f)
