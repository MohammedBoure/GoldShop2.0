import mysql.connector
import getpass  # Importing getpass for secure password input

def reset_all_test_sales(db_password):
    try:
        # Connect using the password provided by the user
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password=db_password, 
            database="JewelleryDB" 
        )
        cursor = conn.cursor()
        
        # 1. Clear sales and invoice items
        cursor.execute("DELETE FROM SaleItems")
        cursor.execute("DELETE FROM Sales")
        
        # 2. Clear financial transactions related to sales only
        cursor.execute("DELETE FROM MoneyTransactions WHERE transaction_type = 'SALE'")
        cursor.execute("DELETE FROM ClientWalletTransactions WHERE description LIKE '%Vente%'")
        
        # 3. Return all products in stock to their original state
        cursor.execute("""
            UPDATE Inventory 
            SET status = 'Available', 
                sold_at = NULL, 
                sold_price = NULL, 
                reserved_for_client_id = NULL, 
                remaining_weight = weight, 
                remaining_quantity = quantity
        """)
        
        conn.commit()
        print("✅ Success! All test sales have been deleted.")
        print("✅ Inventory has been successfully reset. You can now make real sales.")
        
    except mysql.connector.Error as err:
        print(f"❌ Database Error: {err}") # Specific error for database issues (like wrong password)
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        if 'conn' in locals() and conn.is_connected():
            conn.close()

if __name__ == "__main__":
    confirm = input("⚠️ Are you sure you want to delete all sales and reset inventory? (oui/non) : ")
    
    if confirm.lower() == 'oui':
        # Prompt for the database password securely before executing
        entered_password = getpass.getpass("🔑 Please enter the database password for 'root': ")
        reset_all_test_sales(entered_password)
    else:
        print("Cancelled.")