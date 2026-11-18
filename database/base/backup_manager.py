"""
backup_manager.py
-----------------
إدارة النسخ الاحتياطية والاستعادة وأرشفة البيانات القديمة.
يعتمد على DatabaseConnection للوصول إلى Pool وEngine.
"""

import os
import re
import shutil
import logging
import tempfile
import zipfile
from datetime import date, timedelta
from pathlib import Path

import sqlalchemy
from sqlalchemy import text

from .config import TABLE_IMPORT_ORDER


_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9_]+$")


def _load_pandas():
    import pandas as pd
    return pd


def _load_numpy():
    import numpy as np
    return np


def validate_sql_identifier(name: str, kind: str = "identifier") -> str:
    """التحقق الصارم من صلاحية اسم الجدول أو العمود لمنع حقن SQL."""
    text_name = str(name or "").strip()
    if not text_name or not _IDENTIFIER_RE.fullmatch(text_name):
        raise ValueError(f"Invalid {kind} name: {name!r}")
    return text_name


def safe_extract_zip(input_zip_path: str, dest_dir: str, password: str | None = None) -> None:
    """فك ضغط أرشيف ZIP بأمان مع منع هجمات اجتياز المسار (Zip Slip)."""
    base_dir = Path(dest_dir).resolve()

    def _extract_archive(archive):
        if password:
            pwd = password.encode("utf-8") if isinstance(password, str) else password
            archive.setpassword(pwd)
        for info in archive.infolist():
            member_name = info.filename
            if not member_name:
                continue
            # Reject symbolic links inside ZIP archives
            if (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError(f"Unsafe symlink entry in archive: {member_name!r}")
            target_path = (base_dir / member_name).resolve()
            if not target_path.is_relative_to(base_dir):
                raise ValueError(f"Unsafe archive entry path (Zip Slip): {member_name!r}")
            if info.is_dir():
                target_path.mkdir(parents=True, exist_ok=True)
                continue
            target_path.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info, "r") as src, open(target_path, "wb") as dst:
                shutil.copyfileobj(src, dst)

    try:
        with zipfile.ZipFile(input_zip_path, "r") as zip_ref:
            _extract_archive(zip_ref)
    except (RuntimeError, NotImplementedError):
        import pyzipper

        with pyzipper.AESZipFile(input_zip_path, "r") as zip_ref:
            _extract_archive(zip_ref)


def write_zip_from_dir(source_dir: str, output_zip_path: str, password: str = "") -> None:
    """ضغط محتويات مجلد إلى أرشيف ZIP، مع إلزام pyzipper عند تفعيل التشفير."""
    if password:
        try:
            import pyzipper
        except ImportError as exc:
            raise RuntimeError(
                "Le module 'pyzipper' est requis pour créer une sauvegarde chiffrée."
            ) from exc

        with pyzipper.AESZipFile(
            output_zip_path,
            "w",
            compression=pyzipper.ZIP_DEFLATED,
            encryption=pyzipper.WZ_AES,
        ) as zipf:
            zipf.setpassword(password.encode("utf-8"))
            for root, _, files in os.walk(source_dir):
                for file in files:
                    full_path = os.path.join(root, file)
                    arcname = os.path.relpath(full_path, source_dir)
                    zipf.write(full_path, arcname)
        return

    with zipfile.ZipFile(output_zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(source_dir):
            for file in files:
                full_path = os.path.join(root, file)
                arcname = os.path.relpath(full_path, source_dir)
                zipf.write(full_path, arcname)


def _get_table_columns_info(cursor, canonical_table: str) -> tuple[set[str], set[str]]:
    """جلب أسماء الأعمدة الفعلية والأعمدة المولّدة للجدول من قاعدة البيانات."""
    validate_sql_identifier(canonical_table, "table")
    cursor.execute(f"SHOW COLUMNS FROM `{canonical_table}`")
    db_cols = {row[0] for row in cursor.fetchall()}

    cursor.execute(
        "SELECT COLUMN_NAME, EXTRA FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s",
        (canonical_table,),
    )
    generated_cols = {
        row[0]
        for row in cursor.fetchall()
        if row and len(row) >= 2 and "GENERATED" in str(row[1]).upper()
    }
    return db_cols, generated_cols


def _validate_and_filter_columns(
    df_columns,
    db_cols: set[str],
    generated_cols: set[str],
    table_name: str,
) -> list[str]:
    """التحقق من أسماء الأعمدة ضد مخطط الجدول واستبعاد الأعمدة المولّدة."""
    unknown_cols = []
    valid_cols = []
    for raw_col in df_columns:
        col = validate_sql_identifier(str(raw_col), "column")
        if col not in db_cols:
            unknown_cols.append(col)
        elif col not in generated_cols:
            valid_cols.append(col)

    if unknown_cols:
        raise ValueError(
            f"Unknown columns for table '{table_name}': {', '.join(unknown_cols)}"
        )
    return valid_cols


def _clean_dataframe_rows(df, np_module) -> list[tuple]:
    """تحويل صفوف DataFrame إلى tuples متوافقة مع mysql-connector."""
    cleaned_data = []
    for row_tuple in df.itertuples(index=False, name=None):
        cleaned_row = tuple(
            None
            if (v is None or (isinstance(v, float) and np_module.isnan(v)))
            else bool(v)
            if isinstance(v, (bool, np_module.bool_))
            else int(v)
            if isinstance(v, (np_module.integer,))
            else float(v)
            if isinstance(v, (np_module.floating,))
            else str(v)
            if not isinstance(v, (int, float, str, type(None)))
            else v
            for v in row_tuple
        )
        cleaned_data.append(cleaned_row)
    return cleaned_data


class BackupManager:
    """
    يُقدّم عمليات:
      - backup_database_csv   → تصدير كامل إلى ZIP/CSV
      - restore_database_csv  → استعادة ذرية من ZIP/CSV
      - export_to_excel       → تصدير إلى Excel
      - restore_from_excel    → استعادة ذرية من Excel
      - export_and_purge_tables → أرشفة وحذف السجلات القديمة
      - restore_table_from_file → استعادة جدول واحد
    """

    def __init__(self, db_connection):
        """
        Parameters
        ----------
        db_connection : ConnectionManager / DatabaseConnection
            الكائن الذي يمتلك get_db_connection() وget_raw_connection() وengine.
        """
        self._db = db_connection

    def _export_tables_to_dir(self, temp_dir: str, fmt: str = "csv", format_datetimes: bool = True) -> list[str]:
        """تصدير جميع جداول قاعدة البيانات إلى ملفات CSV أو Excel في مجلد مؤقت."""
        if self._db.engine is None:
            raise RuntimeError("SQLAlchemy engine is not initialized.")

        pd = _load_pandas()
        failed_tables = []
        exported_tables = []

        with self._db.engine.connect() as conn_sa:
            inspector = sqlalchemy.inspect(self._db.engine)
            all_db_tables = [validate_sql_identifier(t, "table") for t in inspector.get_table_names()]

            ordered = [t for t in TABLE_IMPORT_ORDER if t in all_db_tables]
            for t in all_db_tables:
                if t not in ordered:
                    ordered.append(t)

            for table_name in ordered:
                try:
                    df = pd.read_sql_query(text(f"SELECT * FROM `{table_name}`"), conn_sa)
                    if fmt == "csv":
                        if format_datetimes:
                            for col in df.select_dtypes(include=["datetime64[ns]", "datetime"]).columns:
                                df[col] = df[col].dt.strftime("%Y-%m-%d %H:%M:%S").replace("NaT", None)
                        df.to_csv(
                            os.path.join(temp_dir, f"{table_name}.csv"),
                            index=False,
                            encoding="utf-8",
                            na_rep="<NULL>",
                        )
                    elif fmt == "xlsx":
                        df.to_excel(os.path.join(temp_dir, f"{table_name}.xlsx"), index=False)
                    else:
                        raise ValueError(f"Unsupported export format: {fmt}")
                    exported_tables.append(table_name)
                except Exception as exc:
                    failed_tables.append(f"{table_name}: {exc}")
                    logging.error(f"❌ Export error {table_name}: {exc}")

        if failed_tables:
            raise RuntimeError(
                f"Export failed for {len(failed_tables)} table(s): {'; '.join(failed_tables)}"
            )
        return exported_tables

    def _restore_from_archive(
        self,
        input_zip_path: str,
        extension: str,
        dataframe_loader,
        password: str | None = None,
    ) -> tuple[bool, str]:
        """استعادة ذرية لقاعدة البيانات من أرشيف ZIP مع التراجع الكامل عند أي خطأ."""
        temp_dir = tempfile.mkdtemp(prefix=f"goldshop_restore_{extension.lstrip('.')}_")
        conn = None
        cursor = None
        try:
            pd = _load_pandas()
            np = _load_numpy()

            safe_extract_zip(input_zip_path, temp_dir, password=password)

            archive_files: dict[str, str] = {}
            for file_name in sorted(os.listdir(temp_dir)):
                if not file_name.lower().endswith(extension):
                    continue
                raw_table = file_name[: -len(extension)]
                validate_sql_identifier(raw_table, "table")
                archive_files[raw_table] = os.path.join(temp_dir, file_name)

            if not archive_files:
                return False, "Backup file is empty."

            # قراءة وتجهيز البيانات قبل فتح معاملة الحذف/الإدراج
            prepared_frames: dict[str, object] = {}
            for raw_table, file_path in archive_files.items():
                df = dataframe_loader(pd, file_path)
                df.columns = df.columns.astype(str)
                df = df.loc[:, ~df.columns.str.contains("^Unnamed", na=False)]
                df = df.where(pd.notnull(df), None)
                prepared_frames[raw_table] = df

            if all(df.empty for df in prepared_frames.values()):
                return False, "Backup file is empty."

            conn = self._db.get_raw_connection()
            cursor = conn.cursor()

            cursor.execute("SHOW TABLES")
            existing_tables = [row[0] for row in cursor.fetchall()]
            existing_map = {t.lower(): validate_sql_identifier(t, "table") for t in existing_tables}

            canonical_files: dict[str, object] = {}
            for raw_table, df in prepared_frames.items():
                canonical = existing_map.get(raw_table.lower())
                if canonical is None:
                    raise ValueError(f"Unknown table in backup archive: {raw_table!r}")
                canonical_files[canonical] = df

            ordered = [t for t in TABLE_IMPORT_ORDER if t in canonical_files]
            remaining = [t for t in canonical_files if t not in TABLE_IMPORT_ORDER]
            final_list = ordered + remaining

            # التحقق المسبق من الأعمدة قبل بدء المسح
            validated_payloads: list[tuple[str, list[str], list[tuple]]] = []
            for canonical_table in final_list:
                df = canonical_files[canonical_table]
                db_cols, generated_cols = _get_table_columns_info(cursor, canonical_table)
                valid_cols = _validate_and_filter_columns(
                    df.columns, db_cols, generated_cols, canonical_table
                )
                if df.empty or not valid_cols:
                    validated_payloads.append((canonical_table, [], []))
                    continue
                df_filtered = df[valid_cols]
                cleaned_data = _clean_dataframe_rows(df_filtered, np)
                validated_payloads.append((canonical_table, valid_cols, cleaned_data))

            # بدء معاملة الاستعادة الذرية الحقيقية
            conn.start_transaction()
            cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
            try:
                for canonical_table in reversed(final_list):
                    cursor.execute(f"DELETE FROM `{canonical_table}`")

                for canonical_table, valid_cols, cleaned_data in validated_payloads:
                    if not cleaned_data or not valid_cols:
                        continue
                    cols_sql = ",".join(f"`{c}`" for c in valid_cols)
                    placeholders = ",".join(["%s"] * len(valid_cols))
                    sql = f"INSERT INTO `{canonical_table}` ({cols_sql}) VALUES ({placeholders})"
                    cursor.executemany(sql, cleaned_data)

                cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")
                conn.commit()
            except Exception:
                try:
                    conn.rollback()
                except Exception as rb_exc:
                    logging.error(f"Rollback error during restore: {rb_exc}")
                try:
                    cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")
                except Exception:
                    pass
                raise

            label = "CSV" if extension == ".csv" else "Excel"
            return True, f"{label} Restore Success."

        except Exception as e:
            logging.error(f"❌ Restore failed and was rolled back: {e}")
            return False, f"Restore failed: {str(e)}"
        finally:
            if cursor is not None:
                try:
                    cursor.close()
                except Exception:
                    pass
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)

    # ─── CSV Backup ───────────────────────────────────────────────────────────
    def backup_database_csv(self, output_zip_path: str, password: str = ""):
        temp_dir = tempfile.mkdtemp(prefix="goldshop_backup_csv_")
        try:
            self._export_tables_to_dir(temp_dir, fmt="csv", format_datetimes=True)
            write_zip_from_dir(temp_dir, output_zip_path, password=password)
            return True, f"Backup created: {os.path.basename(output_zip_path)}"
        except Exception as e:
            logging.error(f"❌ CSV backup failed: {e}")
            return False, str(e)
        finally:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)

    # ─── CSV Restore ──────────────────────────────────────────────────────────
    def restore_database_csv(self, input_zip_path: str, password: str | None = None):
        return self._restore_from_archive(
            input_zip_path,
            extension=".csv",
            dataframe_loader=lambda pd, p: pd.read_csv(
                p, na_values=["<NULL>"], keep_default_na=True
            ),
            password=password,
        )

    # ─── Excel Export ─────────────────────────────────────────────────────────
    def export_to_excel(self, output_zip_path: str, password: str = ""):
        temp_dir = tempfile.mkdtemp(prefix="goldshop_backup_xlsx_")
        try:
            self._export_tables_to_dir(temp_dir, fmt="xlsx", format_datetimes=False)
            write_zip_from_dir(temp_dir, output_zip_path, password=password)
            return True, f"Excel backup created: {os.path.basename(output_zip_path)}"
        except Exception as e:
            logging.error(f"❌ Excel backup failed: {e}")
            return False, str(e)
        finally:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)

    # ─── Excel Restore ────────────────────────────────────────────────────────
    def restore_from_excel(self, input_zip_path: str, password: str | None = None):
        return self._restore_from_archive(
            input_zip_path,
            extension=".xlsx",
            dataframe_loader=lambda pd, p: pd.read_excel(p),
            password=password,
        )

    # ─── Archive Old Logs ─────────────────────────────────────────────────────
    def export_and_purge_tables(self, output_zip_path: str, days_to_keep: int = 365):
        """يُصدّر السجلات القديمة ويحذفها من قاعدة البيانات."""
        tables_to_archive = ("SupplierTransactions", "MoneyTransactions")
        cutoff_date = date.today() - timedelta(days=days_to_keep)
        temp_dir = tempfile.mkdtemp(prefix="goldshop_archive_logs_")

        try:
            if self._db.engine is None:
                raise RuntimeError("SQLAlchemy engine is not initialized.")

            pd = _load_pandas()
            has_data = False
            with self._db.engine.connect() as conn_sa:
                for table in tables_to_archive:
                    safe_table = validate_sql_identifier(table, "table")
                    query = text(f"SELECT * FROM `{safe_table}` WHERE transaction_date < :cutoff")
                    df = pd.read_sql(query, conn_sa, params={"cutoff": cutoff_date})
                    if not df.empty:
                        has_data = True
                        df.to_csv(os.path.join(temp_dir, f"{safe_table}.csv"), index=False, encoding="utf-8")

            if has_data:
                with self._db.get_db_connection() as del_conn:
                    del_cursor = del_conn.cursor()
                    try:
                        for table in tables_to_archive:
                            safe_table = validate_sql_identifier(table, "table")
                            del_cursor.execute(
                                f"DELETE FROM `{safe_table}` WHERE transaction_date < %s",
                                (cutoff_date,),
                            )
                    finally:
                        del_cursor.close()

                write_zip_from_dir(temp_dir, output_zip_path)
                return True, f"Archived old logs to:\n{output_zip_path}"
            return False, "No old records found to archive."

        except Exception as e:
            return False, str(e)
        finally:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)

    # ─── Single Table Restore ─────────────────────────────────────────────────
    def restore_table_from_file(self, table_name: str, file_path: str) -> bool:
        try:
            if self._db.engine is None:
                raise RuntimeError("SQLAlchemy engine is not initialized.")

            safe_table = validate_sql_identifier(table_name, "table")
            inspector = sqlalchemy.inspect(self._db.engine)
            existing_map = {t.lower(): validate_sql_identifier(t, "table") for t in inspector.get_table_names()}
            canonical_table = existing_map.get(safe_table.lower())
            if canonical_table is None:
                raise ValueError(f"Unknown table: {table_name!r}")

            pd = _load_pandas()
            if file_path.lower().endswith(".csv"):
                df = pd.read_csv(file_path, na_values=["<NULL>"], keep_default_na=True)
            else:
                df = pd.read_excel(file_path)

            df.columns = df.columns.astype(str)
            df = df.loc[:, ~df.columns.str.contains("^Unnamed", na=False)]
            df = df.where(pd.notnull(df), None)

            with self._db.get_db_connection() as conn:
                cursor = conn.cursor()
                try:
                    db_cols, generated_cols = _get_table_columns_info(cursor, canonical_table)
                finally:
                    cursor.close()

            valid_cols = _validate_and_filter_columns(
                df.columns, db_cols, generated_cols, canonical_table
            )
            if not valid_cols or df.empty:
                return True

            df = df[valid_cols]
            with self._db.engine.begin() as conn_sa:
                df.to_sql(name=canonical_table, con=conn_sa, if_exists="append", index=False)
            return True
        except Exception as e:
            logging.error(f"restore_table_from_file error: {e}")
            return False

    def create_auto_backup(self, base_backup_path: str, password: str = ""):
        """
        يُنشئ نسخة احتياطية في مجلد Auto_Backups.
        يقوم بإنشاء النسخة الجديدة أولاً ثم يحذف النسخ القديمة لضمان عدم ضياع النسخة السابقة عند الفشل.
        """
        import datetime

        auto_backup_dir = os.path.join(base_backup_path, "Auto_Backups")
        temp_dir = tempfile.mkdtemp(prefix="goldshop_auto_backup_")
        temp_zip_fd, temp_zip_path = tempfile.mkstemp(prefix="AutoBackup_", suffix=".zip")
        os.close(temp_zip_fd)

        try:
            self._export_tables_to_dir(temp_dir, fmt="csv", format_datetimes=True)
            write_zip_from_dir(temp_dir, temp_zip_path, password=password)

            os.makedirs(auto_backup_dir, exist_ok=True)
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            final_zip_path = os.path.join(auto_backup_dir, f"AutoBackup_{timestamp}.zip")
            shutil.copy2(temp_zip_path, final_zip_path)

            for file_name in os.listdir(auto_backup_dir):
                if file_name.endswith(".zip") and file_name != os.path.basename(final_zip_path):
                    file_path = os.path.join(auto_backup_dir, file_name)
                    try:
                        os.remove(file_path)
                    except Exception as e:
                        logging.warning(f"⚠️ Impossible de supprimer l'ancienne sauvegarde: {e}")

            logging.info(f"✅ Sauvegarde Automatique réussie : {final_zip_path}")
            return True

        except Exception as e:
            logging.error(f"❌ Échec de la Sauvegarde Automatique : {e}")
            return False
        finally:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
            if os.path.exists(temp_zip_path):
                try:
                    os.remove(temp_zip_path)
                except OSError:
                    pass

    # ─── Multi-Path Backup (Manual & Auto) ──────────────────────────────────
    def create_multi_backup(self, target_paths: list, password: str = "", is_auto: bool = True):
        """
        يقوم بتوليد النسخة الاحتياطية ونسخها إلى جميع المسارات المحددة في القائمة.
        إذا كان is_auto=True: يضعها في مجلد Auto_Backups ويحذف النسخ القديمة بعد نجاح النسخة الجديدة.
        إذا كان is_auto=False: يضعها مباشرة في المسار المحدد بدون حذف القديم.
        """
        import datetime

        if not target_paths:
            return False, "Aucun chemin de sauvegarde spécifié."

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        prefix = "AutoBackup" if is_auto else "ManualBackup"
        zip_filename = f"{prefix}_{timestamp}.zip"

        temp_csv_dir = tempfile.mkdtemp(prefix="goldshop_multi_backup_")
        temp_zip_fd, master_zip_path = tempfile.mkstemp(prefix=f"{prefix}_", suffix=".zip")
        os.close(temp_zip_fd)

        try:
            self._export_tables_to_dir(temp_csv_dir, fmt="csv", format_datetimes=True)
            write_zip_from_dir(temp_csv_dir, master_zip_path, password=password)

            success_count = 0
            for base_path in target_paths:
                try:
                    if os.path.abspath(base_path) == os.path.abspath("C:\\"):
                        base_path = os.path.join("C:\\", "GoldShop_Backups")
                        logging.info(f"⚠️ Redirection automatique vers {base_path} pour éviter l'erreur de permission.")

                    dest_dir = os.path.join(base_path, "Auto_Backups") if is_auto else base_path
                    os.makedirs(dest_dir, exist_ok=True)

                    final_path = os.path.join(dest_dir, zip_filename)
                    shutil.copy2(master_zip_path, final_path)

                    if is_auto:
                        for file_name in os.listdir(dest_dir):
                            if (
                                file_name.endswith(".zip")
                                and file_name.startswith("AutoBackup")
                                and file_name != zip_filename
                            ):
                                try:
                                    os.remove(os.path.join(dest_dir, file_name))
                                except Exception as rm_exc:
                                    logging.warning(f"⚠️ Impossible de supprimer l'ancienne sauvegarde {file_name}: {rm_exc}")

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
            if os.path.exists(temp_csv_dir):
                shutil.rmtree(temp_csv_dir, ignore_errors=True)
            if os.path.exists(master_zip_path):
                try:
                    os.remove(master_zip_path)
                except OSError:
                    pass

    # ─── Convenience Aliases ──────────────────────────────────────────────────
    def export_all_tables_to_csv_zip(self, output_zip_path: str = "backup_csv.zip"):
        return self.backup_database_csv(output_zip_path)

    def restore_from_archive_zip_destructive(self, input_zip_path: str, tables_to_restore=None):
        return self.restore_database_csv(input_zip_path)
