"""Shared UI customization helpers for themes and discovered UI elements."""

from __future__ import annotations

import copy
import re

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QComboBox,
    QDateEdit,
    QDateTimeEdit,
    QDoubleSpinBox,
    QFrame,
    QGroupBox,
    QLineEdit,
    QListWidget,
    QPlainTextEdit,
    QSpinBox,
    QTabWidget,
    QTableView,
    QTableWidget,
    QTextEdit,
    QTimeEdit,
    QTreeWidget,
    QWidget,
)


DEFAULT_THEME_NAME = "ERP Clair"
DARK_THEME_NAME = "ERP Sombre"
BUILTIN_THEME_NAMES = (DEFAULT_THEME_NAME, DARK_THEME_NAME)
_CONTROL_BASE_PROP = "_ui_customization_base_state"
_CONTROL_APPLIED_PROP = "_ui_customization_applied"
_COLUMN_BASE_PROP = "_ui_customization_column_base_state"
_COLUMN_APPLIED_PROP = "_ui_customization_column_applied"
_INLINE_THEME_ORIGINAL_PROP = "_ui_customization_inline_theme_original"
_INLINE_THEME_APPLIED_PROP = "_ui_customization_inline_theme_applied"
_INLINE_THEME_SYNCING_PROP = "_ui_customization_inline_theme_syncing"
_INLINE_THEME_EXPECTED_PROP = "_ui_customization_inline_theme_expected"
_INLINE_THEME_FILTER_ATTR = "_ui_customization_inline_theme_filter"
_INLINE_CONTAINER_OBJECT_NAMES = {"card", "panel", "structureToolbar", "supplierSidebarForm"}
_INLINE_CONTAINER_SELECTOR_RE = re.compile(
    r"\b(?:QFrame|QGroupBox|QTableWidget|QTableView|QTreeWidget|QListWidget)\b(?!::)|"
    r"\bQTabWidget::pane\b",
    re.IGNORECASE,
)
_INLINE_DATA_CONTAINER_SELECTOR_RE = re.compile(
    r"\bQWidget\s*\[\s*ui_element_type\s*=\s*['\"]?data_container['\"]?\s*\]",
    re.IGNORECASE,
)
_INLINE_QSS_RULE_RE = re.compile(r"(?P<selectors>[^{}]+)\{(?P<body>[^{}]*)\}", re.DOTALL)

DEFAULT_SIDEBAR_ITEMS = [
    {"page_id": 1, "key": "nav_inventory", "label": "Stock", "icon": "fa5s.ring"},
    {"page_id": 2, "key": "nav_sales", "label": "Point de Vente (POS)", "icon": "fa5s.cash-register"},
    {"page_id": 12, "key": "nav_client_commands", "label": "Commandes Client", "icon": "fa5s.clipboard-list"},
    {"page_id": 13, "key": "nav_inventory_count", "label": "Inventaire Physique", "icon": "fa5s.tasks"},
    {"page_id": 3, "key": "nav_partners", "label": "Partenaires", "icon": "fa5s.users"},
    {"page_id": 14, "key": "nav_official_suppliers", "label": "Fournisseurs Officiels", "icon": "fa5s.file-contract"},
    {"page_id": 6, "key": "nav_data", "label": "Donnees de Base", "icon": "fa5s.database"},
    {"page_id": 7, "key": "nav_settings", "label": "Parametres", "icon": "fa5s.cog"},
]

DEFAULT_SIDEBAR_GROUPS = [
    {
        "id": "main",
        "label": "Principal",
        "items": [
            "nav_dashboard",
            "nav_sales",
            "nav_versement",
            "nav_client_commands",
            "nav_inventory",
            "nav_inventory_count",
        ],
    },
    {
        "id": "management",
        "label": "Gestion",
        "items": ["nav_partners", "nav_official_suppliers", "nav_services", "nav_finance", "nav_reports", "nav_history"],
    },
    {
        "id": "system",
        "label": "Systeme",
        "items": ["nav_data", "nav_settings"],
    },
]

DEFAULT_TAB_LAYOUTS = {
    "nav_inventory": [
        {"key": "tab_inv_list", "label": "Stock"},
        {"key": "tab_inv_form", "label": "Ajouter Produit"},
    ],
    "nav_partners": [
        {"key": "tab_clients", "label": "Clients"},
        {"key": "tab_suppliers", "label": "Fournisseurs"},
    ],
    "nav_services": [
        {"key": "tab_repairs", "label": "Reparations"},
        {"key": "tab_artisans", "label": "Artisans"},
    ],
    "nav_finance": [
        {"key": "finance_view", "label": "Vue d'ensemble"},
        {"key": "tab_treasury_ops", "label": "Operations Rapides"},
        {"key": "tab_cashbox", "label": "Journal de Caisse"},
        {"key": "tab_expenses", "label": "Depenses"},
    ],
    "nav_data": [
        {"key": "tab_metals", "label": "Types de Metaux"},
        {"key": "tab_categories", "label": "Categories (Produits)"},
        {"key": "tab_product_names", "label": "Designations (Noms)"},
        {"key": "tab_locations", "label": "Emplacements (Stock)"},
        {"key": "tab_currencies", "label": "Devises (Change)"},
        {"key": "tab_treasury_locs", "label": "Coffres & Caisses"},
        {"key": "tab_exp_cats", "label": "Categories Depenses"},
        {"key": "tab_invoice_notes", "label": "Notes Facture"},
    ],
    "nav_settings": [
        {"key": "tab_config", "label": "Configuration"},
        {"key": "tab_users", "label": "Utilisateurs"},
        {"key": "tab_system_logs", "label": "Logs Systeme"},
    ],
    "nav_history": [
        {"key": "tab_hist_sessions", "label": "Sessions & Caisse"},
        {"key": "tab_hist_sales", "label": "Historique Ventes"},
        {"key": "tab_hist_products", "label": "Tableau des Realisations"},
    ],
}

DEFAULT_LAYOUT_STRUCTURE = {
    "sidebar": {
        "groups": copy.deepcopy(DEFAULT_SIDEBAR_GROUPS),
        "hidden": [],
    },
    "tabs": {
        page_key: {
            "order": [item["key"] for item in items],
            "advanced": [],
            "hidden": [],
        }
        for page_key, items in DEFAULT_TAB_LAYOUTS.items()
    },
    "button_zones": {},
    "hidden_elements": [],
}

DEFAULT_LAYOUT_THEME = {
    "font_size": 13,
    "button_height": 32,
    "input_height": 32,
    "table_row_height": 34,
    "radius": 5,
    "container_radius": 2,
    "spacing": 8,
    "sidebar_full_width": 250,
    "sidebar_compact_width": 70,
    "density": "compact",
}

DEFAULT_BUILTIN_THEMES = {
    DEFAULT_THEME_NAME: {
        "description": "Theme clair, sobre et dense pour usage ERP.",
        "palette": {
            "primary": "#007572",
            "primary_hover": "#006a67",
            "accent": "#d88a21",
            "background": "#f5f7f9",
            "surface": "#ffffff",
            "surface_alt": "#eef3f7",
            "text": "#1f2933",
            "muted": "#6b7280",
            "border": "#d9e1e8",
            "success": "#1f8f61",
            "danger": "#b42318",
            "sidebar": "#ffffff",
            "selection": "#dff2f1",
        },
        "layout": copy.deepcopy(DEFAULT_LAYOUT_THEME),
    },
    DARK_THEME_NAME: {
        "description": "Theme sombre complet pour usage tactile et caisse.",
        "palette": {
            "primary": "#33c7b8",
            "primary_hover": "#4fd9cb",
            "accent": "#f1a849",
            "background": "#111820",
            "surface": "#17222c",
            "surface_alt": "#22303d",
            "text": "#eef4f8",
            "muted": "#a8b5c2",
            "border": "#354655",
            "success": "#58d68d",
            "danger": "#ff7b72",
            "sidebar": "#0e151c",
            "selection": "#204f55",
        },
        "layout": copy.deepcopy(DEFAULT_LAYOUT_THEME),
    },
}

DEFAULT_UI_CUSTOMIZATION = {
    "active_theme": DEFAULT_THEME_NAME,
    "themes": copy.deepcopy(DEFAULT_BUILTIN_THEMES),
    "element_overrides": {},
    "custom_qss": "",
    "active_qss_profile": "",
    "qss_profiles": {},
    "layout_structure": copy.deepcopy(DEFAULT_LAYOUT_STRUCTURE),
}


def ensure_ui_customization(config):
    """Ensure config contains the full UI customization shape."""
    ui_config = config.setdefault("ui_customization", {})
    defaults = copy.deepcopy(DEFAULT_UI_CUSTOMIZATION)

    ui_config.setdefault("active_theme", defaults["active_theme"])
    themes = ui_config.setdefault("themes", {})
    if not isinstance(themes, dict):
        themes = {}
        ui_config["themes"] = themes
    if not themes:
        themes.update(copy.deepcopy(defaults["themes"]))
    else:
        for theme_name in BUILTIN_THEME_NAMES:
            if theme_name not in themes:
                themes[theme_name] = copy.deepcopy(defaults["themes"][theme_name])

    active = str(ui_config.get("active_theme") or "").strip() or DEFAULT_THEME_NAME
    if active not in themes:
        active = next(iter(themes.keys()), DEFAULT_THEME_NAME)
    ui_config["active_theme"] = active

    for name, theme in list(themes.items()):
        themes[name] = normalize_theme(theme)

    overrides = ui_config.setdefault("element_overrides", {})
    if not isinstance(overrides, dict):
        ui_config["element_overrides"] = {}
    ui_config.setdefault("custom_qss", "")
    if not isinstance(ui_config.get("custom_qss", ""), str):
        ui_config["custom_qss"] = ""

    profiles = ui_config.setdefault("qss_profiles", {})
    if not isinstance(profiles, dict):
        profiles = {}
        ui_config["qss_profiles"] = profiles
    else:
        cleaned_profiles = {}
        for name, qss_text in profiles.items():
            clean_name = str(name or "").strip()
            if not clean_name:
                continue
            cleaned_profiles[clean_name] = qss_text if isinstance(qss_text, str) else str(qss_text or "")
        profiles = cleaned_profiles
        ui_config["qss_profiles"] = profiles

    active_qss_profile = str(ui_config.get("active_qss_profile") or "").strip()
    if active_qss_profile and active_qss_profile not in profiles:
        active_qss_profile = ""
    ui_config["active_qss_profile"] = active_qss_profile
    ensure_layout_structure(ui_config)
    return ui_config


def ensure_layout_structure(ui_config):
    layout = ui_config.setdefault("layout_structure", {})
    if not isinstance(layout, dict):
        layout = {}
        ui_config["layout_structure"] = layout

    sidebar = layout.setdefault("sidebar", {})
    if not isinstance(sidebar, dict):
        sidebar = {}
        layout["sidebar"] = sidebar
    sidebar["groups"] = _normalize_sidebar_groups(sidebar.get("groups"))
    sidebar["hidden"] = _clean_string_list(sidebar.get("hidden"))

    tabs = layout.setdefault("tabs", {})
    if not isinstance(tabs, dict):
        tabs = {}
        layout["tabs"] = tabs
    for page_key, items in DEFAULT_TAB_LAYOUTS.items():
        default_order = [item["key"] for item in items]
        page_config = tabs.setdefault(page_key, {})
        if not isinstance(page_config, dict):
            page_config = {}
            tabs[page_key] = page_config
        page_config["order"] = _merge_known_order(page_config.get("order"), default_order)
        page_config["advanced"] = [
            key for key in _clean_string_list(page_config.get("advanced")) if key in default_order
        ]
        page_config["hidden"] = [
            key for key in _clean_string_list(page_config.get("hidden")) if key in default_order
        ]

    button_zones = layout.setdefault("button_zones", {})
    if not isinstance(button_zones, dict):
        button_zones = {}
        layout["button_zones"] = button_zones
    layout["button_zones"] = {
        str(key): str(value)
        for key, value in button_zones.items()
        if str(key or "").strip() and str(value or "").strip()
    }
    layout["hidden_elements"] = _clean_string_list(layout.get("hidden_elements"))
    return layout


def _normalize_sidebar_groups(groups):
    if not isinstance(groups, list):
        groups = copy.deepcopy(DEFAULT_SIDEBAR_GROUPS)

    known_keys = [item["key"] for item in DEFAULT_SIDEBAR_ITEMS]
    used = set()
    normalized = []
    for index, group in enumerate(groups):
        if not isinstance(group, dict):
            continue
        group_id = str(group.get("id") or f"group_{index + 1}").strip() or f"group_{index + 1}"
        label = str(group.get("label") or group_id).strip() or group_id
        items = []
        for key in _clean_string_list(group.get("items")):
            if key in known_keys and key not in used:
                items.append(key)
                used.add(key)
        normalized.append({"id": group_id, "label": label, "items": items})

    missing = [key for key in known_keys if key not in used]
    if missing:
        if normalized:
            normalized[0]["items"].extend(missing)
        else:
            normalized.append({"id": "main", "label": "Principal", "items": missing})
    return normalized


def _clean_string_list(value):
    if not isinstance(value, list):
        return []
    cleaned = []
    for item in value:
        text = str(item or "").strip()
        if text and text not in cleaned:
            cleaned.append(text)
    return cleaned


def _merge_known_order(current_order, default_order):
    current = [key for key in _clean_string_list(current_order) if key in default_order]
    return current + [key for key in default_order if key not in current]


def layout_structure(ui_config):
    return ensure_layout_structure(ui_config or {})


def is_layout_hidden(ui_config, key):
    key = str(key or "")
    layout = layout_structure(ui_config)
    if key in layout.get("hidden_elements", []):
        return True
    if key.startswith("nav_") and key in layout.get("sidebar", {}).get("hidden", []):
        return True
    return False


def normalize_theme(theme):
    base = copy.deepcopy(DEFAULT_UI_CUSTOMIZATION["themes"][DEFAULT_THEME_NAME])
    if isinstance(theme, dict):
        base["description"] = theme.get("description", base["description"])
        base["palette"].update(theme.get("palette") or {})
        base["layout"].update(theme.get("layout") or {})
    return base


def active_theme(ui_config):
    ui_config = ui_config or {}
    themes = ui_config.get("themes") or {}
    name = ui_config.get("active_theme") or DEFAULT_THEME_NAME
    return normalize_theme(themes.get(name) or themes.get(DEFAULT_THEME_NAME) or {})


def is_dark_theme(ui_config):
    palette = active_theme(ui_config).get("palette", {})
    return _color_luminance(palette.get("background", "#ffffff")) < 0.45


def build_application_palette(ui_config):
    palette = active_theme(ui_config).get("palette", {})
    qt_palette = QPalette()
    background = QColor(palette.get("background", "#f5f7f9"))
    surface = QColor(palette.get("surface", "#ffffff"))
    surface_alt = QColor(palette.get("surface_alt", "#eef3f7"))
    text = QColor(palette.get("text", "#1f2933"))
    muted = QColor(palette.get("muted", "#6b7280"))
    border = QColor(palette.get("border", "#d9e1e8"))
    primary = QColor(palette.get("primary", "#007572"))
    selection = QColor(palette.get("selection", "#dff2f1"))

    qt_palette.setColor(QPalette.Window, background)
    qt_palette.setColor(QPalette.WindowText, text)
    qt_palette.setColor(QPalette.Base, surface)
    qt_palette.setColor(QPalette.AlternateBase, surface_alt)
    qt_palette.setColor(QPalette.ToolTipBase, surface_alt)
    qt_palette.setColor(QPalette.ToolTipText, text)
    qt_palette.setColor(QPalette.Text, text)
    qt_palette.setColor(QPalette.Button, surface)
    qt_palette.setColor(QPalette.ButtonText, text)
    qt_palette.setColor(QPalette.BrightText, QColor("#ffffff"))
    qt_palette.setColor(QPalette.Highlight, selection)
    qt_palette.setColor(QPalette.HighlightedText, text)
    qt_palette.setColor(QPalette.PlaceholderText, muted)
    qt_palette.setColor(QPalette.Mid, border)

    for group in (QPalette.Disabled, QPalette.Inactive):
        qt_palette.setColor(group, QPalette.WindowText, muted)
        qt_palette.setColor(group, QPalette.Text, muted)
        qt_palette.setColor(group, QPalette.ButtonText, muted)
        qt_palette.setColor(group, QPalette.Base, surface_alt)
        qt_palette.setColor(group, QPalette.Button, surface_alt)
        qt_palette.setColor(group, QPalette.Highlight, primary)
        qt_palette.setColor(group, QPalette.HighlightedText, text)

    return qt_palette


def build_application_stylesheet(ui_config, zoom_scale=1.0, include_custom=True):
    theme = active_theme(ui_config)
    palette = theme["palette"]
    layout = theme["layout"]
    scale = max(0.5, float(zoom_scale or 1.0))
    font_size = _px(layout.get("font_size", 13), scale)
    button_height = _px(layout.get("button_height", 32), scale)
    input_height = _px(layout.get("input_height", 32), scale)
    row_height = _px(layout.get("table_row_height", 34), scale)
    radius = _px(layout.get("radius", 5), scale)
    container_radius = _px(layout.get("container_radius", 2), scale)
    spacing = _px(layout.get("spacing", 8), scale)

    stylesheet = f"""
    * {{
        color: {palette['text']};
        selection-background-color: {palette['selection']};
        selection-color: {palette['text']};
    }}
    QMainWindow, QDialog, QWidget {{
        background: {palette['background']};
        color: {palette['text']};
        font-size: {font_size}px;
    }}
    QDialog, QMessageBox {{
        background: {palette['background']};
        color: {palette['text']};
    }}
    QLabel {{
        background: transparent;
        color: {palette['text']};
    }}
    QLabel:disabled,
    QPushButton:disabled,
    QLineEdit:disabled,
    QComboBox:disabled,
    QSpinBox:disabled,
    QDoubleSpinBox:disabled,
    QDateEdit:disabled,
    QTimeEdit:disabled,
    QDateTimeEdit:disabled,
    QTextEdit:disabled,
    QPlainTextEdit:disabled {{
        color: {palette['muted']};
    }}
    QDialog#structureDesignerDialog, QWidget#interfaceCustomizationTab {{
        background: {palette['background']};
    }}
    QWidget#main_widget, QStackedWidget, QScrollArea, QAbstractScrollArea {{
        background: {palette['background']};
    }}
    QLabel#pageTitle {{
        color: {palette['text']};
        font-size: {_px(22, scale)}px;
        font-weight: 800;
    }}
    QLabel#sectionTitle {{
        color: {palette['text']};
        font-size: {_px(15, scale)}px;
        font-weight: 700;
    }}
    QLabel#sidebar_group_label {{
        color: {palette['muted']};
        font-size: {_px(12, scale)}px;
        font-weight: 800;
        letter-spacing: 0px;
    }}
    QLabel#mutedLabel,
    QLabel[permission_label="Compte"],
    QLabel[permission_label="Outils"] {{
        color: {palette['muted']};
    }}
    QLabel[ui_element_type="display_field"],
    QLabel#countPill,
    QLabel#profileDescription,
    QLabel#supplierDebtGoldSummary {{
        background: {palette['surface_alt']};
        background-color: {palette['surface_alt']};
        border: 1px solid {palette['border']};
        border-radius: {radius}px;
        color: {palette['text']};
        font-weight: 800;
        padding: 4px 8px;
    }}
    QFrame#panel,
    QWidget[ui_element_type="data_container"],
    QFrame#structureToolbar,
    QGroupBox#supplierSidebarForm {{
        background: {palette['surface']};
        background-color: {palette['surface']};
        border: none;
        border-radius: {container_radius}px;
    }}
    QScrollArea#supplierSidebarScroll {{
        background: transparent;
        border: none;
    }}
    QFrame#footerFrame {{
        background: {palette['surface']};
        background-color: {palette['surface']};
        border-top: 1px solid {palette['border']};
    }}
    QFrame#card {{
        background: {palette['surface']};
        border: none;
        border-radius: {container_radius}px;
    }}
    QFrame#sidebar_container, QWidget#header_container, QWidget#nav_content {{
        background: {palette['sidebar']};
    }}
    QFrame[frameShape="4"], QFrame[frameShape="5"] {{
        color: {palette['border']};
        background: {palette['border']};
    }}
    QPushButton {{
        min-height: {button_height}px;
        border: 1px solid {palette['border']};
        border-radius: {radius}px;
        padding: 4px {spacing}px;
        background: {palette['surface']};
        color: {palette['text']};
        font-weight: 600;
    }}
    QPushButton:hover {{
        background: {palette['surface_alt']};
        border-color: {palette['primary']};
    }}
    QPushButton:pressed, QPushButton:checked {{
        background: {palette['selection']};
        border-color: {palette['primary']};
        color: {palette['text']};
    }}
    QPushButton:disabled {{
        background: {palette['surface_alt']};
        border-color: {palette['border']};
        color: {palette['muted']};
    }}
    QPushButton[class="btn_primary"],
    QPushButton[primary="true"],
    QPushButton[ui_action_zone="primary"],
    QPushButton[permission_key="client_credit_publish"],
    QPushButton[permission_key="supplier_credit_publish"],
    QPushButton[permission_key="supplier_import_publish"],
    QPushButton[permission_key="supplier_payment_post"],
    QPushButton[permission_key="supplier_operation_create"] {{
        background: {palette['primary']};
        background-color: {palette['primary']};
        color: #ffffff;
        border-color: {palette['primary']};
        font-weight: 800;
    }}
    QPushButton[class="btn_primary"]:hover,
    QPushButton[primary="true"]:hover,
    QPushButton[ui_action_zone="primary"]:hover,
    QPushButton[permission_key="client_credit_publish"]:hover,
    QPushButton[permission_key="supplier_credit_publish"]:hover,
    QPushButton[permission_key="supplier_import_publish"]:hover,
    QPushButton[permission_key="supplier_payment_post"]:hover,
    QPushButton[permission_key="supplier_operation_create"]:hover {{
        background: {palette['primary_hover']};
        background-color: {palette['primary_hover']};
        border-color: {palette['primary_hover']};
        color: #ffffff;
    }}
    QPushButton[ui_action_zone="secondary"],
    QPushButton[permission_key="client_credit_create"],
    QPushButton[permission_key="client_credit_update"],
    QPushButton[permission_key="supplier_credit_create"],
    QPushButton[permission_key="supplier_credit_update"],
    QPushButton[permission_key="supplier_import_stage"],
    QPushButton[permission_key="supplier_statement_view"],
    QPushButton[permission_key="supplier_statement_export"],
    QPushButton[permission_key="reports_export"] {{
        background: {palette['surface_alt']};
        background-color: {palette['surface_alt']};
        border-color: {palette['border']};
        color: {palette['text']};
        font-weight: 750;
    }}
    QPushButton[ui_action_zone="tools"],
    QPushButton[permission_key="footer_tools"],
    QPushButton[permission_key="footer_account"] {{
        background: {palette['surface_alt']};
        background-color: {palette['surface_alt']};
        color: {palette['accent']};
        border-color: {palette['accent']};
        font-weight: 750;
    }}
    QPushButton[class="btn_danger"],
    QPushButton[danger="true"],
    QPushButton[ui_action_zone="danger"],
    QPushButton[permission_key="supplier_operation_reverse"],
    QPushButton[permission_key="legacy_credit_reverse"] {{
        background: {palette['surface_alt']};
        background-color: {palette['surface_alt']};
        color: {palette['danger']};
        border-color: {palette['danger']};
        font-weight: 800;
    }}
    QPushButton[class="btn_danger"]:hover,
    QPushButton[danger="true"]:hover,
    QPushButton[ui_action_zone="danger"]:hover,
    QPushButton[permission_key="supplier_operation_reverse"]:hover,
    QPushButton[permission_key="legacy_credit_reverse"]:hover {{
        background: {palette['danger']};
        background-color: {palette['danger']};
        border-color: {palette['danger']};
        color: #ffffff;
    }}
    QPushButton[class="nav_button"] {{
        text-align: left;
        border: none;
        border-radius: {radius}px;
        margin: 2px 8px;
        background: transparent;
    }}
    QPushButton[class="nav_button"]:hover {{
        background: {palette['surface_alt']};
    }}
    QPushButton[class="nav_button"]:checked {{
        background: {palette['selection']};
        color: {palette['primary']};
    }}
    QToolButton {{
        border: 1px solid {palette['border']};
        border-radius: {radius}px;
        background: {palette['surface']};
        color: {palette['text']};
        padding: 4px;
    }}
    QToolButton:hover, QToolButton:checked {{
        background: {palette['surface_alt']};
        border-color: {palette['primary']};
    }}
    QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox,
    QDateEdit, QTimeEdit, QDateTimeEdit {{
        min-height: {input_height}px;
        border: 1px solid {palette['border']};
        border-radius: {radius}px;
        padding: 3px 7px;
        background: {palette['surface']};
        background-color: {palette['surface']};
        color: {palette['text']};
        selection-background-color: {palette['selection']};
        selection-color: {palette['text']};
    }}
    QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus,
    QSpinBox:focus, QDoubleSpinBox:focus, QDateEdit:focus, QTimeEdit:focus, QDateTimeEdit:focus {{
        background: {palette['surface']};
        background-color: {palette['surface']};
        color: {palette['text']};
        border-color: {palette['primary']};
    }}
    QLineEdit:disabled, QTextEdit:disabled, QPlainTextEdit:disabled, QComboBox:disabled,
    QSpinBox:disabled, QDoubleSpinBox:disabled, QDateEdit:disabled, QTimeEdit:disabled, QDateTimeEdit:disabled {{
        background: {palette['surface_alt']};
        background-color: {palette['surface_alt']};
        color: {palette['muted']};
    }}
    QComboBox::drop-down,
    QAbstractSpinBox::up-button,
    QAbstractSpinBox::down-button {{
        background: {palette['surface_alt']};
        border: none;
        border-left: 1px solid {palette['border']};
        width: {_px(24, scale)}px;
    }}
    QComboBox QAbstractItemView,
    QAbstractItemView {{
        background: {palette['surface']};
        background-color: {palette['surface']};
        border: 1px solid {palette['border']};
        color: {palette['text']};
        selection-background-color: {palette['selection']};
        selection-color: {palette['text']};
        outline: none;
    }}
    QAbstractItemView::item:hover {{
        background: {palette['surface_alt']};
    }}
    QGroupBox {{
        background: {palette['surface']};
        border: none;
        border-radius: {container_radius}px;
        margin-top: 12px;
        padding: {spacing}px;
        font-weight: 700;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 10px;
        padding: 0 4px;
        color: {palette['text']};
    }}
    QTableWidget, QTableView, QTreeWidget, QListWidget {{
        background: {palette['surface']};
        alternate-background-color: {palette['background']};
        border: none;
        border-radius: {container_radius}px;
        selection-background-color: {palette['selection']};
        selection-color: {palette['text']};
        gridline-color: {palette['border']};
    }}
    QTableView::item, QTableWidget::item, QTreeWidget::item {{
        min-height: {row_height}px;
    }}
    QTableView::item:hover, QTableWidget::item:hover, QTreeWidget::item:hover, QListWidget::item:hover {{
        background: {palette['surface_alt']};
    }}
    QTableView::item:selected, QTableWidget::item:selected, QTreeWidget::item:selected, QListWidget::item:selected {{
        background: {palette['selection']};
        color: {palette['text']};
    }}
    QHeaderView::section {{
        background: {palette['surface_alt']};
        color: {palette['text']};
        border: none;
        border-right: 1px solid {palette['border']};
        padding: 6px;
        font-weight: 700;
    }}
    QTableCornerButton::section {{
        background: {palette['surface_alt']};
        border: 1px solid {palette['border']};
    }}
    QTabWidget::pane {{
        border: none;
        background: {palette['surface']};
        border-radius: {container_radius}px;
    }}
    QTabBar::tab {{
        background: {palette['surface_alt']};
        color: {palette['text']};
        padding: 8px 14px;
        margin-right: 2px;
        border-top-left-radius: {radius}px;
        border-top-right-radius: {radius}px;
    }}
    QTabBar::tab:selected {{
        background: {palette['surface']};
        color: {palette['primary']};
        border-top: 2px solid {palette['primary']};
        font-weight: 700;
    }}
    QMenu {{
        background: {palette['surface']};
        border: 1px solid {palette['border']};
        border-radius: {radius}px;
        color: {palette['text']};
        padding: 5px;
    }}
    QMenu::item {{
        color: {palette['text']};
        padding: 7px 28px 7px 24px;
        border-radius: {radius}px;
    }}
    QMenu::item:selected {{
        background: {palette['selection']};
        color: {palette['text']};
    }}
    QMenu::separator {{
        background: {palette['border']};
        height: 1px;
        margin: 5px 8px;
    }}
    QToolTip {{
        background: {palette['surface_alt']};
        border: 1px solid {palette['border']};
        border-radius: {radius}px;
        color: {palette['text']};
        padding: 6px 8px;
    }}
    QCheckBox, QRadioButton {{
        background: transparent;
        color: {palette['text']};
        spacing: {spacing}px;
    }}
    QCheckBox::indicator, QRadioButton::indicator {{
        background: {palette['surface']};
        border: 1px solid {palette['border']};
        height: {_px(16, scale)}px;
        width: {_px(16, scale)}px;
    }}
    QCheckBox::indicator {{
        border-radius: {_px(4, scale)}px;
    }}
    QRadioButton::indicator {{
        border-radius: {_px(8, scale)}px;
    }}
    QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
        background: {palette['primary']};
        border-color: {palette['primary']};
    }}
    QSlider::groove:horizontal {{
        background: {palette['border']};
        border-radius: {_px(3, scale)}px;
        height: {_px(6, scale)}px;
    }}
    QSlider::handle:horizontal {{
        background: {palette['primary']};
        border: 2px solid {palette['surface']};
        border-radius: {_px(8, scale)}px;
        margin: -5px 0px;
        width: {_px(16, scale)}px;
    }}
    QProgressBar {{
        background: {palette['surface_alt']};
        border: 1px solid {palette['border']};
        border-radius: {radius}px;
        color: {palette['text']};
        font-weight: 700;
        text-align: center;
    }}
    QProgressBar::chunk {{
        background: {palette['primary']};
        border-radius: {radius}px;
    }}
    QScrollBar:vertical {{
        background: {palette['surface_alt']};
        border: none;
        border-radius: {_px(5, scale)}px;
        margin: 0px;
        width: {_px(10, scale)}px;
    }}
    QScrollBar::handle:vertical {{
        background: {palette['border']};
        border-radius: {_px(5, scale)}px;
        min-height: {_px(26, scale)}px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {palette['primary']};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
    QScrollBar:horizontal {{
        background: {palette['surface_alt']};
        border: none;
        border-radius: {_px(5, scale)}px;
        height: {_px(10, scale)}px;
        margin: 0px;
    }}
    QScrollBar::handle:horizontal {{
        background: {palette['border']};
        border-radius: {_px(5, scale)}px;
        min-width: {_px(26, scale)}px;
    }}
    QScrollBar::handle:horizontal:hover {{
        background: {palette['primary']};
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0px;
    }}
    QCalendarWidget QWidget {{
        background: {palette['surface']};
        color: {palette['text']};
    }}
    QCalendarWidget QToolButton {{
        background: {palette['surface_alt']};
        color: {palette['text']};
        border: 1px solid {palette['border']};
    }}
    QCalendarWidget QMenu {{
        background: {palette['surface']};
        color: {palette['text']};
    }}
    QSplitter::handle {{
        background: {palette['border']};
    }}
    QSplitter::handle:hover {{
        background: {palette['primary']};
    }}
    QStatusBar {{
        background: {palette['surface']};
        color: {palette['text']};
        border-top: 1px solid {palette['border']};
    }}
    """
    if include_custom:
        custom_qss = str((ui_config or {}).get("custom_qss") or "").strip()
        if custom_qss:
            custom_qss = _flatten_inline_container_stylesheet(None, custom_qss, ui_config)
            if is_dark_theme(ui_config):
                custom_qss = adapt_inline_stylesheet_for_theme(custom_qss, ui_config)
            stylesheet = f"{stylesheet}\n\n/* User custom QSS */\n{custom_qss}"
    stylesheet = f"""
    {stylesheet}

    /* Dialog theme safeguard: keep top-level dialogs off the OS dark palette. */
    QDialog, QMessageBox {{
        background: {palette['background']};
        color: {palette['text']};
    }}
    QDialog QLabel, QMessageBox QLabel {{
        color: {palette['text']};
    }}
    """
    return stylesheet


def apply_control_override(control, override):
    if not isinstance(override, dict):
        return

    try:
        if not override:
            if control.property(_CONTROL_APPLIED_PROP):
                _restore_control_state(control)
                control.setProperty(_CONTROL_APPLIED_PROP, False)
            return

        _ensure_control_base_state(control)

        if "visible" in override:
            control.setVisible(bool(override.get("visible")))
        else:
            _restore_control_field(control, "visible")

        if "enabled" in override:
            control.setEnabled(bool(override.get("enabled")))
        else:
            _restore_control_field(control, "enabled")

        text = str(override.get("text") or "").strip()
        if text and hasattr(control, "setText"):
            control.setText(text)
        elif hasattr(control, "setText"):
            _restore_control_field(control, "text")

        tooltip = str(override.get("tooltip") or "").strip()
        if tooltip and hasattr(control, "setToolTip"):
            control.setToolTip(tooltip)
        elif hasattr(control, "setToolTip"):
            _restore_control_field(control, "tooltip")

        _restore_control_field(control, "minimum_width")
        _restore_control_field(control, "minimum_height")
        _restore_control_field(control, "style_sheet")

        control.setProperty(_CONTROL_APPLIED_PROP, True)
    except RuntimeError:
        return


def apply_table_column_override(table, column, override):
    if not isinstance(override, dict):
        return
    try:
        if not override:
            if _column_applied(table, column):
                _restore_column_state(table, column)
                _set_column_applied(table, column, False)
            return

        _ensure_column_base_state(table, column)

        if "visible" in override:
            table.setColumnHidden(column, not bool(override.get("visible")))
        else:
            _restore_column_field(table, column, "hidden")

        _restore_column_field(table, column, "width")

        label = str(override.get("text") or "").strip()
        if label:
            _set_header_label(table, column, label)
        else:
            _restore_column_field(table, column, "label")

        _set_column_applied(table, column, True)
    except RuntimeError:
        return


def _ensure_control_base_state(control):
    if control.property(_CONTROL_BASE_PROP):
        return
    base = {}
    if hasattr(control, "isVisible"):
        base["visible"] = control.isVisible()
    if hasattr(control, "isEnabled"):
        base["enabled"] = control.isEnabled()
    if hasattr(control, "text"):
        base["text"] = control.text()
    if hasattr(control, "toolTip"):
        base["tooltip"] = control.toolTip()
    if hasattr(control, "minimumWidth"):
        base["minimum_width"] = control.minimumWidth()
    if hasattr(control, "minimumHeight"):
        base["minimum_height"] = control.minimumHeight()
    if hasattr(control, "styleSheet"):
        base["style_sheet"] = control.styleSheet()
    control.setProperty(_CONTROL_BASE_PROP, base)


def _restore_control_state(control):
    for field in ("visible", "enabled", "text", "tooltip", "minimum_width", "minimum_height", "style_sheet"):
        _restore_control_field(control, field)


def _restore_control_field(control, field):
    base = control.property(_CONTROL_BASE_PROP) or {}
    if field not in base:
        return
    value = base[field]
    if field == "visible" and hasattr(control, "setVisible"):
        control.setVisible(bool(value))
    elif field == "enabled" and hasattr(control, "setEnabled"):
        control.setEnabled(bool(value))
    elif field == "text" and hasattr(control, "setText"):
        control.setText(str(value))
    elif field == "tooltip" and hasattr(control, "setToolTip"):
        control.setToolTip(str(value))
    elif field == "minimum_width" and hasattr(control, "setMinimumWidth"):
        control.setMinimumWidth(int(value))
    elif field == "minimum_height" and hasattr(control, "setMinimumHeight"):
        control.setMinimumHeight(int(value))
    elif field == "style_sheet" and hasattr(control, "setStyleSheet"):
        control.setStyleSheet(str(value))


def _ensure_column_base_state(table, column):
    column_key = str(column)
    base_map = dict(table.property(_COLUMN_BASE_PROP) or {})
    if column_key in base_map:
        return
    base_map[column_key] = {
        "hidden": table.isColumnHidden(column) if hasattr(table, "isColumnHidden") else False,
        "width": table.columnWidth(column) if hasattr(table, "columnWidth") else 0,
        "label": _header_label(table, column),
    }
    table.setProperty(_COLUMN_BASE_PROP, base_map)


def _restore_column_state(table, column):
    for field in ("hidden", "width", "label"):
        _restore_column_field(table, column, field)


def _restore_column_field(table, column, field):
    base_map = table.property(_COLUMN_BASE_PROP) or {}
    state = base_map.get(str(column)) or {}
    if field not in state:
        return
    value = state[field]
    if field == "hidden" and hasattr(table, "setColumnHidden"):
        table.setColumnHidden(column, bool(value))
    elif field == "width" and int(value) > 0 and hasattr(table, "setColumnWidth"):
        table.setColumnWidth(column, int(value))
    elif field == "label":
        _set_header_label(table, column, str(value))


def _column_applied(table, column):
    applied = table.property(_COLUMN_APPLIED_PROP) or {}
    return bool(applied.get(str(column)))


def _set_column_applied(table, column, value):
    applied = dict(table.property(_COLUMN_APPLIED_PROP) or {})
    applied[str(column)] = bool(value)
    table.setProperty(_COLUMN_APPLIED_PROP, applied)


def _set_header_label(table, column, label):
    if isinstance(table, QTableWidget):
        item = table.horizontalHeaderItem(column)
        if item is not None:
            item.setText(label)
            return
    if isinstance(table, QTreeWidget):
        item = table.headerItem()
        if item is not None:
            item.setText(column, label)
            return
    model = table.model() if hasattr(table, "model") else None
    if model is not None and hasattr(model, "setHeaderData"):
        model.setHeaderData(column, Qt.Horizontal, label)


def _header_label(table, column):
    if isinstance(table, QTableWidget):
        item = table.horizontalHeaderItem(column)
        if item is not None:
            return item.text()
    if isinstance(table, QTreeWidget):
        item = table.headerItem()
        if item is not None:
            return item.text(column)
    model = table.model() if hasattr(table, "model") else None
    if model is not None and hasattr(model, "headerData"):
        value = model.headerData(column, Qt.Horizontal)
        return "" if value is None else str(value)
    return ""


def adapt_inline_stylesheet_for_theme(stylesheet, ui_config):
    stylesheet = str(stylesheet or "")
    if not stylesheet or not is_dark_theme(ui_config):
        return stylesheet

    palette = active_theme(ui_config).get("palette", {})
    border = palette.get("border", "#354655")
    text = palette.get("text", "#eef4f8")
    replacements = _dark_background_replacements(palette)

    def replace_background_declaration(match):
        prop = match.group("prop")
        value = match.group("value")
        adapted = _adapt_dark_background_value(prop, value, palette, replacements)
        return f"{prop}: {adapted}"

    stylesheet = re.sub(
        r"(?P<prop>\b(?:alternate-background-color|selection-background-color|background(?:-color)?))\s*:\s*(?P<value>[^;}]+)",
        replace_background_declaration,
        stylesheet,
        flags=re.IGNORECASE,
    )

    stylesheet = re.sub(
        r"(?P<prefix>(?:^|[;{]\s*))(?P<prop>color)\s*:\s*(?P<value>black|#000000|#000|#2c3e50|#34495e)\b",
        lambda match: f"{match.group('prefix')}{match.group('prop')}: {text}",
        stylesheet,
        flags=re.IGNORECASE,
    )

    for light_border in (
        "#bdc3c7",
        "#ced4da",
        "#d9e1e8",
        "#dcdde1",
        "#dee2e6",
        "#e0e0e0",
        "#e0e6ed",
        "#eeeeee",
        "#eee",
        "#dddddd",
        "#ddd",
        "#f0f0f0",
    ):
        stylesheet = re.sub(re.escape(light_border), border, stylesheet, flags=re.IGNORECASE)

    return stylesheet


def _dark_background_replacements(palette):
    surface = palette.get("surface", "#17222c")
    surface_alt = palette.get("surface_alt", "#22303d")
    background = palette.get("background", "#111820")
    return {
        "white": surface,
        "whitesmoke": surface_alt,
        "snow": surface_alt,
        "#fff": surface,
        "#ffffff": surface,
        "#fcfcfc": surface,
        "#fdfdfd": surface,
        "#fafafa": surface_alt,
        "#f9f9f9": surface_alt,
        "#f8fbff": surface_alt,
        "#f8f9fa": surface_alt,
        "#f6f8fa": surface_alt,
        "#f5fbff": surface_alt,
        "#f5f7f9": background,
        "#f5f5f5": surface_alt,
        "#f4f7fa": background,
        "#f4f6f9": background,
        "#f4f6f7": surface_alt,
        "#f4ecf8": surface_alt,
        "#f1f8ff": surface_alt,
        "#f1f3f5": surface_alt,
        "#f1f2f6": surface_alt,
        "#f0f8ff": surface_alt,
        "#f0f0f0": surface_alt,
        "#eef3f7": surface_alt,
        "#eef2f5": surface_alt,
        "#ecf0f1": surface_alt,
        "#ebf5fb": surface_alt,
        "#ebdef0": surface_alt,
        "#eafaf1": surface_alt,
        "#e8f8f5": surface_alt,
        "#e8f6f3": surface_alt,
        "#e2e6ea": surface_alt,
        "#dfe4ea": surface_alt,
        "#d6eaf8": surface_alt,
        "#d4efdf": surface_alt,
        "#fdedec": surface_alt,
        "#fdf2e9": surface_alt,
        "#fef9e7": surface_alt,
        "#fffaf0": surface_alt,
        "#fff8e1": surface_alt,
        "#fff3e0": surface_alt,
        "#ffebee": surface_alt,
        "#fadbd8": surface_alt,
    }


def _adapt_dark_background_value(prop, value, palette, replacements):
    raw = str(value or "").strip()
    lowered = raw.lower()
    if not raw or lowered in {"none", "transparent"}:
        return raw

    if "selection-background" in prop.lower():
        selection = palette.get("selection", "#204f55")
        return _replace_light_color_tokens(raw, replacements, selection)

    exact = replacements.get(lowered)
    if exact:
        return exact

    return _replace_light_color_tokens(raw, replacements, palette.get("surface_alt", "#22303d"))


def _replace_light_color_tokens(value, replacements, fallback):
    def replace_named(match):
        token = match.group(0)
        return replacements.get(token.lower(), token)

    value = re.sub(r"\b(?:white|whitesmoke|snow)\b", replace_named, value, flags=re.IGNORECASE)

    def replace_hex(match):
        token = match.group(0)
        lowered = token.lower()
        if lowered in replacements:
            return replacements[lowered]
        if _color_luminance(lowered) > 0.78:
            return fallback
        return token

    value = re.sub(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})\b", replace_hex, value)

    def replace_rgb(match):
        token = match.group(0)
        parts = [float(match.group(name)) for name in ("r", "g", "b")]
        alpha = match.group("a")
        if alpha is not None and float(alpha) <= 0.05:
            return token
        color = QColor(int(parts[0]), int(parts[1]), int(parts[2]))
        return fallback if _color_luminance(color.name()) > 0.78 else token

    return re.sub(
        r"rgba?\(\s*(?P<r>\d{1,3})\s*,\s*(?P<g>\d{1,3})\s*,\s*(?P<b>\d{1,3})(?:\s*,\s*(?P<a>0(?:\.\d+)?|1(?:\.0+)?))?\s*\)",
        replace_rgb,
        value,
        flags=re.IGNORECASE,
    )


def sync_application_inline_styles(app, ui_config):
    if app is None:
        return
    style_filter = getattr(app, _INLINE_THEME_FILTER_ATTR, None)
    if style_filter is None:
        style_filter = _InlineThemeEventFilter(app)
        setattr(app, _INLINE_THEME_FILTER_ATTR, style_filter)
        app.installEventFilter(style_filter)
    style_filter.set_ui_config(ui_config)
    for widget in list(app.allWidgets()):
        _sync_widget_inline_styles(widget, ui_config)


def _adapt_inline_stylesheet_for_widget(widget, stylesheet, ui_config):
    adapted = _flatten_inline_container_stylesheet(widget, stylesheet, ui_config)
    if is_dark_theme(ui_config):
        adapted = adapt_inline_stylesheet_for_theme(adapted, ui_config)
        adapted = _add_input_inline_theme_safeguard(widget, adapted, ui_config)
    return adapted


def _flatten_inline_container_stylesheet(widget, stylesheet, ui_config):
    stylesheet = str(stylesheet or "")
    if not stylesheet:
        return stylesheet

    radius = _inline_container_radius(ui_config)
    if "{" not in stylesheet or "}" not in stylesheet:
        if _is_inline_container_widget(widget):
            return _flatten_inline_container_declarations(stylesheet, radius)
        return stylesheet

    def replace_rule(match):
        selectors = match.group("selectors")
        body = match.group("body")
        if not _selector_targets_container_surface(selectors):
            return match.group(0)
        return f"{selectors}{{{_flatten_inline_container_declarations(body, radius)}}}"

    return _INLINE_QSS_RULE_RE.sub(replace_rule, stylesheet)


def _inline_container_radius(ui_config):
    layout = active_theme(ui_config or {}).get("layout", {})
    return max(0, int(float(layout.get("container_radius", 2) or 2)))


def _is_inline_container_widget(widget):
    if isinstance(widget, (QFrame, QGroupBox, QTableWidget, QTableView, QTreeWidget, QListWidget, QTabWidget)):
        return True
    try:
        if str(widget.property("ui_element_type") or "") == "data_container":
            return True
        return str(widget.objectName() or "") in _INLINE_CONTAINER_OBJECT_NAMES
    except RuntimeError:
        return False


def _selector_targets_container_surface(selectors):
    for selector in str(selectors or "").split(","):
        target = re.split(r"\s+|>", selector.strip())[-1]
        if not target:
            continue
        if _INLINE_CONTAINER_SELECTOR_RE.search(target):
            return True
        if _INLINE_DATA_CONTAINER_SELECTOR_RE.search(target):
            return True
        if any(f"#{name}" in target for name in _INLINE_CONTAINER_OBJECT_NAMES):
            return True
    return False


def _flatten_inline_container_declarations(body, radius):
    body = re.sub(
        r"\bborder(?:-(?:top|right|bottom|left))?(?:-(?:left|right))?-radius\s*:\s*[^;}]+",
        f"border-radius: {radius}px",
        str(body or ""),
        flags=re.IGNORECASE,
    )
    body = re.sub(
        r"\bborder(?:-(?:top|right|bottom|left))?\s*:\s*[^;}]+",
        "border: none",
        body,
        flags=re.IGNORECASE,
    )
    body = re.sub(
        r"\bborder(?:-(?:top|right|bottom|left))?-width\s*:\s*[^;}]+",
        "border-width: 0px",
        body,
        flags=re.IGNORECASE,
    )
    body = re.sub(
        r"\bborder(?:-(?:top|right|bottom|left))?-style\s*:\s*[^;}]+",
        "border-style: none",
        body,
        flags=re.IGNORECASE,
    )
    return re.sub(
        r"\bborder(?:-(?:top|right|bottom|left))?-color\s*:\s*[^;}]+",
        "border-color: transparent",
        body,
        flags=re.IGNORECASE,
    )


class _InlineThemeEventFilter(QObject):
    def __init__(self, app):
        super().__init__(app)
        self._ui_config = {}

    def set_ui_config(self, ui_config):
        self._ui_config = ui_config or {}

    def eventFilter(self, obj, event):
        event_type = event.type()
        if event_type in (QEvent.Show, QEvent.Polish):
            _sync_widget_inline_styles(obj, self._ui_config)
        elif event_type == QEvent.StyleChange:
            if isinstance(obj, QWidget) and not bool(obj.property(_INLINE_THEME_SYNCING_PROP)):
                _apply_inline_stylesheet_theme(obj, self._ui_config)
        elif event_type == QEvent.ChildAdded:
            child = event.child()
            _sync_widget_inline_styles(child, self._ui_config)
        return False


def _sync_widget_inline_styles(widget, ui_config):
    if not isinstance(widget, QWidget):
        return
    widgets = [widget]
    try:
        widgets.extend(widget.findChildren(QWidget))
    except RuntimeError:
        return
    for current in widgets:
        _apply_inline_stylesheet_theme(current, ui_config)


def _apply_inline_stylesheet_theme(widget, ui_config):
    if not hasattr(widget, "styleSheet") or not hasattr(widget, "setStyleSheet"):
        return
    try:
        current = str(widget.styleSheet() or "")
        applied = bool(widget.property(_INLINE_THEME_APPLIED_PROP))
        original = widget.property(_INLINE_THEME_ORIGINAL_PROP)
        last_expected = widget.property(_INLINE_THEME_EXPECTED_PROP)

        if not current and not applied:
            return

        source = str(original or "") if applied else current
        if applied and last_expected is not None and current != str(last_expected):
            source = current

        adapted = _adapt_inline_stylesheet_for_widget(widget, source, ui_config)
        transformed = adapted != source
        if current == adapted:
            if transformed:
                widget.setProperty(_INLINE_THEME_ORIGINAL_PROP, source)
                widget.setProperty(_INLINE_THEME_APPLIED_PROP, True)
                widget.setProperty(_INLINE_THEME_EXPECTED_PROP, adapted)
            else:
                widget.setProperty(_INLINE_THEME_ORIGINAL_PROP, None)
                widget.setProperty(_INLINE_THEME_APPLIED_PROP, False)
                widget.setProperty(_INLINE_THEME_EXPECTED_PROP, None)
            return
        if transformed:
            widget.setProperty(_INLINE_THEME_ORIGINAL_PROP, source)
            widget.setProperty(_INLINE_THEME_APPLIED_PROP, True)
            widget.setProperty(_INLINE_THEME_EXPECTED_PROP, adapted)
        else:
            widget.setProperty(_INLINE_THEME_ORIGINAL_PROP, None)
            widget.setProperty(_INLINE_THEME_APPLIED_PROP, False)
            widget.setProperty(_INLINE_THEME_EXPECTED_PROP, None)
        if current != adapted:
            try:
                widget.setProperty(_INLINE_THEME_SYNCING_PROP, True)
                widget.setStyleSheet(adapted)
            finally:
                widget.setProperty(_INLINE_THEME_SYNCING_PROP, False)
    except RuntimeError:
        return


def _add_input_inline_theme_safeguard(widget, stylesheet, ui_config):
    if not is_dark_theme(ui_config) or not _is_input_widget(widget):
        return stylesheet

    palette = active_theme(ui_config).get("palette", {})
    surface = palette.get("surface", "#17222c")
    surface_alt = palette.get("surface_alt", "#22303d")
    text = palette.get("text", "#eef4f8")
    muted = palette.get("muted", "#a8b5c2")
    border = palette.get("border", "#354655")
    primary = palette.get("primary", "#33c7b8")
    selection = palette.get("selection", "#204f55")
    selector = _input_widget_selector(widget)

    declarations = (
        f"background-color: {surface}; "
        f"background: {surface}; "
        f"color: {text}; "
        f"border-color: {border}; "
        f"selection-background-color: {selection}; "
        f"selection-color: {text};"
    )
    focus_declarations = (
        f"background-color: {surface}; "
        f"background: {surface}; "
        f"color: {text}; "
        f"border-color: {primary};"
    )
    disabled_declarations = (
        f"background-color: {surface_alt}; "
        f"background: {surface_alt}; "
        f"color: {muted};"
    )

    if "{" in stylesheet:
        safeguard = (
            f"\n{selector} {{ {declarations} }}\n"
            f"{selector}:focus {{ {focus_declarations} }}\n"
            f"{selector}:disabled {{ {disabled_declarations} }}"
        )
    else:
        safeguard = f"\n{declarations}"

    if safeguard.strip() in stylesheet:
        return stylesheet
    return f"{stylesheet.rstrip()}{safeguard}"


def _is_input_widget(widget):
    return isinstance(widget, _THEMED_INPUT_WIDGETS)


def _input_widget_selector(widget):
    if isinstance(widget, QDoubleSpinBox):
        return "QDoubleSpinBox"
    if isinstance(widget, QSpinBox):
        return "QSpinBox"
    if isinstance(widget, QAbstractSpinBox):
        return "QAbstractSpinBox"
    if isinstance(widget, QComboBox):
        return "QComboBox"
    if isinstance(widget, QLineEdit):
        return "QLineEdit"
    if isinstance(widget, QTextEdit):
        return "QTextEdit"
    if isinstance(widget, QPlainTextEdit):
        return "QPlainTextEdit"
    if isinstance(widget, QDateEdit):
        return "QDateEdit"
    if isinstance(widget, QTimeEdit):
        return "QTimeEdit"
    if isinstance(widget, QDateTimeEdit):
        return "QDateTimeEdit"
    return widget.metaObject().className() if hasattr(widget, "metaObject") else "QWidget"


_THEMED_INPUT_WIDGETS = (
    QLineEdit,
    QTextEdit,
    QPlainTextEdit,
    QComboBox,
    QAbstractSpinBox,
    QDateEdit,
    QTimeEdit,
    QDateTimeEdit,
)


def _color_luminance(value):
    color = QColor(str(value or "#ffffff"))
    if not color.isValid():
        return 1.0
    channels = []
    for component in (color.redF(), color.greenF(), color.blueF()):
        if component <= 0.03928:
            channels.append(component / 12.92)
        else:
            channels.append(((component + 0.055) / 1.055) ** 2.4)
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def _px(value, scale):
    return max(1, int(float(value) * scale))
