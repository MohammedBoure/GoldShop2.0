from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout,
    QPushButton,QLabel,QDialog
)
from PySide6.QtCore import Qt
import qtawesome as qta


class WeightFilterDialog(QDialog):
    def __init__(self, current_min, current_max, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Filtre de Poids")
        self.setFixedSize(400, 450)
        self.setStyleSheet("QDialog { background-color: #f4f7fa; border: 2px solid #2c3e50; border-radius: 12px; }")
        
        self.val_min = float(current_min) if current_min is not None else 0.0
        self.val_max = float(current_max) if current_max is not None else 1000.0
        self.cleared = False 

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)

        header_lbl = QLabel("🎯 Filtrer par Poids (g)")
        header_lbl.setStyleSheet("font-size: 22px; font-weight: bold; color: #2c3e50; margin-bottom: 10px;")
        header_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(header_lbl)

        layout.addWidget(QLabel("Poids Minimum :"))
        self.btn_min = QPushButton(f"{self.val_min:.2f} g")
        self.btn_min.setFixedHeight(70)
        self.btn_min.setCursor(Qt.PointingHandCursor)
        self.btn_min.setStyleSheet(self.input_button_style())
        self.btn_min.clicked.connect(lambda: self.open_numpad("min"))
        layout.addWidget(self.btn_min)

        layout.addWidget(QLabel("Poids Maximum :"))
        self.btn_max = QPushButton(f"{self.val_max:.2f} g")
        self.btn_max.setFixedHeight(70)
        self.btn_max.setCursor(Qt.PointingHandCursor)
        self.btn_max.setStyleSheet(self.input_button_style())
        self.btn_max.clicked.connect(lambda: self.open_numpad("max"))
        layout.addWidget(self.btn_max)

        layout.addStretch()

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(15)

        self.btn_reset = QPushButton(" Réinitialiser")
        self.btn_reset.setIcon(qta.icon("fa5s.undo", color="white"))
        self.btn_reset.setFixedHeight(60)
        self.btn_reset.setStyleSheet("background-color: #7f8c8d; color: white; font-weight: bold; font-size: 16px; border-radius: 10px;")
        self.btn_reset.clicked.connect(self.clear_filter)

        self.btn_apply = QPushButton(" Appliquer")
        self.btn_apply.setIcon(qta.icon("fa5s.check", color="white"))
        self.btn_apply.setFixedHeight(60)
        self.btn_apply.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; font-size: 18px; border-radius: 10px;")
        self.btn_apply.clicked.connect(self.accept)

        btn_layout.addWidget(self.btn_reset, 1)
        btn_layout.addWidget(self.btn_apply, 2)
        layout.addLayout(btn_layout)

    def input_button_style(self):
        return """
            QPushButton {
                background-color: white; border: 2px solid #bdc3c7; border-radius: 12px;
                font-size: 24px; font-weight: bold; color: #3498db; text-align: center;
                padding: 5px; 
            }
            QPushButton:pressed { background-color: #ebf5fb; border-color: #3498db; }
        """

    def open_numpad(self, target):
        title = "Poids Minimum" if target == "min" else "Poids Maximum"
        initial = self.val_min if target == "min" else self.val_max
        
        from ui.tools.virtual_numpad import VirtualNumpad 
        pad = VirtualNumpad(title, allow_decimal=True, initial_value=initial, parent=self)
        
        if pad.exec() == QDialog.Accepted:
            val_str = pad.get_value()
            try:
                val = float(val_str) if val_str else 0.0
                if target == "min":
                    self.val_min = val
                    self.btn_min.setText(f"{val:.2f} g")
                else:
                    self.val_max = val
                    self.btn_max.setText(f"{val:.2f} g")
            except ValueError:
                pass

    def clear_filter(self):
        self.cleared = True
        self.accept()


