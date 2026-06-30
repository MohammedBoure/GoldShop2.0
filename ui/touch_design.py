"""Touch design defaults shared by dialogs and touch-first workflows."""

from __future__ import annotations

from typing import Mapping, Optional

from PySide6.QtCore import QEvent, QObject, QSize, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QAbstractSpinBox,
    QComboBox,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QWidget,
)

from ui.tools.touch_scroll_filter import configure_touch_scroll


TOUCH_BUTTON_HEIGHT = 48
TOUCH_INPUT_HEIGHT = 46
TOUCH_TABLE_ROW_HEIGHT = 42
TOUCH_TABLE_HEADER_HEIGHT = 40
TOUCH_DIALOG_MARGIN = 16
TOUCH_DIALOG_SPACING = 12
TOUCH_FONT_SIZE = 14
TOUCH_HEADER_FONT_SIZE = 13
TOUCH_ICON_SIZE = 22

TOUCH_COLORS = {
    "primary": "#0f8f83",
    "primary_pressed": "#0b776d",
    "success": "#27ae60",
    "warning": "#f39c12",
    "danger": "#e74c3c",
    "surface": "#ffffff",
    "surface_alt": "#f7f9fb",
    "border": "#cbd5df",
    "text": "#24313f",
}

TOUCH_MODE_CONFIG_KEY = "touch_mode"
TOUCH_APPLIED_PROPERTY = "_goldshop_touch_defaults_applied"
TOUCH_MIN_HEIGHT_PROPERTY = "_goldshop_touch_min_height"
TOUCH_MIN_HEIGHT_FILTER_PROPERTY = "_goldshop_touch_min_height_filter"
_QWIDGETSIZE_MAX = 16777215


class _TouchMinimumHeightFilter(QObject):
    def eventFilter(self, obj, event):
        if event.type() in (QEvent.Polish, QEvent.Show, QEvent.StyleChange, QEvent.FontChange):
            height = obj.property(TOUCH_MIN_HEIGHT_PROPERTY)
            try:
                height = int(height or 0)
            except (TypeError, ValueError):
                height = 0
            if height > 0:
                _ensure_minimum_height(obj, height)
        return False


def is_touch_mode_enabled(config: Optional[Mapping[str, object]] = None) -> bool:
    """Return whether touch defaults should be used for an optional config map."""
    if config is None:
        return True
    value = config.get(TOUCH_MODE_CONFIG_KEY, True)
    if isinstance(value, str):
        return value.strip().casefold() not in {"0", "false", "no", "off"}
    return bool(value)


def _ensure_minimum_height(widget: QWidget, height: int) -> None:
    if height <= 0:
        return

    fixed_height = widget.minimumHeight() == widget.maximumHeight()
    if fixed_height and widget.maximumHeight() < height:
        widget.setFixedHeight(height)
        return

    if widget.minimumHeight() < height:
        widget.setMinimumHeight(height)
    if widget.maximumHeight() != _QWIDGETSIZE_MAX and widget.maximumHeight() < height:
        widget.setMaximumHeight(height)


def _install_touch_minimum_height_filter(widget: QWidget, height: int) -> None:
    widget.setProperty(TOUCH_MIN_HEIGHT_PROPERTY, int(height))
    if getattr(widget, TOUCH_MIN_HEIGHT_FILTER_PROPERTY, None) is not None:
        return
    event_filter = _TouchMinimumHeightFilter(widget)
    widget.installEventFilter(event_filter)
    setattr(widget, TOUCH_MIN_HEIGHT_FILTER_PROPERTY, event_filter)


def _append_stylesheet(widget: QWidget, stylesheet: str) -> None:
    existing = widget.styleSheet() if hasattr(widget, "styleSheet") else ""
    if stylesheet and stylesheet not in existing:
        widget.setStyleSheet("\n".join(part for part in (existing, stylesheet) if part))


def apply_touch_button_defaults(button: QPushButton, *, primary: bool = False, danger: bool = False) -> QPushButton:
    """Apply touch-friendly minimum size and role properties to a button."""
    _install_touch_minimum_height_filter(button, TOUCH_BUTTON_HEIGHT)
    _ensure_minimum_height(button, TOUCH_BUTTON_HEIGHT)
    button.setCursor(Qt.PointingHandCursor)
    button.setIconSize(QSize(TOUCH_ICON_SIZE, TOUCH_ICON_SIZE))
    button.setProperty(TOUCH_APPLIED_PROPERTY, True)
    if primary:
        button.setProperty("primary", True)
    if danger:
        button.setProperty("danger", True)
    return button


def apply_touch_input_defaults(widget: QWidget) -> QWidget:
    """Apply touch-friendly minimum height to a text, combo, or spin input."""
    _install_touch_minimum_height_filter(widget, TOUCH_INPUT_HEIGHT)
    _ensure_minimum_height(widget, TOUCH_INPUT_HEIGHT)
    widget.setProperty(TOUCH_APPLIED_PROPERTY, True)
    if isinstance(widget, (QLineEdit, QComboBox, QAbstractSpinBox)):
        _append_stylesheet(widget, f"font-size: {TOUCH_FONT_SIZE}px;")
    elif isinstance(widget, QTextEdit):
        widget.setMinimumHeight(max(widget.minimumHeight(), TOUCH_INPUT_HEIGHT * 2))
    return widget


def apply_touch_table_defaults(view: QAbstractItemView) -> QAbstractItemView:
    """Apply row height, kinetic scroll, and selection defaults to item views."""
    view.setAlternatingRowColors(True)
    view.setSelectionBehavior(QAbstractItemView.SelectRows)
    view.setSelectionMode(QAbstractItemView.SingleSelection)
    view.setProperty(TOUCH_APPLIED_PROPERTY, True)

    if hasattr(view, "verticalHeader"):
        header = view.verticalHeader()
        header.setDefaultSectionSize(TOUCH_TABLE_ROW_HEIGHT)
        header.setMinimumSectionSize(TOUCH_TABLE_ROW_HEIGHT)

    if hasattr(view, "horizontalHeader"):
        horizontal = view.horizontalHeader()
        horizontal.setMinimumHeight(TOUCH_TABLE_HEADER_HEIGHT)

    configure_touch_scroll(view)
    return view


def touch_button_stylesheet() -> str:
    """Return a reusable QSS snippet for touch-sized push buttons."""
    return f"""
    QPushButton {{
        min-height: {TOUCH_BUTTON_HEIGHT}px;
        padding: 8px 14px;
        font-size: {TOUCH_FONT_SIZE}px;
        border-radius: 8px;
    }}
    QPushButton[primary="true"] {{
        background-color: {TOUCH_COLORS["primary"]};
        color: white;
    }}
    QPushButton[danger="true"] {{
        color: {TOUCH_COLORS["danger"]};
        border-color: {TOUCH_COLORS["danger"]};
    }}
    """


def touch_input_stylesheet() -> str:
    """Return a reusable QSS snippet for touch-sized inputs."""
    return f"""
    QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit {{
        min-height: {TOUCH_INPUT_HEIGHT}px;
        font-size: {TOUCH_FONT_SIZE}px;
        padding: 6px 8px;
    }}
    """


def touch_table_stylesheet() -> str:
    """Return a reusable QSS snippet for touch-readable item views."""
    return f"""
    QTableWidget, QTableView, QTreeWidget, QListWidget {{
        font-size: {TOUCH_FONT_SIZE}px;
    }}
    QTableWidget::item, QTableView::item, QTreeWidget::item, QListWidget::item {{
        min-height: {TOUCH_TABLE_ROW_HEIGHT}px;
        padding: 7px 8px;
    }}
    QHeaderView::section {{
        min-height: {TOUCH_TABLE_HEADER_HEIGHT}px;
        font-size: {TOUCH_HEADER_FONT_SIZE}px;
        padding: 8px 6px;
    }}
    """
