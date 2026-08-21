# ui/widgets/versements/versements_view.py

import os
import json
import re
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QStyledItemDelegate, QLabel, QLineEdit, QComboBox,
    QMenu, QMessageBox, QDialog, QAbstractScrollArea, QFormLayout, QFrame,
    QDoubleSpinBox, QApplication, QGroupBox, QCompleter
)
from PySide6.QtCore import Qt, QUrl, QSize, QStringListModel, QTimer
from PySide6.QtGui import QColor, QFont, QBrush, QDesktopServices
import qtawesome as qta

try:
    from ui.tools.invoice_generator import ReceiptGenerator
except ImportError:
    ReceiptGenerator = None

from database.versement import (
    payment_value_da as calculate_payment_value_da,
    price_after_discount,
    shop_price_per_gram,
    calculate_versement_item_balances,
)

from ui.widgets.versements.invoice_note_selector import (
    create_invoice_note_combo,
    normalize_custom_note,
    selected_custom_note,
)
from ui.widgets.versements.edit_payment_dialog import EditPaymentDialog




class VersementTableDelegate(QStyledItemDelegate):
    """Paint separator rows as a solid full-width band."""

    def paint(self, painter, option, index):
        data = index.data(Qt.UserRole)
        if isinstance(data, dict) and data.get("type") == "SEPARATOR":
            painter.save()
            painter.fillRect(option.rect, QColor("#0f8f83"))
            painter.restore()
            return
        super().paint(painter, option, index)


def _open_numpad(widget, allow_decimal=True, parent=None):
    try:
        widget.setFocus()
        from ui.tools.virtual_numpad import VirtualNumpad
        pad = VirtualNumpad(mode="direct", target_widget=widget, allow_decimal=allow_decimal, allow_negative=True, parent=parent)
        pad.exec()
    except Exception:
        pass

def _open_vkb(widget, parent=None):
    try:
        widget.setFocus()
        from ui.tools.virtual_keyboard import VirtualKeyboardDialog
        kb = VirtualKeyboardDialog(parent)
        kb.show()
    except Exception:
        pass

def _wrap_with_numpad(widget, allow_decimal=True, parent=None):
    container = QWidget()
    lay = QHBoxLayout(container)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(5)
    lay.addWidget(widget, stretch=1)
    
    btn = QPushButton("🔢")
    btn.setFocusPolicy(Qt.NoFocus)
    btn.setFixedSize(38, 38)
    btn.setStyleSheet("background-color: #ecf0f1; border: 1px solid #bdc3c7; border-radius: 4px; font-size: 16px;")
    btn.setCursor(Qt.PointingHandCursor)
    btn.clicked.connect(lambda: _open_numpad(widget, allow_decimal, parent))
    lay.addWidget(btn)
    return container

def _wrap_with_keyboard(widget, parent=None):
    container = QWidget()
    lay = QHBoxLayout(container)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(5)
    lay.addWidget(widget, stretch=1)
    
    btn = QPushButton("⌨️")
    btn.setFocusPolicy(Qt.NoFocus)
    btn.setFixedSize(38, 38)
    btn.setStyleSheet("background-color: #ecf0f1; border: 1px solid #bdc3c7; border-radius: 4px; font-size: 16px;")
    btn.setCursor(Qt.PointingHandCursor)
    target = widget.lineEdit() if isinstance(widget, QComboBox) and widget.lineEdit() else widget
    btn.clicked.connect(lambda: _open_vkb(target, parent))
    lay.addWidget(btn)
    return container

def _move_dialog_to_top(dialog):
    """نقل النافذة المنبثقة إلى أعلى الشاشة لتوفير المساحة للوحة المفاتيح"""
    screen = QApplication.primaryScreen().availableGeometry()
    dialog.move(int((screen.width() - dialog.width()) / 2), 0)


# ========================================================
# نافذة قراءة الباركود وإضافة منتج إضافي للملف
# ========================================================
class AddItemToVersementDialog(QDialog):
    def __init__(self, manager, versement_id, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.versement_id = versement_id
        self.inventory_id = None
        self.designation = ""
        self.setWindowTitle("Ajouter un article au dossier")
        self.setMinimumWidth(450)
        self.init_ui()

    def showEvent(self, event):
        super().showEvent(event)
        _move_dialog_to_top(self)

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        title = QLabel("Scanner le code-barres de l'article")
        title.setFont(QFont("", 12, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        self.inp_barcode = QLineEdit()
        self.inp_barcode.setPlaceholderText("Code-barres...")
        self.inp_barcode.setStyleSheet("font-size: 16px; padding: 10px; border: 2px solid #3498db; border-radius: 6px;")
        self.inp_barcode.returnPressed.connect(self.search_item)
        self.inp_barcode.installEventFilter(self)
        
        # إضافة زر الكيبورد للباركود
        layout.addWidget(_wrap_with_keyboard(self.inp_barcode, self))
        
        self.lbl_result = QLabel("")
        self.lbl_result.setStyleSheet("font-size: 14px; font-weight: bold; color: #2c3e50;")
        self.lbl_result.setWordWrap(True)
        self.lbl_result.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_result)

        lbl_note = QLabel("<b>Note / Observation / À Vendre pour cet article :</b>")
        lbl_note.setStyleSheet("font-size: 13px; color: #2c3e50;")
        layout.addWidget(lbl_note)
        self.combo_note = create_invoice_note_combo(self.manager, "", self)
        self.combo_note.setEditable(True)
        layout.addWidget(_wrap_with_keyboard(self.combo_note, self))
        
        btn_layout = QHBoxLayout()
        self.btn_add = QPushButton(" Ajouter au dossier")
        self.btn_add.setIcon(qta.icon("fa5s.plus", color="white"))
        self.btn_add.setStyleSheet("background-color: #27ae60; color: white; padding: 10px; font-weight: bold; font-size: 14px; border-radius: 6px;")
        self.btn_add.setEnabled(False)
        self.btn_add.clicked.connect(self.add_item)
        
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_add)
        layout.addLayout(btn_layout)

    def eventFilter(self, obj, event):
        from PySide6.QtCore import QEvent
        if obj == self.inp_barcode and event.type() == QEvent.Type.KeyPress:
            text = event.text()
            if text:
                azerty_map = str.maketrans("&é\"'(-è_çà", "1234567890")
                corrected_text = text.translate(azerty_map).upper()
                if text != corrected_text:
                    self.inp_barcode.insert(corrected_text)
                    return True
        return super().eventFilter(obj, event)

    def search_item(self):
        barcode = self.inp_barcode.text().strip().upper()
        if not barcode: return
        
        try:
            with self.manager.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute("SELECT * FROM Inventory WHERE barcode = %s", (barcode,))
                item = cursor.fetchone()
                
                if not item:
                    self.lbl_result.setText("❌ Article introuvable.")
                    self.lbl_result.setStyleSheet("color: #e74c3c; font-weight: bold;")
                    self.btn_add.setEnabled(False)
                    self.inp_barcode.selectAll()
                    return
                    
                if item['status'] != 'Available':
                    self.lbl_result.setText(f"⚠️ Cet article n'est pas disponible (Statut: {item['status']}).")
                    self.lbl_result.setStyleSheet("color: #e67e22; font-weight: bold;")
                    self.btn_add.setEnabled(False)
                    self.inp_barcode.selectAll()
                    return
                    
                self.inventory_id = item['id']
                name = item.get('name') or item.get('item_name') or 'Article sans nom'
                weight = float(item.get('weight') or 0)
                self.designation = f"{name} ({weight:.2f}g)" if (weight > 0 and f"({weight:.2f}g)" not in name and not name.strip().endswith("g)")) else name
                
                self.lbl_result.setText(f"✅ Trouvé : {self.designation}")
                self.lbl_result.setStyleSheet("color: #27ae60; font-weight: bold;")
                self.btn_add.setEnabled(True)
                self.btn_add.setFocus()
        except Exception as e:
            self.lbl_result.setText(f"Erreur de recherche : {e}")

    def add_item(self):
        if self.inventory_id and self.designation:
            note_val = selected_custom_note(self.combo_note)
            if self.manager.versements.add_item_to_versement(self.versement_id, self.inventory_id, self.designation, notes=note_val):
                self.accept()
            else:
                QMessageBox.warning(self, "Erreur", "Impossible d'ajouter l'article au dossier.")


class VersementItemNoteDialog(QDialog):
    def __init__(self, manager, data, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.data = data
        self.setWindowTitle("Modifier l'Observation / Note du Produit")
        self.setMinimumWidth(540)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        title = QLabel(f"<b>Article :</b> {self.data.get('designation', '')}")
        title.setWordWrap(True)
        title.setStyleSheet("font-size: 14px; color: #1e293b;")
        layout.addWidget(title)

        existing_note = self.data.get("custom_note") or self.data.get("notes") or ""
        self.combo_note = create_invoice_note_combo(
            self.manager, existing_note, self
        )
        self.combo_note.setEditable(True)
        layout.addWidget(QLabel("<b>Observation / Note :</b> (Sélectionnez ou écrivez librement)"))
        layout.addWidget(_wrap_with_keyboard(self.combo_note, self))

        buttons = QHBoxLayout()
        btn_cancel = QPushButton("Annuler")
        btn_cancel.clicked.connect(self.reject)
        btn_save = QPushButton("Enregistrer")
        btn_save.setStyleSheet("background-color: #0f8f83; color: white; font-weight: bold; font-size: 14px; border-radius: 6px;")
        btn_save.clicked.connect(self.accept)
        for button in (btn_cancel, btn_save):
            button.setFixedHeight(42)
            buttons.addWidget(button)
        layout.addLayout(buttons)

    def get_product_note(self):
        return selected_custom_note(self.combo_note)


class VersementPaymentNoteDialog(QDialog):
    def __init__(self, manager, data, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.data = data
        self.setWindowTitle("Modifier la Note / Observation du Paiement")
        self.setMinimumWidth(520)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        p_id = self.data.get('payment_id')
        title = QLabel(f"<b>Paiement N° :</b> #{p_id}")
        title.setStyleSheet("font-size: 14px; color: #1e293b;")
        layout.addWidget(title)

        layout.addWidget(QLabel("<b>Observation / Note du Paiement :</b> (Texte libre)"))
        self.inp_note = QLineEdit()
        current_notes = str(self.data.get("notes") or "")
        clean_notes = re.sub(r'\[Remise:[^\]]+\]', '', current_notes).strip(" |")
        self.inp_note.setText(clean_notes)
        self.inp_note.setStyleSheet("font-size: 14px; padding: 8px; border: 1px solid #cbd5df; border-radius: 6px;")
        layout.addWidget(_wrap_with_keyboard(self.inp_note, self))

        buttons = QHBoxLayout()
        btn_cancel = QPushButton("Annuler")
        btn_cancel.clicked.connect(self.reject)
        btn_save = QPushButton("Enregistrer")
        btn_save.setStyleSheet("background-color: #0f8f83; color: white; font-weight: bold; font-size: 14px; border-radius: 6px;")
        btn_save.clicked.connect(self.accept)
        for button in (btn_cancel, btn_save):
            button.setFixedHeight(42)
            buttons.addWidget(button)
        layout.addLayout(buttons)

    def get_payment_note(self):
        return self.inp_note.text().strip()


# ========================================================
# الواجهة الرئيسية (Versements View)
# ========================================================
class VersementsView(QWidget):
    def __init__(self, manager):
        super().__init__()
        self.manager = manager
        self.current_page = 1
        self.total_pages = 1
        self.target_rows_per_page = 100
        
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(200)
        self._search_timer.timeout.connect(self._do_filter_changed)
        
        self.init_ui()
        self.load_data()

    def _on_search_text_changed(self):
        self._search_timer.stop()
        self._search_timer.start(200)

    def _do_filter_changed(self):
        self.current_page = 1
        self.load_data()

    def _on_filter_changed(self):
        self._do_filter_changed()

    def _go_first_page(self):
        if self.current_page != 1:
            self.current_page = 1
            self.load_data()

    def _go_prev_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self.load_data()

    def _go_next_page(self):
        if self.current_page < self.total_pages:
            self.current_page += 1
            self.load_data()

    def _go_last_page(self):
        if self.current_page != self.total_pages:
            self.current_page = self.total_pages
            self.load_data()

    @staticmethod
    def _estimate_versement_rows(v):
        items = v.get('items', [])
        payments = v.get('payments', [])
        statut = v.get('status', '')
        is_annule = (statut == 'ANNULE')

        rows = 1  # Header row
        rows += len(items)  # Item rows
        if is_annule and not payments:
            rows += 1
        elif not payments and not is_annule:
            rows += 1
        else:
            rows += len(payments)

        rows += 1  # Summary row for every versement
        rows += 1  # Separator row for all versements
        return rows

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        lbl_main_title = QLabel("SUIVI DES VERSEMENTS & ACOMPTES CLIENTS")
        lbl_main_title.setAlignment(Qt.AlignCenter)
        lbl_main_title.setStyleSheet("""
            font-size: 20px; font-weight: 900; color: white;
            background-color: #0f8f83; padding: 10px; border-radius: 4px; letter-spacing: 1px;
        """)
        layout.addWidget(lbl_main_title)

        tools_layout = QHBoxLayout()
        self.inp_search = QLineEdit()
        self.inp_search.setPlaceholderText("🔍 Rechercher par article, code-barres, client, tél, N° VRS...")
        self.inp_search.setStyleSheet("font-size: 13px; padding: 5px 8px; border: 1px solid #cbd5df; border-radius: 4px; background-color: white;")
        self.inp_search.setClearButtonEnabled(True)
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(300)
        self.search_timer.timeout.connect(self._do_filter_changed)
        self.inp_search.textChanged.connect(self.search_timer.start)

        tools_layout.addWidget(_wrap_with_keyboard(self.inp_search, self))

        self.combo_status = QComboBox()
        self.combo_status.addItems(["En Cours", "Clôturé", "Annulé", "Tous"])
        self.combo_status.setStyleSheet("font-size: 13px; padding: 5px 8px; border: 1px solid #cbd5df; border-radius: 4px; background-color: white;")
        self.combo_status.currentTextChanged.connect(self._on_filter_changed)
        tools_layout.addWidget(self.combo_status)

        self.btn_new = QPushButton(" + Nouveau Versement")
        self.btn_new.setIcon(qta.icon("fa5s.plus", color="white"))
        self.btn_new.setStyleSheet("""
            QPushButton { background-color: #27ae60; color: white; font-weight: bold; font-size: 13px; padding: 5px 12px; border-radius: 4px; }
            QPushButton:hover { background-color: #2ecc71; }
        """)
        self.btn_new.setCursor(Qt.PointingHandCursor)
        self.btn_new.clicked.connect(self.open_new_versement_dialog)
        tools_layout.addWidget(self.btn_new)

        self.toolbar_actions_widget = QWidget()
        self.toolbar_actions_layout = QHBoxLayout(self.toolbar_actions_widget)
        self.toolbar_actions_layout.setContentsMargins(0, 0, 0, 0)
        self.toolbar_actions_layout.setSpacing(5)
        tools_layout.addWidget(self.toolbar_actions_widget)
        tools_layout.addStretch()

        layout.addLayout(tools_layout)

        self.table = QTableWidget(0, 9)
        self.table.setItemDelegate(VersementTableDelegate(self.table))
        self.table.setHorizontalHeaderLabels([
            "Date / Opération", "Cash (DA)", "TPE (DA)", "Montant (€/$)", "Taux (DA/€/$)", "Or Cassé (g)", "Poids Déduit", "Statut", "Observation"
        ])
        
        self.table.setAlternatingRowColors(False)
        self.table.setStyleSheet("""
            QTableWidget { background-color: #ffffff; gridline-color: #dcdde1; border: 1px solid #cbd5df; }
            QHeaderView::section { background-color: #0f8f83; color: white; font-weight: bold; font-size: 14px; padding: 6px; border: 1px solid #0b776d; }
            QTableWidget::item { padding: 6px 10px; }
            QTableWidget::item:selected { background-color: #d1d8e0; color: #1f2937; }
        """)
        
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setMinimumSectionSize(14)
        self.table.setWordWrap(True)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.table.setSizeAdjustPolicy(QAbstractScrollArea.AdjustToContents)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        for i in range(1, 8): header.setSectionResizeMode(i, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(8, QHeaderView.Stretch)

        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        self.table.doubleClicked.connect(self._on_table_double_clicked)
        self.table.itemSelectionChanged.connect(self.on_table_selection_changed)
        layout.addWidget(self.table)

        # ─── شريط التحكم بالصفحات (Pagination Toolbar) ───
        page_layout = QHBoxLayout()
        page_layout.setContentsMargins(0, 5, 0, 0)
        page_layout.setSpacing(8)

        self.lbl_page_info = QLabel("Page 1 / 1 (0 dossiers)")
        self.lbl_page_info.setStyleSheet("font-size: 13px; font-weight: bold; color: #2c3e50;")

        self.btn_first_page = QPushButton("⏮")
        self.btn_prev_page = QPushButton("◀ Précédent")
        self.btn_next_page = QPushButton("Suivant ▶")
        self.btn_last_page = QPushButton("⏭")

        for btn in [self.btn_first_page, self.btn_prev_page, self.btn_next_page, self.btn_last_page]:
            btn.setStyleSheet("""
                QPushButton { background-color: #ecf0f1; color: #2c3e50; font-weight: bold; padding: 5px 12px; border: 1px solid #bdc3c7; border-radius: 4px; font-size: 13px; }
                QPushButton:hover { background-color: #d5dbdb; }
                QPushButton:disabled { background-color: #f2f3f4; color: #bdc3c7; border-color: #eaeded; }
            """)
            btn.setCursor(Qt.PointingHandCursor)

        self.btn_first_page.clicked.connect(self._go_first_page)
        self.btn_prev_page.clicked.connect(self._go_prev_page)
        self.btn_next_page.clicked.connect(self._go_next_page)
        self.btn_last_page.clicked.connect(self._go_last_page)

        page_layout.addWidget(self.lbl_page_info)
        page_layout.addStretch()
        page_layout.addWidget(self.btn_first_page)
        page_layout.addWidget(self.btn_prev_page)
        page_layout.addWidget(self.btn_next_page)
        page_layout.addWidget(self.btn_last_page)

        layout.addLayout(page_layout)

    # ──────────────────────────────────────────────────────────────
    # قراءة أسماء الطابعات من الإعدادات
    # ──────────────────────────────────────────────────────────────
    @staticmethod
    def _read_config_json():
        try:
            if os.path.exists("config.json"):
                with open("config.json", "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    @classmethod
    def _get_pdf_printer_name(cls):
        cfg = cls._read_config_json()
        return str(cfg.get("pdf_config", {}).get("printer_name", "") or "").strip()

    @classmethod
    def _get_thermal_printer_name(cls):
        cfg = cls._read_config_json()
        return str(cfg.get("thermal_config", {}).get("printer_name", "") or "").strip()

    # ──────────────────────────────────────────────────────────────
    # تجهيز بيانات Versement (مشتركة بين PDF و الحرارية)
    # ──────────────────────────────────────────────────────────────
    def _prepare_versement_data(self, versement_id):
        versements = getattr(self.manager.versements, 'get_versements', lambda **k: [])(status_filter=None)
        v_data = next((v for v in versements if v['id'] == versement_id), None)
        
        if not v_data:
            return None, None

        from database.versement import build_versement_payment_summary
        payment_summary = build_versement_payment_summary(v_data.get('payments', []))
        v_num = f"VRS-{v_data['id']:05d}"
        
        pdf_data = {
            "customer_name": v_data.get('client_name', 'Client Inconnu'),
            "phone": v_data.get('phone', ''),
            "sale_id": v_data['id'],
            "operation_number": v_num,
            "versement_operation_number": v_num,
            "versements": [],
            "items": [],
            "currency": "DA"
        }

        balances = calculate_versement_item_balances(v_data.get('items', []), v_data.get('payments', []))

        for item in v_data.get('items', []):
            if item.get('item_status') != 'ANNULE':
                desig = item.get('designation', '')
                item_type = str(item.get('item_type') or 'WEIGHT').upper()
                quantity = max(1, int(item.get('reserved_quantity') or 1)) if item_type == 'PIECE' else 1
                w = float(item.get('display_weight') or item.get('weight') or 0)
                quantity_suffix = f" x{quantity}" if item_type == 'PIECE' else ''
                full_name = f"{desig}{quantity_suffix} ({w:.2f}g)" if (w > 0 and f"({w:.2f}g)" not in desig and not desig.strip().endswith("g)")) else desig
                
                item_id = item.get('item_id') or item.get('id')
                bal = balances.get(item_id, {})
                item_remaining_w = bal.get('remaining_g', max(0.0, w - bal.get('deducted_g', 0.0)))
                item_paid_amount = bal.get('paid_da', 0.0)
                selling_price = float(item.get('display_price') or item.get('selling_price') or 0.0)
                pdf_data['items'].append({
                    "name": full_name,
                    "item_name": full_name,
                    "description": desig,
                    "barcode": item.get('barcode', ''),
                    "item_type": item_type,
                    "reserved_quantity": quantity,
                    "weight": w,
                    "total_weight": w,
                    "selling_price": selling_price,
                    "total_amount": selling_price,
                    "remaining_weight": item_remaining_w,
                    "paid_amount": item_paid_amount,
                    "custom_note": normalize_custom_note(item.get("custom_note")),
                })

        for p in v_data.get('payments', []):
            montant_da = float(p.get('montant_da') or 0)
            montant_tpe = float(p.get('tpe_da') or 0)
            montant_euro = float(p.get('montant_euro') or 0)
            taux = float(p.get('taux_change_euro') or 0)
            montant_dollar = float(p.get('montant_dollar') or 0)
            taux_dollar = float(p.get('taux_change_dollar') or 0)
            remise_da = float(p.get('remise_da') or 0)
            
            poids_casse = float(p.get('or_casse_g') or 0)
            poids_deduit = float(p.get('poids_deduit_g') or 0)
            
            payment_value = calculate_payment_value_da(p)
            shop_ppg = shop_price_per_gram(
                v_data.get("items", []), p.get("versement_item_id")
            )
            after_remise_ppg = price_after_discount(
                shop_ppg, payment_value, remise_da
            )
            total_money = payment_value
            total_weight_pay = poids_deduit

            item_desig = p.get('item_designation', '')
            if item_desig:
                for it in v_data.get('items', []):
                    if it.get('designation') == item_desig:
                        w = float(it.get('weight') or 0)
                        if w > 0 and f"({w:.2f}g)" not in item_desig and not item_desig.strip().endswith("g)"):
                            item_desig = f"{item_desig} ({w:.2f}g)"
                        break
            else:
                raw_notes = str(p.get('notes') or '').strip()
                clean_notes = re.sub(r'\[Remise:[^\]]+\]', '', raw_notes).strip(" |")
                if clean_notes:
                    item_desig = clean_notes
                elif total_money < 0:
                    item_desig = "Rendu surplus / Remboursement"
                elif poids_casse > 0:
                    item_desig = f"Paiement Or Cassé ({poids_casse:.2f}g)"
                elif montant_euro > 0:
                    item_desig = f"Paiement Euro ({montant_euro:,.0f}€)"
                elif montant_dollar > 0:
                    item_desig = f"Paiement Dollar ({montant_dollar:,.0f}$)"
                else:
                    item_desig = "Paiement Espèces / TPE"

            raw_payment_entry = {
                "id": p.get('id', ''),
                "payment_date": p.get('payment_date'),
                "amount": total_money,
                "tpe_da": montant_tpe,
                "montant_euro": montant_euro,
                "taux_change_euro": taux,
                "montant_dollar": montant_dollar,
                "taux_change_dollar": taux_dollar,
                "remise_da": remise_da,
                "weight": total_weight_pay,
                "prix_gramme_magasin": shop_ppg,
                "prix_gramme_apres_remise": after_remise_ppg,
                "product_name": item_desig,
                "item_name": item_desig,
                "operation_number": v_num
            }

            if total_money < 0:
                # Deduct negative amount directly from preceding positive payment(s)
                remaining_refund = abs(total_money)
                for prev in reversed(pdf_data['versements']):
                    prev_amt = float(prev.get('amount') or 0)
                    if prev_amt > 0:
                        deduction = min(prev_amt, remaining_refund)
                        prev['amount'] = prev_amt - deduction
                        remaining_refund -= deduction
                        if remaining_refund <= 0.001:
                            break
            else:
                pdf_data['versements'].append(raw_payment_entry)

        # Filter out any entries fully zeroed out unless it's the only one
        positive_versements = [
            v for v in pdf_data['versements']
            if float(v.get('amount') or 0) > 0.001 or float(v.get('weight') or 0) > 0.001
        ]
        if positive_versements:
            pdf_data['versements'] = positive_versements

        total_estimated_price = float(v_data.get('total_estimated_price_da', 0))
        pdf_data['total_weight'] = float(v_data.get('total_weight_g', 0))
        pdf_data['exact_paid_weight'] = float(v_data.get('total_paid_weight_g', 0))
        pdf_data['remaining_weight'] = float(v_data.get('reste_poids_g', 0))
        pdf_data['total_paid'] = payment_summary['total_paid_da']
        pdf_data['total_estimated_price_da'] = total_estimated_price
        pdf_data['total_remise_da'] = payment_summary['total_remise_da']
        pdf_data['total_dollar'] = payment_summary['dollar_paid']
        pdf_data['payment_summary'] = payment_summary
        pdf_data['cash_paid_da'] = payment_summary['cash_paid_da']
        pdf_data['tpe_paid_da'] = payment_summary['tpe_paid_da']
        pdf_data['euro_paid'] = payment_summary['euro_paid']
        pdf_data['old_gold_weight_g'] = payment_summary['old_gold_weight_g']
        pdf_data['deducted_weight_g'] = payment_summary['deducted_weight_g']
        pdf_data['total_amount'] = total_estimated_price if total_estimated_price > 0 else pdf_data['total_paid']
        pdf_data['total_quantity'] = sum(int(item.get('reserved_quantity') or 1) for item in pdf_data['items'])

        return pdf_data, v_data

    # ──────────────────────────────────────────────────────────────
    # القائمة المنبثقة (كليك يمين)
    # ──────────────────────────────────────────────────────────────
    def show_context_menu(self, pos):
        row = self.table.rowAt(pos.y())
        if row < 0: return
        item = self.table.item(row, 0)
        if not item: return
        
        data = item.data(Qt.UserRole)
        if not isinstance(data, dict): return
        
        row_type = data.get("type")
        v_id = data.get("v_id")
        v_statut = data.get("statut")

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { font-size: 15px; background-color: white; border: 1px solid #ccc; }
            QMenu::item { padding: 10px 30px; }
            QMenu::item:selected { background-color: #3498db; color: white; }
            QMenu::separator { height: 1px; background: #ddd; margin: 4px 10px; }
        """)
        
        act_print_pdf = act_print_direct = act_print_thermal = None
        act_pay_global = act_close = act_cancel = act_add_item = act_show_details = None
        act_reopen_versement = None
        act_pay_item = act_retirer_item = act_cancel_item = act_delete_item = act_edit_item_note = None
        act_change_item_status = None
        act_edit_pay = act_delete_pay = None

        if row_type == "HEADER":
            act_show_details = menu.addAction("ℹ️ Afficher les spécifications détaillées des articles")
            menu.addSeparator()
            pdf_printer = self._get_pdf_printer_name()
            thermal_printer = self._get_thermal_printer_name()

            act_print_pdf = menu.addAction("📄 Télécharger Bon (Aperçu PDF)")

            if pdf_printer:
                act_print_direct = menu.addAction(f"🖨️ Imprimer directement → {pdf_printer}")
            else:
                act_print_direct = menu.addAction("🖨️ Imprimer directement (non configurée)")
                act_print_direct.setEnabled(False)

            if thermal_printer:
                act_print_thermal = menu.addAction(f"🧾 Imprimer sur thermique → {thermal_printer}")
            else:
                act_print_thermal = menu.addAction("🧾 Imprimer sur thermique (non configurée)")
                act_print_thermal.setEnabled(False)

            if v_statut == 'EN_COURS':
                menu.addSeparator()
                act_add_item = menu.addAction("➕ Ajouter un nouvel article à ce dossier")
                menu.addSeparator()
                act_pay_global = menu.addAction("💵 Ajouter un paiement (Dossier Global)")
                act_close = menu.addAction("✅ Clôturer tout le dossier")
                menu.addSeparator()
                act_cancel = menu.addAction("❌ Annuler tout le dossier")
            elif v_statut in ('CLOTURE', 'ANNULE'):
                menu.addSeparator()
                act_reopen_versement = menu.addAction("🔄 Changer état : remettre le dossier En Cours")
            
        elif row_type == "ITEM":
            act_show_details = menu.addAction("ℹ️ Afficher les spécifications détaillées du produit")
            act_edit_item_note = menu.addAction("🏷️ Modifier Observation / Note")
            menu.addSeparator()
            item_status = data.get("item_status")
            if item_status == 'EN_COURS' and v_statut == 'EN_COURS':
                act_pay_item = menu.addAction("💵 Ajouter un paiement pour CET ARTICLE")
                act_retirer_item = menu.addAction("📦 Marquer cet article comme RETIRÉ (Livré)")
                menu.addSeparator()
                act_cancel_item = menu.addAction("❌ Annuler l'article (Retour vitrine)")
                act_delete_item = menu.addAction("🗑️ Supprimer du dossier (Erreur d'ajout)")
            elif item_status == 'RETIRE':
                act_change_item_status = menu.addAction("🔄 Changer état : remettre l'article En Cours")
            elif item_status == 'ANNULE':
                act_change_item_status = menu.addAction("🔄 Changer état : remettre l'article En Cours")
            else:
                menu.addAction("ℹ️ Le dossier est " + v_statut.lower())

        elif row_type == "PAYMENT" and v_statut == 'EN_COURS':
            act_edit_pay = menu.addAction("✏️ Modifier ce paiement")
            act_edit_pay_note = menu.addAction("📝 Modifier Observation / Note")
            act_delete_pay = menu.addAction("🗑️ Supprimer ce paiement (Erreur de saisie)")

        if menu.isEmpty(): return
        action = menu.exec_(self.table.viewport().mapToGlobal(pos))
        if not action: return
        
        if action == act_show_details:
            self.show_product_specs(data)
        elif action == act_print_pdf:
            self.print_versement_pdf(v_id, open_pdf=True, direct=False)
        elif action == act_print_direct:
            self.print_versement_pdf(v_id, open_pdf=False, direct=True)
        elif action == act_print_thermal:
            self.print_versement_thermal(v_id)
        elif action == act_add_item:
            self.open_add_item_dialog(v_id)
        elif action == act_pay_global:
            self.open_add_payment_dialog(v_id)
        elif action == act_pay_item:
            self.open_add_payment_dialog(v_id, preselected_item_id=data.get("item_id"))
        elif action == act_edit_item_note:
            self._handle_edit_item_note(data)
        elif action == act_retirer_item:
            self._handle_retirer_item(data)
        elif action == act_cancel_item:
            self._handle_cancel_item(data)
        elif action == act_delete_item:
            self._handle_delete_item(data)
        elif action == act_change_item_status:
            self._handle_change_item_status(data)
        elif action == act_close:
            self._handle_close_versement(v_id)
        elif action == act_cancel:
            self._handle_cancel_versement(v_id)
        elif action == act_reopen_versement:
            self._handle_change_versement_status(v_id, 'EN_COURS')
        elif action == act_delete_pay:
            self._handle_delete_payment(data)
        elif action == act_edit_pay:
            self._handle_edit_payment(data)
        elif action == act_edit_pay_note:
            self._handle_edit_payment_note(data)

    def _handle_edit_payment_note(self, data):
        dlg = VersementPaymentNoteDialog(self.manager, data, self)
        if dlg.exec() != QDialog.Accepted:
            return
        new_note = dlg.get_payment_note()
        if self.manager.versements.update_payment_notes(data.get("payment_id"), new_note):
            self.load_data()
        else:
            QMessageBox.warning(self, "Erreur", "Impossible d'enregistrer la note du paiement.")

    def _handle_edit_item_note(self, data):
        dlg = VersementItemNoteDialog(self.manager, data, self)
        if dlg.exec() != QDialog.Accepted:
            return

        product_note = dlg.get_product_note()
        if self.manager.versements.update_versement_item_notes(data.get("item_id"), product_note):
            self.load_data()
        else:
            QMessageBox.warning(self, "Erreur", "Impossible d'enregistrer À Vendre pour cet article.")

    def _handle_retirer_item(self, data):
        item_desig = data.get("designation", "")
        item_id = data.get("item_id")
        v_id = data.get("v_id")

        reply = QMessageBox.question(
            self,
            "Confirmer la livraison",
            f"Voulez-vous marquer cet article comme LIVRÉ (Retiré) ?\n\n💍 {item_desig}\n\n(L'article sera marqué comme livré et déduit du stock)",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        journee = self.manager.cash_box.get_or_create_today_session(user_id=1)
        if not journee:
            QMessageBox.critical(self, "Erreur", "La session de caisse est fermée. La livraison n'a pas été enregistrée.")
            return

        if not self.manager.versements.retirer_versement_item(item_id):
            QMessageBox.warning(self, "Erreur", "Impossible de livrer l'article.")
            return

        item_type = str(data.get("item_type") or "WEIGHT").upper()
        item_qty = int(data.get("quantity") or 1)
        
        if item_type == "PIECE":
            reserved_quantity = max(1, int(data.get("reserved_quantity") or 1))
            cart_sold_weight = 0.0
        else:
            reserved_quantity = 1
            original_weight = float(data.get("weight") or 0)
            if item_qty > 1:
                cart_sold_weight = round(original_weight / item_qty, 3)
                remaining_w = float(data.get("remaining_weight") if data.get("remaining_weight") is not None else original_weight)
                cart_sold_weight = min(cart_sold_weight, remaining_w)
            else:
                cart_sold_weight = float(data.get("remaining_weight") if data.get("remaining_weight") is not None else original_weight)

        price = float(data.get("selling_price") or data.get("display_price") or data.get("price") or 0.0)
        if price <= 0:
            try:
                with self.manager.db.get_db_connection() as conn:
                    cursor = conn.cursor(dictionary=True)
                    cursor.execute("SELECT selling_price FROM Inventory WHERE id = %s", (data.get("inventory_id"),))
                    row = cursor.fetchone()
                    if row:
                        price = float(row.get('selling_price') or 0.0)
            except Exception:
                price = 0.0

        client_id = data.get("client_id")
        if not client_id:
            try:
                versements = getattr(self.manager.versements, 'get_versements', lambda **k: [])(status_filter=None)
                v_data = next((v for v in versements if v['id'] == v_id), None)
                client_id = v_data.get('client_id') if v_data else 1
            except Exception:
                client_id = 1

        product_note = data.get("custom_note") or ""

        cart_items = [{
            'id': data.get("inventory_id"),
            'item_type': item_type,
            'barcode': data.get("barcode", ""),
            'name': data.get("designation", "Article Versement"),
            'cart_sold_weight': cart_sold_weight,
            'cart_sold_qty': reserved_quantity,
            'cart_unit_price': price / reserved_quantity if item_type == "PIECE" else price,
            'cart_line_total': price,
            'custom_note': product_note
        }]
        try:
            sale_result = self.manager.sales.create_sale(
                journee_id=journee['id'],
                client_id=client_id,
                user_id=1,
                cart_items=cart_items,
                total_amount=price,
                discount=0,
                net_to_pay=price,
                cash_paid=0,
                tpe_paid=0, old_gold_weight=0, impos_weight=0,
                notes=f"Livraison depuis Versement N°VRS-{v_id:05d}"
            )
        except Exception as exc:
            sale_result = {"success": False, "message": str(exc)}

        if not isinstance(sale_result, dict) or not sale_result.get("success"):
            reverted, revert_message = self.manager.versements.revert_versement_item_status(item_id)
            detail = sale_result.get("message", "Résultat invalide") if isinstance(sale_result, dict) else "Résultat invalide"
            if reverted:
                QMessageBox.critical(
                    self, "Facturation échouée",
                    f"La sortie de stock n'a pas été enregistrée ({detail}). L'article a été remis EN_COURS."
                )
            else:
                QMessageBox.critical(
                    self, "Erreur critique",
                    f"La sortie de stock n'a pas été enregistrée ({detail}) et le retour EN_COURS a échoué: {revert_message}"
                )
            self.load_data()
            return

        self.load_data()
        QMessageBox.information(self, "Livraison réussie", f"L'article '{item_desig}' a été marqué comme livré et déduit du stock avec succès.")


    def _handle_cancel_item(self, data):
        if QMessageBox.question(self, "Annuler", "Annuler cet article ? (Retour en vitrine)", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            if self.manager.versements.cancel_versement_item(data.get("item_id")): self.load_data()

    def _handle_delete_item(self, data):
        if QMessageBox.question(self, "Supprimer", "Voulez-vous supprimer définitivement cet article du dossier ?", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            success, msg = self.manager.versements.delete_versement_item(data.get("item_id"))
            if success: self.load_data()
            else: QMessageBox.warning(self, "Erreur", msg)

    def _handle_change_item_status(self, data):
        if QMessageBox.question(self, "Changer état", "Remettre cet article en cours dans le dossier ?", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            success, msg = self.manager.versements.revert_versement_item_status(data.get("item_id"))
            if success: self.load_data()
            else: QMessageBox.warning(self, "Erreur", msg)

    def _handle_close_versement(self, v_id):
        if QMessageBox.question(self, "Clôturer", "Confirmer la clôture de ce versement ?", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            journee = self.manager.cash_box.get_or_create_today_session(user_id=1)
            journee_id = journee['id'] if journee else 1
            success, msg = self.manager.versements.change_versement_status(v_id, 'CLOTURE', journee_id)
            if success: self.load_data()
            else: QMessageBox.warning(self, "Erreur", msg)

    def _handle_cancel_versement(self, v_id):
        if QMessageBox.question(self, "Annuler", "Voulez-vous vraiment annuler tout le dossier ?", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            success, msg = self.manager.versements.change_versement_status(v_id, 'ANNULE')
            if success: self.load_data()
            else: QMessageBox.warning(self, "Erreur", msg)

    def _handle_change_versement_status(self, v_id, target_status):
        labels = {
            'EN_COURS': 'remettre ce dossier En Cours',
            'CLOTURE': 'cloturer ce dossier',
            'ANNULE': 'annuler ce dossier',
        }
        message = f"Confirmer: {labels.get(target_status, 'changer le statut de ce dossier')} ?"
        if QMessageBox.question(self, "Changer état", message, QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            journee = self.manager.cash_box.get_or_create_today_session(user_id=1)
            journee_id = journee['id'] if journee else 1
            success, msg = self.manager.versements.change_versement_status(v_id, target_status, journee_id)
            if success: self.load_data()
            else: QMessageBox.warning(self, "Erreur", msg)

    def _handle_delete_payment(self, data):
        if QMessageBox.question(self, "Supprimer", "Voulez-vous vraiment annuler et supprimer ce paiement ?", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            if self.manager.versements.delete_payment(data.get("payment_id")): self.load_data()
            else: QMessageBox.critical(self, "Erreur", "Impossible de supprimer ce paiement.")

    def _handle_edit_payment(self, data):
        dlg = EditPaymentDialog(self.manager, data, self)
        if dlg.exec() == QDialog.Accepted: self.load_data()

    def _add_action_btn(self, icon_name, text, bg_color, hover_color, callback, enabled=True):
        btn = QPushButton(f" {text}")
        btn.setIcon(qta.icon(icon_name, color="white"))
        btn.setIconSize(QSize(16, 16))
        btn.setToolTip(text)
        btn.setCursor(Qt.PointingHandCursor if enabled else Qt.ArrowCursor)
        btn.setEnabled(enabled)
        btn.setStyleSheet(f"""
            QPushButton {{ background-color: {bg_color}; color: white; font-weight: bold; font-size: 12px; padding: 5px 10px; border-radius: 4px; border: none; }}
            QPushButton:hover {{ background-color: {hover_color}; }}
            QPushButton:disabled {{ background-color: #bdc3c7; color: white; }}
        """)
        btn.clicked.connect(callback)
        self.toolbar_actions_layout.addWidget(btn)
        return btn

    def on_table_selection_changed(self):
        while self.toolbar_actions_layout.count():
            child = self.toolbar_actions_layout.takeAt(0)
            if child.widget(): child.widget().deleteLater()

        selected_rows = self.table.selectedItems()
        if not selected_rows: return
        row = selected_rows[0].row()
        item = self.table.item(row, 0)
        if not item: return
        data = item.data(Qt.UserRole)
        if not isinstance(data, dict): return

        row_type = data.get("type")
        v_id = data.get("v_id")
        v_statut = data.get("statut")

        if row_type == "HEADER":
            self._add_action_btn("fa5s.search-plus", "Détails Complets", "#0f8f83", "#0b776d", lambda: self.open_full_details_dialog(v_id))
            self._add_action_btn("fa5s.info-circle", "Spécifications", "#3498db", "#2980b9", lambda: self.show_product_specs(data))
            self._add_action_btn("fa5s.file-pdf", "Bon (PDF)", "#e74c3c", "#c0392b", lambda: self.print_versement_pdf(v_id, open_pdf=True, direct=False))
            pdf_printer = self._get_pdf_printer_name()
            self._add_action_btn("fa5s.print", f"Imprimer ({pdf_printer})" if pdf_printer else "Imprimer direct", "#9b59b6", "#8e44ad", lambda: self.print_versement_pdf(v_id, open_pdf=False, direct=True), enabled=bool(pdf_printer))
            thermal_printer = self._get_thermal_printer_name()
            self._add_action_btn("fa5s.receipt", f"Ticket ({thermal_printer})" if thermal_printer else "Ticket thermique", "#e67e22", "#d35400", lambda: self.print_versement_thermal(v_id), enabled=bool(thermal_printer))
            if v_statut == 'EN_COURS':
                self._add_action_btn("fa5s.cart-plus", "Ajouter Article", "#27ae60", "#2ecc71", lambda: self.open_add_item_dialog(v_id))
                self._add_action_btn("fa5s.money-bill-wave", "Paiement Global", "#f1c40f", "#f39c12", lambda: self.open_add_payment_dialog(v_id))
                self._add_action_btn("fa5s.check-circle", "Clôturer", "#2ecc71", "#27ae60", lambda: self._handle_close_versement(v_id))
                self._add_action_btn("fa5s.times-circle", "Annuler", "#c0392b", "#962d2d", lambda: self._handle_cancel_versement(v_id))
            elif v_statut in ('CLOTURE', 'ANNULE'):
                self._add_action_btn("fa5s.exchange-alt", "Remettre En Cours", "#e67e22", "#d35400", lambda: self._handle_change_versement_status(v_id, 'EN_COURS'))

        elif row_type == "ITEM":
            self._add_action_btn("fa5s.tag", "Modifier Observation", "#0f8f83", "#08766e", lambda: self._handle_edit_item_note(data))
            self._add_action_btn("fa5s.info-circle", "Spécifications", "#3498db", "#2980b9", lambda: self.show_product_specs(data))
            item_status = data.get("item_status")
            if item_status == 'EN_COURS' and v_statut == 'EN_COURS':
                self._add_action_btn("fa5s.hand-holding-usd", "Paiement Article", "#f1c40f", "#f39c12", lambda: self.open_add_payment_dialog(v_id, preselected_item_id=data.get("item_id")))
                self._add_action_btn("fa5s.box-open", "Marquer Livré", "#27ae60", "#2ecc71", lambda: self._handle_retirer_item(data))
                self._add_action_btn("fa5s.store-slash", "Annuler Article", "#e74c3c", "#c0392b", lambda: self._handle_cancel_item(data))
                self._add_action_btn("fa5s.trash-alt", "Supprimer", "#7f8c8d", "#95a5a6", lambda: self._handle_delete_item(data))
            elif item_status == 'RETIRE' or item_status == 'ANNULE':
                self._add_action_btn("fa5s.exchange-alt", "Remettre En Cours", "#e67e22", "#d35400", lambda: self._handle_change_item_status(data))

        elif row_type == "PAYMENT" and v_statut == 'EN_COURS':
            self._add_action_btn("fa5s.edit", "Modifier Paiement", "#3498db", "#2980b9", lambda: self._handle_edit_payment(data))
            self._add_action_btn("fa5s.comment-dots", "Modifier Observation", "#0f8f83", "#08766e", lambda: self._handle_edit_payment_note(data))
            self._add_action_btn("fa5s.trash", "Supprimer", "#e74c3c", "#c0392b", lambda: self._handle_delete_payment(data))

    def show_product_specs(self, data):
        try:
            inventory_ids = []
            if data.get("type") == "ITEM" and data.get("inventory_id"):
                inventory_ids.append(data.get("inventory_id"))
            elif data.get("type") == "HEADER" and data.get("v_id"):
                with self.manager.db.get_db_connection() as conn:
                    cursor = conn.cursor(dictionary=True)
                    cursor.execute("SELECT inventory_id FROM Versement_Items WHERE versement_id = %s AND item_status != 'ANNULE'", (data.get("v_id"),))
                    for row in cursor.fetchall():
                        if row.get('inventory_id'):
                            inventory_ids.append(row['inventory_id'])

            if not inventory_ids:
                QMessageBox.information(self, "Détails Produit", "Aucun article spécifique en base n'est associé à cette sélection.")
                return

            details_text = ""
            with self.manager.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                for inv_id in inventory_ids:
                    if not inv_id: continue
                    cursor.execute("""
                        SELECT i.barcode, i.name, i.weight, i.remaining_weight, i.selling_price, i.status, i.entry_date, i.item_type,
                               c.name as category_name, m.name as metal_name, m.purity_value, s.name as supplier_name, l.name as location_name
                        FROM Inventory i
                        LEFT JOIN Categories c ON i.category_id = c.id
                        LEFT JOIN MetalTypes m ON i.metal_type_id = m.id
                        LEFT JOIN Suppliers s ON i.supplier_id = s.id
                        LEFT JOIN StorageLocations l ON i.location_id = l.id
                        WHERE i.id = %s
                    """, (inv_id,))
                    row = cursor.fetchone()
                    if row:
                        details_text += f"🏷️ Article : {row['name']}\n"
                        details_text += f"▪️ Code-barres : {row['barcode'] or 'N/A'}\n"
                        details_text += f"▪️ Catégorie : {row['category_name'] or 'N/A'}\n"
                        details_text += f"▪️ Métal / Titre : {row['metal_name'] or 'N/A'} ({row['purity_value'] or ''})\n"
                        details_text += f"▪️ Fournisseur : {row['supplier_name'] or 'N/A'}\n"
                        details_text += f"▪️ Poids Initial : {float(row['weight'] or 0):.2f} g\n"
                        details_text += f"▪️ Prix de Vente Estimé : {float(row['selling_price'] or 0):,.2f} DA\n"
                        details_text += f"▪️ Emplacement : {row['location_name'] or 'N/A'}\n"
                        details_text += f"▪️ Date d'entrée : {row['entry_date'] or 'N/A'}\n"
                        details_text += "────────────────────────────\n"
            
            if details_text:
                dlg = QMessageBox(self)
                dlg.setWindowTitle("📋 Spécifications Techniques")
                dlg.setText("Voici les spécifications détaillées :")
                dlg.setInformativeText(details_text.strip())
                dlg.setStyleSheet("QLabel { font-size: 14px; font-weight: bold; color: #2c3e50; }")
                dlg.exec()
            else:
                QMessageBox.information(self, "Détails Produit", "Détails introuvables en base de données.")
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Erreur lors du chargement des détails : {e}")

    # ──────────────────────────────────────────────────────────────
    # طباعة PDF (تحميل أو مباشرة)
    # ──────────────────────────────────────────────────────────────
    def print_versement_pdf(self, versement_id, open_pdf=True, direct=False):
        if not ReceiptGenerator:
            QMessageBox.warning(self, "Erreur", "Le module d'impression (invoice_generator) est introuvable.")
            return

        pdf_data, v_data = self._prepare_versement_data(versement_id)
        if not v_data:
            QMessageBox.warning(self, "Erreur", "Données du versement introuvables.")
            return

        output_dir = os.path.abspath("factures/versements")
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, f"Bon_Versement_{v_data['id']}.pdf")

        try:
            direct_printer = self._get_pdf_printer_name() if direct else ""
            if direct and not direct_printer:
                QMessageBox.warning(self, "Aucune imprimante PDF", "Aucune imprimante PDF configurée dans les paramètres.")
                return

            if not pdf_data['items'] or v_data.get('type_versement') == 'A_VIDE':
                ReceiptGenerator.generate_global_versement_receipt(pdf_data, output_path=output_path, direct_printer_name=direct_printer)
            else:
                ReceiptGenerator.generate_product_versement_receipt(pdf_data, output_path=output_path, direct_printer_name=direct_printer)
            
            if open_pdf:
                QDesktopServices.openUrl(QUrl.fromLocalFile(output_path))
            else:
                QMessageBox.information(self, "Impression PDF envoyée", f"Le Bon a été envoyé à :\n{direct_printer}")

        except ValueError as e:
            QMessageBox.critical(self, "Erreur d'impression PDF", f"Impossible d'imprimer :\n\n{e}")
        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Erreur d'impression", f"Impossible de générer le PDF: {e}")

    # ──────────────────────────────────────────────────────────────
    # طباعة حرارية مباشرة
    # ──────────────────────────────────────────────────────────────
    def print_versement_thermal(self, versement_id):
        thermal_printer = self._get_thermal_printer_name()
        if not thermal_printer:
            QMessageBox.warning(self, "Aucune imprimante thermique", "Aucune imprimante thermique n'est configurée.\n\nVeuillez aller dans Paramètres → Impression Thermique.")
            return

        pdf_data, v_data = self._prepare_versement_data(versement_id)
        if not v_data:
            QMessageBox.warning(self, "Erreur", "Données du versement introuvables.")
            return

        try:
            from ui.tools.print_functions import print_thermal_bon_versement
            print_thermal_bon_versement(pdf_data, calculate_only=False, printer_name=thermal_printer)
            QMessageBox.information(self, "Impression thermique envoyée", f"Le ticket de versement a été envoyé à :\n{thermal_printer}")
        except ValueError as e:
            QMessageBox.critical(self, "Erreur imprimante thermique", f"Impossible d'imprimer sur la thermique :\n\n{e}\n\nVérifiez que l'imprimante est allumée et connectée.")
        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Erreur thermique", f"Erreur lors de l'impression thermique :\n{e}")

    def _on_table_double_clicked(self, index):
        if not index.isValid(): return
        item = self.table.item(index.row(), 0)
        if not item: return
        data = item.data(Qt.UserRole)
        if not isinstance(data, dict): return

        row_type = data.get("type")
        if row_type == "ITEM":
            self._handle_edit_item_note(data)
        elif row_type == "PAYMENT" and data.get("statut") == 'EN_COURS':
            self._handle_edit_payment(data)
        elif data.get("v_id"):
            self.open_full_details_dialog(data.get("v_id"))

    def open_full_details_dialog(self, versement_id):
        dlg = VersementFullDetailsDialog(versement_id, self.manager, self)
        dlg.exec()

    # ──────────────────────────────────────────────────────────────
    # باقي الدوال
    # ──────────────────────────────────────────────────────────────
    def add_group_header_row(self, data_dict, text1, span1, text2=None, span2=None, bg_color="#C00080", text_color="white", text_color2=None):
        row = self.table.rowCount()
        self.table.insertRow(row)
        item1 = QTableWidgetItem(text1)
        item1.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        font1 = QFont()
        font1.setPointSize(12)
        font1.setWeight(QFont.Bold)
        item1.setFont(font1)
        item1.setBackground(QBrush(QColor(bg_color)))
        item1.setForeground(QBrush(QColor(text_color)))
        item1.setData(Qt.UserRole, data_dict)
        self.table.setItem(row, 0, item1)
        self.table.setSpan(row, 0, 1, span1)
        
        if text2 and span2:
            item2 = QTableWidgetItem(text2)
            item2.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            font2 = QFont()
            font2.setPointSize(12)
            font2.setWeight(QFont.Bold)
            item2.setFont(font2)
            item2.setBackground(QBrush(QColor(bg_color)))
            item2.setForeground(QBrush(QColor(text_color2 or text_color)))
            item2.setData(Qt.UserRole, data_dict)
            self.table.setItem(row, span1, item2)
            self.table.setSpan(row, span1, 1, span2)
        self.table.setRowHeight(row, 32)

    def create_and_set_item(self, row, col, text, data_dict, bold=False, align_center=True, color_red=False, bg_color=None, text_color=None):
        item = QTableWidgetItem(text)
        f = QFont()
        f.setPointSize(11)
        f.setWeight(QFont.Bold if bold else QFont.Normal)
        item.setFont(f)
        item.setData(Qt.UserRole, data_dict)
        item.setToolTip(text)
        item.setTextAlignment((Qt.AlignCenter if align_center else Qt.AlignLeft) | Qt.AlignVCenter)
        if color_red: item.setForeground(QBrush(QColor("#c0392b")))
        if bg_color: item.setBackground(QBrush(QColor(bg_color)))
        if text_color: item.setForeground(QBrush(QColor(text_color)))
        self.table.setItem(row, col, item)

    def _calculate_item_weight_balance(self, item, payments, total_active_weight=None, precomputed_balances=None):
        item_id = item.get('item_id') or item.get('id')
        item_weight = float(item.get('display_weight') or item.get('weight') or 0)
        if precomputed_balances and item_id in precomputed_balances:
            bal = precomputed_balances[item_id]
            return {
                "deducted_g": bal.get("deducted_g", 0.0),
                "remaining_g": bal.get("remaining_g", item_weight),
                "has_shared": bal.get("has_shared", False),
            }

        balances = calculate_versement_item_balances([item], payments)
        bal = balances.get(item_id, {})
        return {
            "deducted_g": bal.get("deducted_g", 0.0),
            "remaining_g": bal.get("remaining_g", item_weight),
            "has_shared": bal.get("has_shared", False),
        }

    def load_data(self):
        self.table.setRowCount(0)
        status_map = {"En Cours": "EN_COURS", "Clôturé": "CLOTURE", "Annulé": "ANNULE", "Tous": None}
        selected_status = status_map[self.combo_status.currentText()]
        search_text = self.inp_search.text().lower().strip()
        
        try:
            versements = getattr(self.manager.versements, 'get_versements', lambda **k: [])(status_filter=selected_status)
            search_suggestions = set()
            filtered_versements = []
            
            for v in versements:
                client_name = v.get('client_name', 'Inconnu')
                client_phone = str(v.get('phone') or '')
                statut = v.get('status', '')
                v_id = v['id']
                v_code = f"vrs-{v_id:05d}"
                v_code_short = f"vrs-{v_id}"

                items = v.get('items', [])
                payments = v.get('payments', [])

                if client_name and client_name != 'Inconnu':
                    search_suggestions.add(client_name)
                if client_phone:
                    search_suggestions.add(client_phone)
                search_suggestions.add(f"VRS-{v_id:05d}")

                for item in items:
                    desig = item.get('designation', '')
                    barcode = item.get('barcode', '')
                    c_note = item.get('custom_note') or item.get('notes') or ''
                    if desig: search_suggestions.add(desig)
                    if barcode: search_suggestions.add(barcode)
                    if c_note: search_suggestions.add(c_note)

                if search_text:
                    match_found = False
                    if (search_text in client_name.lower() or 
                        search_text in client_phone or 
                        search_text in v_code or 
                        search_text in v_code_short or 
                        search_text in str(v_id)):
                        match_found = True

                    if not match_found:
                        for item in items:
                            desig = str(item.get('designation') or '').lower()
                            barcode = str(item.get('barcode') or '').lower()
                            c_note = str(item.get('custom_note') or item.get('notes') or '').lower()
                            if search_text in desig or search_text in barcode or search_text in c_note:
                                match_found = True
                                break

                    if not match_found:
                        for p in payments:
                            p_notes = str(p.get('notes') or '').lower()
                            p_desig = str(p.get('item_designation') or '').lower()
                            if search_text in p_notes or search_text in p_desig:
                                match_found = True
                                break

                    if not match_found:
                        continue

                filtered_versements.append(v)

            # Partition filtered_versements into pages (~100 rows per page limit)
            pages = []
            current_page_versements = []
            current_page_rows = 0
            target_rows = getattr(self, 'target_rows_per_page', 100)

            for v in filtered_versements:
                v_rows = self._estimate_versement_rows(v)
                if current_page_versements and (current_page_rows + v_rows > target_rows):
                    pages.append(current_page_versements)
                    current_page_versements = [v]
                    current_page_rows = v_rows
                else:
                    current_page_versements.append(v)
                    current_page_rows += v_rows

            if current_page_versements:
                pages.append(current_page_versements)

            if not pages:
                pages = [[]]

            self.total_pages = len(pages)
            if self.current_page < 1:
                self.current_page = 1
            elif self.current_page > self.total_pages:
                self.current_page = self.total_pages

            versements_to_display = pages[self.current_page - 1]

            for v in versements_to_display:
                client_name = v.get('client_name', 'Inconnu')
                client_phone = str(v.get('phone') or '')
                statut = v.get('status', '')
                v_id = v['id']
                is_annule = (statut == 'ANNULE')

                header_data = {"type": "HEADER", "v_id": v_id, "statut": statut}
                header_title = f" 📦 VRS-{v_id} | Client: {client_name} {f'(Tel: {client_phone})' if client_phone else ''}"
                header_details = f"Poids Total Actif: {v.get('total_weight_g', 0):.2f} g "
                self.add_group_header_row(header_data, header_title, 4, header_details, 5, bg_color="#dbe4ec", text_color="#1f2937", text_color2="#1f2937")

                payments = v.get('payments', [])
                items = v.get('items', [])
                balances = calculate_versement_item_balances(items, payments)
                if items:
                    for item in items:
                        row = self.table.rowCount()
                        self.table.insertRow(row)
                        i_statut = item.get('item_status', 'EN_COURS')
                        item_type = str(item.get('item_type') or 'WEIGHT').upper()
                        reserved_quantity = max(1, int(item.get('reserved_quantity') or 1)) if item_type == 'PIECE' else 1
                        weight = float(item.get('display_weight') or item.get('weight') or 0)
                        balance = balances.get(item['item_id'], {
                            "deducted_g": 0.0, "remaining_g": weight, "has_shared": False
                        })
                        custom_note = normalize_custom_note(item.get('custom_note'))
                        i_data = {
                            "type": "ITEM", "v_id": v_id, "statut": statut, "item_id": item['item_id'],
                            "item_status": i_statut, "inventory_id": item.get('inventory_id'),
                            "designation": item.get('designation', 'Inconnu'),
                            "custom_note": custom_note,
                            "weight": weight,
                            "item_type": item_type,
                            "reserved_quantity": reserved_quantity,
                            "barcode": item.get("barcode", ""),
                            "deducted_g": balance["deducted_g"],
                            "remaining_g": balance["remaining_g"]
                        }
                        designation = f"   💍 Article: {item.get('designation', 'Inconnu')}"
                        if item_type == "PIECE":
                            designation += f" x{reserved_quantity}"
                        weight_str = (
                            f"Quantité: {reserved_quantity} pcs | Poids: {weight:.2f} g"
                            if item_type == "PIECE" else f"Poids: {weight:.2f} g"
                        )
                        remain_g_str = f"Déduit: {balance['deducted_g']:.3f} g | Reste: {balance['remaining_g']:.3f} g"
                        obs_str = f"Reste poids produit: {balance['remaining_g']:.3f} g"
                        if balance.get("has_shared"):
                            obs_str += " (avec part poids globale)"
                        if custom_note:
                            obs_str += f" | Obs: {custom_note}"
                        
                        bg_c = None; fg_c = None
                        if i_statut == 'ANNULE': bg_c = "#fff5f3"; fg_c = "#be3528"
                        elif i_statut == 'RETIRE': bg_c = "#eafaf1"; fg_c = "#27ae60"
                        else: bg_c = "#eef7f5"; fg_c = "#075f58"
                        
                        self.create_and_set_item(row, 0, designation, i_data, bold=True, align_center=False, bg_color=bg_c, text_color=fg_c)
                        for col in range(1, 5): self.create_and_set_item(row, col, "-", i_data, bg_color=bg_c)
                        self.create_and_set_item(row, 5, weight_str, i_data, bold=True, bg_color=bg_c, text_color=fg_c)
                        self.create_and_set_item(row, 6, remain_g_str, i_data, bold=True, color_red=(balance["remaining_g"] > 0), bg_color=bg_c, text_color="#c0392b" if balance["remaining_g"] > 0 else "#27ae60")
                        self.create_and_set_item(row, 7, i_statut, i_data, bold=True, bg_color=bg_c, text_color=fg_c)

                        obs_widget = QWidget()
                        obs_layout = QHBoxLayout(obs_widget)
                        obs_layout.setContentsMargins(4, 2, 4, 2)
                        obs_layout.setSpacing(6)

                        lbl_obs = QLabel(obs_str)
                        lbl_obs.setStyleSheet(f"font-size: 11px; font-weight: bold; color: {fg_c or '#075f58'};")
                        lbl_obs.setWordWrap(True)
                        obs_layout.addWidget(lbl_obs, stretch=1)

                        btn_edit_obs = QPushButton("🏷️ Modifier")
                        btn_edit_obs.setFocusPolicy(Qt.NoFocus)
                        btn_edit_obs.setCursor(Qt.PointingHandCursor)
                        btn_edit_obs.setStyleSheet("""
                            QPushButton {
                                background-color: #0f8f83; color: white; font-weight: bold;
                                font-size: 11px; padding: 3px 8px; border-radius: 4px; border: none;
                            }
                            QPushButton:hover { background-color: #08766e; }
                        """)
                        btn_edit_obs.clicked.connect(lambda _, d=i_data: self._handle_edit_item_note(d))
                        obs_layout.addWidget(btn_edit_obs)

                        self.create_and_set_item(row, 8, "", i_data, align_center=False, bg_color=bg_c, text_color=fg_c)
                        self.table.setCellWidget(row, 8, obs_widget)
                        self.table.setRowHeight(row, 40)

                if is_annule and not payments:
                    row = self.table.rowCount()
                    self.table.insertRow(row)
                    dummy_data = {"type": "INFO"}
                    self.create_and_set_item(row, 0, "Dossier Annulé", dummy_data, bold=True, align_center=False, bg_color="#fff5f3", text_color="#be3528")
                    for col in range(1, 9): self.create_and_set_item(row, col, "-", dummy_data, bg_color="#fff5f3")
                elif not payments and not is_annule:
                    row = self.table.rowCount()
                    self.table.insertRow(row)
                    dummy_data = {"type": "INFO"}
                    date_init = v['created_at'].strftime("%d/%m/%Y") if hasattr(v['created_at'], 'strftime') else str(v['created_at'])
                    self.create_and_set_item(row, 0, f"   ↳ {date_init} - Création à vide", dummy_data, align_center=False, bg_color="#edf2f6", text_color="#526170")
                    for col in range(1, 9): self.create_and_set_item(row, col, "-", dummy_data, bg_color="#edf2f6")
                else:
                    for idx, p in enumerate(payments):
                        row = self.table.rowCount()
                        self.table.insertRow(row)
                        d = p.get('payment_date', v['created_at'])
                        date_str = d.strftime("%d/%m/%Y") if hasattr(d, 'strftime') else str(d)
                        
                        m_da = float(p.get('montant_da') or 0); m_tpe = float(p.get('tpe_da') or 0); m_eu = float(p.get('montant_euro') or 0)
                        taux = float(p.get('taux_change_euro') or 0); o_c = float(p.get('or_casse_g') or 0)
                        deduit = float(p.get('poids_deduit_g') or 0); p_notes = p.get('notes') or ""
                        m_dl = float(p.get('montant_dollar') or 0); taux_dl = float(p.get('taux_change_dollar') or 0)
                        remise = float(p.get('remise_da') or 0)
                        
                        op_label = f"   💵 {date_str} - Versement #{idx+1}"
                        if p.get('item_designation'): op_label += f" [{p['item_designation']}]"
                        
                        p_data = {
                            "type": "PAYMENT", "v_id": v_id, "statut": statut, "payment_id": p.get('id'),
                            "versement_item_id": p.get('versement_item_id'),
                            "montant_da": m_da, "tpe_da": m_tpe, "montant_euro": m_eu, "taux_change_euro": taux,
                            "montant_dollar": m_dl, "taux_change_dollar": taux_dl, "remise_da": remise,
                            "or_casse_g": o_c, "poids_deduit_g": deduit, "notes": p_notes
                        }
                        self.create_and_set_item(row, 0, op_label, p_data, bold=True, align_center=False, bg_color="#fff8e8", text_color="#7a4d08")
                        self.create_and_set_item(row, 1, f"{m_da:,.0f} DA" if m_da != 0 else "-", p_data, color_red=(m_da < 0), bg_color="#fff8e8", text_color="#27ae60" if m_da >= 0 else None)
                        self.create_and_set_item(row, 2, f"{m_tpe:,.0f} DA" if m_tpe != 0 else "-", p_data, color_red=(m_tpe < 0), bg_color="#fff8e8", text_color="#27ae60" if m_tpe >= 0 else None)
                        devise_str = []
                        if m_eu != 0: devise_str.append(f"{m_eu:,.0f} €")
                        if m_dl != 0: devise_str.append(f"{m_dl:,.0f} $")
                        self.create_and_set_item(row, 3, " | ".join(devise_str) if devise_str else "-", p_data, color_red=(m_eu < 0 or m_dl < 0), bg_color="#fff8e8", text_color="#27ae60" if (m_eu >= 0 and m_dl >= 0) else None)
                        
                        taux_str = []
                        if taux != 0: taux_str.append(f"{taux:,.2f} €")
                        if taux_dl != 0: taux_str.append(f"{taux_dl:,.2f} $")
                        self.create_and_set_item(row, 4, " | ".join(taux_str) if taux_str else "-", p_data, color_red=(taux < 0 or taux_dl < 0), bg_color="#fff8e8", text_color="#27ae60" if (taux >= 0 and taux_dl >= 0) else None)
                        
                        self.create_and_set_item(row, 5, f"{o_c:.2f} g" if o_c != 0 else "-", p_data, color_red=(o_c < 0), bg_color="#fff8e8", text_color="#27ae60" if o_c >= 0 else None)
                        
                        deduit_str = f"{deduit:.2f} g" if deduit != 0 else "-"
                        self.create_and_set_item(row, 6, deduit_str, p_data, bold=(deduit!=0), color_red=(deduit>0), bg_color="#fff8e8", text_color="#7a4d08" if deduit <= 0 else None)
                        
                        self.create_and_set_item(row, 7, "Paiement", p_data, bg_color="#fff8e8", text_color="#27ae60")
                        
                        clean_notes = re.sub(r'\[Remise:[^\]]+\]', '', p_notes).strip(" |")
                        obs_str = ""
                        if remise > 0: obs_str += f"[Remise: {remise:,.0f} DA] "
                        if clean_notes: obs_str += clean_notes
                        self.create_and_set_item(row, 8, obs_str if obs_str.strip() else "-", p_data, align_center=False, bg_color="#fff8e8", text_color="#7a4d08")
                        self.table.setRowHeight(row, 28)

                total_paid_da = v.get('total_paid_money_da', 0)
                total_tpe = v.get('total_tpe_da', 0)
                total_dollar = v.get('total_dollar', 0)
                total_remise = v.get('total_remise_da', 0)
                total_deducted = v.get('total_paid_weight_g', 0)
                reste_poids = v.get('reste_poids_g', 0)

                sum_text_1 = f"💰 Payé: {total_paid_da:,.0f} DA"
                if total_tpe != 0: sum_text_1 += f"  |  TPE: {total_tpe:,.0f} DA"
                if total_dollar > 0: sum_text_1 += f"  |  💵 {total_dollar:,.0f} $"
                if total_remise > 0: sum_text_1 += f"  |  🎁 Remise: {total_remise:,.0f} DA"
                sum_text_1 += f"  |  ⚖️ Déduit: - {total_deducted:.2f} g"

                sum_text_2 = f"STATUT: {statut}  |  ⚖️ RESTE: {reste_poids:.3f} g"
                is_complete = (reste_poids <= 0) or (statut == 'CLOTURE')
                bg_summary = "#d1e7dd"  # خلفية خضراء فاتحة مريحة دائماً للسطر الأخير
                payment_summary_color = "#0f5132"
                text_color_reste = "#0f5132" if is_complete else "#c0392b"
                self.add_group_header_row({"type": "SUMMARY"}, sum_text_1, 4, sum_text_2, 5, bg_color=bg_summary, text_color=payment_summary_color, text_color2=text_color_reste)

                # الشريط الفاصل الأخضر بين كل ملف versement وآخر (بنفس لون شريط الجدول)
                row_space = self.table.rowCount()
                self.table.insertRow(row_space)
                self.table.setRowHeight(row_space, 14)
                separator_data = {"type": "SEPARATOR"}
                for col in range(9):
                    empty_item = QTableWidgetItem("")
                    empty_item.setFlags(Qt.NoItemFlags)
                    empty_item.setBackground(QBrush(QColor("#0f8f83")))
                    empty_item.setData(Qt.UserRole, separator_data)
                    self.table.setItem(row_space, col, empty_item)
                self.table.setSpan(row_space, 0, 1, 9)



            total_count = len(filtered_versements)
            if hasattr(self, 'lbl_page_info'):
                self.lbl_page_info.setText(
                    f"Page {self.current_page} / {self.total_pages} ({total_count} dossier{'s' if total_count > 1 else ''})"
                )
            if hasattr(self, 'btn_first_page'):
                self.btn_first_page.setEnabled(self.current_page > 1)
                self.btn_prev_page.setEnabled(self.current_page > 1)
                self.btn_next_page.setEnabled(self.current_page < self.total_pages)
                self.btn_last_page.setEnabled(self.current_page < self.total_pages)

        except Exception as e:
            import traceback
            print(f"Erreur load_data: {e}\n{traceback.format_exc()}")

    # ========================================================
    # فتح النوافذ المنبثقة
    # ========================================================
    def open_new_versement_dialog(self):
        from ui.widgets.versements.new_versement_dialog import NewVersementDialog
        try:
            app = QApplication.instance()
            current_user = app.current_main_window.current_user if hasattr(app, 'current_main_window') else {}
        except: current_user = {}

        dlg = NewVersementDialog(self.manager, current_user, self)
        if dlg.exec() == QDialog.Accepted: self.load_data()
        
    def open_add_payment_dialog(self, versement_id, preselected_item_id=None):
        from ui.widgets.versements.add_payment_dialog import AddPaymentDialog
        journee = self.manager.cash_box.get_or_create_today_session(user_id=1)
        current_journee_id = journee['id'] if journee else 1
            
        dlg = AddPaymentDialog(self.manager, versement_id, current_journee_id, preselected_item_id, self)
        if dlg.exec() == QDialog.Accepted: self.load_data()

    def open_add_item_dialog(self, versement_id):
        dlg = AddItemToVersementDialog(self.manager, versement_id, self)
        if dlg.exec() == QDialog.Accepted:
            self.load_data()


class VersementFullDetailsDialog(QDialog):
    """
    نافذة عرض كافة تفاصيل الملف والدفعات والمنتجات في جداول مستقلة ونظيفة بدون أي تقطيع (...).
    """
    def __init__(self, versement_id, manager, parent=None):
        super().__init__(parent)
        self.versement_id = versement_id
        self.manager = manager
        self.setWindowTitle(f"📋 Détails complets du Versement N° VRS-{versement_id:05d}")
        self.setWindowFlags(Qt.Window | Qt.CustomizeWindowHint | Qt.WindowTitleHint | Qt.WindowMaximizeButtonHint | Qt.WindowCloseButtonHint)
        screen = QApplication.primaryScreen().availableGeometry()
        self.setGeometry(screen)
        self.setWindowState(Qt.WindowMaximized)
        self._init_ui()

    def showEvent(self, event):
        super().showEvent(event)
        self.setWindowState(Qt.WindowMaximized)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        versements = getattr(self.manager.versements, 'get_versements', lambda **k: [])(status_filter=None)
        v = next((item for item in versements if item['id'] == self.versement_id), None)
        
        if not v:
            layout.addWidget(QLabel("Erreur: Données du versement introuvables."))
            return

        client_name = v.get('client_name', 'Inconnu')
        client_phone = str(v.get('phone') or 'Non renseigné')
        statut = v.get('status', 'EN_COURS')
        created_at = str(v.get('created_at', ''))

        info_frame = QFrame()
        info_frame.setStyleSheet("background-color: #f0f9ff; border: 1px solid #7dd3fc; border-radius: 8px; padding: 12px;")
        info_layout = QHBoxLayout(info_frame)
        
        lbl_info = QLabel(
            f"<b>📦 Dossier VRS-{self.versement_id:05d}</b> &nbsp;|&nbsp; "
            f"<b>Client :</b> {client_name} &nbsp;|&nbsp; "
            f"<b>Téléphone :</b> {client_phone} &nbsp;|&nbsp; "
            f"<b>Date :</b> {created_at[:10]} &nbsp;|&nbsp; "
            f"<b>Statut :</b> <span style='color: {'#27ae60' if statut=='CLOTURE' else ('#c0392b' if statut=='ANNULE' else '#0284c7')}'>{statut}</span>"
        )
        lbl_info.setStyleSheet("font-size: 14px; color: #1e293b;")
        info_layout.addWidget(lbl_info)
        layout.addWidget(info_frame)

        # Section 1: Tableau des Articles (Produits)
        lbl_articles = QLabel("💍 Articles et Bijoux dans ce Versement (Double-cliquez pour modifier la note) :")
        lbl_articles.setStyleSheet("font-size: 15px; font-weight: bold; color: #0f8f83; margin-top: 5px;")
        layout.addWidget(lbl_articles)

        table_articles = QTableWidget()
        table_articles.setColumnCount(7)
        table_articles.setHorizontalHeaderLabels([
            "Code-barres", "Désignation Produit", "Poids Initial (g)", "Poids Déduit (g)", "Poids Restant (g)", "Statut", "Observation / Note"
        ])
        table_articles.setStyleSheet("""
            QTableWidget { background-color: white; gridline-color: #cbd5e1; font-size: 13px; }
            QHeaderView::section { background-color: #0f8f83; color: white; font-weight: bold; font-size: 13px; padding: 6px; }
            QTableWidget::item { padding: 6px; }
        """)
        table_articles.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table_articles.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        table_articles.horizontalHeader().setSectionResizeMode(6, QHeaderView.Stretch)

        items = v.get('items', [])
        payments = v.get('payments', [])
        balances = calculate_versement_item_balances(items, payments)

        table_articles.setRowCount(len(items))
        for row_idx, item in enumerate(items):
            item_weight = float(item.get('display_weight') or item.get('weight') or 0)
            item_id = item.get('item_id') or item.get('id')
            
            bal = balances.get(item_id, {})
            deducted_g = bal.get('deducted_g', 0.0)
            remaining_g = bal.get('remaining_g', max(0.0, item_weight - deducted_g))

            barcode = item.get("barcode", "N/A")
            desig = item.get("designation", "Article Inconnu")
            i_statut = item.get("item_status", "EN_COURS")
            custom_note = item.get("custom_note") or item.get("notes") or ""

            it_bc = QTableWidgetItem(str(barcode)); it_bc.setToolTip(str(barcode))
            it_desig = QTableWidgetItem(str(desig)); it_desig.setToolTip(str(desig))
            it_w = QTableWidgetItem(f"{item_weight:.2f} g")
            it_ded = QTableWidgetItem(f"{deducted_g:.3f} g")
            it_rem = QTableWidgetItem(f"{remaining_g:.3f} g")
            it_st = QTableWidgetItem(str(i_statut))

            for it in [it_bc, it_w, it_ded, it_rem, it_st]:
                it.setTextAlignment(Qt.AlignCenter)

            table_articles.setItem(row_idx, 0, it_bc)
            table_articles.setItem(row_idx, 1, it_desig)
            table_articles.setItem(row_idx, 2, it_w)
            table_articles.setItem(row_idx, 3, it_ded)
            table_articles.setItem(row_idx, 4, it_rem)
            table_articles.setItem(row_idx, 5, it_st)

            note_widget = QWidget()
            note_layout = QHBoxLayout(note_widget)
            note_layout.setContentsMargins(4, 2, 4, 2)
            note_layout.setSpacing(6)

            lbl_note_text = QLabel(str(custom_note) if custom_note else "(Aucune note)")
            lbl_note_text.setStyleSheet("font-size: 12px; color: #1e293b;" if custom_note else "font-size: 12px; color: #94a3b8; font-style: italic;")
            lbl_note_text.setWordWrap(True)
            note_layout.addWidget(lbl_note_text, stretch=1)

            btn_edit = QPushButton("🏷️ Modifier")
            btn_edit.setFocusPolicy(Qt.NoFocus)
            btn_edit.setCursor(Qt.PointingHandCursor)
            btn_edit.setStyleSheet("""
                QPushButton {
                    background-color: #0f8f83; color: white; font-weight: bold;
                    font-size: 11px; padding: 3px 8px; border-radius: 4px; border: none;
                }
                QPushButton:hover { background-color: #08766e; }
            """)
            btn_edit.clicked.connect(lambda _, it_d=item, r=row_idx: self._edit_dialog_item_note(table_articles, it_d, r))
            note_layout.addWidget(btn_edit)

            table_articles.setCellWidget(row_idx, 6, note_widget)
            table_articles.setRowHeight(row_idx, 38)

        table_articles.setContextMenuPolicy(Qt.CustomContextMenu)
        table_articles.customContextMenuRequested.connect(lambda pos: self._on_article_context_menu(table_articles, items, pos))
        table_articles.doubleClicked.connect(lambda idx: self._on_article_double_clicked(table_articles, items, idx))

        layout.addWidget(table_articles)

        # Section 2: Tableau des Paiements (Versements)
        lbl_payments = QLabel("💵 Historique des Paiements et Versements (Double-cliquez pour modifier) :")
        lbl_payments.setStyleSheet("font-size: 15px; font-weight: bold; color: #0284c7; margin-top: 5px;")
        layout.addWidget(lbl_payments)

        table_payments = QTableWidget()
        table_payments.setColumnCount(9)
        table_payments.setHorizontalHeaderLabels([
            "Date", "Cash (DA)", "TPE (DA)", "Montant (€/$)", "Taux", "Or Cassé (g)", "Poids Déduit (g)", "Remise (DA)", "Notes / Description"
        ])
        table_payments.setStyleSheet("""
            QTableWidget { background-color: white; gridline-color: #cbd5e1; font-size: 13px; }
            QHeaderView::section { background-color: #0284c7; color: white; font-weight: bold; font-size: 13px; padding: 6px; }
            QTableWidget::item { padding: 6px; }
        """)
        table_payments.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table_payments.horizontalHeader().setSectionResizeMode(8, QHeaderView.Stretch)

        table_payments.setRowCount(len(payments))
        for row_idx, p in enumerate(payments):
            d = p.get('payment_date', '')
            date_str = d.strftime("%d/%m/%Y %H:%M") if hasattr(d, 'strftime') else str(d)
            m_da = float(p.get('montant_da') or 0)
            m_tpe = float(p.get('tpe_da') or 0)
            m_eu = float(p.get('montant_euro') or 0)
            m_dl = float(p.get('montant_dollar') or 0)
            taux = float(p.get('taux_change_euro') or p.get('taux_change_dollar') or 0)
            o_c = float(p.get('or_casse_g') or 0)
            deduit = float(p.get('poids_deduit_g') or 0)
            remise = float(p.get('remise_da') or 0)
            raw_notes = p.get('notes') or ""
            clean_notes = re.sub(r'\[Remise:[^\]]+\]', '', raw_notes).strip(" |")

            devise_str = []
            if m_eu != 0: devise_str.append(f"{m_eu:,.2f} €")
            if m_dl != 0: devise_str.append(f"{m_dl:,.2f} $")

            it_date = QTableWidgetItem(date_str)
            it_da = QTableWidgetItem(f"{m_da:,.0f} DA" if m_da != 0 else "-")
            it_tpe = QTableWidgetItem(f"{m_tpe:,.0f} DA" if m_tpe != 0 else "-")
            it_dev = QTableWidgetItem(" / ".join(devise_str) if devise_str else "-")
            it_taux = QTableWidgetItem(f"{taux:.2f}" if taux > 0 else "-")
            it_oc = QTableWidgetItem(f"{o_c:.2f} g" if o_c != 0 else "-")
            it_ded = QTableWidgetItem(f"{deduit:.3f} g" if deduit != 0 else "-")
            it_rem = QTableWidgetItem(f"{remise:,.0f} DA" if remise != 0 else "-")
            it_notes = QTableWidgetItem(str(clean_notes)); it_notes.setToolTip(str(clean_notes))

            table_payments.setItem(row_idx, 0, it_date)
            table_payments.setItem(row_idx, 1, it_da)
            table_payments.setItem(row_idx, 2, it_tpe)
            table_payments.setItem(row_idx, 3, it_dev)
            table_payments.setItem(row_idx, 4, it_taux)
            table_payments.setItem(row_idx, 5, it_oc)
            table_payments.setItem(row_idx, 6, it_ded)
            table_payments.setItem(row_idx, 7, it_rem)
            table_payments.setItem(row_idx, 8, it_notes)

        table_payments.setContextMenuPolicy(Qt.CustomContextMenu)
        table_payments.customContextMenuRequested.connect(lambda pos: self._on_payment_context_menu(table_payments, payments, pos))
        table_payments.doubleClicked.connect(lambda idx: self._on_payment_double_clicked(table_payments, payments, idx))

        layout.addWidget(table_payments)

        # Action bar
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_close = QPushButton("Fermer")
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setStyleSheet("background-color: #64748b; color: white; font-weight: bold; padding: 8px 24px; border-radius: 6px;")
        btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(btn_close)

        layout.addLayout(btn_layout)

    def _on_article_double_clicked(self, table_articles, items, idx):
        if not idx.isValid(): return
        row = idx.row()
        if 0 <= row < len(items):
            self._edit_dialog_item_note(table_articles, items[row], row)

    def _on_article_context_menu(self, table_articles, items, pos):
        row = table_articles.rowAt(pos.y())
        if row < 0 or row >= len(items): return
        item_data = items[row]
        menu = QMenu(self)
        act_edit = menu.addAction("🏷️ Modifier Observation / Note")
        action = menu.exec_(table_articles.viewport().mapToGlobal(pos))
        if action == act_edit:
            self._edit_dialog_item_note(table_articles, item_data, row)

    def _edit_dialog_item_note(self, table_articles, item_data, row):
        item_id = item_data.get("item_id") or item_data.get("id")
        dlg = VersementItemNoteDialog(self.manager, item_data, self)
        if dlg.exec() == QDialog.Accepted:
            new_note = dlg.get_product_note()
            if self.manager.versements.update_versement_item_notes(item_id, new_note):
                item_data["custom_note"] = new_note
                item_data["notes"] = new_note
                w = table_articles.cellWidget(row, 6)
                if w:
                    lbl = w.findChild(QLabel)
                    if lbl:
                        lbl.setText(new_note if new_note else "(Aucune note)")
                        lbl.setStyleSheet("font-size: 12px; color: #1e293b;" if new_note else "font-size: 12px; color: #94a3b8; font-style: italic;")
                if self.parent() and hasattr(self.parent(), "load_data"):
                    self.parent().load_data()

    def _on_payment_double_clicked(self, table_payments, payments, idx):
        if not idx.isValid(): return
        row = idx.row()
        if 0 <= row < len(payments):
            self._edit_dialog_payment(table_payments, payments[row], row)

    def _on_payment_context_menu(self, table_payments, payments, pos):
        row = table_payments.rowAt(pos.y())
        if row < 0 or row >= len(payments): return
        p_data = payments[row]
        menu = QMenu(self)
        act_edit = menu.addAction("✏️ Modifier ce paiement")
        act_edit_note = menu.addAction("📝 Modifier Observation / Note")
        action = menu.exec_(table_payments.viewport().mapToGlobal(pos))
        if action == act_edit:
            self._edit_dialog_payment(table_payments, p_data, row)
        elif action == act_edit_note:
            self._edit_dialog_payment_note(table_payments, p_data, row)

    def _edit_dialog_payment(self, table_payments, p_data, row):
        p_data_dict = dict(p_data)
        p_data_dict["v_id"] = self.versement_id
        p_data_dict["payment_id"] = p_data.get("id")
        dlg = EditPaymentDialog(self.manager, p_data_dict, self)
        if dlg.exec() == QDialog.Accepted:
            self.accept()
            if self.parent() and hasattr(self.parent(), "load_data"):
                self.parent().load_data()

    def _edit_dialog_payment_note(self, table_payments, p_data, row):
        p_data_dict = dict(p_data)
        p_data_dict["payment_id"] = p_data.get("id")
        dlg = VersementPaymentNoteDialog(self.manager, p_data_dict, self)
        if dlg.exec() == QDialog.Accepted:
            new_note = dlg.get_payment_note()
            if self.manager.versements.update_payment_notes(p_data.get("id"), new_note):
                p_data["notes"] = new_note
                it_note = table_payments.item(row, 8)
                if it_note:
                    it_note.setText(new_note)
                    it_note.setToolTip(new_note)
                if self.parent() and hasattr(self.parent(), "load_data"):
                    self.parent().load_data()
