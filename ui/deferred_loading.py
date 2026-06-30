"""Helpers for showing Qt pages before running expensive data refreshes."""

from __future__ import annotations

import logging

from PySide6.QtCore import QTimer


LOGGER = logging.getLogger("JEWELLERY_SYS")

DEFERRED_INITIAL_LOAD_PROP = "_goldshop_deferred_initial_load_pending"
SCHEDULED_REFRESH_PROP = "_goldshop_scheduled_refresh_pending"


def defer_initial_load(widget, callback, delay_ms=0):
    """Run an initial data load after the widget has had a chance to appear."""
    if widget is None or not callable(callback):
        return
    widget.setProperty(DEFERRED_INITIAL_LOAD_PROP, True)
    QTimer.singleShot(
        max(0, int(delay_ms or 0)),
        lambda widget=widget, callback=callback: _run_deferred_initial_load(widget, callback),
    )


def has_deferred_initial_load(widget):
    return bool(widget is not None and widget.property(DEFERRED_INITIAL_LOAD_PROP))


def is_live_widget(widget):
    if widget is None:
        return False
    try:
        widget.objectName()
        return True
    except RuntimeError:
        return False


def _run_deferred_initial_load(widget, callback):
    if not is_live_widget(widget):
        return

    widget.setProperty(DEFERRED_INITIAL_LOAD_PROP, False)
    if not widget.isVisible():
        return

    try:
        callback()
    except Exception as exc:
        LOGGER.exception("Deferred initial UI load failed: %s", exc)
