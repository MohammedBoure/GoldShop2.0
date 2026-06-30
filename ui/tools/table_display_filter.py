# ui/tools/table_display_filter.py

import hashlib
import os

from PySide6.QtCore import QObject, QEvent, QSettings, Qt, QTimer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QAbstractScrollArea,
    QHeaderView,
    QScroller,
    QScrollerProperties,
    QTableView,
)


_CONFIGURED_PROP = "_goldshop_full_table_display_configured"
_SCROLLER_CONFIGURED_PROP = "_goldshop_table_scroller_configured"
_COLUMN_ORDER_CONFIGURED_PROP = "_goldshop_table_column_order_configured"
_COLUMN_ORDER_RESTORING_PROP = "_goldshop_table_column_order_restoring"
_COLUMN_ORDER_RESTORE_PENDING_PROP = "_goldshop_table_column_order_restore_pending"
_COLUMN_ORDER_RESTORED_KEY_PROP = "_goldshop_table_column_order_restored_key"
_COLUMN_ORDER_KEY_PROP = "_goldshop_table_column_order_key"
_MODEL_ID_PROP = "_goldshop_full_table_display_model_id"
_RESIZE_PENDING_PROP = "_goldshop_full_table_display_resize_pending"
_RESIZE_SIGNATURE_PROP = "_goldshop_full_table_display_resize_signature"
_OPT_OUT_PROP = "goldshop_table_auto_width_disabled"
_SCROLL_OPT_OUT_PROP = "goldshop_table_touch_scroll_disabled"
_COLUMN_ORDER_OPT_OUT_PROP = "goldshop_table_column_order_disabled"
_COLUMN_ORDER_KEY_OVERRIDE_PROP = "goldshop_table_layout_key"
_RESIZE_DELAY_MS = 120
_RESIZE_CONTENTS_PRECISION = 80

_RUNTIME_DIR = "runtime"
_SETTINGS_FILE = os.path.join(_RUNTIME_DIR, "table_layouts.ini")
_LEGACY_SETTINGS_FILE = "table_layouts.ini"
_settings = None


class GlobalTableDisplayFilter(QObject):
    """Applies the global table policy for touch-friendly data tables."""

    def eventFilter(self, obj, event):
        if event.type() in (QEvent.Polish, QEvent.Show) and isinstance(obj, QTableView):
            configure_table_display(obj)
        return super().eventFilter(obj, event)


def configure_table_display(table: QTableView) -> None:
    configure_table_scrolling(table)
    configure_table_column_order(table)

    if table.property(_OPT_OUT_PROP):
        return

    first_configure = not bool(table.property(_CONFIGURED_PROP))

    table.setWordWrap(False)
    table.setTextElideMode(Qt.ElideNone)
    table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    table.setSizeAdjustPolicy(QAbstractScrollArea.AdjustIgnored)

    header = table.horizontalHeader()
    if header:
        header.setStretchLastSection(False)
        header.setDefaultSectionSize(max(header.defaultSectionSize(), 110))
        header.setMinimumSectionSize(max(header.minimumSectionSize(), 70))
        header.setResizeContentsPrecision(_RESIZE_CONTENTS_PRECISION)
        header.setSectionResizeMode(QHeaderView.Interactive)

    if first_configure:
        table.setProperty(_CONFIGURED_PROP, True)

    model_changed = _connect_model_signals(table)
    if first_configure or model_changed:
        schedule_table_resize(table)


def configure_table_column_order(table: QTableView) -> None:
    """Allow users to reorder table columns and persist that order."""

    if table.property(_COLUMN_ORDER_OPT_OUT_PROP):
        return

    header = table.horizontalHeader()
    if header is None:
        return

    try:
        header.setSectionsMovable(True)
        header.setFirstSectionMovable(True)
    except AttributeError:
        pass

    key = _table_column_order_key(table)
    if not key:
        return

    table.setProperty(_COLUMN_ORDER_KEY_PROP, key)

    if not table.property(_COLUMN_ORDER_CONFIGURED_PROP):
        table.setProperty(_COLUMN_ORDER_CONFIGURED_PROP, True)
        header.sectionMoved.connect(lambda *_, table=table: _save_table_column_order(table))

    schedule_table_column_order_restore(table)


def configure_table_scrolling(table: QTableView) -> None:
    """Enable smooth kinetic scrolling for any table-like view."""

    if table.property(_SCROLL_OPT_OUT_PROP):
        return

    table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
    table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)

    viewport = table.viewport()
    if viewport is None or viewport.property(_SCROLLER_CONFIGURED_PROP):
        return

    QScroller.grabGesture(viewport, QScroller.TouchGesture)
    QScroller.grabGesture(viewport, QScroller.LeftMouseButtonGesture)

    scroller = QScroller.scroller(viewport)
    props = scroller.scrollerProperties()
    props.setScrollMetric(
        QScrollerProperties.ScrollMetric.VerticalOvershootPolicy,
        QScrollerProperties.OvershootPolicy.OvershootAlwaysOff,
    )
    props.setScrollMetric(
        QScrollerProperties.ScrollMetric.HorizontalOvershootPolicy,
        QScrollerProperties.OvershootPolicy.OvershootAlwaysOff,
    )
    props.setScrollMetric(QScrollerProperties.ScrollMetric.DragStartDistance, 0.001)
    scroller.setScrollerProperties(props)

    viewport.setProperty(_SCROLLER_CONFIGURED_PROP, True)


def schedule_table_column_order_restore(table: QTableView) -> None:
    try:
        key = table.property(_COLUMN_ORDER_KEY_PROP) or _table_column_order_key(table)
        if not key or table.property(_COLUMN_ORDER_RESTORED_KEY_PROP) == key:
            return
        if table.property(_COLUMN_ORDER_RESTORE_PENDING_PROP):
            return

        table.setProperty(_COLUMN_ORDER_RESTORE_PENDING_PROP, True)
        QTimer.singleShot(0, lambda table=table: _restore_table_column_order(table))
    except RuntimeError:
        pass


def _restore_table_column_order(table: QTableView) -> None:
    try:
        table.setProperty(_COLUMN_ORDER_RESTORE_PENDING_PROP, False)
        if table.property(_COLUMN_ORDER_OPT_OUT_PROP):
            return

        header = table.horizontalHeader()
        if header is None or header.count() <= 1:
            return

        key = _table_column_order_key(table)
        if not key:
            return

        table.setProperty(_COLUMN_ORDER_KEY_PROP, key)
        order = _load_saved_column_order(key, header.count())
        if not order:
            table.setProperty(_COLUMN_ORDER_RESTORED_KEY_PROP, key)
            return

        table.setProperty(_COLUMN_ORDER_RESTORING_PROP, True)
        for target_visual_index, logical_index in enumerate(order):
            current_visual_index = header.visualIndex(logical_index)
            if current_visual_index >= 0 and current_visual_index != target_visual_index:
                header.moveSection(current_visual_index, target_visual_index)

        table.setProperty(_COLUMN_ORDER_RESTORED_KEY_PROP, key)
    except RuntimeError:
        pass
    finally:
        try:
            table.setProperty(_COLUMN_ORDER_RESTORING_PROP, False)
        except RuntimeError:
            pass


def _save_table_column_order(table: QTableView) -> None:
    try:
        if table.property(_COLUMN_ORDER_RESTORING_PROP):
            return

        header = table.horizontalHeader()
        if header is None or header.count() <= 1:
            return

        key = _table_column_order_key(table)
        if not key:
            return

        order = [str(header.logicalIndex(visual_index)) for visual_index in range(header.count())]
        settings = _table_layout_settings()
        settings.setValue(f"tables/{key}/order", ",".join(order))
        settings.setValue(f"tables/{key}/signature", _table_column_signature(table))
        settings.sync()

        table.setProperty(_COLUMN_ORDER_KEY_PROP, key)
        table.setProperty(_COLUMN_ORDER_RESTORED_KEY_PROP, key)
    except RuntimeError:
        pass


def _load_saved_column_order(key: str, column_count: int) -> list[int]:
    raw_order = _table_layout_settings().value(f"tables/{key}/order", "")
    if not raw_order:
        return []

    try:
        order = [int(value) for value in str(raw_order).split(",") if value != ""]
    except ValueError:
        return []

    if len(order) != column_count or sorted(order) != list(range(column_count)):
        return []
    return order


def _table_layout_settings() -> QSettings:
    global _settings
    if _settings is None:
        os.makedirs(_RUNTIME_DIR, exist_ok=True)
        settings_file = _SETTINGS_FILE if os.path.exists(_SETTINGS_FILE) or not os.path.exists(_LEGACY_SETTINGS_FILE) else _LEGACY_SETTINGS_FILE
        _settings = QSettings(os.path.abspath(settings_file), QSettings.IniFormat)
        _settings.setFallbacksEnabled(False)
    return _settings


def _table_column_order_key(table: QTableView) -> str:
    header = table.horizontalHeader()
    if header is None or header.count() <= 1:
        return ""

    override = table.property(_COLUMN_ORDER_KEY_OVERRIDE_PROP)
    if override:
        base_key = str(override)
    else:
        base_key = f"{_object_path(table)}|{_table_column_signature(table)}"

    return hashlib.sha1(base_key.encode("utf-8")).hexdigest()


def _table_column_signature(table: QTableView) -> str:
    model = table.model()
    header = table.horizontalHeader()
    column_count = header.count() if header is not None else 0
    labels = []

    for logical_index in range(column_count):
        value = None
        if model is not None:
            value = model.headerData(logical_index, Qt.Horizontal, Qt.DisplayRole)
        labels.append(str(value or ""))

    return f"{column_count}:" + "|".join(labels)


def _object_path(obj: QObject) -> str:
    parts = []
    current = obj

    while current is not None and len(parts) < 8:
        cls = current.__class__
        name = current.objectName()
        part = f"{cls.__module__}.{cls.__qualname__}"
        if name:
            part = f"{part}#{name}"
        parts.append(part)
        current = current.parent()

    return ">".join(reversed(parts))


def _connect_model_signals(table: QTableView) -> bool:
    model = table.model()
    if model is None:
        return False

    model_id = str(id(model))
    if table.property(_MODEL_ID_PROP) == model_id:
        return False

    table.setProperty(_MODEL_ID_PROP, model_id)
    table.setProperty(_RESIZE_SIGNATURE_PROP, "")
    for signal_name in ("columnsInserted", "columnsRemoved", "headerDataChanged", "modelReset", "layoutChanged"):
        signal = getattr(model, signal_name, None)
        if signal is not None:
            signal.connect(lambda *_, table=table: _handle_table_structure_changed(table))
    return True


def _handle_table_structure_changed(table: QTableView) -> None:
    try:
        table.setProperty(_COLUMN_ORDER_RESTORED_KEY_PROP, "")
        configure_table_column_order(table)
        schedule_table_resize(table)
    except RuntimeError:
        pass


def schedule_table_resize(table: QTableView) -> None:
    try:
        if table.property(_RESIZE_PENDING_PROP):
            return

        table.setProperty(_RESIZE_PENDING_PROP, True)
        QTimer.singleShot(_RESIZE_DELAY_MS, lambda table=table: _resize_table_columns(table))
    except RuntimeError:
        pass


def _resize_table_columns(table: QTableView) -> None:
    try:
        table.setProperty(_RESIZE_PENDING_PROP, False)
        if table.property(_OPT_OUT_PROP):
            return

        signature = _table_resize_signature(table)
        if table.property(_RESIZE_SIGNATURE_PROP) == signature:
            return

        header = table.horizontalHeader()
        if header:
            header.setStretchLastSection(False)
            header.setResizeContentsPrecision(_RESIZE_CONTENTS_PRECISION)
            header.setSectionResizeMode(QHeaderView.ResizeToContents)
        table.resizeColumnsToContents()
        if header:
            header.setSectionResizeMode(QHeaderView.Interactive)
        table.setProperty(_RESIZE_SIGNATURE_PROP, signature)
    except RuntimeError:
        pass


def _table_resize_signature(table: QTableView) -> str:
    model = table.model()
    if model is None:
        return "no-model"
    try:
        rows = model.rowCount()
        columns = model.columnCount()
    except RuntimeError:
        rows = 0
        columns = 0
    return f"{id(model)}:{rows}:{columns}:{_table_column_signature(table)}"
