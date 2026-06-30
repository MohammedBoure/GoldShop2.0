# ui/widgets/inventory/inventory_list_tab.py

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QLineEdit, QLabel, QComboBox, QCheckBox,
    QMessageBox,QDoubleSpinBox, QGridLayout, QDialog
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QColor, QFont
import qtawesome as qta

from ui.deferred_loading import defer_initial_load
from ._helpers import SortableTableWidgetItem, load_label_config


class InventoryListTab(QWidget):
    """
    تبويب عرض المخزون: جدول مرقّم بالصفحات مع بحث، فلتر، ترتيب،
    وتحميل تدريجي عند التمرير.
    """

    request_history = Signal(str)

    # أسماء الأعمدة وأرقامها الثابتة
    COL_SELECT    = 0
    COL_ID        = 1
    COL_BARCODE   = 2
    COL_NAME      = 3
    COL_CATEGORY  = 4
    COL_METAL     = 5
    COL_WEIGHT    = 6
    COL_REM_W     = 7
    COL_LABOR     = 8
    COL_MTYPE     = 9
    COL_MARGIN    = 10
    COL_PRICE     = 11
    COL_RESERVED  = 12
    COL_STATUS    = 13
    COL_ACTIONS   = 14

    COLUMNS = [
        "ID", "Code-barres", "Article", "Catégorie", "Métal",
        "Poids U.", "Pds Reste", "Coût Façon", "Type Marge", "Marge",
        "P.Vente", "Réservé", "Statut", "Actions"
    ]

    COLUMNS = [""] + COLUMNS

    def __init__(self, manager):
        super().__init__()
        self.manager = manager
        self.limit       = 30
        self.offset      = 0
        self.is_loading  = False
        self.all_loaded  = False
        self.sort_col    = self.COL_ID
        self.sort_dir    = "DESC"
        self._total_count = 0
        self._total_weight = 0.0
        self.selected_items = {}
        self._print_icon = qta.icon("fa5s.print", color="#34495e")
        self.filter_min_weight = None  # تمت الإضافة لحفظ الحد الأدنى
        self.filter_max_weight = None  # تمت الإضافة لحفظ الحد الأقصى
        self.init_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        layout.addLayout(self._build_toolbar())
        layout.addWidget(self._build_table())

        self.lbl_status = QLabel("Chargement...")
        self.lbl_status.setStyleSheet("color: #7f8c8d; font-size: 12px; font-weight: bold;")
        layout.addWidget(self.lbl_status)

        defer_initial_load(self, self.refresh_data)

    def _open_weight_filter_dialog(self):
        dialog = WeightFilterDialog(self.filter_min_weight, self.filter_max_weight, self)
        if dialog.exec() == QDialog.Accepted:
            if dialog.cleared:
                self.filter_min_weight = None
                self.filter_max_weight = None
                self.btn_weight_filter.setStyleSheet("color: #8e44ad; font-weight: bold; border: 1px solid #8e44ad; padding: 5px 10px; border-radius: 4px;")
            else:
                self.filter_min_weight, self.filter_max_weight = dialog.get_values()
                self.btn_weight_filter.setStyleSheet("background-color: #8e44ad; color: white; font-weight: bold; padding: 5px 10px; border-radius: 4px;")
            self.reset_and_load()

    def _build_toolbar(self) -> QHBoxLayout:
        toolbar = QHBoxLayout()

        # حاوية البحث التي تجمع حقل البحث مع زر الكيبورد
        search_container = QWidget()
        search_layout = QHBoxLayout(search_container)
        search_layout.setContentsMargins(0, 0, 0, 0)
        search_layout.setSpacing(5)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Recherche (Code, Nom, Client)...")
        self.search_input.setFixedHeight(35)
        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(300)
        self.search_timer.timeout.connect(self.reset_and_load)
        self.search_input.textChanged.connect(self.search_timer.start)
        
        # زر الكيبورد الافتراضي
        self.btn_keyboard = QPushButton()
        self.btn_keyboard.setIcon(qta.icon("fa5s.keyboard", color="#34495e"))
        self.btn_keyboard.setFixedSize(40, 35)
        self.btn_keyboard.setCursor(Qt.PointingHandCursor)
        self.btn_keyboard.setToolTip("Afficher le clavier virtuel")
        self.btn_keyboard.setStyleSheet("background-color: #ecf0f1; border: 1px solid #bdc3c7; border-radius: 4px;")
        self.btn_keyboard.clicked.connect(self._show_virtual_keyboard)

        search_layout.addWidget(self.search_input)
        search_layout.addWidget(self.btn_keyboard)
        
        toolbar.addWidget(search_container, 2)

        # فلتر الحالات (متاح، محجوز...)
        self.combo_status_filter = QComboBox()
        self.combo_status_filter.setFixedHeight(35)
        self.combo_status_filter.addItem("Tous (الكل)", "ALL")
        self.combo_status_filter.addItem("Disponible (متاح)", "Available")
        self.combo_status_filter.addItem("Partiellement Vendu (محجوز جزئياً)", "Partially_Sold")
        self.combo_status_filter.addItem("Réservé (محجوز كلياً)", "Reserved")
        self.combo_status_filter.currentIndexChanged.connect(self.reset_and_load)
        toolbar.addWidget(self.combo_status_filter, 1)

        self.filter_category = QComboBox()
        self.filter_category.setFixedHeight(35)
        self.filter_category.addItem("Toutes Catégories", None)
        self.filter_category.currentIndexChanged.connect(self.reset_and_load)
        toolbar.addWidget(self.filter_category, 1)

        # 🟢 إضافة زر فلتر الوزن الجديد
        self.btn_weight_filter = QPushButton(" Filtre Poids")
        self.btn_weight_filter.setFixedHeight(35)
        self.btn_weight_filter.setIcon(qta.icon("fa5s.balance-scale", color="#8e44ad"))
        self.btn_weight_filter.setStyleSheet("color: #8e44ad; font-weight: bold; border: 1px solid #8e44ad; padding: 5px 10px; border-radius: 4px;")
        self.btn_weight_filter.clicked.connect(self._open_weight_filter_dialog)
        toolbar.addWidget(self.btn_weight_filter)

        self.btn_select_visible = QPushButton("Tout selectionner")
        self.btn_select_visible.setFixedHeight(35)
        self.btn_select_visible.setIcon(qta.icon("fa5s.check-square", color="#16a085"))
        self.btn_select_visible.setStyleSheet("color: #16a085; font-weight: bold; border: 1px solid #16a085; padding: 5px 10px; border-radius: 4px;")
        self.btn_select_visible.clicked.connect(self.toggle_visible_selection)
        toolbar.addWidget(self.btn_select_visible)

        self.btn_bulk_print = QPushButton("Imprimer selection")
        self.btn_bulk_print.setFixedHeight(35)
        self.btn_bulk_print.setIcon(qta.icon("fa5s.print", color="#2c3e50"))
        self.btn_bulk_print.setEnabled(False)
        self.btn_bulk_print.clicked.connect(self.print_selected_items)
        toolbar.addWidget(self.btn_bulk_print)

        self.btn_bulk_delete = QPushButton("Supprimer selection")
        self.btn_bulk_delete.setFixedHeight(35)
        self.btn_bulk_delete.setIcon(qta.icon("fa5s.trash-alt", color="#c0392b"))
        self.btn_bulk_delete.setEnabled(False)
        self.btn_bulk_delete.setStyleSheet("color: #c0392b; font-weight: bold; border: 1px solid #c0392b; padding: 5px 10px; border-radius: 4px;")
        self.btn_bulk_delete.clicked.connect(self.delete_selected_items)
        toolbar.addWidget(self.btn_bulk_delete)

        self.lbl_bulk_count = QLabel("0 selection")
        self.lbl_bulk_count.setStyleSheet("color: #16a085; font-size: 12px; font-weight: bold;")
        toolbar.addWidget(self.lbl_bulk_count)

        self.btn_update_price = QPushButton("Maj Cours Or")
        self.btn_update_price.setFixedHeight(35)
        self.btn_update_price.setIcon(qta.icon("fa5s.chart-line", color="#d35400"))
        self.btn_update_price.setStyleSheet("color: #d35400; font-weight: bold; border: 1px solid #d35400; padding: 5px 10px; border-radius: 4px;")
        self.btn_update_price.clicked.connect(self._open_price_update_dialog)
        toolbar.addWidget(self.btn_update_price)

        self.btn_update_margin = QPushButton("Marge Poids")
        self.btn_update_margin.setFixedHeight(35)
        self.btn_update_margin.setIcon(qta.icon("fa5s.percent", color="#2980b9"))
        self.btn_update_margin.setStyleSheet("color: #2980b9; font-weight: bold; border: 1px solid #2980b9; padding: 5px 10px; border-radius: 4px;")
        self.btn_update_margin.clicked.connect(self._open_margin_update_dialog)
        toolbar.addWidget(self.btn_update_margin)

        self.chk_show_zero = QCheckBox("Afficher Stock Épuisé")
        self.chk_show_zero.setStyleSheet("font-weight: bold; color: #c0392b;")
        self.chk_show_zero.stateChanged.connect(self.reset_and_load)
        toolbar.addWidget(self.chk_show_zero)

        btn_refresh = QPushButton()
        btn_refresh.setFixedHeight(35)
        btn_refresh.setIcon(qta.icon("fa5s.sync-alt", color="#2c3e50"))
        btn_refresh.clicked.connect(self.refresh_data)
        toolbar.addWidget(btn_refresh)

        return toolbar

    def _build_table(self) -> QTableWidget:
        self.table = QTableWidget()
        self.table.setColumnCount(len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)

        h = self.table.horizontalHeader()
        h.setSectionResizeMode(QHeaderView.Interactive)
        widths = {
            self.COL_SELECT: 42,
            self.COL_ID: 65,
            self.COL_BARCODE: 130,
            self.COL_CATEGORY: 135,
            self.COL_METAL: 110,
            self.COL_WEIGHT: 90,
            self.COL_REM_W: 100,
            self.COL_LABOR: 110,
            self.COL_MTYPE: 95,
            self.COL_MARGIN: 105,
            self.COL_PRICE: 125,
            self.COL_RESERVED: 130,
            self.COL_STATUS: 120,
        }
        for col, width in widths.items():
            self.table.setColumnWidth(col, width)
        h.setSectionResizeMode(self.COL_NAME, QHeaderView.Stretch)
        h.setSectionResizeMode(self.COL_SELECT, QHeaderView.Fixed)
        h.setSectionResizeMode(self.COL_ACTIONS, QHeaderView.Fixed)
        self.table.setColumnWidth(self.COL_SELECT, 42)
        self.table.setColumnWidth(self.COL_ACTIONS, 60)

        self.table.verticalHeader().setDefaultSectionSize(40)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(False)

        h.setSectionsClickable(True)
        h.setSortIndicatorShown(True)
        h.setSortIndicator(self.COL_ID, Qt.DescendingOrder)
        h.sectionClicked.connect(self._handle_header_sort)

        self.table.clicked.connect(self._on_table_click)
        self.table.verticalScrollBar().valueChanged.connect(self._check_scroll_position)

        return self.table

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def load_combos(self):
        self.filter_category.blockSignals(True)
        self.filter_category.clear()
        self.filter_category.addItem("Toutes Catégories", None)
        try:
            for c in self.manager.categories.get_all_categories():
                self.filter_category.addItem(c['name'], c['id'])
        except Exception:
            pass
        self.filter_category.blockSignals(False)

    def reset_and_load(self):
        self.selected_items.clear()
        self._update_bulk_actions()
        self.table.setSortingEnabled(False)
        self.table.clearContents()
        self.table.setRowCount(0)
        self.offset     = 0
        self.all_loaded = False
        self._total_count = 0
        self._total_weight = 0.0
        self.load_batch()

    def load_batch(self):
        if self.is_loading or self.all_loaded:
            return
        self.is_loading = True
        self.lbl_status.setText("Chargement en cours...")

        try:
            include_totals = self.offset == 0
            items, total_count, total_weight = self.manager.inventory.get_inventory_paginated(
                limit=self.limit,
                offset=self.offset,
                search_text=self.search_input.text().strip(),
                show_zero_stock=self.chk_show_zero.isChecked(),
                category_id=self.filter_category.currentData(),
                sort_col=self.sort_col,
                sort_dir=self.sort_dir,
                status_filter=self.combo_status_filter.currentData(),
                min_weight=self.filter_min_weight, # 🟢 تمرير الحد الأدنى للوزن
                max_weight=self.filter_max_weight, # 🟢 تمرير الحد الأقصى للوزن
                include_totals=include_totals,
            )
            if include_totals:
                self._total_count = total_count
                self._total_weight = total_weight
            else:
                total_count = self._total_count
                total_weight = self._total_weight

            if items:
                self.table.setUpdatesEnabled(False)
                try:
                    self._append_to_table(items)
                finally:
                    self.table.setUpdatesEnabled(True)
                    self.table.viewport().update()
                self.offset += len(items)
                self.all_loaded = self.offset >= total_count
                self.lbl_status.setText(
                    f"Affichage: {self.table.rowCount()} / {total_count} articles"
                    f"   |   ⚖️ Poids Total : {total_weight:,.2f} g"
                )
            else:
                self.all_loaded = True
                self.lbl_status.setText(
                    f"Fin de la liste ({total_count} articles)"
                    f"   |   ⚖️ Poids Total : {total_weight:,.2f} g."
                )
        except Exception as e:
            self.lbl_status.setText("Erreur de chargement.")

        self.is_loading = False

    def _show_virtual_keyboard(self):
        if not hasattr(self, 'vkb') or self.vkb is None:
            from ui.tools.virtual_keyboard import VirtualKeyboardDialog

            self.vkb = VirtualKeyboardDialog(self.window())
        
        self.vkb.show()
        self.vkb.raise_()
        self.search_input.setFocus()
    # ------------------------------------------------------------------
    # Table population
    # ------------------------------------------------------------------

    def _append_to_table(self, items: list):
        self.table.setSortingEnabled(False)
        start_row = self.table.rowCount()
        self.table.setRowCount(start_row + len(items))

        for i, item in enumerate(items):
            row = start_row + i
            i_type = item.get('item_type', 'WEIGHT')
            item_id = item.get('id')

            chk_select = QCheckBox()
            chk_select.setCursor(Qt.PointingHandCursor)
            chk_select.setToolTip("Selectionner pour action groupée")
            chk_select.setChecked(item_id in self.selected_items)
            chk_select.stateChanged.connect(
                lambda _state, d=item, cb=chk_select: self._set_item_selected(d, cb.isChecked())
            )
            select_container = QWidget()
            select_container.setStyleSheet("background-color: transparent;")
            select_layout = QHBoxLayout(select_container)
            select_layout.setContentsMargins(0, 0, 0, 0)
            select_layout.setAlignment(Qt.AlignCenter)
            select_layout.addWidget(chk_select)
            self.table.setCellWidget(row, self.COL_SELECT, select_container)

            self.table.setItem(row, self.COL_ID,
                SortableTableWidgetItem(str(item.get('id')), item.get('id')))
            self.table.setItem(row, self.COL_BARCODE,
                QTableWidgetItem(str(item.get('barcode') or "-")))

            name_item = QTableWidgetItem(str(item.get('name') or ""))
            name_item.setData(Qt.UserRole, item)
            self.table.setItem(row, self.COL_NAME, name_item)

            self.table.setItem(row, self.COL_CATEGORY,
                QTableWidgetItem(str(item.get('category_name') or "-")))
            self.table.setItem(row, self.COL_METAL,
                QTableWidgetItem(str(item.get('metal_type_name') or "-")))

            # Poids U.
            w_val = float(item.get('weight') or 0)
            w_item = SortableTableWidgetItem(
                f"{w_val:.2f} g" if i_type == 'WEIGHT' else "-", w_val
            )
            w_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, self.COL_WEIGHT, w_item)

            # Pds Reste
            rw_val = float(item.get('remaining_weight') or 0)
            rw_item = SortableTableWidgetItem(
                f"{rw_val:.2f} g" if i_type == 'WEIGHT' else "-", rw_val
            )
            rw_item.setTextAlignment(Qt.AlignCenter)
            if i_type == 'WEIGHT' and rw_val <= 0:
                rw_item.setBackground(QColor("#ffebee"))
                rw_item.setForeground(QColor("#c0392b"))
            elif i_type == 'WEIGHT':
                rw_item.setForeground(QColor("#27ae60"))
                rw_item.setFont(QFont("Arial", 10, QFont.Bold))
            self.table.setItem(row, self.COL_REM_W, rw_item)

            # Coût Façon
            labor_val = float(item.get('labor_cost_per_gram') or 0)
            labor_item = SortableTableWidgetItem(f"{labor_val:,.2f} DA", labor_val)
            labor_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, self.COL_LABOR, labor_item)

            # Type Marge
            margin_type = item.get('margin_type', 'FIXED')
            mt_item = QTableWidgetItem("%" if margin_type == "PERCENTAGE" else "Fixe")
            mt_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, self.COL_MTYPE, mt_item)

            # Marge
            margin_val = float(item.get('profit_margin') or 0)
            suffix = "%" if margin_type == "PERCENTAGE" else "DA"
            mg_item = SortableTableWidgetItem(f"{margin_val:,.2f} {suffix}", margin_val)
            mg_item.setTextAlignment(Qt.AlignCenter)
            mg_item.setForeground(QColor("#2980b9"))
            mg_item.setFont(QFont("Arial", 10, QFont.Bold))
            self.table.setItem(row, self.COL_MARGIN, mg_item)

            # Prix vente
            price_val = float(item.get('selling_price') or 0)
            p_item = SortableTableWidgetItem(f"{price_val:,.2f}", price_val)
            p_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(row, self.COL_PRICE, p_item)

            # Réservé
            reserved = str(item.get('reserved_client_name') or '-')
            res_item = QTableWidgetItem(reserved)
            res_item.setTextAlignment(Qt.AlignCenter)
            if reserved != '-':
                res_item.setForeground(QColor("#8e44ad"))
                res_item.setFont(QFont("Arial", 10, QFont.Bold))
            self.table.setItem(row, self.COL_RESERVED, res_item)

            # Statut
            status = str(item.get('status') or 'Available')
            st_item = QTableWidgetItem(status)
            if status == 'Partially_Sold':
                st_item.setForeground(QColor("#d35400"))
            elif status == 'Available' and rw_val > 0:
                st_item.setForeground(QColor("green"))
            else:
                st_item.setForeground(QColor("red"))
            self.table.setItem(row, self.COL_STATUS, st_item)

            # زر طباعة
            btn_print = QPushButton()
            btn_print.setIcon(self._print_icon)
            btn_print.setCursor(Qt.PointingHandCursor)
            btn_print.setFixedSize(28, 28)
            btn_print.setStyleSheet(
                "QPushButton { background-color: transparent; border: none; margin: 0px; padding: 0px; }"
                "QPushButton:hover { background-color: #e0e0e0; border-radius: 4px; }"
            )
            btn_print.clicked.connect(lambda checked=False, d=item: self._print_barcode_action(d))

            container = QWidget()
            container.setStyleSheet("background-color: transparent;")
            cl = QHBoxLayout(container)
            cl.setContentsMargins(0, 0, 0, 0)
            cl.setAlignment(Qt.AlignCenter)
            cl.addWidget(btn_print)
            self.table.setCellWidget(row, self.COL_ACTIONS, container)

    # ------------------------------------------------------------------
    # Interactions
    # ------------------------------------------------------------------

    def _selected_items_list(self):
        return list(self.selected_items.values())

    def _set_item_selected(self, item: dict, checked: bool):
        item_id = item.get('id')
        if item_id is None:
            return
        if checked:
            self.selected_items[item_id] = item
        else:
            self.selected_items.pop(item_id, None)
        self._update_bulk_actions()

    def _update_bulk_actions(self):
        count = len(getattr(self, "selected_items", {}))
        if hasattr(self, "lbl_bulk_count"):
            self.lbl_bulk_count.setText(f"{count} selection" if count <= 1 else f"{count} selections")
        if hasattr(self, "btn_bulk_print"):
            self.btn_bulk_print.setEnabled(count > 0)
        if hasattr(self, "btn_bulk_delete"):
            self.btn_bulk_delete.setEnabled(count > 0)

    def toggle_visible_selection(self):
        visible_items = []
        for row in range(self.table.rowCount()):
            item = self.table.item(row, self.COL_NAME)
            if item and item.data(Qt.UserRole):
                visible_items.append(item.data(Qt.UserRole))
        if not visible_items:
            return

        should_select = any(item.get('id') not in self.selected_items for item in visible_items)
        for item in visible_items:
            item_id = item.get('id')
            if item_id is None:
                continue
            if should_select:
                self.selected_items[item_id] = item
            else:
                self.selected_items.pop(item_id, None)
        self._sync_selection_checkboxes()
        self._update_bulk_actions()

    def _sync_selection_checkboxes(self):
        for row in range(self.table.rowCount()):
            item = self.table.item(row, self.COL_NAME)
            item_data = item.data(Qt.UserRole) if item else None
            container = self.table.cellWidget(row, self.COL_SELECT)
            checkbox = container.findChild(QCheckBox) if container else None
            if checkbox and item_data:
                checkbox.blockSignals(True)
                checkbox.setChecked(item_data.get('id') in self.selected_items)
                checkbox.blockSignals(False)

    def _handle_header_sort(self, logical_index: int):
        if logical_index in (self.COL_SELECT, self.COL_ACTIONS):
            return
        if self.sort_col == logical_index:
            self.sort_dir = "DESC" if self.sort_dir == "ASC" else "ASC"
        else:
            self.sort_col = logical_index
            self.sort_dir = "ASC"
        qt_order = Qt.AscendingOrder if self.sort_dir == "ASC" else Qt.DescendingOrder
        self.table.horizontalHeader().setSortIndicator(logical_index, qt_order)
        self.reset_and_load()

    def _check_scroll_position(self, value: int):
        if self.is_loading or self.all_loaded:
            return
        max_val = self.table.verticalScrollBar().maximum()
        if max_val > 0 and value >= (max_val * 0.9):
            self.load_batch()

    def _on_table_click(self, index=None):
        if index is not None and index.column() in (self.COL_SELECT, self.COL_ACTIONS):
            return
        row = self.table.currentRow()
        if row < 0:
            return
        item = self.table.item(row, self.COL_NAME)
        if item and item.data(Qt.UserRole):
            from ui.dialogs.Product_edit import ProductEditDialog

            dialog = ProductEditDialog(self.manager, item.data(Qt.UserRole), self)
            if dialog.exec():
                self.reset_and_load()

    def _print_barcode_action(self, item_data: dict):
        label_config = load_label_config(self)
        if label_config is None:
            return
        if not label_config.get("printer_name"):
            QMessageBox.warning(self, "Erreur", "Aucune imprimante d'étiquettes n'est sélectionnée.")
            return
        from ui.dialogs.printer_label import LabelPrintPreviewDialog

        LabelPrintPreviewDialog(label_config, item_data, self).exec()

    def print_selected_items(self):
        items = self._selected_items_list()
        if not items:
            QMessageBox.warning(self, "Attention", "Selectionnez au moins un article.")
            return

        label_config = load_label_config(self)
        if label_config is None:
            return
        printer_name = label_config.get("printer_name")
        if not printer_name:
            QMessageBox.warning(self, "Erreur", "Aucune imprimante d'étiquettes n'est sélectionnée.")
            return

        from ui.dialogs.printer_label import LocalLabelPrinter

        printed = 0
        failures = []
        for item in items:
            try:
                img = LocalLabelPrinter.create_jewelry_label(label_config, item)
                raw_data = LocalLabelPrinter.get_tspl_for_image(label_config, img, 1)
                success, message = LocalLabelPrinter.send_to_printer(printer_name, raw_data)
                if success:
                    printed += 1
                else:
                    failures.append(f"{item.get('barcode') or item.get('id')}: {message}")
            except Exception as exc:
                failures.append(f"{item.get('barcode') or item.get('id')}: {exc}")

        if failures:
            QMessageBox.warning(
                self,
                "Impression partielle",
                f"{printed} etiquette(s) imprimee(s), {len(failures)} echec(s).\n\n"
                + "\n".join(failures[:8]),
            )
        else:
            QMessageBox.information(self, "Impression", f"{printed} etiquette(s) envoyee(s) a l'imprimante.")

    def _confirm_bulk_delete(self, items):
        count = len(items)
        first = QMessageBox.question(
            self,
            "Suppression groupee",
            f"Supprimer {count} article(s) selectionne(s) ?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if first != QMessageBox.Yes:
            return False

        second = QMessageBox.question(
            self,
            "Confirmation finale",
            "Cette action peut supprimer plusieurs produits du stock.\n"
            "Confirmez une deuxieme fois la suppression definitive.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        return second == QMessageBox.Yes

    def delete_selected_items(self):
        items = self._selected_items_list()
        if not items:
            QMessageBox.warning(self, "Attention", "Selectionnez au moins un article.")
            return
        if not self._confirm_bulk_delete(items):
            return

        deleted = []
        failed = []
        for item in items:
            item_id = item.get('id')
            if self.manager.inventory.delete_item(item_id):
                deleted.append(item)
            else:
                failed.append(item)

        self.selected_items.clear()
        self._update_bulk_actions()
        self.reset_and_load()

        if failed:
            QMessageBox.warning(
                self,
                "Suppression partielle",
                f"{len(deleted)} article(s) supprime(s), {len(failed)} echec(s).",
            )
        else:
            QMessageBox.information(self, "Suppression", f"{len(deleted)} article(s) supprime(s).")

    def _open_price_update_dialog(self):
        from ui.dialogs.price_update import PriceUpdateDialog

        if PriceUpdateDialog(self.manager, self).exec():
            self.reset_and_load()

    def _open_margin_update_dialog(self):
        from ui.dialogs.margin_update import MarginUpdateDialog

        if MarginUpdateDialog(self.manager, self).exec():
            self.reset_and_load()

    def refresh_data(self):
        self.load_combos()
        self.reset_and_load()

class WeightFilterDialog(QDialog):
    """نافذة لإدخال نطاق الوزن (أدنى وأقصى) مع دعم لوحة الأرقام الافتراضية"""
    def __init__(self, current_min, current_max, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Filtre par Poids (فلتر الوزن)")
        self.setFixedSize(350, 180) # قمنا بزيادة العرض قليلاً لاستيعاب الأزرار
        self.cleared = False
        
        layout = QVBoxLayout(self)
        form = QGridLayout()
        
        # --- حقل الحد الأدنى ---
        form.addWidget(QLabel("Poids Min (g) - الحد الأدنى:"), 0, 0)
        self.spin_min = QDoubleSpinBox()
        self.spin_min.setRange(0, 10000)
        self.spin_min.setDecimals(2)
        self.spin_min.setStyleSheet("font-size: 14px; padding: 5px;")
        if current_min is not None: self.spin_min.setValue(current_min)
        
        btn_kb_min = QPushButton()
        btn_kb_min.setIcon(qta.icon("fa5s.calculator", color="#34495e"))
        btn_kb_min.setFixedSize(35, 35)
        btn_kb_min.setCursor(Qt.PointingHandCursor)
        btn_kb_min.setStyleSheet("background-color: #ecf0f1; border: 1px solid #bdc3c7; border-radius: 4px;")
        btn_kb_min.clicked.connect(lambda: self._open_numpad(self.spin_min, "Saisir Poids Min"))
        
        min_layout = QHBoxLayout()
        min_layout.setContentsMargins(0, 0, 0, 0)
        min_layout.addWidget(self.spin_min)
        min_layout.addWidget(btn_kb_min)
        form.addLayout(min_layout, 0, 1)
        
        # --- حقل الحد الأقصى ---
        form.addWidget(QLabel("Poids Max (g) - الحد الأقصى:"), 1, 0)
        self.spin_max = QDoubleSpinBox()
        self.spin_max.setRange(0, 10000)
        self.spin_max.setDecimals(2)
        self.spin_max.setStyleSheet("font-size: 14px; padding: 5px;")
        if current_max is not None: self.spin_max.setValue(current_max)
        else: self.spin_max.setValue(50.0) # قيمة افتراضية
        
        btn_kb_max = QPushButton()
        btn_kb_max.setIcon(qta.icon("fa5s.calculator", color="#34495e"))
        btn_kb_max.setFixedSize(35, 35)
        btn_kb_max.setCursor(Qt.PointingHandCursor)
        btn_kb_max.setStyleSheet("background-color: #ecf0f1; border: 1px solid #bdc3c7; border-radius: 4px;")
        btn_kb_max.clicked.connect(lambda: self._open_numpad(self.spin_max, "Saisir Poids Max"))
        
        max_layout = QHBoxLayout()
        max_layout.setContentsMargins(0, 0, 0, 0)
        max_layout.addWidget(self.spin_max)
        max_layout.addWidget(btn_kb_max)
        form.addLayout(max_layout, 1, 1)
        
        layout.addLayout(form)
        
        # --- أزرار التأكيد والإلغاء ---
        btn_lay = QHBoxLayout()
        btn_clear = QPushButton(" Annuler Filtre")
        btn_clear.setIcon(qta.icon("fa5s.times", color="#c0392b"))
        btn_clear.setStyleSheet("font-weight: bold; padding: 8px;")
        btn_clear.clicked.connect(self.clear_filter)
        
        btn_apply = QPushButton(" Appliquer")
        btn_apply.setIcon(qta.icon("fa5s.check", color="white"))
        btn_apply.setStyleSheet("background-color: #8e44ad; color: white; font-weight: bold; padding: 8px;")
        btn_apply.clicked.connect(self.accept)
        
        btn_lay.addWidget(btn_clear)
        btn_lay.addWidget(btn_apply)
        layout.addLayout(btn_lay)

    def _open_numpad(self, target_widget, title):
        """يفتح لوحة الأرقام ويربطها مباشرة بالحقل المستهدف"""
        from ui.tools.virtual_numpad import VirtualNumpad

        numpad = VirtualNumpad(
            title=title,
            mode="direct",              # التحديث المباشر للرقم
            target_widget=target_widget, # الحقل المستهدف (SpinBox)
            allow_decimal=True,         # السماح بالفواصل للوزن
            parent=self
        )
        numpad.exec()
        
    def clear_filter(self):
        self.cleared = True
        self.accept()
        
    def get_values(self):
        return self.spin_min.value(), self.spin_max.value()
