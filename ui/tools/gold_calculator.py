# ui/tools/gold_calculator.py

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QPushButton, QComboBox, QTabWidget, QWidget, QFrame, QApplication
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QClipboard
import qtawesome as qta

class GoldCalculatorDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Calculatrice du Bijoutier (Hsab Dhab)")
        self.setFixedSize(400, 520)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint) 
        
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        tabs = QTabWidget()
        tabs.addTab(self.create_money_tab(), "Argent <-> Or")
        tabs.addTab(self.create_purity_tab(), "Conversion Titre (Casse)")
        
        layout.addWidget(tabs)

    def create_money_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(15)

        # --- القسم 1: تحويل المال إلى ذهب ---
        grp1 = self.create_group("Convertir DA en Poids")
        l1 = QVBoxLayout(grp1)
        
        self.inp_amount = QLineEdit()
        self.inp_amount.setPlaceholderText("Montant (ex: 20 000 000)")
        
        self.inp_price = QLineEdit()
        self.inp_price.setPlaceholderText("Prix du Gramme (ex: 17150)")
        
        self.lbl_result_weight = QLabel("Resultat: 0.00 g")
        self.lbl_result_weight.setStyleSheet("font-size: 18px; font-weight: bold; color: #27ae60;")
        
        btn_calc_weight = QPushButton("Calculer Poids")
        btn_calc_weight.clicked.connect(self.calc_money_to_weight)
        
        l1.addWidget(QLabel("Montant (DA):"))
        l1.addWidget(self.inp_amount)
        l1.addWidget(QLabel("Prix Unitaire (DA/g):"))
        l1.addWidget(self.inp_price)
        l1.addWidget(btn_calc_weight)
        l1.addWidget(self.lbl_result_weight)
        
        layout.addWidget(grp1)

        # --- القسم 2: تحويل الذهب إلى مال ---
        grp2 = self.create_group("Convertir Poids en DA")
        l2 = QVBoxLayout(grp2)
        
        self.inp_weight_rev = QLineEdit()
        self.inp_weight_rev.setPlaceholderText("Poids (g)")
        
        self.inp_price_rev = QLineEdit()
        self.inp_price_rev.setPlaceholderText("Prix du Gramme")
        
        self.lbl_result_money = QLabel("Resultat: 0.00 DA")
        self.lbl_result_money.setStyleSheet("font-size: 18px; font-weight: bold; color: #c0392b;")
        
        btn_calc_money = QPushButton("Calculer Montant")
        btn_calc_money.clicked.connect(self.calc_weight_to_money)
        
        l2.addWidget(QLabel("Poids (g):"))
        l2.addWidget(self.inp_weight_rev)
        l2.addWidget(QLabel("Prix Unitaire (DA/g):"))
        l2.addWidget(self.inp_price_rev)
        l2.addWidget(btn_calc_money)
        l2.addWidget(self.lbl_result_money)
        
        layout.addWidget(grp2)
        layout.addStretch()
        
        return widget

    def create_purity_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(20)
        
        info = QLabel("Convertir le poids selon le titre.\nSélectionnez dans la liste ou tapez directement un chiffre (ex: 800).")
        info.setWordWrap(True)
        info.setStyleSheet("color: #555; font-style: italic; font-size: 12px;")
        layout.addWidget(info)

        # المدخلات
        self.inp_purity_weight = QLineEdit()
        self.inp_purity_weight.setPlaceholderText("Poids d'origine (g)")
        self.inp_purity_weight.setStyleSheet("font-size: 14px; padding: 5px; font-weight: bold;")
        
        layout.addWidget(QLabel("Poids Actuel (g):"))
        layout.addWidget(self.inp_purity_weight)

        # القوائم المنسدلة للعيار
        h_layout = QHBoxLayout()
        
        self.combo_from = QComboBox()
        self.combo_to = QComboBox()
        
        # تفعيل الكتابة اليدوية بدون QDoubleValidator لمنع التعارض مع النصوص
        self.combo_from.setEditable(True)
        self.combo_from.lineEdit().setPlaceholderText("ex: 750")
        
        self.combo_to.setEditable(True)
        self.combo_to.lineEdit().setPlaceholderText("ex: 705")

        # تعبئة العيارات المعروفة
        purities = [("24k (999)", 999.9), ("21k (875)", 875.0), ("18k Imp (750)", 750.0), 
                    ("18k Loc (710)", 710.0), ("18k Loc (705)", 705.0), ("18k (700)", 700.0)]
        
        for name, val in purities:
            self.combo_from.addItem(name, val)
            self.combo_to.addItem(name, val)
            
        # الافتراضي: من 750 إلى 705
        self.combo_from.setCurrentIndex(2) # 750
        self.combo_to.setCurrentIndex(4)   # 705
        
        v_l1 = QVBoxLayout()
        v_l1.addWidget(QLabel("De (Titre Origine):"))
        v_l1.addWidget(self.combo_from)
        
        v_l2 = QVBoxLayout()
        v_l2.addWidget(QLabel("Vers (Titre Cible):"))
        v_l2.addWidget(self.combo_to)

        h_layout.addLayout(v_l1)
        h_layout.addSpacing(10)
        h_layout.addLayout(v_l2)
        
        layout.addLayout(h_layout)
        
        # الزر والنتيجة
        btn_convert = QPushButton("Convertir (Tasser)")
        btn_convert.setIcon(qta.icon("fa5s.exchange-alt"))
        btn_convert.setStyleSheet("background-color: #2980b9; color: white; font-weight: bold; padding: 10px; border-radius: 5px;")
        btn_convert.clicked.connect(self.calc_purity)
        
        layout.addWidget(btn_convert)
        
        self.lbl_purity_res = QLabel("0.000 g")
        self.lbl_purity_res.setAlignment(Qt.AlignCenter)
        self.lbl_purity_res.setStyleSheet("""
            font-size: 32px; font-weight: 800; color: #d4af37; 
            border: 2px solid #d4af37; border-radius: 10px; padding: 15px; background: white;
        """)
        
        layout.addWidget(self.lbl_purity_res)
        
        # زر النسخ
        btn_copy = QPushButton("Copier le résultat")
        btn_copy.setFlat(True)
        btn_copy.setIcon(qta.icon("fa5s.copy"))
        btn_copy.clicked.connect(self.copy_result)
        layout.addWidget(btn_copy)
        
        layout.addStretch()
        return widget

    def create_group(self, title):
        grp = QFrame()
        grp.setStyleSheet(".QFrame { border: 1px solid #ccc; border-radius: 6px; background: #f9f9f9; }")
        return grp

    # --- المنطق الحسابي ---

    def get_float(self, text):
        try:
            return float(text.replace(',', '.').replace(' ', ''))
        except ValueError:
            return 0.0

    def get_combo_value(self, combo):
        """دالة ذكية: تقرأ ما كتبه المستخدم أولاً، وإذا لم يكن رقماً تأخذ القيمة من القائمة"""
        text = combo.currentText().strip()
        
        # 1. نحاول تحويل النص المكتوب إلى رقم (مثلاً كتب المستخدم 800)
        try:
            return float(text.replace(',', '.'))
        except ValueError:
            # 2. إذا فشل التحويل (لأن النص هو "18k (750)"), نأخذ القيمة المخزنة في القائمة
            idx = combo.currentIndex()
            if idx != -1:
                val = combo.itemData(idx)
                if val is not None:
                    return float(val)
        return 0.0

    def calc_money_to_weight(self):
        amount = self.get_float(self.inp_amount.text())
        price = self.get_float(self.inp_price.text())
        
        if price > 0:
            weight = amount / price
            self.lbl_result_weight.setText(f"{weight:.2f} g")
        else:
            self.lbl_result_weight.setText("Erreur")

    def calc_weight_to_money(self):
        weight = self.get_float(self.inp_weight_rev.text())
        price = self.get_float(self.inp_price_rev.text())
        
        amount = weight * price
        self.lbl_result_money.setText(f"{amount:,.2f} DA")

    def calc_purity(self):
        weight = self.get_float(self.inp_purity_weight.text())
        
        p_from = self.get_combo_value(self.combo_from)
        p_to = self.get_combo_value(self.combo_to)
        
        if p_to > 0 and p_from > 0:
            new_weight = weight * (p_from / p_to)
            self.lbl_purity_res.setText(f"{new_weight:.3f}")
        else:
            self.lbl_purity_res.setText("Erreur (Vérifiez les titres)")

    def copy_result(self):
        clipboard = QApplication.clipboard()
        text = self.lbl_purity_res.text().replace(' g', '')
        clipboard.setText(text)