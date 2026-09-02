# مجلد البنية الأساسية لقاعدة البيانات (Database Base)

يحتوي هذا المجلد على وحدات الاتصال الأساسية وإنشاء جداول قاعدة البيانات وترحيل المخططات (Migrations).

---

## فهرس الملفات ومسؤولياتها:

* `__init__.py`: تهيئة الحزمة وتصدير فئة `Database` المركزية.
* `database.py`: إدارة الاتصال بقاعدة بيانات MySQL ومجمعات الاتصال (Connection Pools) وتأكيد وتنفيذ الاستعلامات.
* `tables.py`: تعريف مخططات وجداول النظام الأساسية (Sales, SaleItems, Inventory, MetalTypes, Suppliers, Versement_Payments, ArtisanWorkOrders, إلخ) وتنفيذ ترقيات وتعديلات الجداول تلقائياً (Migrations) بما فيها دعم الفضة والذهب المتعدد وكسر الفضة وترقية حقول الموردين وحقول دفعات ورشة الحرفيين والتصليح (`journee_id`, `pay_cash_da`, `pay_tpe_da`, `pay_oc_g`, `pay_oc_silver_g`).
