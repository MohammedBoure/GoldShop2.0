# ui/tools/control_geometry_filter.py

from PySide6.QtCore import QObject, QEvent, QTimer
from PySide6.QtWidgets import QAbstractSpinBox, QComboBox, QLineEdit, QPushButton, QWidget


_PENDING_PROP = "_goldshop_control_geometry_pending"
_OPT_OUT_PROP = "goldshop_auto_fit_disabled"
_QWIDGETSIZE_MAX = 16777215


class GlobalControlGeometryFilter(QObject):
    """Keeps single-line inputs and buttons large enough for their text, border, and icon."""

    def eventFilter(self, obj, event):
        if isinstance(obj, (QLineEdit, QComboBox, QAbstractSpinBox, QPushButton)):
            if event.type() in (
                QEvent.Polish,
                QEvent.Show,
                QEvent.FontChange,
                QEvent.StyleChange,
                QEvent.EnabledChange,
            ):
                schedule_control_geometry_fit(obj)
        return super().eventFilter(obj, event)


def schedule_control_geometry_fit(widget: QWidget) -> None:
    try:
        if widget.property(_OPT_OUT_PROP) or widget.property(_PENDING_PROP):
            return

        widget.setProperty(_PENDING_PROP, True)
        QTimer.singleShot(0, lambda widget=widget: fit_control_geometry(widget))
    except RuntimeError:
        pass


def fit_control_geometry(widget: QWidget) -> None:
    try:
        widget.setProperty(_PENDING_PROP, False)
        if widget.property(_OPT_OUT_PROP):
            return

        if isinstance(widget, QPushButton):
            _fit_button(widget)
        elif isinstance(widget, (QLineEdit, QComboBox, QAbstractSpinBox)):
            _ensure_minimum_height(widget, _single_line_height(widget))
    except RuntimeError:
        pass


def _single_line_height(widget: QWidget) -> int:
    return max(34, widget.fontMetrics().height() + 16, _hint_height(widget))


def _button_height(button: QPushButton) -> int:
    icon_height = 0 if button.icon().isNull() else button.iconSize().height()
    text_height = button.fontMetrics().height() if button.text().strip() else 0
    return max(32, icon_height + 10, text_height + 16, _hint_height(button))


def _fit_button(button: QPushButton) -> None:
    _ensure_minimum_height(button, _button_height(button))

    text = button.text().strip()
    if not text:
        return

    icon_width = 0 if button.icon().isNull() else button.iconSize().width() + 8
    needed_width = max(
        button.fontMetrics().horizontalAdvance(text) + icon_width + 32,
        button.sizeHint().width(),
        button.minimumSizeHint().width(),
    )

    if _has_fixed_width(button) and button.maximumWidth() < needed_width:
        button.setFixedWidth(min(needed_width, 420))


def _ensure_minimum_height(widget: QWidget, needed_height: int) -> None:
    if needed_height <= 0:
        return

    if _has_fixed_height(widget):
        if widget.maximumHeight() < needed_height:
            widget.setFixedHeight(needed_height)
        return

    if widget.minimumHeight() < needed_height:
        widget.setMinimumHeight(needed_height)

    if widget.maximumHeight() != _QWIDGETSIZE_MAX and widget.maximumHeight() < needed_height:
        widget.setMaximumHeight(needed_height)


def _has_fixed_height(widget: QWidget) -> bool:
    return widget.minimumHeight() == widget.maximumHeight()


def _has_fixed_width(widget: QWidget) -> bool:
    return widget.minimumWidth() == widget.maximumWidth()


def _hint_height(widget: QWidget) -> int:
    try:
        widget.ensurePolished()
        return max(widget.sizeHint().height(), widget.minimumSizeHint().height())
    except RuntimeError:
        return 0
