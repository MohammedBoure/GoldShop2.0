from __future__ import annotations

from typing import Any, Dict, Optional

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QWidget

from ui.deferred_loading import defer_initial_load

from .actions import InventoryCountActionsMixin
from .item_tables import InventoryCountItemTablesMixin
from .session_data import InventoryCountSessionDataMixin
from .ui_builders import InventoryCountUiMixin


class InventoryCountView(
    QWidget,
    InventoryCountUiMixin,
    InventoryCountSessionDataMixin,
    InventoryCountItemTablesMixin,
    InventoryCountActionsMixin,
):
    def __init__(self, manager, current_user: Optional[dict] = None):
        super().__init__()
        self.manager = manager
        self.current_user = current_user or {}
        self.current_session: Dict[str, Any] = {}
        self._barcode_processing = False
        self._item_page_size = 150
        self._checked_offset = 0
        self._remaining_offset = 0
        self._checked_has_more = True
        self._remaining_has_more = True
        self._items_loading = False
        self._barcode_scan_timer = QTimer(self)
        self._barcode_scan_timer.setSingleShot(True)
        self._barcode_scan_timer.setInterval(450)
        self._barcode_scan_timer.timeout.connect(self._auto_count_barcode)
        self._init_ui()
        defer_initial_load(self, self.refresh_data)
