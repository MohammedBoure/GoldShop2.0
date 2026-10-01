import os
import re
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QTextEdit,
    QLineEdit,
    QPushButton,
    QCheckBox,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QGroupBox,
    QFrame,
    QWidget,
    QTabWidget,
    QAbstractItemView,
)
import qtawesome as qta


MAX_CUSTOM_NOTE_LENGTH = 255
EMPTY_NOTE_LABEL = "--- Note ---"


def get_or_create_check_icon_path():
    """Returns absolute path to a crisp white checkmark icon for QCheckBox styling."""
    assets_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "assets"))
    os.makedirs(assets_dir, exist_ok=True)
    icon_path = os.path.join(assets_dir, "check_white.png")
    if not os.path.exists(icon_path):
        try:
            icon = qta.icon("fa5s.check", color="white")
            icon.pixmap(14, 14).save(icon_path)
        except Exception:
            pass
    return icon_path.replace("\\", "/")


def normalize_custom_note(value):
    """Return the persisted snapshot format used by SaleItems.custom_note."""
    if not value or value == EMPTY_NOTE_LABEL:
        return ""
    return str(value or "").strip()[:MAX_CUSTOM_NOTE_LENGTH]


def get_invoice_note_values(manager):
    """Load the POS note catalogue without making the dialog fail if unavailable."""
    try:
        values = manager.invoice_notes.get_all_notes()
    except Exception:
        values = []

    notes = []
    seen = set()
    for value in values or []:
        note = normalize_custom_note(value)
        if note and note not in seen:
            notes.append(note)
            seen.add(note)
    return notes


def create_invoice_note_combo(manager, current_value="", parent=None):
    """Build the Versement equivalent of the POS ``À Vendre`` selector with free manual typing support."""
    combo = QComboBox(parent)
    combo.setEditable(True)
    combo.addItem(EMPTY_NOTE_LABEL, "")

    available_notes = get_invoice_note_values(manager)
    for note in available_notes:
        combo.addItem(note, note)

    current_note = normalize_custom_note(current_value)
    if current_note:
        if current_note not in available_notes:
            combo.addItem(current_note, current_note)
        current_index = combo.findText(current_note)
        if current_index >= 0:
            combo.setCurrentIndex(current_index)
        else:
            combo.setEditText(current_note)
    else:
        combo.setCurrentIndex(0)

    if combo.lineEdit():
        combo.lineEdit().setPlaceholderText("Note, observation ou À Vendre...")

    combo.setMaxVisibleItems(20)
    combo.setStyleSheet("font-size: 14px; padding: 5px;")
    return combo


def selected_custom_note(combo):
    if combo is None:
        return ""
    text = combo.currentText().strip() if hasattr(combo, 'currentText') else ""
    if text.endswith("(valeur actuelle)"):
        text = text.replace("(valeur actuelle)", "").strip()
    if text and text != EMPTY_NOTE_LABEL:
        return normalize_custom_note(text)

    data = combo.currentData()
    if data is not None and str(data).strip() and str(data) != EMPTY_NOTE_LABEL:
        return normalize_custom_note(data)
    return ""


class VersementPrintNoteDialog(QDialog):
    """
    Boîte de dialogue permettant de configurer les notes avant l'impression du Bon de Versement (PDF / Thermique).
    - Contrôle de la visibilité des notes pour CHAQUE opération de paiement (activer/désactiver et modifier).
    - Saisie d'une note générale sur le bon avec modèles prédéfinis.
    - Contrôle de la visibilité des notes sur chaque article réservé.
    - Enregistrement optionnel des modifications en base de données.
    - Choix de la méthode d'impression (Aperçu PDF, PDF Direct, Ticket Thermique).
    """

    def __init__(
        self,
        parent=None,
        manager=None,
        v_data=None,
        pdf_data=None,
        has_pdf_printer=False,
        has_thermal_printer=False,
        pdf_printer_name="",
        thermal_printer_name="",
        default_action="pdf_preview",
    ):
        super().__init__(parent)
        self.manager = manager
        self.v_data = v_data or {}
        self.pdf_data = pdf_data or {}
        self.has_pdf_printer = has_pdf_printer
        self.has_thermal_printer = has_thermal_printer
        self.pdf_printer_name = pdf_printer_name
        self.thermal_printer_name = thermal_printer_name
        self.selected_action = default_action
        self.payment_row_widgets = []
        self.item_row_widgets = []
        self.chk_save_payment_notes = None
        self.chk_save_item_notes = None
        self.chk_save_db = QCheckBox()

        op_num = (
            self.pdf_data.get("operation_number")
            or f"VRS-{self.v_data.get('id', 0):05d}"
        )
        self.setWindowTitle(f"Options d'impression & Notes — Bon de Versement {op_num}")
        self.setMinimumWidth(820)
        self.resize(860, 640)
        self._init_ui()

    def _init_ui(self):
        check_icon_path = get_or_create_check_icon_path()
        self.setStyleSheet(f"""
            QDialog {{
                background-color: #f8fafc;
            }}
            QCheckBox {{
                font-size: 13px;
                color: #1e293b;
                background: transparent;
                spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border: 1.5px solid #94a3b8;
                border-radius: 4px;
                background-color: #ffffff;
            }}
            QCheckBox::indicator:hover {{
                border-color: #0f8f83;
                background-color: #f0fdfa;
            }}
            QCheckBox::indicator:checked {{
                background-color: #0f8f83;
                border: 1.5px solid #0f8f83;
                image: url("{check_icon_path}");
            }}
            QCheckBox::indicator:checked:hover {{
                background-color: #0b776d;
                border-color: #0b776d;
            }}
            QTabWidget::pane {{
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                background-color: #ffffff;
                top: -1px;
            }}
            QTabBar::tab {{
                background-color: #f1f5f9;
                color: #475569;
                font-size: 13px;
                font-weight: bold;
                padding: 10px 22px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 4px;
                border: 1px solid #cbd5e1;
                border-bottom: none;
            }}
            QTabBar::tab:selected {{
                background-color: #0f8f83;
                color: #ffffff;
                border-color: #0f8f83;
            }}
            QTabBar::tab:hover:!selected {{
                background-color: #e6f6f4;
                color: #075f58;
            }}
            QTableWidget {{
                background-color: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 6px;
                gridline-color: #f1f5f9;
            }}
            QHeaderView::section {{
                background-color: #f8fafc;
                font-weight: bold;
                font-size: 12px;
                color: #1e293b;
                padding: 8px 10px;
                border: none;
                border-bottom: 2px solid #0f8f83;
            }}
            QTableWidget::item {{
                padding: 4px 8px;
            }}
            QTextEdit, QLineEdit, QComboBox {{
                font-size: 13px;
                padding: 6px 10px;
                border: 1px solid #cbd5e1;
                border-radius: 5px;
                background-color: white;
                color: #1e293b;
            }}
            QTextEdit:focus, QLineEdit:focus, QComboBox:focus {{
                border: 2px solid #0f8f83;
                background-color: #f0fdfa;
            }}
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(18, 18, 18, 18)

        # ── 1. Entête du versement (Header Card) ───────────────────
        header_frame = QFrame()
        header_frame.setStyleSheet("""
            QFrame {
                background-color: #f0fdfa;
                border: 1px solid #99dfd3;
                border-radius: 8px;
                padding: 10px 14px;
            }
        """)
        header_layout = QVBoxLayout(header_frame)
        header_layout.setSpacing(6)
        header_layout.setContentsMargins(6, 6, 6, 6)

        client_name = self.pdf_data.get("customer_name") or self.v_data.get("client_name", "Client Inconnu")
        op_num = self.pdf_data.get("operation_number") or f"VRS-{self.v_data.get('id', 0):05d}"
        phone = self.pdf_data.get("phone") or self.v_data.get("phone", "")
        total_paid = float(self.pdf_data.get("total_paid", 0.0) or 0.0)
        items_count = len(self.pdf_data.get("items", []))
        payments_count = len(self.pdf_data.get("versements", []))

        title_layout = QHBoxLayout()
        title_icon = QLabel()
        title_icon.setPixmap(qta.icon("fa5s.file-invoice-dollar", color="#0f8f83").pixmap(20, 20))
        title_layout.addWidget(title_icon)

        lbl_title = QLabel(f"<b>Bon de Versement {op_num}</b> &nbsp;—&nbsp; <span style='color: #475569;'>Client : <b>{client_name}</b></span>")
        lbl_title.setStyleSheet("font-size: 15px; color: #075f58; background: transparent; border: none;")
        title_layout.addWidget(lbl_title, stretch=1)
        header_layout.addLayout(title_layout)

        info_parts = []
        if phone:
            info_parts.append(f"<span style='color:#64748b;'>Tél :</span> <b>{phone}</b>")
        info_parts.append(f"<span style='color:#64748b;'>Total Versé :</span> <b style='color:#0f8f83;'>{total_paid:,.2f} DA</b>")
        info_parts.append(f"<span style='color:#64748b;'>Paiements :</span> <b style='color:#2563eb;'>{payments_count}</b>")
        if items_count > 0:
            info_parts.append(f"<span style='color:#64748b;'>Articles :</span> <b style='color:#7c3aed;'>{items_count}</b>")
        else:
            info_parts.append("<span style='color:#d97706; font-weight:bold;'>Versement libre</span>")

        lbl_info = QLabel(" &nbsp;&nbsp;•&nbsp;&nbsp; ".join(info_parts))
        lbl_info.setStyleSheet("font-size: 12px; color: #334155; background: transparent; border: none;")
        header_layout.addWidget(lbl_info)

        main_layout.addWidget(header_frame)

        # ── 2. Onglets de personnalisation (Tabs) ───────────────────
        self.tabs = QTabWidget()

        # ──────── TAB 1 : Notes de chaque ligne de paiement ─────────
        tab_payments = QWidget()
        lay_payments = QVBoxLayout(tab_payments)
        lay_payments.setSpacing(10)
        lay_payments.setContentsMargins(12, 12, 12, 12)

        lbl_pay_sub = QLabel(
            "Cochez les notes de chaque opération de paiement que vous souhaitez afficher sur le bon et modifiez-les si nécessaire :"
        )
        lbl_pay_sub.setStyleSheet("font-size: 12px; color: #475569;")
        lbl_pay_sub.setWordWrap(True)
        lay_payments.addWidget(lbl_pay_sub)

        quick_pay_lay = QHBoxLayout()
        btn_check_all_pay = QPushButton("Tout afficher")
        btn_check_all_pay.setIcon(qta.icon("fa5s.check-double", color="#0f8f83"))
        btn_check_all_pay.setCursor(Qt.PointingHandCursor)
        btn_check_all_pay.setStyleSheet("""
            QPushButton {
                background-color: #e8f7f4;
                color: #075f58;
                font-size: 12px;
                font-weight: bold;
                padding: 6px 14px;
                border: 1px solid #99dfd3;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #d1f2ec;
                border-color: #0f8f83;
            }
        """)
        btn_check_all_pay.clicked.connect(self._check_all_payments)
        quick_pay_lay.addWidget(btn_check_all_pay)

        btn_uncheck_all_pay = QPushButton("Tout masquer")
        btn_uncheck_all_pay.setIcon(qta.icon("fa5s.times", color="#64748b"))
        btn_uncheck_all_pay.setCursor(Qt.PointingHandCursor)
        btn_uncheck_all_pay.setStyleSheet("""
            QPushButton {
                background-color: #f8fafc;
                color: #475569;
                font-size: 12px;
                font-weight: bold;
                padding: 6px 14px;
                border: 1px solid #cbd5e1;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #f1f5f9;
                border-color: #94a3b8;
            }
        """)
        btn_uncheck_all_pay.clicked.connect(self._uncheck_all_payments)
        quick_pay_lay.addWidget(btn_uncheck_all_pay)
        quick_pay_lay.addStretch()
        lay_payments.addLayout(quick_pay_lay)

        # Table des paiements
        versements = self.pdf_data.get("versements", [])
        self.table_payments = QTableWidget()
        self.table_payments.setColumnCount(3)
        self.table_payments.setHorizontalHeaderLabels(["Afficher ?", "Opération & Montant", "Note / Observation de la ligne"])
        self.table_payments.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.table_payments.horizontalHeader().setSectionResizeMode(1, QHeaderView.Interactive)
        self.table_payments.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table_payments.setColumnWidth(0, 90)
        self.table_payments.setColumnWidth(1, 380)
        self.table_payments.verticalHeader().setVisible(False)
        self.table_payments.verticalHeader().setDefaultSectionSize(44)
        self.table_payments.setRowCount(len(versements))
        self.table_payments.setSelectionMode(QAbstractItemView.NoSelection)

        for row_idx, p in enumerate(versements):
            p_id = p.get("payment_id") or p.get("id")
            p_date = str(p.get("payment_date") or "")[:10]
            p_amount = float(p.get("amount") or 0.0)
            p_op = str(p.get("product_name") or p.get("item_name") or "Versement").strip()
            raw_p_note = str(p.get("note") or p.get("notes") or p.get("payment_note") or "").strip()
            clean_p_note = re.sub(r'\[Remise:[^\]]+\]', '', raw_p_note).strip(" |")

            # Col 0: Checkbox
            chk_widget = QWidget()
            chk_lay = QHBoxLayout(chk_widget)
            chk_lay.setContentsMargins(0, 0, 0, 0)
            chk_lay.setAlignment(Qt.AlignCenter)
            chk = QCheckBox()
            chk.setCursor(Qt.PointingHandCursor)
            chk.setFixedSize(22, 22)
            chk.setChecked(bool(clean_p_note))
            chk_lay.addWidget(chk)
            self.table_payments.setCellWidget(row_idx, 0, chk_widget)

            # Col 1: Date, Opération & Montant
            label_text = f"{p_date}   •   {p_op} :  {p_amount:,.2f} DA"
            it_desc = QTableWidgetItem(label_text)
            it_desc.setFlags(Qt.ItemIsEnabled)
            it_desc.setFont(QFont("Arial", 10, QFont.Bold))
            self.table_payments.setItem(row_idx, 1, it_desc)

            # Col 2: Editable Note LineEdit
            txt_note = QLineEdit(clean_p_note)
            txt_note.setPlaceholderText("Ajouter une note à ce paiement...")
            txt_note.setStyleSheet("""
                QLineEdit {
                    font-size: 13px;
                    padding: 6px 10px;
                    border: 1px solid #cbd5e1;
                    border-radius: 5px;
                    background-color: #ffffff;
                    color: #1e293b;
                }
                QLineEdit:focus {
                    border: 2px solid #0f8f83;
                    background-color: #f0fdfa;
                }
            """)

            def _create_pay_text_changed_handler(target_chk):
                def _handler(text):
                    if text.strip() and not target_chk.isChecked():
                        target_chk.setChecked(True)
                return _handler

            txt_note.textChanged.connect(_create_pay_text_changed_handler(chk))
            self.table_payments.setCellWidget(row_idx, 2, txt_note)

            self.payment_row_widgets.append({
                "payment_id": p_id,
                "chk": chk,
                "txt": txt_note,
                "orig_note": clean_p_note,
            })

        lay_payments.addWidget(self.table_payments)

        self.chk_save_payment_notes = QCheckBox("Enregistrer également ces modifications de notes de paiement en base de données")
        self.chk_save_payment_notes.setCursor(Qt.PointingHandCursor)
        self.chk_save_payment_notes.setStyleSheet("font-size: 12px; color: #1e293b; font-weight: bold; spacing: 8px;")
        self.chk_save_payment_notes.setChecked(False)
        lay_payments.addWidget(self.chk_save_payment_notes)

        self.tabs.addTab(tab_payments, qta.icon("fa5s.money-bill-wave", color="#475569", color_selected="#ffffff"), f"Notes des Paiements ({len(versements)})")

        # ──────── TAB 2 : Note Générale du Bon ──────────────────────
        tab_general = QWidget()
        lay_general = QVBoxLayout(tab_general)
        lay_general.setSpacing(10)
        lay_general.setContentsMargins(12, 12, 12, 12)

        self.chk_enable_general = QCheckBox("Afficher une note générale sur le bon")
        self.chk_enable_general.setCursor(Qt.PointingHandCursor)
        self.chk_enable_general.setStyleSheet("font-size: 13px; font-weight: bold; color: #0f8f83; spacing: 8px;")
        self.chk_enable_general.setChecked(False)
        lay_general.addWidget(self.chk_enable_general)

        preset_layout = QHBoxLayout()
        lbl_preset = QLabel("Modèle rapide :")
        lbl_preset.setStyleSheet("font-size: 12px; color: #555;")
        preset_layout.addWidget(lbl_preset)

        self.combo_predefined = QComboBox()
        self.combo_predefined.addItem("--- Choisir une note prédéfinie ---", "")
        for note in get_invoice_note_values(self.manager):
            self.combo_predefined.addItem(note, note)
        self.combo_predefined.currentIndexChanged.connect(self._on_predefined_selected)
        preset_layout.addWidget(self.combo_predefined, stretch=1)
        lay_general.addLayout(preset_layout)

        self.txt_general_note = QTextEdit()
        self.txt_general_note.setPlaceholderText(
            "Entrez une note ou observation générale à afficher sur le bon... (Ex: Solde à la livraison, Valable 30 jours, etc.)"
        )
        self.txt_general_note.setMinimumHeight(100)
        default_gn = str(
            self.pdf_data.get("general_note")
            or self.pdf_data.get("invoice_note")
            or self.v_data.get("notes")
            or ""
        ).strip()
        if default_gn:
            self.txt_general_note.setPlainText(default_gn)
            self.chk_enable_general.setChecked(True)

        lay_general.addWidget(self.txt_general_note)

        # Boutons outils note générale
        tools_layout = QHBoxLayout()
        self.btn_vkb = QPushButton(" Clavier Tactile (Touch)")
        self.btn_vkb.setIcon(qta.icon("fa5s.keyboard", color="white"))
        self.btn_vkb.setCursor(Qt.PointingHandCursor)
        self.btn_vkb.setStyleSheet("""
            QPushButton { background-color: #2c3e50; color: white; border: none; padding: 6px 14px; font-size: 12px; border-radius: 5px; }
            QPushButton:hover { background-color: #34495e; }
        """)
        self.btn_vkb.clicked.connect(lambda: self._open_virtual_keyboard(self.txt_general_note))
        tools_layout.addWidget(self.btn_vkb)

        self.btn_clear_general = QPushButton("Effacer")
        self.btn_clear_general.setIcon(qta.icon("fa5s.eraser", color="white"))
        self.btn_clear_general.setCursor(Qt.PointingHandCursor)
        self.btn_clear_general.setStyleSheet("""
            QPushButton { background-color: #94a3b8; color: white; border: none; padding: 6px 14px; font-size: 12px; border-radius: 5px; }
            QPushButton:hover { background-color: #64748b; }
        """)
        self.btn_clear_general.clicked.connect(self.txt_general_note.clear)
        tools_layout.addWidget(self.btn_clear_general)
        tools_layout.addStretch()
        lay_general.addLayout(tools_layout)

        self.tabs.addTab(tab_general, qta.icon("fa5s.sticky-note", color="#475569", color_selected="#ffffff"), "Note Générale du Bon")

        # ──────── TAB 3 : Notes des Articles Réservés ────────────────
        items = self.pdf_data.get("items", [])
        if items:
            tab_items = QWidget()
            lay_items = QVBoxLayout(tab_items)
            lay_items.setSpacing(10)
            lay_items.setContentsMargins(12, 12, 12, 12)

            lbl_item_sub = QLabel(
                "Cochez les notes des articles que vous souhaitez faire apparaître sur le bon et modifiez-les si nécessaire :"
            )
            lbl_item_sub.setStyleSheet("font-size: 12px; color: #475569;")
            lbl_item_sub.setWordWrap(True)
            lay_items.addWidget(lbl_item_sub)

            quick_item_lay = QHBoxLayout()
            btn_check_all_items = QPushButton("Tout afficher")
            btn_check_all_items.setIcon(qta.icon("fa5s.check-double", color="#0f8f83"))
            btn_check_all_items.setCursor(Qt.PointingHandCursor)
            btn_check_all_items.setStyleSheet("""
                QPushButton {
                    background-color: #e8f7f4;
                    color: #075f58;
                    font-size: 12px;
                    font-weight: bold;
                    padding: 6px 14px;
                    border: 1px solid #99dfd3;
                    border-radius: 5px;
                }
                QPushButton:hover {
                    background-color: #d1f2ec;
                    border-color: #0f8f83;
                }
            """)
            btn_check_all_items.clicked.connect(self._check_all_items)
            quick_item_lay.addWidget(btn_check_all_items)

            btn_uncheck_all_items = QPushButton("Tout masquer")
            btn_uncheck_all_items.setIcon(qta.icon("fa5s.times", color="#64748b"))
            btn_uncheck_all_items.setCursor(Qt.PointingHandCursor)
            btn_uncheck_all_items.setStyleSheet("""
                QPushButton {
                    background-color: #f8fafc;
                    color: #475569;
                    font-size: 12px;
                    font-weight: bold;
                    padding: 6px 14px;
                    border: 1px solid #cbd5e1;
                    border-radius: 5px;
                }
                QPushButton:hover {
                    background-color: #f1f5f9;
                    border-color: #94a3b8;
                }
            """)
            btn_uncheck_all_items.clicked.connect(self._uncheck_all_items)
            quick_item_lay.addWidget(btn_uncheck_all_items)
            quick_item_lay.addStretch()
            lay_items.addLayout(quick_item_lay)

            self.table_items = QTableWidget()
            self.table_items.setColumnCount(3)
            self.table_items.setHorizontalHeaderLabels(["Afficher ?", "Article", "Note à imprimer"])
            self.table_items.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
            self.table_items.horizontalHeader().setSectionResizeMode(1, QHeaderView.Interactive)
            self.table_items.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
            self.table_items.setColumnWidth(0, 90)
            self.table_items.setColumnWidth(1, 320)
            self.table_items.verticalHeader().setVisible(False)
            self.table_items.verticalHeader().setDefaultSectionSize(44)
            self.table_items.setRowCount(len(items))
            self.table_items.setSelectionMode(QAbstractItemView.NoSelection)

            for row_idx, item in enumerate(items):
                item_id = item.get("item_id") or item.get("id")
                item_name = str(item.get("name") or item.get("item_name") or item.get("description") or "Article").strip()
                raw_note = normalize_custom_note(item.get("custom_note") or item.get("note") or "")

                chk_widget = QWidget()
                chk_lay = QHBoxLayout(chk_widget)
                chk_lay.setContentsMargins(0, 0, 0, 0)
                chk_lay.setAlignment(Qt.AlignCenter)
                chk = QCheckBox()
                chk.setCursor(Qt.PointingHandCursor)
                chk.setFixedSize(22, 22)
                chk.setChecked(bool(raw_note))
                chk_lay.addWidget(chk)
                self.table_items.setCellWidget(row_idx, 0, chk_widget)

                it_name = QTableWidgetItem(item_name)
                it_name.setFlags(Qt.ItemIsEnabled)
                it_name.setFont(QFont("Arial", 10, QFont.Bold))
                self.table_items.setItem(row_idx, 1, it_name)

                txt_note = QLineEdit(raw_note)
                txt_note.setPlaceholderText("Ajouter une note à cet article...")
                txt_note.setStyleSheet("""
                    QLineEdit {
                        font-size: 13px;
                        padding: 6px 10px;
                        border: 1px solid #cbd5e1;
                        border-radius: 5px;
                        background-color: #ffffff;
                        color: #1e293b;
                    }
                    QLineEdit:focus {
                        border: 2px solid #0f8f83;
                        background-color: #f0fdfa;
                    }
                """)

                def _create_item_text_changed_handler(target_chk):
                    def _handler(text):
                        if text.strip() and not target_chk.isChecked():
                            target_chk.setChecked(True)
                    return _handler

                txt_note.textChanged.connect(_create_item_text_changed_handler(chk))
                self.table_items.setCellWidget(row_idx, 2, txt_note)

                self.item_row_widgets.append({
                    "item_id": item_id,
                    "chk": chk,
                    "txt": txt_note,
                    "orig_note": raw_note,
                })

            lay_items.addWidget(self.table_items)

            self.chk_save_item_notes = QCheckBox("Enregistrer également ces modifications de notes des articles en base de données")
            self.chk_save_item_notes.setCursor(Qt.PointingHandCursor)
            self.chk_save_item_notes.setStyleSheet("font-size: 12px; color: #1e293b; font-weight: bold; spacing: 8px;")
            self.chk_save_item_notes.setChecked(False)
            self.chk_save_db = self.chk_save_item_notes
            lay_items.addWidget(self.chk_save_item_notes)

            self.tabs.addTab(tab_items, qta.icon("fa5s.gem", color="#475569", color_selected="#ffffff"), f"Notes des Articles ({len(items)})")

        main_layout.addWidget(self.tabs)

        # ── 3. Boutons d'Action / Impression (Bottom Bar) ───────────
        main_layout.addSpacing(6)
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        self.btn_pdf_preview = QPushButton("Aperçu PDF")
        self.btn_pdf_preview.setIcon(qta.icon("fa5s.file-pdf", color="white"))
        self.btn_pdf_preview.setCursor(Qt.PointingHandCursor)
        self.btn_pdf_preview.setMinimumHeight(40)
        self.btn_pdf_preview.setStyleSheet("""
            QPushButton { background-color: #dc2626; color: white; border: none; padding: 10px 18px; border-radius: 6px; font-weight: bold; font-size: 13px; }
            QPushButton:hover { background-color: #b91c1c; }
        """)
        self.btn_pdf_preview.clicked.connect(lambda: self._apply_and_close("pdf_preview"))
        btn_layout.addWidget(self.btn_pdf_preview)

        pdf_printer_short = self.pdf_printer_name if len(self.pdf_printer_name) <= 18 else self.pdf_printer_name[:16] + "..."
        pdf_label = f"PDF Direct ({pdf_printer_short})" if self.pdf_printer_name else "PDF Direct"
        self.btn_pdf_direct = QPushButton(pdf_label)
        if self.pdf_printer_name:
            self.btn_pdf_direct.setToolTip(f"Imprimer directement sur : {self.pdf_printer_name}")
        self.btn_pdf_direct.setIcon(qta.icon("fa5s.print", color="white"))
        self.btn_pdf_direct.setCursor(Qt.PointingHandCursor)
        self.btn_pdf_direct.setEnabled(bool(self.has_pdf_printer))
        self.btn_pdf_direct.setMinimumHeight(40)
        if self.has_pdf_printer:
            self.btn_pdf_direct.setStyleSheet("""
                QPushButton { background-color: #7c3aed; color: white; border: none; padding: 10px 18px; border-radius: 6px; font-weight: bold; font-size: 13px; }
                QPushButton:hover { background-color: #6d28d9; }
            """)
        else:
            self.btn_pdf_direct.setStyleSheet("""
                QPushButton { background-color: #e2e8f0; color: #94a3b8; border: none; padding: 10px 18px; border-radius: 6px; font-weight: bold; font-size: 13px; }
            """)
        self.btn_pdf_direct.clicked.connect(lambda: self._apply_and_close("pdf_direct"))
        btn_layout.addWidget(self.btn_pdf_direct)

        thermal_printer_short = self.thermal_printer_name if len(self.thermal_printer_name) <= 18 else self.thermal_printer_name[:16] + "..."
        thermal_label = f"Ticket ({thermal_printer_short})" if self.thermal_printer_name else "Ticket Thermique"
        self.btn_thermal = QPushButton(thermal_label)
        if self.thermal_printer_name:
            self.btn_thermal.setToolTip(f"Imprimer sur ticket thermique : {self.thermal_printer_name}")
        self.btn_thermal.setIcon(qta.icon("fa5s.receipt", color="white"))
        self.btn_thermal.setCursor(Qt.PointingHandCursor)
        self.btn_thermal.setEnabled(bool(self.has_thermal_printer))
        self.btn_thermal.setMinimumHeight(40)
        if self.has_thermal_printer:
            self.btn_thermal.setStyleSheet("""
                QPushButton { background-color: #ea580c; color: white; border: none; padding: 10px 18px; border-radius: 6px; font-weight: bold; font-size: 13px; }
                QPushButton:hover { background-color: #c2410c; }
            """)
        else:
            self.btn_thermal.setStyleSheet("""
                QPushButton { background-color: #e2e8f0; color: #94a3b8; border: none; padding: 10px 18px; border-radius: 6px; font-weight: bold; font-size: 13px; }
            """)
        self.btn_thermal.clicked.connect(lambda: self._apply_and_close("thermal"))
        btn_layout.addWidget(self.btn_thermal)

        btn_layout.addStretch()

        self.btn_cancel = QPushButton("Annuler")
        self.btn_cancel.setIcon(qta.icon("fa5s.times", color="#475569"))
        self.btn_cancel.setCursor(Qt.PointingHandCursor)
        self.btn_cancel.setMinimumHeight(40)
        self.btn_cancel.setStyleSheet("""
            QPushButton { background-color: #ffffff; color: #475569; border: 1px solid #cbd5e1; padding: 10px 20px; border-radius: 6px; font-weight: bold; font-size: 13px; }
            QPushButton:hover { background-color: #f1f5f9; color: #1e293b; border-color: #94a3b8; }
        """)
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)

        main_layout.addLayout(btn_layout)

    def _check_all_payments(self):
        for w in self.payment_row_widgets:
            w["chk"].setChecked(True)

    def _uncheck_all_payments(self):
        for w in self.payment_row_widgets:
            w["chk"].setChecked(False)

    def _check_all_items(self):
        for w in self.item_row_widgets:
            w["chk"].setChecked(True)

    def _uncheck_all_items(self):
        for w in self.item_row_widgets:
            w["chk"].setChecked(False)

    def _on_predefined_selected(self, index):
        if index <= 0:
            return
        selected_text = self.combo_predefined.itemData(index) or self.combo_predefined.currentText()
        if selected_text:
            current = self.txt_general_note.toPlainText().strip()
            if current:
                self.txt_general_note.setPlainText(f"{current} | {selected_text}")
            else:
                self.txt_general_note.setPlainText(selected_text)
            self.chk_enable_general.setChecked(True)
            self.combo_predefined.setCurrentIndex(0)

    def _open_virtual_keyboard(self, target_widget=None):
        try:
            from ui.tools.virtual_keyboard import VirtualKeyboardDialog, KeyboardFocusTracker
            w = target_widget or self.txt_general_note
            w.setFocus()
            KeyboardFocusTracker.last_input_widget = w
            kb = VirtualKeyboardDialog._instance
            if not kb:
                kb = VirtualKeyboardDialog(parent=self)
            kb.set_active_parent(self)
            kb.show()
        except Exception:
            pass

    def _apply_and_close(self, action_type):
        self.selected_action = action_type
        self.accept()

    def apply_to_pdf_data(self, pdf_data):
        """Met à jour le dictionnaire pdf_data avec les choix de notes effectués par l'utilisateur."""
        # 1. Notes de chaque ligne de paiement
        if self.payment_row_widgets and "versements" in pdf_data:
            for idx, widgets in enumerate(self.payment_row_widgets):
                if idx < len(pdf_data["versements"]):
                    p_entry = pdf_data["versements"][idx]
                    chk = widgets["chk"]
                    txt_edit = widgets["txt"]
                    if chk.isChecked():
                        new_note = txt_edit.text().strip()
                        p_entry["note"] = new_note
                        p_entry["notes"] = new_note
                        p_entry["payment_note"] = new_note
                        p_entry["display_payment_note"] = True
                    else:
                        p_entry["note"] = ""
                        p_entry["notes"] = ""
                        p_entry["payment_note"] = ""
                        p_entry["display_payment_note"] = False

        # 2. Note générale
        if self.chk_enable_general.isChecked():
            gn_text = self.txt_general_note.toPlainText().strip()
            pdf_data["general_note"] = gn_text
            pdf_data["invoice_note"] = gn_text
        else:
            pdf_data["general_note"] = ""
            pdf_data["invoice_note"] = ""

        # 3. Notes des articles
        if self.item_row_widgets and "items" in pdf_data:
            for idx, widgets in enumerate(self.item_row_widgets):
                if idx < len(pdf_data["items"]):
                    item = pdf_data["items"][idx]
                    chk = widgets["chk"]
                    txt_edit = widgets["txt"]
                    if chk.isChecked():
                        new_note = normalize_custom_note(txt_edit.text().strip())
                        item["custom_note"] = new_note
                        item["note"] = new_note
                    else:
                        item["custom_note"] = ""
                        item["note"] = ""

    def save_to_database_if_requested(self):
        """Si demandé, enregistre les modifications de notes de paiements et d'articles en base de données."""
        if not self.manager or not hasattr(self.manager, "versements"):
            return

        # 1. Sauvegarde des notes de chaque paiement
        if hasattr(self, "chk_save_payment_notes") and self.chk_save_payment_notes and self.chk_save_payment_notes.isChecked():
            for widgets in self.payment_row_widgets:
                p_id = widgets.get("payment_id")
                if not p_id:
                    continue
                chk = widgets["chk"]
                txt_edit = widgets["txt"]
                orig_note = widgets.get("orig_note", "")
                if chk.isChecked():
                    new_note = txt_edit.text().strip()
                    if new_note != orig_note:
                        try:
                            self.manager.versements.update_payment_notes(p_id, notes=new_note)
                        except Exception as e:
                            print(f"Erreur sauvegarde note paiement {p_id}: {e}")

        # 2. Sauvegarde des notes d'articles
        should_save_items = False
        if hasattr(self, "chk_save_item_notes") and self.chk_save_item_notes and self.chk_save_item_notes.isChecked():
            should_save_items = True
        elif hasattr(self, "chk_save_db") and self.chk_save_db and self.chk_save_db.isChecked():
            should_save_items = True

        if should_save_items:
            for widgets in self.item_row_widgets:
                item_id = widgets.get("item_id")
                if not item_id:
                    continue
                chk = widgets["chk"]
                txt_edit = widgets["txt"]
                orig_note = widgets.get("orig_note", "")
                if chk.isChecked():
                    new_note = normalize_custom_note(txt_edit.text().strip())
                    if new_note != orig_note:
                        try:
                            self.manager.versements.update_versement_item_notes(item_id, notes=new_note)
                        except Exception as e:
                            print(f"Erreur sauvegarde note article {item_id}: {e}")
