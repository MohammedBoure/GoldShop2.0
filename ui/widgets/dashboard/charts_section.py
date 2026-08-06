# ui/widgets/dashboard/charts_section.py

import logging
from datetime import date, datetime, timedelta
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QFrame, QGraphicsDropShadowEffect, QSizePolicy
from PySide6.QtCharts import (QChart, QChartView, QSplineSeries, QDateTimeAxis, 
                              QValueAxis, QAreaSeries)
from PySide6.QtCore import Qt, QDateTime, QTime, QPointF, QMargins
from PySide6.QtGui import QPainter, QColor, QPen, QFont, QLinearGradient, QGradient

class ChartsSection(QWidget):
    def __init__(self):
        super().__init__()
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # حاوية للشارت مع ظل خفيف وأنيق
        container = QFrame()
        container.setMinimumHeight(260)
        container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        container.setStyleSheet("background-color: white; border-radius: 15px; border: 1px solid #f0f0f0;")
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 10))
        shadow.setOffset(0, 5)
        container.setGraphicsEffect(shadow)
        
        cont_layout = QVBoxLayout(container)
        cont_layout.setContentsMargins(10, 10, 10, 10)

        # إعداد الشارت
        self.chart = QChart()
        self.chart.setTitle("📈 Évolution du Chiffre d'Affaires (30 derniers jours)")
        self.chart.setTitleFont(QFont("Segoe UI", 14, QFont.Bold))
        self.chart.setAnimationOptions(QChart.SeriesAnimations)
        self.chart.setMargins(QMargins(10, 10, 10, 10))
        self.chart.setBackgroundRoundness(0)

        self.chart_view = QChartView(self.chart)
        self.chart_view.setMinimumHeight(240)
        self.chart_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.chart_view.setRenderHint(QPainter.Antialiasing)
        self.chart_view.setStyleSheet("background: transparent;")
        cont_layout.addWidget(self.chart_view)

        layout.addWidget(container)
        self._apply_chart_theme()

    def _theme_colors(self):
        app = QApplication.instance()
        if app is None:
            return {
                "surface": QColor("#ffffff"),
                "background": QColor("#f4f7fa"),
                "text": QColor("#2c3e50"),
                "muted": QColor("#7f8c8d"),
                "grid": QColor("#ecf0f1"),
            }
        palette = app.palette()
        return {
            "surface": palette.base().color(),
            "background": palette.window().color(),
            "text": palette.text().color(),
            "muted": palette.placeholderText().color(),
            "grid": palette.mid().color(),
        }

    def _apply_chart_theme(self):
        colors = self._theme_colors()
        self.chart.setBackgroundBrush(colors["surface"])
        self.chart.setPlotAreaBackgroundBrush(colors["background"])
        self.chart.setPlotAreaBackgroundVisible(True)
        self.chart.setTitleBrush(colors["text"])
        self.chart.legend().setLabelBrush(colors["text"])
        for axis in self.chart.axes():
            axis.setLabelsColor(colors["muted"])
            axis.setGridLineColor(colors["grid"])

    def update_data(self, sales_trend):
        """تحديث بيانات الشارت لعرض المبيعات فقط بشكل واسع وجميل"""
        colors = self._theme_colors()
        self.chart.removeAllSeries()
        for ax in self.chart.axes():
            self.chart.removeAxis(ax)

        # خط المبيعات (أزرق)
        series_sales = QSplineSeries()
        series_sales.setName("Ventes (DZD)")
        pen_sales = QPen(QColor("#2980b9"))
        pen_sales.setWidth(4) # خط سميك وواضح
        series_sales.setPen(pen_sales)

        # توليد بيانات 30 يوم 
        today = date.today()
        start_date = today - timedelta(days=29)

        # 🟢 تم التصحيح هنا: استخدام 'daily_value' بدلاً من 'total_sales'
        sales_dict = {str(row['date']): float(row.get('daily_value') or 0.0) for row in sales_trend} if sales_trend else {}

        pts_sales = []
        max_val = 1000 # قيمة مبدئية لكي لا يكون الشارت فارغاً تماماً

        for i in range(30):
            current_date = start_date + timedelta(days=i)
            date_str = str(current_date)

            s_val = sales_dict.get(date_str, 0.0)
            if s_val > max_val: 
                max_val = s_val

            dt_ms = QDateTime(current_date, QTime(0, 0)).toMSecsSinceEpoch()
            pts_sales.append(QPointF(dt_ms, s_val))

        series_sales.append(pts_sales)

        # تلوين المنطقة تحت الخط بتدرج لوني أزرق أنيق
        area_sales = QAreaSeries(series_sales)
        area_sales.setName("Volume Ventes")
        gradient = QLinearGradient(QPointF(0, 0), QPointF(0, 1))
        gradient.setCoordinateMode(QGradient.ObjectBoundingMode)
        gradient.setColorAt(0.0, QColor(41, 128, 185, 120)) # أزرق شفاف في الأعلى
        gradient.setColorAt(1.0, QColor(41, 128, 185, 0))   # شفاف تماماً في الأسفل
        area_sales.setBrush(gradient)
        area_sales.setPen(QPen(Qt.PenStyle.NoPen))

        self.chart.addSeries(area_sales)
        self.chart.addSeries(series_sales)

        # إخفاء تكرار اسم السلسلة في مفتاح الشارت
        for marker in self.chart.legend().markers(area_sales): marker.setVisible(False)

        # --- المحاور ---
        # محور X (التاريخ)
        axis_x = QDateTimeAxis()
        axis_x.setTickCount(min(len(pts_sales), 8)) # عدد النقاط في الأسفل
        axis_x.setFormat("dd MMM")
        axis_x.setRange(QDateTime(start_date, QTime(0,0)), QDateTime(today, QTime(0,0)))
        axis_x.setLabelsFont(QFont("Segoe UI", 10, QFont.Bold))
        axis_x.setLabelsColor(colors["muted"])
        axis_x.setGridLineColor(colors["grid"])
        self.chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)

        # محور Y (القيمة)
        axis_y = QValueAxis()
        axis_y.setRange(0, max_val * 1.2) # زيادة 20% للأعلى لكي لا يلمس الخط السقف
        axis_y.setLabelFormat("%.0f DA")
        axis_y.setLabelsFont(QFont("Segoe UI", 10, QFont.Bold))
        axis_y.setLabelsColor(colors["muted"])
        axis_y.setGridLineColor(colors["grid"])
        self.chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)

        # ربط السلاسل بالمحاور
        series_sales.attachAxis(axis_x)
        series_sales.attachAxis(axis_y)
        area_sales.attachAxis(axis_x)
        area_sales.attachAxis(axis_y)

        # إعدادات مفتاح الشارت
        self.chart.legend().setVisible(True)
        self.chart.legend().setAlignment(Qt.AlignTop)
        self.chart.legend().setFont(QFont("Segoe UI", 11, QFont.Bold))
        self._apply_chart_theme()
