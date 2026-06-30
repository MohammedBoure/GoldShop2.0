import hashlib
from database.base import Database

def reset_password():
    db = Database()
    # تشفير كلمة المرور الجديدة (admin123)
    new_hash = hashlib.sha256("admin123".encode()).hexdigest()
    
    with db.get_db_connection() as conn:
        cursor = conn.cursor()
        # إجبار قاعدة البيانات على تحديث كلمة المرور للأدمن
        cursor.execute("UPDATE Users SET password_hash = %s WHERE username = 'admin'", (new_hash,))
        conn.commit()
        print("✅ تم إعادة تعيين كلمة المرور بنجاح! يمكنك الآن الدخول بـ: admin / admin123")

if __name__ == "__main__":
    reset_password()