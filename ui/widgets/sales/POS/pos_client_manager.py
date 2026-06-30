from PySide6.QtWidgets import QMessageBox, QDialog, QInputDialog

PERM_VERSEMENT_ADD = "act_versement_add"

class POSClientManager:
    """
    Mixin — إدارة العملاء وتحديد العميل الحالي لواجهة نقطة البيع.
    تم تبسيطه ليتوافق مع نظام الإكسيل (بدون جداول العملات والديون المعقدة).
    """

    def load_clients(self, keep_client_id=None, is_reserved_auto=False):
        try:
            self.clients_data = self.manager.customers.get_all_customers_with_balances()
            target_id = keep_client_id
            if not target_id:
                default_client = next(
                    (c for c in self.clients_data
                     if "passager" in c['name'].lower() or "comptoir" in c['name'].lower()),
                    None
                )
                target_id = default_client['id'] if default_client else 1
            self.set_current_client(target_id, is_reserved_auto)
        except Exception as e:
            print(f"Error loading clients: {e}")

    def set_current_client(self, client_id, is_reserved_auto=False):
        self.current_client_id = client_id
        client = next((c for c in self.clients_data if c['id'] == client_id), None)

        if client:
            # إخفاء الرصيد القديم لأنه لم يعد مستخدماً في نظام الإكسيل
            if hasattr(self, 'lbl_client_balance'):
                self.lbl_client_balance.hide()

            # تحديث الزر ليعرض اسم العميل بوضوح
            if is_reserved_auto:
                self.btn_select_client.setText(f" {client['name']} (Réservé)")
                self.btn_select_client.setStyleSheet("""
                    QPushButton {
                        font-size: 18px; font-weight: bold; color: white;
                        background-color: #8e44ad; border: 2px solid #9b59b6;
                        border-radius: 8px; text-align: left; padding-left: 15px;
                    }
                """)
            else:
                self.btn_select_client.setText(f" {client['name']}")
                self.btn_select_client.setStyleSheet("""
                    QPushButton {
                        font-size: 18px; font-weight: bold; color: #2c3e50;
                        background-color: white; border: 2px solid #bdc3c7;
                        border-radius: 8px; text-align: left; padding-left: 15px;
                    }
                    QPushButton:hover { border: 2px solid #3498db; background-color: #f1f8ff; }
                """)

    def get_valid_client_id(self):
        return self.current_client_id

    def open_client_selection_dialog(self):
        from ui.dialogs.client_selection_dialog import ClientSelectionDialog
        dlg = ClientSelectionDialog(self.manager, self)
        if dlg.exec():
            self.load_clients(keep_client_id=dlg.selected_client_id)

    def open_advanced_payment_dialog(self):
        QMessageBox.information(
            self, "Information", 
            "Ce système utilise le mode simplifié (Journal Excel). "
            "Les paiements avancés sont désactivés."
        )

    def add_client_versement(self):
        """تسجيل دفعة (Versement) مباشرة في يومية الإكسيل بدون تعقيد"""
        client_id = self.get_valid_client_id()
        if client_id is None or client_id == 1:
            QMessageBox.warning(self, "Attention", "Veuillez sélectionner un client spécifique.")
            return

        amount, ok = QInputDialog.getDouble(
            self, "Versement Client", 
            "Entrez le montant du versement (DA):", 
            0, 0, 10000000, 2
        )
        
        if ok and amount > 0:
            try:
                journee = self.manager.cash_box.get_or_create_today_session(user_id=self.session_info.get('user_id', 1))
                if not journee: return
                
                client_name = self.btn_select_client.text().replace("(Réservé)", "").strip()
                
                with self.manager.db.get_db_connection() as conn:
                    cursor = conn.cursor()
                    query = """
                        INSERT INTO Sales (
                            receipt_number, journee_id, client_id, user_id, 
                            total_amount_da, net_to_pay_da, cash_paid_da, notes, status
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'COMPLETED')
                    """
                    import time
                    receipt = f"VERS-{int(time.time())}"
                    cursor.execute(query, (
                        receipt, journee['id'], client_id, self.session_info.get('user_id', 1),
                        amount, amount, amount, f"Versement: {client_name}"
                    ))
                    conn.commit()
                    
                QMessageBox.information(self, "Succès", f"Versement de {amount:,.2f} DA enregistré avec succès.")
            except Exception as e:
                QMessageBox.critical(self, "Erreur", f"Erreur lors de l'enregistrement: {e}")