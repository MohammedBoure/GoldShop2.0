import calendar
from datetime import date, datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QLabel, QFrame, QStyledItemDelegate,
    QMessageBox, QLineEdit, QApplication
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QBrush, QPalette
import qtawesome as qta


class ColorOverrideDelegate(QStyledItemDelegate):
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


class MonthlySummaryView(QWidget):
    """
    Interface de suivi et de synthèse mensuelle des recettes et bénéfices.
    Protégée par mot de passe administrateur avec session persistante lors de la navigation
    et bouton explicite de déconnexion.
    """
    # État de session partagé au niveau applicatif pour persister lors de la navigation
    _session_authenticated = False

    def __init__(self, manager, current_user=None):
        super().__init__()
        self.manager = manager
        self.current_user = current_user or {}
        self._is_authenticated = MonthlySummaryView._session_authenticated
        self._is_prompting = False

        self.init_ui()
        self.populate_filters()
        self._update_auth_ui_state()

    def showEvent(self, event):
        super().showEvent(event)
        # Vérification si la session globale est déjà déverrouillée
        if not self._is_authenticated and MonthlySummaryView._session_authenticated:
            self._is_authenticated = True

        if not self._is_authenticated:
            if not self._is_prompting:
                self._is_prompting = True
                try:
                    if self._prompt_admin_password():
                        self.load_data()
                    else:
                        self._render_locked_state()
                finally:
                    self._is_prompting = False
                    self._update_auth_ui_state()
        else:
            self._update_auth_ui_state()
            if self.table.rowCount() == 0:
                self.load_data()

    def hideEvent(self, event):
        super().hideEvent(event)
        # 🟢 Important : La session reste active lors de la navigation dans les onglets/pages.
        # La déconnexion ne se fait que si l'utilisateur clique volontairement sur le bouton de déconnexion.

    def _get_current_user(self):
        if hasattr(self, 'current_user') and self.current_user:
            return self.current_user

        app = QApplication.instance()
        if app:
            main_win = getattr(app, 'current_main_window', None)
            if not main_win and hasattr(app, 'activeWindow'):
                main_win = app.activeWindow()
            if main_win and hasattr(main_win, 'current_user'):
                return main_win.current_user

        if hasattr(self.manager, 'current_user'):
            return self.manager.current_user

        return {}

    def _prompt_admin_password(self):
        user = self._get_current_user()
        username = user.get('username') if user else None

        if username:
            prompt_label = f"Veuillez entrer le mot de passe de l'administrateur ({username}) :"
        else:
            prompt_label = "Veuillez entrer le mot de passe Administrateur :"

        from ui.tools.virtual_keyboard import VirtualPasswordInputDialog
        # 🟢 auto_open_keyboard=False : ouverture normale sans forcer le clavier virtuel tactile
        pwd, ok = VirtualPasswordInputDialog.getText(
            self,
            "Protection Administrateur",
            prompt_label,
            QLineEdit.Password,
            auto_open_keyboard=False
        )

        if not ok or not pwd:
            return False

        is_valid = False
        if username and hasattr(self.manager, 'users') and hasattr(self.manager.users, 'authenticate'):
            try:
                auth_res = self.manager.users.authenticate(username, pwd)
                if auth_res:
                    is_valid = True
            except Exception:
                pass

        if not is_valid and hasattr(self.manager, 'users') and hasattr(self.manager.users, 'verify_admin_password'):
            try:
                if self.manager.users.verify_admin_password(pwd):
                    is_valid = True
            except Exception:
                pass

        if is_valid:
            self._is_authenticated = True
            MonthlySummaryView._session_authenticated = True
            self._update_auth_ui_state()
            return True
        else:
            QMessageBox.warning(self, "Accès Refusé", "Mot de passe Administrateur incorrect.")
            self._is_authenticated = False
            MonthlySummaryView._session_authenticated = False
            self._update_auth_ui_state()
            return False

    def lock_session(self):
        """Verrouille manuellement la session administrateur."""
        self._is_authenticated = False
        MonthlySummaryView._session_authenticated = False
        self._render_locked_state()
        self._update_auth_ui_state()
        QMessageBox.information(self, "Session Verrouillée", "La session administrateur du résumé mensuel a été verrouillée.")

    def _on_unlock_clicked(self):
        """Déclenche la demande de mot de passe lors d'un clic explicite sur Déverrouiller."""
        if self._prompt_admin_password():
            self.load_data()

    def _render_locked_state(self):
        """Affiche un état verrouillé clair dans le tableau."""
        self.table.clearSpans()
        self.table.setRowCount(1)
        item = QTableWidgetItem("🔒 Accès Administrateur requis — Cliquez sur 'Déverrouiller' pour afficher le résumé mensuel.")
        item.setTextAlignment(Qt.AlignCenter)
        item.setFont(QFont("", 13, QFont.Bold))
        item.setForeground(QBrush(QColor("#64748b")))
        self.table.setItem(0, 0, item)
        for i in range(1, self.table.columnCount()):
            self.table.setItem(0, i, QTableWidgetItem(""))
        self.table.setSpan(0, 0, 1, self.table.columnCount())

    def _update_auth_ui_state(self):
        """Met à jour l'apparence des contrôles et des boutons selon l'état d'authentification."""
        if self._is_authenticated:
            self.btn_unlock.setVisible(False)
            self.btn_logout.setVisible(True)
            self.lbl_session_status.setText("🟢 Session Admin active")
            self.lbl_session_status.setStyleSheet("""
                color: #0f8f83;
                font-weight: bold;
                font-size: 12px;
                padding: 5px 10px;
                background-color: #e8f7f4;
                border-radius: 6px;
                border: 1px solid #bfe7df;
            """)
            self.lbl_session_status.setVisible(True)
            self.btn_search.setEnabled(True)
            self.combo_year.setEnabled(True)
            self.combo_month.setEnabled(True)
        else:
            self.btn_unlock.setVisible(True)
            self.btn_logout.setVisible(False)
            self.lbl_session_status.setText("🔒 Session verrouillée")
            self.lbl_session_status.setStyleSheet("""
                color: #be3528;
                font-weight: bold;
                font-size: 12px;
                padding: 5px 10px;
                background-color: #fff5f3;
                border-radius: 6px;
                border: 1px solid #f9d2ce;
            """)
            self.lbl_session_status.setVisible(True)
            self.btn_search.setEnabled(False)

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # --- شريط الفلاتر العلوي وأزرار التحكم بالوصول ---
        filter_frame = QFrame()
        filter_frame.setObjectName("panel")
        filter_frame.setStyleSheet("""
            QFrame#panel {
                background-color: #ffffff;
                border: 1px solid #d9e0e7;
                border-radius: 8px;
                padding: 6px 12px;
            }
            QLabel {
                font-size: 13px;
                font-weight: bold;
                color: #24313f;
            }
            QComboBox {
                font-size: 13px;
                font-weight: bold;
                padding: 5px 10px;
                border: 1px solid #cbd5df;
                border-radius: 6px;
                background-color: #ffffff;
                min-width: 140px;
            }
            QComboBox:focus {
                border: 2px solid #0f8f83;
            }
        """)
        row1 = QHBoxLayout(filter_frame)
        row1.setContentsMargins(8, 6, 8, 6)
        row1.setSpacing(10)

        row1.addWidget(QLabel("📅 Année :"))
        self.combo_year = QComboBox()
        self.combo_year.currentIndexChanged.connect(self._on_filter_changed)
        row1.addWidget(self.combo_year)

        row1.addSpacing(10)
        row1.addWidget(QLabel("Mois :"))
        self.combo_month = QComboBox()
        self.combo_month.currentIndexChanged.connect(self._on_filter_changed)
        row1.addWidget(self.combo_month)

        row1.addSpacing(15)
        self.btn_search = QPushButton(" Afficher le Tableau")
        self.btn_search.setIcon(qta.icon("fa5s.calendar-alt", color="white"))
        self.btn_search.setStyleSheet("""
            QPushButton {
                background-color: #0f8f83;
                color: white;
                padding: 6px 15px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 13px;
                border: none;
            }
            QPushButton:hover {
                background-color: #0a7c72;
            }
        """)
        self.btn_search.setCursor(Qt.PointingHandCursor)
        self.btn_search.clicked.connect(self.load_data)
        row1.addWidget(self.btn_search)

        row1.addStretch()

        # Badge de statut de session
        self.lbl_session_status = QLabel("")
        row1.addWidget(self.lbl_session_status)

        # Bouton Déverrouiller (quand verrouillé)
        self.btn_unlock = QPushButton(" Déverrouiller")
        self.btn_unlock.setIcon(qta.icon("fa5s.unlock-alt", color="white"))
        self.btn_unlock.setCursor(Qt.PointingHandCursor)
        self.btn_unlock.setStyleSheet("""
            QPushButton {
                background-color: #0f8f83;
                color: white;
                font-weight: bold;
                font-size: 13px;
                padding: 6px 14px;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover {
                background-color: #0a7c72;
            }
        """)
        self.btn_unlock.clicked.connect(self._on_unlock_clicked)
        row1.addWidget(self.btn_unlock)

        # Bouton Déconnexion / Verrouiller (quand connecté)
        self.btn_logout = QPushButton(" Déconnexion")
        self.btn_logout.setIcon(qta.icon("fa5s.sign-out-alt", color="#be3528"))
        self.btn_logout.setToolTip("Verrouiller la session administrateur du résumé mensuel")
        self.btn_logout.setCursor(Qt.PointingHandCursor)
        self.btn_logout.setStyleSheet("""
            QPushButton {
                background-color: #fff5f3;
                border: 1px solid #e66f61;
                color: #be3528;
                font-weight: bold;
                font-size: 13px;
                padding: 6px 14px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #d94d3f;
                color: white;
            }
        """)
        self.btn_logout.clicked.connect(self.lock_session)
        row1.addWidget(self.btn_logout)

        layout.addWidget(filter_frame)

        # --- عنوان الصفحة ---
        self.lbl_main_title = QLabel("RÉSUMÉ MENSUEL DES RECETTES")
        self.lbl_main_title.setStyleSheet("""
            font-size: 19px;
            font-weight: 900;
            color: white;
            background-color: #0f8f83;
            padding: 10px 16px;
            border-radius: 6px;
            letter-spacing: 1px;
        """)
        self.lbl_main_title.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_main_title)

        # --- إعداد الجدول ---
        self.table = QTableWidget(0, 12)
        self.table.setItemDelegate(ColorOverrideDelegate(self.table))
        self.table.setHorizontalHeaderLabels([
            "Jours", "Dates", "P.S (Or)", "P.S (Argent)", "Recettes DA", "O.C (Or)", "O.C (Argent)", "TPE", "Euro", "Dollar", "Vendeur", "Bénéfice (Faaida)"
        ])

        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #ffffff;
                gridline-color: #eef2f6;
                border: 1px solid #cbd5df;
                border-radius: 6px;
                selection-background-color: #dff5f1;
                selection-color: #17202a;
                font-size: 13px;
            }
            QHeaderView::section {
                background-color: #0f8f83;
                color: white;
                font-weight: bold;
                font-size: 13px;
                padding: 7px 6px;
                border: 1px solid #0b776d;
            }
            QTableWidget::item {
                padding: 5px 8px;
            }
            QTableWidget::item:selected {
                background-color: #dff5f1;
                color: #17202a;
            }
        """)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)

        header = self.table.horizontalHeader()
        for i in range(self.table.columnCount()):
            header.setSectionResizeMode(i, QHeaderView.Stretch if i in [4, 11] else QHeaderView.ResizeToContents)

        layout.addWidget(self.table)

    def _on_filter_changed(self):
        """Recharge automatiquement les données lors du changement de mois ou d'année si authentifié."""
        if self._is_authenticated:
            self.load_data()

    def populate_filters(self):
        current_date = datetime.now()
        for y in range(current_date.year - 2, current_date.year + 3):
            self.combo_year.addItem(str(y), y)
        self.combo_year.setCurrentText(str(current_date.year))

        months = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin", "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"]
        for i, m in enumerate(months, 1):
            self.combo_month.addItem(m, i)
        self.combo_month.setCurrentIndex(current_date.month - 1)

    def get_french_day(self, date_obj):
        days = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
        return days[date_obj.weekday()]

    def load_data(self):
        if not self._is_authenticated:
            if not self._prompt_admin_password():
                self._render_locked_state()
                return

        self.table.clearSpans()
        self.table.setRowCount(0)
        year = self.combo_year.currentData()
        month = self.combo_month.currentData()
        month_name = self.combo_month.currentText()

        self.lbl_main_title.setText(f"RÉSUMÉ MENSUEL DES RECETTES — {month_name.upper()} {year}")

        def to_date_key(val):
            if not val:
                return None
            if isinstance(val, datetime):
                return val.date()
            if isinstance(val, date):
                return val
            if isinstance(val, str):
                try:
                    return datetime.strptime(val.split()[0], "%Y-%m-%d").date()
                except Exception:
                    pass
            return None

        try:
            with self.manager.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)

                # 1. جلب أوزان المبيعات الخارجة (P.S Or & P.S Argent)
                cursor.execute("""
                    SELECT 
                        DATE(s.created_at) as sale_date,
                        SUM(CASE WHEN COALESCE(si.metal_category, mt.metal_category, 'GOLD') = 'GOLD' THEN si.sold_weight_g ELSE 0 END) as total_ps_gold,
                        SUM(CASE WHEN COALESCE(si.metal_category, mt.metal_category, 'GOLD') = 'SILVER' THEN si.sold_weight_g ELSE 0 END) as total_ps_silver
                    FROM SaleItems si
                    JOIN Sales s ON si.sale_id = s.id
                    LEFT JOIN Inventory i ON si.inventory_id = i.id
                    LEFT JOIN MetalTypes mt ON COALESCE(si.metal_type_id, i.metal_type_id) = mt.id
                    WHERE YEAR(s.created_at) = %s AND MONTH(s.created_at) = %s AND s.status = 'COMPLETED'
                    GROUP BY DATE(s.created_at)
                """, (year, month))
                weight_results = cursor.fetchall()
                while cursor.nextset() is True: pass
                weights_by_date = {to_date_key(r['sale_date']): r for r in weight_results if to_date_key(r.get('sale_date'))}

                # 2. جلب مبالغ المبيعات (Recette, TPE, OC Gold, OC Silver, Euro, Dollar)
                cursor.execute("""
                    SELECT 
                        DATE(s.created_at) as sale_date,
                        SUM(CASE WHEN s.receipt_number NOT LIKE 'VRS-%' THEN s.cash_paid_da ELSE 0 END) as total_recette,
                        SUM(CASE WHEN s.receipt_number NOT LIKE 'VRS-%' THEN s.old_gold_weight_g ELSE 0 END) as total_oc_gold,
                        SUM(CASE WHEN s.receipt_number NOT LIKE 'VRS-%' THEN COALESCE(s.old_silver_weight_g, 0) ELSE 0 END) as total_oc_silver,
                        SUM(CASE WHEN s.receipt_number NOT LIKE 'VRS-%' THEN s.tpe_paid_da ELSE 0 END) as total_tpe,
                        SUM(CASE WHEN s.receipt_number NOT LIKE 'VRS-%' THEN s.euro_paid ELSE 0 END) as total_euro,
                        SUM(CASE WHEN s.receipt_number NOT LIKE 'VRS-%' THEN s.dollar_paid ELSE 0 END) as total_dollar
                    FROM Sales s
                    WHERE YEAR(s.created_at) = %s AND MONTH(s.created_at) = %s AND s.status = 'COMPLETED'
                    GROUP BY DATE(s.created_at)
                """, (year, month))
                sales_results = cursor.fetchall()
                while cursor.nextset() is True: pass
                sales_by_date = {to_date_key(r['sale_date']): r for r in sales_results if to_date_key(r.get('sale_date'))}

                # 3. جلب دفعات وتأكيدات العربون (Versement Payments)
                cursor.execute("""
                    SELECT 
                        DATE(vp.payment_date) as pay_date,
                        SUM(vp.montant_da) as total_vp_recette,
                        SUM(vp.tpe_da) as total_vp_tpe,
                        SUM(vp.montant_euro) as total_vp_euro,
                        SUM(vp.montant_dollar) as total_vp_dollar,
                        SUM(vp.or_casse_g) as total_vp_oc_gold,
                        SUM(COALESCE(vp.argent_casse_g, 0)) as total_vp_oc_silver
                    FROM Versement_Payments vp
                    JOIN Versements v ON vp.versement_id = v.id
                    WHERE YEAR(vp.payment_date) = %s AND MONTH(vp.payment_date) = %s AND v.status != 'ANNULE'
                    GROUP BY DATE(vp.payment_date)
                """, (year, month))
                vp_results = cursor.fetchall()
                while cursor.nextset() is True: pass
                vp_by_date = {to_date_key(r['pay_date']): r for r in vp_results if to_date_key(r.get('pay_date'))}

                # 4. جلب عمليات ودفعات وأرباح الورشة والتصليحات (ArtisanWorkOrders)
                cursor.execute("""
                    SELECT 
                        DATE(awo.date_remis) as awo_date,
                        SUM(COALESCE(awo.pay_cash_da, 0.0)) as total_awo_recette,
                        SUM(COALESCE(awo.pay_tpe_da, 0.0)) as total_awo_tpe,
                        SUM(COALESCE(awo.pay_oc_g, 0.0)) as total_awo_oc_gold,
                        SUM(COALESCE(awo.pay_oc_silver_g, 0.0)) as total_awo_oc_silver,
                        SUM(COALESCE(awo.diff, 0.0)) as total_awo_benefice
                    FROM ArtisanWorkOrders awo
                    WHERE YEAR(awo.date_remis) = %s AND MONTH(awo.date_remis) = %s
                      AND (
                          COALESCE(awo.pay_cash_da, 0) != 0 
                          OR COALESCE(awo.pay_tpe_da, 0) != 0 
                          OR COALESCE(awo.pay_oc_g, 0) != 0
                          OR COALESCE(awo.pay_oc_silver_g, 0) != 0
                          OR COALESCE(awo.diff, 0) != 0
                      )
                    GROUP BY DATE(awo.date_remis)
                """, (year, month))
                awo_results = cursor.fetchall()
                while cursor.nextset() is True: pass
                awo_by_date = {to_date_key(r['awo_date']): r for r in awo_results if to_date_key(r.get('awo_date'))}

                # 5. حساب الأرباح الصافية (Bénéfice / Faaida) لكل يوم
                raw_profit_dict = getattr(self.manager.sales, 'get_monthly_profit_by_day', lambda *_: {})(year, month)
                profit_by_date = {to_date_key(k): v for k, v in raw_profit_dict.items() if to_date_key(k)}

                num_days = calendar.monthrange(year, month)[1]
                sum_ps_gold = sum_ps_silver = sum_recettes = sum_oc_gold = sum_oc_silver = sum_tpe = sum_euro = sum_dollar = sum_benefice = 0.0

                for day in range(1, num_days + 1):
                    current_date = date(year, month, day)
                    day_name = self.get_french_day(current_date)
                    date_str = f"{day:02d}/{month:02d}/{year}"

                    row_idx = self.table.rowCount()
                    self.table.insertRow(row_idx)

                    item_day = QTableWidgetItem(day_name)
                    item_day.setTextAlignment(Qt.AlignCenter)
                    self.table.setItem(row_idx, 0, item_day)

                    item_date = QTableWidgetItem(date_str)
                    item_date.setTextAlignment(Qt.AlignCenter)
                    self.table.setItem(row_idx, 1, item_date)

                    has_data = (
                        current_date in weights_by_date or 
                        current_date in sales_by_date or 
                        current_date in vp_by_date or 
                        current_date in awo_by_date or 
                        current_date in profit_by_date
                    )

                    if has_data:
                        w_data = weights_by_date.get(current_date, {})
                        s_data = sales_by_date.get(current_date, {})
                        vp_data = vp_by_date.get(current_date, {})
                        awo_data = awo_by_date.get(current_date, {})

                        ps_gold = float(w_data.get('total_ps_gold') or 0)
                        ps_silver = float(w_data.get('total_ps_silver') or 0)
                        recette = float(s_data.get('total_recette') or 0) + float(vp_data.get('total_vp_recette') or 0) + float(awo_data.get('total_awo_recette') or 0)
                        oc_gold = float(s_data.get('total_oc_gold') or 0) + float(vp_data.get('total_vp_oc_gold') or 0) + float(awo_data.get('total_awo_oc_gold') or 0)
                        oc_silver = float(s_data.get('total_oc_silver') or 0) + float(vp_data.get('total_vp_oc_silver') or 0) + float(awo_data.get('total_awo_oc_silver') or 0)
                        tpe = float(s_data.get('total_tpe') or 0) + float(vp_data.get('total_vp_tpe') or 0) + float(awo_data.get('total_awo_tpe') or 0)
                        euro = float(s_data.get('total_euro') or 0) + float(vp_data.get('total_vp_euro') or 0)
                        dollar = float(s_data.get('total_dollar') or 0) + float(vp_data.get('total_vp_dollar') or 0)

                        sales_profit = float(profit_by_date.get(current_date, {}).get('profit_da') or 0)
                        awo_profit = float(awo_data.get('total_awo_benefice') or 0)
                        benefice = sales_profit + awo_profit

                        # تجميع الإجماليات
                        sum_ps_gold += ps_gold
                        sum_ps_silver += ps_silver
                        sum_recettes += recette
                        sum_oc_gold += oc_gold
                        sum_oc_silver += oc_silver
                        sum_tpe += tpe
                        sum_euro += euro
                        sum_dollar += dollar
                        sum_benefice += benefice

                        cols = [
                            f"{ps_gold:.2f}" if ps_gold else "●",
                            f"{ps_silver:.2f}" if ps_silver else "●",
                            f"{recette:,.0f}" if recette != 0 else "●",
                            f"{oc_gold:.2f}" if oc_gold else "●",
                            f"{oc_silver:.2f}" if oc_silver else "●",
                            f"{tpe:,.0f}" if tpe else "●",
                            f"{euro:,.0f}" if euro else "●",
                            f"{dollar:,.0f}" if dollar else "●",
                            "Multi" if any([ps_gold, ps_silver, recette, oc_gold, oc_silver, tpe, euro, dollar, benefice]) else "●",
                            f"{benefice:,.2f}" if benefice != 0 else "●"
                        ]

                        for col_idx, val in enumerate(cols, start=2):
                            item = QTableWidgetItem(val)
                            item.setTextAlignment(Qt.AlignCenter)
                            if val == "●":
                                item.setForeground(QBrush(QColor("#e74c3c")))
                            elif col_idx == 4 and recette < 0:
                                item.setForeground(QBrush(QColor("#e74c3c")))
                            elif col_idx == 11:
                                item.setForeground(QBrush(QColor("#27ae60" if benefice > 0 else "#c0392b")))
                            self.table.setItem(row_idx, col_idx, item)

                    else:
                        # حالة عدم وجود مبيعات أو حركات في هذا اليوم
                        for col_idx in range(2, self.table.columnCount()):
                            item = QTableWidgetItem("●")
                            item.setTextAlignment(Qt.AlignCenter)
                            item.setForeground(QBrush(QColor("#e74c3c")))
                            self.table.setItem(row_idx, col_idx, item)

                # --- إضافة السطر الأخير للمجاميع (Totals) ---
                total_row_idx = self.table.rowCount()
                self.table.insertRow(total_row_idx)

                totals = [
                    "TOTAL", "",
                    f"{sum_ps_gold:.2f}" if sum_ps_gold else "●",
                    f"{sum_ps_silver:.2f}" if sum_ps_silver else "●",
                    f"{sum_recettes:,.0f}" if sum_recettes != 0 else "●",
                    f"{sum_oc_gold:.2f}" if sum_oc_gold else "●",
                    f"{sum_oc_silver:.2f}" if sum_oc_silver else "●",
                    f"{sum_tpe:,.0f}" if sum_tpe else "●",
                    f"{sum_euro:,.0f}" if sum_euro else "●",
                    f"{sum_dollar:,.0f}" if sum_dollar else "●",
                    "",
                    f"{sum_benefice:,.2f}" if sum_benefice != 0 else "●"
                ]

                for col_idx, val in enumerate(totals):
                    item = QTableWidgetItem(val)
                    item.setTextAlignment(Qt.AlignCenter)
                    item.setFont(QFont("", 13, QFont.Bold))
                    item.setBackground(QBrush(QColor("#0f8f83")))
                    item.setForeground(QBrush(QColor("#e74c3c" if val == "●" else "white")))
                    self.table.setItem(total_row_idx, col_idx, item)

        except Exception as e:
            import logging
            logging.error(f"Erreur chargement résumé mensuel: {e}")
