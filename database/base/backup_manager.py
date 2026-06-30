"""
backup_manager.py
-----------------
إدارة النسخ الاحتياطية والاستعادة وأرشفة البيانات القديمة.
يعتمد على DatabaseConnection للوصول إلى Pool وEngine.
"""

import os
import shutil
import logging
import zipfile
from datetime import date, timedelta

import sqlalchemy
from sqlalchemy import text

from .config import TABLE_IMPORT_ORDER, ARCHIVE_VIEW_FLAG_FILE


def _load_pandas():
    import pandas as pd
    return pd


def _load_numpy():
    import numpy as np
    return np


class BackupManager:
    """
    يُقدّم عمليات:
      - backup_database_csv   → تصدير كامل إلى ZIP/CSV
      - restore_database_csv  → استعادة من ZIP/CSV
      - export_to_excel       → تصدير إلى Excel
      - restore_from_excel    → استعادة من Excel
      - export_and_purge_tables → أرشفة وحذف السجلات القديمة
      - restore_table_from_file → استعادة جدول واحد
    """

    def __init__(self, db_connection):
        """
        Parameters
        ----------
        db_connection : DatabaseConnection
            الكائن الذي يمتلك get_db_connection() وget_raw_connection() وengine.
        """
        self._db = db_connection

    # ─── CSV Backup ───────────────────────────────────────────────────────────
    def backup_database_csv(self, output_zip_path: str):
        temp_dir = os.path.abspath('temp_backup_csv')
        conn_sa = None
        try:
            pd = _load_pandas()
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            os.makedirs(temp_dir, exist_ok=True)

            try:
                conn_sa = self._db.engine.connect()
            except Exception as e:
                logging.error(f"❌ SQLAlchemy Connection Failed: {e}")
                return False, str(e)

            inspector = sqlalchemy.inspect(self._db.engine)
            all_db_tables = inspector.get_table_names()

            tables_to_export = [t for t in TABLE_IMPORT_ORDER if t in all_db_tables]
            for t in all_db_tables:
                if t not in tables_to_export:
                    tables_to_export.append(t)

            exported_count = 0
            for table_name in tables_to_export:
                csv_path = os.path.join(temp_dir, f"{table_name}.csv")
                try:
                    df = pd.read_sql_query(text(f"SELECT * FROM `{table_name}`"), conn_sa)
                    for col in df.select_dtypes(include=['datetime64[ns]', 'datetime']).columns:
                        df[col] = df[col].dt.strftime('%Y-%m-%d %H:%M:%S').replace('NaT', None)
                    df.to_csv(csv_path, index=False, encoding='utf-8', na_rep='<NULL>')
                    if not df.empty:
                        exported_count += 1
                except Exception as e:
                    logging.warning(f"⚠️ Export error {table_name}: {e}")

            with zipfile.ZipFile(output_zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, _, files in os.walk(temp_dir):
                    for file in files:
                        zipf.write(os.path.join(root, file), file)
            return True, f"Backup created: {os.path.basename(output_zip_path)}"

        except Exception as e:
            return False, str(e)
        finally:
            if conn_sa:
                conn_sa.close()
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)

    # ─── CSV Restore ──────────────────────────────────────────────────────────
    def restore_database_csv(self, input_zip_path: str):
        temp_dir = 'temp_restore_csv'
        conn = None
        try:
            pd = _load_pandas()
            np = _load_numpy()
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            os.makedirs(temp_dir)

            with zipfile.ZipFile(input_zip_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)

            conn = self._db.get_raw_connection()
            conn.start_transaction()
            cursor = conn.cursor()
            cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")

            backup_files = [f for f in os.listdir(temp_dir) if f.endswith('.csv')]
            tables_to_restore = []
            for file_name in backup_files:
                table_name = file_name.replace('.csv', '')
                csv_path = os.path.join(temp_dir, file_name)
                try:
                    df_check = pd.read_csv(csv_path, nrows=1)
                    if not df_check.empty:
                        tables_to_restore.append(table_name)
                except Exception:
                    continue

            if not tables_to_restore:
                cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")
                return False, "Backup file is empty."

            cursor.execute("SHOW TABLES")
            existing_tables = [row[0] for row in cursor.fetchall()]

            for table_to_clean in tables_to_restore:
                match = next((t for t in existing_tables if t.lower() == table_to_clean.lower()), None)
                if match:
                    try:
                        cursor.execute(f"DELETE FROM `{match}`")
                    except Exception as e:
                        logging.warning(f"Failed to clear {match}: {e}")

            ordered = [t for t in TABLE_IMPORT_ORDER if t in tables_to_restore]
            remaining = [t for t in tables_to_restore if t not in TABLE_IMPORT_ORDER]
            final_list = ordered + remaining

            for table_name in final_list:
                csv_file = os.path.join(temp_dir, f"{table_name}.csv")
                try:
                    df = pd.read_csv(csv_file, na_values=['<NULL>'], keep_default_na=True)
                    df.columns = df.columns.astype(str)
                    df = df.loc[:, ~df.columns.str.contains('^Unnamed', na=False)]
                    df = df.where(pd.notnull(df), None)

                    if df.empty:
                        continue

                    cursor.execute(f"SHOW COLUMNS FROM `{table_name}`")
                    db_cols = {row[0] for row in cursor.fetchall()}
                    generated_cols = set()
                    for col in db_cols:
                        try:
                            cursor.execute(
                                f"SELECT EXTRA FROM information_schema.COLUMNS "
                                f"WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s AND COLUMN_NAME=%s",
                                (table_name, col)
                            )
                            row = cursor.fetchone()
                            if row and 'GENERATED' in str(row[0]).upper():
                                generated_cols.add(col)
                        except Exception:
                            pass

                    valid_cols = [c for c in df.columns if c in db_cols and c not in generated_cols]
                    if not valid_cols:
                        continue
                    df = df[valid_cols]

                    cleaned_data = []
                    for row_tuple in df.itertuples(index=False, name=None):
                        cleaned_row = tuple(
                            None if (v is None or (isinstance(v, float) and np.isnan(v)))
                            else bool(v) if isinstance(v, (bool, np.bool_))
                            else int(v) if isinstance(v, (np.integer,))
                            else float(v) if isinstance(v, (np.floating,))
                            else str(v) if not isinstance(v, (int, float, str, type(None)))
                            else v
                            for v in row_tuple
                        )
                        cleaned_data.append(cleaned_row)

                    if cleaned_data:
                        cols = ",".join([f"`{c}`" for c in valid_cols])
                        placeholders = ",".join(["%s"] * len(valid_cols))
                        sql = f"INSERT INTO `{table_name}` ({cols}) VALUES ({placeholders})"
                        cursor.executemany(sql, cleaned_data)

                except Exception as e:
                    logging.error(f"❌ Error restoring {table_name}: {e}")

            cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")
            conn.commit()
            return True, "CSV Restore Success."

        except Exception as e:
            if conn:
                conn.rollback()
            return False, f"Restore failed: {str(e)}"
        finally:
            if conn and conn.is_connected():
                conn.close()
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)

    # ─── Excel Export ─────────────────────────────────────────────────────────
    def export_to_excel(self, output_zip_path: str):
        temp_dir = 'temp_backup_excel'
        try:
            pd = _load_pandas()
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            os.makedirs(temp_dir)

            with self._db.engine.connect() as conn_sa:
                inspector = sqlalchemy.inspect(self._db.engine)
                all_tables = inspector.get_table_names()

                for table_name in all_tables:
                    try:
                        df = pd.read_sql_query(text(f"SELECT * FROM `{table_name}`"), conn_sa)
                        excel_path = os.path.join(temp_dir, f"{table_name}.xlsx")
                        df.to_excel(excel_path, index=False)
                    except Exception as e:
                        logging.warning(f"⚠️ Export error {table_name}: {e}")

            with zipfile.ZipFile(output_zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, _, files in os.walk(temp_dir):
                    for file in files:
                        zipf.write(os.path.join(root, file), file)
            return True, f"Excel backup created: {os.path.basename(output_zip_path)}"

        except Exception as e:
            return False, str(e)
        finally:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)

    # ─── Excel Restore ────────────────────────────────────────────────────────
    def restore_from_excel(self, input_zip_path: str):
        temp_dir = 'temp_restore_excel'
        conn = None
        try:
            pd = _load_pandas()
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            os.makedirs(temp_dir)

            with zipfile.ZipFile(input_zip_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)

            conn = self._db.get_raw_connection()
            conn.start_transaction()
            cursor = conn.cursor()
            cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")

            excel_files = [f for f in os.listdir(temp_dir) if f.endswith('.xlsx')]
            tables_to_restore = [f.replace('.xlsx', '') for f in excel_files]

            cursor.execute("SHOW TABLES")
            existing_tables = [row[0] for row in cursor.fetchall()]
            for table_name in tables_to_restore:
                match = next((t for t in existing_tables if t.lower() == table_name.lower()), None)
                if match:
                    try:
                        cursor.execute(f"DELETE FROM `{match}`")
                    except Exception as e:
                        logging.warning(f"Failed to clear {match}: {e}")

            ordered = [t for t in TABLE_IMPORT_ORDER if t in tables_to_restore]
            remaining = [t for t in tables_to_restore if t not in TABLE_IMPORT_ORDER]

            for table_name in ordered + remaining:
                excel_file = os.path.join(temp_dir, f"{table_name}.xlsx")
                try:
                    df = pd.read_excel(excel_file)
                    df.columns = df.columns.astype(str)
                    df = df.loc[:, ~df.columns.str.contains('^Unnamed', na=False)]
                    df = df.where(pd.notnull(df), None)

                    if df.empty:
                        continue

                    cols = ",".join([f"`{c}`" for c in df.columns])
                    placeholders = ",".join(["%s"] * len(df.columns))
                    sql = f"INSERT INTO `{table_name}` ({cols}) VALUES ({placeholders})"
                    cleaned_data = [tuple(x) for x in df.to_numpy()]

                    if cleaned_data:
                        cursor.executemany(sql, cleaned_data)

                except Exception as e:
                    logging.error(f"❌ Error restoring {table_name}: {e}")

            cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")
            conn.commit()
            return True, "Excel Restore Success."

        except Exception as e:
            if conn:
                conn.rollback()
            return False, f"Restore failed: {str(e)}"
        finally:
            if conn and conn.is_connected():
                conn.close()
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)

    # ─── Archive Old Logs ─────────────────────────────────────────────────────
    def export_and_purge_tables(self, output_zip_path: str, days_to_keep: int = 365):
        """يُصدّر السجلات القديمة ويحذفها من قاعدة البيانات."""
        tables_to_archive = ['SupplierTransactions', 'MoneyTransactions']
        cutoff_date = date.today() - timedelta(days=days_to_keep)
        temp_dir = 'temp_archive_logs'

        try:
            pd = _load_pandas()
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            os.makedirs(temp_dir)

            has_data = False
            with self._db.engine.connect() as conn_sa:
                for table in tables_to_archive:
                    query = text(f"SELECT * FROM {table} WHERE transaction_date < :cutoff")
                    df = pd.read_sql(query, conn_sa, params={"cutoff": cutoff_date})
                    if not df.empty:
                        has_data = True
                        df.to_csv(os.path.join(temp_dir, f"{table}.csv"), index=False, encoding='utf-8')

            if has_data:
                with self._db.get_db_connection() as del_conn:
                    del_cursor = del_conn.cursor()
                    for table in tables_to_archive:
                        del_cursor.execute(
                            f"DELETE FROM {table} WHERE transaction_date < %s",
                            (cutoff_date,)
                        )
                    del_conn.commit()

                with zipfile.ZipFile(output_zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for root, _, files in os.walk(temp_dir):
                        for file in files:
                            zipf.write(os.path.join(root, file), file)
                return True, f"Archived old logs to:\n{output_zip_path}"
            else:
                return False, "No old records found to archive."

        except Exception as e:
            return False, str(e)
        finally:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)

    # ─── Single Table Restore ─────────────────────────────────────────────────
    def restore_table_from_file(self, table_name: str, file_path: str) -> bool:
        try:
            pd = _load_pandas()
            if file_path.endswith('.csv'):
                df = pd.read_csv(file_path)
            else:
                df = pd.read_excel(file_path)

            df.columns = df.columns.astype(str)
            df = df.loc[:, ~df.columns.str.contains('^Unnamed', na=False)]
            df = df.where(pd.notnull(df), None)

            with self._db.engine.begin() as conn_sa:
                df.to_sql(name=table_name, con=conn_sa, if_exists='append', index=False)
            return True
        except Exception as e:
            logging.error(f"restore_table_from_file error: {e}")
            return False
        
    def create_auto_backup(self, base_backup_path: str, password: str = ""):
        """
        يُنشئ نسخة احتياطية في مجلد Auto_Backups.
        يقوم بحذف النسخ القديمة لترك أحدث نسخة فقط، ويشفرها بكلمة مرور إذا طُلب ذلك.
        """
        import datetime
        try:
            import pyzipper
            has_pyzipper = True
        except ImportError:
            has_pyzipper = False
            logging.warning("⚠️ Module 'pyzipper' non installé. Le mot de passe ne sera pas appliqué. (pip install pyzipper)")

        auto_backup_dir = os.path.join(base_backup_path, "Auto_Backups")
        
        try:
            # 1. إنشاء المجلد إذا لم يكن موجوداً
            os.makedirs(auto_backup_dir, exist_ok=True)

            # 2. حذف الملفات القديمة (نحتفظ بملف واحد فقط لتوفير المساحة)
            for file_name in os.listdir(auto_backup_dir):
                if file_name.endswith('.zip'):
                    file_path = os.path.join(auto_backup_dir, file_name)
                    try:
                        os.remove(file_path)
                    except Exception as e:
                        logging.warning(f"⚠️ Impossible de supprimer l'ancienne sauvegarde: {e}")

            # 3. تحضير اسم الملف الجديد
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            final_zip_path = os.path.join(auto_backup_dir, f"AutoBackup_{timestamp}.zip")
            
            # 4. تصدير الجداول إلى مجلد مؤقت (نستخدم نفس منطق CSV)
            temp_dir = os.path.abspath('temp_auto_backup_csv')
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            os.makedirs(temp_dir)
            pd = _load_pandas()

            with self._db.engine.connect() as conn_sa:
                inspector = sqlalchemy.inspect(self._db.engine)
                all_tables = inspector.get_table_names()
                
                for table_name in all_tables:
                    try:
                        df = pd.read_sql_query(text(f"SELECT * FROM `{table_name}`"), conn_sa)
                        for col in df.select_dtypes(include=['datetime64[ns]', 'datetime']).columns:
                            df[col] = df[col].dt.strftime('%Y-%m-%d %H:%M:%S').replace('NaT', None)
                        df.to_csv(os.path.join(temp_dir, f"{table_name}.csv"), index=False, encoding='utf-8', na_rep='<NULL>')
                    except Exception:
                        pass

            # 5. ضغط الملفات وتشفيرها إذا لزم الأمر
            if has_pyzipper and password:
                with pyzipper.AESZipFile(final_zip_path, 'w', compression=pyzipper.ZIP_DEFLATED, encryption=pyzipper.WZ_AES) as zipf:
                    zipf.setpassword(password.encode('utf-8'))
                    for root, _, files in os.walk(temp_dir):
                        for file in files:
                            zipf.write(os.path.join(root, file), file)
            else:
                # ضغط عادي بدون كلمة مرور
                import zipfile
                with zipfile.ZipFile(final_zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for root, _, files in os.walk(temp_dir):
                        for file in files:
                            zipf.write(os.path.join(root, file), file)

            logging.info(f"✅ Sauvegarde Automatique réussie : {final_zip_path}")
            return True

        except Exception as e:
            logging.error(f"❌ Échec de la Sauvegarde Automatique : {e}")
            return False
        finally:
            if 'temp_dir' in locals() and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
    # ─── Multi-Path Backup (Manual & Auto) ──────────────────────────────────
    def create_multi_backup(self, target_paths: list, password: str = "", is_auto: bool = True):
        """
        يقوم بتوليد النسخة الاحتياطية ونسخها إلى جميع المسارات المحددة في القائمة.
        إذا كان is_auto=True: يضعها في مجلد Auto_Backups ويحذف النسخ القديمة.
        إذا كان is_auto=False: يضعها مباشرة في المسار المحدد بدون حذف القديم.
        """
        import datetime
        import shutil
        import os
        
        if not target_paths:
            return False, "Aucun chemin de sauvegarde spécifié."
            
        try:
            import pyzipper
            has_pyzipper = True
        except ImportError:
            has_pyzipper = False
            logging.warning("⚠️ Module 'pyzipper' non installé. Le mot de passe ne sera pas appliqué.")

        # 1. تحضير اسم الملف الأساسي
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        prefix = "AutoBackup" if is_auto else "ManualBackup"
        zip_filename = f"{prefix}_{timestamp}.zip"
        
        master_zip_path = os.path.abspath(f'temp_{zip_filename}')
        temp_csv_dir = os.path.abspath('temp_export_csv')

        try:
            # 2. توليد ملفات CSV
            if os.path.exists(temp_csv_dir): shutil.rmtree(temp_csv_dir)
            os.makedirs(temp_csv_dir)

            with self._db.engine.connect() as conn_sa:
                import sqlalchemy
                from sqlalchemy import text
                import pandas as pd
                inspector = sqlalchemy.inspect(self._db.engine)
                for table_name in inspector.get_table_names():
                    try:
                        df = pd.read_sql_query(text(f"SELECT * FROM `{table_name}`"), conn_sa)
                        df.to_csv(os.path.join(temp_csv_dir, f"{table_name}.csv"), index=False, encoding='utf-8')
                    except: pass

            # 3. ضغط وتشفير الملف الماستر
            if has_pyzipper and password:
                with pyzipper.AESZipFile(master_zip_path, 'w', compression=pyzipper.ZIP_DEFLATED, encryption=pyzipper.WZ_AES) as zipf:
                    zipf.setpassword(password.encode('utf-8'))
                    for root, _, files in os.walk(temp_csv_dir):
                        for file in files:
                            zipf.write(os.path.join(root, file), file)
            else:
                import zipfile
                with zipfile.ZipFile(master_zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for root, _, files in os.walk(temp_csv_dir):
                        for file in files:
                            zipf.write(os.path.join(root, file), file)

            # 4. توزيع الملف الماستر على جميع المسارات المحددة
            success_count = 0
            for base_path in target_paths:
                try:
                    # 🟢 الحل الذكي لمشكلة الصلاحيات في قرص C
                    # إذا كان المسار هو C:\ أو C:/ بالضبط، نضيف مجلد فرعي
                    if os.path.abspath(base_path) == os.path.abspath("C:\\"):
                        base_path = os.path.join("C:\\", "GoldShop_Backups")
                        logging.info(f"⚠️ Redirection automatique vers {base_path} pour éviter l'erreur de permission.")

                    # تحديد المجلد الوجهة
                    dest_dir = os.path.join(base_path, "Auto_Backups") if is_auto else base_path
                    os.makedirs(dest_dir, exist_ok=True)
                    
                    # حذف النسخ التلقائية القديمة
                    if is_auto:
                        for file_name in os.listdir(dest_dir):
                            if file_name.endswith('.zip') and file_name.startswith('AutoBackup'):
                                try: os.remove(os.path.join(dest_dir, file_name))
                                except: pass
                                
                    # النسخ النهائي
                    final_path = os.path.join(dest_dir, zip_filename)
                    shutil.copy2(master_zip_path, final_path)
                    success_count += 1
                    logging.info(f"✅ Sauvegarde copiée vers : {final_path}")
                except Exception as e:
                    logging.error(f"❌ Impossible de copier vers {base_path}: {e}")

            if success_count > 0:
                return True, f"Succès ({success_count}/{len(target_paths)})"
            return False, "Toutes les copies ont échoué."

        except Exception as e:
            logging.error(f"❌ Backup Error: {e}")
            return False, str(e)
        finally:
            if os.path.exists(temp_csv_dir): shutil.rmtree(temp_csv_dir)
            if os.path.exists(master_zip_path): os.remove(master_zip_path)
    # ─── Convenience Aliases ──────────────────────────────────────────────────
    def export_all_tables_to_csv_zip(self, output_zip_path='backup_csv.zip'):
        return self.backup_database_csv(output_zip_path)

    def restore_from_archive_zip_destructive(self, input_zip_path, tables_to_restore=None):
        return self.restore_database_csv(input_zip_path)
