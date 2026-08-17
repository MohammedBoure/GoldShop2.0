# ui/widgets/dashboard/charts_section.py

import logging
from datetime import date, datetime, timedelta
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QGraphicsDropShadowEffect, QSizePolicy, QComboBox, QPushButton,
    QDateEdit, QButtonGroup
)
from PySide6.QtCharts import (
    QChart, QChartView, QBarSeries, QBarSet, QBarCategoryAxis, QValueAxis
)
from PySide6.QtCore import Qt, QDate, Signal, QMargins
from PySide6.QtGui import QPainter, QColor, QPen, QFont, QBrush


class MetricPill(QFrame):
    """عنصر بطاقة مصغرة لعرض إحصائيات سريعة في رأس الشارت"""
    def __init__(self, title: str, value: str, color: str = "#10b981", bg_color: str = "#ecfdf5", border_color: str = "#a7f3d0"):
        super().__init__()
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_color};
                border: 1px solid {border_color};
                border-radius: 8px;
                padding: 4px 8px;
            }}
        """)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(6)

        self.lbl_title = QLabel(title)
        self.lbl_title.setStyleSheet("color: #64748b; font-size: 11px; font-weight: 600; border: none; background: transparent;")

        self.lbl_value = QLabel(value)
        self.lbl_value.setStyleSheet(f"color: {color}; font-size: 12px; font-weight: 800; border: none; background: transparent;")

        layout.addWidget(self.lbl_title)
        layout.addWidget(self.lbl_value)

    def set_value(self, value: str, color: str = None, bg_color: str = None, border_color: str = None):
        self.lbl_value.setText(value)
        if color:
            self.lbl_value.setStyleSheet(f"color: {color}; font-size: 12px; font-weight: 800; border: none; background: transparent;")
        if bg_color and border_color:
            self.setStyleSheet(f"""
                QFrame {{
                    background-color: {bg_color};
                    border: 1px solid {border_color};
                    border-radius: 8px;
                    padding: 4px 8px;
                }}
            """)


class ChartsSection(QWidget):
    """
    قسم المخطط المالي الاحترافي (نمط أعمدة البورصة والتدفق المالي):
    - الأخضر: الداخل (المبيعات / الإيرادات)
    - الأحمر: الخارج (المشتريات / المصاريف / ديون الموردين)
    - فلاتر تاريخية ومحلية متكاملة:
      * اختيار تجميع كل عمود: يومي (Jour)، أسبوعي (Semaine)، شهري (Mois)
      * اختيار النطاق الزمني: مسبق (7، 15، 30، 90، 180، 365 يوم، الكل) أو مخصص (تاريخ بداية ونهاية)
      * نمط العرض: الداخل والخارج معاً، الداخل فقط، الخارج فقط، أو الصافي (Net)
    - بطاقات ملخص فوري وشريط تفاصيل تفاعلي عند تمرير الفأرة فوق أي عمود
    """

    filterChanged = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.stats_manager = None
        self._raw_sales_trend = []
        self._raw_purchases_trend = []
        self._processed_data = []
        self._hovered_index = -1

        self._init_ui()

    def set_stats_manager(self, stats_manager):
        """ربط مدير الإحصائيات لجلب البيانات المحدثة تلقائياً عند تغيير الفلاتر"""
        self.stats_manager = stats_manager

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # الحاوية الرئيسية مع ظل خفيف وأطراف مستديرة أنيقة
        self.container = QFrame()
        self.container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.container.setStyleSheet("""
            QFrame#chart_card {
                background-color: #ffffff;
                border-radius: 14px;
                border: 1px solid #e2e8f0;
            }
        """)
        self.container.setObjectName("chart_card")

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(16)
        shadow.setColor(QColor(15, 23, 42, 18))
        shadow.setOffset(0, 4)
        self.container.setGraphicsEffect(shadow)

        cont_layout = QVBoxLayout(self.container)
        cont_layout.setContentsMargins(16, 14, 16, 12)
        cont_layout.setSpacing(10)

        # 1. شريط العنوان والفلاتر العلوية
        top_header_layout = QHBoxLayout()
        top_header_layout.setSpacing(12)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)

        header_title_layout = QHBoxLayout()
        header_title_layout.setSpacing(8)

        self.lbl_icon = QLabel("📊")
        self.lbl_icon.setStyleSheet("font-size: 18px;")

        self.lbl_title = QLabel("Flux Financier & Analyse Commerciale")
        self.lbl_title.setStyleSheet("font-size: 15px; font-weight: 800; color: #1e293b;")

        header_title_layout.addWidget(self.lbl_icon)
        header_title_layout.addWidget(self.lbl_title)
        header_title_layout.addStretch()

        self.lbl_subtitle = QLabel("🟢 30 Derniers Jours • Par Jour • Style Bourse (Entrées / Sorties)")
        self.lbl_subtitle.setStyleSheet("font-size: 11px; font-weight: 600; color: #64748b;")

        title_box.addLayout(header_title_layout)
        title_box.addWidget(self.lbl_subtitle)

        top_header_layout.addLayout(title_box, 1)

        # 2. أزرار الفلاتر وعناصر التحكم
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(8)

        # اختيار التجميع لكل عمود (Granularité)
        lbl_gran = QLabel("Fréquence :")
        lbl_gran.setStyleSheet("font-size: 11px; font-weight: 700; color: #475569;")
        controls_layout.addWidget(lbl_gran)

        self.combo_granularity = QComboBox()
        self.combo_granularity.addItems(["📅 Par Jour", "📆 Par Semaine", "🗓️ Par Mois"])
        self.combo_granularity.setCurrentIndex(0)
        self.combo_granularity.setStyleSheet(self._control_style())
        self.combo_granularity.currentIndexChanged.connect(self._on_filter_changed)
        controls_layout.addWidget(self.combo_granularity)

        # اختيار النطاق الزمني (Time Range)
        lbl_range = QLabel("Historique :")
        lbl_range.setStyleSheet("font-size: 11px; font-weight: 700; color: #475569;")
        controls_layout.addWidget(lbl_range)

        self.combo_range = QComboBox()
        self.combo_range.addItems([
            "⚡ 7 Jours",
            "⚡ 15 Jours",
            "⚡ 30 Jours",
            "📅 3 Mois (90J)",
            "📅 6 Mois (180J)",
            "📅 1 An (365J)",
            "📅 Cette Année",
            "🌐 Tout l'historique",
            "⚙️ Personnalisé..."
        ])
        self.combo_range.setCurrentIndex(2) # 30 Jours
        self.combo_range.setStyleSheet(self._control_style())
        self.combo_range.currentIndexChanged.connect(self._on_range_preset_changed)
        controls_layout.addWidget(self.combo_range)

        # نمط العرض (View Mode)
        lbl_mode = QLabel("Vue :")
        lbl_mode.setStyleSheet("font-size: 11px; font-weight: 700; color: #475569;")
        controls_layout.addWidget(lbl_mode)

        self.combo_view_mode = QComboBox()
        self.combo_view_mode.addItems([
            "📊 Deux Colonnes (Entrées/Sorties)",
            "🟢 Entrées uniquement (Ventes)",
            "🔴 Sorties uniquement (Achats)",
            "⚖️ Solde Net (Bénéfice/Perte)"
        ])
        self.combo_view_mode.setCurrentIndex(0)
        self.combo_view_mode.setStyleSheet(self._control_style())
        self.combo_view_mode.currentIndexChanged.connect(self._refresh_chart_display)
        controls_layout.addWidget(self.combo_view_mode)

        top_header_layout.addLayout(controls_layout)
        cont_layout.addLayout(top_header_layout)

        # 3. شريط النطاق الزمني المخصص (يظهر عند اختيار 'Personnalisé...')
        self.custom_date_bar = QFrame()
        self.custom_date_bar.setStyleSheet("""
            QFrame {
                background-color: #f8fafc;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                padding: 4px;
            }
        """)
        self.custom_date_bar.setVisible(False)

        custom_layout = QHBoxLayout(self.custom_date_bar)
        custom_layout.setContentsMargins(8, 4, 8, 4)
        custom_layout.setSpacing(10)

        lbl_from = QLabel("Du :")
        lbl_from.setStyleSheet("font-weight: 700; color: #334155; font-size: 11px;")
        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDisplayFormat("dd/MM/yyyy")
        self.date_from.setDate(QDate.currentDate().addDays(-30))
        self.date_from.setStyleSheet(self._date_edit_style())

        lbl_to = QLabel("Au :")
        lbl_to.setStyleSheet("font-weight: 700; color: #334155; font-size: 11px;")
        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDisplayFormat("dd/MM/yyyy")
        self.date_to.setDate(QDate.currentDate())
        self.date_to.setStyleSheet(self._date_edit_style())

        self.btn_apply_custom = QPushButton("Appliquer la période")
        self.btn_apply_custom.setCursor(Qt.PointingHandCursor)
        self.btn_apply_custom.setStyleSheet("""
            QPushButton {
                background-color: #007572;
                color: white;
                font-weight: 700;
                font-size: 11px;
                border-radius: 6px;
                padding: 5px 12px;
                border: none;
            }
            QPushButton:hover {
                background-color: #005f5c;
            }
        """)
        self.btn_apply_custom.clicked.connect(self._on_filter_changed)

        custom_layout.addWidget(lbl_from)
        custom_layout.addWidget(self.date_from)
        custom_layout.addWidget(lbl_to)
        custom_layout.addWidget(self.date_to)
        custom_layout.addWidget(self.btn_apply_custom)
        custom_layout.addStretch()

        cont_layout.addWidget(self.custom_date_bar)

        # 4. شريط المؤشرات المالية السريعة (Mini KPI Summary Strip)
        self.kpi_strip_layout = QHBoxLayout()
        self.kpi_strip_layout.setSpacing(8)

        self.pill_inflow = MetricPill("🟢 Entrées (Ventes)", "0.00 DA", "#059669", "#ecfdf5", "#a7f3d0")
        self.pill_outflow = MetricPill("🔴 Sorties (Achats/Frais)", "0.00 DA", "#dc2626", "#fff1f2", "#fecdd3")
        self.pill_net = MetricPill("⚖️ Solde Net", "0.00 DA", "#0284c7", "#f0f9ff", "#bae6fd")
        self.pill_avg = MetricPill("📈 Moyenne / Colonne", "0.00 DA", "#475569", "#f8fafc", "#e2e8f0")

        self.kpi_strip_layout.addWidget(self.pill_inflow)
        self.kpi_strip_layout.addWidget(self.pill_outflow)
        self.kpi_strip_layout.addWidget(self.pill_net)
        self.kpi_strip_layout.addWidget(self.pill_avg)
        self.kpi_strip_layout.addStretch()

        cont_layout.addLayout(self.kpi_strip_layout)

        # 5. إعداد الشارت الرئيسي وعرض الرسوم البيانية
        self.chart = QChart()
        self.chart.setAnimationOptions(QChart.SeriesAnimations)
        self.chart.setMargins(QMargins(8, 8, 8, 8))
        self.chart.setBackgroundRoundness(0)
        self.chart.legend().setVisible(True)
        self.chart.legend().setAlignment(Qt.AlignTop)
        self.chart.legend().setFont(QFont("Segoe UI", 10, QFont.Bold))

        self.chart_view = QChartView(self.chart)
        self.chart_view.setMinimumHeight(280)
        self.chart_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.chart_view.setRenderHint(QPainter.Antialiasing)
        self.chart_view.setStyleSheet("background: transparent;")
        cont_layout.addWidget(self.chart_view, 1)

        # 6. شريط التفاصيل التفاعلي عند التحويم (Interactive Hover Info Banner)
        self.hover_banner = QFrame()
        self.hover_banner.setStyleSheet("""
            QFrame {
                background-color: #f8fafc;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                padding: 6px 12px;
            }
        """)
        hover_layout = QHBoxLayout(self.hover_banner)
        hover_layout.setContentsMargins(10, 5, 10, 5)
        hover_layout.setSpacing(14)

        self.lbl_hover_date = QLabel("📌 Survolez une colonne pour voir les détails")
        self.lbl_hover_date.setStyleSheet("font-weight: 700; color: #334155; font-size: 12px;")

        self.lbl_hover_in = QLabel("🟢 Entrées: --")
        self.lbl_hover_in.setStyleSheet("font-weight: 700; color: #059669; font-size: 12px;")

        self.lbl_hover_out = QLabel("🔴 Sorties: --")
        self.lbl_hover_out.setStyleSheet("font-weight: 700; color: #dc2626; font-size: 12px;")

        self.lbl_hover_net = QLabel("⚖️ Net: --")
        self.lbl_hover_net.setStyleSheet("font-weight: 800; color: #0284c7; font-size: 12px;")

        hover_layout.addWidget(self.lbl_hover_date)
        hover_layout.addStretch()
        hover_layout.addWidget(self.lbl_hover_in)
        hover_layout.addWidget(self.lbl_hover_out)
        hover_layout.addWidget(self.lbl_hover_net)

        cont_layout.addWidget(self.hover_banner)

        main_layout.addWidget(self.container)
        self._apply_chart_theme()

    def _control_style(self):
        return """
            QComboBox {
                background-color: #f8fafc;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 600;
                color: #1e293b;
                min-height: 24px;
            }
            QComboBox:hover {
                border-color: #007572;
                background-color: #ffffff;
            }
            QComboBox::drop-down {
                border: none;
                width: 18px;
            }
            QComboBox QAbstractItemView {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                selection-background-color: #e6fffa;
                selection-color: #007572;
                font-size: 11px;
                padding: 4px;
            }
        """

    def _date_edit_style(self):
        return """
            QDateEdit {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 3px 8px;
                font-size: 11px;
                font-weight: 600;
                color: #1e293b;
                min-height: 22px;
            }
            QDateEdit:focus {
                border-color: #007572;
            }
        """

    def _theme_colors(self):
        app = QApplication.instance()
        if app is None:
            return {
                "surface": QColor("#ffffff"),
                "background": QColor("#ffffff"),
                "text": QColor("#1e293b"),
                "muted": QColor("#64748b"),
                "grid": QColor("#f1f5f9"),
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
        self.chart.setPlotAreaBackgroundBrush(QColor("#fafbfc"))
        self.chart.setPlotAreaBackgroundVisible(True)
        self.chart.setTitleBrush(colors["text"])
        self.chart.legend().setLabelBrush(colors["text"])
        for axis in self.chart.axes():
            axis.setLabelsColor(colors["muted"])
            axis.setGridLineColor(QColor("#f1f5f9"))

    def _on_range_preset_changed(self, index):
        """معالجة تغيير القائمة المنسدلة للنطاقات الزمنية المسبقة"""
        is_custom = (index == 8) # "⚙️ Personnalisé..."
        self.custom_date_bar.setVisible(is_custom)
        if not is_custom:
            self._on_filter_changed()

    def _get_active_filters(self):
        """استخراج معايير التصفية الحالية (النوع، التجميع، التواريخ)"""
        gran_idx = self.combo_granularity.currentIndex()
        granularity = "day" if gran_idx == 0 else ("week" if gran_idx == 1 else "month")

        range_idx = self.combo_range.currentIndex()
        today = date.today()

        if range_idx == 0:   # 7 Jours
            start_date = today - timedelta(days=6)
            end_date = today
            days = 7
        elif range_idx == 1: # 15 Jours
            start_date = today - timedelta(days=14)
            end_date = today
            days = 15
        elif range_idx == 2: # 30 Jours
            start_date = today - timedelta(days=29)
            end_date = today
            days = 30
        elif range_idx == 3: # 3 Mois (90J)
            start_date = today - timedelta(days=89)
            end_date = today
            days = 90
        elif range_idx == 4: # 6 Mois (180J)
            start_date = today - timedelta(days=179)
            end_date = today
            days = 180
        elif range_idx == 5: # 1 An (365J)
            start_date = today - timedelta(days=364)
            end_date = today
            days = 365
        elif range_idx == 6: # Cette Année
            start_date = date(today.year, 1, 1)
            end_date = today
            days = (today - start_date).days + 1
        elif range_idx == 7: # Tout l'historique
            start_date = None
            end_date = None
            days = None
        else:                # Personnalisé
            q_start = self.date_from.date()
            q_end = self.date_to.date()
            start_date = date(q_start.year(), q_start.month(), q_start.day())
            end_date = date(q_end.year(), q_end.month(), q_end.day())
            if start_date > end_date:
                start_date, end_date = end_date, start_date
            days = (end_date - start_date).days + 1

        view_mode_idx = self.combo_view_mode.currentIndex()
        view_mode = "both" if view_mode_idx == 0 else ("inflow" if view_mode_idx == 1 else ("outflow" if view_mode_idx == 2 else "net"))

        return {
            "granularity": granularity,
            "start_date": start_date,
            "end_date": end_date,
            "days": days,
            "view_mode": view_mode,
        }

    def _on_filter_changed(self):
        """يتم استدعاؤها عند تغيير أي فلتر محلي لتحديث البيانات ورسم الأعمدة"""
        filters = self._get_active_filters()
        self.filterChanged.emit(filters)

        # إذا كان مدير الإحصائيات متوفراً، يتم جلب البيانات مباشرة من قاعدة البيانات بدقة وسرعة
        if self.stats_manager:
            try:
                financial_data = self.stats_manager.get_financial_trend(
                    days=filters["days"],
                    start_date=filters["start_date"],
                    end_date=filters["end_date"],
                    granularity=filters["granularity"]
                )
                self._render_financial_trend(financial_data, filters)
                return
            except Exception as e:
                logging.error(f"Error fetching filtered trend from stats_manager: {e}", exc_info=True)

        # كاحتياطي: استخدام البيانات المخزنة محلياً وتجميعها بواسطة محرك الذاكرة
        self._aggregate_and_render_local(filters)

    def update_data(self, sales_trend=None, purchases_trend=None):
        """
        تحديث البيانات الأساسية من المصدر وإعادة الرسم:
        sales_trend: قائمة بالمبيعات اليومية
        purchases_trend: قائمة بالمشتريات/المصاريف اليومية
        """
        if sales_trend is not None:
            self._raw_sales_trend = sales_trend
        if purchases_trend is not None:
            self._raw_purchases_trend = purchases_trend

        self._on_filter_changed()

    def _aggregate_and_render_local(self, filters):
        """محرك التجميع الداخلي للبيانات في الذاكرة وفقاً للفلاتر المحددة"""
        granularity = filters["granularity"]
        start_date = filters["start_date"]
        end_date = filters["end_date"]

        # خريطة المبيعات (الداخل)
        inflow_map = {}
        for s in self._raw_sales_trend:
            d_raw = s.get("date") or s.get("created_at")
            if not d_raw:
                continue
            d_str = str(d_raw)[:10]
            val = float(s.get("daily_value") or s.get("total_amount") or 0.0)
            inflow_map[d_str] = inflow_map.get(d_str, 0.0) + val

        # خريطة المشتريات (الخارج)
        outflow_map = {}
        for p in self._raw_purchases_trend:
            d_raw = p.get("date") or p.get("transaction_date")
            if not d_raw:
                continue
            d_str = str(d_raw)[:10]
            val = float(p.get("daily_cost") or p.get("total_amount") or 0.0)
            outflow_map[d_str] = outflow_map.get(d_str, 0.0) + val

        # إذا لم يتم تحديد نطاق، نستنتج البداية والنهاية من البيانات
        all_dates = sorted(list(set(list(inflow_map.keys()) + list(outflow_map.keys()))))
        if not start_date or not end_date:
            if all_dates:
                try:
                    start_date = datetime.strptime(all_dates[0], "%Y-%m-%d").date()
                    end_date = datetime.strptime(all_dates[-1], "%Y-%m-%d").date()
                except Exception:
                    start_date = date.today() - timedelta(days=29)
                    end_date = date.today()
            else:
                start_date = date.today() - timedelta(days=29)
                end_date = date.today()

        # بناء النوافذ الزمنية المتسلسلة (Day, Week, Month)
        buckets = {}
        curr = start_date
        while curr <= end_date:
            if granularity == "month":
                bucket_key = curr.strftime("%Y-%m")
                label = curr.strftime("%b %Y")
                next_step = (curr.replace(day=28) + timedelta(days=4)).replace(day=1)
            elif granularity == "week":
                # الاثنين كبداية للأسبوع
                monday = curr - timedelta(days=curr.weekday())
                bucket_key = monday.strftime("%Y-W%U")
                label = f"Sem {monday.strftime('%W')} ({monday.strftime('%d/%m')})"
                next_step = curr + timedelta(days=7)
            else: # day
                bucket_key = curr.strftime("%Y-%m-%d")
                label = curr.strftime("%d %b")
                next_step = curr + timedelta(days=1)

            if bucket_key not in buckets:
                buckets[bucket_key] = {
                    "period_key": bucket_key,
                    "date": str(curr),
                    "label": label,
                    "inflow": 0.0,
                    "outflow": 0.0,
                    "net": 0.0
                }
            curr = next_step

        # توزيع القيم على النوافذ
        for d_str, val in inflow_map.items():
            try:
                d_obj = datetime.strptime(d_str, "%Y-%m-%d").date()
                if start_date <= d_obj <= end_date:
                    if granularity == "month":
                        k = d_obj.strftime("%Y-%m")
                    elif granularity == "week":
                        m = d_obj - timedelta(days=d_obj.weekday())
                        k = m.strftime("%Y-W%U")
                    else:
                        k = d_obj.strftime("%Y-%m-%d")

                    if k in buckets:
                        buckets[k]["inflow"] += val
            except Exception:
                pass

        for d_str, val in outflow_map.items():
            try:
                d_obj = datetime.strptime(d_str, "%Y-%m-%d").date()
                if start_date <= d_obj <= end_date:
                    if granularity == "month":
                        k = d_obj.strftime("%Y-%m")
                    elif granularity == "week":
                        m = d_obj - timedelta(days=d_obj.weekday())
                        k = m.strftime("%Y-W%U")
                    else:
                        k = d_obj.strftime("%Y-%m-%d")

                    if k in buckets:
                        buckets[k]["outflow"] += val
            except Exception:
                pass

        financial_data = []
        for k in sorted(buckets.keys()):
            entry = buckets[k]
            entry["net"] = entry["inflow"] - entry["outflow"]
            financial_data.append(entry)

        self._render_financial_trend(financial_data, filters)

    def _format_label(self, raw_key: str, raw_date: str, granularity: str) -> str:
        """تنسيق تسمية محور السينات بشكل أنيق وقصير"""
        try:
            if granularity == "month":
                dt = datetime.strptime(raw_key[:7], "%Y-%m")
                months_fr = ["Jan", "Fév", "Mar", "Avr", "Mai", "Juin", "Juil", "Aoû", "Sep", "Oct", "Nov", "Déc"]
                return f"{months_fr[dt.month - 1]} {dt.year % 100:02d}"
            elif granularity == "week":
                if "-" in raw_date:
                    dt = datetime.strptime(raw_date[:10], "%Y-%m-%d")
                    return f"S{dt.strftime('%W')} ({dt.strftime('%d/%m')})"
                return f"Sem {raw_key[-2:]}"
            else:
                dt = datetime.strptime(raw_date[:10], "%Y-%m-%d")
                months_fr = ["Jan", "Fév", "Mar", "Avr", "Mai", "Juin", "Juil", "Aoû", "Sep", "Oct", "Nov", "Déc"]
                return f"{dt.day:02d} {months_fr[dt.month - 1]}"
        except Exception:
            return str(raw_key)

    def _render_financial_trend(self, financial_data, filters):
        """رسم أعمدة البورصة مع الألوان الخضراء للداخل والحمراء للخارج"""
        self._processed_data = financial_data or []
        self._refresh_chart_display()

    def _refresh_chart_display(self):
        """إعادة بناء سلسلة الأعمدة والمحاور بناء على البيانات المجهزة ونمط العرض المحدد"""
        filters = self._get_active_filters()
        view_mode = filters["view_mode"]
        granularity = filters["granularity"]
        colors = self._theme_colors()

        # تفريغ الشارت والمحاور القديمة
        self.chart.removeAllSeries()
        for ax in self.chart.axes():
            self.chart.removeAxis(ax)

        # حساب الإجماليات والمؤشرات
        total_inflow = sum(item.get("inflow", 0.0) for item in self._processed_data)
        total_outflow = sum(item.get("outflow", 0.0) for item in self._processed_data)
        net_solde = total_inflow - total_outflow
        col_count = max(len(self._processed_data), 1)
        avg_inflow = total_inflow / col_count

        # تحديث بطاقات المؤشرات (Mini KPIs)
        self.pill_inflow.set_value(f"+ {total_inflow:,.2f} DA")
        self.pill_outflow.set_value(f"- {total_outflow:,.2f} DA")
        
        net_prefix = "+ " if net_solde >= 0 else "- "
        net_color = "#059669" if net_solde >= 0 else "#dc2626"
        net_bg = "#ecfdf5" if net_solde >= 0 else "#fff1f2"
        net_border = "#a7f3d0" if net_solde >= 0 else "#fecdd3"
        self.pill_net.set_value(f"{net_prefix}{abs(net_solde):,.2f} DA", net_color, net_bg, net_border)
        self.pill_avg.set_value(f"{avg_inflow:,.2f} DA / col")

        # تحديث النص التوضيحي في العنوان
        freq_name = "Par Jour" if granularity == "day" else ("Par Semaine" if granularity == "week" else "Par Mois")
        self.lbl_subtitle.setText(
            f"📊 {col_count} Colonnes • {freq_name} • Entrées: {total_inflow:,.0f} DA | Sorties: {total_outflow:,.0f} DA"
        )

        # إعداد مجموعات الأعمدة (Bar Sets)
        categories = []
        max_val = 1000.0

        # ألوان أعمدة البورصة المالية الاحترافية:
        # الداخل (أخضر زمردي): #10b981 / حدود #059669
        # الخارج (أحمر مرجاني/قرمزي): #ef4444 / حدود #dc2626
        set_inflow = QBarSet("🟢 Entrées (Ventes)")
        set_inflow.setColor(QColor("#10b981"))
        set_inflow.setPen(QPen(QColor("#059669"), 1.2))

        set_outflow = QBarSet("🔴 Sorties (Achats & Frais)")
        set_outflow.setColor(QColor("#ef4444"))
        set_outflow.setPen(QPen(QColor("#dc2626"), 1.2))

        set_net_pos = QBarSet("🟢 Solde Positif (+)")
        set_net_pos.setColor(QColor("#10b981"))
        set_net_pos.setPen(QPen(QColor("#059669"), 1.2))

        set_net_neg = QBarSet("🔴 Déficit (-)")
        set_net_neg.setColor(QColor("#ef4444"))
        set_net_neg.setPen(QPen(QColor("#dc2626"), 1.2))

        # في حال عدم وجود بيانات
        if not self._processed_data:
            categories = ["Aucune Donnée"]
            set_inflow.append(0)
            set_outflow.append(0)
        else:
            for idx, item in enumerate(self._processed_data):
                raw_k = item.get("period_key") or ""
                raw_d = item.get("date") or raw_k
                label = self._format_label(raw_k, raw_d, granularity)
                categories.append(label)

                in_v = float(item.get("inflow") or 0.0)
                out_v = float(item.get("outflow") or 0.0)
                net_v = in_v - out_v

                set_inflow.append(in_v)
                set_outflow.append(out_v)

                if net_v >= 0:
                    set_net_pos.append(net_v)
                    set_net_neg.append(0)
                else:
                    set_net_pos.append(0)
                    set_net_neg.append(abs(net_v))

                if in_v > max_val:
                    max_val = in_v
                if out_v > max_val:
                    max_val = out_v
                if abs(net_v) > max_val:
                    max_val = abs(net_v)

        # ربط أحداث التحويم (Hover Events) للتفاعل الاحترافي
        set_inflow.hovered.connect(lambda status, index: self._on_bar_hovered(status, index))
        set_outflow.hovered.connect(lambda status, index: self._on_bar_hovered(status, index))
        set_net_pos.hovered.connect(lambda status, index: self._on_bar_hovered(status, index))
        set_net_neg.hovered.connect(lambda status, index: self._on_bar_hovered(status, index))

        # بناء السلسلة وفق نمط العرض
        series = QBarSeries()
        series.setBarWidth(0.68)

        if view_mode == "both":
            series.append(set_inflow)
            series.append(set_outflow)
        elif view_mode == "inflow":
            series.append(set_inflow)
        elif view_mode == "outflow":
            series.append(set_outflow)
        else: # "net"
            series.append(set_net_pos)
            series.append(set_net_neg)

        self.chart.addSeries(series)

        # المحاور
        # محور السينات (X Axis - الفئات والتواريخ)
        axis_x = QBarCategoryAxis()
        axis_x.append(categories)
        axis_x.setLabelsColor(colors["muted"])
        axis_x.setGridLineColor(QColor("#f1f5f9"))
        
        # تحسين خط المحور بحسب كثافة الأعمدة
        font_size = 9 if len(categories) > 20 else 10
        axis_x.setLabelsFont(QFont("Segoe UI", font_size, QFont.Bold))
        self.chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        series.attachAxis(axis_x)

        # محور العينات (Y Axis - القيم بالدينار)
        axis_y = QValueAxis()
        axis_y.setRange(0, max_val * 1.18) # زيادة 18% مساحة علوية لمنع تلامس الأعمدة مع السقف
        axis_y.setLabelFormat("%.0f DA")
        axis_y.setLabelsFont(QFont("Segoe UI", 10, QFont.Bold))
        axis_y.setLabelsColor(colors["muted"])
        axis_y.setGridLineColor(QColor("#f1f5f9"))
        self.chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        series.attachAxis(axis_y)

        # إعداد وسيلة الإيضاح (Legend)
        self.chart.legend().setVisible(True)
        self.chart.legend().setAlignment(Qt.AlignTop)
        self._apply_chart_theme()

    def _on_bar_hovered(self, status: bool, index: int):
        """تحديث شريط التفاصيل السفلي عند المرور فوق أي عمود"""
        if not status or index < 0 or index >= len(self._processed_data):
            self.lbl_hover_date.setText("📌 Survolez une colonne pour voir les détails")
            self.lbl_hover_in.setText("🟢 Entrées: --")
            self.lbl_hover_out.setText("🔴 Sorties: --")
            self.lbl_hover_net.setText("⚖️ Net: --")
            return

        item = self._processed_data[index]
        granularity = self._get_active_filters()["granularity"]
        raw_k = item.get("period_key") or ""
        raw_d = item.get("date") or raw_k
        label = self._format_label(raw_k, raw_d, granularity)

        inflow = float(item.get("inflow") or 0.0)
        outflow = float(item.get("outflow") or 0.0)
        net = inflow - outflow

        margin_str = ""
        if inflow > 0:
            m = (net / inflow) * 100.0
            margin_str = f" ({m:+.1f}%)"

        self.lbl_hover_date.setText(f"📍 Période : {label} ({raw_d})")
        self.lbl_hover_in.setText(f"🟢 Entrées: +{inflow:,.2f} DA")
        self.lbl_hover_out.setText(f"🔴 Sorties: -{outflow:,.2f} DA")

        net_prefix = "+" if net >= 0 else ""
        net_col = "#059669" if net >= 0 else "#dc2626"
        self.lbl_hover_net.setText(f"⚖️ Solde Net: {net_prefix}{net:,.2f} DA{margin_str}")
        self.lbl_hover_net.setStyleSheet(f"font-weight: 800; color: {net_col}; font-size: 12px;")
