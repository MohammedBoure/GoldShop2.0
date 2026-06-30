"""Reusable touch-first helpers for GoldShop dialogs."""

from __future__ import annotations

from typing import Callable, Dict, Iterable, Optional, Tuple

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QWidget,
)

from ui.touch_design import (
    TOUCH_DIALOG_MARGIN,
    TOUCH_DIALOG_SPACING,
    apply_touch_button_defaults,
)


class TouchDialogMixin:
    """Mixin for dialogs that need consistent touch keyboard and footer behavior."""

    _touch_keyboard = None
    _touch_dirty = False

    def setup_touch_dialog(self, *, size: str = "large", dirty_tracking: bool = False) -> None:
        self.set_touch_size(size)
        if hasattr(self, "layout") and self.layout():
            self.layout().setContentsMargins(
                TOUCH_DIALOG_MARGIN,
                TOUCH_DIALOG_MARGIN,
                TOUCH_DIALOG_MARGIN,
                TOUCH_DIALOG_MARGIN,
            )
            self.layout().setSpacing(TOUCH_DIALOG_SPACING)
        if dirty_tracking:
            self._touch_dirty = False

    def set_touch_size(self, mode: str = "large") -> None:
        app = QApplication.instance()
        screen = app.primaryScreen() if app is not None else None
        if screen is None:
            if mode == "fullscreen":
                self.setMinimumSize(900, 650)
            elif mode == "large":
                self.setMinimumSize(720, 520)
            return

        geometry = screen.availableGeometry()
        if mode == "fullscreen":
            width = int(geometry.width() * 0.92)
            height = int(geometry.height() * 0.90)
        elif mode == "compact":
            width = min(620, int(geometry.width() * 0.62))
            height = min(460, int(geometry.height() * 0.58))
        else:
            width = min(820, int(geometry.width() * 0.74))
            height = min(620, int(geometry.height() * 0.76))

        self.setMinimumSize(width, height)
        self.resize(width, height)

    def center_on_screen(self) -> None:
        app = QApplication.instance()
        screen = app.primaryScreen() if app is not None else None
        if screen is None:
            return
        geometry = screen.availableGeometry()
        self.move(
            geometry.x() + (geometry.width() - self.width()) // 2,
            geometry.y() + (geometry.height() - self.height()) // 2,
        )

    def add_keyboard_button(
        self,
        layout: Optional[QHBoxLayout] = None,
        *,
        text: str = "Clavier",
        target: Optional[QWidget] = None,
    ) -> QPushButton:
        button = QPushButton(text)
        apply_touch_button_defaults(button)
        button.clicked.connect(lambda: self.show_virtual_keyboard(target))
        if layout is not None:
            layout.addWidget(button)
        return button

    def create_numpad_button(
        self,
        target_widget: QWidget,
        title: str = "Saisie",
        *,
        text: str = "123",
        allow_decimal: bool = True,
    ) -> QPushButton:
        button = QPushButton(text)
        button.setToolTip("Pavé numérique")
        apply_touch_button_defaults(button)
        button.clicked.connect(
            lambda: self.open_numpad_for(target_widget, title, allow_decimal=allow_decimal)
        )
        return button

    def show_virtual_keyboard(self, target: Optional[QWidget] = None) -> None:
        if target is not None:
            target.setFocus(Qt.OtherFocusReason)
        from ui.tools.virtual_keyboard import VirtualKeyboardDialog

        if self._touch_keyboard is None:
            self._touch_keyboard = VirtualKeyboardDialog(self)
        self._touch_keyboard.show()

    def close_virtual_keyboard(self) -> None:
        keyboard = self._touch_keyboard
        if keyboard is None:
            return
        try:
            if keyboard.isVisible():
                keyboard.close()
        except RuntimeError:
            pass
        self._touch_keyboard = None

    def open_numpad_for(
        self,
        target_widget: QWidget,
        title: str = "Saisie",
        *,
        allow_decimal: bool = True,
    ) -> int:
        self.close_virtual_keyboard()
        from ui.tools.virtual_numpad import VirtualNumpad

        pad = VirtualNumpad(
            title,
            mode="direct",
            target_widget=target_widget,
            allow_decimal=allow_decimal,
            parent=self,
        )
        return pad.exec()

    def create_touch_footer(
        self,
        *,
        primary_text: str = "Valider",
        cancel_text: str = "Annuler",
        primary_slot: Optional[Callable[[], None]] = None,
        cancel_slot: Optional[Callable[[], None]] = None,
        extra_buttons: Iterable[QPushButton] = (),
    ) -> Tuple[QHBoxLayout, Dict[str, QPushButton]]:
        footer = QHBoxLayout()
        footer.setSpacing(TOUCH_DIALOG_SPACING)

        buttons: Dict[str, QPushButton] = {}
        for index, button in enumerate(extra_buttons):
            apply_touch_button_defaults(button)
            footer.addWidget(button)
            buttons[f"extra_{index}"] = button

        footer.addStretch()

        cancel_button = QPushButton(cancel_text)
        apply_touch_button_defaults(cancel_button)
        cancel_button.setAutoDefault(False)
        cancel_button.setDefault(False)
        cancel_button.clicked.connect(cancel_slot or self.reject)

        primary_button = QPushButton(primary_text)
        apply_touch_button_defaults(primary_button, primary=True)
        primary_button.setAutoDefault(False)
        primary_button.setDefault(False)
        if primary_slot is not None:
            primary_button.clicked.connect(primary_slot)

        footer.addWidget(cancel_button)
        footer.addWidget(primary_button)
        buttons["cancel"] = cancel_button
        buttons["primary"] = primary_button
        return footer, buttons

    def mark_dirty(self) -> None:
        self._touch_dirty = True

    def clear_dirty(self) -> None:
        self._touch_dirty = False

    def confirm_discard_changes(self) -> bool:
        if not self._touch_dirty:
            return True
        reply = QMessageBox.question(
            self,
            "Modifications non enregistrées",
            "Des informations ont ete saisies mais pas validees. Voulez-vous fermer sans enregistrer ?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        return reply == QMessageBox.Yes

    def reject(self) -> None:
        if not self.confirm_discard_changes():
            return
        self.close_virtual_keyboard()
        super().reject()

    def accept(self) -> None:
        self.clear_dirty()
        self.close_virtual_keyboard()
        super().accept()

    def closeEvent(self, event: QEvent) -> None:
        if not self.confirm_discard_changes():
            event.ignore()
            return
        self.close_virtual_keyboard()
        super().closeEvent(event)

    def showEvent(self, event: QEvent) -> None:
        super().showEvent(event)
        self.center_on_screen()
