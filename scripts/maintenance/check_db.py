import mysql.connector

# تأكد من وضع نفس بيانات الاتصال الخاصة بك
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'root',  # ضع كلمة المرور إن وجدت
    'database': 'JewelleryDB'
}

try:
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    
    print("=== SupplierTransactions Schema ===")
    cursor.execute("SHOW CREATE TABLE SupplierTransactions")
    print(cursor.fetchone()[1])
    
    print("\n=== MoneyTransactions Schema ===")
    cursor.execute("SHOW CREATE TABLE MoneyTransactions")
    print(cursor.fetchone()[1])
    
    conn.close()
except Exception as e:
    print(f"Error: {e}")