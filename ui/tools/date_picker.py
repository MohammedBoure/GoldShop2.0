"""Stable touch-friendly date picker used instead of Qt's calendar popup."""

from __future__ import annotations

from PySide6.QtCore import QDate, QEvent, QObject, Qt, QTimer, QLocale
from PySide6.QtGui import QMouseEvent, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QCalendarWidget,
    QComboBox,
    QDateEdit,
    QDateTimeEdit,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QStyle,
    QStyleOptionSpinBox,
    QVBoxLayout,
)


_FILTER_ATTR = "_goldshop_date_picker_filter"
_OPEN_PROP = "_goldshop_date_picker_open"
_DISABLED_PROP = "_goldshop_date_picker_disabled"


class DatePickerDialog(QDialog):
    """A roomy calendar dialog that does not inherit fragile popup styling."""

    def __init__(self, initial_date=None, parent=None, minimum_date=None, maximum_date=None):
        super().__init__(parent)
        self.setObjectName("goldshopDatePickerDialog")
        self.setWindowTitle("Selectionner une date")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setMinimumWidth(430)

        self.locale = QLocale()
        self.minimum_date = minimum_date if isinstance(minimum_date, QDate) else QDate(1900, 1, 1)
        self.maximum_date = maximum_date if isinstance(maximum_date, QDate) else QDate(2100, 12, 31)
        self._selected_date = self._clamp_date(
            initial_date if isinstance(initial_date, QDate) and initial_date.isValid() else QDate.currentDate()
        )

        self._build_ui()
        self._sync_controls_from_date(self._selected_date)

    def selected_date(self):
        return QDate(self._selected_date)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 16)
        root.setSpacing(12)

        header = QFrame()
        header.setObjectName("datePickerHeader")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(14, 12, 14, 12)
        header_layout.setSpacing(4)

        title = QLabel("Selectionner une date")
        title.setObjectName("datePickerTitle")
        self.lbl_selected = QLabel()
        self.lbl_selected.setObjectName("datePickerSelected")
        header_layout.addWidget(title)
        header_layout.addWidget(self.lbl_selected)
        root.addWidget(header)

        nav = QHBoxLayout()
        nav.setSpacing(8)

        self.btn_previous = QPushButton("<")
        self.btn_previous.setToolTip("Mois precedent")
        self.btn_next = QPushButton(">")
        self.btn_next.setToolTip("Mois suivant")
        self.combo_month = QComboBox()
        self.spin_year = QSpinBox()

        for month in range(1, 13):
            name = self.locale.monthName(month, QLocale.LongFormat) or str(month)
            self.combo_month.addItem(name.capitalize(), month)

        self.spin_year.setRange(self.minimum_date.year(), self.maximum_date.year())
        self.combo_month.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.btn_previous.clicked.connect(lambda: self._shift_months(-1))
        self.btn_next.clicked.connect(lambda: self._shift_months(1))
        self.combo_month.currentIndexChanged.connect(self._month_year_changed)
        self.spin_year.valueChanged.connect(self._month_year_changed)

        nav.addWidget(self.btn_previous)
        nav.addWidget(self.combo_month, 1)
        nav.addWidget(self.spin_year)
        nav.addWidget(self.btn_next)
        root.addLayout(nav)

        self.calendar = QCalendarWidget()
        self.calendar.setObjectName("goldshopDateCalendar")
        self.calendar.setNavigationBarVisible(False)
        self.calendar.setGridVisible(True)
        self.calendar.setFirstDayOfWeek(Qt.Monday)
        self.calendar.setVerticalHeaderFormat(QCalendarWidget.NoVerticalHeader)
        self.calendar.setMinimumSize(390, 285)
        self.calendar.setMinimumDate(self.minimum_date)
        self.calendar.setMaximumDate(self.maximum_date)
        self.calendar.clicked.connect(self._set_date)
        self.calendar.activated.connect(self._accept_date)
        root.addWidget(self.calendar)

        quick = QHBoxLayout()
        quick.setSpacing(8)
        for label, callback in (
            ("Aujourd'hui", lambda: self._set_date(QDate.currentDate())),
            ("Hier", lambda: self._set_date(QDate.currentDate().addDays(-1))),
            ("Debut mois", self._set_month_start),
            ("Fin mois", self._set_month_end),
        ):
            button = QPushButton(label)
            button.setProperty("secondary", True)
            button.clicked.connect(callback)
            quick.addWidget(button)
        root.addLayout(quick)

        actions = QHBoxLayout()
        actions.addStretch()
        self.btn_cancel = QPushButton("Annuler")
        self.btn_accept = QPushButton("Valider")
        self.btn_accept.setProperty("primary", True)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_accept.clicked.connect(self.accept)
        actions.addWidget(self.btn_cancel)
        actions.addWidget(self.btn_accept)
        root.addLayout(actions)

        self.setStyleSheet(self._stylesheet())

    def _stylesheet(self):
        palette = QApplication.palette()
        background = palette.color(QPalette.Window).name()
        surface = palette.color(QPalette.Base).name()
        surface_alt = palette.color(QPalette.AlternateBase).name()
        text = palette.color(QPalette.WindowText).name()
        muted = palette.color(QPalette.PlaceholderText).name()
        border = palette.color(QPalette.Mid).name()
        primary = "#0f8f83"
        selection = palette.color(QPalette.Highlight).name()
        highlighted_text = "#ffffff"

        return f"""
        QDialog#goldshopDatePickerDialog {{
            background: {background};
            color: {text};
        }}
        QDialog#goldshopDatePickerDialog QLabel {{
            background: transparent;
            color: {text};
        }}
        QFrame#datePickerHeader {{
            background: {surface};
            border: 1px solid {border};
            border-radius: 8px;
        }}
        QLabel#datePickerTitle {{
            font-size: 18px;
            font-weight: 800;
        }}
        QLabel#datePickerSelected {{
            color: {muted};
            font-size: 13px;
            font-weight: 650;
        }}
        QDialog#goldshopDatePickerDialog QPushButton {{
            min-height: 38px;
            border: 1px solid {border};
            border-radius: 7px;
            padding: 7px 12px;
            background: {surface};
            color: {text};
            font-weight: 700;
        }}
        QDialog#goldshopDatePickerDialog QPushButton:hover {{
            background: {surface_alt};
            border-color: {primary};
        }}
        QDialog#goldshopDatePickerDialog QPushButton[primary="true"] {{
            background: {primary};
            border-color: {primary};
            color: {highlighted_text};
        }}
        QDialog#goldshopDatePickerDialog QPushButton[secondary="true"] {{
            background: {surface_alt};
        }}
        QDialog#goldshopDatePickerDialog QComboBox,
        QDialog#goldshopDatePickerDialog QSpinBox {{
            min-height: 38px;
            border: 1px solid {border};
            border-radius: 7px;
            padding: 4px 8px;
            background: {surface};
            color: {text};
            font-weight: 650;
        }}
        QCalendarWidget#goldshopDateCalendar {{
            background: {surface};
            border: 1px solid {border};
            border-radius: 8px;
        }}
        QCalendarWidget#goldshopDateCalendar QWidget {{
            background: {surface};
            color: {text};
        }}
        QCalendarWidget#goldshopDateCalendar QAbstractItemView {{
            background: {surface};
            color: {text};
            selection-background-color: {selection};
            selection-color: {text};
            outline: 0;
            font-size: 15px;
            border: none;
        }}
        QCalendarWidget#goldshopDateCalendar QAbstractItemView:disabled {{
            color: {muted};
        }}
        QCalendarWidget#goldshopDateCalendar QHeaderView::section {{
            background: {surface_alt};
            color: {text};
            border: none;
            padding: 7px;
            font-weight: 800;
        }}
        """

    def _clamp_date(self, date):
        if date < self.minimum_date:
            return QDate(self.minimum_date)
        if date > self.maximum_date:
            return QDate(self.maximum_date)
        return QDate(date)

    def _sync_controls_from_date(self, date):
        date = self._clamp_date(date)
        self._selected_date = date

        self.combo_month.blockSignals(True)
        self.spin_year.blockSignals(True)
        self.combo_month.setCurrentIndex(max(0, date.month() - 1))
        self.spin_year.setValue(date.year())
        self.combo_month.blockSignals(False)
        self.spin_year.blockSignals(False)

        self.calendar.setCurrentPage(date.year(), date.month())
        self.calendar.setSelectedDate(date)
        self.lbl_selected.setText(self.locale.toString(date, "dddd dd MMMM yyyy"))

    def _set_date(self, date):
        self._sync_controls_from_date(date)

    def _accept_date(self, date):
        self._set_date(date)
        self.accept()

    def _month_year_changed(self):
        month = self.combo_month.currentData() or self._selected_date.month()
        year = self.spin_year.value()
        day = min(self._selected_date.day(), QDate(year, month, 1).daysInMonth())
        self._set_date(QDate(year, month, day))

    def _shift_months(self, count):
        self._set_date(self._selected_date.addMonths(count))

    def _set_month_start(self):
        today = QDate.currentDate()
        self._set_date(QDate(today.year(), today.month(), 1))

    def _set_month_end(self):
        today = QDate.currentDate()
        first_day = QDate(today.year(), today.month(), 1)
        self._set_date(first_day.addMonths(1).addDays(-1))


class DatePickerEventFilter(QObject):
    """Open DatePickerDialog from QDateEdit/QDateTimeEdit calendar buttons."""

    def eventFilter(self, obj, event):
        if not _is_supported_editor(obj):
            return super().eventFilter(obj, event)
        if obj.property(_DISABLED_PROP):
            return super().eventFilter(obj, event)
        if not _uses_calendar_popup(obj):
            return super().eventFilter(obj, event)

        if event.type() == QEvent.MouseButtonPress and _is_left_mouse_event(event):
            if _is_calendar_button_click(obj, _event_pos(event)):
                self._open_later(obj)
                return True

        if event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_F4 or (
                event.key() == Qt.Key_Down and event.modifiers() & Qt.AltModifier
            ):
                self._open_later(obj)
                return True

        return super().eventFilter(obj, event)

    def _open_later(self, editor):
        QTimer.singleShot(0, lambda: self.open_for_editor(editor))

    def open_for_editor(self, editor):
        try:
            if not _is_supported_editor(editor) or editor.property(_OPEN_PROP):
                return False
            if not _uses_calendar_popup(editor):
                return False
            if not editor.isEnabled() or editor.isReadOnly():
                return False
        except RuntimeError:
            return False

        editor.setProperty(_OPEN_PROP, True)
        try:
            dialog = DatePickerDialog(
                _editor_date(editor),
                parent=editor.window(),
                minimum_date=editor.minimumDate(),
                maximum_date=editor.maximumDate(),
            )
            if dialog.exec() == QDialog.Accepted:
                _apply_selected_date(editor, dialog.selected_date())
                return True
            return False
        except RuntimeError:
            return False
        finally:
            try:
                editor.setProperty(_OPEN_PROP, False)
            except RuntimeError:
                pass


def install_custom_date_picker(app=None):
    app = app or QApplication.instance()
    if app is None:
        return None

    existing = getattr(app, _FILTER_ATTR, None)
    if existing is not None:
        return existing

    event_filter = DatePickerEventFilter(app)
    app.installEventFilter(event_filter)
    setattr(app, _FILTER_ATTR, event_filter)
    return event_filter


def _is_supported_editor(widget):
    return isinstance(widget, (QDateEdit, QDateTimeEdit))


def _uses_calendar_popup(editor):
    try:
        return bool(editor.calendarPopup())
    except RuntimeError:
        return False


def _editor_date(editor):
    return editor.date()


def _apply_selected_date(editor, date):
    if isinstance(date, QDate) and date.isValid():
        editor.setDate(date)


def _is_left_mouse_event(event):
    return isinstance(event, QMouseEvent) and event.button() == Qt.LeftButton


def _event_pos(event):
    if hasattr(event, "position"):
        return event.position().toPoint()
    return event.pos()


def _is_calendar_button_click(editor, pos):
    try:
        option = QStyleOptionSpinBox()
        editor.initStyleOption(option)
        rect = editor.style().subControlRect(
            QStyle.CC_SpinBox,
            option,
            QStyle.SC_SpinBoxDown,
            editor,
        )
        if rect.isValid() and rect.contains(pos):
            return True
    except RuntimeError:
        return False

    fallback_width = max(34, editor.height())
    return pos.x() >= editor.width() - fallback_width
