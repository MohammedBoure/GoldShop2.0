# ui/widgets/dashboard/alerts_section.py

import logging
from PySide6.QtWidgets import (QFrame, QVBoxLayout, QTableWidget, QTableWidgetItem, 
                               QHeaderView, QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                               QButtonGroup, QComboBox)
from PySide6.QtGui import QColor, QFont, QBrush
from PySide6.QtCore import Qt

class AlertsSection(QFrame):
    def __init__(self, data_manager=None):
        super().__init__()
        self.all_data = [] 
        self.active_filter = "All"
        self.init_ui()

    def init_ui(self):
        self.setObjectName("AlertsSection")
        self.setStyleSheet("""
            #AlertsSection { background: white; border-radius: 12px; border: 1px solid #ecf0f1; }
            QTableWidget { border: none; gridline-color: #f8f9fa; }
            QHeaderView::section { background-color: #f8f9fa; border: none; font-weight: bold; color: #7f8c8d; padding: 10px; }
            QLineEdit, QComboBox { border: 1px solid #dcdde1; border-radius: 6px; padding: 6px; background: #fdfdfd; }
            QPushButton { padding: 6px 12px; border-radius: 15px; font-weight: bold; border: 1px solid #dcdde1; background: #f8f9fa; color: #7f8c8d; }
            QPushButton:checked { background: #007572; color: white; border: none; }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # 1. أزرار الفلترة
        type_layout = QHBoxLayout()
        self.btn_group = QButtonGroup(self)
        self.btn_all = QPushButton("Tout")
        self.btn_urgent = QPushButton("Urgents 🚨")
        self.btn_stock = QPushButton("Stocks Dormants 📦")

        for i, btn in enumerate([self.btn_all, self.btn_urgent, self.btn_stock]):
            btn.setCheckable(True)
            self.btn_group.addButton(btn, i)
        self.btn_all.setChecked(True)
        self.btn_group.idClicked.connect(self.on_filter_clicked)
        
        type_layout.addWidget(self.btn_all)
        type_layout.addWidget(self.btn_urgent)
        type_layout.addWidget(self.btn_stock)
        type_layout.addStretch()
        layout.addLayout(type_layout)

        # 2. الجدول
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["PRODUIT", "FAMILLE", "TYPE", "VALEUR", "DÉTAILS"])
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        
        layout.addWidget(self.table)

    def on_filter_clicked(self, id):
        filters = ["All", "Urgente", "Stock"]
        self.active_filter = filters[id]
        self.refresh_table_view()

    def update_alerts(self, alerts):
        self.all_data = alerts
        self.refresh_table_view()

    def refresh_table_view(self):
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        
        filtered = []
        for a in self.all_data:
            if self.active_filter != "All" and self.active_filter != a['Type']:
                continue
            filtered.append(a)
        
        for row, a in enumerate(filtered):
            self.table.insertRow(row)
            
            p_item = QTableWidgetItem(str(a['Product']))
            p_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
            
            fam_item = QTableWidgetItem(str(a.get('Family', '-')))
            
            t_item = QTableWidgetItem(str(a['Type']))
            t_item.setTextAlignment(Qt.AlignCenter)
            
            v_item = QTableWidgetItem(str(a['Val']))
            v_item.setTextAlignment(Qt.AlignCenter)
            
            d_item = QTableWidgetItem(str(a['Details']))

            # الألوان حسب النوع
            text_color = QColor("#2c3e50")
            if a['Type'] == "Urgente": text_color = QColor("#c0392b")
            elif a['Type'] == "Stock": text_color = QColor("#d35400")

            for item in [p_item, fam_item, t_item, v_item, d_item]:
                item.setForeground(QBrush(text_color))

            self.table.setItem(row, 0, p_item)
            self.table.setItem(row, 1, fam_item)
            self.table.setItem(row, 2, t_item)
            self.table.setItem(row, 3, v_item)
            self.table.setItem(row, 4, d_item)

        self.table.setSortingEnabled(True)