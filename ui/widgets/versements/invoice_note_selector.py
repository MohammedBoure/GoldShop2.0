"""Shared helpers and dialogs for Versement invoice notes and print customization."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
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
    QAbstractItemView,
)
import qtawesome as qta


MAX_CUSTOM_NOTE_LENGTH = 255
EMPTY_NOTE_LABEL = "--- Note ---"


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
    - Choisir d'afficher ou non une note générale (avec liste de modèles ou saisie libre).
    - Spécifier les notes des articles à faire apparaître ou masquer.
    - Modifier les notes directement avant impression.
    - Possibilité d'enregistrer les modifications en base de données.
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
        self.item_row_widgets = []

        op_num = (
            self.pdf_data.get("operation_number")
            or f"VRS-{self.v_data.get('id', 0):05d}"
        )
        self.setWindowTitle(f"Options d'impression & Notes — Bon de Versement {op_num}")
        self.setMinimumWidth(660)
        self.resize(700, 600)
        self._init_ui()

    def _init_ui(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #f8f9fa;
            }
            QGroupBox {
                font-size: 13px;
                font-weight: bold;
                color: #2c3e50;
                border: 1px solid #dcdde1;
                border-radius: 6px;
                margin-top: 12px;
                padding-top: 15px;
                background-color: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 12px;
                padding: 0 6px;
                background-color: white;
            }
            QLabel {
                font-size: 13px;
                color: #2c3e50;
            }
            QTextEdit, QLineEdit, QComboBox {
                font-size: 13px;
                padding: 6px 8px;
                border: 1px solid #bdc3c7;
                border-radius: 5px;
                background-color: white;
                color: #2c3e50;
            }
            QTextEdit:focus, QLineEdit:focus, QComboBox:focus {
                border: 2px solid #0f8f83;
            }
            QPushButton {
                font-size: 13px;
                font-weight: bold;
                padding: 8px 14px;
                border-radius: 6px;
            }
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # ── 1. Entête du versement ─────────────────────────────────
        header_frame = QFrame()
        header_frame.setStyleSheet("""
            QFrame {
                background-color: #e8f7f4;
                border: 1px solid #a2ded0;
                border-radius: 6px;
                padding: 8px 12px;
            }
        """)
        header_layout = QVBoxLayout(header_frame)
        header_layout.setSpacing(4)
        header_layout.setContentsMargins(6, 6, 6, 6)

        client_name = self.pdf_data.get("customer_name") or self.v_data.get("client_name", "Client Inconnu")
        op_num = self.pdf_data.get("operation_number") or f"VRS-{self.v_data.get('id', 0):05d}"
        phone = self.pdf_data.get("phone") or self.v_data.get("phone", "")
        total_paid = float(self.pdf_data.get("total_paid", 0.0) or 0.0)
        items_count = len(self.pdf_data.get("items", []))

        lbl_title = QLabel(f"📄 Bon de Versement {op_num} — Client : {client_name}")
        lbl_title.setStyleSheet("font-size: 15px; font-weight: bold; color: #075f58; background: transparent; border: none;")
        header_layout.addWidget(lbl_title)

        info_parts = []
        if phone:
            info_parts.append(f"📞 Tél: {phone}")
        if items_count > 0:
            info_parts.append(f"📦 Articles réservés: {items_count}")
        else:
            info_parts.append("💰 Versement libre")
        info_parts.append(f"💵 Total Versé: {total_paid:,.2f} DA")

        lbl_info = QLabel("   |   ".join(info_parts))
        lbl_info.setStyleSheet("font-size: 12px; color: #2c3e50; background: transparent; border: none;")
        header_layout.addWidget(lbl_info)

        main_layout.addWidget(header_frame)

        # ── 2. Section Note Générale ────────────────────────────────
        grp_general = QGroupBox("1. Note Générale du Bon")
        lay_general = QVBoxLayout(grp_general)
        lay_general.setSpacing(8)

        self.chk_enable_general = QCheckBox("Afficher une note générale sur le bon")
        self.chk_enable_general.setStyleSheet("font-size: 13px; font-weight: bold; color: #0f8f83;")
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
        self.txt_general_note.setMaximumHeight(70)
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

        # Boutons outils pour note générale
        tools_layout = QHBoxLayout()
        self.btn_vkb = QPushButton(" Clavier Tactile (Touch)")
        self.btn_vkb.setIcon(qta.icon("fa5s.keyboard", color="white"))
        self.btn_vkb.setCursor(Qt.PointingHandCursor)
        self.btn_vkb.setStyleSheet("""
            QPushButton { background-color: #2c3e50; color: white; border: none; padding: 5px 12px; font-size: 12px; }
            QPushButton:hover { background-color: #34495e; }
        """)
        self.btn_vkb.clicked.connect(lambda: self._open_virtual_keyboard(self.txt_general_note))
        tools_layout.addWidget(self.btn_vkb)

        self.btn_clear_general = QPushButton("Effacer")
        self.btn_clear_general.setCursor(Qt.PointingHandCursor)
        self.btn_clear_general.setStyleSheet("""
            QPushButton { background-color: #95a5a6; color: white; border: none; padding: 5px 12px; font-size: 12px; }
            QPushButton:hover { background-color: #7f8c8d; }
        """)
        self.btn_clear_general.clicked.connect(self.txt_general_note.clear)
        tools_layout.addWidget(self.btn_clear_general)

        tools_layout.addStretch()
        lay_general.addLayout(tools_layout)

        main_layout.addWidget(grp_general)

        # ── 3. Section Notes des Articles Réservés ───────────────────
        items = self.pdf_data.get("items", [])
        if items:
            grp_items = QGroupBox("2. Notes des Articles Réservés")
            lay_items = QVBoxLayout(grp_items)
            lay_items.setSpacing(8)

            lbl_sub = QLabel(
                "Cochez les notes des articles que vous souhaitez faire apparaître sur le bon et modifiez leur texte si nécessaire :"
            )
            lbl_sub.setStyleSheet("font-size: 12px; color: #555;")
            lbl_sub.setWordWrap(True)
            lay_items.addWidget(lbl_sub)

            quick_lay = QHBoxLayout()
            btn_check_all = QPushButton(" Tout afficher (Cocher)")
            btn_check_all.setCursor(Qt.PointingHandCursor)
            btn_check_all.setStyleSheet("""
                QPushButton { background-color: #ecf0f1; color: #2c3e50; font-size: 11px; padding: 4px 10px; border: 1px solid #bdc3c7; }
                QPushButton:hover { background-color: #dcdde1; }
            """)
            btn_check_all.clicked.connect(self._check_all_items)
            quick_lay.addWidget(btn_check_all)

            btn_uncheck_all = QPushButton(" Tout masquer (Décocher)")
            btn_uncheck_all.setCursor(Qt.PointingHandCursor)
            btn_uncheck_all.setStyleSheet("""
                QPushButton { background-color: #ecf0f1; color: #2c3e50; font-size: 11px; padding: 4px 10px; border: 1px solid #bdc3c7; }
                QPushButton:hover { background-color: #dcdde1; }
            """)
            btn_uncheck_all.clicked.connect(self._uncheck_all_items)
            quick_lay.addWidget(btn_uncheck_all)
            quick_lay.addStretch()
            lay_items.addLayout(quick_lay)

            self.table_items = QTableWidget()
            self.table_items.setColumnCount(3)
            self.table_items.setHorizontalHeaderLabels(["Afficher ?", "Article", "Note à imprimer"])
            self.table_items.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
            self.table_items.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
            self.table_items.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
            self.table_items.setColumnWidth(0, 75)
            self.table_items.verticalHeader().setVisible(False)
            self.table_items.setRowCount(len(items))
            self.table_items.setSelectionMode(QAbstractItemView.NoSelection)
            self.table_items.setStyleSheet("""
                QTableWidget { background-color: white; border: 1px solid #dcdde1; border-radius: 4px; }
                QHeaderView::section { background-color: #f1f2f6; font-weight: bold; font-size: 12px; color: #2f3542; padding: 5px; border-bottom: 2px solid #0f8f83; }
            """)

            for row_idx, item in enumerate(items):
                item_id = item.get("item_id") or item.get("id")
                item_name = str(item.get("name") or item.get("item_name") or item.get("description") or "Article").strip()
                raw_note = normalize_custom_note(item.get("custom_note") or item.get("note") or "")

                # Col 0: Checkbox
                chk_widget = QWidget()
                chk_lay = QHBoxLayout(chk_widget)
                chk_lay.setContentsMargins(0, 0, 0, 0)
                chk_lay.setAlignment(Qt.AlignCenter)
                chk = QCheckBox()
                chk.setChecked(bool(raw_note))
                chk_lay.addWidget(chk)
                self.table_items.setCellWidget(row_idx, 0, chk_widget)

                # Col 1: Article name
                it_name = QTableWidgetItem(item_name)
                it_name.setFlags(Qt.ItemIsEnabled)
                it_name.setFont(QFont("Arial", 10, QFont.Bold))
                self.table_items.setItem(row_idx, 1, it_name)

                # Col 2: Editable line edit for note
                txt_note = QLineEdit(raw_note)
                txt_note.setPlaceholderText("Aucune note pour cet article")
                txt_note.setStyleSheet("font-size: 12px; padding: 4px 6px; border: 1px solid #ccc; border-radius: 4px;")

                def _create_text_changed_handler(target_chk):
                    def _handler(text):
                        if text.strip() and not target_chk.isChecked():
                            target_chk.setChecked(True)
                    return _handler

                txt_note.textChanged.connect(_create_text_changed_handler(chk))
                self.table_items.setCellWidget(row_idx, 2, txt_note)

                self.item_row_widgets.append({
                    "item_id": item_id,
                    "chk": chk,
                    "txt": txt_note,
                    "orig_note": raw_note,
                })

            table_h = min(170, max(80, len(items) * 36 + 32))
            self.table_items.setFixedHeight(table_h)
            lay_items.addWidget(self.table_items)

            self.chk_save_db = QCheckBox("💾 Enregistrer également ces modifications de notes en base de données")
            self.chk_save_db.setStyleSheet("font-size: 12px; color: #2c3e50;")
            self.chk_save_db.setChecked(False)
            lay_items.addWidget(self.chk_save_db)

            main_layout.addWidget(grp_items)

        # ── 4. Boutons d'Action / Impression ────────────────────────
        main_layout.addSpacing(6)
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.btn_pdf_preview = QPushButton("📄 Aperçu PDF")
        self.btn_pdf_preview.setIcon(qta.icon("fa5s.file-pdf", color="white"))
        self.btn_pdf_preview.setCursor(Qt.PointingHandCursor)
        self.btn_pdf_preview.setStyleSheet("""
            QPushButton { background-color: #e74c3c; color: white; border: none; padding: 10px 15px; border-radius: 6px; font-weight: bold; }
            QPushButton:hover { background-color: #c0392b; }
        """)
        self.btn_pdf_preview.clicked.connect(lambda: self._apply_and_close("pdf_preview"))
        btn_layout.addWidget(self.btn_pdf_preview)

        pdf_label = f"🖨️ PDF Direct ({self.pdf_printer_name})" if self.pdf_printer_name else "🖨️ PDF Direct"
        self.btn_pdf_direct = QPushButton(pdf_label)
        self.btn_pdf_direct.setIcon(qta.icon("fa5s.print", color="white"))
        self.btn_pdf_direct.setCursor(Qt.PointingHandCursor)
        self.btn_pdf_direct.setEnabled(bool(self.has_pdf_printer))
        if self.has_pdf_printer:
            self.btn_pdf_direct.setStyleSheet("""
                QPushButton { background-color: #9b59b6; color: white; border: none; padding: 10px 15px; border-radius: 6px; font-weight: bold; }
                QPushButton:hover { background-color: #8e44ad; }
            """)
        else:
            self.btn_pdf_direct.setStyleSheet("""
                QPushButton { background-color: #dcdde1; color: #7f8c8d; border: none; padding: 10px 15px; border-radius: 6px; font-weight: bold; }
            """)
        self.btn_pdf_direct.clicked.connect(lambda: self._apply_and_close("pdf_direct"))
        btn_layout.addWidget(self.btn_pdf_direct)

        thermal_label = f"🧾 Ticket Thermique ({self.thermal_printer_name})" if self.thermal_printer_name else "🧾 Ticket Thermique"
        self.btn_thermal = QPushButton(thermal_label)
        self.btn_thermal.setIcon(qta.icon("fa5s.receipt", color="white"))
        self.btn_thermal.setCursor(Qt.PointingHandCursor)
        self.btn_thermal.setEnabled(bool(self.has_thermal_printer))
        if self.has_thermal_printer:
            self.btn_thermal.setStyleSheet("""
                QPushButton { background-color: #e67e22; color: white; border: none; padding: 10px 15px; border-radius: 6px; font-weight: bold; }
                QPushButton:hover { background-color: #d35400; }
            """)
        else:
            self.btn_thermal.setStyleSheet("""
                QPushButton { background-color: #dcdde1; color: #7f8c8d; border: none; padding: 10px 15px; border-radius: 6px; font-weight: bold; }
            """)
        self.btn_thermal.clicked.connect(lambda: self._apply_and_close("thermal"))
        btn_layout.addWidget(self.btn_thermal)

        btn_layout.addStretch()

        self.btn_cancel = QPushButton("Annuler")
        self.btn_cancel.setCursor(Qt.PointingHandCursor)
        self.btn_cancel.setStyleSheet("""
            QPushButton { background-color: #bdc3c7; color: #2c3e50; border: none; padding: 10px 15px; border-radius: 6px; font-weight: bold; }
            QPushButton:hover { background-color: #95a5a6; }
        """)
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)

        main_layout.addLayout(btn_layout)

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

    def _check_all_items(self):
        for w in self.item_row_widgets:
            w["chk"].setChecked(True)

    def _uncheck_all_items(self):
        for w in self.item_row_widgets:
            w["chk"].setChecked(False)

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
        # 1. Note générale
        if self.chk_enable_general.isChecked():
            gn_text = self.txt_general_note.toPlainText().strip()
            pdf_data["general_note"] = gn_text
            pdf_data["invoice_note"] = gn_text
        else:
            pdf_data["general_note"] = ""
            pdf_data["invoice_note"] = ""

        # 2. Notes des articles
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
        """Si demandé, enregistre les modifications de notes des articles en base de données."""
        if not hasattr(self, "chk_save_db") or not self.chk_save_db.isChecked():
            return
        if not self.manager or not hasattr(self.manager, "versements"):
            return

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
