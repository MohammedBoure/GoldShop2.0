import hashlib
import json
import logging

import qtawesome as qta
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel, QTabWidget, QVBoxLayout, QWidget

from permissions.catalog import expand_permission_keys
from ui.ui_customization import is_layout_hidden, layout_structure


class MainWindowPermissionsMixin:
    """Permission checks, scoped tabs, and runtime permission discovery."""

    def _parse_permissions(self):
        """تفكيك الصلاحيات بشكل آمن ومتوافق مع نظام إدارة المستخدمين"""
        if hasattr(self.data_manager.users, "get_user_permissions"):
            return expand_permission_keys(self.data_manager.users.get_user_permissions(self.current_user))

        perms_str = self.current_user.get("permissions", "[]")
        try:
            if isinstance(perms_str, list):
                return expand_permission_keys(perms_str)
            return expand_permission_keys(json.loads(perms_str))
        except Exception as exc:
            logging.error("Error parsing permissions: %s", exc)
            return []

    def has_permission(self, perm_key):
        """التحقق من الصلاحية بعد توسيع صلاحيات الأب في الشجرة."""
        if self._is_admin_user():
            return True
        self._ensure_permission_cache_current()
        return perm_key in getattr(self, "user_permissions_set", set())

    def _permission_signature(self):
        if self._is_admin_user():
            return f"admin:{self.current_user.get('id', '')}"
        self._ensure_permission_cache_current()
        return self._permission_signature_cache

    def _ensure_permission_cache_current(self):
        source_token = self._current_permission_source_token()
        if source_token != getattr(self, "_permission_source_token", None) or getattr(self, "_permission_signature_cache", None) is None:
            fresh_permissions = self._parse_permissions()
            fresh_permissions_set = set(fresh_permissions)
            self._permission_source_token = source_token
            self.user_permissions = fresh_permissions
            self.user_permissions_set = fresh_permissions_set
            payload = "\n".join(sorted(str(key) for key in self.user_permissions_set))
            digest = hashlib.sha1(payload.encode("utf-8")).hexdigest()
            self._permission_signature_cache = f"user:{self.current_user.get('id', '')}:{digest}"

    def _current_permission_source_token(self):
        raw_permissions = self.current_user.get("permissions", "[]")
        try:
            return json.dumps(raw_permissions, ensure_ascii=False, sort_keys=True)
        except TypeError:
            return str(raw_permissions)

    def _is_admin_user(self):
        return self.current_user.get("role") == "Admin"

    def _scope_widget(self, widget, permission_key, label=None):
        """دالة مبسطة لربط الصلاحيات بواجهة معينة (تمت إزالة نظام auto_permissions)"""
        if widget:
            widget._layout_tab_permission_key = permission_key
        return widget

    def _add_scoped_tab(self, tabs, widget, permission_key, label, icon=None):
        """إضافة تبويب مع ربط صلاحية (نسخة مبسطة)"""
        self._scope_widget(widget, permission_key, label)
        if icon is None:
            tabs.addTab(widget, label)
        else:
            tabs.addTab(widget, icon, label)
        return widget

    def _add_lazy_scoped_tab(self, tabs, factory, permission_key, label, icon=None):
        """إضافة تبويب مؤجل التحميل (Lazy Load)"""
        placeholder = QWidget()
        placeholder._lazy_tab_factory = factory
        placeholder._lazy_tab_permission_key = permission_key
        placeholder._lazy_tab_label = label
        layout = QVBoxLayout(placeholder)
        layout.setContentsMargins(20, 20, 20, 20)
        loading = QLabel("Le contenu sera charge lors de l'ouverture de cet onglet.")
        loading.setAlignment(Qt.AlignCenter)
        layout.addWidget(loading, 1)
        self._scope_widget(placeholder, permission_key, label)
        if icon is None:
            tabs.addTab(placeholder, label)
        else:
            tabs.addTab(placeholder, icon, label)
        return placeholder

    def _ensure_lazy_tab_loaded(self, tabs, index=None):
        """تحميل محتوى التبويب المؤجل عند الحاجة إليه"""
        if not isinstance(tabs, QTabWidget):
            return None
        index = tabs.currentIndex() if index is None else index
        if index < 0:
            return None
        widget = tabs.widget(index)
        factory = getattr(widget, "_lazy_tab_factory", None)
        if not callable(factory):
            return widget

        permission_key = getattr(widget, "_lazy_tab_permission_key", None)
        label = getattr(widget, "_lazy_tab_label", tabs.tabText(index))
        icon = tabs.tabIcon(index)
        title = tabs.tabText(index)
        tooltip = tabs.tabToolTip(index)

        built = factory()
        if permission_key:
            self._scope_widget(built, permission_key, label)

        tabs.blockSignals(True)
        tabs.removeTab(index)
        if icon.isNull():
            tabs.insertTab(index, built, title)
        else:
            tabs.insertTab(index, built, icon, title)
        tabs.setTabToolTip(index, tooltip)
        tabs.setCurrentIndex(index)
        tabs.blockSignals(False)
        return built

    def _apply_tab_layout(self, tabs, page_key):
        """تطبيق ترتيب التبويبات بناءً على الإعدادات"""
        if not isinstance(tabs, QTabWidget) or not page_key:
            return tabs

        page_layout = layout_structure(self.get_ui_customization_config()).get("tabs", {}).get(page_key, {})
        order = page_layout.get("order") or []
        advanced = set(page_layout.get("advanced") or [])
        hidden = set(page_layout.get("hidden") or [])

        tab_items = []
        while tabs.count():
            widget = tabs.widget(0)
            title = tabs.tabText(0)
            icon = tabs.tabIcon(0)
            tooltip = tabs.tabToolTip(0)
            key = getattr(widget, "_layout_tab_permission_key", "")
            tabs.removeTab(0)
            if key and (key in hidden or is_layout_hidden(self.get_ui_customization_config(), key)):
                widget.setParent(None)
                widget.deleteLater()
                continue
            tab_items.append({
                "key": str(key or ""),
                "widget": widget,
                "title": title,
                "icon": icon,
                "tooltip": tooltip,
            })

        def order_index(item):
            key = item.get("key")
            return order.index(key) if key in order else len(order)

        tab_items.sort(key=order_index)
        normal_items = [item for item in tab_items if item["key"] not in advanced]
        advanced_items = [item for item in tab_items if item["key"] in advanced]

        for item in normal_items:
            self._insert_prepared_tab(tabs, item)

        if advanced_items:
            advanced_tabs = QTabWidget()
            advanced_tabs.setProperty("permission_scope_key", f"{page_key}.advanced")
            advanced_tabs.setProperty("permission_scope_label", "Avance")
            for item in advanced_items:
                self._insert_prepared_tab(advanced_tabs, item)
            tabs.addTab(advanced_tabs, qta.icon("fa5s.layer-group"), "Avance")
        return tabs

    def _insert_prepared_tab(self, tabs, item):
        icon = item["icon"]
        if icon.isNull():
            index = tabs.addTab(item["widget"], item["title"])
        else:
            index = tabs.addTab(item["widget"], icon, item["title"])
        tabs.setTabToolTip(index, item.get("tooltip", ""))
        item["widget"]._layout_tab_permission_key = item.get("key", "")

    def _bind_scoped_dialog(self, dialog, permission_key, label=None):
        self._scope_widget(dialog, permission_key, label or permission_key)
        return dialog

    def _page_permission_key(self, page_id):
        return {
            0: "nav_dashboard",
            1: "nav_inventory",
            2: "nav_sales",
            3: "nav_partners",
            4: "nav_services",
            5: "nav_finance",
            6: "nav_data",
            7: "nav_settings",
            8: "nav_reports",
            9: "nav_history",
            10: "nav_market",
            11: "nav_versement",
            12: "nav_client_commands",
            13: "nav_inventory_count",
            14: "nav_official_suppliers",
            15: "nav_rh",
        }.get(page_id)

    def _page_permission_label(self, page_id):
        return {
            0: "Tableau de Bord",
            1: "Stock",
            2: "Point de Vente",
            3: "Partenaires",
            5: "Finance",
            6: "Donnees de Base",
            7: "Parametres",
            8: "Rapports",
            9: "Tracabilite",
            10: "Marche",
            11: "Versements & Dettes",
            12: "Commandes Client",
            13: "Inventaire Physique",
            14: "Fournisseurs Officiels",
            15: "Gestion Personnel & RH",
        }.get(page_id)

    def _open_first_available_page(self):
        """فتح أول صفحة يملك المستخدم صلاحية الوصول إليها تلقائياً"""
        if hasattr(self, "nav_group") and self.nav_group.buttons():
            for button in self.nav_group.buttons():
                page_id = self.nav_group.id(button)
                self.switch_page(page_id)
                button.setChecked(True)
                return