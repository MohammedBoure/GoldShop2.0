# مجلد الاختبارات الآلية (Automated Tests)

يحتوي هذا المجلد على وحدات الاختبارات الآلية الشاملة (Unit & Integration Tests) لنظام GoldShop.

---

## فهرس ملفات الاختبار ومسؤولياتها:

* `test_multi_metal_sales.py`: اختبارات دعم الذهب والفضة في المبيعات، تسجيل الأوزان الخارجة، حساب مبالغ الفضة الكسر، وتلخيص دفعات العربون.
* `test_excel_journal_features.py`: اختبارات مزايا يومية المبيعات بنمط إكسل وتعديل المبالغ والأوزان.
* `test_invoice_pdf_generator.py`: اختبارات توليد وصولات وفواتير PDF والملاحظات المخصصة.
* `test_profit_calculator.py`: اختبارات حساب الأرباح الصافية وتوزيع العائدات والتكاليف.
* `test_versement_custom_notes.py`: اختبارات الملاحظات المخصصة لعمليات العربون.
* `test_versement_idempotency_and_weight.py`: اختبارات موثوقية دفعات وأوزان العربون.
* `test_versement_pricing.py`: اختبارات تسعير وتخفيضات دفعات العربون.
* `test_versement_quantity_manager.py`: اختبارات حجز وإدارة كميات قطع العربون.
* `test_versement_quantity_ui.py`: اختبارات واجهة المستخدم لإدارة كميات العربون.
* `test_versement_reservation.py`: اختبارات حجز المخزون لملفات العربون.
