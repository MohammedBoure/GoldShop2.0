import os
import re
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor
from PySide6.QtWidgets import (
    QApplication,
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
    - Support complet des écrans tactiles POS (clavier virtuel intégré sur chaque champ et barre d'actions).
    - Disposition réactive adaptative pour toutes résolutions d'écran (1024x768, 1280x800, FHD, etc.).
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
        self.vkb = None
        self.last_focused_input = None

        op_num = (
            self.pdf_data.get("operation_number")
            or f"VRS-{self.v_data.get('id', 0):05d}"
        )
        self.setWindowTitle(f"Options d'impression & Notes — Bon de Versement Libre {op_num}")

        # Dimensions réactives selon l'écran disponible
        screen_geom = QApplication.primaryScreen().availableGeometry() if QApplication.primaryScreen() else None
        screen_w = screen_geom.width() if screen_geom else 1024
        screen_h = screen_geom.height() if screen_geom else 768

        target_w = min(880, max(680, int(screen_w * 0.88)))
        target_h = min(620, max(460, int(screen_h * 0.82)))
        self.resize(target_w, target_h)
        self.setMinimumSize(660, 430)

        self._init_ui()

    def showEvent(self, event):
        super().showEvent(event)
        screen = QApplication.primaryScreen().availableGeometry() if QApplication.primaryScreen() else None
        if screen:
            x = max(0, (screen.width() - self.width()) // 2)
            # Pour écrans tactiles POS (hauteur <= 850px), placer la fenêtre vers le haut
            # afin de libérer l'espace inférieur pour le clavier virtuel
            if screen.height() <= 850:
                y = max(10, min(35, (screen.height() - self.height()) // 4))
            else:
                y = max(0, (screen.height() - self.height()) // 2)
            self.move(x, y)

    def show_virtual_keyboard(self, target_widget=None):
        """Ouvre le clavier virtuel tactile adapté au champ actuellement actif ou sélectionné."""
        try:
            from ui.tools.virtual_keyboard import VirtualKeyboardDialog, KeyboardFocusTracker

            if target_widget is None:
                focused = self.focusWidget()
                if focused and isinstance(focused, (QLineEdit, QTextEdit)):
                    target_widget = focused
                elif self.last_focused_input:
                    target_widget = self.last_focused_input
                else:
                    target_widget = self._get_default_target_input()

            if target_widget:
                target_widget.setFocus()
                KeyboardFocusTracker.last_input_widget = target_widget
                self.last_focused_input = target_widget

            if not self.vkb:
                self.vkb = VirtualKeyboardDialog(self)
            self.vkb.set_active_parent(self)
            self.vkb.show()
            self.vkb.raise_()
        except Exception:
            pass

    def close_keyboard(self):
        """Ferme le clavier virtuel s'il est visible."""
        try:
            if hasattr(self, "vkb") and self.vkb:
                if self.vkb.isVisible():
                    self.vkb.close()
        except Exception:
            pass

    def accept(self):
        self.close_keyboard()
        super().accept()

    def reject(self):
        self.close_keyboard()
        super().reject()

    def _get_default_target_input(self):
        """Retourne le champ de saisie par défaut selon l'onglet courant."""
        if hasattr(self, "tabs") and self.tabs:
            current_tab = self.tabs.currentWidget()
            tab_type = current_tab.property("tab_type") if current_tab else None
            if tab_type == "payments" and self.payment_row_widgets:
                return self.payment_row_widgets[0]["txt"]
            elif tab_type == "items" and self.item_row_widgets:
                return self.item_row_widgets[0]["txt"]
            elif tab_type == "general" and hasattr(self, "txt_general_note"):
                return self.txt_general_note
        if self.payment_row_widgets:
            return self.payment_row_widgets[0]["txt"]
        return getattr(self, "txt_general_note", None)

    def _track_input_widget(self, widget):
        """Enregistre le widget actif pour le clavier virtuel."""
        self.last_focused_input = widget
        try:
            from ui.tools.virtual_keyboard import KeyboardFocusTracker
            KeyboardFocusTracker.last_input_widget = widget
        except Exception:
            pass

    def _create_note_edit_cell(self, initial_text, placeholder, on_text_changed=None):
        """Crée un conteneur composé d'un QLineEdit et d'un bouton clavier tactile ⌨️ pour chaque ligne."""
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        lay = QHBoxLayout(container)
        lay.setContentsMargins(0, 2, 0, 2)
        lay.setSpacing(6)

        txt_note = QLineEdit(initial_text)
        txt_note.setPlaceholderText(placeholder)
        txt_note.setStyleSheet("""
            QLineEdit {
                font-size: 13px;
                padding: 6px 10px;
                border: 1px solid #cbd5e1;
                border-radius: 5px;
                background-color: #ffffff;
                color: #0f172a;
            }
            QLineEdit:focus {
                border: 2px solid #0f8f83;
                background-color: #f0fdfa;
            }
        """)

        # Suivi du focus pour le clavier tactile
        orig_focus_in = txt_note.focusInEvent

        def _on_focus_in(event):
            self._track_input_widget(txt_note)
            orig_focus_in(event)

        txt_note.focusInEvent = _on_focus_in

        if on_text_changed:
            txt_note.textChanged.connect(on_text_changed)

        btn_row_kb = QPushButton()
        btn_row_kb.setIcon(qta.icon("fa5s.keyboard", color="white"))
        btn_row_kb.setToolTip("Ouvrir le clavier tactile pour cette note")
        btn_row_kb.setCursor(Qt.PointingHandCursor)
        btn_row_kb.setFixedSize(36, 32)
        btn_row_kb.setStyleSheet("""
            QPushButton {
                background-color: #334155;
                color: white;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #0f8f83;
            }
            QPushButton:pressed {
                background-color: #0b776d;
            }
        """)
        btn_row_kb.clicked.connect(lambda _, w=txt_note: self.show_virtual_keyboard(w))

        lay.addWidget(txt_note, stretch=1)
        lay.addWidget(btn_row_kb)
        return container, txt_note

    def _update_tab_icons(self, active_index):
        """Met à jour les icônes des onglets pour garantir un contraste parfait (blanc pur sur l'onglet actif)."""
        for idx in range(self.tabs.count()):
            is_active = (idx == active_index)
            w = self.tabs.widget(idx)
            tab_type = w.property("tab_type") if w else ""
            icon_color = "#ffffff" if is_active else "#0f8f83"

            if tab_type == "payments":
                self.tabs.setTabIcon(idx, qta.icon("fa5s.money-bill-wave", color=icon_color))
            elif tab_type == "general":
                self.tabs.setTabIcon(idx, qta.icon("fa5s.sticky-note", color=icon_color))
            elif tab_type == "items":
                self.tabs.setTabIcon(idx, qta.icon("fa5s.gem", color=icon_color))

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
                width: 20px;
                height: 20px;
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
                border-radius: 8px;
                background-color: #ffffff;
                top: -1px;
            }}
            QTabBar::tab {{
                background-color: #f1f5f9;
                color: #475569;
                font-size: 13px;
                font-weight: bold;
                padding: 10px 20px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                margin-right: 4px;
                border: 1px solid #cbd5e1;
                border-bottom: none;
            }}
            QTabBar::tab:selected {{
                background-color: #0f8f83;
                color: #ffffff;
                border: 1px solid #0f8f83;
                border-bottom: 2px solid #0f8f83;
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
                color: #0f172a;
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
                padding: 2px 6px;
                color: #0f172a;
            }}
            QTextEdit, QLineEdit, QComboBox {{
                font-size: 13px;
                padding: 6px 10px;
                border: 1px solid #cbd5e1;
                border-radius: 5px;
                background-color: white;
                color: #0f172a;
            }}
            QTextEdit:focus, QLineEdit:focus, QComboBox:focus {{
                border: 2px solid #0f8f83;
                background-color: #f0fdfa;
            }}
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(14, 14, 14, 14)

        # ── 1. Entête du versement (Header Card) ───────────────────
        header_frame = QFrame()
        header_frame.setStyleSheet("""
            QFrame {
                background-color: #f0fdfa;
                border: 1px solid #99dfd3;
                border-radius: 8px;
                padding: 8px 12px;
            }
        """)
        header_layout = QVBoxLayout(header_frame)
        header_layout.setSpacing(5)
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

        lbl_title = QLabel(f"<b>Bon de Versement Libre {op_num}</b> &nbsp;—&nbsp; <span style='color: #475569;'>Client : <b>{client_name}</b></span>")
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
        tab_payments.setProperty("tab_type", "payments")
        lay_payments = QVBoxLayout(tab_payments)
        lay_payments.setSpacing(8)
        lay_payments.setContentsMargins(10, 10, 10, 10)

        lbl_pay_sub = QLabel(
            "Cochez les notes de chaque opération de paiement que vous souhaitez afficher sur le bon et modifiez-les si nécessaire :"
        )
        lbl_pay_sub.setStyleSheet("font-size: 12px; color: #475569;")
        lbl_pay_sub.setWordWrap(True)
        lay_payments.addWidget(lbl_pay_sub)

        # Barre d'actions rapides Tab 1 avec bouton clavier tactile
        quick_pay_lay = QHBoxLayout()
        btn_check_all_pay = QPushButton(" Tout afficher")
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

        btn_uncheck_all_pay = QPushButton(" Tout masquer")
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

        btn_pay_kb = QPushButton(" Clavier Tactile")
        btn_pay_kb.setIcon(qta.icon("fa5s.keyboard", color="#334155"))
        btn_pay_kb.setCursor(Qt.PointingHandCursor)
        btn_pay_kb.setStyleSheet("""
            QPushButton {
                background-color: #f1f5f9;
                color: #334155;
                font-size: 12px;
                font-weight: bold;
                padding: 6px 14px;
                border: 1px solid #cbd5e1;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #e2e8f0;
                border-color: #94a3b8;
            }
        """)
        btn_pay_kb.clicked.connect(lambda: self.show_virtual_keyboard())
        quick_pay_lay.addWidget(btn_pay_kb)

        lay_payments.addLayout(quick_pay_lay)

        # Table des paiements
        versements = self.pdf_data.get("versements", [])
        self.table_payments = QTableWidget()
        self.table_payments.setColumnCount(3)
        self.table_payments.setHorizontalHeaderLabels(["Afficher ?", "Opération & Montant", "Note / Observation de la ligne"])
        self.table_payments.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.table_payments.horizontalHeader().setSectionResizeMode(1, QHeaderView.Interactive)
        self.table_payments.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table_payments.setColumnWidth(0, 75)
        self.table_payments.setColumnWidth(1, 350)
        self.table_payments.verticalHeader().setVisible(False)
        self.table_payments.verticalHeader().setDefaultSectionSize(46)
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
            chk.setFixedSize(24, 24)
            chk.setChecked(bool(clean_p_note))
            chk_lay.addWidget(chk)
            self.table_payments.setCellWidget(row_idx, 0, chk_widget)

            # Col 1: Date, Opération & Montant
            label_text = f"{p_date}   •   {p_op} :  {p_amount:,.2f} DA"
            lbl_pay_info = QLabel(label_text)
            lbl_pay_info.setStyleSheet("font-size: 13px; font-weight: bold; color: #0f172a; padding-left: 8px;")
            self.table_payments.setCellWidget(row_idx, 1, lbl_pay_info)

            # Col 2: Cellule éditable avec champ de texte + raccourci clavier tactile
            def _create_pay_text_changed_handler(target_chk):
                def _handler(text):
                    if text.strip() and not target_chk.isChecked():
                        target_chk.setChecked(True)
                return _handler

            note_container, txt_note = self._create_note_edit_cell(
                clean_p_note,
                "Ajouter une note à ce paiement...",
                on_text_changed=_create_pay_text_changed_handler(chk)
            )
            self.table_payments.setCellWidget(row_idx, 2, note_container)

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

        self.tabs.addTab(tab_payments, qta.icon("fa5s.money-bill-wave", color="#ffffff"), f"Notes des Paiements ({len(versements)})")

        # ──────── TAB 2 : Note Générale du Bon ──────────────────────
        tab_general = QWidget()
        tab_general.setProperty("tab_type", "general")
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

        orig_txt_gen_focus = self.txt_general_note.focusInEvent

        def _on_gen_focus(event):
            self._track_input_widget(self.txt_general_note)
            orig_txt_gen_focus(event)

        self.txt_general_note.focusInEvent = _on_gen_focus

        lay_general.addWidget(self.txt_general_note)

        # Boutons outils note générale
        tools_layout = QHBoxLayout()
        self.btn_vkb = QPushButton(" Clavier Tactile (Touch)")
        self.btn_vkb.setIcon(qta.icon("fa5s.keyboard", color="white"))
        self.btn_vkb.setCursor(Qt.PointingHandCursor)
        self.btn_vkb.setStyleSheet("""
            QPushButton { background-color: #334155; color: white; border: none; padding: 7px 16px; font-size: 12px; font-weight: bold; border-radius: 5px; }
            QPushButton:hover { background-color: #1e293b; }
        """)
        self.btn_vkb.clicked.connect(lambda: self.show_virtual_keyboard(self.txt_general_note))
        tools_layout.addWidget(self.btn_vkb)

        self.btn_clear_general = QPushButton("Effacer")
        self.btn_clear_general.setIcon(qta.icon("fa5s.eraser", color="white"))
        self.btn_clear_general.setCursor(Qt.PointingHandCursor)
        self.btn_clear_general.setStyleSheet("""
            QPushButton { background-color: #94a3b8; color: white; border: none; padding: 7px 16px; font-size: 12px; font-weight: bold; border-radius: 5px; }
            QPushButton:hover { background-color: #64748b; }
        """)
        self.btn_clear_general.clicked.connect(self.txt_general_note.clear)
        tools_layout.addWidget(self.btn_clear_general)
        tools_layout.addStretch()
        lay_general.addLayout(tools_layout)

        self.tabs.addTab(tab_general, qta.icon("fa5s.sticky-note", color="#0f8f83"), "Note Générale du Bon")

        # ──────── TAB 3 : Notes des Articles Réservés ────────────────
        items = self.pdf_data.get("items", [])
        if items:
            tab_items = QWidget()
            tab_items.setProperty("tab_type", "items")
            lay_items = QVBoxLayout(tab_items)
            lay_items.setSpacing(8)
            lay_items.setContentsMargins(10, 10, 10, 10)

            lbl_item_sub = QLabel(
                "Cochez les notes des articles que vous souhaitez faire apparaître sur le bon et modifiez-les si nécessaire :"
            )
            lbl_item_sub.setStyleSheet("font-size: 12px; color: #475569;")
            lbl_item_sub.setWordWrap(True)
            lay_items.addWidget(lbl_item_sub)

            quick_item_lay = QHBoxLayout()
            btn_check_all_items = QPushButton(" Tout afficher")
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

            btn_uncheck_all_items = QPushButton(" Tout masquer")
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

            btn_item_kb = QPushButton(" Clavier Tactile")
            btn_item_kb.setIcon(qta.icon("fa5s.keyboard", color="#334155"))
            btn_item_kb.setCursor(Qt.PointingHandCursor)
            btn_item_kb.setStyleSheet("""
                QPushButton {
                    background-color: #f1f5f9;
                    color: #334155;
                    font-size: 12px;
                    font-weight: bold;
                    padding: 6px 14px;
                    border: 1px solid #cbd5e1;
                    border-radius: 5px;
                }
                QPushButton:hover {
                    background-color: #e2e8f0;
                    border-color: #94a3b8;
                }
            """)
            btn_item_kb.clicked.connect(lambda: self.show_virtual_keyboard())
            quick_item_lay.addWidget(btn_item_kb)

            lay_items.addLayout(quick_item_lay)

            self.table_items = QTableWidget()
            self.table_items.setColumnCount(3)
            self.table_items.setHorizontalHeaderLabels(["Afficher ?", "Article", "Note à imprimer"])
            self.table_items.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
            self.table_items.horizontalHeader().setSectionResizeMode(1, QHeaderView.Interactive)
            self.table_items.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
            self.table_items.setColumnWidth(0, 75)
            self.table_items.setColumnWidth(1, 260)
            self.table_items.verticalHeader().setVisible(False)
            self.table_items.verticalHeader().setDefaultSectionSize(46)
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
                chk.setFixedSize(24, 24)
                chk.setChecked(bool(raw_note))
                chk_lay.addWidget(chk)
                self.table_items.setCellWidget(row_idx, 0, chk_widget)

                lbl_item_name = QLabel(item_name)
                lbl_item_name.setStyleSheet("font-size: 13px; font-weight: bold; color: #0f172a; padding-left: 8px;")
                self.table_items.setCellWidget(row_idx, 1, lbl_item_name)

                def _create_item_text_changed_handler(target_chk):
                    def _handler(text):
                        if text.strip() and not target_chk.isChecked():
                            target_chk.setChecked(True)
                    return _handler

                note_container, txt_note = self._create_note_edit_cell(
                    raw_note,
                    "Ajouter une note à cet article...",
                    on_text_changed=_create_item_text_changed_handler(chk)
                )
                self.table_items.setCellWidget(row_idx, 2, note_container)

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

            self.tabs.addTab(tab_items, qta.icon("fa5s.gem", color="#0f8f83"), f"Notes des Articles ({len(items)})")

        self.tabs.currentChanged.connect(self._update_tab_icons)
        self._update_tab_icons(0)

        main_layout.addWidget(self.tabs)

        # ── 3. Boutons d'Action / Impression (Bottom Bar) ───────────
        main_layout.addSpacing(4)
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        btn_layout.setContentsMargins(0, 2, 0, 0)

        self.btn_pdf_preview = QPushButton("Aperçu PDF")
        self.btn_pdf_preview.setIcon(qta.icon("fa5s.file-pdf", color="white"))
        self.btn_pdf_preview.setCursor(Qt.PointingHandCursor)
        self.btn_pdf_preview.setMinimumHeight(42)
        self.btn_pdf_preview.setStyleSheet("""
            QPushButton { background-color: #dc2626; color: white; border: none; padding: 8px 16px; border-radius: 6px; font-weight: bold; font-size: 13px; }
            QPushButton:hover { background-color: #b91c1c; }
        """)
        self.btn_pdf_preview.clicked.connect(lambda: self._apply_and_close("pdf_preview"))
        btn_layout.addWidget(self.btn_pdf_preview)

        pdf_printer_short = self.pdf_printer_name if len(self.pdf_printer_name) <= 16 else self.pdf_printer_name[:14] + "..."
        pdf_label = f"PDF Direct ({pdf_printer_short})" if self.pdf_printer_name else "PDF Direct"
        self.btn_pdf_direct = QPushButton(pdf_label)
        if self.pdf_printer_name:
            self.btn_pdf_direct.setToolTip(f"Imprimer directement sur : {self.pdf_printer_name}")
        self.btn_pdf_direct.setIcon(qta.icon("fa5s.print", color="white"))
        self.btn_pdf_direct.setCursor(Qt.PointingHandCursor)
        self.btn_pdf_direct.setEnabled(bool(self.has_pdf_printer))
        self.btn_pdf_direct.setMinimumHeight(42)
        if self.has_pdf_printer:
            self.btn_pdf_direct.setStyleSheet("""
                QPushButton { background-color: #7c3aed; color: white; border: none; padding: 8px 16px; border-radius: 6px; font-weight: bold; font-size: 13px; }
                QPushButton:hover { background-color: #6d28d9; }
            """)
        else:
            self.btn_pdf_direct.setStyleSheet("""
                QPushButton { background-color: #e2e8f0; color: #94a3b8; border: none; padding: 8px 16px; border-radius: 6px; font-weight: bold; font-size: 13px; }
            """)
        self.btn_pdf_direct.clicked.connect(lambda: self._apply_and_close("pdf_direct"))
        btn_layout.addWidget(self.btn_pdf_direct)

        thermal_printer_short = self.thermal_printer_name if len(self.thermal_printer_name) <= 16 else self.thermal_printer_name[:14] + "..."
        thermal_label = f"Ticket ({thermal_printer_short})" if self.thermal_printer_name else "Ticket Thermique"
        self.btn_thermal = QPushButton(thermal_label)
        if self.thermal_printer_name:
            self.btn_thermal.setToolTip(f"Imprimer sur ticket thermique : {self.thermal_printer_name}")
        self.btn_thermal.setIcon(qta.icon("fa5s.receipt", color="white"))
        self.btn_thermal.setCursor(Qt.PointingHandCursor)
        self.btn_thermal.setEnabled(bool(self.has_thermal_printer))
        self.btn_thermal.setMinimumHeight(42)
        if self.has_thermal_printer:
            self.btn_thermal.setStyleSheet("""
                QPushButton { background-color: #ea580c; color: white; border: none; padding: 8px 16px; border-radius: 6px; font-weight: bold; font-size: 13px; }
                QPushButton:hover { background-color: #c2410c; }
            """)
        else:
            self.btn_thermal.setStyleSheet("""
                QPushButton { background-color: #e2e8f0; color: #94a3b8; border: none; padding: 8px 16px; border-radius: 6px; font-weight: bold; font-size: 13px; }
            """)
        self.btn_thermal.clicked.connect(lambda: self._apply_and_close("thermal"))
        btn_layout.addWidget(self.btn_thermal)

        btn_layout.addStretch()

        # Bouton clavier virtuel dans la barre principale (comme les autres dialogues)
        self.btn_kb_bottom = QPushButton(" Clavier Tactile")
        self.btn_kb_bottom.setIcon(qta.icon("fa5s.keyboard", color="white"))
        self.btn_kb_bottom.setToolTip("Ouvrir le clavier tactile virtuel")
        self.btn_kb_bottom.setCursor(Qt.PointingHandCursor)
        self.btn_kb_bottom.setMinimumHeight(42)
        self.btn_kb_bottom.setStyleSheet("""
            QPushButton {
                background-color: #334155;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #1e293b;
            }
        """)
        self.btn_kb_bottom.clicked.connect(lambda: self.show_virtual_keyboard())
        btn_layout.addWidget(self.btn_kb_bottom)

        self.btn_cancel = QPushButton("Annuler")
        self.btn_cancel.setIcon(qta.icon("fa5s.times", color="#475569"))
        self.btn_cancel.setCursor(Qt.PointingHandCursor)
        self.btn_cancel.setMinimumHeight(42)
        self.btn_cancel.setStyleSheet("""
            QPushButton { background-color: #ffffff; color: #475569; border: 1px solid #cbd5e1; padding: 8px 18px; border-radius: 6px; font-weight: bold; font-size: 13px; }
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
        """Compatibilité avec les appels antérieurs."""
        self.show_virtual_keyboard(target_widget)

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
