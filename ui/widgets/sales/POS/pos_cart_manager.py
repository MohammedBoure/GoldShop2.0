from PySide6.QtWidgets import QMessageBox, QPushButton, QTableWidgetItem, QWidget, QHBoxLayout, QVBoxLayout, QLabel, QComboBox, QDialog
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QFont, QColor
import qtawesome as qta

from ui.touch_design import apply_touch_button_defaults


class POSCartManager:
    """
    Mixin — إدارة سلة المشتريات:
    إضافة عناصر، تعديل الكميات / الأوزان، حذف، تحديث الجدول.
    يعتمد على: self.cart_items, self.cart_table, self.clients_data,
               self.load_clients(), self.update_totals(), self.inp_barcode
    """

    def add_item_to_cart_logic(self, item):
        cart_item = dict(item)
        item_type = cart_item.get('item_type', 'WEIGHT')
        
        # إذا كان المنتج محجوزاً لعميل محدد، نحدّث العميل الحالي تلقائياً
        reserved_client_id = cart_item.get('reserved_for_client_id')
        if reserved_client_id and str(reserved_client_id) != '1':
            client_id_int = int(reserved_client_id)
            self.load_clients(keep_client_id=client_id_int, is_reserved_auto=True)
            
            client_data = next(
                (c for c in self.clients_data if c['id'] == client_id_int),
                None
            )
            client_name = client_data['name'] if client_data else "Inconnu"
            
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("Produit Réservé")
            msg_box.setText(f"Ce produit est réservé pour le client : {client_name}.")
            msg_box.setIcon(QMessageBox.Information)
            
            btn_ok = msg_box.addButton("Continuer", QMessageBox.AcceptRole)
            btn_details = msg_box.addButton("Voir Détails Client", QMessageBox.ActionRole)
            
            msg_box.exec()
            
            if msg_box.clickedButton() == btn_details and client_data:
                try:
                    from ui.widgets.finance.customer_detail_dialog import CustomerDetailDialog
                except ImportError:
                    from ui.dialogs.customer_detail_dialog import CustomerDetailDialog
                dlg = CustomerDetailDialog(client_data, self.manager, self)
                dlg.exec()
        
        if item_type == 'WEIGHT':
            # استخدام البيانات الحالية للمنتج لحساب السعر (وليس exact_remaining_debt القديم)
            rem_weight = float(cart_item.get('remaining_weight') or cart_item.get('weight') or 0.0)
            unit_weight = float(cart_item.get('weight') or 0.0)
            original_weight = float(cart_item.get('original_sold_weight') or cart_item.get('total_weight') or unit_weight or rem_weight)
            
            # جلب التكاليف والهامش الحالية
            metal_cost = float(cart_item.get('metal_cost_per_gram') or 0)
            labor = float(cart_item.get('labor_cost_per_gram') or 0)
            margin = float(cart_item.get('profit_margin') or 0)
            margin_type = cart_item.get('margin_type', 'FIXED')
            
            if margin_type == 'PERCENTAGE':
                profit_per_gram = (metal_cost + labor) * (margin / 100.0)
            else:
                profit_per_gram = margin
            
            unit_price_per_gram = metal_cost + labor + profit_per_gram
            price_per_piece = unit_price_per_gram * unit_weight
            
            # حساب الإجمالي باستخدام السعر الحالي
            cart_item['cart_line_total'] = unit_price_per_gram * rem_weight
            
            cart_item['cart_max_qty'] = 1
            cart_item['cart_max_weight'] = rem_weight
            cart_item['cart_sold_qty'] = 1
            cart_item['cart_unit_weight'] = unit_weight
            cart_item['cart_original_weight'] = original_weight
            cart_item['cart_sold_weight'] = rem_weight
            cart_item['cart_unit_price'] = price_per_piece
            
            # إزالة أي أثر للسعر القديم
            if 'exact_remaining_debt' in cart_item:
                del cart_item['exact_remaining_debt']
                
        else:  # UNIT
            rem_q = int(cart_item.get('remaining_quantity') or cart_item.get('quantity') or 1)
            actual_qty = 1 if rem_q > 0 else 0
            
            # استخدام سعر البيع الحالي
            unit_price = float(cart_item.get('selling_price') or 0.0)
            
            cart_item['cart_max_qty'] = rem_q
            cart_item['cart_sold_qty'] = actual_qty
            cart_item['cart_sold_weight'] = 0.0
            cart_item['cart_unit_price'] = unit_price
            cart_item['cart_line_total'] = unit_price * actual_qty
            
            if 'exact_remaining_debt' in cart_item:
                del cart_item['exact_remaining_debt']
        
        self.cart_items.append(cart_item)
        self.refresh_cart()

    # ------------------------------------------------------------------ edit qty
    def edit_cart_amount(self, idx):
        if idx < 0 or idx >= len(self.cart_items):
            return

        from ui.tools.virtual_numpad import VirtualNumpad

        cart_item = self.cart_items[idx]
        is_weight = (cart_item.get('item_type', 'WEIGHT') == 'WEIGHT')

        if is_weight:
            initial_val = cart_item.get('cart_sold_weight', 0.0)
            max_val     = float(cart_item.get('cart_max_weight', 0.0))
            pad_title   = "Poids à vendre (g)"
            allow_dec   = True
        else:
            initial_val = cart_item.get('cart_sold_qty', 1)
            max_val     = int(cart_item.get('cart_max_qty', 1))
            pad_title   = "Quantité à vendre (pcs)"
            allow_dec   = False

        pad = VirtualNumpad(pad_title, allow_decimal=allow_dec, initial_value=initial_val, parent=self)
        if pad.exec() == QDialog.Accepted:
            val_str = pad.get_value()
            if not val_str:
                return
            try:
                val = float(val_str) if is_weight else int(val_str)
            except ValueError:
                return

            if val > max_val:
                unit_str   = "g" if is_weight else "pcs"
                format_max = f"{max_val:.2f}" if is_weight else f"{max_val}"
                QMessageBox.warning(
                    self, "Stock Insuffisant",
                    f"Le maximum disponible (Dispo) est de {format_max} {unit_str}."
                )
                val = max_val

            if val <= 0:
                return

            if is_weight:
                cart_item['cart_sold_weight'] = val
                if cart_item.get('status') == 'Partially_Sold' and 'exact_remaining_debt' in cart_item:
                    max_weight = float(cart_item.get('cart_max_weight') or 0.0)
                    price_per_gram = (
                        float(cart_item.get('exact_remaining_debt') or 0.0) / max_weight
                        if max_weight > 0 else 0
                    )
                else:
                    unit_weight      = cart_item.get('cart_unit_weight', 0.0)
                    price_per_piece  = cart_item.get('cart_unit_price', 0.0)
                    price_per_gram   = (price_per_piece / unit_weight) if unit_weight > 0 else 0
                cart_item['cart_line_total'] = price_per_gram * val
            else:
                cart_item['cart_sold_qty']   = val
                cart_item['cart_line_total'] = cart_item.get('cart_unit_price', 0.0) * val

            self.refresh_cart()

    # ------------------------------------------------------------------ delete
    def on_delete_clicked(self, idx):
        if idx is not None and 0 <= idx < len(self.cart_items):
            del self.cart_items[idx]
            self.refresh_cart()
        self.inp_barcode.setFocus()

    # ------------------------------------------------------------------ refresh
    def refresh_cart(self):
        self.cart_table.setRowCount(0)

        # 🟢 جلب الملاحظات المتاحة من قاعدة البيانات
        try:
            available_notes = getattr(self.manager.invoice_notes, 'get_all_notes', lambda: [])()
        except Exception:
            available_notes = []

        for i, item in enumerate(reversed(self.cart_items)):
            self.cart_table.insertRow(i)

            barcode_str   = str(item.get('barcode') or '')
            name_str      = str(item.get('name') or '')
            category_str  = str(item.get('category_name') or 'N/A')
            metal_str     = str(item.get('metal_type_name') or 'N/A')
            supplier_str  = str(item.get('supplier_name') or 'N/A')

            is_weight   = (item.get('item_type', 'WEIGHT') == 'WEIGHT')
            is_reserved = bool(
                item.get('reserved_for_client_id') and
                str(item.get('reserved_for_client_id')) != '1'
            )

            name_display     = name_str + ("  🔒 (Acompte)" if is_reserved else "")
            details_display  = f"Cat: {category_str} | Métal: {metal_str} | Fourn: {supplier_str}"
            full_item_display = f"{name_display}\n{details_display}"

            if is_weight:
                display_weight = item.get('cart_max_weight', 0)
                if item.get('status') == 'Partially_Sold':
                    display_weight = item.get('cart_original_weight') or item.get('original_sold_weight') or display_weight
                dispo_str = f"{float(display_weight or 0):.2f} g"
            else:
                dispo_str = f"{item.get('cart_max_qty', 0)} pcs"

            total_price = float(item.get('cart_line_total', 0.0))

            # العمود 0: الباركود
            it_code = QTableWidgetItem(barcode_str)
            it_code.setFont(QFont("", 11, QFont.Bold))
            self.cart_table.setItem(i, 0, it_code)

            # العمود 1: الاسم والتفاصيل (بدون القائمة المنسدلة)
            it_name = QTableWidgetItem(full_item_display)
            it_name.setFont(QFont("", 10, QFont.Bold))
            if is_reserved:
                it_name.setForeground(QBrush(QColor("#8e44ad")))
            self.cart_table.setItem(i, 1, it_name)

            # العمود 2: الكمية/الوزن المتاح (Dispo)
            dispo_item = QTableWidgetItem(dispo_str)
            dispo_item.setTextAlignment(Qt.AlignCenter)
            dispo_item.setFont(QFont("", 11))
            self.cart_table.setItem(i, 2, dispo_item)

            real_index = len(self.cart_items) - 1 - i

            # 🟢 العمود 3: القائمة المنسدلة (Note) بدلاً من تعديل الكمية (A vendre)
            combo_note = QComboBox()
            combo_note.setStyleSheet("""
                QComboBox {
                    font-size: 13px; padding: 4px; border: 1px solid #bdc3c7; 
                    border-radius: 4px; background-color: #f8f9fa;
                }
            """)
            combo_note.addItem("--- Note ---", "")
            for note in available_notes:
                combo_note.addItem(note, note)
                
            current_note = item.get('custom_note', "")
            if current_note:
                idx = combo_note.findData(current_note)
                if idx >= 0:
                    combo_note.setCurrentIndex(idx)
                    
            combo_note.currentIndexChanged.connect(
                lambda _, c=combo_note, idx=real_index: self.cart_items[idx].update({'custom_note': c.currentData()})
            )
            
            note_container = QWidget()
            note_lay = QHBoxLayout(note_container)
            note_lay.setContentsMargins(5, 5, 5, 5)
            note_lay.addWidget(combo_note)
            self.cart_table.setCellWidget(i, 3, note_container)

            # العمود 4: السعر الإجمالي
            p_item = QTableWidgetItem(f"{total_price:,.2f}")
            p_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            p_item.setFont(QFont("", 11, QFont.Bold))
            p_item.setForeground(Qt.darkGreen)
            self.cart_table.setItem(i, 4, p_item)

            # العمود 5: الحذف
            btn_delete = QPushButton()
            btn_delete.setIcon(qta.icon("fa5s.trash", color="white"))
            btn_delete.setIconSize(QSize(20, 20))
            btn_delete.setCursor(Qt.PointingHandCursor)
            apply_touch_button_defaults(btn_delete, danger=True)
            btn_delete.setFixedWidth(56)
            btn_delete.setStyleSheet("background-color: #e74c3c; border-radius: 6px;")
            btn_delete.clicked.connect(
                lambda checked=False, idx=real_index: self.on_delete_clicked(idx)
            )
            del_container = QWidget()
            del_layout = QHBoxLayout(del_container)
            del_layout.setContentsMargins(0, 0, 0, 0)
            del_layout.setAlignment(Qt.AlignCenter)
            del_layout.addWidget(btn_delete)
            self.cart_table.setCellWidget(i, 5, del_container)

            # إعادة ارتفاع السطر إلى الحجم الطبيعي المدمج
            self.cart_table.setRowHeight(i, 55)

        self.update_totals()
        self.inp_barcode.setFocus()
    # ------------------------------------------------------------------ clear cart
    def clear_cart_with_confirmation(self):
        # التحقق مما إذا كانت السلة فارغة أصلاً
        if not self.cart_items:
            return

        total_amount = sum(float(item.get('cart_line_total') or 0) for item in self.cart_items)
        total_weight = sum(float(item.get('cart_sold_weight') or 0) for item in self.cart_items)
        summary = (
            f"Articles dans le panier: {len(self.cart_items)}\n"
            f"Montant total: {total_amount:,.2f} DA\n"
            f"Poids total: {total_weight:,.3f} g\n\n"
            "Cette action vide uniquement le panier actuel. Elle n'annule aucune vente deja enregistree."
        )

        # إظهار رسالة التأكيد
        reply = QMessageBox.question(
            self, 
            "Vider le panier",
            summary + "\n\nVoulez-vous vraiment vider tout le panier ?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No  # جعل خيار "لا" هو الافتراضي لتجنب الحذف بالخطأ
        )

        # إذا وافق المستخدم، قم بالتفريغ والتحديث
        if reply == QMessageBox.Yes:
            self.cart_items.clear()
            self.refresh_cart()
            
        # إعادة التركيز على حقل الباركود في كلتا الحالتين
        self.inp_barcode.setFocus()
