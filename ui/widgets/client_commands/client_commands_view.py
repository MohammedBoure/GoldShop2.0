from __future__ import annotations

from types import SimpleNamespace

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
import qtawesome as qta

from ui.dialogs.client_selection_dialog import ClientSelectionDialog
from ui.dialogs.supplier_selection import SupplierSelectionDialog
from ui.deferred_loading import defer_initial_load
from ui.touch_design import (
    apply_touch_button_defaults,
    apply_touch_input_defaults,
    apply_touch_table_defaults,
)
from ui.widgets.inventory.touch_product_entry import wrap_with_numpad


COMMAND_STATUSES = [
    ("Tous", None),
    ("En attente", "PENDING"),
    ("Confirme", "CONFIRMED"),
    ("En fabrication", "IN_PROGRESS"),
    ("Pret", "READY"),
    ("Livre", "DELIVERED"),
    ("Annule", "CANCELLED"),
]

PAYMENT_STATUSES = [
    ("Tous", None),
    ("Non paye", "UNPAID"),
    ("Partiel", "PARTIAL"),
    ("Paye", "PAID"),
]


def _as_float(value) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _fmt_money(value) -> str:
    return f"{_as_float(value):,.2f}"


def _status_label(status: str) -> str:
    return {
        "PENDING": "En attente",
        "CONFIRMED": "Confirme",
        "IN_PROGRESS": "En fabrication",
        "READY": "Pret",
        "DELIVERED": "Livre",
        "CANCELLED": "Annule",
    }.get(str(status or ""), str(status or ""))


def _payment_label(status: str) -> str:
    return {
        "UNPAID": "Non paye",
        "PARTIAL": "Partiel",
        "PAID": "Paye",
    }.get(str(status or ""), str(status or ""))


class _ClientSelectionAdapter:
    def __init__(self, service):
        self.service = service

    def get_clients_paginated(self, search_text: str = "", limit: int = 50, offset: int = 0):
        if hasattr(self.service, "get_clients_paginated"):
            return self.service.get_clients_paginated(search_text=search_text, limit=limit, offset=offset)
        rows = list(self.service.get_all_clients() if hasattr(self.service, "get_all_clients") else [])
        needle = str(search_text or "").strip().casefold()
        if needle:
            rows = [
                row for row in rows
                if needle in str(row.get("name") or "").casefold()
                or needle in str(row.get("phone") or "").casefold()
            ]
        return rows[offset:offset + limit]

    def add_customer(self, name: str, phone: str = "", address: str = "", notes: str = ""):
        if hasattr(self.service, "add_customer"):
            return self.service.add_customer(name=name, phone=phone, address=address, notes=notes)
        if hasattr(self.service, "add_client"):
            return self.service.add_client(name=name, phone=phone, address=address, notes=notes)
        return None

    def get_customer_by_id(self, client_id):
        if hasattr(self.service, "get_customer_by_id"):
            return self.service.get_customer_by_id(client_id)
        if hasattr(self.service, "get_client_by_id"):
            return self.service.get_client_by_id(client_id)
        for row in self.get_clients_paginated("", limit=1000, offset=0):
            if int(row.get("id") or 0) == int(client_id or 0):
                return row
        return None


class ClientCommandEditorDialog(QDialog):
    def __init__(self, manager, parent=None, command: dict | None = None):
        super().__init__(parent)
        self.manager = manager
        self.command = dict(command or {})
        self.vkb = None
        self._selected_client = {}
        self._selected_supplier = {}
        self.setWindowTitle("Modifier commande client" if self.command else "Nouvelle commande client")
        self.setMinimumSize(940, 640)
        self._resize_for_touch_screen()
        self._init_ui()
        self._load_references()
        if self.command:
            self._populate_command(self.command)

    def _resize_for_touch_screen(self):
        screen = QApplication.primaryScreen()
        if not screen:
            self.resize(1040, 720)
            return
        available = screen.availableGeometry()
        width = min(max(1040, int(available.width() * 0.88)), max(940, available.width() - 40))
        height = min(max(680, int(available.height() * 0.84)), max(620, available.height() - 70))
        self.resize(width, height)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        title = QLabel("Commande pour produit non disponible")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(12)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setTabPosition(QTabWidget.North)
        client_tab, client_layout = self._tab_page()
        product_tab, product_layout = self._tab_page()
        pricing_tab, pricing_layout = self._tab_page()
        payment_tab, payment_layout = self._tab_page()
        self.tabs.addTab(client_tab, "1. Client")
        self.tabs.addTab(product_tab, "2. Produit")
        self.tabs.addTab(pricing_tab, "3. Prix")
        self.tabs.addTab(payment_tab, "4. Paiement")
        content_layout.addWidget(self.tabs)

        self.client_combo = QComboBox()
        self.client_combo.setVisible(False)
        self.client_display = QLineEdit()
        self.client_display.setReadOnly(True)
        self.client_display.setPlaceholderText("Aucun client choisi")
        self.btn_select_client = QPushButton("Choisir / creer")
        self.btn_select_client.setIcon(qta.icon("fa5s.user-check", color="#0f8f83"))
        apply_touch_button_defaults(self.btn_select_client, primary=True)
        self.btn_select_client.clicked.connect(self._open_client_selection)
        client_selector = self._client_selector_widget()
        self.command_date = QDateEdit(QDate.currentDate())
        self.command_date.setCalendarPopup(True)
        self.expected_delivery = QDateEdit(QDate.currentDate().addDays(30))
        self.expected_delivery.setCalendarPopup(True)
        self.status_combo = QComboBox()
        self.status_combo.addItem("En attente", "PENDING")
        self.status_combo.addItem("Confirme", "CONFIRMED")
        self.status_combo.addItem("En fabrication", "IN_PROGRESS")
        self.status_combo.addItem("Pret", "READY")

        command_box = QGroupBox("Client et suivi")
        command_grid = QGridLayout(command_box)
        command_grid.setVerticalSpacing(10)
        command_grid.setHorizontalSpacing(12)
        self._add_grid_row(command_grid, 0, "Client:", client_selector, "Date commande:", self.command_date)
        self._add_grid_row(command_grid, 1, "Date livraison:", self.expected_delivery, "Etat initial:", self.status_combo)
        client_layout.addWidget(command_box)

        self.product_name = QLineEdit()
        self.category_combo = QComboBox()
        self.metal_combo = QComboBox()
        self.supplier_combo = QComboBox()
        self.supplier_combo.setVisible(False)
        self.supplier_display = QLineEdit()
        self.supplier_display.setReadOnly(True)
        self.supplier_display.setPlaceholderText("Aucun fournisseur choisi")
        self.btn_select_supplier = QPushButton("Choisir")
        self.btn_select_supplier.setIcon(qta.icon("fa5s.truck", color="#0f8f83"))
        apply_touch_button_defaults(self.btn_select_supplier)
        self.btn_select_supplier.clicked.connect(self._open_supplier_selection)
        supplier_selector = self._supplier_selector_widget()

        product_box = QGroupBox("Produit commande")
        product_grid = QGridLayout(product_box)
        product_grid.setVerticalSpacing(10)
        product_grid.setHorizontalSpacing(12)
        self._add_grid_row(product_grid, 0, "Produit:", self.product_name, "Categorie:", self.category_combo)
        self._add_grid_row(product_grid, 1, "Metal:", self.metal_combo, "Fournisseur:", supplier_selector)
        product_layout.addWidget(product_box)

        self.weight = self._double_spin(" g", decimals=3, maximum=99999)
        self.metal_cost = self._double_spin(" DA/g")
        self.labor_cost = self._double_spin(" DA/g")
        self.total_cost = self._double_spin(" DA")
        self.initial_cost = self._double_spin(" DA")
        self.margin_type = QComboBox()
        self.margin_type.addItem("Fixe", "FIXED")
        self.margin_type.addItem("Pourcentage", "PERCENTAGE")
        self.profit_margin = self._double_spin(" DA/g")
        self.selling_price = self._double_spin(" DA")

        pricing_box = QGroupBox("Poids, couts et prix")
        pricing_grid = QGridLayout(pricing_box)
        pricing_grid.setVerticalSpacing(10)
        pricing_grid.setHorizontalSpacing(12)
        self._add_grid_row(
            pricing_grid,
            0,
            "Poids:",
            self._numpad_row(self.weight, "Poids", allow_decimal=True),
            "Cout metal:",
            self._numpad_row(self.metal_cost, "Cout metal", allow_decimal=True),
        )
        self._add_grid_row(
            pricing_grid,
            1,
            "Facon:",
            self._numpad_row(self.labor_cost, "Cout facon", allow_decimal=True),
            "Type marge:",
            self.margin_type,
        )
        self._add_grid_row(
            pricing_grid,
            2,
            "Marge:",
            self._numpad_row(self.profit_margin, "Marge", allow_decimal=True),
            "Cout total:",
            self._numpad_row(self.total_cost, "Cout total", allow_decimal=True),
        )
        self._add_grid_row(
            pricing_grid,
            3,
            "Cout initial:",
            self._numpad_row(self.initial_cost, "Cout initial", allow_decimal=True),
            "Prix vente / total:",
            self._numpad_row(self.selling_price, "Prix vente", allow_decimal=True),
        )
        pricing_layout.addWidget(pricing_box)

        self.initial_payment = self._double_spin(" DA")
        self.payment_method = QComboBox()
        self.payment_method.addItem("Aucun paiement initial", "NONE")
        self.payment_method.addItem("Espece / caisse", "CASH")
        self.payment_method.addItem("TPE", "TPE")
        self.payment_method.addItem("Depuis versement libre", "VERSEMENT_LIBRE")
        self.payment_method.addItem("Autre", "OTHER")
        self.source_free = QComboBox()
        self.payment_location = QComboBox()
        self.btn_pay_all = QPushButton("Utiliser le total")
        apply_touch_button_defaults(self.btn_pay_all)

        self.payment_box = QGroupBox("Paiement initial")
        payment_grid = QGridLayout(self.payment_box)
        payment_grid.setVerticalSpacing(10)
        payment_grid.setHorizontalSpacing(12)
        self._add_grid_row(
            payment_grid,
            0,
            "Avance:",
            self._numpad_row(self.initial_payment, "Avance", allow_decimal=True),
            "Mode:",
            self.payment_method,
        )
        self._add_grid_row(payment_grid, 1, "Versement libre:", self.source_free, "Caisse:", self.payment_location)
        payment_grid.addWidget(self.btn_pay_all, 2, 2, 1, 2)
        payment_layout.addWidget(self.payment_box)

        self.notes = QTextEdit()
        self.notes.setMaximumHeight(90)
        notes_box = QGroupBox("Notes")
        notes_layout = QVBoxLayout(notes_box)
        notes_layout.addWidget(self.notes)
        payment_layout.addWidget(notes_box)
        for tab_layout in (client_layout, product_layout, pricing_layout, payment_layout):
            tab_layout.addStretch()

        for widget in (
            self.client_display,
            self.command_date,
            self.product_name,
            self.expected_delivery,
            self.status_combo,
            self.weight,
            self.category_combo,
            self.metal_combo,
            self.supplier_display,
            self.metal_cost,
            self.labor_cost,
            self.total_cost,
            self.initial_cost,
            self.margin_type,
            self.profit_margin,
            self.selling_price,
            self.initial_payment,
            self.payment_method,
            self.source_free,
            self.payment_location,
            self.notes,
        ):
            apply_touch_input_defaults(widget)

        for spin in (self.weight, self.metal_cost, self.labor_cost, self.profit_margin):
            spin.valueChanged.connect(self.calculate_totals)
        self.margin_type.currentIndexChanged.connect(self._on_margin_type_changed)
        self.payment_method.currentIndexChanged.connect(self._on_payment_method_changed)
        self.initial_payment.valueChanged.connect(self._on_initial_payment_changed)
        self.client_combo.currentIndexChanged.connect(self._load_free_sources)
        self.btn_pay_all.clicked.connect(lambda: self.initial_payment.setValue(self.selling_price.value()))

        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.btn_save = buttons.button(QDialogButtonBox.Save)
        self.btn_save.setText("Enregistrer")
        buttons.button(QDialogButtonBox.Cancel).setText("Annuler")
        save_key = "client_command_update" if self.command else "client_command_create"
        self.btn_save.setProperty("permission_key", save_key)
        self.btn_save.setProperty("permission_label", "Enregistrer commande client")
        self.btn_save.setProperty("ui_element_type", "action")
        self.btn_keyboard = QPushButton("Clavier")
        self.btn_keyboard.setToolTip("Clavier")
        self.btn_keyboard.setFocusPolicy(Qt.NoFocus)
        self.btn_previous = QPushButton("Precedent")
        self.btn_previous.setFocusPolicy(Qt.NoFocus)
        self.btn_next = QPushButton("Suivant")
        self.btn_next.setFocusPolicy(Qt.NoFocus)
        buttons.addButton(self.btn_keyboard, QDialogButtonBox.ActionRole)
        buttons.addButton(self.btn_previous, QDialogButtonBox.ActionRole)
        buttons.addButton(self.btn_next, QDialogButtonBox.ActionRole)
        self.btn_keyboard.clicked.connect(self.show_virtual_keyboard)
        self.btn_previous.clicked.connect(self._go_previous_tab)
        self.btn_next.clicked.connect(self._go_next_tab)
        self.tabs.currentChanged.connect(self._update_tab_nav)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        for button in buttons.buttons():
            apply_touch_button_defaults(button, primary=button == self.btn_save)
        layout.addWidget(buttons)
        self.calculate_totals()
        self._on_payment_method_changed()
        self._update_tab_nav()

    @staticmethod
    def _tab_page():
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(10, 12, 10, 10)
        layout.setSpacing(12)
        return page, layout

    def _numpad_row(self, widget, title, *, allow_decimal=True):
        return wrap_with_numpad(self, widget, title, allow_decimal=allow_decimal)

    def _client_selector_widget(self):
        container = QWidget()
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        row.addWidget(self.client_display, 1)
        row.addWidget(self.btn_select_client)
        row.addWidget(self.client_combo)
        return container

    def _supplier_selector_widget(self):
        container = QWidget()
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        row.addWidget(self.supplier_display, 1)
        row.addWidget(self.btn_select_supplier)
        row.addWidget(self.supplier_combo)
        return container

    def _client_selection_manager(self):
        customers = getattr(self.manager, "customers", None)
        if customers is not None and hasattr(customers, "get_clients_paginated"):
            return self.manager
        return SimpleNamespace(customers=_ClientSelectionAdapter(getattr(self.manager, "clients", None)))

    def _open_client_selection(self):
        dialog = ClientSelectionDialog(self._client_selection_manager(), self)
        if dialog.exec() != QDialog.Accepted:
            return
        client_id = dialog.selected_client_id
        if not client_id:
            return
        client = self._get_client_record(client_id)
        self._set_selected_client(client_id, self._client_label(client), client)

    def _open_supplier_selection(self):
        dialog = SupplierSelectionDialog(self.manager, self)
        if dialog.exec() != QDialog.Accepted:
            return
        supplier_id = dialog.get_selected_supplier_id()
        if not supplier_id:
            return
        supplier = self._get_supplier_record(supplier_id)
        self._set_selected_supplier(supplier_id, self._supplier_label(supplier), supplier)

    def _get_client_record(self, client_id):
        for service in (
            getattr(self.manager, "customers", None),
            getattr(self.manager, "clients", None),
        ):
            if service is None:
                continue
            for method_name in ("get_customer_by_id", "get_client_by_id"):
                method = getattr(service, method_name, None)
                if callable(method):
                    row = method(client_id)
                    if row:
                        return row
        return {"id": client_id, "name": f"Client #{client_id}"}

    def _get_supplier_record(self, supplier_id):
        service = getattr(self.manager, "suppliers", None)
        if service is not None:
            for method_name in ("get_supplier_by_id", "get_supplier"):
                method = getattr(service, method_name, None)
                if callable(method):
                    row = method(supplier_id)
                    if row:
                        return row
            if hasattr(service, "get_all_suppliers"):
                for row in service.get_all_suppliers() or []:
                    if int(row.get("id") or 0) == int(supplier_id or 0):
                        return row
        return {"id": supplier_id, "name": f"Fournisseur #{supplier_id}"}

    @staticmethod
    def _client_label(client):
        if not client:
            return ""
        phone = str(client.get("phone") or "").strip()
        name = str(client.get("name") or client.get("client_name") or client.get("id") or "").strip()
        return f"{name} - {phone}" if phone else name

    @staticmethod
    def _supplier_label(supplier):
        if not supplier:
            return ""
        phone = str(supplier.get("phone") or "").strip()
        name = str(supplier.get("name") or supplier.get("supplier_name") or supplier.get("id") or "").strip()
        return f"{name} - {phone}" if phone else name

    def _set_selected_client(self, client_id, label="", client=None):
        client_id = int(client_id) if client_id else None
        client = dict(client or {})
        if client_id and "id" not in client:
            client["id"] = client_id
        if not label:
            label = self._client_label(client) or (f"Client #{client_id}" if client_id else "")
        self._selected_client = client
        blocked = self.client_combo.blockSignals(True)
        self.client_combo.clear()
        self.client_combo.addItem(label or "Choisir un client", client_id)
        self.client_combo.setCurrentIndex(0)
        self.client_combo.blockSignals(blocked)
        self.client_display.setText(label)
        self._load_free_sources()

    def _set_selected_supplier(self, supplier_id, label="", supplier=None):
        supplier_id = int(supplier_id) if supplier_id else None
        supplier = dict(supplier or {})
        if supplier_id and "id" not in supplier:
            supplier["id"] = supplier_id
        if not label:
            label = self._supplier_label(supplier) or (f"Fournisseur #{supplier_id}" if supplier_id else "")
        self._selected_supplier = supplier
        blocked = self.supplier_combo.blockSignals(True)
        self.supplier_combo.clear()
        self.supplier_combo.addItem(label or "Aucun fournisseur", supplier_id)
        self.supplier_combo.setCurrentIndex(0)
        self.supplier_combo.blockSignals(blocked)
        self.supplier_display.setText(label)

    def _go_previous_tab(self):
        self.tabs.setCurrentIndex(max(0, self.tabs.currentIndex() - 1))

    def _go_next_tab(self):
        self.tabs.setCurrentIndex(min(self.tabs.count() - 1, self.tabs.currentIndex() + 1))

    def _update_tab_nav(self):
        index = self.tabs.currentIndex()
        self.btn_previous.setEnabled(index > 0)
        self.btn_next.setEnabled(index < self.tabs.count() - 1)

    def _keyboard_target(self):
        focus = QApplication.focusWidget()
        if focus is not None and (focus is self or self.isAncestorOf(focus)):
            target = self._editable_keyboard_target(focus)
            if target is not None:
                return target
        return self.product_name

    def _editable_keyboard_target(self, widget):
        current = widget
        while current is not None:
            try:
                if isinstance(current, QComboBox):
                    return current.lineEdit() if current.isEditable() else None
                if isinstance(current, (QLineEdit, QTextEdit)):
                    return current if current.isEnabled() else None
                current = current.parentWidget()
            except RuntimeError:
                return None
        return None

    def show_virtual_keyboard(self):
        target = self._keyboard_target()
        if target is not None:
            target.setFocus(Qt.OtherFocusReason)
        from ui.tools.virtual_keyboard import KeyboardFocusTracker, VirtualKeyboardDialog

        if target is not None:
            KeyboardFocusTracker.last_input_widget = target
        if self.vkb is None:
            self.vkb = VirtualKeyboardDialog(self)
        self.vkb.show()
        self.vkb.raise_()

    def close_virtual_keyboard(self):
        if self.vkb is None:
            return
        try:
            if self.vkb.isVisible():
                self.vkb.close()
        except RuntimeError:
            pass
        self.vkb = None

    def accept(self):
        self.close_virtual_keyboard()
        super().accept()

    def reject(self):
        self.close_virtual_keyboard()
        super().reject()

    def closeEvent(self, event):
        self.close_virtual_keyboard()
        super().closeEvent(event)

    @staticmethod
    def _double_spin(suffix="", decimals=2, maximum=999999999):
        spin = QDoubleSpinBox()
        spin.setDecimals(decimals)
        spin.setMaximum(maximum)
        spin.setSuffix(suffix)
        return spin

    @staticmethod
    def _add_grid_row(grid, row, label_a, widget_a, label_b="", widget_b=None):
        grid.addWidget(QLabel(label_a), row, 0)
        grid.addWidget(widget_a, row, 1)
        if widget_b is not None:
            grid.addWidget(QLabel(label_b), row, 2)
            grid.addWidget(widget_b, row, 3)

    def _load_combo(self, combo, rows, label_key="name"):
        combo.clear()
        combo.addItem("Aucun", None)
        for row in rows or []:
            combo.addItem(str(row.get(label_key) or row.get("name") or row.get("id")), row.get("id"))

    def _load_references(self):
        self._set_selected_client(None, "")
        self._set_selected_supplier(None, "")
        try:
            self._load_combo(self.category_combo, self.manager.categories.get_all_categories())
        except Exception:
            self.category_combo.clear()
            self.category_combo.addItem("Aucun", None)
        try:
            self._load_combo(self.metal_combo, self.manager.metal_types.get_all_metal_types())
        except Exception:
            self.metal_combo.clear()
            self.metal_combo.addItem("Aucun", None)
        self._load_payment_locations()
        self._load_free_sources()

    @staticmethod
    def _set_combo_data(combo, value):
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    @staticmethod
    def _set_date(edit, value):
        date = QDate.fromString(str(value or "")[:10], "yyyy-MM-dd")
        if date.isValid():
            edit.setDate(date)

    def _populate_command(self, command):
        client_id = command.get("client_id")
        self._set_selected_client(client_id, self._client_label(command), command)
        self._set_selected_supplier(command.get("supplier_id"), self._supplier_label(command), command)
        self.client_combo.setEnabled(False)
        self.client_display.setEnabled(False)
        self.btn_select_client.setEnabled(False)
        self._set_date(self.command_date, command.get("command_date"))
        self._set_date(self.expected_delivery, command.get("expected_delivery_date"))
        self._set_combo_data(self.status_combo, command.get("status"))
        self.product_name.setText(str(command.get("product_name") or ""))
        self._set_combo_data(self.category_combo, command.get("category_id"))
        self._set_combo_data(self.metal_combo, command.get("metal_type_id"))
        self.weight.setValue(_as_float(command.get("weight")))
        self.metal_cost.setValue(_as_float(command.get("metal_cost_per_gram")))
        self.labor_cost.setValue(_as_float(command.get("labor_cost_per_gram")))
        self.total_cost.setValue(_as_float(command.get("total_cost")))
        self.initial_cost.setValue(_as_float(command.get("initial_cost")))
        self._set_combo_data(self.margin_type, command.get("margin_type") or "FIXED")
        self.profit_margin.setValue(_as_float(command.get("profit_margin")))
        self.selling_price.setValue(_as_float(command.get("selling_price") or command.get("total_amount")))
        self.notes.setPlainText(str(command.get("notes") or ""))
        self.payment_box.setVisible(False)
        self.calculate_totals()

    def _load_payment_locations(self):
        self.payment_location.clear()
        self.payment_location.addItem("Choisir caisse", None)
        try:
            for row in self.manager.treasury.get_all_locations(only_active=True):
                self.payment_location.addItem(str(row.get("name") or row.get("id")), row.get("id"))
        except Exception:
            pass

    def _load_free_sources(self):
        self.source_free.clear()
        self.source_free.addItem("Aucun", None)
        client_id = self.client_combo.currentData()
        if not client_id:
            return
        try:
            for row in self.manager.client_payments.get_available_free_versements(client_id):
                amount = _fmt_money(row.get("remaining_amount") or row.get("available_amount"))
                label = f"{row.get('display_number') or row.get('document_number') or row.get('id')} - {amount} DA"
                self.source_free.addItem(label, row.get("id"))
        except Exception:
            pass

    def _on_margin_type_changed(self):
        self.profit_margin.setSuffix(" %" if self.margin_type.currentData() == "PERCENTAGE" else " DA/g")
        self.calculate_totals()

    def _on_payment_method_changed(self):
        method = self.payment_method.currentData()
        self.source_free.setEnabled(method == "VERSEMENT_LIBRE")
        self.payment_location.setEnabled(method in {"CASH", "TPE"})
        if method == "NONE":
            self.initial_payment.setValue(0)
        elif method in {"CASH", "TPE"}:
            self._select_single_payment_location()

    def _on_initial_payment_changed(self, value):
        if value > 0 and self.payment_method.currentData() == "NONE":
            self._set_payment_method("CASH")
            self._select_single_payment_location()
        elif value <= 0 and self.payment_method.currentData() != "NONE":
            self._set_payment_method("NONE")

    def _set_payment_method(self, method):
        index = self.payment_method.findData(method)
        if index >= 0 and self.payment_method.currentIndex() != index:
            self.payment_method.setCurrentIndex(index)

    def _select_single_payment_location(self):
        if self.payment_location.currentData():
            return
        if self.payment_location.count() == 2:
            self.payment_location.setCurrentIndex(1)

    def calculate_totals(self):
        weight = self.weight.value()
        metal = self.metal_cost.value()
        labor = self.labor_cost.value()
        margin = self.profit_margin.value()
        total_cost = (metal + labor) * weight
        profit_per_gram = (metal + labor) * (margin / 100.0) if self.margin_type.currentData() == "PERCENTAGE" else margin
        selling_price = total_cost + (profit_per_gram * weight)
        for spin, value in ((self.total_cost, total_cost), (self.initial_cost, total_cost), (self.selling_price, selling_price)):
            blocked = spin.blockSignals(True)
            spin.setValue(value)
            spin.blockSignals(blocked)

    def get_payload(self) -> dict:
        client_id = self.client_combo.currentData()
        product_name = self.product_name.text().strip()
        total_amount = self.selling_price.value()
        initial_payment = self.initial_payment.value()
        if not client_id:
            raise ValueError("Veuillez choisir un client.")
        if not product_name:
            raise ValueError("Veuillez saisir le nom du produit.")
        if total_amount <= 0:
            raise ValueError("Le prix total doit etre positif.")
        if self.weight.value() <= 0:
            raise ValueError("Le poids doit etre positif.")
        if initial_payment > total_amount:
            raise ValueError("L'avance ne peut pas depasser le prix total.")
        payload = {
            "client_id": int(client_id),
            "barcode": None,
            "product_name": product_name,
            "command_date": self.command_date.date().toString("yyyy-MM-dd"),
            "expected_delivery_date": self.expected_delivery.date().toString("yyyy-MM-dd"),
            "status": self.status_combo.currentData(),
            "item_type": "WEIGHT",
            "weight": self.weight.value(),
            "quantity": 1,
            "category_id": self.category_combo.currentData(),
            "metal_type_id": self.metal_combo.currentData(),
            "location_id": None,
            "supplier_id": self.supplier_combo.currentData(),
            "image_url": None,
            "metal_cost_per_gram": self.metal_cost.value(),
            "labor_cost_per_gram": self.labor_cost.value(),
            "total_cost": self.total_cost.value(),
            "initial_cost": self.initial_cost.value(),
            "profit_margin": self.profit_margin.value(),
            "margin_type": self.margin_type.currentData(),
            "selling_price": total_amount,
            "total_amount": total_amount,
            "initial_payment_amount": initial_payment,
            "notes": self.notes.toPlainText().strip(),
            "currency_id": 1,
        }
        if initial_payment <= 0:
            return payload

        method = self.payment_method.currentData()
        if method == "NONE":
            raise ValueError("Veuillez choisir le mode du paiement initial.")
        payload["payment_method"] = method
        if method == "VERSEMENT_LIBRE":
            source_id = self.source_free.currentData()
            if not source_id:
                raise ValueError("Veuillez choisir un versement libre.")
            payload["source_free_versement_id"] = source_id
            payload["source_amount_to_use"] = initial_payment
        elif method in {"CASH", "TPE"}:
            location_id = self.payment_location.currentData()
            if not location_id:
                raise ValueError("Veuillez choisir la caisse du paiement initial.")
            payload["cash_transaction"] = {
                "location_id": location_id,
                "currency_id": 1,
                "transaction_type": "CLIENT_COMMAND_PAYMENT",
            }
        return payload

    def get_update_payload(self) -> dict:
        payload = self.get_payload()
        for key in (
            "client_id",
            "initial_payment_amount",
            "payment_method",
            "cash_transaction",
            "source_free_versement_id",
            "source_amount_to_use",
            "currency_id",
        ):
            payload.pop(key, None)
        return payload


class ClientCommandPaymentDialog(QDialog):
    def __init__(self, manager, command: dict, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.command = dict(command or {})
        self.setWindowTitle("Ajouter paiement commande")
        self.setMinimumWidth(560)
        self._init_ui()
        self._load_sources()
        self._on_method_changed()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        total = _as_float(self.command.get("total_amount"))
        paid = _as_float(self.command.get("paid_amount"))
        remaining = max(0.0, total - paid)
        summary = QLabel(f"Reste a payer: {_fmt_money(remaining)} DA")
        summary.setObjectName("sectionTitle")
        layout.addWidget(summary)

        form = QFormLayout()
        form.setVerticalSpacing(10)
        self.amount = QDoubleSpinBox()
        self.amount.setDecimals(2)
        self.amount.setMaximum(999999999)
        self.amount.setSuffix(" DA")
        self.amount.setValue(remaining)
        self.method = QComboBox()
        self.method.addItem("Espece / caisse", "CASH")
        self.method.addItem("TPE", "TPE")
        self.method.addItem("Depuis versement libre", "VERSEMENT_LIBRE")
        self.method.addItem("Autre", "OTHER")
        self.source_free = QComboBox()
        self.location = QComboBox()
        self.notes = QTextEdit()
        self.notes.setMaximumHeight(80)
        for widget in (self.amount, self.method, self.source_free, self.location, self.notes):
            apply_touch_input_defaults(widget)
        self.method.currentIndexChanged.connect(self._on_method_changed)
        form.addRow("Montant:", self.amount)
        form.addRow("Mode:", self.method)
        form.addRow("Versement libre:", self.source_free)
        form.addRow("Caisse:", self.location)
        form.addRow("Notes:", self.notes)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.btn_save = buttons.button(QDialogButtonBox.Save)
        self.btn_save.setProperty("permission_key", "client_command_payment")
        self.btn_save.setProperty("permission_label", "Enregistrer paiement commande")
        self.btn_save.setProperty("ui_element_type", "action")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        for button in buttons.buttons():
            apply_touch_button_defaults(button, primary=button == self.btn_save)
        layout.addWidget(buttons)

    def _load_sources(self):
        self.source_free.clear()
        self.source_free.addItem("Aucun", None)
        client_id = self.command.get("client_id")
        try:
            for row in self.manager.client_payments.get_available_free_versements(client_id):
                amount = _fmt_money(row.get("remaining_amount") or row.get("available_amount"))
                label = f"{row.get('display_number') or row.get('document_number') or row.get('id')} - {amount} DA"
                self.source_free.addItem(label, row.get("id"))
        except Exception:
            pass

        self.location.clear()
        self.location.addItem("Choisir caisse", None)
        try:
            for row in self.manager.treasury.get_all_locations(only_active=True):
                self.location.addItem(str(row.get("name") or row.get("id")), row.get("id"))
        except Exception:
            pass

    def _on_method_changed(self):
        method = self.method.currentData()
        self.source_free.setEnabled(method == "VERSEMENT_LIBRE")
        self.location.setEnabled(method in {"CASH", "TPE"})

    def get_payload(self) -> dict:
        amount = self.amount.value()
        if amount <= 0:
            raise ValueError("Le montant doit etre positif.")
        method = self.method.currentData()
        payload = {
            "amount": amount,
            "payment_method": method,
            "notes": self.notes.toPlainText().strip(),
        }
        if method == "VERSEMENT_LIBRE":
            source_id = self.source_free.currentData()
            if not source_id:
                raise ValueError("Veuillez choisir un versement libre.")
            payload["source_free_versement_id"] = source_id
            payload["source_amount_to_use"] = amount
            return payload
        if method in {"CASH", "TPE"}:
            location_id = self.location.currentData()
            if not location_id:
                raise ValueError("Veuillez choisir une caisse.")
            payload["cash_transaction"] = {
                "location_id": location_id,
                "currency_id": 1,
                "transaction_type": "CLIENT_COMMAND_PAYMENT",
            }
        return payload


class ClientCommandDetailsDialog(QDialog):
    def __init__(self, manager, command_id: int, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.command_id = command_id
        self.setWindowTitle("Details commande client")
        self.setMinimumSize(760, 520)
        self._init_ui()
        self.load_data()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)
        self.summary = QLabel("")
        self.summary.setWordWrap(True)
        self.summary.setObjectName("sectionTitle")
        layout.addWidget(self.summary)
        self.info = QTableWidget(0, 2)
        self.info.setHorizontalHeaderLabels(["Champ", "Valeur"])
        self.info.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.info.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.info.setEditTriggers(QTableWidget.NoEditTriggers)
        apply_touch_table_defaults(self.info)
        layout.addWidget(self.info)
        self.payments = QTableWidget(0, 6)
        self.payments.setHorizontalHeaderLabels(["Date", "Montant", "Mode", "Source", "Caisse", "Notes"])
        self.payments.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.payments.setEditTriggers(QTableWidget.NoEditTriggers)
        apply_touch_table_defaults(self.payments)
        layout.addWidget(self.payments, 1)
        close = QPushButton("Fermer")
        apply_touch_button_defaults(close)
        close.clicked.connect(self.accept)
        layout.addWidget(close)

    def load_data(self):
        command = self.manager.client_commands.get_command(self.command_id, include_payments=True) or {}
        self.summary.setText(
            f"{command.get('display_number') or command.get('command_number') or self.command_id} | "
            f"{command.get('client_name') or ''} | {command.get('product_name') or ''}\n"
            f"Total: {_fmt_money(command.get('total_amount'))} DA | "
            f"Paye: {_fmt_money(command.get('paid_amount'))} DA | "
            f"Etat: {_status_label(command.get('status'))}"
        )
        info_values = [
            ("Produit", command.get("product_name") or ""),
            ("Poids", f"{_as_float(command.get('weight')):,.3f} g"),
            ("Fournisseur", command.get("supplier_name") or command.get("supplier_id") or ""),
            ("Cout metal", f"{_fmt_money(command.get('metal_cost_per_gram'))} DA/g"),
            ("Facon", f"{_fmt_money(command.get('labor_cost_per_gram'))} DA/g"),
            ("Cout total", f"{_fmt_money(command.get('total_cost'))} DA"),
            ("Marge", f"{_fmt_money(command.get('profit_margin'))}"),
            ("Livraison prevue", str(command.get("expected_delivery_date") or "")[:10]),
            ("Stock lie", command.get("linked_inventory_barcode") or command.get("linked_inventory_id") or ""),
            ("Facture liee", command.get("linked_facture_number") or command.get("linked_sale_id") or ""),
        ]
        self.info.setRowCount(0)
        for label, value in info_values:
            row = self.info.rowCount()
            self.info.insertRow(row)
            self.info.setItem(row, 0, QTableWidgetItem(str(label)))
            self.info.setItem(row, 1, QTableWidgetItem(str(value or "")))
        rows = command.get("payments") or []
        self.payments.setRowCount(0)
        for payment in rows:
            row = self.payments.rowCount()
            self.payments.insertRow(row)
            values = [
                str(payment.get("payment_date") or "")[:16],
                _fmt_money(payment.get("amount")),
                str(payment.get("payment_method") or ""),
                str(payment.get("source_type") or ""),
                str(payment.get("location_id") or ""),
                str(payment.get("notes") or ""),
            ]
            for column, value in enumerate(values):
                self.payments.setItem(row, column, QTableWidgetItem(value))


class ClientCommandsView(QWidget):
    def __init__(self, manager):
        super().__init__()
        self.manager = manager
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel("Commandes client")
        title.setObjectName("pageTitle")
        header.addWidget(title)
        header.addStretch()

        self.btn_new = self._button("Nouvelle", "fa5s.plus-circle", "client_command_create", primary=True)
        self.btn_edit = self._button("Modifier", "fa5s.edit", "client_command_update")
        self.btn_payment = self._button("Paiement", "fa5s.hand-holding-usd", "client_command_payment")
        self.btn_details = self._button("Details", "fa5s.info-circle", "client_command_view")
        self.btn_inventory = self._button("Creer stock", "fa5s.box-open", "client_command_inventory")
        self.btn_refresh = self._button("Actualiser", "fa5s.sync-alt", "client_command_view")
        for button in (self.btn_new, self.btn_edit, self.btn_payment, self.btn_details, self.btn_inventory, self.btn_refresh):
            header.addWidget(button)
        layout.addLayout(header)

        filters = QFrame()
        filters.setObjectName("panel")
        filter_layout = QHBoxLayout(filters)
        filter_layout.setContentsMargins(10, 10, 10, 10)
        filter_layout.setSpacing(8)

        self.status_filter = QComboBox()
        for label, value in COMMAND_STATUSES:
            self.status_filter.addItem(label, value)
        self.payment_filter = QComboBox()
        for label, value in PAYMENT_STATUSES:
            self.payment_filter.addItem(label, value)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Client, produit, numero commande...")
        for widget in (self.status_filter, self.payment_filter, self.search):
            apply_touch_input_defaults(widget)
        filter_layout.addWidget(QLabel("Etat:"))
        filter_layout.addWidget(self.status_filter)
        filter_layout.addWidget(QLabel("Paiement:"))
        filter_layout.addWidget(self.payment_filter)
        filter_layout.addWidget(self.search, 1)
        layout.addWidget(filters)

        self.table = QTableWidget(0, 12)
        self.table.setHorizontalHeaderLabels([
            "ID",
            "Numero",
            "Client",
            "Date",
            "Livraison",
            "Produit",
            "Total",
            "Paye",
            "Reste",
            "Paiement",
            "Etat",
            "Liens",
        ])
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        apply_touch_table_defaults(self.table)
        layout.addWidget(self.table, 1)

        self.btn_new.clicked.connect(self.new_command)
        self.btn_edit.clicked.connect(self.edit_command)
        self.btn_payment.clicked.connect(self.add_payment)
        self.btn_details.clicked.connect(self.open_details)
        self.btn_inventory.clicked.connect(self.create_inventory)
        self.btn_refresh.clicked.connect(self.refresh_data)
        self.status_filter.currentIndexChanged.connect(self.refresh_data)
        self.payment_filter.currentIndexChanged.connect(self.refresh_data)
        self.search.returnPressed.connect(self.refresh_data)
        self.table.itemSelectionChanged.connect(self._update_actions)
        self.table.cellDoubleClicked.connect(lambda *_args: self.open_details())

        status_row = QHBoxLayout()
        self.btn_progress = self._button("En fabrication", "fa5s.cogs", "client_command_update")
        self.btn_ready = self._button("Pret", "fa5s.check", "client_command_update")
        self.btn_delivered = self._button("Livre", "fa5s.truck", "client_command_update")
        self.btn_cancel = self._button("Annuler", "fa5s.times-circle", "client_command_cancel", danger=True)
        for button in (self.btn_progress, self.btn_ready, self.btn_delivered, self.btn_cancel):
            status_row.addWidget(button)
        status_row.addStretch()
        layout.addLayout(status_row)

        self.btn_progress.clicked.connect(lambda: self._set_status("IN_PROGRESS"))
        self.btn_ready.clicked.connect(lambda: self._set_status("READY"))
        self.btn_delivered.clicked.connect(lambda: self._set_status("DELIVERED"))
        self.btn_cancel.clicked.connect(self.cancel_command)
        self._update_actions()
        defer_initial_load(self, self.refresh_data)

    def _button(self, text, icon, permission_key, primary=False, danger=False):
        button = QPushButton(text)
        button.setIcon(qta.icon(icon, color="#0f8f83"))
        button.setProperty("permission_key", permission_key)
        button.setProperty("permission_label", text)
        button.setProperty("ui_element_type", "action")
        apply_touch_button_defaults(button, primary=primary, danger=danger)
        return button

    def _bind_dialog(self, dialog, permission_key, label):
        binder = getattr(self.window(), "_bind_scoped_dialog", None)
        if callable(binder):
            return binder(dialog, permission_key, label)
        dialog.setProperty("permission_scope_key", permission_key)
        dialog.setProperty("permission_scope_label", label)
        return dialog

    def _command_service(self):
        return getattr(self.manager, "client_commands", None)

    def refresh_data(self):
        service = self._command_service()
        if service is None:
            QMessageBox.warning(self, "Commandes client", "Service commandes client indisponible.")
            return
        try:
            rows = service.get_commands(
                status=self.status_filter.currentData(),
                payment_status=self.payment_filter.currentData(),
                search_text=self.search.text().strip(),
                limit=500,
            )
        except Exception as exc:
            QMessageBox.critical(self, "Commandes client", str(exc))
            rows = []
        self.table.setRowCount(0)
        for command in rows:
            self._append_command(command)
        self._update_actions()

    def _append_command(self, command: dict):
        row = self.table.rowCount()
        self.table.insertRow(row)
        total = _as_float(command.get("total_amount"))
        paid = _as_float(command.get("paid_amount"))
        links = []
        if command.get("linked_inventory_id"):
            links.append(f"Stock #{command.get('linked_inventory_id')}")
        if command.get("linked_sale_id"):
            links.append(f"Facture #{command.get('linked_sale_id')}")
        values = [
            command.get("id"),
            command.get("display_number") or command.get("command_number") or "",
            command.get("client_name") or "",
            str(command.get("command_date") or "")[:10],
            str(command.get("expected_delivery_date") or "")[:10],
            command.get("product_name") or "",
            _fmt_money(total),
            _fmt_money(paid),
            _fmt_money(max(0.0, total - paid)),
            _payment_label(command.get("payment_status")),
            _status_label(command.get("status")),
            " | ".join(links),
        ]
        for column, value in enumerate(values):
            item = QTableWidgetItem(str(value or ""))
            if column == 0:
                item.setData(Qt.UserRole, command)
            if column in {6, 7, 8}:
                item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(row, column, item)

    def _selected_command(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return item.data(Qt.UserRole) if item else None

    def _update_actions(self):
        command = self._selected_command()
        has_command = bool(command)
        status = str((command or {}).get("status") or "").upper()
        payment_status = str((command or {}).get("payment_status") or "").upper()
        payable = has_command and status not in {"CANCELLED", "DELIVERED"} and payment_status != "PAID"
        for button in (
            self.btn_payment,
            self.btn_edit,
            self.btn_details,
            self.btn_inventory,
            self.btn_progress,
            self.btn_ready,
            self.btn_delivered,
            self.btn_cancel,
        ):
            button.setEnabled(has_command)
        self.btn_payment.setEnabled(payable)
        self.btn_edit.setEnabled(has_command and status not in {"CANCELLED", "DELIVERED"})
        self.btn_inventory.setEnabled(has_command and not command.get("linked_inventory_id") and status != "CANCELLED")
        self.btn_cancel.setEnabled(has_command and status not in {"CANCELLED", "DELIVERED"})
        self.btn_delivered.setEnabled(has_command and status != "CANCELLED")

    def new_command(self):
        dialog = self._bind_dialog(
            ClientCommandEditorDialog(self.manager, self),
            "client_command_create",
            "Nouvelle commande client",
        )
        if dialog.exec() != QDialog.Accepted:
            return
        try:
            payload = dialog.get_payload()
            command_id = self.manager.client_commands.create_command(**payload)
        except Exception as exc:
            QMessageBox.critical(self, "Commandes client", str(exc))
            return
        if not command_id:
            QMessageBox.critical(self, "Commandes client", "Impossible d'enregistrer la commande.")
            return
        self.refresh_data()
        QMessageBox.information(self, "Commandes client", f"Commande #{command_id} enregistree.")

    def edit_command(self):
        command = self._selected_command()
        if not command:
            return
        full_command = self.manager.client_commands.get_command(int(command["id"]), include_payments=False) or command
        dialog = self._bind_dialog(
            ClientCommandEditorDialog(self.manager, self, command=full_command),
            "client_command_update",
            "Modifier commande client",
        )
        if dialog.exec() != QDialog.Accepted:
            return
        try:
            ok = self.manager.client_commands.update_command(int(command["id"]), **dialog.get_update_payload())
        except Exception as exc:
            QMessageBox.critical(self, "Commandes client", str(exc))
            return
        if not ok:
            QMessageBox.critical(self, "Commandes client", "Impossible de modifier la commande.")
            return
        self.refresh_data()

    def add_payment(self):
        command = self._selected_command()
        if not command:
            return
        dialog = self._bind_dialog(
            ClientCommandPaymentDialog(self.manager, command, self),
            "client_command_payment",
            "Paiement commande client",
        )
        if dialog.exec() != QDialog.Accepted:
            return
        try:
            payload = dialog.get_payload()
            payment_id = self.manager.client_commands.add_command_payment(command["id"], **payload)
        except Exception as exc:
            QMessageBox.critical(self, "Commandes client", str(exc))
            return
        if not payment_id:
            QMessageBox.critical(self, "Commandes client", "Impossible d'ajouter le paiement.")
            return
        self.refresh_data()

    def open_details(self):
        command = self._selected_command()
        if not command:
            return
        self._bind_dialog(
            ClientCommandDetailsDialog(self.manager, int(command["id"]), self),
            "client_command_view",
            "Details commande client",
        ).exec()

    def create_inventory(self):
        command = self._selected_command()
        if not command:
            return
        inventory_id = self.manager.client_commands.create_inventory_from_command(int(command["id"]))
        if not inventory_id:
            QMessageBox.critical(self, "Commandes client", "Impossible de creer le produit en stock.")
            return
        self.refresh_data()
        QMessageBox.information(self, "Commandes client", f"Produit stock #{inventory_id} cree et reserve.")

    def _set_status(self, status: str):
        command = self._selected_command()
        if not command:
            return
        ok = self.manager.client_commands.set_command_status(int(command["id"]), status)
        if not ok:
            QMessageBox.critical(self, "Commandes client", "Impossible de changer l'etat.")
            return
        self.refresh_data()

    def cancel_command(self):
        command = self._selected_command()
        if not command:
            return
        reply = QMessageBox.question(
            self,
            "Annuler commande",
            "Annuler cette commande client ?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        ok = self.manager.client_commands.cancel_command(int(command["id"]), allow_paid=False)
        if not ok:
            QMessageBox.warning(
                self,
                "Commandes client",
                "Impossible d'annuler cette commande. Elle contient peut-etre deja un paiement.",
            )
            return
        self.refresh_data()
