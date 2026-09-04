# ui/widgets/coffre/coffre_management_view.py
"""
Interface Coffre Magasin & Caisse Centrale
Conception moderne alignée sur le thème général GoldShop, Versement et Journal de Caisse (Excel).
"""

import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QLineEdit, QDialog, QMessageBox,
    QLabel, QApplication, QAbstractItemView, QComboBox,
    QDateEdit, QFormLayout, QMenu, QFrame, QStyledItemDelegate
)
from PySide6.QtCore import Qt, QDate, QTimer
from PySide6.QtGui import QColor, QFont, QBrush, QAction, QPalette
import qtawesome as qta

from ui.deferred_loading import defer_initial_load
from ui.tools.virtual_numpad import VirtualNumpad
from ui.tools.virtual_keyboard import VirtualKeyboardDialog


# ============================================================================
# Couleurs & Thème Harmonisé (GoldShop / Versement / Reports)
# ============================================================================
BRAND_TEAL = "#0f8f83"
BRAND_TEAL_DARK = "#0b776d"
BRAND_TEAL_HOVER = "#0a7c72"
BRAND_TEAL_LIGHT = "#e8f7f4"
BRAND_SELECTION_BG = "#dff5f1"
BORDER_LIGHT = "#cbd5df"
TEXT_DARK = "#24313f"
TEXT_MUTED = "#64748b"

GOLD_ACCENT = "#b8860b"
SILVER_ACCENT = "#5c6b77"
CASH_GREEN = "#27ae60"
CASH_RED = "#e74c3c"
BANK_BLUE = "#2980b9"
DEVISE_PURPLE = "#8e44ad"


# ============================================================================
# Délégué d'affichage pour préserver les couleurs programmatiques
# ============================================================================
class ColorOverrideDelegate(QStyledItemDelegate):
    """
    Delegate garantissant le rendu fidèle des couleurs définies par code
    (ligne de totaux, or, argent, montants) sans interférence des styles QSS.
    """
    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        fg = index.data(Qt.ForegroundRole)
        if isinstance(fg, QBrush) and fg.style() != Qt.NoBrush:
            color = fg.color()
            option.palette.setColor(QPalette.Text, color)
            option.palette.setColor(QPalette.WindowText, color)
            option.palette.setColor(QPalette.HighlightedText, color)
            option.palette.setColor(QPalette.ButtonText, color)

    def paint(self, painter, option, index):
        bg = index.data(Qt.BackgroundRole)
        fg = index.data(Qt.ForegroundRole)

        if isinstance(bg, QBrush) and bg.style() != Qt.NoBrush:
            option.backgroundBrush = bg
            painter.fillRect(option.rect, bg)

        if isinstance(fg, QBrush) and fg.style() != Qt.NoBrush:
            color = fg.color()
            option.palette.setColor(QPalette.Text, color)
            option.palette.setColor(QPalette.WindowText, color)
            option.palette.setColor(QPalette.PlaceholderText, color)
            option.palette.setColor(QPalette.HighlightedText, color)
            option.palette.setColor(QPalette.ButtonText, color)

        super().paint(painter, option, index)


# ============================================================================
# Fonctions Utilitaires
# ============================================================================
def extract_year(date_str):
    if not date_str:
        return None
    d = str(date_str).strip()
    if '/' in d:
        parts = d.split('/')
        if len(parts) == 3 and len(parts[2]) == 4:
            try:
                return int(parts[2])
            except ValueError:
                return None
    elif '-' in d:
        try:
            return int(d[:4])
        except ValueError:
            return None
    return None


def extract_month(date_str):
    if not date_str:
        return None
    d = str(date_str).strip()
    if '/' in d:
        parts = d.split('/')
        if len(parts) == 3:
            try:
                return int(parts[1])
            except ValueError:
                return None
    elif '-' in d:
        try:
            return int(d[5:7])
        except (ValueError, IndexError):
            return None
    return None


def safe_float(val):
    try:
        return float(str(val).replace(' ', '').replace(',', '.'))
    except (ValueError, TypeError):
        return 0.0


# ============================================================================
# Carte KPI Statistique Moderne
# ============================================================================
class CoffreStatCard(QFrame):
    """Carte métrique compacte avec icône et badge de valeur."""
    def __init__(self, title, initial_value, icon_name, color, parent=None):
        super().__init__(parent)
        self.color = color
        self.setStyleSheet(f"""
            QFrame {{
                background-color: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                padding: 4px;
            }}
            QFrame:hover {{
                border-color: {color};
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)

        # Icône avec fond translucide
        self.icon_lbl = QLabel()
        self.icon_lbl.setFixedSize(38, 38)
        self.icon_lbl.setAlignment(Qt.AlignCenter)
        self.icon_lbl.setStyleSheet(f"""
            background-color: {color}15;
            border-radius: 19px;
            border: none;
        """)
        self.icon_lbl.setPixmap(qta.icon(icon_name, color=color).pixmap(20, 20))
        layout.addWidget(self.icon_lbl)

        # Textes (Titre + Valeur)
        v_layout = QVBoxLayout()
        v_layout.setContentsMargins(0, 0, 0, 0)
        v_layout.setSpacing(1)

        self.lbl_title = QLabel(title.upper())
        self.lbl_title.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px; font-weight: bold; border: none;")
        v_layout.addWidget(self.lbl_title)

        self.lbl_val = QLabel(initial_value)
        self.lbl_val.setStyleSheet(f"color: {color}; font-size: 15px; font-weight: 800; border: none;")
        v_layout.addWidget(self.lbl_val)

        layout.addLayout(v_layout)
        layout.addStretch()

    def set_value(self, text):
        self.lbl_val.setText(str(text))


# ============================================================================
# Boîte de dialogue : Nouvelle Opération / Modification (OperationDialog)
# ============================================================================
class OperationDialog(QDialog):
    """
    Fenêtre de création et de modification d'opérations dans le Coffre.
    Mise en page épurée reprenant le style de TransferToCoffreDialog et Versement.
    """
    def showEvent(self, event):
        super().showEvent(event)
        screen = QApplication.primaryScreen().availableGeometry()
        x = (screen.width() - self.width()) // 2
        self.move(x, 20)

    def __init__(self, record=None, parent=None):
        super().__init__(parent)
        self.record = record
        self.setWindowTitle("Modifier l'opération — Coffre Magasin" if record else "Nouvelle Opération — Coffre Magasin")
        self.setFixedSize(620, 590)
        self.setStyleSheet("""
            QDialog {
                background-color: #f8fafc;
                border-radius: 8px;
            }
            QLabel {
                font-size: 13px;
                color: #1e293b;
                font-weight: bold;
            }
            QLineEdit, QDateEdit {
                font-size: 14px;
                font-weight: bold;
                padding: 6px 10px;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                background-color: #ffffff;
                color: #0f172a;
            }
            QLineEdit:focus, QDateEdit:focus {
                border: 2px solid #0f8f83;
                background-color: #f8fffd;
            }
        """)
        self.init_ui()

    def _open_keyboard(self, target):
        try:
            from ui.tools.virtual_keyboard import VirtualKeyboardDialog, KeyboardFocusTracker
            target.setFocus()
            KeyboardFocusTracker.last_input_widget = target
            kb = VirtualKeyboardDialog._instance
            if not kb:
                kb = VirtualKeyboardDialog(parent=self)
            kb.set_active_parent(self)
            kb.show()
        except Exception:
            target.setFocus()
            kb = VirtualKeyboardDialog(self.window())
            kb.show()
            kb.raise_()

    def _open_numpad(self, target, allow_decimal=True):
        try:
            target.setFocus()
            numpad = VirtualNumpad(
                title="Saisie Montant",
                mode="direct",
                target_widget=target,
                allow_decimal=allow_decimal,
                allow_leading_zero=True,
                parent=self
            )
            numpad.show()
            numpad.raise_()
        except Exception:
            pass

    def _wrap_kb(self, widget):
        container = QWidget()
        lay = QHBoxLayout(container)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(5)
        lay.addWidget(widget, stretch=1)

        btn = QPushButton()
        btn.setIcon(qta.icon("fa5s.keyboard", color="white"))
        btn.setFixedSize(40, 36)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        btn.clicked.connect(lambda: self._open_keyboard(widget))
        lay.addWidget(btn)
        return container

    def _wrap_num(self, widget, allow_decimal=True):
        container = QWidget()
        lay = QHBoxLayout(container)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(5)
        lay.addWidget(widget, stretch=1)

        btn = QPushButton()
        btn.setIcon(qta.icon("fa5s.calculator", color="white"))
        btn.setFixedSize(40, 36)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet("""
            QPushButton {
                background-color: #8e44ad;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover {
                background-color: #7d3c98;
            }
        """)
        btn.clicked.connect(lambda: self._open_numpad(widget, allow_decimal))
        lay.addWidget(btn)
        return container

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        # En-tête bannière stylisée
        header_frame = QFrame()
        header_frame.setStyleSheet("""
            QFrame {
                background-color: #0f8f83;
                border-radius: 6px;
                padding: 10px;
            }
        """)
        h_layout = QVBoxLayout(header_frame)
        h_layout.setContentsMargins(10, 8, 10, 8)
        h_layout.setSpacing(3)

        title_text = "✏️ Modifier l'Opération" if self.record else "🏦 Nouvelle Opération Coffre Magasin"
        lbl_head = QLabel(title_text)
        lbl_head.setStyleSheet("color: white; font-size: 16px; font-weight: bold; border: none;")
        lbl_head.setAlignment(Qt.AlignCenter)

        lbl_sub = QLabel("Flux de trésorerie, devises et métaux de récupération (O.C)")
        lbl_sub.setStyleSheet("color: #e6fffa; font-size: 12px; border: none;")
        lbl_sub.setAlignment(Qt.AlignCenter)

        h_layout.addWidget(lbl_head)
        h_layout.addWidget(lbl_sub)
        layout.addWidget(header_frame)

        # Formulaire
        form = QFormLayout()
        form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.inp_date = QDateEdit()
        self.inp_date.setCalendarPopup(True)
        self.inp_date.setDisplayFormat("dd/MM/yyyy")
        if self.record and self.record.get('date_operation'):
            d = str(self.record['date_operation'])
            for fmt in ("dd/MM/yyyy", "d/M/yyyy", "yyyy-MM-dd"):
                date_obj = QDate.fromString(d, fmt)
                if date_obj.isValid():
                    self.inp_date.setDate(date_obj)
                    break
            else:
                self.inp_date.setDate(QDate.currentDate())
        else:
            self.inp_date.setDate(QDate.currentDate())
        form.addRow("📅 Date opération :", self.inp_date)

        fields = [
            ("💰 Montant Espèces (DA) :", "montant_da"),
            ("🥇 O.C Or (g) :", "oc_or"),
            ("🥈 O.C Argent (g) :", "oc_argent"),
            ("💳 TPE (DA) :", "tpe"),
            ("📮 CCP (DA) :", "ccp"),
            ("💶 Euro (€) :", "euro"),
            ("💵 Dollar ($) :", "dollar")
        ]
        self.inp_fields = {}
        for label, key in fields:
            inp = QLineEdit()
            inp.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            inp.setPlaceholderText("0")
            if self.record:
                inp.setText(str(self.record.get(key, '0')))
            self.inp_fields[key] = inp
            form.addRow(label, self._wrap_num(inp, allow_decimal=True))

        self.inp_designation = QLineEdit()
        self.inp_designation.setPlaceholderText("Source, motif, destination ou note...")
        if self.record:
            self.inp_designation.setText(str(self.record.get('designation') or ''))
        form.addRow("📝 Désignation :", self._wrap_kb(self.inp_designation))

        layout.addLayout(form)
        layout.addStretch()

        # Barre d'actions inférieure
        btn_lay = QHBoxLayout()
        btn_lay.setSpacing(10)

        btn_cancel = QPushButton(" Annuler")
        btn_cancel.setIcon(qta.icon("fa5s.times", color="#2c3e50"))
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #cbd5df;
                color: #2c3e50;
                font-weight: bold;
                font-size: 14px;
                padding: 9px 18px;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover {
                background-color: #b8c4d1;
            }
        """)
        btn_cancel.clicked.connect(self.reject)
        btn_lay.addWidget(btn_cancel)

        btn_save = QPushButton(" Enregistrer l'opération")
        btn_save.setIcon(qta.icon("fa5s.check", color="white"))
        btn_save.setCursor(Qt.PointingHandCursor)
        btn_save.setStyleSheet("""
            QPushButton {
                background-color: #0f8f83;
                color: white;
                font-weight: bold;
                font-size: 14px;
                padding: 9px 24px;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover {
                background-color: #0a7c72;
            }
            QPushButton:pressed {
                background-color: #075f58;
            }
        """)
        btn_save.clicked.connect(self.accept)
        btn_lay.addWidget(btn_save)

        layout.addLayout(btn_lay)

    def get_data(self):
        return {
            "id": self.record['id'] if self.record else None,
            "date_operation": self.inp_date.date().toString("dd/MM/yyyy"),
            "montant_da": self.inp_fields['montant_da'].text().strip() or "0",
            "oc_or": self.inp_fields['oc_or'].text().strip() or "0",
            "oc_argent": self.inp_fields['oc_argent'].text().strip() or "0",
            "tpe": self.inp_fields['tpe'].text().strip() or "0",
            "ccp": self.inp_fields['ccp'].text().strip() or "0",
            "euro": self.inp_fields['euro'].text().strip() or "0",
            "dollar": self.inp_fields['dollar'].text().strip() or "0",
            "designation": self.inp_designation.text().strip()
        }


# ============================================================================
# Vue Principale : Coffre Magasin (CoffreMagasinView)
# ============================================================================
class CoffreMagasinView(QWidget):
    """
    Interface de gestion et de suivi de la trésorerie centrale (Coffre Magasin).
    Alignée avec les standards de design GoldShop, Versements et Rapports.
    """
    FONT_NORMAL = QFont("", 11, QFont.Normal)
    FONT_BOLD_11 = QFont("", 11, QFont.Bold)
    FONT_BOLD_12 = QFont("", 12, QFont.Bold)

    BRUSH_WHITE = QBrush(QColor("white"))
    BRUSH_TOTAL_BG = QBrush(QColor(BRAND_TEAL))
    BRUSH_GOLD = QBrush(QColor(GOLD_ACCENT))
    BRUSH_SILVER = QBrush(QColor(SILVER_ACCENT))
    BRUSH_GREEN = QBrush(QColor(CASH_GREEN))
    BRUSH_RED = QBrush(QColor(CASH_RED))

    def __init__(self, manager):
        super().__init__()
        self.manager = manager
        self.full_data = []

        # Timer de recherche avec debounce (250ms)
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(250)
        self._search_timer.timeout.connect(self._apply_filter)

        self.init_ui()
        defer_initial_load(self, self._initial_load)

    def _initial_load(self):
        self._build_year_combo()
        self.load_data()

    def showEvent(self, event):
        super().showEvent(event)
        # Recharger les données lors de l'accès à l'onglet
        if hasattr(self, "full_data") and not self.full_data:
            self.load_data()

    def refresh_data(self):
        """Méthode standard reconnue par le chargeur de pages lazy de MainWindow."""
        self.load_data()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        # 1. Bannière Titre Principale (Thème Teal #0f8f83 identique à Versements)
        self.lbl_title = QLabel("SUIVI & ÉTAT DU COFFRE MAGASIN (CAISSE CENTRALE)")
        self.lbl_title.setAlignment(Qt.AlignCenter)
        self.lbl_title.setStyleSheet(f"""
            font-size: 19px;
            font-weight: 900;
            color: white;
            background-color: {BRAND_TEAL};
            padding: 10px 16px;
            border-radius: 6px;
            letter-spacing: 1px;
        """)
        layout.addWidget(self.lbl_title)

        # 2. Section des Cartes KPI (Statistiques en temps réel)
        self.cards_layout = QHBoxLayout()
        self.cards_layout.setSpacing(10)

        self.card_cash = CoffreStatCard("Espèces (DA)", "0.00 DA", "fa5s.money-bill-wave", BRAND_TEAL)
        self.card_gold = CoffreStatCard("O.C Or (g)", "0.00 g", "fa5s.ring", GOLD_ACCENT)
        self.card_silver = CoffreStatCard("O.C Argent (g)", "0.00 g", "fa5s.balance-scale", SILVER_ACCENT)
        self.card_bank = CoffreStatCard("TPE & CCP (DA)", "0.00 DA", "fa5s.credit-card", BANK_BLUE)
        self.card_devises = CoffreStatCard("Devises (€ / $)", "0 € | 0 $", "fa5s.coins", DEVISE_PURPLE)

        self.cards_layout.addWidget(self.card_cash)
        self.cards_layout.addWidget(self.card_gold)
        self.cards_layout.addWidget(self.card_silver)
        self.cards_layout.addWidget(self.card_bank)
        self.cards_layout.addWidget(self.card_devises)
        layout.addLayout(self.cards_layout)

        # 3. Panneau de Contrôle & Filtres (Frame panel harmonisé)
        filter_panel = QFrame()
        filter_panel.setObjectName("panel")
        filter_panel.setStyleSheet(f"""
            QFrame#panel {{
                background-color: #ffffff;
                border: 1px solid #d9e0e7;
                border-radius: 8px;
                padding: 6px 12px;
            }}
            QLabel {{
                font-size: 13px;
                font-weight: bold;
                color: {TEXT_DARK};
            }}
            QComboBox {{
                font-size: 13px;
                font-weight: bold;
                padding: 5px 10px;
                border: 1px solid {BORDER_LIGHT};
                border-radius: 6px;
                background-color: #ffffff;
                min-width: 140px;
            }}
            QComboBox:focus {{
                border: 2px solid {BRAND_TEAL};
            }}
            QLineEdit {{
                font-size: 13px;
                padding: 5px 10px;
                border: 1px solid {BORDER_LIGHT};
                border-radius: 6px;
                background-color: #ffffff;
            }}
            QLineEdit:focus {{
                border: 2px solid {BRAND_TEAL};
                background-color: #f8fffd;
            }}
        """)
        filter_layout = QHBoxLayout(filter_panel)
        filter_layout.setContentsMargins(8, 6, 8, 6)
        filter_layout.setSpacing(10)

        # Filtre Année
        filter_layout.addWidget(QLabel("📅 Année :"))
        self.combo_annee = QComboBox()
        self.combo_annee.addItem("Toutes les années", 0)
        self.combo_annee.currentIndexChanged.connect(self._update_title_and_filter)
        filter_layout.addWidget(self.combo_annee)

        # Filtre Mois
        filter_layout.addWidget(QLabel("Mois :"))
        self.combo_mois = QComboBox()
        self.combo_mois.addItem("Tous les mois", 0)
        mois_noms = [
            "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
            "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"
        ]
        for i in range(1, 13):
            self.combo_mois.addItem(f"{i:02d} - {mois_noms[i-1]}", i)
        self.combo_mois.currentIndexChanged.connect(self._update_title_and_filter)
        filter_layout.addWidget(self.combo_mois)

        # Champ de recherche
        filter_layout.addSpacing(5)
        filter_layout.addWidget(QLabel("🔍 Recherche :"))
        self.inp_search = QLineEdit()
        self.inp_search.setPlaceholderText("Désignation, note, date, montant...")
        self.inp_search.setClearButtonEnabled(True)
        self.inp_search.textChanged.connect(lambda: self._search_timer.start())
        filter_layout.addWidget(self.inp_search, stretch=1)

        # Bouton clavier virtuel pour l'écran tactile
        btn_touch_kb = QPushButton()
        btn_touch_kb.setIcon(qta.icon("fa5s.keyboard", color="#2c3e50"))
        btn_touch_kb.setFixedSize(36, 34)
        btn_touch_kb.setCursor(Qt.PointingHandCursor)
        btn_touch_kb.setToolTip("Clavier tactile (Touch)")
        btn_touch_kb.setStyleSheet(f"""
            QPushButton {{
                background-color: #ffffff;
                border: 1px solid {BORDER_LIGHT};
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background-color: #f1f5f9;
                border-color: {BRAND_TEAL};
            }}
        """)
        btn_touch_kb.clicked.connect(self._open_search_keyboard)
        filter_layout.addWidget(btn_touch_kb)

        # Bouton Actualiser
        self.btn_refresh = QPushButton(" Actualiser")
        self.btn_refresh.setIcon(qta.icon("fa5s.sync-alt", color="#24313f"))
        self.btn_refresh.setCursor(Qt.PointingHandCursor)
        self.btn_refresh.setStyleSheet(f"""
            QPushButton {{
                background-color: #ffffff;
                border: 1px solid {BORDER_LIGHT};
                border-radius: 6px;
                color: #24313f;
                font-weight: bold;
                font-size: 13px;
                padding: 6px 12px;
            }}
            QPushButton:hover {{
                background-color: #f8fafc;
                border-color: {BRAND_TEAL};
            }}
        """)
        self.btn_refresh.clicked.connect(self.load_data)
        filter_layout.addWidget(self.btn_refresh)

        # Bouton Action Principale : + Nouvelle Opération
        self.btn_add = QPushButton(" + Nouvelle Opération")
        self.btn_add.setIcon(qta.icon("fa5s.plus", color="white"))
        self.btn_add.setCursor(Qt.PointingHandCursor)
        self.btn_add.setStyleSheet(f"""
            QPushButton {{
                background-color: {CASH_GREEN};
                color: white;
                font-weight: bold;
                font-size: 13px;
                padding: 6px 16px;
                border-radius: 6px;
                border: none;
            }}
            QPushButton:hover {{
                background-color: #219a52;
            }}
            QPushButton:pressed {{
                background-color: #1e8449;
            }}
        """)
        self.btn_add.clicked.connect(self.open_add_dialog)
        filter_layout.addWidget(self.btn_add)

        layout.addWidget(filter_panel)

        # 4. Table des Opérations (Style moderne aligné sur Journal et Versements)
        self.table = QTableWidget(0, 9)
        self.table.setItemDelegate(ColorOverrideDelegate(self.table))
        self.table.setHorizontalHeaderLabels([
            "Date", "Montant (DA)", "O.C Or (g)", "O.C Ag (g)",
            "TPE", "CCP", "Euro", "Dollar", "Désignation"
        ])
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background-color: #ffffff;
                gridline-color: #eef2f6;
                border: 1px solid {BORDER_LIGHT};
                border-radius: 6px;
                selection-background-color: {BRAND_SELECTION_BG};
                selection-color: #17202a;
            }}
            QHeaderView::section {{
                background-color: {BRAND_TEAL};
                color: white;
                font-weight: bold;
                font-size: 13px;
                padding: 7px 6px;
                border: 1px solid {BRAND_TEAL_DARK};
            }}
            QTableWidget::item {{
                padding: 5px 8px;
            }}
            QTableWidget::item:selected {{
                background-color: {BRAND_SELECTION_BG};
                color: #17202a;
            }}
        """)

        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        self.table.cellDoubleClicked.connect(self._on_table_double_clicked)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(36)

        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(7, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(8, QHeaderView.Stretch)
        layout.addWidget(self.table)

    def _open_search_keyboard(self):
        try:
            from ui.tools.virtual_keyboard import VirtualKeyboardDialog, KeyboardFocusTracker
            self.inp_search.setFocus()
            KeyboardFocusTracker.last_input_widget = self.inp_search
            kb = VirtualKeyboardDialog._instance
            if not kb:
                kb = VirtualKeyboardDialog(parent=self)
            kb.set_active_parent(self)
            kb.show()
        except Exception:
            pass

    def _on_table_double_clicked(self, row, col):
        """Permet l'édition directe d'une opération par double clic."""
        if row < 0 or row >= len(self.full_data):
            return
        item = self.table.item(row, 0)
        if item and item.text() == "TOTAUX :":
            return
        record = item.data(Qt.UserRole) if item else None
        if record:
            self.open_edit_dialog(record)

    def show_context_menu(self, pos):
        row = self.table.rowAt(pos.y())
        if row < 0:
            return

        item = self.table.item(row, 0)
        if not item or item.text() == "TOTAUX :":
            return

        record = item.data(Qt.UserRole)
        if not record:
            # Recherche par index dans full_data si non attaché à l'item
            if row < len(self.full_data):
                record = self.full_data[row]
        if not record:
            return

        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: #ffffff;
                border: 1px solid {BORDER_LIGHT};
                border-radius: 8px;
                padding: 6px 4px;
                font-size: 13px;
                font-weight: 600;
            }}
            QMenu::item {{
                border-radius: 5px;
                color: {TEXT_DARK};
                padding: 7px 28px 7px 24px;
            }}
            QMenu::item:selected {{
                background-color: {BRAND_SELECTION_BG};
                color: {BRAND_TEAL_DARK};
            }}
            QMenu::separator {{
                background-color: #e4ebf2;
                height: 1px;
                margin: 4px 8px;
            }}
        """)

        action_edit = QAction("  Modifier cette opération", self)
        action_edit.setIcon(qta.icon("fa5s.edit", color=BRAND_TEAL))
        action_edit.triggered.connect(lambda: self.open_edit_dialog(record))
        menu.addAction(action_edit)

        menu.addSeparator()

        action_del = QAction("  Supprimer cette opération", self)
        action_del.setIcon(qta.icon("fa5s.trash-alt", color=CASH_RED))
        action_del.triggered.connect(lambda: self.delete_record(record['id']))
        menu.addAction(action_del)

        menu.exec_(self.table.viewport().mapToGlobal(pos))

    def _update_title_and_filter(self):
        annee = self.combo_annee.currentData()
        mois = self.combo_mois.currentData()
        mois_noms = ["", "Janvier", "Février", "Mars", "Avril", "Mai", "Juin", "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"]

        titre = "SUIVI & ÉTAT DU COFFRE MAGASIN"
        if annee and annee != 0:
            titre += f" — {annee}"
            if mois and mois != 0:
                titre += f" ({mois_noms[mois]})"
        self.lbl_title.setText(titre)
        self._apply_filter()

    def _build_year_combo(self):
        self.combo_annee.blockSignals(True)
        current = self.combo_annee.currentData()
        self.combo_annee.clear()
        self.combo_annee.addItem("Toutes les années", 0)
        years = set()
        for r in self.full_data:
            year = extract_year(r.get('date_operation', ''))
            if year:
                years.add(year)
        for y in sorted(years, reverse=True):
            self.combo_annee.addItem(str(y), y)
        idx = self.combo_annee.findData(current)
        if idx >= 0:
            self.combo_annee.setCurrentIndex(idx)
        self.combo_annee.blockSignals(False)

    def _apply_filter(self):
        annee = self.combo_annee.currentData()
        mois = self.combo_mois.currentData()
        search_txt = self.inp_search.text().strip().lower()

        filtered = []
        for r in self.full_data:
            d = str(r.get('date_operation', ''))
            rec_year = extract_year(d)
            rec_month = extract_month(d)

            ok = True
            if annee and annee != 0 and rec_year != annee:
                ok = False
            if mois and mois != 0 and rec_month != mois:
                ok = False

            if ok and search_txt:
                searchable = (
                    f"{r.get('date_operation', '')} "
                    f"{r.get('montant_da', '')} "
                    f"{r.get('oc_or', '')} "
                    f"{r.get('oc_argent', '')} "
                    f"{r.get('tpe', '')} "
                    f"{r.get('ccp', '')} "
                    f"{r.get('euro', '')} "
                    f"{r.get('dollar', '')} "
                    f"{r.get('designation', '')}"
                ).lower()
                if search_txt not in searchable:
                    ok = False

            if ok:
                filtered.append(r)

        self._render_table(filtered)

    def _color_for_amount(self, val_str):
        val = safe_float(val_str)
        if val < 0:
            return self.BRUSH_RED
        elif val > 0:
            return self.BRUSH_GREEN
        return QBrush(QColor(TEXT_DARK))

    def _render_table(self, records):
        self.table.blockSignals(True)
        self.table.setUpdatesEnabled(False)
        self.table.setRowCount(0)

        total_da = total_oc_or = total_oc_argent = total_tpe = total_ccp = total_euro = total_dollar = 0.0

        for r in records:
            row = self.table.rowCount()
            self.table.insertRow(row)

            montant = safe_float(r.get('montant_da', '0'))
            oc_or = safe_float(r.get('oc_or', '0'))
            oc_argent = safe_float(r.get('oc_argent', '0'))
            tpe = safe_float(r.get('tpe', '0'))
            ccp = safe_float(r.get('ccp', '0'))
            euro = safe_float(r.get('euro', '0'))
            dollar = safe_float(r.get('dollar', '0'))

            total_da += montant
            total_oc_or += oc_or
            total_oc_argent += oc_argent
            total_tpe += tpe
            total_ccp += ccp
            total_euro += euro
            total_dollar += dollar

            color_brush = self._color_for_amount(r.get('montant_da', '0'))

            def m_item(text, align=Qt.AlignCenter, brush=None, bold=False, user_data=None):
                it = QTableWidgetItem(str(text))
                it.setTextAlignment(align)
                if brush:
                    it.setForeground(brush)
                if bold:
                    it.setFont(self.FONT_BOLD_11)
                else:
                    it.setFont(self.FONT_NORMAL)
                if user_data is not None:
                    it.setData(Qt.UserRole, user_data)
                return it

            it_date = m_item(r.get('date_operation', ''), user_data=r)
            self.table.setItem(row, 0, it_date)

            it_montant = m_item(r.get('montant_da', '0'), brush=color_brush, bold=True)
            self.table.setItem(row, 1, it_montant)

            it_gold = m_item(
                f"{oc_or:.2f}" if oc_or != 0 else "0",
                brush=self.BRUSH_GOLD if oc_or > 0 else None,
                bold=(oc_or > 0)
            )
            self.table.setItem(row, 2, it_gold)

            it_silver = m_item(
                f"{oc_argent:.2f}" if oc_argent != 0 else "0",
                brush=self.BRUSH_SILVER if oc_argent > 0 else None,
                bold=(oc_argent > 0)
            )
            self.table.setItem(row, 3, it_silver)

            self.table.setItem(row, 4, m_item(r.get('tpe', '0')))
            self.table.setItem(row, 5, m_item(r.get('ccp', '0')))
            self.table.setItem(row, 6, m_item(r.get('euro', '0')))
            self.table.setItem(row, 7, m_item(r.get('dollar', '0')))
            self.table.setItem(row, 8, m_item(r.get('designation') or '', align=Qt.AlignLeft | Qt.AlignVCenter))

        # ─── Ligne Récapitulative des Totaux (Thème Teal #0f8f83 identique au Journal) ───
        if records:
            row = self.table.rowCount()
            self.table.insertRow(row)

            it_lbl = QTableWidgetItem("TOTAUX :")
            it_lbl.setTextAlignment(Qt.AlignCenter)
            it_lbl.setBackground(self.BRUSH_TOTAL_BG)
            it_lbl.setForeground(self.BRUSH_WHITE)
            it_lbl.setFont(self.FONT_BOLD_12)
            self.table.setItem(row, 0, it_lbl)

            tot_vals = [
                f"{total_da:,.2f}",
                f"{total_oc_or:.2f} g",
                f"{total_oc_argent:.2f} g",
                f"{total_tpe:,.2f}",
                f"{total_ccp:,.2f}",
                f"{total_euro:,.2f}",
                f"{total_dollar:,.2f}"
            ]
            for i, val_text in enumerate(tot_vals):
                it = QTableWidgetItem(val_text)
                it.setTextAlignment(Qt.AlignCenter)
                it.setBackground(self.BRUSH_TOTAL_BG)
                it.setForeground(self.BRUSH_WHITE)
                it.setFont(self.FONT_BOLD_11)
                self.table.setItem(row, i + 1, it)

            it_empty = QTableWidgetItem("")
            it_empty.setBackground(self.BRUSH_TOTAL_BG)
            it_empty.setForeground(self.BRUSH_WHITE)
            self.table.setItem(row, 8, it_empty)

        # Mise à jour des cartes KPI
        self.card_cash.set_value(f"{total_da:,.2f} DA")
        self.card_gold.set_value(f"{total_oc_or:.2f} g")
        self.card_silver.set_value(f"{total_oc_argent:.2f} g")
        total_bank = total_tpe + total_ccp
        self.card_bank.set_value(f"{total_bank:,.2f} DA")
        self.card_devises.set_value(f"{total_euro:,.0f} € | {total_dollar:,.0f} $")

        self.table.blockSignals(False)
        self.table.setUpdatesEnabled(True)

    def load_data(self):
        self.full_data = self.manager.coffre.get_all_operations()
        self._build_year_combo()
        self._update_title_and_filter()

    def open_add_dialog(self):
        dlg = OperationDialog(parent=self)
        if dlg.exec() == QDialog.Accepted:
            d = dlg.get_data()
            self.manager.coffre.add_operation(
                d['date_operation'],
                d['montant_da'],
                d['tpe'],
                d['ccp'],
                d['euro'],
                d['dollar'],
                d['designation'],
                oc_or=d['oc_or'],
                oc_argent=d['oc_argent']
            )
            self.load_data()

    def open_edit_dialog(self, record):
        dlg = OperationDialog(record=record, parent=self)
        if dlg.exec() == QDialog.Accepted:
            d = dlg.get_data()
            self.manager.coffre.update_operation(
                d['id'],
                d['date_operation'],
                d['montant_da'],
                d['tpe'],
                d['ccp'],
                d['euro'],
                d['dollar'],
                d['designation'],
                oc_or=d['oc_or'],
                oc_argent=d['oc_argent']
            )
            self.load_data()

    def delete_record(self, rid):
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Confirmation")
        msg_box.setText("Êtes-vous sûr de vouloir supprimer définitivement cette opération du coffre ?")
        msg_box.setIcon(QMessageBox.Question)
        btn_yes = msg_box.addButton("Oui, Supprimer", QMessageBox.YesRole)
        btn_no = msg_box.addButton("Annuler", QMessageBox.NoRole)
        msg_box.setStyleSheet("""
            QMessageBox {
                background-color: #ffffff;
            }
            QPushButton {
                padding: 6px 14px;
                border-radius: 5px;
                font-weight: bold;
                font-size: 13px;
            }
        """)
        msg_box.exec()
        if msg_box.clickedButton() == btn_yes:
            self.manager.coffre.delete_operation(rid)
            self.load_data()
