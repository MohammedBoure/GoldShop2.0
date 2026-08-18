from database.base import Database
from database.versement import VersementManager

db = Database()
vm = VersementManager(db)

if __name__ == '__main__':
    with db.get_db_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        
        # Find an item that is NOT in any versement
        cursor.execute("""
            SELECT id FROM Inventory 
            WHERE item_type = 'WEIGHT' AND remaining_weight > 0 AND status = 'Available'
            AND NOT EXISTS (SELECT 1 FROM Versement_Items WHERE inventory_id = Inventory.id)
            LIMIT 1
        """)
        inv = cursor.fetchone()
        if not inv:
            print("No suitable inventory item found.")
            exit()
            
        inv_id = inv['id']
        print("Found clean Inventory ID:", inv_id)
        
        # Create a versement
        v_data = vm.create_versement(
            client_id=1, journee_id=1, type_versement='TEST',
            items_list=[{"id": inv_id, "versement_quantity": 1}],
            montant_da=0, or_casse_g=0, prix_gramme_jour_da=1000
        )
        if not v_data or 'versement_id' not in v_data:
            print("Failed to create versement")
            exit()
            
        v_id = v_data['versement_id']
        print("Created Versement ID:", v_id)
        
        # Get the versement item
        cursor.execute("SELECT id FROM Versement_Items WHERE versement_id = %s", (v_id,))
        item = cursor.fetchone()
        item_id = item['id']
        print("Created Versement Item ID:", item_id)
        
        # Cancel it
        res_cancel = vm.cancel_versement_item(item_id)
        print("Cancelled?", res_cancel)
        
        # Restore it
        res_restore = vm.revert_versement_item_status(item_id)
        print("Restored?", res_restore)
        
        # Cleanup
        cursor.execute("DELETE FROM Versement_Items WHERE versement_id = %s", (v_id,))
        cursor.execute("DELETE FROM Versement_Payments WHERE versement_id = %s", (v_id,))
        cursor.execute("DELETE FROM Versements WHERE id = %s", (v_id,))
        conn.commit()
        print("Cleanup done.")
