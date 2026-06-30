# ui/tools/barcode_generator.py

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton
)
from PySide6.QtCore import Qt
import qtawesome as qta
import random
import string

class BarcodeGeneratorDialog(QDialog):
    def __init__(self, manager, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.setWindowTitle("Générateur de Code-barres")
        self.setFixedSize(450, 350)
        self.setStyleSheet("QDialog { background-color: #ecf0f1; }")
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        lbl_title = QLabel("Création de Code-barres (Article)")
        lbl_title.setStyleSheet("font-size: 18px; font-weight: bold; color: #2c3e50;")
        lbl_title.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl_title)

        self.inp_code = QLineEdit()
        self.inp_code.setPlaceholderText("Appuyez sur générer...")
        self.inp_code.setReadOnly(True)
        self.inp_code.setAlignment(Qt.AlignCenter)
        self.inp_code.setStyleSheet("font-size: 24px; font-weight: bold; padding: 15px; border: 2px solid #bdc3c7; border-radius: 8px; background-color: white; color: #d35400;")
        layout.addWidget(self.inp_code)
        
        btn_generate = QPushButton(" Générer un Code Aléatoire")
        btn_generate.setIcon(qta.icon("fa5s.random", color="white"))
        btn_generate.setFixedHeight(60) # زر كبير للمس
        btn_generate.setStyleSheet("background-color: #2980b9; color: white; font-weight: bold; font-size: 16px; border-radius: 8px;")
        btn_generate.clicked.connect(self.generate_random)
        layout.addWidget(btn_generate)
        
        # شكل رمزي للباركود
        self.lbl_display = QLabel("||| || ||| | |||")
        self.lbl_display.setAlignment(Qt.AlignCenter)
        self.lbl_display.setStyleSheet("font-size: 40px; color: #bdc3c7; font-weight: 900;")
        layout.addWidget(self.lbl_display)
        
        layout.addStretch()

        btn_close = QPushButton(" Fermer")
        btn_close.setIcon(qta.icon("fa5s.times", color="white"))
        btn_close.setFixedHeight(60) # زر كبير للمس
        btn_close.setStyleSheet("background-color: #e74c3c; color: white; font-weight: bold; font-size: 16px; border-radius: 8px;")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)

    def generate_random(self):
        # توليد كود باركود احترافي (مثال: GS-847291)
        prefix = "GS" 
        random_nums = ''.join(random.choices(string.digits, k=6))
        code = f"{prefix}-{random_nums}"
        
        self.inp_code.setText(code)
        self.lbl_display.setStyleSheet("font-size: 40px; color: #2c3e50; font-weight: 900; letter-spacing: 2px;")
        self.lbl_display.setText(f"||| {random_nums} |||")