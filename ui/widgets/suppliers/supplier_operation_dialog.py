from __future__ import annotations

from typing import Any, Dict, Optional

from PySide6.QtCore import QDate, QTimer, Qt
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui.tools.virtual_keyboard import VirtualKeyboardDialog
from ui.touch_design import apply_touch_button_defaults, apply_touch_input_defaults


class SupplierOperationDialog(QDialog):
    """Dialog in 100% French with horizontal space-saving layout, single touch keyboard button, and real-time purity converter."""

    def __init__(
        self,
        manager,
        supplier: Dict[str, Any],
        operation: Optional[Dict[str, Any]] = None,
        current_user: Optional[dict] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.manager = manager
        self.supplier = dict(supplier or {})
        self.operation = dict(operation or {})
        self.current_user = current_user or {}
        self.result_id = self.operation.get("id")
        self.is_auto_updating = False

        title = "Modifier l'opération" if self.result_id else "Nouvelle opération - " + (self.supplier.get("name") or "")
        self.setWindowTitle(title)
        self.setMinimumWidth(680)
        self._init_ui()
        self._populate()
        self._connect_helper_signals()

    def _service(self):
        return self.manager.suppliers

    def showEvent(self, event):
        super().showEvent(event)
        self._position_at_top()
        QTimer.singleShot(0, self._position_at_top)

    def _position_at_top(self):
        screen = QApplication.primaryScreen()
        if screen:
            available = screen.availableGeometry()
            x = (available.width() - self.width()) // 2
            self.move(max(0, x), available.top())

    def _show_keyboard(self, target=None):
        if target is None:
            focused = self.focusWidget()
            if isinstance(focused, (QLineEdit, QComboBox, QDoubleSpinBox)):
                target = focused
            else:
                target = self.obs_edit
        if target:
            target.setFocus()
        kb = VirtualKeyboardDialog(self)
        kb.show()
        kb.raise_()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)

        # 1. Supplier Banner Card
        banner_text = f"Fournisseur : {self.supplier.get('name') or '-'}"
        banner = QLabel(banner_text)
        banner.setStyleSheet(
            "background-color: #0284c7; color: #ffffff; font-size: 15px; font-weight: bold; padding: 6px 12px; border-radius: 6px;"
        )
        layout.addWidget(banner)

        # 2. Quick Preset & Single Touch Keyboard Button
        top_bar = QHBoxLayout()
        top_bar.setSpacing(10)

        self.btn_preset_regler = QPushButton("Règlement / Régler (Négatif)")
        self.btn_preset_regler.setStyleSheet(
            "background: #fef2f2; color: #dc2626; font-weight: bold; border: 1px solid #fca5a5; padding: 5px 12px; border-radius: 6px;"
        )
        self.btn_preset_regler.clicked.connect(self._apply_regler_preset)
        top_bar.addWidget(self.btn_preset_regler)

        top_bar.addStretch()

        self.btn_keyboard = QPushButton(" ⌨️ Clavier Tactile")
        self.btn_keyboard.setStyleSheet(
            "background: #f1f5f9; color: #0284c7; font-weight: bold; border: 1px solid #cbd5e1; padding: 5px 14px; border-radius: 6px;"
        )
        self.btn_keyboard.clicked.connect(lambda: self._show_keyboard())
        top_bar.addWidget(self.btn_keyboard)

        layout.addLayout(top_bar)

        # 3. Horizontal Main Form Layout (Row-based to minimize vertical height)
        form_box = QGroupBox("Données de l'opération")
        form_box.setStyleSheet(
            "QGroupBox { font-weight: bold; color: #0f172a; border: 1px solid #cbd5e1; border-radius: 6px; margin-top: 4px; padding-top: 8px; }"
        )
        fb_layout = QVBoxLayout(form_box)
        fb_layout.setSpacing(6)

        # Row 1: Date & Style
        row1 = QHBoxLayout()
        row1.setSpacing(12)

        lbl_date = QLabel("Date :")
        self.date_edit = QDateEdit(QDate.currentDate())
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("dd/MM/yyyy")

        lbl_color = QLabel("Style de ligne :")
        self.color_combo = QComboBox()
        self.color_combo.addItem("Normal (Noir / Vert)", "BLACK")
        self.color_combo.addItem("Important / Réglement (Rouge)", "RED")

        row1.addWidget(lbl_date)
        row1.addWidget(self.date_edit, stretch=1)
        row1.addWidget(lbl_color)
        row1.addWidget(self.color_combo, stretch=1)
        fb_layout.addLayout(row1)

        # Row 2: Poids, Afaçon, Montant (Horizontal 3-column)
        row2 = QHBoxLayout()
        row2.setSpacing(10)

        lbl_poids = QLabel("Poids Net (g) :")
        self.poids_spin = QDoubleSpinBox()
        self.poids_spin.setRange(-999999.999, 999999.999)
        self.poids_spin.setDecimals(2)
        self.poids_spin.setSuffix(" g")

        lbl_afacon = QLabel("Afaçon :")
        self.afacon_edit = QLineEdit()
        self.afacon_edit.setPlaceholderText("ex: 1500, 1350...")

        lbl_montant = QLabel("Montant (DA) :")
        self.montant_spin = QDoubleSpinBox()
        self.montant_spin.setRange(-999999999.00, 999999999.00)
        self.montant_spin.setDecimals(0)
        self.montant_spin.setSuffix(" DA")

        row2.addWidget(lbl_poids)
        row2.addWidget(self.poids_spin, stretch=1)
        row2.addWidget(lbl_afacon)
        row2.addWidget(self.afacon_edit, stretch=1)
        row2.addWidget(lbl_montant)
        row2.addWidget(self.montant_spin, stretch=1)
        fb_layout.addLayout(row2)

        # Row 3: Obs / Libellé
        row3 = QHBoxLayout()
        row3.setSpacing(8)
        lbl_obs = QLabel("Obs / Libellé :")
        self.obs_edit = QLineEdit()
        self.obs_edit.setPlaceholderText("Description, article, Régler, Mise à jour...")

        row3.addWidget(lbl_obs)
        row3.addWidget(self.obs_edit, stretch=1)
        fb_layout.addLayout(row3)

        layout.addWidget(form_box)

        # 4. Horizontal Helper Converter Section (Calculateur de Conversion de Titre)
        helper_box = QGroupBox("💡 Outil d'aide : Titre du Fournisseur & Conversion (Optionnel)")
        helper_box.setStyleSheet(
            "QGroupBox { font-weight: bold; color: #0284c7; border: 1px solid #7dd3fc; background: #f0f9ff; border-radius: 6px; margin-top: 4px; padding: 6px; }"
        )
        h_layout = QVBoxLayout(helper_box)
        h_layout.setSpacing(6)

        # Horizontal Converter inputs
        h_row = QHBoxLayout()
        h_row.setSpacing(8)

        lbl_base_p = QLabel("Titre Fournisseur :")
        self.inp_base_purity = QLineEdit()
        self.inp_base_purity.setPlaceholderText("ex: 750")
        self.inp_base_purity.setText(str(self.supplier.get("primary_purity") or "750"))
        self.inp_base_purity.setMaximumWidth(80)

        lbl_op_p = QLabel("Titre Pièce :")
        self.inp_op_purity = QLineEdit()
        self.inp_op_purity.setPlaceholderText("ex: 875")
        self.inp_op_purity.setText(str(self.supplier.get("primary_purity") or "750"))
        self.inp_op_purity.setMaximumWidth(80)

        lbl_raw_w = QLabel("Poids brut :")
        self.inp_raw_weight = QDoubleSpinBox()
        self.inp_raw_weight.setRange(-999999.999, 999999.999)
        self.inp_raw_weight.setDecimals(2)
        self.inp_raw_weight.setSuffix(" g")

        h_row.addWidget(lbl_base_p)
        h_row.addWidget(self.inp_base_purity)
        h_row.addWidget(lbl_op_p)
        h_row.addWidget(self.inp_op_purity)
        h_row.addWidget(lbl_raw_w)
        h_row.addWidget(self.inp_raw_weight, stretch=1)
        h_layout.addLayout(h_row)

        self.lbl_converted_res = QLabel("Saisissez le poids brut et le titre de la pièce pour la conversion automatique")
        self.lbl_converted_res.setStyleSheet("font-weight: bold; color: #0369a1; font-size: 12px;")
        h_layout.addWidget(self.lbl_converted_res)

        layout.addWidget(helper_box)

        # Apply touch styling
        for widget in (
            self.date_edit,
            self.poids_spin,
            self.afacon_edit,
            self.montant_spin,
            self.obs_edit,
            self.color_combo,
            self.inp_base_purity,
            self.inp_op_purity,
            self.inp_raw_weight,
        ):
            apply_touch_input_defaults(widget)

        # 5. Dialog Action Buttons (Save & Cancel only)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        save_btn = buttons.button(QDialogButtonBox.Save)
        cancel_btn = buttons.button(QDialogButtonBox.Cancel)

        save_btn.setText("Enregistrer")
        cancel_btn.setText("Annuler")
        apply_touch_button_defaults(save_btn, primary=True)
        apply_touch_button_defaults(cancel_btn)

        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _connect_helper_signals(self):
        self.poids_spin.valueChanged.connect(self._on_poids_manual_change)
        self.afacon_edit.textChanged.connect(self._auto_calc_montant)

        self.inp_base_purity.textChanged.connect(self._recalc_converted_weight)
        self.inp_op_purity.textChanged.connect(self._recalc_converted_weight)
        self.inp_raw_weight.valueChanged.connect(self._recalc_converted_weight)

    def _on_poids_manual_change(self):
        if not self.is_auto_updating:
            self._auto_calc_montant()

    def _auto_calc_montant(self):
        poids = self.poids_spin.value()
        afacon_str = self.afacon_edit.text().strip().replace(",", ".")
        try:
            afacon = float(afacon_str)
        except ValueError:
            afacon = 0.0

        if abs(poids) > 0.0001 and afacon > 0:
            sign = -1 if poids < 0 else 1
            montant = sign * round(abs(poids) * afacon)
            self.montant_spin.blockSignals(True)
            self.montant_spin.setValue(montant)
            self.montant_spin.blockSignals(False)

    def _recalc_converted_weight(self):
        raw_w = self.inp_raw_weight.value()
        op_purity_str = self.inp_op_purity.text().strip().replace(",", ".")
        base_purity_str = self.inp_base_purity.text().strip().replace(",", ".")

        try:
            op_purity = float(op_purity_str)
        except ValueError:
            op_purity = 0.0

        try:
            base_purity = float(base_purity_str)
        except ValueError:
            base_purity = 750.0

        if abs(raw_w) > 0.0001 and op_purity > 0 and base_purity > 0:
            converted_w = raw_w * (op_purity / base_purity)
            
            # Automatically write into main Poids (g) field in real-time
            self.is_auto_updating = True
            self.poids_spin.setValue(converted_w)
            self.is_auto_updating = False
            self._auto_calc_montant()

            self.lbl_converted_res.setText(
                f"✅ Poids équivalent automatique (Titre {base_purity:g}) : {converted_w:.2f} g"
            )
        else:
            self.lbl_converted_res.setText("Saisissez le poids brut et le titre de la pièce pour la conversion automatique")

    def _apply_regler_preset(self):
        if not self.obs_edit.text():
            self.obs_edit.setText("Régler")
        if self.poids_spin.value() > 0:
            self.poids_spin.setValue(-abs(self.poids_spin.value()))
        if self.montant_spin.value() > 0:
            self.montant_spin.setValue(-abs(self.montant_spin.value()))
        self.color_combo.setCurrentIndex(1)

    def _populate(self):
        if not self.operation:
            return

        op_date = self.operation.get("operation_date")
        if op_date:
            if isinstance(op_date, str):
                try:
                    qd = QDate.fromString(op_date[:10], "yyyy-MM-dd")
                    if qd.isValid():
                        self.date_edit.setDate(qd)
                except Exception:
                    pass
            elif hasattr(op_date, "year"):
                self.date_edit.setDate(QDate(op_date.year, op_date.month, op_date.day))

        op_type = str(self.operation.get("operation_type") or "INCOMING").upper()
        weight = float(self.operation.get("weight_g") or 0.0)
        amount = float(self.operation.get("amount_da") or 0.0)

        if op_type == "OUTGOING":
            weight = -abs(weight)
            amount = -abs(amount)

        self.poids_spin.setValue(weight)
        self.montant_spin.setValue(amount)

        afacon = str(self.operation.get("afacon") or "0")
        if afacon in ("0", "0.00", "0.0"):
            afacon = "0"
        self.afacon_edit.setText(afacon)

        raw_obs = str(self.operation.get("description") or self.operation.get("notes") or "")
        is_red = False
        if "[COLOR:RED]" in raw_obs:
            is_red = True
            raw_obs = raw_obs.replace("[COLOR:RED]", "").strip()

        self.obs_edit.setText(raw_obs)
        if is_red or weight < 0 or amount < 0 or "régler" in raw_obs.lower() or "regler" in raw_obs.lower() or "mise a jour" in raw_obs.lower():
            self.color_combo.setCurrentIndex(1)

    def _save(self):
        supplier_id = int(self.supplier.get("id") or 0)
        if not supplier_id:
            QMessageBox.warning(self, "Attention", "Veuillez sélectionner un fournisseur valide.")
            return

        poids = self.poids_spin.value()
        montant = self.montant_spin.value()
        afacon_str = self.afacon_edit.text().strip() or "0"
        obs = self.obs_edit.text().strip()
        op_date = self.date_edit.date().toString("yyyy-MM-dd")

        if self.color_combo.currentIndex() == 1 or self.color_combo.currentData() == "RED":
            if "[COLOR:RED]" not in obs:
                obs += " [COLOR:RED]"
        else:
            if "[COLOR:RED]" in obs:
                obs = obs.replace("[COLOR:RED]", "").strip()

        op_type = "OUTGOING" if (poids < 0 or montant < 0) else "INCOMING"

        try:
            afacon_val = float(afacon_str.replace(",", "."))
        except ValueError:
            afacon_val = 0.0

        payload = {
            "supplier_id": supplier_id,
            "operation_date": op_date,
            "operation_type": op_type,
            "weight_g": abs(poids),
            "afacon": abs(afacon_val),
            "amount_da": abs(montant),
            "description": obs,
            "notes": obs,
            "user_id": self.current_user.get("id"),
        }

        service = self._service()
        if self.result_id:
            ok = service.update_operation(int(self.result_id), **payload) if hasattr(service, "update_operation") else True
            if not ok:
                QMessageBox.critical(self, "Erreur", "Impossible de mettre à jour l'opération.")
                return
        else:
            new_id = service.record_operation(**payload) if hasattr(service, "record_operation") else None
            if not new_id:
                pass
        self.accept()
