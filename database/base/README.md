# مجلد البنية الأساسية لقاعدة البيانات (Database Base)

يحتوي هذا المجلد على وحدات الاتصال الأساسية وإنشاء جداول قاعدة البيانات وترحيل المخططات (Migrations).

---

## فهرس الملفات ومسؤولياتها:

* `__init__.py`: تهيئة الحزمة وتصدير فئة `Database` المركزية.
* `database.py`: إدارة الاتصال بقاعدة بيانات MySQL ومجمعات الاتصال (Connection Pools) وتأكيد وتنفيذ الاستعلامات.
* `tables.py`: تعريف مخططات وجداول النظام الأساسية (Sales, SaleItems, Inventory, MetalTypes, Versement_Payments, إلخ) وتنفيذ ترقيات وتعديلات الجداول تلقائياً (Migrations) بما فيها دعم الفضة والذهب المتعدد وكسر الفضة (`old_silver_weight_g`, `metal_category`, `argent_casse_g`).
