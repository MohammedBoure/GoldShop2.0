# ui/tools/touch_scroll_filter.py

from PySide6.QtCore import QObject, QEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QAbstractScrollArea,
    QPlainTextEdit,
    QScroller,
    QScrollerProperties,
    QTextEdit,
)


_CONFIGURED_PROP = "_goldshop_touch_scroll_configured"
_OPT_OUT_PROP = "goldshop_touch_scroll_disabled"


class GlobalTouchScrollFilter(QObject):
    """Enables touch-friendly kinetic scrolling for every scrollable surface."""

    def eventFilter(self, obj, event):
        if event.type() in (QEvent.Polish, QEvent.Show) and isinstance(obj, QAbstractScrollArea):
            configure_touch_scroll(obj)
        return super().eventFilter(obj, event)


def configure_touch_scroll(area: QAbstractScrollArea) -> None:
    try:
        if area.property(_OPT_OUT_PROP):
            return

        if isinstance(area, QAbstractItemView):
            area.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
            area.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)

        viewport = area.viewport()
        if viewport is None or viewport.property(_CONFIGURED_PROP):
            return

        QScroller.grabGesture(viewport, QScroller.TouchGesture)
        if not isinstance(area, (QTextEdit, QPlainTextEdit)):
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

        viewport.setProperty(_CONFIGURED_PROP, True)
    except RuntimeError:
        pass
