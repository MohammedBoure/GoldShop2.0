from PySide6.QtWidgets import QMessageBox, QDialog
from PySide6.QtCore import Qt, QStringListModel, QEvent, QTimer


class POSInventoryLoader:
    """
    Mixin — تحميل المخزون في ذاكرة التخزين المؤقت،
    معالجة الباركود، الاستكمال التلقائي، فلتر الوزن.
    يعتمد على: self.manager, self.products_cache,
               self.inp_barcode, self.product_completer,
               self.filter_min_weight, self.filter_max_weight,
               self.btn_weight_filter
    """
    CACHE_PAGE_LIMIT = 1000

    @staticmethod
    def _has_real_stock(item):
        reserved_client_id = item.get('reserved_for_client_id')
        if item.get('status') in ('Scrap', 'Repair', 'Lost', 'Sold'):
            return False

        item_type = str(item.get('item_type') or 'WEIGHT').upper()
        try:
            active_count = int(item.get('active_versement_count') or 0)
        except (TypeError, ValueError):
            active_count = 0

        if item_type == 'PIECE':
            try:
                remaining = int(item.get('remaining_quantity') or 0)
                reserved = int(item.get('active_reserved_quantity') or 0)
                return remaining - reserved > 0
            except (TypeError, ValueError):
                return False

        try:
            return (
                float(item.get('remaining_weight') or 0.0) > 0.0
                and active_count == 0
                and (
                    item.get('status') in ('Available', 'Partially_Sold')
                    or (
                        item.get('status') == 'Reserved'
                        and bool(item.get('reserved_for_client_id'))
                        and str(item.get('reserved_for_client_id')) != '1'
                    )
                )
            )
        except (TypeError, ValueError):
            return False

    # ------------------------------------------------------------------ cache
    def load_inventory_cache(self):
        self.products_cache = {}
        completer_list = []
        is_filter_active = (
            self.filter_min_weight is not None
            and self.filter_max_weight is not None
        )

        try:
            query_options = {
                "limit": self.CACHE_PAGE_LIMIT,
                "offset": 0,
                "show_zero_stock": False,
                "status_filter": "SELLABLE",
                "include_totals": False,
            }
            if is_filter_active:
                query_options["min_weight"] = self.filter_min_weight
                query_options["max_weight"] = self.filter_max_weight

            items = self.manager.inventory.get_inventory_paginated(
                **query_options
            )[0]

            for item in items:
                if not self._has_real_stock(item):
                    continue

                code = str(item.get('barcode') or '').strip()
                name = str(item.get('name') or '').strip()

                metal_str = str(
                    item.get('metal_type_name') or
                    item.get('metal_name') or
                    item.get('metal_type') or ''
                ).strip()
                if metal_str:
                    name = f"{name} [{metal_str}]"

                item_type = item.get('item_type', 'WEIGHT')
                is_weight_item = (item_type == 'WEIGHT')
                current_weight = float(item.get('remaining_weight') or 0.0)

                if is_filter_active:
                    if not is_weight_item:
                        continue
                    if not (self.filter_min_weight <= current_weight <= self.filter_max_weight):
                        continue

                if code:
                    self.products_cache[code] = item
                    if is_weight_item:
                        display_str = f"{code} | {name} | {current_weight:.2f}g"
                    else:
                        display_str = f"{code} | {name}"
                    completer_list.append(display_str)

        except Exception as e:
            print(f"Erreur Cache: {e}")

        model = QStringListModel(completer_list)
        self.product_completer.setModel(model)

    # ------------------------------------------------------------------ weight filter
    def open_weight_filter(self):
        from ..weight_filter_dialog import WeightFilterDialog
        dlg = WeightFilterDialog(self.filter_min_weight, self.filter_max_weight, self)

        if dlg.exec() == QDialog.Accepted:
            if dlg.cleared:
                self.filter_min_weight = None
                self.filter_max_weight = None
                self.btn_weight_filter.setStyleSheet(
                    "background-color: #7f8c8d; border-radius: 6px;"
                )
            else:
                self.filter_min_weight = dlg.val_min
                self.filter_max_weight = dlg.val_max
                self.btn_weight_filter.setStyleSheet(
                    "background-color: #e67e22; border-radius: 6px;"
                )

            self.load_inventory_cache()
            self.inp_barcode.setFocus()

    # ------------------------------------------------------------------ barcode input
    def eventFilter(self, obj, event):
        if obj == self.inp_barcode and event.type() == QEvent.Type.KeyPress:
            text = event.text()
            if text:
                azerty_map = str.maketrans("&é\"'(-è_çà", "1234567890")
                corrected_text = text.translate(azerty_map).upper()
                if text != corrected_text:
                    self.inp_barcode.insert(corrected_text)
                    return True
        return super().eventFilter(obj, event)

    def on_text_changed_auto_add(self, text):
        text = text.strip()
        if not text:
            return
        if text in self.products_cache:
            self.process_barcode(text)

    def on_completer_activated(self, text):
        if " | " in text:
            barcode = text.split(" | ")[0].strip()
            self.inp_barcode.blockSignals(True)
            self.inp_barcode.setText(barcode)
            self.inp_barcode.blockSignals(False)
            self.process_barcode(barcode)

    def on_barcode_entered(self):
        text = self.inp_barcode.text().strip()
        if not text:
            return
        barcode = text
        if " | " in text:
            barcode = text.split(" | ")[0].strip()
        self.process_barcode(barcode)

    def open_numpad_for_barcode(self):
        from ui.tools.virtual_numpad import VirtualNumpad
        pad = VirtualNumpad("Saisir Code", allow_decimal=False, parent=self)
        if pad.exec() == QDialog.Accepted:
            val = pad.get_value()
            if val:
                self.inp_barcode.setText(val)
                self.on_barcode_entered()

    def force_clear_barcode(self):
        self.inp_barcode.blockSignals(True)
        self.inp_barcode.clear()
        self.inp_barcode.blockSignals(False)
        self.inp_barcode.setFocus()

    def refresh_inventory_cache(self):
        """Force le rechargement complet du cache d'inventaire"""
        try:
            # Fermer toutes les connexions existantes dans le pool
            if hasattr(self.manager.db, 'close_all_connections'):
                self.manager.db.close_all_connections()
            # Recharger le cache
            self.load_inventory_cache()
        except Exception as e:
            print(f"Error refreshing cache: {e}")

    def process_barcode(self, barcode):
        # Force fresh query by using a new connection and disabling cache
        try:
            with self.manager.db.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SET SESSION query_cache_type = OFF")
                cursor.execute("SELECT 1 FROM Inventory WHERE barcode = %s FOR UPDATE", (barcode,))
                cursor.fetchall() # 🟢 قراءة النتيجة لمنع بقائها معلقة
                while cursor.nextset(): pass # 🟢 تنظيف أي نتائج أخرى
                conn.commit()
        except:
            pass
        
        # 1. جلب المنتج من خلال الـ Manager
        item = self.manager.inventory.get_item_by_barcode(barcode)
        
        if item:
            # 2. معالجة المنتجات المحجوزة جزئياً (Partially_Sold)
            if item.get('status') == 'Partially_Sold':
                # إزالة أي مفتاح قديم قد يسبب استخدام سعر قديم
                if 'exact_remaining_debt' in item:
                    del item['exact_remaining_debt']
                # التأكد من وجود remaining_weight/quantity صحيحين (يتم جلبهما من قاعدة البيانات)
                if item.get('item_type') == 'WEIGHT':
                    if 'remaining_weight' not in item or item['remaining_weight'] is None:
                        item['remaining_weight'] = item.get('weight', 0.0)
                else:
                    if 'remaining_quantity' not in item or item['remaining_quantity'] is None:
                        item['remaining_quantity'] = item.get('quantity', 1)
            
            # 3. يعتمد السماح على المخزون القابل للبيع بعد خصم حجوزات العربون.
            if not self._has_real_stock(item):
                QMessageBox.warning(
                    self, "Stock indisponible",
                    f"L'article '{barcode}' n'est pas disponible pour la vente "
                    f"(stock vendable épuisé ou réservé)."
                )
                self.force_clear_barcode()
                return
            
            # 4. إضافة المنتج للسلة
            self.add_item_to_cart_logic(item)
            
            if self.product_completer.popup().isVisible():
                self.product_completer.popup().hide()
            
            self.force_clear_barcode()
            QTimer.singleShot(0, self.force_clear_barcode)
        else:
            QMessageBox.warning(
                self, "Article Introuvable",
                f"Le code '{barcode}' n'existe pas dans la base de données."
            )
            self.inp_barcode.setFocus()
            self.inp_barcode.selectAll()