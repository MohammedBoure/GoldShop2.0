import os
import calendar
from datetime import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QLabel, QFrame,
    QInputDialog, QMessageBox, QLineEdit, QMenu, QDialog, QFormLayout, QGridLayout
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QBrush
import qtawesome as qta

from PySide6.QtWidgets import QStyledItemDelegate
from PySide6.QtGui import QPalette

class ColorOverrideDelegate(QStyledItemDelegate):
    """
    Delegate يقرأ الألوان من البيانات ويرسمها مباشرة، 
    متجاوزاً تأثير QSS على لون النص والخلفية.
    """
    def paint(self, painter, option, index):
        # قراءة الألوان المحددة برمجياً
        bg = index.data(Qt.BackgroundRole)
        fg = index.data(Qt.ForegroundRole)

        if isinstance(bg, QBrush) and bg.style() != Qt.NoBrush:
            option.backgroundBrush = bg

        if isinstance(fg, QBrush) and fg.style() != Qt.NoBrush:
            color = fg.color()
            option.palette.setColor(QPalette.Text, color)
            option.palette.setColor(QPalette.PlaceholderText, color)
            option.palette.setColor(QPalette.HighlightedText, color)

        super().paint(painter, option, index)


class SaleDetailsDialog(QDialog):
    def __init__(self, manager, sale_id, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.sale_id = sale_id
        self.setWindowTitle("Détails complets de la vente (Mode Excel)")
        
        self.setMinimumSize(1200, 700)
        from PySide6.QtWidgets import QApplication
        screen = QApplication.primaryScreen().availableGeometry()
        self.resize(int(screen.width() * 0.9), int(screen.height() * 0.85))
        
        self.init_ui()

    def showEvent(self, event):
        super().showEvent(event)
        from PySide6.QtWidgets import QApplication
        screen = QApplication.primaryScreen().availableGeometry()
        x = (screen.width() - self.width()) // 2
        y = 10
        self.move(x, y)

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        try:
            with self.manager.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute("""
                    SELECT s.*, c.name as client_name, u.username as user_name 
                    FROM Sales s 
                    LEFT JOIN Clients c ON s.client_id = c.id 
                    LEFT JOIN Users u ON s.user_id = u.id 
                    WHERE s.id = %s
                """, (self.sale_id,))
                sale = cursor.fetchone()
                while cursor.nextset(): pass

                cursor.execute("""
                    SELECT si.*, 
                           cat.name as category_name,
                           sup.name as supplier_name,
                           COALESCE(i.metal_cost_per_gram, 0) as m_cost, 
                           COALESCE(i.labor_cost_per_gram, 0) as l_cost
                    FROM SaleItems si
                    LEFT JOIN Inventory i ON si.inventory_id = i.id
                    LEFT JOIN Categories cat ON i.category_id = cat.id
                    LEFT JOIN Suppliers sup ON i.supplier_id = sup.id
                    WHERE si.sale_id = %s
                """, (self.sale_id,))
                items = cursor.fetchall()
                while cursor.nextset(): pass
        except Exception as e:
            layout.addWidget(QLabel(f"Erreur de chargement: {e}"))
            return

        if not sale:
            layout.addWidget(QLabel("Vente introuvable."))
            return

        header_frame = QFrame()
        header_frame.setStyleSheet("background-color: #ecf0f1; border: 1px solid #bdc3c7; border-radius: 8px; padding: 15px;")
        header_layout = QGridLayout(header_frame)
        
        lbl_font = "font-size: 16px; color: #34495e;"
        val_font = "font-size: 18px; font-weight: bold; color: #16a085;"
        
        def create_lbl(text, style):
            lbl = QLabel(text)
            lbl.setStyleSheet(style)
            lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
            return lbl

        header_layout.addWidget(create_lbl("<b>N° Facture :</b>", lbl_font), 0, 0)
        header_layout.addWidget(create_lbl(sale.get('receipt_number', ''), val_font), 0, 1)
        
        header_layout.addWidget(create_lbl("<b>Date :</b>", lbl_font), 0, 2)
        header_layout.addWidget(create_lbl(str(sale.get('created_at', '')), val_font), 0, 3)

        header_layout.addWidget(create_lbl("<b>Client :</b>", lbl_font), 1, 0)
        header_layout.addWidget(create_lbl(sale.get('client_name') or 'Passager', val_font), 1, 1)
        
        header_layout.addWidget(create_lbl("<b>Vendeur :</b>", lbl_font), 1, 2)
        header_layout.addWidget(create_lbl(sale.get('user_name', ''), val_font), 1, 3)
        
        layout.addWidget(header_frame)

        table = QTableWidget(0, 9)
        table.setHorizontalHeaderLabels([
            "Code Barres", "Catégorie", "Désignation", "Fournisseur", 
            "Poids (g)", "Qté", "Prix Vendu", "Coût Estimé", "Faaida (Bénéfice)"
        ])
        
        table.setStyleSheet("""
            QTableWidget {
                background-color: white; gridline-color: #bdc3c7; font-size: 15px;
            }
            QHeaderView::section {
                background-color: #2c3e50; color: white; font-weight: bold; font-size: 15px; padding: 10px; border: 1px solid #1a252f;
            }
            QTableWidget::item:selected {
                background-color: #3498db; color: white;
            }
        """)
        table.setAlternatingRowColors(True)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectItems)
        
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        for i in range(4, 9):
            header.setSectionResizeMode(i, QHeaderView.ResizeToContents)

        total_benefice_brut = 0.0
        
        for item in items:
            row = table.rowCount()
            table.insertRow(row)

            barcode = str(item.get('barcode') or 'N/A')
            cat_name = str(item.get('category_name') or 'N/A')
            name = str(item.get('name') or '')
            sup_name = str(item.get('supplier_name') or 'N/A')
            w = float(item.get('sold_weight_g') or 0)
            q = int(item.get('sold_quantity') or 1)
            total_price = float(item.get('total_price_da') or 0)

            m_cost = float(item.get('m_cost', 0))
            l_cost = float(item.get('l_cost', 0))
            item_type = item.get('item_type', 'WEIGHT')

            cost = ((m_cost + l_cost) * w) if item_type == 'WEIGHT' else ((m_cost + l_cost) * q)
            benefice = total_price - cost
            total_benefice_brut += benefice

            def create_item(text, bold=False, color=None, align_left=False):
                it = QTableWidgetItem(text)
                it.setFont(QFont("", 12, QFont.Bold if bold else QFont.Normal))
                if color: it.setForeground(QBrush(QColor(color)))
                it.setTextAlignment(Qt.AlignLeft|Qt.AlignVCenter if align_left else Qt.AlignCenter)
                it.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                return it

            table.setItem(row, 0, create_item(barcode, bold=True, align_left=True))
            table.setItem(row, 1, create_item(cat_name))
            table.setItem(row, 2, create_item(name, align_left=True))
            table.setItem(row, 3, create_item(sup_name))
            table.setItem(row, 4, create_item(f"{w:.2f}"))
            table.setItem(row, 5, create_item(str(q)))
            table.setItem(row, 6, create_item(f"{total_price:,.2f} DA", bold=True))
            table.setItem(row, 7, create_item(f"{cost:,.2f} DA"))
            
            b_color = "green" if benefice >= 0 else "red"
            table.setItem(row, 8, create_item(f"{benefice:,.2f} DA", bold=True, color=b_color))

        layout.addWidget(table)

        discount = float(sale.get('discount_da') or 0)
        net_pay = float(sale.get('net_to_pay_da') or 0)
        final_profit = total_benefice_brut - discount

        summary_frame = QFrame()
        summary_frame.setStyleSheet("background-color: #fdf2e9; border: 1px solid #e67e22; border-radius: 8px; padding: 20px;")
        sum_lay = QGridLayout(summary_frame)

        sum_lay.addWidget(QLabel("<span style='font-size: 16px;'><b>Remise (Takhfid accordé) :</b></span>"), 0, 0)
        sum_lay.addWidget(QLabel(f"<span style='color: red; font-size: 18px; font-weight: bold;'>- {discount:,.2f} DA</span>"), 0, 1)

        sum_lay.addWidget(QLabel("<span style='font-size: 16px;'><b>Net à Payer par le client :</b></span>"), 1, 0)
        sum_lay.addWidget(QLabel(f"<span style='font-size: 20px; font-weight: bold; color: #2980b9;'>{net_pay:,.2f} DA</span>"), 1, 1)

        prof_color = "green" if final_profit >= 0 else "red"
        sum_lay.addWidget(QLabel("<span style='font-size: 18px;'><b>Bénéfice Net (Faaida الصافية) :</b></span>"), 2, 0)
        sum_lay.addWidget(QLabel(f"<span style='font-size: 24px; font-weight: 900; color: {prof_color};'>{final_profit:,.2f} DA</span>"), 2, 1)

        layout.addWidget(summary_frame)

        btn_close = QPushButton("Fermer (Annuler)")
        btn_close.setStyleSheet("background-color: #95a5a6; color: white; padding: 15px; font-weight: bold; font-size: 18px; border-radius: 5px;")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)


class EditSaleDialog(QDialog):
    def __init__(self, cash, tpe, oc, impos, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Modifier les montants de la vente")
        self.setFixedSize(400, 300)
        
        layout = QVBoxLayout(self)
        form = QFormLayout()
        
        self.inp_cash = QLineEdit(str(cash))
        self.inp_tpe = QLineEdit(str(tpe))
        self.inp_oc = QLineEdit(str(oc))
        self.inp_impos = QLineEdit(str(impos))
        
        from ui.tools.virtual_numpad import VirtualNumpad
        
        def show_pad(inp):
            VirtualNumpad(mode="direct", target_widget=inp, allow_decimal=True, allow_negative=False, parent=self).show()
        
        for inp in [self.inp_cash, self.inp_tpe, self.inp_oc, self.inp_impos]:
            inp.setStyleSheet("font-size: 18px; padding: 5px; font-weight: bold;")
            inp.setFocusPolicy(Qt.ClickFocus) 
            inp.mousePressEvent = lambda e, i=inp: show_pad(i)
            
        form.addRow("💰 Cash (DA) :", self.inp_cash)
        form.addRow("💳 TPE (DA) :", self.inp_tpe)
        form.addRow("⚖️ Or Cassé (g) :", self.inp_oc)
        form.addRow("📑 Impos (g) :", self.inp_impos)
        layout.addLayout(form)
        
        btn_lay = QHBoxLayout()
        btn_save = QPushButton("Enregistrer les modifications")
        btn_save.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; font-size: 14px; padding: 10px;")
        btn_save.clicked.connect(self.accept)
        btn_lay.addWidget(btn_save)
        layout.addLayout(btn_lay)

    def get_values(self):
        try: c = float(self.inp_cash.text() or 0)
        except: c = 0.0
        try: t = float(self.inp_tpe.text() or 0)
        except: t = 0.0
        try: o = float(self.inp_oc.text() or 0)
        except: o = 0.0
        try: i = float(self.inp_impos.text() or 0)
        except: i = 0.0
        return c, t, o, i

    def accept(self):
        try:
            if self.focusWidget(): self.focusWidget().clearFocus()
        except: pass
        super().accept()

    def reject(self):
        try:
            if self.focusWidget(): self.focusWidget().clearFocus()
        except: pass
        super().reject()

    def showEvent(self, event):
        super().showEvent(event)
        from PySide6.QtWidgets import QApplication
        screen = QApplication.primaryScreen().availableGeometry()
        x = (screen.width() - self.width()) // 2
        y = 10
        self.move(x, y)


class EditObservationDialog(QDialog):
    def __init__(self, current_obs, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Modifier l'observation")
        self.setFixedSize(500, 200)
        
        layout = QVBoxLayout(self)
        
        self.inp_obs = QLineEdit(current_obs)
        self.inp_obs.setStyleSheet("font-size: 18px; padding: 5px; font-weight: bold;")
        layout.addWidget(QLabel("Observation :"))
        layout.addWidget(self.inp_obs)
        
        btn_lay = QHBoxLayout()
        btn_save = QPushButton("Enregistrer")
        btn_save.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; font-size: 14px; padding: 10px;")
        btn_save.clicked.connect(self.accept)
        
        from ui.tools.virtual_keyboard import KeyboardFocusTracker
        KeyboardFocusTracker.track_widget(self.inp_obs, auto_open=True)
        
        btn_lay.addWidget(btn_save)
        layout.addLayout(btn_lay)

    def showEvent(self, event):
        super().showEvent(event)
        from PySide6.QtWidgets import QApplication
        screen = QApplication.primaryScreen().availableGeometry()
        x = (screen.width() - self.width()) // 2
        y = 10
        self.move(x, y)

    def get_value(self):
        return self.inp_obs.text().strip()


class EditSellerDialog(QDialog):
    def __init__(self, manager, current_seller_id, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.current_seller_id = current_seller_id
        self.setWindowTitle("Modifier le vendeur")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.combo_seller = QComboBox()
        self.combo_seller.setStyleSheet("font-size: 16px; padding: 6px;")
        self._load_sellers()
        form.addRow("Vendeur :", self.combo_seller)
        layout.addLayout(form)

        buttons = QHBoxLayout()
        btn_cancel = QPushButton("Annuler")
        btn_save = QPushButton("Enregistrer")
        btn_save.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; padding: 8px 18px;")
        btn_cancel.clicked.connect(self.reject)
        btn_save.clicked.connect(self.accept)
        buttons.addWidget(btn_cancel)
        buttons.addWidget(btn_save)
        layout.addLayout(buttons)

    def _load_sellers(self):
        try:
            with self.manager.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute(
                    "SELECT id, username FROM Users WHERE is_active = 1 OR id = %s ORDER BY username",
                    (self.current_seller_id,)
                )
                sellers = cursor.fetchall()
                while cursor.nextset():
                    pass

            for seller in sellers:
                self.combo_seller.addItem(seller['username'], seller['id'])
            if self.current_seller_id is not None:
                index = self.combo_seller.findData(self.current_seller_id)
                if index >= 0:
                    self.combo_seller.setCurrentIndex(index)
        except Exception as e:
            QMessageBox.warning(self, "Erreur", f"Impossible de charger les vendeurs : {e}")

    def get_seller_id(self):
        return self.combo_seller.currentData()

class ExcelJournalView(QWidget):
    def __init__(self, manager):
        super().__init__()
        self.manager = manager
        self.init_ui()
        self.populate_filters()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        filter_frame = QFrame()
        filter_frame.setObjectName("panel") 
        filter_layout_v = QVBoxLayout(filter_frame)
        filter_layout_v.setContentsMargins(15, 10, 15, 10)
        
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("📅 Année :"))
        self.combo_year = QComboBox()
        self.combo_year.setStyleSheet("font-size: 13px; padding: 4px 8px; border: 1px solid #cbd5df; border-radius: 4px; background-color: white;")
        row1.addWidget(self.combo_year)
        row1.addWidget(QLabel("Mois :"))
        self.combo_month = QComboBox()
        self.combo_month.setStyleSheet("font-size: 13px; padding: 4px 8px; border: 1px solid #cbd5df; border-radius: 4px; background-color: white;")
        row1.addWidget(self.combo_month)
        row1.addWidget(QLabel("Jour :"))
        self.combo_day = QComboBox()
        self.combo_day.setStyleSheet("font-size: 13px; padding: 4px 8px; border: 1px solid #cbd5df; border-radius: 4px; background-color: white;")
        row1.addWidget(self.combo_day)
        
        self.btn_search = QPushButton(" Afficher le Journal")
        self.btn_search.setIcon(qta.icon("fa5s.search", color="white"))
        self.btn_search.setStyleSheet("background-color: #0f8f83; color: white; padding: 5px 12px; border-radius: 4px; font-weight: bold; font-size: 13px;")
        self.btn_search.clicked.connect(self.load_data)
        
        row1.addStretch()
        
        self.btn_set_fc = QPushButton(" Fc (Caisse)")
        self.btn_set_fc.setIcon(qta.icon("fa5s.cash-register", color="white"))
        self.btn_set_fc.setStyleSheet("background-color: #f39c12; color: white; padding: 5px 12px; border-radius: 4px; font-weight: bold; font-size: 13px;")
        self.btn_set_fc.clicked.connect(self.set_starting_cash)
        
        self.btn_new_sale = QPushButton(" + Nouvelle Vente")
        self.btn_new_sale.setIcon(qta.icon("fa5s.cart-plus", color="white"))
        self.btn_new_sale.setStyleSheet("background-color: #27ae60; color: white; padding: 5px 12px; border-radius: 4px; font-weight: bold; font-size: 13px;")
        self.btn_new_sale.clicked.connect(self.open_sales_interface)
        
        row1.addWidget(self.btn_search)
        row1.addSpacing(10)
        row1.addWidget(self.btn_set_fc)
        row1.addSpacing(10)
        row1.addWidget(self.btn_new_sale)
        
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("🔍 Recherche Client :"))
        self.inp_search_client = QLineEdit()
        self.inp_search_client.setPlaceholderText("Nom du client ou désignation...")
        self.inp_search_client.setStyleSheet("font-size: 13px; padding: 4px 8px; border: 1px solid #cbd5df; border-radius: 4px; background-color: white; min-width: 200px;")
        self.inp_search_client.textChanged.connect(self.load_data)
        row2.addWidget(self.inp_search_client)
        
        row2.addSpacing(15)
        row2.addWidget(QLabel("👨‍💼 Vendeur :"))
        self.combo_seller = QComboBox()
        self.combo_seller.setStyleSheet("font-size: 13px; padding: 4px 8px; border: 1px solid #cbd5df; border-radius: 4px; background-color: white;")
        self.combo_seller.addItem("Tous les vendeurs", 0)
        self.combo_seller.currentIndexChanged.connect(self.load_data)
        row2.addWidget(self.combo_seller)

        row2.addSpacing(15)
        self.toolbar_actions_widget = QWidget()
        self.toolbar_actions_layout = QHBoxLayout(self.toolbar_actions_widget)
        self.toolbar_actions_layout.setContentsMargins(0, 0, 0, 0)
        self.toolbar_actions_layout.setSpacing(5)
        row2.addWidget(self.toolbar_actions_widget)
        row2.addStretch()
        
        filter_layout_v.addLayout(row1)
        filter_layout_v.addLayout(row2)
        layout.addWidget(filter_frame)

        self.lbl_main_title = QLabel("États De Recettes Du Mois")
        self.lbl_main_title.setObjectName("pageTitle")
        self.lbl_main_title.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_main_title)

        self.table = QTableWidget(0, 10)
        self.table.setItemDelegate(ColorOverrideDelegate(self.table)) 
        self.table.setHorizontalHeaderLabels(["Disignation", "P.S", "Recette", "O.C", "TPE", "Euro", "Dollar", "Vendeur", "Observation", "Impos"])
        self.table.setStyleSheet("""
            QHeaderView::section { background-color: #0f8f83; color: white; font-weight: bold; border: 1px solid #0b776d; padding: 5px; font-size: 14px; }
            QTableWidget::item:selected { background-color: #d1d8e0; color: black; }
        """)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        self.table.itemSelectionChanged.connect(self.on_table_selection_changed)
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)       
        for i in range(1, 10):
            if i != 8: header.setSectionResizeMode(i, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(8, QHeaderView.Stretch)       
        layout.addWidget(self.table)
        self.load_sellers_combo()

    # ──────────────────────────────────────────────────────────────
    # قراءة أسماء الطابعات من الإعدادات
    # ──────────────────────────────────────────────────────────────
    @staticmethod
    def _read_config_json():
        """قراءة config.json بأمان"""
        try:
            import json
            if os.path.exists("config.json"):
                with open("config.json", "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    @classmethod
    def _get_pdf_printer_name(cls):
        """اسم طابعة PDF من pdf_config.printer_name"""
        cfg = cls._read_config_json()
        return str(cfg.get("pdf_config", {}).get("printer_name", "") or "").strip()

    @classmethod
    def _get_thermal_printer_name(cls):
        """اسم الطابعة الحرارية من thermal_config.printer_name"""
        cfg = cls._read_config_json()
        return str(cfg.get("thermal_config", {}).get("printer_name", "") or "").strip()

    # ──────────────────────────────────────────────────────────────
    # القائمة المنسدلة (كليك يمين) - 3 خيارات طباعة
    # ──────────────────────────────────────────────────────────────
    def show_context_menu(self, pos):
        row = self.table.rowAt(pos.y())
        if row < 0: return
        item = self.table.item(row, 0)
        if not item: return
        
        sale_id = item.data(Qt.UserRole)
        if not sale_id: return 
        
        is_versement = isinstance(sale_id, str) and sale_id.startswith("VRS_")
        item_id = item.data(Qt.UserRole + 1)
        
        cash = item.data(Qt.UserRole + 2)
        tpe = item.data(Qt.UserRole + 3)
        oc = item.data(Qt.UserRole + 4)
        impos = item.data(Qt.UserRole + 5)
        seller_id = item.data(Qt.UserRole + 6)

        item_obs = self.table.item(row, 8)
        current_obs = item_obs.text() if item_obs else ""

        # قراءة أسماء الطابعات
        pdf_printer = self._get_pdf_printer_name()
        thermal_printer = self._get_thermal_printer_name()

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { font-size: 14px; background-color: white; border: 1px solid #ccc; padding: 5px 0; }
            QMenu::item { padding: 8px 30px; }
            QMenu::item:selected { background-color: #3498db; color: white; }
            QMenu::separator { height: 1px; background: #ddd; margin: 4px 10px; }
        """)

        if is_versement:
            act_edit_obs = menu.addAction("Modifier l'observation")
            action = menu.exec_(self.table.viewport().mapToGlobal(pos))
            if action == act_edit_obs:
                self.edit_versement_observation(item_id, current_obs)
            return

        # ── خيار 1: تحميل PDF ──
        act_print_pdf = menu.addAction("📄 Télécharger PDF (Aperçu)")

        # ── خيار 2: طباعة مباشرة على طابعة PDF ──
        if pdf_printer:
            act_print_direct = menu.addAction(f"🖨️ Imprimer directement → {pdf_printer}")
        else:
            act_print_direct = menu.addAction("🖨️ Imprimer directement (non configurée)")
            act_print_direct.setEnabled(False)

        # ── خيار 3: طباعة حرارية ──
        if thermal_printer:
            act_print_thermal = menu.addAction(f"🧾 Imprimer sur thermique → {thermal_printer}")
        else:
            act_print_thermal = menu.addAction("🧾 Imprimer sur thermique (non configurée)")
            act_print_thermal.setEnabled(False)

        menu.addSeparator()

        # ── باقي الخيارات ──
        act_details = menu.addAction("ℹ️ Détails complets et Bénéfice (Faaida)")
        menu.addSeparator()
        act_edit = menu.addAction("✏️ Modifier les montants de cette vente")
        act_edit_seller = menu.addAction("Modifier le vendeur")
        act_edit_obs = menu.addAction("📝 Modifier l'observation")
        menu.addSeparator()
        act_del = menu.addAction("🗑️ Supprimer (Annuler) cette vente")

        action = menu.exec_(self.table.viewport().mapToGlobal(pos))
        if not action: return
        
        if action == act_print_pdf:
            self.print_invoice_pdf(sale_id)
        elif action == act_print_direct:
            self.print_invoice_pdf(sale_id, open_pdf=False, direct=True)
        elif action == act_print_thermal:
            self.print_invoice_thermal(sale_id)
        elif action == act_details:
            self.show_sale_details(sale_id)
        elif action == act_edit:
            self.edit_sale(sale_id, cash, tpe, oc, impos)
        elif action == act_edit_seller:
            self.edit_seller(sale_id, seller_id)
        elif action == act_edit_obs:
            self.edit_observation(sale_id, item_id, current_obs)
        elif action == act_del:
            self.delete_sale(sale_id)

    def _add_action_btn(self, icon_name, tooltip, bg_color, hover_color, callback, enabled=True):
        from PySide6.QtCore import QSize
        btn = QPushButton()
        btn.setIcon(qta.icon(icon_name, color="white"))
        btn.setIconSize(QSize(16, 16))
        btn.setToolTip(tooltip)
        btn.setCursor(Qt.PointingHandCursor if enabled else Qt.ArrowCursor)
        btn.setEnabled(enabled)
        btn.setStyleSheet(f"""
            QPushButton {{ background-color: {bg_color}; border: none; padding: 5px 10px; border-radius: 4px; }}
            QPushButton:hover {{ background-color: {hover_color}; }}
            QPushButton:disabled {{ background-color: #bdc3c7; }}
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
        
        sale_id = item.data(Qt.UserRole)
        if not sale_id: return 
        
        is_versement = isinstance(sale_id, str) and sale_id.startswith("VRS_")
        item_id = item.data(Qt.UserRole + 1)
        
        if is_versement:
            current_vrs_obs = self.table.item(row, 8).text() if self.table.item(row, 8) else ""
            self._add_action_btn("fa5s.comment-dots", "Modifier l'observation", "#f1c40f", "#f39c12", lambda: self.edit_versement_observation(item_id, current_vrs_obs))
            return

        cash = item.data(Qt.UserRole + 2)
        tpe = item.data(Qt.UserRole + 3)
        oc = item.data(Qt.UserRole + 4)
        impos = item.data(Qt.UserRole + 5)
        seller_id = item.data(Qt.UserRole + 6)

        item_obs = self.table.item(row, 8)
        current_obs = item_obs.text() if item_obs else ""

        pdf_printer = self._get_pdf_printer_name()
        thermal_printer = self._get_thermal_printer_name()

        self._add_action_btn("fa5s.info-circle", "Détails complets et Bénéfice (Faaida)", "#3498db", "#2980b9", lambda: self.show_sale_details(sale_id))
        self._add_action_btn("fa5s.file-pdf", "Télécharger PDF (Aperçu)", "#e74c3c", "#c0392b", lambda: self.print_invoice_pdf(sale_id))
        self._add_action_btn("fa5s.print", f"Imprimer directement → {pdf_printer}" if pdf_printer else "Imprimer directement (non configurée)", "#9b59b6", "#8e44ad", lambda: self.print_invoice_pdf(sale_id, open_pdf=False, direct=True), enabled=bool(pdf_printer))
        self._add_action_btn("fa5s.receipt", f"Imprimer sur thermique → {thermal_printer}" if thermal_printer else "Imprimer sur thermique (non configurée)", "#e67e22", "#d35400", lambda: self.print_invoice_thermal(sale_id), enabled=bool(thermal_printer))
        self._add_action_btn("fa5s.edit", "Modifier les montants de cette vente", "#27ae60", "#2ecc71", lambda: self.edit_sale(sale_id, cash, tpe, oc, impos))
        self._add_action_btn("fa5s.user-edit", "Modifier le vendeur", "#16a085", "#1abc9c", lambda: self.edit_seller(sale_id, seller_id))
        self._add_action_btn("fa5s.comment-dots", "Modifier l'observation", "#f1c40f", "#f39c12", lambda: self.edit_observation(sale_id, item_id, current_obs))
        self._add_action_btn("fa5s.trash-alt", "Supprimer (Annuler) cette vente", "#c0392b", "#962d2d", lambda: self.delete_sale(sale_id))

    # ──────────────────────────────────────────────────────────────
    # طباعة PDF (تحميل أو مباشرة على طابعة PDF)
    # ──────────────────────────────────────────────────────────────
    def print_invoice_pdf(self, sale_id, open_pdf=True, direct=False):
        sale = self.manager.sales.get_sale_details(sale_id)
        if not sale:
            QMessageBox.warning(self, "Erreur", "Détails de la vente introuvables.")
            return

        client_name = sale.get('client_name') or 'Passager'
        items = sale.get('items', [])
        total_brut = float(sale.get('total_amount_da', 0))
        discount = float(sale.get('discount_da', 0))
        net = float(sale.get('net_to_pay_da', 0))
        
        cash = float(sale.get('cash_paid_da', 0))
        tpe = float(sale.get('tpe_paid_da', 0))
        old_gold = float(sale.get('old_gold_weight_g', 0))

        mapped_items = []
        for it in items:
            mapped = dict(it)
            mapped['name'] = it.get('name', '')
            mapped['cart_line_total'] = float(it.get('total_price_da', 0))
            mapped['cart_sold_weight'] = float(it.get('sold_weight_g', 0))
            mapped['cart_sold_qty'] = int(it.get('sold_quantity', 1))
            mapped['cart_unit_price'] = float(it.get('unit_price_da', 0))
            mapped['custom_note'] = str(it.get('custom_note') or '')
            mapped_items.append(mapped)

        try:
            from ui.tools.invoice_generator import generate_invoice_pdf

            direct_printer = ""
            if direct:
                direct_printer = self._get_pdf_printer_name()
                if not direct_printer:
                    QMessageBox.warning(
                        self, "Aucune imprimante PDF",
                        "Aucune imprimante PDF n'est configurée.\n\n"
                        "Veuillez aller dans Paramètres → Impression PDF\n"
                        "et sélectionner une imprimante."
                    )
                    return

            generate_invoice_pdf(
                sale_id=sale_id,
                client_name=client_name,
                items=mapped_items,
                total_brut=total_brut,
                discount=discount,
                net=net,
                cash_paid=cash,
                tpe_paid=tpe,
                or_casse_g=old_gold,
                show_discount=(discount > 0),
                facture_number=sale.get('receipt_number', ''),
                printed_at=sale.get('created_at'),
                open_pdf=open_pdf,
                direct_printer_name=direct_printer
            )

            if direct:
                QMessageBox.information(
                    self, "Impression PDF envoyée",
                    f"La facture a été envoyée à :\n{direct_printer}"
                )

        except ValueError as e:
            QMessageBox.critical(
                self, "Erreur d'impression PDF",
                f"Impossible d'imprimer :\n\n{e}\n\n"
                "Vérifiez que l'imprimante est allumée et connectée."
            )
        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Erreur", f"Impossible de générer la facture:\n{e}")

    # ──────────────────────────────────────────────────────────────
    # طباعة حرارية مباشرة (QPainter → الطابعة الحرارية)
    # ──────────────────────────────────────────────────────────────
    def print_invoice_thermal(self, sale_id):
        sale = self.manager.sales.get_sale_details(sale_id)
        if not sale:
            QMessageBox.warning(self, "Erreur", "Détails de la vente introuvables.")
            return

        thermal_printer = self._get_thermal_printer_name()
        if not thermal_printer:
            QMessageBox.warning(
                self, "Aucune imprimante thermique",
                "Aucune imprimante thermique n'est configurée.\n\n"
                "Veuillez aller dans Paramètres → Impression Thermique\n"
                "et sélectionner une imprimante."
            )
            return

        # تجهيز البيانات بالشكل الذي يتوقعه print_functions.py
        thermal_items = []
        total_weight = 0.0
        for it in sale.get('items', []):
            is_w = (it.get('item_type', 'WEIGHT') == 'WEIGHT')
            w = float(it.get('sold_weight_g', 0)) if is_w else 0.0
            q = float(it.get('sold_quantity', 1)) if not is_w else 0.0
            if is_w:
                total_weight += w

            thermal_items.append({
                'barcode': str(it.get('barcode') or it.get('inventory_barcode') or ''),
                'name': str(it.get('name') or it.get('item_name') or 'Article'),
                'itemName': str(it.get('name') or it.get('item_name') or 'Article'),
                'item_type': it.get('item_type', 'WEIGHT'),
                'cart_sold_weight': w,
                'cart_sold_qty': q,
                'weight': w,
                'cart_line_total': float(it.get('total_price_da', 0)),
                'amount': float(it.get('total_price_da', 0)),
                'custom_note': str(it.get('custom_note') or ''),
                'note': str(it.get('custom_note') or ''),
            })

        thermal_data = {
            'items': thermal_items,
            'sale_id': sale_id,     
            'total_brut': float(sale.get('total_amount_da', 0)),
            'total': float(sale.get('total_amount_da', 0)),
            'discount': float(sale.get('discount_da', 0)),
            'net': float(sale.get('net_to_pay_da', 0)),
            'net_to_pay': float(sale.get('net_to_pay_da', 0)),
            'total_weight': total_weight,
            'paid_weight_equiv': total_weight,
            'remainder_weight': 0.0,
            'client_name': sale.get('client_name') or 'Passager',
            'customerFullName': sale.get('client_name') or 'Passager',
            'currency': 'DA',
            'facture_number': str(sale.get('receipt_number', '')),
            'sale_date': str(sale.get('created_at', '')),
            'printed_at': sale.get('created_at'),
            'payments_history': [],
            'amount_in_words': '.............................................',
        }

        try:
            from ui.tools.print_functions import print_thermal_facture

            print_thermal_facture(
                thermal_data,
                calculate_only=False,
                printer_name=thermal_printer
            )

            QMessageBox.information(
                self, "Impression thermique envoyée",
                f"Le ticket a été envoyé à l'imprimante thermique :\n{thermal_printer}"
            )

        except ValueError as e:
            QMessageBox.critical(
                self, "Erreur imprimante thermique",
                f"Impossible d'imprimer sur la thermique :\n\n{e}\n\n"
                "Vérifiez que l'imprimante est allumée, connectée,\n"
                "et que le nom correspond exactement dans les paramètres."
            )
        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.critical(
                self, "Erreur thermique",
                f"Erreur lors de l'impression thermique :\n{e}"
            )

    # ──────────────────────────────────────────────────────────────
    # باقي الدوال (بدون تغيير)
    # ──────────────────────────────────────────────────────────────
    def show_sale_details(self, sale_id):
        pwd, ok = QInputDialog.getText(
            self, "Protection Admin", 
            "Veuillez entrer le mot de passe Administrateur pour afficher les bénéfices (Faaida) :", 
            QLineEdit.Password
        )
        if not ok or not pwd:
            return
            
        if not self.manager.users.verify_admin_password(pwd):
            QMessageBox.warning(self, "Accès Refusé", "Mot de passe Administrateur incorrect.")
            return

        dlg = SaleDetailsDialog(self.manager, sale_id, self)
        dlg.exec()

    def edit_sale(self, sale_id, cash, tpe, oc, impos):
        dlg = EditSaleDialog(cash, tpe, oc, impos, self)
        if dlg.exec() == QDialog.Accepted:
            n_cash, n_tpe, n_oc, n_impos = dlg.get_values()
            if self.manager.sales.update_sale_financials(sale_id, n_cash, n_tpe, n_oc, n_impos):
                self.load_data() 
            else:
                QMessageBox.warning(self, "Erreur", "Erreur lors de la mise à jour.")

    def edit_seller(self, sale_id, current_seller_id):
        dlg = EditSellerDialog(self.manager, current_seller_id, self)
        if dlg.exec() == QDialog.Accepted:
            seller_id = dlg.get_seller_id()
            if seller_id is None:
                QMessageBox.warning(self, "Erreur", "Veuillez sÃ©lectionner un vendeur.")
                return
            if self.manager.sales.update_sale_seller(sale_id, seller_id):
                self.load_data()
            else:
                QMessageBox.warning(self, "Erreur", "Erreur lors de la mise Ã  jour du vendeur.")
    def edit_observation(self, sale_id, sale_item_id, current_obs):
        dlg = EditObservationDialog(current_obs, self)
        if dlg.exec() == QDialog.Accepted:
            n_obs = dlg.get_value()
            updated = False
            if sale_item_id and hasattr(self.manager.sales, "update_sale_item_notes"):
                updated = self.manager.sales.update_sale_item_notes(sale_item_id, n_obs)
            elif hasattr(self.manager.sales, "update_sale_notes"):
                updated = self.manager.sales.update_sale_notes(sale_id, n_obs)
            if updated:
                self.load_data()
            else:
                QMessageBox.warning(self, "Erreur", "Erreur lors de la mise à jour de l'observation.")

    def edit_versement_observation(self, payment_id, current_obs):
        if not payment_id or not hasattr(self.manager.versements, "update_payment_notes"):
            QMessageBox.warning(self, "Erreur", "La modification de la note du versement est indisponible.")
            return
        dlg = EditObservationDialog(current_obs, self)
        if dlg.exec() == QDialog.Accepted:
            if self.manager.versements.update_payment_notes(payment_id, dlg.get_value()):
                self.load_data()
            else:
                QMessageBox.warning(self, "Erreur", "Erreur lors de la mise à jour de l'observation.")

    def delete_sale(self, sale_id):
        reply = QMessageBox.question(self, "Confirmation", "Voulez-vous vraiment annuler cette vente ?\n\n(Les articles seront automatiquement remis en stock)", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            if self.manager.sales.cancel_sale(sale_id): 
                QMessageBox.information(self, "Succès", "Vente annulée avec succès. Le stock a été mis à jour.")
                self.load_data()
            else:
                QMessageBox.warning(self, "Erreur", "Impossible d'annuler la vente.")

    def load_sellers_combo(self):
        try:
            with self.manager.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute("SELECT id, username FROM Users WHERE is_active = 1")
                for u in cursor.fetchall():
                    self.combo_seller.addItem(u['username'], u['id'])
                while cursor.nextset(): pass
        except Exception: pass
            
    def set_starting_cash(self):
        journee = self.manager.cash_box.get_or_create_today_session()
        if not journee: return
        current_fc = float(journee.get('starting_cash_da', 0.0))
        from ui.tools.virtual_numpad import VirtualNumpad
        pad = VirtualNumpad(title="Fond de Caisse (Fc)", mode="dialog", allow_decimal=True, initial_value=str(current_fc), parent=self)
        if pad.exec() == QDialog.Accepted:
            try:
                amount = float(pad.get_value())
                if self.manager.cash_box.update_starting_cash(journee['id'], amount): 
                    self.load_data() 
            except ValueError:
                pass
                
    def populate_filters(self):
        current_date = datetime.now()
        for y in range(current_date.year - 2, current_date.year + 3):
            self.combo_year.addItem(str(y), y)
        self.combo_year.setCurrentText(str(current_date.year))
        months = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin", "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"]
        for i, m in enumerate(months, 1): self.combo_month.addItem(m, i)
        self.combo_month.setCurrentIndex(current_date.month - 1)
        self.combo_day.addItem("Tous les jours", 0)
        for d in range(1, 32): self.combo_day.addItem(f"{d:02d}", d)
            
    def get_french_date_string(self, date_obj):
        days = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
        day_name = days[date_obj.weekday()]
        return f"{day_name} Le {date_obj.strftime('%d/%m/%Y')}"
        
    def add_merged_row(self, text1, col_span1, text2=None, col_span2=None, bg_color="#2c3e50", text_color="white", bg_color2="#d35400"):
        row = self.table.rowCount()
        self.table.insertRow(row)
        item1 = QTableWidgetItem(text1)
        item1.setTextAlignment(Qt.AlignCenter)
        item1.setFont(QFont("", 12, QFont.Bold))
        item1.setBackground(QBrush(QColor(bg_color)))
        item1.setForeground(QBrush(QColor(text_color)))
        self.table.setItem(row, 0, item1)
        self.table.setSpan(row, 0, 1, col_span1)
        if text2 and col_span2:
            item2 = QTableWidgetItem(text2)
            item2.setTextAlignment(Qt.AlignCenter)
            item2.setFont(QFont("", 12, QFont.Bold))
            item2.setBackground(QBrush(QColor(bg_color2)))
            item2.setForeground(QBrush(QColor(text_color)))
            self.table.setItem(row, col_span1, item2)
            self.table.setSpan(row, col_span1, 1, col_span2)
            
    def load_data(self):
        self.table.setRowCount(0)
        year = self.combo_year.currentData()
        month = self.combo_month.currentData()
        day = self.combo_day.currentData()
        client_search = self.inp_search_client.text().lower().strip()
        seller_filter_name = self.combo_seller.currentText()
        seller_filter_id = self.combo_seller.currentData()
        
        self.lbl_main_title.setText(f"États De Recettes Du Mois De {self.combo_month.currentText()} {year}")
        try:
            with self.manager.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query_sessions = "SELECT * FROM DailySessions WHERE YEAR(opened_at) = %s AND MONTH(opened_at) = %s"
                params = [year, month]
                if day > 0:
                    query_sessions += " AND DAY(opened_at) = %s"
                    params.append(day)
                query_sessions += " ORDER BY opened_at ASC"
                cursor.execute(query_sessions, tuple(params))
                sessions = cursor.fetchall()
                while cursor.nextset(): pass
                
                if not sessions:
                    self.add_merged_row("Aucune donnée trouvée pour cette période.", 10, bg_color="#ecf0f1", text_color="#7f8c8d")
                    return
                    
                for session in sessions:
                    journee_id = session['id']
                    date_obj = session['opened_at'] 
                    fc_amount = float(session['starting_cash_da'] or 0)
                    
                    receipts = getattr(self.manager.sales, 'get_daily_sales_for_excel', lambda x: [])(journee_id)
                    filtered_receipts = []
                    for r in receipts:
                        obs = str(r.get('Observation', '')).lower()
                        des = str(r.get('Designation', '')).lower()
                        vend = str(r.get('Vendeur_Sofiane', ''))
                        if client_search and (client_search not in obs and client_search not in des): continue
                        if seller_filter_id != 0 and vend != seller_filter_name: continue
                        filtered_receipts.append(r)
                        
                    if not filtered_receipts and (client_search or seller_filter_id != 0): continue
                        
                    self.add_merged_row(self.get_french_date_string(date_obj), 3, f"Fc : {fc_amount:,.0f} Da", 7, bg_color="#2c3e50", text_color="white", bg_color2="#d35400")
                    
                    if not filtered_receipts:
                        row = self.table.rowCount()
                        self.table.insertRow(row)
                        self.table.setItem(row, 0, QTableWidgetItem("Aucune vente"))
                        continue
                        
                    t_ps, t_rec, t_oc, t_tpe, t_euro, t_dollar = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
                    
                    current_sale_id = None
                    current_bg = "#ffffff"
                    
                    for r in filtered_receipts:
                        sale_id = r.get('sale_id')
                        if current_sale_id is None:
                            current_sale_id = sale_id
                            current_bg = "#ffffff"
                        elif sale_id != current_sale_id:
                            current_sale_id = sale_id
                            current_bg = "#ebf5fb" if current_bg == "#ffffff" else "#ffffff"

                        t_ps += float(r.get('P_S') or 0)
                        t_rec += float(r.get('Recette') or 0)
                        t_oc += float(r.get('OC') or 0)
                        t_tpe += float(r.get('TPE') or 0)
                        t_euro += float(r.get('Euro') or 0)
                        t_dollar += float(r.get('Dollar') or 0)
                        
                        row = self.table.rowCount()
                        self.table.insertRow(row)
                        cols_data = [
                            str(r.get('Designation', '')),
                            f"{float(r.get('P_S') or 0):.2f}",
                            f"{float(r.get('Recette') or 0):.0f}" if float(r.get('Recette') or 0) != 0 else ";",
                            f"{float(r.get('OC') or 0):.2f}" if float(r.get('OC') or 0) != 0 else "0",
                            f"{float(r.get('TPE') or 0):.0f}" if float(r.get('TPE') or 0) != 0 else "0",
                            f"{float(r.get('Euro') or 0):.0f}" if float(r.get('Euro') or 0) != 0 else "0",
                            f"{float(r.get('Dollar') or 0):.0f}" if float(r.get('Dollar') or 0) != 0 else "0",
                            str(r.get('Vendeur_Sofiane', '')),
                            str(r.get('Observation', '')),
                            f"{float(r.get('Impos') or 0):.2f}" if float(r.get('Impos') or 0) != 0 else "0"
                        ]
                        
                        for col_idx, val in enumerate(cols_data):
                            item = QTableWidgetItem(val)
                            item.setTextAlignment(Qt.AlignCenter if col_idx in [1,2,3,4,5,6,9] else Qt.AlignLeft | Qt.AlignVCenter)
                            item.setBackground(QBrush(QColor(current_bg)))
                            if val == ";" or (val.startswith("-") and val not in ["-0", "-0.0", "-0.00"]):
                                item.setForeground(QBrush(QColor("#c0392b")))

                            
                            if col_idx == 0:
                                item.setData(Qt.UserRole, r.get('sale_id'))
                                item.setData(Qt.UserRole + 1, r.get('item_id'))
                                item.setData(Qt.UserRole + 2, float(r.get('Recette') or 0))
                                item.setData(Qt.UserRole + 3, float(r.get('TPE') or 0))
                                item.setData(Qt.UserRole + 4, float(r.get('OC') or 0))
                                item.setData(Qt.UserRole + 5, float(r.get('Impos') or 0))
                                item.setData(Qt.UserRole + 6, r.get('vendeur_id'))
                                
                            self.table.setItem(row, col_idx, item)
                            
                    totals = getattr(self.manager.sales, 'get_daily_totals', lambda x: {})(journee_id)
                    row = self.table.rowCount()
                    self.table.insertRow(row)
                    
                    empty_item = QTableWidgetItem("Total Journée")
                    empty_item.setFont(QFont("", 11, QFont.Bold))
                    empty_item.setTextAlignment(Qt.AlignCenter)
                    empty_item.setBackground(QBrush(QColor("#0f8f83")))
                    empty_item.setForeground(QBrush(QColor("white")))
                    self.table.setItem(row, 0, empty_item)
                    
                    for idx, t_val in enumerate([t_ps, t_rec, t_oc, t_tpe, t_euro, t_dollar], start=1):
                        fmt = f"{t_val:.2f}" if idx in [1, 3] else f"{t_val:.0f}"
                        t_item = QTableWidgetItem(fmt)
                        t_item.setFont(QFont("", 11, QFont.Bold))
                        t_item.setTextAlignment(Qt.AlignCenter)
                        t_item.setBackground(QBrush(QColor("#0f8f83")))
                        t_item.setForeground(QBrush(QColor("white")))
                        self.table.setItem(row, idx, t_item)
                        
                    for col_idx in [7, 8]:
                        item = QTableWidgetItem("")
                        item.setBackground(QBrush(QColor("#0f8f83")))
                        self.table.setItem(row, col_idx, item)
                        
                    t_impos = QTableWidgetItem(f"{totals.get('total_impos', 0):.2f}")
                    t_impos.setFont(QFont("", 11, QFont.Bold))
                    t_impos.setTextAlignment(Qt.AlignCenter)
                    t_impos.setBackground(QBrush(QColor("#0f8f83")))
                    t_impos.setForeground(QBrush(QColor("white")))
                    self.table.setItem(row, 9, t_impos)
        except Exception as e:
            pass

    def open_sales_interface(self):
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if hasattr(app, 'current_main_window'):
            app.current_main_window.switch_page(2)
