from database.base import Database
import logging

def reset_session_tables():
    print("⏳ جاري الاتصال بقاعدة البيانات لحذف الجداول القديمة...")
    
    try:
        db = Database()
        conn = db.get_raw_connection()
        cursor = conn.cursor()
        
        # نوقف التحقق من المفاتيح الخارجية مؤقتاً لتجنب أخطاء الحذف
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
        
        # 1. حذف الجداول التي تسبب المشكلة
        tables_to_drop = [
            "SessionAuditDetails",  # يجب حذفه
            "SessionReconciliations" # يجب حذفه
        ]
        
        for table in tables_to_drop:
            cursor.execute(f"DROP TABLE IF EXISTS {table};")
            print(f"✅ تم حذف الجدول القديم: {table}")
            
        # إعادة تفعيل التحقق
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")
        conn.commit()
        conn.close()
        
        print("\n🎉 تمت العملية بنجاح!")
        print("👉 الآن قم بتشغيل برنامجك الرئيسي (app.py أو main.py).")
        print("   سيقوم البرنامج بإنشاء الجداول الجديدة تلقائياً مع عمود 'difference'.")
        
    except Exception as e:
        print(f"❌ حدث خطأ أثناء الحذف: {e}")

if __name__ == "__main__":
    reset_session_tables()