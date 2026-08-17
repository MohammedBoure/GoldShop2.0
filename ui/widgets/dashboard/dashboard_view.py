# ui/widgets/dashboard/dashboard_view.py

import logging
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QScrollArea, QPushButton, QSizePolicy)
from PySide6.QtCore import Qt, QTimer
import qtawesome as qta
from ui.deferred_loading import defer_initial_load
from .overview_tab import OverviewTab 

class DashboardView(QWidget):
    def __init__(self, manager, current_user=None, parent=None, **kwargs):
        super().__init__(parent)
        self.manager = manager
        self.current_user = current_user or {}
        self._density_key = None
        if hasattr(self.manager, 'db'):
            try:
                from database.statistics_manager import StatisticsManager
                self.manager.stats = StatisticsManager(self.manager.db)
            except Exception:
                pass
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.scroll = QScrollArea()
        scroll = self.scroll
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("background-color: #f4f7fa; border: none;")
        
        self.content_widget = QWidget()
        content_widget = self.content_widget
        content_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.content_layout = QVBoxLayout(content_widget)
        self.content_layout.setContentsMargins(20, 20, 20, 20)
        self.content_layout.setSpacing(20)

        header_layout = QHBoxLayout()
        self.lbl_title = QLabel("Tableau de Bord")
        self.lbl_title.setStyleSheet("font-size: 24px; font-weight: 800; color: #2c3e50;")
        
        self.btn_refresh = QPushButton("Actualiser")
        self.btn_refresh.setCursor(Qt.PointingHandCursor)
        self.btn_refresh.setIcon(qta.icon("fa5s.sync-alt", color="white"))
        self.btn_refresh.setStyleSheet("""
            QPushButton { 
                background-color: #007572; color: white; border-radius: 6px; 
                padding: 8px 16px; font-weight: bold; border: none;
            }
            QPushButton:hover { background-color: #005f5c; }
        """)
        self.btn_refresh.clicked.connect(self.refresh_dashboard)
        
        header_layout.addWidget(self.lbl_title)
        header_layout.addStretch()
        header_layout.addWidget(self.btn_refresh)
        self.content_layout.addLayout(header_layout)

        self.overview_tab = OverviewTab()
        self.content_layout.addWidget(self.overview_tab)
        
        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll)

        defer_initial_load(self, self.refresh_dashboard, 100)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_responsive_density()

    def _apply_responsive_density(self):
        width = max(1, self.width())
        if width < 520:
            density_key = "compact"
            margin = 10
            spacing = 12
            title_size = 20
            button_padding = "6px 10px"
        elif width < 820:
            density_key = "medium"
            margin = 14
            spacing = 14
            title_size = 22
            button_padding = "7px 12px"
        else:
            density_key = "regular"
            margin = 20
            spacing = 20
            title_size = 24
            button_padding = "8px 16px"

        if self._density_key == density_key:
            return
        self._density_key = density_key

        self.content_layout.setContentsMargins(margin, margin, margin, margin)
        self.content_layout.setSpacing(spacing)
        self.lbl_title.setStyleSheet(
            f"font-size: {title_size}px; font-weight: 800; color: #2c3e50;"
        )
        self.btn_refresh.setStyleSheet(f"""
            QPushButton {{
                background-color: #007572; color: white; border-radius: 6px;
                padding: {button_padding}; font-weight: bold; border: none;
            }}
            QPushButton:hover {{ background-color: #005f5c; }}
        """)

    def refresh_dashboard(self):
        try:
            # 🟢 جلب إحصائيات الذهب والمال الجديدة
            metrics = self.manager.stats.get_dashboard_metrics()
            sales_trend = self.manager.stats.get_sales_trend(30)
            purchases_trend = self.manager.stats.get_purchases_trend(30)
            alerts_data = self.manager.stats.get_active_alerts()

            if hasattr(self.overview_tab, 'charts_section') and hasattr(self.manager, 'stats'):
                self.overview_tab.charts_section.set_stats_manager(self.manager.stats)

            self.overview_tab.update_content(metrics, sales_trend, purchases_trend, alerts_data)

        except Exception as e:
            logging.error(f"Dashboard Refresh Error: {e}", exc_info=True)

    def refresh_data(self):
        self.refresh_dashboard()
