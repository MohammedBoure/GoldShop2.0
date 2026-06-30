"""
base.py  ←  ملف التوافق العكسي (Backward Compatibility Shim)
-------------------------------------------------------------
هذا الملف يستبدل base.py القديم تماماً.
جميع الملفات الأخرى التي تستورد منه لن تحتاج أي تعديل:

    from database.base import Database          ✅ يعمل
    from database.base import CustomJSONEncoder ✅ يعمل
    from database.base import TABLE_IMPORT_ORDER ✅ يعمل
    from database.base import get_external_path  ✅ يعمل
    from database.base import logger             ✅ يعمل

المنطق الفعلي انتقل إلى:
    database/database.py          ← Database class
    database/config.py            ← ثوابت + logging + CustomJSONEncoder
    database/connection.py        ← ConnectionManager
    database/schema_initializer.py ← تهيئة المخطط
    database/backup_manager.py    ← نسخ احتياطي / استعادة
    database/archive_view_manager.py ← وضع الأرشيف
    database/schema/              ← تعريفات SQL
"""

# ── إعادة تصدير كل ما كان موجوداً في base.py القديم ──────────────────────────
from .database import Database                    # noqa: F401
from .config import (                             # noqa: F401
    get_external_path,
    TABLE_IMPORT_ORDER,
    ARCHIVE_VIEW_FLAG_FILE,
    HARD_RESET_PASSWORD,
    CustomJSONEncoder,
    logger,
)