"""Helpers for keeping top-level dialogs on the application theme."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QWidget

from ui.ui_customization import active_theme, build_application_stylesheet


def apply_dialog_theme(dialog, parent=None, object_name=None, extra_stylesheet=""):
    if dialog is None:
        return

    if object_name and not dialog.objectName():
        dialog.setObjectName(object_name)
    dialog.setAttribute(Qt.WA_StyledBackground, True)

    host = _find_customization_host(parent or dialog.parentWidget())
    ui_config = _host_ui_config(host)
    zoom_scale = getattr(host, "zoom_scale", 1.0) if host is not None else 1.0

    parts = []
    app = QApplication.instance()
    app_stylesheet = app.styleSheet() if app is not None else ""
    if app_stylesheet:
        parts.append(app_stylesheet)
    elif ui_config is not None:
        parts.append(build_application_stylesheet(ui_config, zoom_scale))

    parent_stylesheet = _safe_stylesheet(parent)
    if parent_stylesheet and parent_stylesheet not in parts:
        parts.append(parent_stylesheet)

    parts.append(_dialog_safeguard_stylesheet(ui_config, dialog.objectName()))
    if extra_stylesheet:
        parts.append(str(extra_stylesheet))

    dialog.setStyleSheet("\n".join(part for part in parts if part))


def _find_customization_host(widget):
    current = widget if isinstance(widget, QWidget) else None
    visited = set()
    while current is not None and id(current) not in visited:
        visited.add(id(current))
        if hasattr(current, "get_ui_customization_config"):
            return current
        window = current.window()
        if window is not None and window is not current and hasattr(window, "get_ui_customization_config"):
            return window
        current = current.parentWidget()
    return None


def _host_ui_config(host):
    if host is None or not hasattr(host, "get_ui_customization_config"):
        return None
    try:
        return host.get_ui_customization_config()
    except Exception:
        return None


def _safe_stylesheet(widget):
    if widget is None or not hasattr(widget, "styleSheet"):
        return ""
    try:
        return widget.styleSheet()
    except RuntimeError:
        return ""


def _dialog_safeguard_stylesheet(ui_config, object_name):
    theme = active_theme(ui_config or {})
    palette = theme.get("palette", {})
    layout = theme.get("layout", {})
    background = palette.get("background", "#f5f7f9")
    surface = palette.get("surface", "#ffffff")
    surface_alt = palette.get("surface_alt", "#eef3f7")
    text = palette.get("text", "#1f2933")
    muted = palette.get("muted", "#6b7280")
    border = palette.get("border", "#d9e1e8")
    primary = palette.get("primary", "#007572")
    selection = palette.get("selection", "#dff2f1")
    danger = palette.get("danger", "#b42318")
    radius = int(layout.get("radius", 5) or 5)
    container_radius = int(layout.get("container_radius", 2) or 2)

    selector = f"QDialog#{object_name}" if object_name else "QDialog"
    return f"""
    {selector} {{
        background: {background};
        color: {text};
    }}
    {selector} QWidget {{
        background: transparent;
        color: {text};
    }}
    {selector} QDialogButtonBox,
    {selector} QCheckBox,
    {selector} QRadioButton {{
        background: transparent;
        color: {text};
    }}
    {selector} QLabel {{
        color: {text};
        background: transparent;
    }}
    {selector} QLabel#mutedLabel {{
        color: {muted};
    }}
    {selector} QLabel#sectionTitle,
    {selector} QLabel#pageTitle {{
        color: {text};
        font-weight: 700;
    }}
    {selector} QLabel#countPill {{
        background: {surface_alt};
        color: {text};
        border: 1px solid {border};
        border-radius: {radius}px;
        padding: 4px 8px;
        font-weight: 700;
    }}
    {selector} QFrame#panel,
    {selector} QGroupBox {{
        background: {surface};
        border: none;
        border-radius: {container_radius}px;
    }}
    {selector} QLineEdit,
    {selector} QTextEdit,
    {selector} QPlainTextEdit,
    {selector} QComboBox,
    {selector} QSpinBox,
    {selector} QDoubleSpinBox,
    {selector} QDateEdit {{
        background: {surface};
        color: {text};
        border: 1px solid {border};
        border-radius: {radius}px;
        selection-background-color: {selection};
        selection-color: {text};
    }}
    {selector} QTreeWidget,
    {selector} QTableWidget,
    {selector} QTableView,
    {selector} QListWidget {{
        background: {surface};
        alternate-background-color: {background};
        color: {text};
        border: none;
        border-radius: {container_radius}px;
        selection-background-color: {selection};
        selection-color: {text};
        gridline-color: {border};
    }}
    {selector} QHeaderView::section {{
        background: {surface_alt};
        color: {text};
        border: none;
        border-right: 1px solid {border};
        padding: 6px;
        font-weight: 700;
    }}
    {selector} QPushButton {{
        background: {surface};
        color: {text};
        border: 1px solid {border};
        border-radius: {radius}px;
        padding: 5px 10px;
        font-weight: 600;
    }}
    {selector} QPushButton:hover {{
        background: {surface_alt};
        border-color: {primary};
    }}
    {selector} QPushButton[primary="true"] {{
        background: {primary};
        color: #ffffff;
        border-color: {primary};
    }}
    {selector} QPushButton[danger="true"] {{
        color: {danger};
        border-color: {danger};
    }}
    """
