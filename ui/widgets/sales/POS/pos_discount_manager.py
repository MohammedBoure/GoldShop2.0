from PySide6.QtWidgets import QMessageBox, QDialog


class POSDiscountManager:
    """
    Mixin — حساب الخصومات وتحديث إجماليات الفاتورة.
    يعتمد على: self.cart_items, self.discount_percent,
               self.final_price_val, self.calculated_discount_amount,
               self.current_discount_mode, وعدة labels وأزرار.
    """

    # ------------------------------------------------------------------ نافذة الخصم بالنسبة المئوية
    def open_numpad_for_discount_pct(self):
        from ui.tools.virtual_numpad import VirtualNumpad
        pad = VirtualNumpad(
            "Saisir la Remise (%)",
            allow_decimal=True,
            initial_value=self.discount_percent,
            parent=self
        )
        if pad.exec() == QDialog.Accepted:
            val = pad.get_value()
            if val:
                pct = float(val)
                if 0 <= pct <= 100:
                    self.discount_percent        = pct
                    self.current_discount_mode   = "PERCENT"
                    self.update_totals()
                else:
                    QMessageBox.warning(self, "Erreur", "Le pourcentage doit être entre 0 et 100.")

    # ------------------------------------------------------------------ نافذة السعر النهائي
    def open_numpad_for_final_price(self):
        from ui.tools.virtual_numpad import VirtualNumpad
        total_brut = sum(float(item.get('cart_line_total') or 0) for item in self.cart_items)
        pad = VirtualNumpad(
            "Saisir le Prix Final (DA)",
            allow_decimal=True,
            initial_value=self.final_price_val,
            parent=self
        )
        if pad.exec() == QDialog.Accepted:
            val = pad.get_value()
            if val:
                price = float(val)
                if 0 <= price <= total_brut:
                    # 🟢 التعديل: نحفظ "قيمة التخفيض" بدلاً من تجميد السعر الكلي
                    # لمنع جعل المنتجات المضافة لاحقاً مجانية
                    self.fixed_discount_amount = total_brut - price
                    self.final_price_val       = price
                    self.current_discount_mode = "FINAL_PRICE"
                    self.update_totals()
                else:
                    QMessageBox.warning(
                        self, "Erreur",
                        f"Le prix final doit être entre 0 et {total_brut:,.2f} DA."
                    )

    # ------------------------------------------------------------------ نافذة السعر لكل غرام
    def open_numpad_for_price_per_gram(self):
        from ui.tools.virtual_numpad import VirtualNumpad
        total_weight = sum(
            float(item.get('cart_sold_weight') or 0.0) for item in self.cart_items
        )
        if total_weight <= 0:
            QMessageBox.warning(self, "Erreur", "Aucun article avec poids dans le panier.")
            return

        total_brut   = sum(float(item.get('cart_line_total') or 0) for item in self.cart_items)
        current_avg  = total_brut / total_weight if total_weight > 0 else 0

        pad = VirtualNumpad(
            "Saisir le Nouveau Prix par Gramme",
            allow_decimal=True,
            initial_value=current_avg,
            parent=self
        )
        if pad.exec() == QDialog.Accepted:
            val = pad.get_value()
            if val:
                new_price_per_gram = float(val)
                if new_price_per_gram >= 0:
                    # 🟢 التعديل الجوهري: تفعيل وضع "السعر للغرام" وحفظ الهدف
                    self.target_price_per_gram = new_price_per_gram
                    self.current_discount_mode = "PRICE_PER_GRAM"
                    self.update_totals()
                else:
                    QMessageBox.warning(self, "Erreur", "Le prix par gramme doit être positif.")

    # ------------------------------------------------------------------ تحديث الإجماليات
    def update_totals(self):
        total_brut = sum(float(item.get('cart_line_total') or 0) for item in self.cart_items)
        self.lbl_total_raw.setText(f"{total_brut:,.2f} DA")

        total_weight = sum(
            float(item.get('cart_sold_weight') or 0.0) for item in self.cart_items
        )
        self.lbl_total_weight.setText(f"{total_weight:,.2f} g")

        avg_price_per_gram = (total_brut / total_weight) if total_weight > 0 else 0.0
        self.lbl_avg_price_per_gram.setText(f"{avg_price_per_gram:,.2f} DA/g")

        if total_brut == 0:
            # تصفير المتغيرات بالكامل عند فراغ السلة
            self.discount_percent            = 0.0
            self.final_price_val             = 0.0
            self.calculated_discount_amount  = 0.0
            self.current_discount_mode       = "NONE"
            self.target_price_per_gram       = 0.0
            self.fixed_discount_amount       = 0.0
        else:
            if self.current_discount_mode == "PERCENT":
                self.calculated_discount_amount = total_brut * (self.discount_percent / 100.0)
                self.final_price_val            = total_brut - self.calculated_discount_amount

            elif self.current_discount_mode == "PRICE_PER_GRAM":
                # 🟢 حساب التخفيض بشكل ديناميكي بحيث يبقى "السعر للغرام" ثابتاً مهما أضفنا من منتجات
                target_ppg = getattr(self, 'target_price_per_gram', 0.0)
                expected_final = target_ppg * total_weight
                
                if expected_final > total_brut:
                    expected_final = total_brut
                    
                self.final_price_val = expected_final
                self.calculated_discount_amount = total_brut - self.final_price_val
                self.discount_percent = (self.calculated_discount_amount / total_brut) * 100.0

            elif self.current_discount_mode == "FINAL_PRICE":
                # 🟢 الحفاظ على "قيمة التخفيض" ثابتة، للسماح للسعر النهائي بالتكيف إذا تمت إضافة منتج
                fixed_discount = getattr(self, 'fixed_discount_amount', self.calculated_discount_amount)
                
                if fixed_discount > total_brut:
                    fixed_discount = total_brut
                    
                self.calculated_discount_amount = fixed_discount
                self.final_price_val = total_brut - fixed_discount
                self.discount_percent = (self.calculated_discount_amount / total_brut) * 100.0
                
            else:
                self.calculated_discount_amount = 0.0
                self.discount_percent           = 0.0
                self.final_price_val            = total_brut

        net = max(0, total_brut - self.calculated_discount_amount)

        self.btn_discount_pct.setText(f"Remise: {self.discount_percent:.2f} %")
        self.btn_discount_value.setText(f"Final: {self.final_price_val:,.2f} DA")
        self.lbl_discount_amount_display.setText(f"(- {self.calculated_discount_amount:,.2f} DA)")
        self.lbl_net_to_pay.setText(f"{net:,.2f} DA")

        net_price_per_gram = (net / total_weight) if total_weight > 0 else 0.0
        if hasattr(self, 'btn_price_per_gram'):
            self.btn_price_per_gram.setText(f"Prix/g: {net_price_per_gram:,.2f} DA")