# ui/widgets/inventory/margin_update_dialog.py

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QDoubleSpinBox,
    QComboBox, QMessageBox, QGroupBox, QFormLayout
)
from PySide6.QtCore import Qt

from ui.dialogs.touch_dialog import TouchDialogMixin
from ui.touch_design import apply_touch_input_defaults


class MarginUpdateDialog(TouchDialogMixin, QDialog):
    def __init__(self, manager, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.setWindowTitle("Mise à jour de la Marge par Poids")
        self.setMinimumSize(560, 420)
        self.setStyleSheet("QDialog { background-color: #f4f7fa; }")
        self.init_ui()
        self.setup_touch_dialog(size="compact")

    def init_ui(self):
        layout = QVBoxLayout(self)

        # العنوان
        header_label = QLabel("⚖️ Mettre à jour la marge selon le poids")
        header_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #2980b9; margin-bottom: 10px;")
        header_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(header_label)

        # صندوق الإعدادات
        group_box = QGroupBox("Paramètres de mise à jour")
        group_box.setStyleSheet("""
            QGroupBox { font-weight: bold; border: 2px solid #bdc3c7; border-radius: 8px; 
            margin-top: 10px; padding: 15px; background-color: white; }
        """)
        form_layout = QFormLayout(group_box)
        form_layout.setSpacing(15)

        input_style = "font-size: 15px; font-weight: bold; padding: 5px; border: 1px solid #bdc3c7; border-radius: 5px; background-color: #f9f9f9;"

        # 1. نطاق الوزن (من - إلى)
        weight_layout = QHBoxLayout()
        self.spin_min_weight = QDoubleSpinBox()
        self.spin_min_weight.setRange(0, 10000)
        self.spin_min_weight.setDecimals(2)
        self.spin_min_weight.setSuffix(" g")
        self.spin_min_weight.setStyleSheet(input_style)
        apply_touch_input_defaults(self.spin_min_weight)

        self.spin_max_weight = QDoubleSpinBox()
        self.spin_max_weight.setRange(0, 10000)
        self.spin_max_weight.setDecimals(2)
        self.spin_max_weight.setValue(5.0) # قيمة افتراضية
        self.spin_max_weight.setSuffix(" g")
        self.spin_max_weight.setStyleSheet(input_style)
        apply_touch_input_defaults(self.spin_max_weight)

        lbl_to = QLabel(" à ")
        lbl_to.setStyleSheet("font-weight: bold; font-size: 14px;")

        weight_layout.addWidget(self.spin_min_weight)
        weight_layout.addWidget(self.create_numpad_button(self.spin_min_weight, "Poids minimum"))
        weight_layout.addWidget(lbl_to)
        weight_layout.addWidget(self.spin_max_weight)
        weight_layout.addWidget(self.create_numpad_button(self.spin_max_weight, "Poids maximum"))

        form_layout.addRow("Nid de Poids (De - À) :", weight_layout)

        # 2. نوع الفائدة
        self.combo_margin_type = QComboBox()
        self.combo_margin_type.addItem("Pourcentage (%)", "PERCENTAGE")
        self.combo_margin_type.addItem("Fixe (DA/g)", "FIXED")
        self.combo_margin_type.setStyleSheet(input_style)
        self.combo_margin_type.currentIndexChanged.connect(self.update_suffix)
        apply_touch_input_defaults(self.combo_margin_type)
        form_layout.addRow("Type de Marge :", self.combo_margin_type)

        # 3. الفائدة الجديدة
        margin_layout = QHBoxLayout()
        self.spin_new_margin = QDoubleSpinBox()
        self.spin_new_margin.setRange(0, 1000000)
        self.spin_new_margin.setDecimals(2)
        self.spin_new_margin.setSuffix(" %")
        self.spin_new_margin.setStyleSheet(input_style + "background-color: #e8f8f5; color: #27ae60;")
        apply_touch_input_defaults(self.spin_new_margin)
        margin_layout.addWidget(self.spin_new_margin)
        margin_layout.addWidget(self.create_numpad_button(self.spin_new_margin, "Nouvelle marge"))
        form_layout.addRow("Nouvelle Marge :", margin_layout)

        layout.addWidget(group_box)

        # الأزرار
        footer, _buttons = self.create_touch_footer(
            primary_text="Mettre à jour",
            cancel_text="Annuler",
            primary_slot=self.apply_update,
        )
        layout.addLayout(footer)

    def update_suffix(self):
        """تغيير الرمز % أو DA حسب نوع الفائدة المختار"""
        if self.combo_margin_type.currentData() == "PERCENTAGE":
            self.spin_new_margin.setSuffix(" %")
        else:
            self.spin_new_margin.setSuffix(" DA/g")

    def apply_update(self):
        min_w = self.spin_min_weight.value()
        max_w = self.spin_max_weight.value()
        m_type = self.combo_margin_type.currentData()
        n_margin = self.spin_new_margin.value()

        if min_w > max_w:
            QMessageBox.warning(self, "Erreur", "Le poids minimum ne peut pas être supérieur au poids maximum.")
            return

        suffix_str = "%" if m_type == "PERCENTAGE" else "DA/g"
        
        reply = QMessageBox.question(
            self, "Confirmation",
            f"Voulez-vous vraiment appliquer une marge de {n_margin} {suffix_str}\n"
            f"aux articles pesant entre {min_w}g et {max_w}g ?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            affected = self.manager.inventory.update_margin_by_weight_range(min_w, max_w, m_type, n_margin)
            
            if affected > 0:
                QMessageBox.information(self, "Succès", f"Mise à jour réussie.\n{affected} article(s) modifié(s).")
                self.accept()
            elif affected == 0:
                QMessageBox.information(self, "Info", "Aucun article trouvé dans cette plage de poids avec ce type de marge.")
            else:
                QMessageBox.critical(self, "Erreur", "Une erreur s'est produite lors de la mise à jour.")
