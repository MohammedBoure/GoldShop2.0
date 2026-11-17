# database/user_manager.py

import logging
import hashlib
import hmac
import json
from typing import List, Dict, Tuple, Optional

from werkzeug.security import check_password_hash, generate_password_hash


class UserManager:
    """
    مسؤول عن إدارة المستخدمين: تسجيل الدخول، إنشاء الحسابات، وإدارة الصلاحيات الدقيقة.
    """

    def __init__(self, db_instance):
        self.db = db_instance

    def _hash_password(self, password: str) -> str:
        """تشفير كلمة المرور باستخدام PBKDF2-SHA256 مع salt عشوائي."""
        return generate_password_hash(str(password or ""), method="pbkdf2:sha256")

    @staticmethod
    def _legacy_sha256(password: str) -> str:
        return hashlib.sha256(str(password or "").encode()).hexdigest()

    def _verify_password_hash(self, stored_hash: str, password: str) -> tuple[bool, bool]:
        """التحقق من كلمة المرور مع دعم الترقية التلقائية من SHA-256 القديم إلى PBKDF2.
        Returns (is_valid, needs_rehash).
        """
        stored = str(stored_hash or "")
        plain = str(password or "")
        if not stored:
            return False, False
        if stored.startswith(("pbkdf2:", "scrypt:")):
            return check_password_hash(stored, plain), False
        return hmac.compare_digest(stored, self._legacy_sha256(plain)), True

    def authenticate(self, username, password) -> Optional[Dict]:
        """التحقق من صحة بيانات الدخول."""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = """
                    SELECT id, username, full_name, role, is_active, permissions, password_hash
                    FROM Users
                    WHERE username = %s
                """
                cursor.execute(query, (username,))
                user = cursor.fetchone()

                if not user:
                    logging.warning(f"فشل تسجيل الدخول: {username}")
                    return None

                is_valid, needs_rehash = self._verify_password_hash(user.get("password_hash"), password)
                if not is_valid:
                    logging.warning(f"فشل تسجيل الدخول: {username}")
                    return None

                if not user['is_active']:
                    logging.warning(f"محاولة دخول لمستخدم معطل: {username}")
                    return None

                if needs_rehash:
                    try:
                        upgraded_hash = self._hash_password(password)
                        cursor.execute(
                            "UPDATE Users SET password_hash = %s WHERE id = %s",
                            (upgraded_hash, user["id"]),
                        )
                        conn.commit()
                    except Exception as rehash_exc:
                        logging.warning(f"Could not upgrade password hash for {username}: {rehash_exc}")

                user.pop("password_hash", None)
                logging.info(f"تسجيل دخول ناجح: {username}")

                if not user.get('permissions'):
                    user['permissions'] = '[]'
                return user
        except Exception as e:
            logging.error(f"Error during authentication: {e}")
            return None

    def add_user(self, username, password, full_name, role, permissions=None) -> Optional[int]:
        """إضافة مستخدم جديد مع الصلاحيات."""
        try:
            password_hash = self._hash_password(password)
            if permissions is None:
                permissions = '[]'

            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                query = """
                    INSERT INTO Users (username, password_hash, full_name, role, is_active, permissions)
                    VALUES (%s, %s, %s, %s, TRUE, %s)
                """
                cursor.execute(query, (username, password_hash, full_name, role, permissions))
                conn.commit()
                new_id = cursor.lastrowid
                logging.info(f"User {username} created with ID {new_id}")
                return new_id
        except Exception as e:
            logging.error(f"Error adding user: {e}")
            return None

    def update_user(self, user_id, full_name, role, is_active: bool, username=None, password=None, permissions=None) -> bool:
        """تحديث بيانات المستخدم (مرن: يسمح بتحديث اسم المستخدم وكلمة المرور والصلاحيات معاً)"""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                
                # بناء الاستعلام ديناميكياً بناءً على المعطيات المرسلة
                query = "UPDATE Users SET full_name = %s, role = %s, is_active = %s"
                params = [full_name, role, int(is_active)]
                
                if username is not None:
                    query += ", username = %s"
                    params.append(username)
                if password is not None and password.strip() != "":
                    query += ", password_hash = %s"
                    params.append(self._hash_password(password))
                if permissions is not None:
                    query += ", permissions = %s"
                    params.append(permissions)
                    
                query += " WHERE id = %s"
                params.append(user_id)
                
                cursor.execute(query, tuple(params))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Error updating user {user_id}: {e}")
            return False

    def update_permissions(self, user_id, permissions_json: str) -> bool:
        """تحديث صلاحيات المستخدم فقط."""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                query = "UPDATE Users SET permissions = %s WHERE id = %s"
                cursor.execute(query, (permissions_json, user_id))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Error updating permissions for user {user_id}: {e}")
            return False

    def change_password(self, user_id, new_password) -> bool:
        """تغيير كلمة المرور"""
        try:
            new_hash = self._hash_password(new_password)
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE Users SET password_hash = %s WHERE id = %s", (new_hash, user_id))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Error changing password for user {user_id}: {e}")
            return False

    def delete_user(self, user_id) -> bool:
        """حذف مستخدم"""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM Users WHERE id = %s", (user_id,))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Error deleting user {user_id}: {e}")
            return False

    def get_all_users(self) -> List[Dict]:
        """جلب كل المستخدمين مع صلاحياتهم"""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute("SELECT id, username, full_name, role, is_active, permissions FROM Users ORDER BY id")
                users = cursor.fetchall()
                for u in users:
                    if not u.get('permissions'):
                        u['permissions'] = '[]'
                return users
        except Exception as e:
            logging.error(f"Error fetching users: {e}")
            return []

    def get_user_by_id(self, user_id) -> Optional[Dict]:
        """جلب مستخدم محدد"""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute("SELECT * FROM Users WHERE id = %s", (user_id,))
                user = cursor.fetchone()
                if user and not user.get('permissions'):
                     user['permissions'] = '[]'
                return user
        except Exception as e:
            print(f"Error fetching user: {e}")
            return None

    def verify_admin_password(self, password_text):
        """التحقق من كلمة مرور المسؤول (للعمليات الحساسة)"""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = """
                    SELECT id, password_hash FROM Users
                    WHERE role = 'Admin' AND is_active = 1
                """
                cursor.execute(query)
                for row in cursor.fetchall():
                    is_valid, needs_rehash = self._verify_password_hash(row.get("password_hash"), password_text)
                    if is_valid:
                        if needs_rehash:
                            try:
                                cursor.execute(
                                    "UPDATE Users SET password_hash = %s WHERE id = %s",
                                    (self._hash_password(password_text), row["id"]),
                                )
                                conn.commit()
                            except Exception as rehash_exc:
                                logging.warning(f"Could not upgrade admin password hash: {rehash_exc}")
                        return True
                return False
        except Exception as exc:
            logging.error(f"Error verifying admin password: {exc}")
            return False
    
    def get_user_by_username(self, username):
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute("SELECT * FROM Users WHERE username = %s", (username,))
                return cursor.fetchone()
        except Exception:
            return None

    def get_user_permissions(self, user_dict) -> list:
        """تأخذ قاموس بيانات المستخدم وترجع قائمة الصلاحيات كـ list."""
        if not user_dict:
            return []
        perms = user_dict.get('permissions', '[]')
        try:
            if isinstance(perms, str):
                return json.loads(perms)
            if isinstance(perms, list):
                return perms
        except Exception as e:
            logging.error(f"Error parsing user permissions: {e}")
        return []