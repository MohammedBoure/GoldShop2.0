from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QTableWidget, QHeaderView,
    QPushButton, QLineEdit, QGroupBox, QLabel, QFrame,
    QGridLayout, QWidget, QAbstractItemView, QSizePolicy, QCompleter
)
from PySide6.QtCore import Qt, QTimer, QStringListModel, QSize
from PySide6.QtGui import QPalette
import qtawesome as qta
from PySide6.QtWidgets import QScroller

from ui.touch_design import (
    apply_touch_button_defaults,
    apply_touch_input_defaults,
    apply_touch_table_defaults,
)

def _pos_theme_colors(widget):
    palette = widget.palette()
    return {
        "surface": palette.color(QPalette.Base).name(),
        "surface_alt": palette.color(QPalette.AlternateBase).name(),
        "text": palette.color(QPalette.WindowText).name(),
        "muted": palette.color(QPalette.PlaceholderText).name(),
        "border": palette.color(QPalette.Mid).name(),
        "pressed": palette.color(QPalette.Highlight).name(),
    }


class POSUIBuilder:
    """
    Mixin — بناء كامل واجهة نقطة البيع (init_ui).
    تم تحصينه وتنسيقه ليتناسب مع المتطلبات الجديدة (زر دفع واحد، بدون دفعات خارجية).
    """

    def _pos_icon_button(self, icon_name, tooltip, accent, slot=None, *, object_name=""):
        colors = _pos_theme_colors(self)
        button = QPushButton()
        if object_name:
            button.setObjectName(object_name)
        button.setText("")
        button.setIcon(qta.icon(icon_name, color=accent))
        button.setIconSize(QSize(23, 23))
        button.setFixedSize(54, 54)
        button.setToolTip(tooltip)
        button.setAccessibleName(tooltip)
        button.setCursor(Qt.PointingHandCursor)
        apply_touch_button_defaults(button)
        button.setStyleSheet(f"""
            QPushButton {{
                background-color: {colors["surface"]};
                border: 1px solid {colors["border"]};
                border-radius: 10px;
                padding: 0;
            }}
            QPushButton:hover {{
                background-color: {colors["surface_alt"]};
                border: 2px solid {accent};
            }}
            QPushButton:pressed {{
                background-color: {colors["pressed"]};
                border: 2px solid {accent};
            }}
        """)
        if slot is not None:
            button.clicked.connect(slot)
        return button

    def _pos_filled_icon_button(self, icon_name, text, tooltip, bg_color, slot=None, *, object_name="", permission_key=None):
        button = QPushButton(text)
        if object_name:
            button.setObjectName(object_name)
            
        has_permission = getattr(self, "_has_ui_permission", None)
        allowed = True if not permission_key or not callable(has_permission) else bool(has_permission(permission_key))
        
        button.setIcon(qta.icon(icon_name, color="white"))
        button.setIconSize(QSize(28, 28))
        button.setToolTip(tooltip)
        button.setAccessibleName(tooltip)
        if permission_key and not allowed:
            button.setToolTip(f"{tooltip}\nAcces refuse par les permissions.")
        button.setCursor(Qt.PointingHandCursor if allowed else Qt.ArrowCursor)
        apply_touch_button_defaults(button, primary=True)
        button.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg_color};
                color: white;
                font-weight: bold;
                font-size: 16px;
                border: none;
                border-radius: 10px;
                padding: 10px;
            }}
            QPushButton:hover {{
                background-color: {bg_color};
                border: 2px solid rgba(255, 255, 255, 0.35);
            }}
            QPushButton:pressed {{
                background-color: {bg_color};
                border: 2px solid rgba(0, 0, 0, 0.18);
            }}
            QPushButton:disabled {{
                background-color: #7f8c8d;
                color: rgba(255, 255, 255, 0.55);
            }}
        """)
        button.setEnabled(allowed)
        if slot is not None and allowed:
            button.clicked.connect(slot)
        return button

    def init_ui(self):
        # التأكد من تنظيف أي Layout سابق لتجنب التداخل
        if self.layout() is not None:
            QWidget().setLayout(self.layout())
            
        colors = _pos_theme_colors(self)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)

        # ---- Header ----
        header = QFrame()
        header.setObjectName("pos_top_bar")
        header.setStyleSheet(f"""
            QFrame#pos_top_bar {{
                background-color: {colors["surface"]};
                border: 1px solid {colors["border"]};
                border-radius: 10px;
            }}
        """)
        h_lay = QHBoxLayout(header)
        h_lay.setContentsMargins(12, 10, 12, 10)
        h_lay.setSpacing(10)

        session_chip = QFrame()
        session_chip.setObjectName("pos_session_chip")
        session_chip.setFixedHeight(54)
        session_chip.setStyleSheet(f"""
            QFrame#pos_session_chip {{
                background-color: {colors["surface_alt"]};
                border: 1px solid {colors["border"]};
                border-radius: 10px;
            }}
            QLabel {{
                color: {colors["text"]};
                background: transparent;
                border: none;
            }}
        """)
        chip_layout = QHBoxLayout(session_chip)
        chip_layout.setContentsMargins(12, 0, 14, 0)
        chip_layout.setSpacing(8)
        lbl_session_icon = QLabel()
        lbl_session_icon.setPixmap(qta.icon("fa5s.cash-register", color="#0f8f83").pixmap(22, 22))
        lbl_caisse = QLabel(f"Caisse: {self.session_info['location_name']}")
        lbl_caisse.setStyleSheet("font-size: 16px; font-weight: 800;")
        chip_layout.addWidget(lbl_session_icon)
        chip_layout.addWidget(lbl_caisse)
        h_lay.addWidget(session_chip)
        h_lay.addStretch()

        for name, tooltip, icon_name, color, slot in [
            ("refresh", "Actualiser les donnees", "fa5s.sync-alt", "#3498db", getattr(self, "load_inventory_cache", lambda *a: None)),
            ("quick_add", "Ajouter rapidement un article", "fa5s.plus-circle", "#27ae60", getattr(self, "open_quick_add_product", lambda *a: None)),
            ("close", "Fermer l'interface", "fa5s.power-off", "#c0392b", getattr(self, "on_close_session", lambda *a: None)),
        ]:
            h_lay.addWidget(
                POSUIBuilder._pos_icon_button(
                    self, icon_name, tooltip, color, slot, object_name=f"btn_pos_top_{name}"
                )
            )

        main_layout.addWidget(header)

        # ---- Input Row ----
        input_row = QHBoxLayout()
        input_row.setContentsMargins(5, 5, 5, 5)

        # 1. Client Container (مبسط)
        client_container = QWidget()
        client_container.setFixedWidth(320)
        client_vbox = QVBoxLayout(client_container)
        client_vbox.setContentsMargins(0, 0, 0, 0)
        client_vbox.setSpacing(5)

        client_header_lay = QHBoxLayout()
        client_header_lay.setContentsMargins(0, 0, 0, 0)
        lbl_client = QLabel("Client actuel:")
        lbl_client.setStyleSheet("font-size: 16px; font-weight: bold; color: #7f8c8d;")
        self.lbl_client_balance = QLabel("")
        self.lbl_client_balance.setStyleSheet("""
            background-color: #e8f8f5; border: 1px solid #2ecc71; color: #27ae60; 
            font-weight: bold; font-size: 14px; border-radius: 4px; padding: 2px 8px;
        """)
        self.lbl_client_balance.hide() 
        client_header_lay.addWidget(lbl_client)
        client_header_lay.addWidget(self.lbl_client_balance)
        client_header_lay.addStretch()

        self.btn_select_client = QPushButton("Client Passager")
        self.btn_select_client.setIcon(qta.icon("fa5s.user", color="#3498db"))
        self.btn_select_client.setIconSize(QSize(20, 20))
        self.btn_select_client.setFixedHeight(50)
        apply_touch_button_defaults(self.btn_select_client)
        self.btn_select_client.setStyleSheet("""
            QPushButton {
                font-size: 18px; font-weight: bold; color: #2c3e50;
                background-color: white; border: 2px solid #bdc3c7; border-radius: 8px;
                text-align: left; padding-left: 15px;
            }
            QPushButton:hover { border: 2px solid #3498db; background-color: #f1f8ff; }
        """)
        self.btn_select_client.setCursor(Qt.PointingHandCursor)
        self.btn_select_client.clicked.connect(getattr(self, "open_client_selection_dialog", lambda *a: None))

        client_vbox.addLayout(client_header_lay) 
        client_vbox.addWidget(self.btn_select_client)
        input_row.addWidget(client_container, alignment=Qt.AlignTop)
        input_row.addSpacing(20)

        # 2. Barcode Container (مصحح)
        barcode_container = QWidget()
        barcode_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred) 
        barcode_vbox = QVBoxLayout(barcode_container)
        barcode_vbox.setContentsMargins(0, 0, 0, 0)
        barcode_vbox.setSpacing(5)

        lbl_barcode = QLabel("Recherche Article / Code-barres:")
        lbl_barcode.setStyleSheet("font-size: 16px; font-weight: bold; color: #7f8c8d;")
        barcode_vbox.addWidget(lbl_barcode)

        bar_row = QHBoxLayout()
        self.inp_barcode = QLineEdit()
        self.inp_barcode.installEventFilter(self)
        self.inp_barcode.setMinimumWidth(300)
        self.inp_barcode.setFixedHeight(50)
        self.inp_barcode.setPlaceholderText("Scanner ou taper le nom...")
        apply_touch_input_defaults(self.inp_barcode)
        self.inp_barcode.setStyleSheet("""
            QLineEdit { font-size: 18px; font-weight: bold; border: 2px solid #3498db;
                        border-radius: 6px; padding: 0 15px; background-color: white; }
            QLineEdit:focus { background-color: #ebf5fb; border: 2px solid #2980b9; }
        """)

        self.product_completer = QCompleter([])
        self.product_completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.product_completer.setFilterMode(Qt.MatchContains)
        self.product_completer.setCompletionMode(QCompleter.PopupCompletion)
        popup = self.product_completer.popup()
        popup.setMinimumWidth(500)
        popup.setStyleSheet("""
            QListView { font-size: 18px; font-weight: bold; background-color: white;
                        border: 2px solid #3498db; border-radius: 6px; }
            QListView::item { padding: 12px; border-bottom: 1px solid #ecf0f1; }
            QListView::item:selected { background-color: #3498db; color: white; }
        """)
        self.inp_barcode.setCompleter(self.product_completer)
        self.inp_barcode.returnPressed.connect(getattr(self, "on_barcode_entered", lambda *a: None))
        self.inp_barcode.textChanged.connect(getattr(self, "on_text_changed_auto_add", lambda *a: None))
        self.product_completer.activated.connect(getattr(self, "on_completer_activated", lambda *a: None))
        
        bar_row.addWidget(self.inp_barcode)

        btn_manual_code = QPushButton()
        btn_manual_code.setIcon(qta.icon("fa5s.keyboard", color="white"))
        btn_manual_code.setToolTip("Clavier / saisie manuelle du code")
        apply_touch_button_defaults(btn_manual_code)
        btn_manual_code.setFixedSize(60, 50)
        btn_manual_code.setStyleSheet("background-color: #34495e; border-radius: 6px;")
        btn_manual_code.clicked.connect(getattr(self, "open_numpad_for_barcode", lambda *a: None))
        bar_row.addWidget(btn_manual_code)

        self.btn_weight_filter = QPushButton()
        self.btn_weight_filter.setIcon(qta.icon("fa5s.filter", color="white"))
        self.btn_weight_filter.setToolTip("Filtrer par poids")
        apply_touch_button_defaults(self.btn_weight_filter)
        self.btn_weight_filter.setFixedSize(60, 50)
        self.btn_weight_filter.setStyleSheet("background-color: #7f8c8d; border-radius: 6px;")
        self.btn_weight_filter.clicked.connect(getattr(self, "open_weight_filter", lambda *a: None))
        bar_row.addWidget(self.btn_weight_filter)

        self.btn_clear_cart = QPushButton()
        self.btn_clear_cart.setIcon(qta.icon("fa5s.broom", color="white")) 
        apply_touch_button_defaults(self.btn_clear_cart, danger=True)
        self.btn_clear_cart.setFixedSize(60, 50)
        self.btn_clear_cart.setCursor(Qt.PointingHandCursor)
        self.btn_clear_cart.setToolTip("Vider le panier")
        self.btn_clear_cart.setStyleSheet("background-color: #e74c3c; border-radius: 6px;") 
        self.btn_clear_cart.clicked.connect(getattr(self, "clear_cart_with_confirmation", lambda *a: None))
        bar_row.addWidget(self.btn_clear_cart)
        
        barcode_vbox.addLayout(bar_row) # 🟢 السر هنا: إضافة bar_row إلى حاوية الباركود
        input_row.addWidget(barcode_container, alignment=Qt.AlignTop)
        
        main_layout.addLayout(input_row)

        # ---- Cart Table ----
        self.cart_table = QTableWidget(0, 6)
        apply_touch_table_defaults(self.cart_table)
        self.cart_table.setHorizontalHeaderLabels(
            ["Code", "Article", "Dispo.", "À Vendre", "Total", "Act."]
        )
        header = self.cart_table.horizontalHeader()
        for col, mode in [
            (0, QHeaderView.ResizeToContents),
            (1, QHeaderView.Stretch),
            (2, QHeaderView.ResizeToContents),
            (3, QHeaderView.ResizeToContents),
            (4, QHeaderView.ResizeToContents),
            (5, QHeaderView.Fixed),
        ]:
            header.setSectionResizeMode(col, mode)
        self.cart_table.setColumnWidth(5, 70)
        self.cart_table.verticalHeader().setDefaultSectionSize(65)
        self.cart_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.cart_table.setStyleSheet("""
            QTableWidget { font-size: 16px; background-color: white; }
            QHeaderView::section { font-size: 15px; font-weight: bold;
                                   background-color: #f8f9fa; padding: 10px; }
            QTableWidget::item { padding: 10px; }
        """)
        self.cart_table.setFocusPolicy(Qt.NoFocus)
        self.cart_table.setSelectionMode(QTableWidget.NoSelection)
        self.cart_table.setEditTriggers(QTableWidget.NoEditTriggers)
        QScroller.grabGesture(self.cart_table.viewport(), QScroller.TouchGesture)
        self.cart_table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        main_layout.addWidget(self.cart_table, stretch=1)

        # ---- Bottom (Totals + Checkout Button) ----
        payment_bar = QFrame()
        payment_bar.setObjectName("pos_payment_bar")
        payment_bar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        payment_bar.setStyleSheet("QFrame#pos_payment_bar { background-color: transparent; border: none; }")
        self.payment_bottom_frame = payment_bar

        bottom_layout = QHBoxLayout(payment_bar)
        bottom_layout.setContentsMargins(6, 0, 8, 8)
        bottom_layout.setSpacing(8)

        # Totals box
        totals_box = QGroupBox("Facturation")
        self.totals_box = totals_box
        totals_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        totals_box.setStyleSheet(f"""
            QGroupBox {{
                background-color: {colors["surface"]}; color: {colors["text"]};
                font-weight: 800; font-size: 15px; border: none; border-radius: 2px;
                margin-top: 4px; padding-top: 6px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin; left: 12px; padding: 0 6px; top: -7px;
                color: {colors["muted"]}; background: transparent;
            }}
            QGroupBox QLabel {{ background: transparent; border: none; }}
        """)
        t_lay = QGridLayout(totals_box)
        t_lay.setContentsMargins(18, 14, 18, 12)
        t_lay.setVerticalSpacing(8)
        t_lay.setHorizontalSpacing(18)

        self.lbl_total_weight         = QLabel("0.00 g")
        self.lbl_total_raw            = QLabel("0.00 DA")
        self.lbl_avg_price_per_gram   = QLabel("0.00 DA/g")
        self.lbl_total_weight.setStyleSheet("font-size: 15px; font-weight: bold; color: #8e44ad;")
        self.lbl_total_raw.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {colors['text']};")
        self.lbl_avg_price_per_gram.setStyleSheet("font-size: 14px; font-weight: bold; color: #16a085;")
        
        t_lay.addWidget(QLabel("Poids Total:"),    0, 0)
        t_lay.addWidget(self.lbl_total_weight,     0, 1)
        t_lay.addWidget(QLabel("Total Brut:"),     1, 0)
        t_lay.addWidget(self.lbl_total_raw,        1, 1)
        t_lay.addWidget(QLabel("Moyenne (Prix/g):"), 2, 0)
        t_lay.addWidget(self.lbl_avg_price_per_gram, 2, 1)

        lbl_ajustements = QLabel("Ajustements:")
        lbl_ajustements.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {colors['muted']};")
        edit_buttons_layout = QHBoxLayout()
        edit_buttons_layout.setContentsMargins(0, 0, 0, 0)
        edit_buttons_layout.setSpacing(8)

        def adjustment_button_style(accent):
            return f"""
                QPushButton {{
                    background-color: {colors["surface_alt"]}; border: none;
                    border-left: 3px solid {accent}; border-radius: 4px;
                    font-size: 14px; font-weight: 800; color: {accent}; padding: 0 12px;
                }}
                QPushButton:hover {{ background-color: {colors["surface"]}; }}
                QPushButton:pressed {{ background-color: {colors["pressed"]}; }}
            """

        self.btn_discount_pct = QPushButton("Remise: 0.00 %")
        apply_touch_button_defaults(self.btn_discount_pct)
        self.btn_discount_pct.setCursor(Qt.PointingHandCursor)
        self.btn_discount_pct.setFixedHeight(48)
        self.btn_discount_pct.setStyleSheet(adjustment_button_style("#e67e22"))
        self.btn_discount_pct.clicked.connect(getattr(self, "open_numpad_for_discount_pct", lambda *a: None))

        self.btn_price_per_gram = QPushButton("Prix/g: 0.00 DA")
        apply_touch_button_defaults(self.btn_price_per_gram)
        self.btn_price_per_gram.setCursor(Qt.PointingHandCursor)
        self.btn_price_per_gram.setFixedHeight(48)
        self.btn_price_per_gram.setStyleSheet(adjustment_button_style("#8e44ad"))
        self.btn_price_per_gram.clicked.connect(getattr(self, "open_numpad_for_price_per_gram", lambda *a: None))

        self.btn_discount_value = QPushButton("Final: 0.00 DA")
        apply_touch_button_defaults(self.btn_discount_value)
        self.btn_discount_value.setCursor(Qt.PointingHandCursor)
        self.btn_discount_value.setFixedHeight(48)
        self.btn_discount_value.setStyleSheet(adjustment_button_style("#2980b9"))
        self.btn_discount_value.clicked.connect(getattr(self, "open_numpad_for_final_price", lambda *a: None))

        edit_buttons_layout.addWidget(self.btn_discount_pct)
        edit_buttons_layout.addWidget(self.btn_price_per_gram)
        edit_buttons_layout.addWidget(self.btn_discount_value)

        net_container = QWidget()
        net_lay = QHBoxLayout(net_container)
        net_lay.setContentsMargins(0, 0, 0, 0)

        self.lbl_discount_amount_display = QLabel("(- 0.00 DA)")
        self.lbl_discount_amount_display.setStyleSheet("font-size: 14px; font-weight: bold; color: #e74c3c;")
        self.lbl_net_to_pay = QLabel("0.00 DA")
        self.lbl_net_to_pay.setStyleSheet("font-size: 26px; font-weight: 900; color: #c0392b;")
        self.lbl_net_to_pay.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        net_lay.addWidget(self.lbl_discount_amount_display)
        net_lay.addStretch()
        net_lay.addWidget(self.lbl_net_to_pay)

        t_lay.addWidget(lbl_ajustements,       0, 2)
        t_lay.addLayout(edit_buttons_layout,   0, 3)
        t_lay.addWidget(QLabel("NET À PAYER:"), 1, 2, 2, 1)
        t_lay.addWidget(net_container,          1, 3, 2, 1)

        # Checkout Action Section (زر دفع واحد فقط)
        actions_frame = QFrame()
        actions_frame.setObjectName("pos_payment_actions")
        actions_frame.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        actions_frame.setStyleSheet(f"QFrame#pos_payment_actions {{ background-color: {colors['surface']}; border: none; border-radius: 3px; }}")
        self.payment_actions_frame = actions_frame
        
        actions_layout = QVBoxLayout(actions_frame)
        actions_layout.setContentsMargins(15, 15, 15, 15)
        actions_layout.setSpacing(10)

        self.btn_direct_checkout = self._pos_filled_icon_button(
            "fa5s.check-circle",
            " Valider et Encaisser",
            "Procéder à l'encaissement",
            "#27ae60",
            getattr(self, "quick_checkout_dzd", lambda *a: None),
            object_name="btn_pos_quick_checkout",
        )
        self.btn_direct_checkout.setFixedSize(220, 80)
        self.btn_direct_checkout.setStyleSheet("""
            QPushButton {
                background-color: #27ae60; color: white; border: none; border-radius: 8px;
                font-size: 18px; font-weight: bold;
            }
            QPushButton:hover { background-color: #2ecc71; }
            QPushButton:pressed { background-color: #1e8449; }
        """)

        actions_layout.addWidget(self.btn_direct_checkout, alignment=Qt.AlignCenter)
        actions_frame.setFixedSize(250, 110)

        bottom_layout.addWidget(totals_box, stretch=1)
        bottom_layout.addWidget(actions_frame, stretch=0, alignment=Qt.AlignVCenter)
        main_layout.addWidget(payment_bar)

        self.inp_barcode.setFocus()
        if hasattr(self, "load_inventory_cache"):
            QTimer.singleShot(0, self.load_inventory_cache)