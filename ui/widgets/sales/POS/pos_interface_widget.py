from PySide6.QtWidgets import QWidget, QMessageBox, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QFormLayout, QApplication, QComboBox
from PySide6.QtCore import Qt, QTimer
import qtawesome as qta

from .pos_ui_builder          import POSUIBuilder
from .pos_client_manager      import POSClientManager
from .pos_inventory_loader    import POSInventoryLoader
from .pos_cart_manager        import POSCartManager
from .pos_discount_manager    import POSDiscountManager

# ──────────────────────────────────────────────────────────
# كلاس نافذة إتمام البيع 
# ──────────────────────────────────────────────────────────
class POSCheckoutDialog(QDialog):
    def __init__(self, manager, net_to_pay, client_name, current_user_id, current_client_id, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.net_to_pay = net_to_pay
        self.client_name = client_name
        self.current_user_id = current_user_id
        self.current_client_id = current_client_id
        
        self.setWindowTitle("Finalisation de la Vente")
        self.setObjectName("panel") 
        
        screen = QApplication.primaryScreen().availableGeometry()
        self.resize(screen.width(), int(screen.height() * 0.45)) 
        self.move(screen.x(), screen.y()) 
        
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 20, 30, 20)
        layout.setSpacing(15)

        header_lay = QHBoxLayout()
        icon_lbl = QLabel()
        icon_lbl.setPixmap(qta.icon("fa5s.money-check-alt", color="#27ae60").pixmap(28, 28))
        title_lbl = QLabel(f"Encaisser la vente - {self.client_name}")
        title_lbl.setStyleSheet("font-size: 18px; font-weight: bold; color: #2c3e50;")
        header_lay.addWidget(icon_lbl)
        header_lay.addWidget(title_lbl)
        header_lay.addStretch()
        
        self.lbl_net = QLabel(f"NET À PAYER : {self.net_to_pay:,.2f} DA")
        self.lbl_net.setStyleSheet("font-size: 22px; font-weight: 900; color: #c0392b; background-color: #fdf2e9; padding: 5px 15px; border-radius: 5px;")
        header_lay.addWidget(self.lbl_net)
        layout.addLayout(header_lay)

        form_layout = QFormLayout()
        form_layout.setSpacing(10)
        form_layout.setLabelAlignment(Qt.AlignRight)

        self.inp_cash = QLineEdit(str(int(self.net_to_pay)))
        self.inp_cash.setStyleSheet("font-size: 20px; font-weight: bold; color: #27ae60; height: 40px;")
        self.inp_tpe = QLineEdit("0")
        self.inp_tpe.setStyleSheet("font-size: 20px; font-weight: bold; color: #2980b9; height: 40px;")
        # ── Or Cassé : Poids × Prix/g → Total auto-calculé ──
        oc_container = QWidget()
        oc_row_layout = QHBoxLayout(oc_container)
        oc_row_layout.setContentsMargins(0, 0, 0, 0)
        oc_row_layout.setSpacing(6)

        self.inp_oc_weight = QLineEdit("0.000")
        self.inp_oc_weight.setPlaceholderText("Poids (g)")
        self.inp_oc_weight.setStyleSheet("font-size: 19px; font-weight: bold; color: #8e44ad; height: 40px; min-width: 110px;")

        lbl_oc_sep = QLabel("×")
        lbl_oc_sep.setStyleSheet("font-size: 20px; font-weight: bold; color: #8e44ad;")
        lbl_oc_sep.setAlignment(Qt.AlignCenter)
        lbl_oc_sep.setFixedWidth(20)

        self.inp_oc_price = QLineEdit("0.00")
        self.inp_oc_price.setPlaceholderText("Prix/g (DA)")
        self.inp_oc_price.setStyleSheet("font-size: 19px; font-weight: bold; color: #8e44ad; height: 40px; min-width: 120px;")

        lbl_oc_eq = QLabel("=")
        lbl_oc_eq.setStyleSheet("font-size: 20px; font-weight: bold; color: #8e44ad;")
        lbl_oc_eq.setAlignment(Qt.AlignCenter)
        lbl_oc_eq.setFixedWidth(18)

        self.lbl_oc_total = QLabel("0.00 DA")
        self.lbl_oc_total.setStyleSheet(
            "font-size: 19px; font-weight: 900; color: #6c3483; "
            "background: #f5eef8; border: 1px solid #c39bd3; "
            "border-radius: 4px; padding: 4px 10px; min-width: 140px;"
        )
        self.lbl_oc_total.setAlignment(Qt.AlignCenter)

        oc_row_layout.addWidget(self.inp_oc_weight)
        oc_row_layout.addWidget(lbl_oc_sep)
        oc_row_layout.addWidget(self.inp_oc_price)
        oc_row_layout.addWidget(lbl_oc_eq)
        oc_row_layout.addWidget(self.lbl_oc_total)
        oc_row_layout.addStretch()
        
        self.inp_obs = QLineEdit("")
        self.inp_obs.setPlaceholderText("Remarque / Observation sur la vente...")
        self.inp_obs.setStyleSheet("font-size: 16px; font-weight: bold; color: #2c3e50; height: 40px; padding: 5px; border: 1px solid #bdc3c7; border-radius: 4px;")

        # ── Euro : montant € × taux DA/€ → Total DA auto-calculé ──
        euro_container, self.inp_euro_amt, self.inp_euro_rate, self.lbl_euro_total = \
            self._build_currency_row("#1a6b8a", "€", "Montant (€)", "Taux (DA/€)")

        # ── Dollar : montant $ × taux DA/$ → Total DA auto-calculé ──
        dollar_container, self.inp_dollar_amt, self.inp_dollar_rate, self.lbl_dollar_total = \
            self._build_currency_row("#1d8348", "$", "Montant ($)", "Taux (DA/$)")

        self.inp_tpe.textChanged.connect(self.update_cash_auto)
        self.inp_oc_weight.textChanged.connect(self._update_oc_and_cash)
        self.inp_oc_price.textChanged.connect(self._update_oc_and_cash)
        self.inp_euro_amt.textChanged.connect(self._update_euro_and_cash)
        self.inp_euro_rate.textChanged.connect(self._update_euro_and_cash)
        self.inp_dollar_amt.textChanged.connect(self._update_dollar_and_cash)
        self.inp_dollar_rate.textChanged.connect(self._update_dollar_and_cash)

        self.combo_vendeur = QComboBox()
        self.combo_vendeur.setStyleSheet("font-size: 18px; font-weight: bold; color: #2c3e50; height: 40px;")
        self.load_sellers()

        form_layout.addRow("💸 Vers. Espèces (Cash) :", self.inp_cash)
        form_layout.addRow("💳 Vers. Carte TPE :", self.inp_tpe)
        form_layout.addRow("⚖️ Or Cassé (O.C) :", oc_container)
        form_layout.addRow("🇪🇺 Euro (€) :", euro_container)
        form_layout.addRow("🇺🇸 Dollar ($) :", dollar_container)
        form_layout.addRow("📝 Observation :", self.inp_obs)
        form_layout.addRow("👨‍💼 Vendeur :", self.combo_vendeur)
        layout.addLayout(form_layout)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(15)

        self.btn_keyboard = QPushButton("⌨️ Clavier")
        self.btn_keyboard.setFixedHeight(50)
        self.btn_keyboard.setStyleSheet("background-color: #34495e; color: white; font-weight: bold; font-size: 16px; border-radius: 6px;")
        self.btn_keyboard.clicked.connect(self.show_virtual_keyboard)

        self.btn_cancel = QPushButton("Annuler")
        self.btn_cancel.setFixedHeight(50)
        self.btn_cancel.setStyleSheet("background-color: #95a5a6; color: white; font-weight: bold; font-size: 16px; border-radius: 6px;")
        self.btn_cancel.clicked.connect(self.reject)

        self.btn_confirm = QPushButton("🔒 Confirmer et Encaisser")
        self.btn_confirm.setFixedHeight(50)
        self.btn_confirm.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; font-size: 16px; border-radius: 6px;")
        self.btn_confirm.clicked.connect(self.accept)

        btn_layout.addWidget(self.btn_keyboard, 1)
        btn_layout.addWidget(self.btn_cancel, 1)
        btn_layout.addWidget(self.btn_confirm, 2)
        layout.addLayout(btn_layout)

    # ─────────────────────────────────────────────────────────────
    # Helpers : construction et calcul des lignes devise
    # ─────────────────────────────────────────────────────────────
    def _build_currency_row(self, accent: str, symbol: str, ph_amount: str, ph_rate: str):
        """Construit une ligne: [montant devise] × [taux] = [total DA]. Retourne (container, inp_amt, inp_rate, lbl_total)."""
        container = QWidget()
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)

        inp_amt = QLineEdit("0.00")
        inp_amt.setPlaceholderText(ph_amount)
        inp_amt.setStyleSheet(f"font-size: 19px; font-weight: bold; color: {accent}; height: 40px; min-width: 110px;")

        lbl_x = QLabel("×")
        lbl_x.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {accent};")
        lbl_x.setAlignment(Qt.AlignCenter)
        lbl_x.setFixedWidth(20)

        inp_rate = QLineEdit("0.00")
        inp_rate.setPlaceholderText(ph_rate)
        inp_rate.setStyleSheet(f"font-size: 19px; font-weight: bold; color: {accent}; height: 40px; min-width: 120px;")

        lbl_eq = QLabel("=")
        lbl_eq.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {accent};")
        lbl_eq.setAlignment(Qt.AlignCenter)
        lbl_eq.setFixedWidth(18)

        lbl_total = QLabel(f"{symbol} 0.00 DA")
        lbl_total.setStyleSheet(
            f"font-size: 19px; font-weight: 900; color: {accent}; "
            f"background: #f0f9ff; border: 1px solid {accent}55; "
            "border-radius: 4px; padding: 4px 10px; min-width: 160px;"
        )
        lbl_total.setAlignment(Qt.AlignCenter)

        row.addWidget(inp_amt)
        row.addWidget(lbl_x)
        row.addWidget(inp_rate)
        row.addWidget(lbl_eq)
        row.addWidget(lbl_total)
        row.addStretch()
        return container, inp_amt, inp_rate, lbl_total

    def _calc_devise_da(self, inp_amt: QLineEdit, inp_rate: QLineEdit) -> float:
        """Calcule montant_devise × taux → valeur DA."""
        try: a = float(inp_amt.text() or 0)
        except: a = 0.0
        try: r = float(inp_rate.text() or 0)
        except: r = 0.0
        return a * r

    def _refresh_devise_label(self, lbl: QLabel, symbol: str, accent: str, amount_da: float):
        lbl.setText(f"{symbol} {amount_da:,.2f} DA")
        over = amount_da > self.net_to_pay
        if over:
            lbl.setStyleSheet(
                "font-size: 19px; font-weight: 900; color: #c0392b; "
                "background: #fdf2e9; border: 1px solid #e74c3c; "
                "border-radius: 4px; padding: 4px 10px; min-width: 160px;"
            )
        else:
            lbl.setStyleSheet(
                f"font-size: 19px; font-weight: 900; color: {accent}; "
                f"background: #f0f9ff; border: 1px solid {accent}55; "
                "border-radius: 4px; padding: 4px 10px; min-width: 160px;"
            )

    def _get_oc_amount(self) -> float:
        """Retourne le montant en DA de l'or cassé (poids × prix/g)."""
        try: w = float(self.inp_oc_weight.text() or 0)
        except: w = 0.0
        try: p = float(self.inp_oc_price.text() or 0)
        except: p = 0.0
        return w * p

    def _update_oc_and_cash(self):
        oc_amount = self._get_oc_amount()
        self.lbl_oc_total.setText(f"{oc_amount:,.2f} DA")
        if oc_amount > self.net_to_pay:
            self.lbl_oc_total.setStyleSheet(
                "font-size: 19px; font-weight: 900; color: #c0392b; "
                "background: #fdf2e9; border: 1px solid #e74c3c; "
                "border-radius: 4px; padding: 4px 10px; min-width: 140px;"
            )
        else:
            self.lbl_oc_total.setStyleSheet(
                "font-size: 19px; font-weight: 900; color: #6c3483; "
                "background: #f5eef8; border: 1px solid #c39bd3; "
                "border-radius: 4px; padding: 4px 10px; min-width: 140px;"
            )
        self.update_cash_auto()

    def _update_euro_and_cash(self):
        da = self._calc_devise_da(self.inp_euro_amt, self.inp_euro_rate)
        self._refresh_devise_label(self.lbl_euro_total, "€", "#1a6b8a", da)
        self.update_cash_auto()

    def _update_dollar_and_cash(self):
        da = self._calc_devise_da(self.inp_dollar_amt, self.inp_dollar_rate)
        self._refresh_devise_label(self.lbl_dollar_total, "$", "#1d8348", da)
        self.update_cash_auto()

    def update_cash_auto(self):
        try: tpe = float(self.inp_tpe.text() or 0)
        except: tpe = 0.0
        oc_da     = self._get_oc_amount()
        euro_da   = self._calc_devise_da(self.inp_euro_amt, self.inp_euro_rate)
        dollar_da = self._calc_devise_da(self.inp_dollar_amt, self.inp_dollar_rate)
        req_cash  = self.net_to_pay - tpe - oc_da - euro_da - dollar_da
        if not self.focusWidget() or self.focusWidget() != self.inp_cash:
            self.inp_cash.setText(f"{req_cash:.2f}")

    def get_payment_values(self):
        try: cash = float(self.inp_cash.text() or 0)
        except: cash = 0.0
        try: tpe = float(self.inp_tpe.text() or 0)
        except: tpe = 0.0
        try: oc_weight = float(self.inp_oc_weight.text() or 0)
        except: oc_weight = 0.0
        try: oc_price = float(self.inp_oc_price.text() or 0)
        except: oc_price = 0.0
        oc_amount = oc_weight * oc_price
        try: euro = float(self.inp_euro_amt.text() or 0)
        except: euro = 0.0
        try: taux_euro = float(self.inp_euro_rate.text() or 0)
        except: taux_euro = 0.0
        try: dollar = float(self.inp_dollar_amt.text() or 0)
        except: dollar = 0.0
        try: taux_dollar = float(self.inp_dollar_rate.text() or 0)
        except: taux_dollar = 0.0
        obs = self.inp_obs.text().strip()
        vendeur_id = self.combo_vendeur.currentData()
        # cash, tpe, oc_weight(g), oc_price(DA/g), oc_amount(DA),
        # euro(€), taux_euro(DA/€), dollar($), taux_dollar(DA/$), vendeur_id, obs
        return cash, tpe, oc_weight, oc_price, oc_amount, euro, taux_euro, dollar, taux_dollar, vendeur_id, obs

    def load_sellers(self):
        try:
            with self.manager.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute("SELECT id, username, full_name FROM Users WHERE is_active = 1")
                users = cursor.fetchall()
                while cursor.nextset(): pass
                for u in users:
                    fn = str(u.get('full_name') or '').strip()
                    un = str(u.get('username') or '').strip()
                    display_name = fn if fn else un
                    if fn and un and fn != un:
                        display_name = f"{fn} ({un})"
                    self.combo_vendeur.addItem(display_name, u['id'])
                    if u['id'] == self.current_user_id:
                        self.combo_vendeur.setCurrentIndex(self.combo_vendeur.count() - 1)
        except Exception:
            pass


    # -------------------------------------------------------------
    # 🟢 الدالة الخاصة بفتح الكيبورد الافتراضي
    # -------------------------------------------------------------
    def show_virtual_keyboard(self):
        try:
            from ui.tools.virtual_keyboard import VirtualKeyboardDialog
            kb = VirtualKeyboardDialog._instance
            if not kb:
                kb = VirtualKeyboardDialog(self)
            else:
                kb.set_active_parent(self)
            kb.show()
            
            # إعادة التركيز على خانة المبلغ تلقائياً ليتمكن من الكتابة فوراً
            if not self.focusWidget() or not isinstance(self.focusWidget(), QLineEdit):
                self.inp_cash.setFocus()
                self.inp_cash.selectAll()
        except Exception as e:
            print(f"Erreur d'ouverture du clavier: {e}")

    # -------------------------------------------------------------
    # 🟢 حماية من التركيز التلقائي الذي يسبب انهيار الفلاتر
    # -------------------------------------------------------------
    def showEvent(self, event):
        super().showEvent(event)
        # تم إزالة التأخير (QTimer) والتركيز العنيف لمنع انهيار البرنامج

    def accept(self):
        try: self.inp_cash.clearFocus()
        except: pass
        super().accept()

    def reject(self):
        try: self.inp_cash.clearFocus()
        except: pass
        super().reject()


class POSInterfaceWidget(POSUIBuilder, POSClientManager, POSInventoryLoader, POSCartManager, POSDiscountManager, QWidget):
    def __init__(self, manager, session_info, on_close_session_callback):
        QWidget.__init__(self)
        self.manager = manager
        self.session_info = session_info
        self.on_close_session = on_close_session_callback
        self.cart_items = []
        self.calculated_discount_amount = 0.0
        self.discount_percent = 0.0
        self.final_price_val = 0.0
        self.current_discount_mode = "NONE" 
        self.products_cache = {}
        self.filter_min_weight = None
        self.filter_max_weight = None
        self.clients_data = []
        self.current_client_id = 1   
        self.init_ui()

    def _has_ui_permission(self, permission_key: str) -> bool:
        permission_key = str(permission_key or "").strip()
        if not permission_key: return True
        widget = self
        while widget is not None:
            checker = getattr(widget, "has_permission", None)
            if callable(checker):
                try: return bool(checker(permission_key))
                except Exception: return False
            parent_getter = getattr(widget, "parentWidget", None)
            widget = parent_getter() if callable(parent_getter) else None
        return True

    def _warn_permission_denied(self, message: str = "Action non autorisée."):
        QMessageBox.warning(self, "Permissions", message)

    def quick_checkout_dzd(self):
        if not self.cart_items:
            QMessageBox.warning(self, "Panier vide", "Le panier est vide. Ajoutez des articles avant d'encaisser.")
            return

        total_brut = sum(float(item.get('cart_line_total') or 0) for item in self.cart_items)
        net_to_pay = max(0, total_brut - self.calculated_discount_amount)
        client_name = getattr(self, 'btn_select_client', QPushButton("Client")).text().replace("(Réservé)", "").strip()

        dialog = POSCheckoutDialog(self.manager, net_to_pay, client_name, self.session_info.get('user_id', 1), self.current_client_id, self)
        if dialog.exec() == QDialog.Accepted:
            cash, tpe, oc_weight, oc_price, oc_amount, euro, taux_euro, dollar, taux_dollar, vendeur_id, obs = dialog.get_payment_values()

            journee = self.manager.cash_box.get_or_create_today_session(user_id=self.session_info.get('user_id', 1))
            if not journee: return
                
            journee_id = journee['id']

            result = self.manager.sales.create_sale(
                journee_id=journee_id,
                client_id=self.current_client_id,
                user_id=vendeur_id,
                cart_items=self.cart_items,
                total_amount=total_brut,
                discount=self.calculated_discount_amount,
                net_to_pay=net_to_pay,
                cash_paid=cash,
                tpe_paid=tpe,
                old_gold_weight=oc_weight,
                euro_paid=euro,
                taux_change_euro=taux_euro,
                dollar_paid=dollar,
                taux_change_dollar=taux_dollar,
                notes=obs
            )

            if result.get("success"):
                self.cart_items.clear()
                self.update_totals()
                if hasattr(self, 'refresh_cart'): self.refresh_cart()
            else:
                QMessageBox.critical(self, "Erreur", f"Erreur lors de l'enregistrement : {result.get('message')}")

    def deduct_from_versements(self, client_id, amount_to_deduct, receipt_number, journee_id):
        try:
            v_list = self.manager.versements.get_versements(status_filter='EN_COURS', client_id=client_id)
            v_list = [v for v in v_list if v.get('type_versement') == 'A_VIDE']
            
            remaining = amount_to_deduct
            for v in v_list:
                if remaining <= 0: break
                avail = float(v.get('total_paid_money_da', 0))
                if avail <= 0: continue
                
                deduct = min(avail, remaining)
                self.manager.versements.add_payment(
                    versement_id=v['id'],
                    journee_id=journee_id,
                    montant_da=-deduct,
                    or_casse_g=0,
                    prix_gramme_jour_da=0,
                    notes=f"Utilisé pour régler la Facture {receipt_number}"
                )
                remaining -= deduct
                
                if avail - deduct <= 0:
                    self.manager.versements.cloture_versement(v['id'])
                    
        except Exception as e:
            print(f"Erreur deduction versement: {e}")