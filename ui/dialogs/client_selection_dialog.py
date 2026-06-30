# ui/dialogs/client_selection_dialog.py

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit,
    QLabel, QTableWidget, QTableWidgetItem, QHeaderView, QStackedWidget,
    QWidget, QFormLayout, QMessageBox, QFrame, QApplication
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QColor
import qtawesome as qta

from ui.tools.virtual_keyboard import VirtualKeyboardDialog

class ClientSelectionDialog(QDialog):
    def __init__(self, manager, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.selected_client_id = None
        self.vkb = None

        # --- Lazy Loading Variables ---
        self.current_offset = 0
        self.page_limit = 50
        self.is_loading = False
        self.has_more_data = True

        # --- Search Timer (Debounce) ---
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(400)
        self.search_timer.timeout.connect(lambda: self.load_clients(reset=True))

        self.setWindowTitle("Sélection du Client")
        self.setFixedSize(800, 550)
        self.setStyleSheet("QDialog { background-color: #f8f9fa; }")

        self.init_ui()
        self.load_clients(reset=True)

    def showEvent(self, event):
        super().showEvent(event)
        screen_geom = QApplication.primaryScreen().availableGeometry()
        x = (screen_geom.width() - self.width()) // 2
        y = 0
        self.move(x, y)

    def show_virtual_keyboard(self):
        if not self.vkb:
            self.vkb = VirtualKeyboardDialog(self)
        self.vkb.show()
        self.vkb.raise_()

    def close_keyboard(self):
        if self.vkb and self.vkb.isVisible():
            self.vkb.close()

    def accept(self):
        self.close_keyboard()
        super().accept()

    def reject(self):
        self.close_keyboard()
        super().reject()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        self.stack = QStackedWidget()
        main_layout.addWidget(self.stack)

        # ==========================================
        # Page 1: Client List
        # ==========================================
        page_list = QWidget()
        list_layout = QVBoxLayout(page_list)

        top_bar = QHBoxLayout()

        self.inp_search = QLineEdit()
        self.inp_search.setPlaceholderText("🔍 Rechercher par nom ou téléphone...")
        self.inp_search.setFixedHeight(50)
        self.inp_search.setStyleSheet("font-size: 18px; padding: 10px; border: 2px solid #bdc3c7; border-radius: 8px;")

        self.inp_search.textChanged.connect(self.on_search_text_changed)

        btn_kb_search = QPushButton("⌨️")
        btn_kb_search.setFixedHeight(50)
        btn_kb_search.setFixedWidth(60)
        btn_kb_search.setStyleSheet("background-color: #34495e; color: white; font-size: 24px; border-radius: 8px;")
        btn_kb_search.clicked.connect(self.show_virtual_keyboard)

        btn_add_new = QPushButton(" Nouveau Client")
        btn_add_new.setIcon(qta.icon("fa5s.user-plus", color="white"))
        btn_add_new.setFixedHeight(50)
        btn_add_new.setStyleSheet("background-color: #2980b9; color: white; font-weight: bold; font-size: 16px; padding: 0 20px; border-radius: 8px;")
        btn_add_new.clicked.connect(lambda: self.stack.setCurrentIndex(1))

        top_bar.addWidget(self.inp_search)
        top_bar.addWidget(btn_kb_search)
        top_bar.addWidget(btn_add_new)
        list_layout.addLayout(top_bar)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Client", "Téléphone", "Action"])

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Fixed)
        self.table.setColumnWidth(2, 120)

        self.table.verticalHeader().setDefaultSectionSize(70)
        self.table.verticalHeader().setVisible(False)
        self.table.setFocusPolicy(Qt.NoFocus)
        self.table.setSelectionMode(QTableWidget.NoSelection)
        self.table.setStyleSheet("""
            QTableWidget { background-color: white; border: 1px solid #dcdde1; border-radius: 8px; font-size: 16px; }
            QHeaderView::section { font-weight: bold; background-color: #ecf0f1; padding: 10px; font-size: 15px; }
        """)

        self.table.verticalScrollBar().valueChanged.connect(self.on_table_scroll)
        list_layout.addWidget(self.table)

        btn_cancel_list = QPushButton("Annuler (Fermer)")
        btn_cancel_list.setFixedHeight(50)
        btn_cancel_list.setStyleSheet("background-color: #95a5a6; color: white; font-weight: bold; font-size: 16px; border-radius: 8px;")
        btn_cancel_list.clicked.connect(self.reject)
        list_layout.addWidget(btn_cancel_list)

        self.stack.addWidget(page_list)

        # ==========================================
        # Page 2: Add New Client
        # ==========================================
        page_add = QWidget()
        add_layout = QVBoxLayout(page_add)

        lbl_title = QLabel("📝 Créer un Nouveau Client")
        lbl_title.setStyleSheet("font-size: 22px; font-weight: bold; color: #2c3e50;")
        add_layout.addWidget(lbl_title)

        form_frame = QFrame()
        form_frame.setStyleSheet("background-color: white; border-radius: 8px; padding: 20px;")
        form = QFormLayout(form_frame)
        form.setVerticalSpacing(20)

        input_style = "font-size: 18px; padding: 10px; border: 2px solid #bdc3c7; border-radius: 8px;"

        self.inp_new_name = QLineEdit()
        self.inp_new_name.setFixedHeight(50)
        self.inp_new_name.setStyleSheet(input_style)

        self.inp_new_phone = QLineEdit()
        self.inp_new_phone.setFixedHeight(50)
        self.inp_new_phone.setStyleSheet(input_style)

        self.inp_new_address = QLineEdit()
        self.inp_new_address.setFixedHeight(50)
        self.inp_new_address.setStyleSheet(input_style)

        lbl_style = "font-size: 16px; font-weight: bold;"
        lbl_n = QLabel("Nom Complet (*):"); lbl_n.setStyleSheet(lbl_style)
        lbl_p = QLabel("Téléphone :"); lbl_p.setStyleSheet(lbl_style)
        lbl_a = QLabel("Adresse :"); lbl_a.setStyleSheet(lbl_style)

        form.addRow(lbl_n, self.inp_new_name)
        form.addRow(lbl_p, self.inp_new_phone)
        form.addRow(lbl_a, self.inp_new_address)

        add_layout.addWidget(form_frame)
        add_layout.addStretch()

        bottom_add = QHBoxLayout()
        btn_cancel_add = QPushButton("Retour")
        btn_cancel_add.setFixedHeight(60)
        btn_cancel_add.setStyleSheet("background-color: #95a5a6; color: white; font-weight: bold; font-size: 18px; border-radius: 8px;")
        btn_cancel_add.clicked.connect(lambda: self.stack.setCurrentIndex(0))

        btn_kb_add = QPushButton("⌨️ Clavier")
        btn_kb_add.setFixedHeight(60)
        btn_kb_add.setStyleSheet("background-color: #34495e; color: white; font-weight: bold; font-size: 18px; border-radius: 8px;")
        btn_kb_add.clicked.connect(self.show_virtual_keyboard)

        btn_save_client = QPushButton("✔ Enregistrer le Client")
        btn_save_client.setFixedHeight(60)
        btn_save_client.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; font-size: 18px; border-radius: 8px;")
        btn_save_client.clicked.connect(self.save_new_client)

        bottom_add.addWidget(btn_cancel_add)
        bottom_add.addWidget(btn_kb_add)
        bottom_add.addWidget(btn_save_client)
        add_layout.addLayout(bottom_add)

        self.stack.addWidget(page_add)

    def on_search_text_changed(self, text):
        self.search_timer.start()

    def on_table_scroll(self, value):
        scroll_bar = self.table.verticalScrollBar()
        if value == scroll_bar.maximum() and self.has_more_data and not self.is_loading:
            self.load_clients(reset=False)

    def load_clients(self, reset=False):
        if reset:
            self.current_offset = 0
            self.has_more_data = True
            self.table.setRowCount(0)

        if not self.has_more_data or self.is_loading:
            return

        self.is_loading = True
        search_text = self.inp_search.text().strip()

        try:
            new_clients = self.manager.customers.get_clients_paginated(
                search_text=search_text,
                limit=self.page_limit,
                offset=self.current_offset
            )

            if not new_clients:
                self.has_more_data = False
            else:
                self.append_to_table(new_clients)
                self.current_offset += self.page_limit

                if len(new_clients) < self.page_limit:
                    self.has_more_data = False

        except Exception as e:
            print(f"Loading error: {e}")
        finally:
            self.is_loading = False

    def append_to_table(self, data):
        start_row = self.table.rowCount()

        for i, c in enumerate(data):
            row = start_row + i
            self.table.insertRow(row)

            it_name = QTableWidgetItem(str(c['name']))
            it_name.setFont(QFont("", 12, QFont.Bold))
            self.table.setItem(row, 0, it_name)

            it_phone = QTableWidgetItem(str(c.get('phone') or '-'))
            it_phone.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 1, it_phone)

            btn_select = QPushButton("Choisir")
            btn_select.setCursor(Qt.PointingHandCursor)
            btn_select.setStyleSheet("""
                QPushButton { background-color: #27ae60; color: white; font-weight: bold; border-radius: 6px; font-size: 15px; }
                QPushButton:pressed { background-color: #2ecc71; }
            """)
            btn_select.clicked.connect(lambda checked, cid=c['id']: self.select_client(cid))

            btn_container = QWidget()
            btn_lay = QHBoxLayout(btn_container)
            btn_lay.setContentsMargins(10, 10, 10, 10)
            btn_lay.addWidget(btn_select)

            self.table.setCellWidget(row, 2, btn_container)

    def select_client(self, client_id):
        self.selected_client_id = client_id
        self.accept()

    def save_new_client(self):
        name = self.inp_new_name.text().strip()
        phone = self.inp_new_phone.text().strip()
        address = self.inp_new_address.text().strip()

        if not name:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Erreur", "Le nom du client est obligatoire.")
            return

        # 🟢 استخدام add_customer المتوافقة مع CustomerManager
        new_id = self.manager.customers.add_customer(name=name, phone=phone, address=address)
        if new_id:
            self.selected_client_id = new_id
            self.accept()
        else:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Erreur", "Échec de la création du client.")