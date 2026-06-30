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
        self.available_versement = 0.0
        
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

        self.load_versement_balance()
        
        self.inp_cash = QLineEdit(str(int(self.net_to_pay)))
        self.inp_cash.setStyleSheet("font-size: 20px; font-weight: bold; color: #27ae60; height: 40px;")
        self.inp_tpe = QLineEdit("0")
        self.inp_tpe.setStyleSheet("font-size: 20px; font-weight: bold; color: #2980b9; height: 40px;")
        self.inp_oc = QLineEdit("0.00")
        self.inp_oc.setStyleSheet("font-size: 20px; font-weight: bold; color: #8e44ad; height: 40px;")
        
        self.inp_impos = QLineEdit("0.00")
        self.inp_impos.setStyleSheet("font-size: 20px; font-weight: bold; color: #d35400; height: 40px;")
        
        self.inp_versement = QLineEdit("0.00")
        self.inp_versement.setStyleSheet("font-size: 20px; font-weight: bold; color: #e67e22; height: 40px;")
        
        self.inp_versement.textChanged.connect(self.update_cash_auto)
        self.inp_tpe.textChanged.connect(self.update_cash_auto)

        self.combo_vendeur = QComboBox()
        self.combo_vendeur.setStyleSheet("font-size: 18px; font-weight: bold; color: #2c3e50; height: 40px;")
        self.load_sellers()

        form_layout.addRow("💸 Vers. Espèces (Cash) :", self.inp_cash)
        form_layout.addRow("💳 Vers. Carte TPE :", self.inp_tpe)
        
        vers_lay = QHBoxLayout()
        vers_lay.addWidget(self.inp_versement)
        lbl_dispo = QLabel(f"(Dispo: {self.available_versement:,.2f} DA)")
        lbl_dispo.setStyleSheet("font-size: 14px; font-weight: bold; color: #7f8c8d;")
        vers_lay.addWidget(lbl_dispo)
        form_layout.addRow("💰 Utiliser Versement :", vers_lay)

        form_layout.addRow("⚖️ Or Cassé (O.C) :", self.inp_oc)
        form_layout.addRow("📑 Impos (Déclaré) :", self.inp_impos)
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

    def load_versement_balance(self):
        try:
            v_list = self.manager.versements.get_versements(status_filter='EN_COURS', client_id=self.current_client_id)
            for v in v_list:
                if v.get('type_versement') == 'A_VIDE':
                    self.available_versement += float(v.get('total_paid_money_da', 0))
        except Exception:
            pass

    def update_cash_auto(self):
        try: tpe = float(self.inp_tpe.text() or 0)
        except: tpe = 0.0
        try: versement = float(self.inp_versement.text() or 0)
        except: versement = 0.0
        
        req_cash = self.net_to_pay - tpe - versement
        if not self.focusWidget() or self.focusWidget() != self.inp_cash:
            self.inp_cash.setText(f"{req_cash:.2f}")

    def get_payment_values(self):
        try: cash = float(self.inp_cash.text() or 0)
        except: cash = 0.0
        try: tpe = float(self.inp_tpe.text() or 0)
        except: tpe = 0.0
        try: oc = float(self.inp_oc.text() or 0)
        except: oc = 0.0
        try: impos = float(self.inp_impos.text() or 0)
        except: impos = 0.0
        try: versement = float(self.inp_versement.text() or 0)
        except: versement = 0.0
        
        if versement > self.available_versement:
            versement = self.available_versement
            
        vendeur_id = self.combo_vendeur.currentData()
        return cash, tpe, oc, impos, vendeur_id, versement

    def load_sellers(self):
        try:
            with self.manager.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute("SELECT id, username FROM Users WHERE is_active = 1")
                users = cursor.fetchall()
                while cursor.nextset(): pass
                for u in users:
                    self.combo_vendeur.addItem(u['username'], u['id'])
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
            cash, tpe, oc, impos, vendeur_id, versement_used = dialog.get_payment_values()

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
                old_gold_weight=oc,
                impos_weight=impos, 
                notes=f"Payé {versement_used:,.0f} DA par Versement" if versement_used > 0 else ""
            )

            if result.get("success"):
                if versement_used > 0:
                    self.deduct_from_versements(self.current_client_id, versement_used, result.get('receipt_number', ''), journee_id)
                QMessageBox.information(self, "Succès", f"Vente enregistrée avec succès !\nFacture N°: {result['receipt_number']}")
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