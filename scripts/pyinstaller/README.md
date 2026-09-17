# scripts/pyinstaller

يحتوي هذا المجلد على سكربتات بناء وإعداد الحزم التنفيذية الخاصة بالتطبيق باستخدام PyInstaller.

## الملفات

- `pyinstaller.py`: سكربت أتمتة بناء النسخة التنفيذية الإنتاجية (`GOLDSHOP.exe`) وتجهيز المسارات والموارد؛ يشمل تجميع خادم الويب (`web/templates`, `web/static`, Flask, Jinja2, Werkzeug)، ملفات الترجمة، الأنماط، وموصلات MySQL.
