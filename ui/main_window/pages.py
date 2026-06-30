import logging
import time

import qtawesome as qta
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QLabel, QMessageBox, QTabWidget, QWidget, QVBoxLayout


from ui.deferred_loading import SCHEDULED_REFRESH_PROP, has_deferred_initial_load, is_live_widget

PAGE_REFRESH_DELAY_MS = 70
PAGE_BUILD_DELAY_MS = 15
AUTO_REFRESH_MIN_INTERVAL_SECONDS = 3.0
LAST_AUTO_REFRESH_PROP = "_goldshop_last_auto_refresh_at"


class MainWindowPagesMixin:
    """Lazy page construction and deferred content refreshing."""

    def _scope_widget(self, widget, permission_key, label=None):
        return widget

    def _add_lazy_scoped_tab(self, tabs, factory, permission_key, label, icon=None):
        placeholder = QWidget()
        placeholder._lazy_tab_factory = factory
        layout = QVBoxLayout(placeholder)
        layout.setContentsMargins(20, 20, 20, 20)
        loading = QLabel("جاري التحميل...")
        loading.setAlignment(Qt.AlignCenter)
        layout.addWidget(loading, 1)
        if icon is None:
            tabs.addTab(placeholder, label)
        else:
            tabs.addTab(placeholder, icon, label)
        return placeholder

    def _apply_tab_layout(self, tabs, page_key):
        return tabs

    def _page_permission_key(self, page_id):
        return ""

    def _page_permission_label(self, page_id):
        return ""

    def _init_placeholders(self):
        for index in range(17):  # تم تخفيضها إلى 17
            label = QLabel(f"Chargement de la page {index}...")
            label.setAlignment(Qt.AlignCenter)
            self.content_area.addWidget(label)

    def _load_page(self, page_id):
        if page_id in self.loaded_pages:
            return self.loaded_pages[page_id]

        widget = None

        if page_id == 1:
            tabs = QTabWidget()
            tabs.setStyleSheet("QTabBar::tab { height: 40px; min-width: 180px; font-weight: bold; font-size: 13px; }")
            inventory_tabs = {}

            if self.has_permission("tab_inv_list"):
                def make_inventory_list():
                    from ui.widgets.inventory.inventory_list import InventoryListTab
                    tab = InventoryListTab(self.data_manager)
                    inventory_tabs["list"] = tab
                    form = inventory_tabs.get("form")
                    if form is not None:
                        form.item_saved.connect(tab.reset_and_load)
                    return tab
                self._add_lazy_scoped_tab(tabs, make_inventory_list, "tab_inv_list", "Stock", qta.icon("fa5s.box-open"))

            if self.has_permission("tab_inv_form"):
                def make_inventory_form():
                    from ui.widgets.inventory.tabs_batches.tabs_batches import InventoryFormTab
                    tab = InventoryFormTab(self.data_manager)
                    inventory_tabs["form"] = tab
                    list_tab = inventory_tabs.get("list")
                    if list_tab is not None:
                        tab.item_saved.connect(list_tab.reset_and_load)
                    return tab
                self._add_lazy_scoped_tab(tabs, make_inventory_form, "tab_inv_form", "Ajouter Produit", qta.icon("fa5s.plus-circle"))

            if self.has_permission("tab_inv_form"):
                def make_achat_oc():
                    from ui.widgets.inventory.achat_oc_view import AchatOCView
                    return AchatOCView(self.data_manager)
                self._add_lazy_scoped_tab(tabs, make_achat_oc, "tab_inv_form", "Registre Achat OC", qta.icon("fa5s.balance-scale"))

            widget = tabs if tabs.count() > 0 else None

        elif page_id == 2:
            from ui.widgets.sales.sales_view import SalesView
            widget = self._scope_widget(SalesView(self.data_manager, self.current_user), "nav_sales", "Point de Vente")

        elif page_id == 3:
            from ui.widgets.partners.clients_tab import ClientsTab
            tabs = QTabWidget()
            if self.has_permission("tab_clients"):
                self._add_lazy_scoped_tab(tabs, lambda: ClientsTab(self.data_manager), "tab_clients", "Clients")
            widget = tabs if tabs.count() > 0 else None

        elif page_id == 6:
            from ui.widgets.master_data.categories_tab import CategoriesTab
            from ui.widgets.master_data.invoice_notes_tab import InvoiceNotesTab
            from ui.widgets.master_data.locations_tab import LocationsTab
            from ui.widgets.master_data.metals_tab import MetalsTab
            from ui.widgets.master_data.product_names_tab import ProductNamesTab

            tabs = QTabWidget()
            if self.has_permission("tab_metals"):
                self._add_lazy_scoped_tab(tabs, lambda: MetalsTab(self.data_manager), "tab_metals", "Types de Metaux")
            if self.has_permission("tab_categories"):
                self._add_lazy_scoped_tab(tabs, lambda: CategoriesTab(self.data_manager), "tab_categories", "Categories (Produits)")
            if self.has_permission("tab_product_names"):
                self._add_lazy_scoped_tab(tabs, lambda: ProductNamesTab(self.data_manager), "tab_product_names", "Designations (Noms)")
            if self.has_permission("tab_locations"):
                self._add_lazy_scoped_tab(tabs, lambda: LocationsTab(self.data_manager), "tab_locations", "Emplacements (Stock)")
            if self.has_permission("tab_invoice_notes"):
                self._add_lazy_scoped_tab(tabs, lambda: InvoiceNotesTab(self.data_manager), "tab_invoice_notes", "Notes Facture")
            widget = tabs if tabs.count() > 0 else None

        elif page_id == 7:
            tabs = QTabWidget()
            tabs.setStyleSheet("QTabBar::tab { height: 40px; width: 160px; font-weight: bold; }")

            if self.has_permission("tab_config"):
                def make_settings_tab():
                    from ui.widgets.settings.settings_tab import SettingsTab
                    return SettingsTab(self.data_manager)
                self._add_lazy_scoped_tab(tabs, make_settings_tab, "tab_config", "Configuration", qta.icon("fa5s.cogs"))

            if self.has_permission("tab_users"):
                def make_users_tab():
                    from ui.widgets.settings.users_view import UsersManagementView
                    return UsersManagementView(self.data_manager)
                self._add_lazy_scoped_tab(tabs, make_users_tab, "tab_users", "Utilisateurs", qta.icon("fa5s.users-cog"))

            widget = tabs if tabs.count() > 0 else None

        elif page_id == 8:
            tabs = QTabWidget()
            tabs.setStyleSheet("QTabBar::tab { height: 40px; width: 250px; font-weight: bold; font-size: 14px; }")

            if self.has_permission("nav_reports"):
                def make_excel_journal():
                    from ui.widgets.reports.excel_journal_view import ExcelJournalView
                    return ExcelJournalView(self.data_manager)
                self._add_lazy_scoped_tab(tabs, make_excel_journal, "nav_reports", "Journal de Caisse (Excel)", qta.icon("fa5s.file-excel"))

            if self.has_permission("nav_reports"):
                def make_monthly_summary():
                    from ui.widgets.reports.monthly_summary_view import MonthlySummaryView
                    return MonthlySummaryView(self.data_manager)
                self._add_lazy_scoped_tab(tabs, make_monthly_summary, "tab_monthly_summary", "Résumé Mensuel", qta.icon("fa5s.calendar-alt"))

            widget = tabs if tabs.count() > 0 else None

        elif page_id == 11:
            from ui.widgets.versements.versements_view import VersementsView
            widget = self._scope_widget(VersementsView(self.data_manager), "nav_versement", "Versements & Dettes")
    
        elif page_id == 12:
            from ui.widgets.client_commands import ClientCommandsView
            widget = self._scope_widget(ClientCommandsView(self.data_manager), "nav_client_commands", "Commandes Client")

        elif page_id == 13:
            from ui.widgets.inventory_count import InventoryCountView
            widget = self._scope_widget(InventoryCountView(self.data_manager, self.current_user), "nav_inventory_count", "Inventaire Physique")

        elif page_id == 14:
            from ui.widgets.official_suppliers import OfficialSuppliersView
            widget = self._scope_widget(OfficialSuppliersView(self.data_manager, self.current_user), "nav_official_suppliers", "Fournisseurs Officiels")
            
        elif page_id == 15:
            from ui.widgets.rh.rh_management_view import RHManagementView
            widget = self._scope_widget(RHManagementView(self.data_manager), "nav_rh", "Gestion Personnel & RH")

        elif page_id == 16:
            from ui.widgets.coffre.coffre_management_view import CoffreMagasinView
            widget = self._scope_widget(CoffreMagasinView(self.data_manager), "nav_coffre_magasin", "Coffre Magasin")

        if widget:
            old_widget = self.content_area.widget(page_id)
            self.content_area.removeWidget(old_widget)
            self.content_area.insertWidget(page_id, widget)
            self.loaded_pages[page_id] = widget
            return widget

        return None

    def switch_page(self, page_id):
        required_perm = {
            0: "nav_dashboard",
            1: "nav_inventory",
            2: "nav_sales",
            3: "nav_partners",
            4: "nav_services",
            5: "nav_finance",
            6: "nav_data",
            7: "nav_settings",
            8: "nav_reports",
            9: "nav_history",
            10: "nav_market",
            11: "nav_versement",
            12: "nav_client_commands",
            13: "nav_inventory_count",
            14: "nav_official_suppliers",
            15: "nav_rh",
            16: "nav_coffre_magasin",
        }.get(page_id)

        if required_perm and not self.has_permission(required_perm):
            QMessageBox.warning(self, "Accès refusé", "Vos autorisations ne vous permettent pas d'accéder à cette page.")
            return

        if page_id not in self.loaded_pages:
            self._pending_page_id = page_id
            self.content_area.setCurrentIndex(page_id)
            QTimer.singleShot(PAGE_BUILD_DELAY_MS, lambda pid=page_id: self._finish_switch_page(pid))
            return

        self._finish_switch_page(page_id)

    def _finish_switch_page(self, page_id):
        pending_page = getattr(self, "_pending_page_id", page_id)
        if page_id not in self.loaded_pages and pending_page != page_id:
            return

        try:
            widget = self._load_page(page_id)
            if widget:
                self._pending_page_id = None
                self.content_area.setCurrentIndex(page_id)
                self.trigger_refresh(widget)
            else:
                self._pending_page_id = None
                QMessageBox.warning(self, "Accès refusé", "Vous n'êtes pas autorisé à consulter les onglets internes de cette section.")
        except Exception as exc:
            self._pending_page_id = None
            QMessageBox.critical(self, "Erreur", f"Erreur lors du chargement de la page {page_id}:\n{exc}")
            logging.error("Page Load Error: %s", exc, exc_info=True)

    def trigger_refresh(self, widget):
        if not widget:
            return

        if isinstance(widget, QTabWidget):
            self._ensure_lazy_tab_loaded(widget)
            current_tab = widget.currentWidget()
            self.trigger_refresh(current_tab)

            if not getattr(widget, "_refresh_connected", False):
                widget.currentChanged.connect(
                    lambda index, tabs=widget: self.trigger_refresh(self._ensure_lazy_tab_loaded(tabs, index))
                )
                widget._refresh_connected = True
            return

        method_name, _method = self._refresh_method_for(widget)
        if method_name:
            self._schedule_refresh(widget, method_name)

    def _ensure_lazy_tab_loaded(self, tabs, index=None):
        if not isinstance(tabs, QTabWidget):
            return None
        index = tabs.currentIndex() if index is None else index
        if index < 0:
            return None
        widget = tabs.widget(index)
        factory = getattr(widget, "_lazy_tab_factory", None)
        if not callable(factory):
            return widget

        title = tabs.tabText(index)
        icon = tabs.tabIcon(index)
        tooltip = tabs.tabToolTip(index)

        built = factory()

        tabs.blockSignals(True)
        tabs.removeTab(index)
        if icon.isNull():
            tabs.insertTab(index, built, title)
        else:
            tabs.insertTab(index, built, icon, title)
        tabs.setTabToolTip(index, tooltip)
        tabs.setCurrentIndex(index)
        tabs.blockSignals(False)
        return built

    def _refresh_method_for(self, widget):
        refresh_methods = [
            "refresh_data", "refresh_all_data", "load_data", "reset_and_load",
            "load_inventory_data", "refresh_dashboard", "generate_report"
        ]
        for method_name in refresh_methods:
            if hasattr(widget, method_name):
                method = getattr(widget, method_name)
                if callable(method):
                    return method_name, method
        return None, None

    def _schedule_refresh(self, widget, method_name):
        if not is_live_widget(widget) or has_deferred_initial_load(widget):
            return
        if widget.property(SCHEDULED_REFRESH_PROP):
            return
        try:
            last_refresh = float(widget.property(LAST_AUTO_REFRESH_PROP) or 0.0)
        except (TypeError, ValueError):
            last_refresh = 0.0
        if last_refresh and (time.monotonic() - last_refresh) < AUTO_REFRESH_MIN_INTERVAL_SECONDS:
            return

        widget.setProperty(SCHEDULED_REFRESH_PROP, True)
        QTimer.singleShot(PAGE_REFRESH_DELAY_MS, lambda current_widget=widget, name=method_name: self._run_scheduled_refresh(current_widget, name))

    def _run_scheduled_refresh(self, widget, method_name):
        if not is_live_widget(widget):
            return

        widget.setProperty(SCHEDULED_REFRESH_PROP, False)
        if has_deferred_initial_load(widget):
            return

        method = getattr(widget, method_name, None)
        if not callable(method):
            return

        try:
            if method_name == "reset_and_load" and hasattr(widget, "load_combos"):
                widget.load_combos()
            method()
            widget.setProperty(LAST_AUTO_REFRESH_PROP, time.monotonic())
        except RuntimeError:
            return
        except Exception as exc:
            logging.error("Deferred page refresh failed for %s: %s", method_name, exc, exc_info=True)