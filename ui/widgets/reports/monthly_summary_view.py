import calendar
from datetime import date, datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QLabel, QFrame
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QBrush
import qtawesome as qta

class MonthlySummaryView(QWidget):
    def __init__(self, manager):
        super().__init__()
        self.manager = manager
        self.init_ui()
        self.populate_filters()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # --- شريط الفلاتر العلوي ---
        filter_frame = QFrame()
        filter_frame.setStyleSheet("background-color: #f8f9fa; border-radius: 8px; padding: 10px;")
        row1 = QHBoxLayout(filter_frame)
        
        row1.addWidget(QLabel("<b>📅 Année :</b>"))
        self.combo_year = QComboBox()
        row1.addWidget(self.combo_year)
        
        row1.addSpacing(15)
        row1.addWidget(QLabel("<b>Mois :</b>"))
        self.combo_month = QComboBox()
        row1.addWidget(self.combo_month)
        
        row1.addSpacing(20)
        self.btn_search = QPushButton(" Afficher le Tableau")
        self.btn_search.setIcon(qta.icon("fa5s.calendar-alt", color="white"))
        self.btn_search.setStyleSheet("background-color: #6a1b9a; color: white; padding: 6px 15px; border-radius: 4px; font-weight: bold; font-size: 14px;")
        self.btn_search.clicked.connect(self.load_data)
        row1.addWidget(self.btn_search)
        row1.addStretch()
        
        layout.addWidget(filter_frame)

        # --- عنوان الصفحة ---
        self.lbl_main_title = QLabel("Recettes Du Mois")
        self.lbl_main_title.setStyleSheet("font-size: 20px; font-weight: bold; color: white; background-color: #6a1b9a; padding: 10px; border-radius: 5px;")
        self.lbl_main_title.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_main_title)

        # --- إعداد الجدول ---
        self.table = QTableWidget(0, 11) # 11 أعمدة
        self.table.setHorizontalHeaderLabels([
            "Jours", "Dates", "P.S", "Recettes DA", "O.c", "TPE", "Euro", "Dollar", "Vendeur", "Impos", "Bénéfice (Faaida)"
        ])
        
        # تنسيق الجدول ليشبه الصورة (اللون البنفسجي)
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: white; gridline-color: black; font-size: 14px; font-weight: bold;
            }
            QHeaderView::section {
                background-color: #6a1b9a; color: white; font-weight: bold; font-size: 14px; padding: 8px; border: 1px solid #4a148c;
            }
            QTableWidget::item {
                border-bottom: 1px solid #bdc3c7;
                border-right: 1px solid #bdc3c7;
            }
        """)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        
        header = self.table.horizontalHeader()
        for i in range(11):
            header.setSectionResizeMode(i, QHeaderView.Stretch if i in [3, 10] else QHeaderView.ResizeToContents)
            
        layout.addWidget(self.table)

    def populate_filters(self):
        current_date = datetime.now()
        for y in range(current_date.year - 2, current_date.year + 3):
            self.combo_year.addItem(str(y), y)
        self.combo_year.setCurrentText(str(current_date.year))
        
        months = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin", "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"]
        for i, m in enumerate(months, 1): 
            self.combo_month.addItem(m, i)
        self.combo_month.setCurrentIndex(current_date.month - 1)

    def get_french_day(self, date_obj):
        days = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
        return days[date_obj.weekday()]

    def load_data(self):
        self.table.setRowCount(0)
        year = self.combo_year.currentData()
        month = self.combo_month.currentData()
        month_name = self.combo_month.currentText()
        
        self.lbl_main_title.setText(f"Recettes Du Mois {month_name} {year}")

        # 1. الاستعلام المجمع: يجمع كل مبيعات اليوم في سطر واحد ويحسب الفائدة
        query = """
            SELECT 
                DATE(s.created_at) as sale_date,
                SUM(si.sold_weight_g) as total_ps,
                SUM(s.cash_paid_da) as total_recette,
                SUM(s.old_gold_weight_g) as total_oc,
                SUM(s.tpe_paid_da) as total_tpe,
                SUM(s.impos_weight_g) as total_impos,
                
                -- حساب الفائدة الصافية (سعر البيع ناقص التكلفة الأصلية)
                SUM(
                    si.total_price_da - 
                    IF(si.item_type = 'WEIGHT', 
                       (COALESCE(i.metal_cost_per_gram, 0) + COALESCE(i.labor_cost_per_gram, 0)) * si.sold_weight_g,
                       (COALESCE(i.metal_cost_per_gram, 0) + COALESCE(i.labor_cost_per_gram, 0)) * si.sold_quantity
                    )
                ) as total_benefice
                
            FROM Sales s
            JOIN SaleItems si ON s.id = si.sale_id
            LEFT JOIN Inventory i ON si.inventory_id = i.id
            WHERE YEAR(s.created_at) = %s AND MONTH(s.created_at) = %s AND s.status = 'COMPLETED'
            GROUP BY DATE(s.created_at)
        """
        
        try:
            with self.manager.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute(query, (year, month))
                results = cursor.fetchall()
                while cursor.nextset(): pass
                
                # تحويل النتائج إلى قاموس (Key = Date) لتسهيل البحث
                sales_by_date = {row['sale_date']: row for row in results}
                
                # Fetch Versement Payments
                cursor.execute("""
                    SELECT 
                        DATE(vp.payment_date) as pay_date,
                        SUM(CASE WHEN vp.montant_da > 0 AND COALESCE(vp.montant_euro, 0) = 0 AND COALESCE(vp.montant_dollar, 0) = 0 AND COALESCE(vp.or_casse_g, 0) = 0 THEN vp.montant_da ELSE 0 END) as total_vp_recette,
                        SUM(vp.montant_euro) as total_vp_euro,
                        SUM(vp.montant_dollar) as total_vp_dollar,
                        SUM(vp.or_casse_g) as total_vp_oc
                    FROM Versement_Payments vp
                    WHERE YEAR(vp.payment_date) = %s AND MONTH(vp.payment_date) = %s
                    GROUP BY DATE(vp.payment_date)
                """, (year, month))
                vp_results = cursor.fetchall()
                while cursor.nextset(): pass
                vp_by_date = {row['pay_date']: row for row in vp_results}
                
                num_days = calendar.monthrange(year, month)[1]
                
                sum_ps = sum_recettes = sum_oc = sum_tpe = sum_euro = sum_dollar = sum_impos = sum_benefice = 0.0

                for day in range(1, num_days + 1):
                    current_date = date(year, month, day)
                    day_name = self.get_french_day(current_date)
                    date_str = f"{day:02d}/{month:02d}/{year}"
                    
                    row_idx = self.table.rowCount()
                    self.table.insertRow(row_idx)
                    
                    item_day = QTableWidgetItem(day_name)
                    item_day.setTextAlignment(Qt.AlignCenter)
                    self.table.setItem(row_idx, 0, item_day)
                    
                    item_date = QTableWidgetItem(date_str)
                    item_date.setTextAlignment(Qt.AlignCenter)
                    self.table.setItem(row_idx, 1, item_date)

                    if current_date in sales_by_date or current_date in vp_by_date:
                        s_data = sales_by_date.get(current_date, {})
                        vp_data = vp_by_date.get(current_date, {})
                        
                        ps = float(s_data.get('total_ps') or 0)
                        recette = float(s_data.get('total_recette') or 0) + float(vp_data.get('total_vp_recette') or 0)
                        oc = float(s_data.get('total_oc') or 0) + float(vp_data.get('total_vp_oc') or 0)
                        tpe = float(s_data.get('total_tpe') or 0)
                        euro = float(vp_data.get('total_vp_euro') or 0)
                        dollar = float(vp_data.get('total_vp_dollar') or 0)
                        impos = float(s_data.get('total_impos') or 0)
                        benefice = float(s_data.get('total_benefice') or 0)
                        
                        # تجميع الإجماليات
                        sum_ps += ps
                        sum_recettes += recette
                        sum_oc += oc
                        sum_tpe += tpe
                        sum_euro += euro
                        sum_dollar += dollar
                        sum_impos += impos
                        sum_benefice += benefice

                        cols = [
                            f"{ps:.2f}" if ps else "0",
                            f"{recette:,.0f}" if recette else "0",
                            f"{oc:.2f}" if oc else "0",
                            f"{tpe:,.0f}" if tpe else "0",
                            f"{euro:,.0f}" if euro else "0",
                            f"{dollar:,.0f}" if dollar else "0",
                            "Multi",
                            f"{impos:.2f}" if impos else "0",
                            f"{benefice:,.2f}" # الفائدة (Bénéfice)
                        ]
                        
                        for col_idx, val in enumerate(cols, start=2):
                            item = QTableWidgetItem(val)
                            item.setTextAlignment(Qt.AlignCenter)
                            if col_idx == 10: # تلوين الفائدة بالأخضر
                                item.setForeground(QBrush(QColor("#27ae60")))
                            self.table.setItem(row_idx, col_idx, item)

                    else:
                        # حالة عدم وجود مبيعات في هذا اليوم (Repot)
                        for col_idx in range(2, 11):
                            item = QTableWidgetItem("Repot" if col_idx != 10 else "-")
                            item.setTextAlignment(Qt.AlignCenter)
                            item.setForeground(QBrush(QColor("red")))
                            self.table.setItem(row_idx, col_idx, item)

                # --- إضافة السطر الأخير للمجاميع (Totals) ---
                total_row_idx = self.table.rowCount()
                self.table.insertRow(total_row_idx)
                
                totals = [
                    "", "", 
                    f"{sum_ps:.2f}", f"{sum_recettes:,.0f}", f"{sum_oc:.2f}", 
                    f"{sum_tpe:,.0f}", f"{sum_euro:,.0f}", f"{sum_dollar:,.0f}", "", 
                    f"{sum_impos:.2f}", f"{sum_benefice:,.2f}"
                ]
                
                for col_idx, val in enumerate(totals):
                    item = QTableWidgetItem(val)
                    item.setTextAlignment(Qt.AlignCenter)
                    item.setFont(QFont("", 14, QFont.Bold))
                    item.setBackground(QBrush(QColor("#6a1b9a"))) # لون بنفسجي
                    item.setForeground(QBrush(QColor("white")))
                    self.table.setItem(total_row_idx, col_idx, item)

        except Exception as e:
            import logging
            logging.error(f"Erreur chargement résumé mensuel: {e}")
