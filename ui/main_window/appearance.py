import copy
import json
import logging
import os
import re
import sys

import qtawesome as qta
from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QSize, Qt
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QScroller,
    QVBoxLayout,
    QWidget,
)

from ui.ui_customization import (
    DEFAULT_SIDEBAR_ITEMS,
    active_theme,
    build_application_palette,
    build_application_stylesheet,
    ensure_ui_customization,
    is_layout_hidden,
    layout_structure,
    sync_application_inline_styles,
)
from ui.tools.date_picker import install_custom_date_picker


def get_resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


class MainWindowAppearanceMixin:
    """Zoom, stylesheet, and sidebar composition behavior."""

    def load_saved_zoom(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r", encoding="utf-8") as handle:
                    config = json.load(handle)
                    self.zoom_scale = float(config.get("zoom_level", 100)) / 100.0
            except Exception:
                self.zoom_scale = 1.0

    def get_ui_customization_config(self):
        mtime = self._config_mtime()
        if self._ui_customization_cache is not None and self._ui_customization_cache_mtime == mtime:
            return self._ui_customization_cache

        config = {}
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r", encoding="utf-8") as handle:
                    config = json.load(handle)
            except Exception:
                config = {}
        self._ui_customization_cache = ensure_ui_customization(config)
        self._ui_customization_cache_mtime = mtime
        return self._ui_customization_cache

    def _config_mtime(self):
        try:
            return os.path.getmtime(self.config_file)
        except OSError:
            return None

    def set_ui_customization_config(self, ui_config):
        config = {"ui_customization": copy.deepcopy(ui_config or {})}
        self._ui_customization_cache = ensure_ui_customization(config)
        self._ui_customization_cache_mtime = self._config_mtime()

    def current_ui_theme(self):
        return active_theme(self.get_ui_customization_config())

    def load_scaled_stylesheet(self):
        try:
            style_path = get_resource_path("ui/styles.qss")
            content = ""
            if os.path.exists(style_path):
                with open(style_path, "r", encoding="utf-8") as handle:
                    content = handle.read()

            def scale_px(match):
                value = int(match.group(1))
                return f"{value}px" if value <= 1 else f"{int(value * self.zoom_scale)}px"

            scaled = re.sub(r"(\d+)px", scale_px, content)
            custom = build_application_stylesheet(self.get_ui_customization_config(), self.zoom_scale)
            stylesheet = f"{scaled}\n{custom}"
            app = QApplication.instance()
            if app is not None:
                ui_config = self.get_ui_customization_config()
                app.setPalette(build_application_palette(ui_config))
                if app.styleSheet() != stylesheet:
                    app.setStyleSheet(stylesheet)
                sync_application_inline_styles(app, ui_config)
                install_custom_date_picker(app)
        except Exception:
            pass

    def refresh_ui_scaling(self):
        layout = self.current_ui_theme().get("layout", {})
        full_base = int(layout.get("sidebar_full_width", self.base_sidebar_full) or self.base_sidebar_full)
        compact_base = int(layout.get("sidebar_compact_width", self.base_sidebar_compact) or self.base_sidebar_compact)
        self.sidebar_full_width = int(full_base * self.zoom_scale)
        self.sidebar_compact_width = int(compact_base * self.zoom_scale)
        current_width = self.sidebar_full_width if self.is_sidebar_expanded else self.sidebar_compact_width
        if hasattr(self, "sidebar_container"):
            self.sidebar_container.setFixedWidth(current_width)
        icon_size = int(20 * self.zoom_scale)
        if hasattr(self, "nav_group"):
            for button in self.nav_group.buttons():
                button.setIconSize(QSize(icon_size, icon_size))

        if hasattr(self, "btn_tools_toggle") and self.btn_tools_toggle:
            self.btn_tools_toggle.setIconSize(QSize(icon_size, icon_size))
        if hasattr(self, "btn_logout"):
            self.btn_logout.setIconSize(QSize(icon_size, icon_size))

        self.load_scaled_stylesheet()

    def apply_ui_customization_config(self, ui_config=None):
        if ui_config is not None:
            self.set_ui_customization_config(ui_config)
        if hasattr(self, "sidebar_container"):
            self._rebuild_sidebar_from_layout()
        self.refresh_ui_scaling()

    def save_zoom_setting(self):
        current_config = {}
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r", encoding="utf-8") as handle:
                    current_config = json.load(handle)
            except Exception:
                pass

        current_config["zoom_level"] = int(self.zoom_scale * 100)
        try:
            from config import save_full_config
            save_full_config(current_config)
        except Exception as exc:
            logging.error("Erreur sauvegarde zoom: %s", exc)

    def change_zoom(self, amount):
        self.zoom_scale = max(0.6, min(self.zoom_scale + amount, 1.8))
        self.refresh_ui_scaling()
        self.save_zoom_setting()

    def wheelEvent(self, event):
        if event.modifiers() == Qt.ControlModifier:
            self.change_zoom(0.1 if event.angleDelta().y() > 0 else -0.1)
            event.accept()
        else:
            super().wheelEvent(event)

    def _populate_sidebar_from_layout(self):
        report_item = {
            "key": "nav_reports",
            "label": "Rapports",
            "icon": "fa5s.file-excel",
            "page_id": 8
        }
        versement_item = {
            "key": "nav_versement",
            "label": "Versements",
            "icon": "fa5s.hand-holding-usd",
            "page_id": 11
        }
        rh_item = {
            "key": "nav_rh",
            "label": "Gestion RH",
            "icon": "fa5s.users-cog",
            "page_id": 15
        }
        coffre_item = {
            "key": "nav_coffre_magasin",
            "label": "Coffre Magasin",
            "icon": "fa5s.archive",
            "page_id": 16
        }
        
        reports_inserted = False
        versements_inserted = False
        rh_inserted = False
        coffre_inserted = False

        for group in self._sidebar_layout_groups():
            group_label = self._make_sidebar_group_label(group.get("label", ""))
            group_added = False
            for item in group.get("items", []):
                if item.get("key") == "nav_reports" and reports_inserted: continue
                if item.get("key") == "nav_versement" and versements_inserted: continue
                if item.get("key") == "nav_rh" and rh_inserted: continue
                if item.get("key") == "nav_coffre_magasin" and coffre_inserted: continue
                
                if not self._sidebar_item_allowed(item): continue
                if not group_added and group_label is not None:
                    self.nav_layout.addWidget(group_label)
                    group_added = True
                
                self._add_sidebar_button(item)

                if item.get("key") == "nav_sales" and not versements_inserted:
                    if self._sidebar_item_allowed(versement_item):
                        self._add_sidebar_button(versement_item)
                        versements_inserted = True

                if item.get("key") == "nav_inventory" and not reports_inserted:
                    if self._sidebar_item_allowed(report_item):
                        self._add_sidebar_button(report_item)
                        reports_inserted = True
                        
                if item.get("key") == "nav_reports" and not rh_inserted:
                    if self._sidebar_item_allowed(rh_item):
                        self._add_sidebar_button(rh_item)
                        rh_inserted = True

                if item.get("key") == "nav_rh" and not coffre_inserted:
                    if self._sidebar_item_allowed(coffre_item):
                        self._add_sidebar_button(coffre_item)
                        coffre_inserted = True

        if not versements_inserted and self._sidebar_item_allowed(versement_item):
            self._add_sidebar_button(versement_item)
            
        if not rh_inserted and self._sidebar_item_allowed(rh_item):
            self._add_sidebar_button(rh_item)

        if not coffre_inserted and self._sidebar_item_allowed(coffre_item):
            self._add_sidebar_button(coffre_item)

        if not reports_inserted:
            reports_exists = any(btn.property("permission_key") == "nav_reports" for btn in self.nav_group.buttons())
            if not reports_exists and self._sidebar_item_allowed(report_item):
                lbl = self._make_sidebar_group_label("Analyses & Rapports")
                if lbl: self.nav_layout.addWidget(lbl)
                self._add_sidebar_button(report_item)

    def _sidebar_layout_groups(self):
        ui_config = self.get_ui_customization_config()
        layout = layout_structure(ui_config)
        catalog = {item["key"]: item for item in DEFAULT_SIDEBAR_ITEMS}
        groups = []
        for group in layout.get("sidebar", {}).get("groups", []):
            items = [
                catalog[key]
                for key in group.get("items", [])
                if key in catalog and not is_layout_hidden(ui_config, key)
            ]
            if items:
                groups.append({"id": group.get("id"), "label": group.get("label", ""), "items": items})
        return groups

    def _make_sidebar_group_label(self, text):
        text = str(text or "").strip()
        if not text:
            return None
        label = QLabel(text.upper())
        label.setObjectName("sidebar_group_label")
        label.setStyleSheet(
            "color: #7b8794; font-size: 11px; font-weight: 800; "
            "padding: 12px 14px 4px 14px;"
        )
        if hasattr(self, "sidebar_group_labels"):
            self.sidebar_group_labels.append(label)
        return label

    def _add_sidebar_button(self, item):
        required_perm = item.get("key")
        if not self._sidebar_item_allowed(item):
            return False

        text = item.get("label", required_perm)
        button = QPushButton(text)
        button.setIcon(qta.icon(item.get("icon", "fa5s.circle"), color="#546e7a"))
        button.setIconSize(QSize(20, 20))
        button.setCheckable(True)
        button.setProperty("class", "nav_button")
        button.setProperty("permission_key", required_perm)
        button.setProperty("permission_label", text)
        button.setProperty("ui_element_type", "navigation")
        button.setCursor(Qt.PointingHandCursor)

        self.button_texts[button] = text
        self.nav_group.addButton(button, int(item.get("page_id", -1)))
        self.nav_layout.addWidget(button)
        return True

    def _sidebar_item_allowed(self, item):
        required_perm = item.get("key")
        return bool(required_perm and self.has_permission(required_perm))

    def _rebuild_sidebar_from_layout(self):
        if not hasattr(self, "sidebar_container"):
            return
        old_sidebar = self.sidebar_container
        current_page = self.content_area.currentIndex() if hasattr(self, "content_area") else None
        try:
            self.main_layout.removeWidget(old_sidebar)
        except RuntimeError:
            return
        old_sidebar.setParent(None)
        old_sidebar.deleteLater()
        self.button_texts = {}
        self._setup_sidebar(insert_index=0)
        if current_page is not None:
            button = self.nav_group.button(current_page)
            if button is not None:
                button.setChecked(True)

    def _setup_sidebar(self, insert_index=None):
        self.sidebar_container = QFrame()
        self.sidebar_container.setObjectName("sidebar_container")
        self.sidebar_container.setFixedWidth(self.sidebar_full_width)

        sidebar_main_layout = QVBoxLayout(self.sidebar_container)
        sidebar_main_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_main_layout.setSpacing(0)

        self.header_container = QWidget()
        self.header_container.setObjectName("header_container")
        self.header_container.setFixedHeight(80)

        header_layout = QHBoxLayout(self.header_container)
        lbl_icon = QLabel()
        lbl_icon.setPixmap(qta.icon("fa5s.gem", color="#0f8f83").pixmap(32, 32))
        self.lbl_title = QLabel("GoldShop")
        self.lbl_title.setStyleSheet(
            "font-size: 20px; font-weight: 800; color: #2c3e50; font-family: 'Segoe UI';"
        )

        header_layout.addWidget(lbl_icon)
        header_layout.addWidget(self.lbl_title)
        header_layout.addStretch()
        sidebar_main_layout.addWidget(self.header_container)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setObjectName("sidebar_scroll")
        QScroller.grabGesture(self.scroll_area.viewport(), QScroller.LeftMouseButtonGesture)

        self.nav_content = QWidget()
        self.nav_content.setObjectName("nav_content")
        self.nav_layout = QVBoxLayout(self.nav_content)
        self.nav_layout.setContentsMargins(0, 10, 0, 10)
        self.nav_layout.setSpacing(5)

        self.nav_group = QButtonGroup(self)
        self.nav_group.idClicked.connect(self.switch_page)
        self.sidebar_group_labels = []
        self._populate_sidebar_from_layout()

        self.nav_layout.addStretch()
        self.scroll_area.setWidget(self.nav_content)
        sidebar_main_layout.addWidget(self.scroll_area)

        self.footer_container = QWidget()
        footer_layout = QVBoxLayout(self.footer_container)
        footer_layout.setContentsMargins(0, 5, 0, 5)
        footer_layout.setSpacing(5)

        tool_perms = ["tool_calculator", "tool_audit", "tool_zakat", "tool_market_prices"]
        if any(self.has_permission(permission) for permission in tool_perms):
            self.btn_tools_toggle = QPushButton("Outils")
            self.btn_tools_toggle.setIcon(qta.icon("fa5s.toolbox", color="#0f8f83"))
            self.btn_tools_toggle.setIconSize(QSize(20, 20))
            self.btn_tools_toggle.setProperty("class", "nav_button")
            self.btn_tools_toggle.setProperty("permission_key", "footer_tools")
            self.btn_tools_toggle.setProperty("permission_label", "Outils")
            self.btn_tools_toggle.setProperty("ui_element_type", "navigation")
            self.btn_tools_toggle.setCursor(Qt.PointingHandCursor)
            self.btn_tools_toggle.clicked.connect(self.open_tools_dialog)
            self.button_texts[self.btn_tools_toggle] = "Outils"
            footer_layout.addWidget(self.btn_tools_toggle)

        if self.has_permission("footer_account"):
            self.btn_logout = QPushButton("Compte")
            self.btn_logout.setIcon(qta.icon("fa5s.user-circle", color="#0f8f83"))
            self.btn_logout.setIconSize(QSize(20, 20))
            self.btn_logout.setProperty("class", "nav_button")
            self.btn_logout.setProperty("permission_key", "footer_account")
            self.btn_logout.setProperty("permission_label", "Compte")
            self.btn_logout.setProperty("ui_element_type", "navigation")
            self.btn_logout.setCursor(Qt.PointingHandCursor)
            self.btn_logout.clicked.connect(self.open_account_menu)
            self.button_texts[self.btn_logout] = "Compte"
            footer_layout.addWidget(self.btn_logout)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("background-color: #bdc3c7; margin: 5px;")
        footer_layout.addWidget(line)

        self.btn_toggle = QPushButton("Réduire")
        self.btn_toggle.setIcon(qta.icon("fa5s.chevron-left", color="#b0bec5"))
        self.btn_toggle.setFlat(True)
        self.btn_toggle.setCursor(Qt.PointingHandCursor)
        self.btn_toggle.clicked.connect(self.toggle_sidebar)
        footer_layout.addWidget(self.btn_toggle)

        sidebar_main_layout.addWidget(self.footer_container)
        if insert_index is None:
            self.main_layout.addWidget(self.sidebar_container)
        else:
            self.main_layout.insertWidget(insert_index, self.sidebar_container)
        if not self.is_sidebar_expanded:
            self.lbl_title.hide()
            for label in getattr(self, "sidebar_group_labels", []):
                label.hide()
            for button in self.nav_group.buttons():
                button.setText("")
                if button in self.button_texts:
                    button.setToolTip(self.button_texts[button])
            if hasattr(self, "btn_tools_toggle") and self.btn_tools_toggle:
                self.btn_tools_toggle.setText("")
                self.btn_tools_toggle.setToolTip("Outils")
            if hasattr(self, "btn_logout"):
                self.btn_logout.setText("")

    def toggle_sidebar(self):
        target_width = self.sidebar_compact_width if self.is_sidebar_expanded else self.sidebar_full_width

        self.anim = QPropertyAnimation(self.sidebar_container, b"minimumWidth")
        self.anim.setDuration(250)
        self.anim.setEndValue(target_width)
        self.anim.setEasingCurve(QEasingCurve.InOutQuad)
        self.anim.start()

        self.anim_max = QPropertyAnimation(self.sidebar_container, b"maximumWidth")
        self.anim_max.setDuration(250)
        self.anim_max.setEndValue(target_width)
        self.anim_max.start()

        if self.is_sidebar_expanded:
            self.lbl_title.hide()
            for label in getattr(self, "sidebar_group_labels", []):
                label.hide()
            self.btn_toggle.setIcon(qta.icon("fa5s.chevron-right", color="#b0bec5"))
            self.btn_toggle.setText("")
            for button in self.nav_group.buttons():
                button.setText("")
                if button in self.button_texts:
                    button.setToolTip(self.button_texts[button])

            if hasattr(self, "btn_tools_toggle") and self.btn_tools_toggle:
                self.btn_tools_toggle.setText("")
                self.btn_tools_toggle.setToolTip("Outils")

            if hasattr(self, "btn_logout"):
                self.btn_logout.setText("")
                if self.btn_logout in self.button_texts:
                    self.btn_logout.setToolTip(self.button_texts[self.btn_logout])
        else:
            self.lbl_title.show()
            for label in getattr(self, "sidebar_group_labels", []):
                label.show()
            self.btn_toggle.setIcon(qta.icon("fa5s.chevron-left", color="#b0bec5"))
            self.btn_toggle.setText("Réduire")
            for button in self.nav_group.buttons():
                if button in self.button_texts:
                    button.setText(self.button_texts[button])
                button.setToolTip("")

            if hasattr(self, "btn_tools_toggle") and self.btn_tools_toggle:
                self.btn_tools_toggle.setText(self.button_texts.get(self.btn_tools_toggle, "Outils & Calculs"))
                self.btn_tools_toggle.setToolTip("")

            if hasattr(self, "btn_logout") and self.btn_logout in self.button_texts:
                self.btn_logout.setText(self.button_texts[self.btn_logout])
                self.btn_logout.setToolTip("")

        self.is_sidebar_expanded = not self.is_sidebar_expanded