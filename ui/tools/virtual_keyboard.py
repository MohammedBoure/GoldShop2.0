# ui/tools/virtual_keyboard.py

import logging
import pyautogui
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, 
    QPushButton, QLineEdit, QSizePolicy, QApplication,
    QTextEdit, QPlainTextEdit, QAbstractSpinBox, QWidget, QComboBox
)
from PySide6.QtCore import Qt, QTimer, QEvent, QObject
from PySide6.QtGui import QKeyEvent
import qtawesome as qta

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [V-KEYBOARD] - %(message)s')

class KeyboardFocusTracker:
    DEFAULT_TARGETS = {
        "line_edit": True,
        "text_edit": True,
        "spin_box": False,
        "editable_combo": False,
        "combo_box": False,
    }
    last_input_widget = None
    auto_open_enabled = False
    target_types = dict(DEFAULT_TARGETS)
    _event_filter = None

    @classmethod
    def configure_targets(cls, targets=None):
        merged = dict(cls.DEFAULT_TARGETS)
        if isinstance(targets, dict):
            for key in merged:
                if key in targets:
                    merged[key] = bool(targets[key])
        cls.target_types = merged

    @classmethod
    def _find_parent(cls, widget, widget_type):
        current = widget
        while current is not None:
            try:
                if isinstance(current, widget_type):
                    return current
                current = current.parentWidget()
            except RuntimeError:
                return None
        return None

    @classmethod
    def _target_for_widget(cls, widget, respect_target_types=True):
        if widget is None or not isinstance(widget, QWidget):
            return None
        if cls._is_keyboard_widget(widget):
            return None

        combo_parent = cls._find_parent(widget, QComboBox)
        if combo_parent is not None:
            if combo_parent.isEditable():
                if respect_target_types and not cls.target_types.get("editable_combo", False):
                    return None
                return combo_parent.lineEdit()
            return combo_parent if cls.target_types.get("combo_box", False) else None

        spin_parent = cls._find_parent(widget, QAbstractSpinBox)
        if spin_parent is not None:
            if respect_target_types and not cls.target_types.get("spin_box", False):
                return None
            return spin_parent.lineEdit() if hasattr(spin_parent, "lineEdit") else spin_parent

        text_parent = cls._find_parent(widget, (QTextEdit, QPlainTextEdit))
        if text_parent is not None:
            if respect_target_types and not cls.target_types.get("text_edit", True):
                return None
            return text_parent

        if isinstance(widget, QLineEdit):
            if respect_target_types and not cls.target_types.get("line_edit", True):
                return None
            return widget
        return None

    @classmethod
    def _is_keyboard_widget(cls, widget):
        current = widget
        while current is not None:
            try:
                if current.property("is_vkb") or isinstance(current, VirtualKeyboardDialog):
                    return True
                current = current.parentWidget()
            except RuntimeError:
                return True
        return False

    @classmethod
    def _is_usable_target(cls, target):
        try:
            if target is None or target.property("is_vkb"):
                return False
            if not target.isEnabled():
                return False
            if hasattr(target, "isReadOnly") and target.isReadOnly():
                return False
            return True
        except RuntimeError:
            return False

    @classmethod
    def _activate_target(cls, target):
        if not cls._is_usable_target(target):
            return False
        cls.last_input_widget = target
        try:
            kb = VirtualKeyboardDialog._instance
            if kb:
                kb.set_active_parent(target.window())
        except RuntimeError:
            return False
        return True

    @classmethod
    def track_widget(cls, widget, auto_open=False):
        try:
            target = cls._target_for_widget(widget, respect_target_types=False)
        except RuntimeError:
            return False
        if not cls._activate_target(target):
            return False
        if auto_open:
            try:
                auto_target = cls._target_for_widget(widget, respect_target_types=True)
            except RuntimeError:
                auto_target = None
            if auto_target is not None:
                cls.open_for_target(target)
        return True

    @classmethod
    def track_focus(cls, old, new):
        if new is None or new.property("is_vkb"):
            return

        cls.track_widget(new, auto_open=cls.auto_open_enabled)

    @classmethod
    def install(cls):
        app = QApplication.instance()
        if not app:
            return
        if not hasattr(app, '_kb_tracker_installed'):
            app.focusChanged.connect(cls.track_focus)
            app._kb_tracker_installed = True
        if cls._event_filter is None:
            cls._event_filter = KeyboardTargetEventFilter(app)
            app.installEventFilter(cls._event_filter)
            app._kb_target_event_filter = cls._event_filter

    @classmethod
    def configure_auto_open(cls, enabled: bool, targets=None):
        cls.auto_open_enabled = bool(enabled)
        cls.configure_targets(targets)
        cls.install()

    @classmethod
    def open_for_target(cls, target):
        if not target or target.property("is_vkb"):
            return
        try:
            if not cls._is_usable_target(target):
                return
            keyboard = VirtualKeyboardDialog._instance
            if keyboard is None:
                keyboard = VirtualKeyboardDialog(target.window())
            else:
                keyboard.set_active_parent(target.window())
            keyboard.show()
        except RuntimeError:
            cls.last_input_widget = None


class KeyboardTargetEventFilter(QObject):
    def eventFilter(self, obj, event):
        if not isinstance(obj, QWidget):
            return super().eventFilter(obj, event)

        event_type = event.type()
        if event_type == QEvent.FocusIn:
            KeyboardFocusTracker.track_widget(
                obj,
                auto_open=KeyboardFocusTracker.auto_open_enabled,
            )
        elif event_type in (QEvent.MouseButtonPress, QEvent.MouseButtonRelease):
            KeyboardFocusTracker.track_widget(obj, auto_open=False)
        return super().eventFilter(obj, event)


def configure_auto_virtual_keyboard(enabled: bool, targets=None):
    KeyboardFocusTracker.configure_auto_open(enabled, targets)

class VirtualKeyboardDialog(QDialog):
    _instance = None 

    def __init__(self, parent=None):
        if VirtualKeyboardDialog._instance:
            try: VirtualKeyboardDialog._instance.close()
            except RuntimeError: pass
            
        super().__init__(parent)
        VirtualKeyboardDialog._instance = self
        KeyboardFocusTracker.install()
        
        self.setWindowTitle("Clavier Virtuel")
        
        self.setWindowFlags(Qt.Tool | Qt.WindowStaysOnTopHint | Qt.WindowDoesNotAcceptFocus | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_ShowWithoutActivating) 
        self.setStyleSheet("QDialog { background-color: #ecf0f1; border: 2px solid #bdc3c7; border-top-left-radius: 12px; border-top-right-radius: 12px; }")
        
        # 🟢 تطبيق الحجم مبكراً
        self.apply_size()
        
        self.is_shifted = False
        self.direct_mode = True 
        self.letter_buttons = [] 
        
        self.init_ui()
        self.toggle_direct_mode()

    def apply_size(self):
        # 🟢 دالة مستقلة لفرض الحجم الصحيح دائماً
        screen = QApplication.primaryScreen().availableGeometry()
        width = int(screen.width() * 0.80)
        height = min(280, int(screen.height() * 0.38)) 
        self.resize(width, height)

    def move_to_bottom(self):
        screen_geom = QApplication.primaryScreen().availableGeometry()
        x = (screen_geom.width() - self.width()) // 2
        y = screen_geom.height() - self.height()
        self.move(x, y)

    def show(self):
        active_window = QApplication.activeModalWidget() or QApplication.activeWindow()
        if active_window and active_window != self: 
            self.set_active_parent(active_window)
        
        # 🟢 إظهار النافذة أولاً لكي يحسب Qt أبعادها بشكل سليم
        super().show()
        
        # 🟢 السحر هنا: نأمر النظام بنقل النافذة بعد 10 مللي ثانية (بعد أن يكتمل رسمها وحساب أبعادها)
        QTimer.singleShot(10, self.move_to_bottom)

    def set_active_parent(self, new_parent):
        try:
            if new_parent is None or self.parent() == new_parent: return
            was_visible = self.isVisible()
            
            if self.parent(): self.parent().removeEventFilter(self)
            self.setParent(new_parent)
            self.setWindowFlags(Qt.Tool | Qt.WindowStaysOnTopHint | Qt.WindowDoesNotAcceptFocus | Qt.FramelessWindowHint)
            new_parent.installEventFilter(self)
            
            self.apply_size()
            
            # Force the layout engine to recalculate after reparenting
            if self.layout():
                self.layout().activate()
            
            if was_visible:
                super().show()
                QTimer.singleShot(10, self.move_to_bottom)
        except RuntimeError: pass

    def eventFilter(self, obj, event):
        try:
            if obj == self.parent() and event.type() in (QEvent.Hide, QEvent.Close):
                was_visible = self.isVisible()
                obj.removeEventFilter(self)
                self.setParent(None)
                self.setWindowFlags(Qt.Tool | Qt.WindowStaysOnTopHint | Qt.WindowDoesNotAcceptFocus | Qt.FramelessWindowHint)
                
                self.apply_size()
                
                if was_visible:
                    super().show()
                    QTimer.singleShot(10, self.move_to_bottom)
        except RuntimeError: pass
        return super().eventFilter(obj, event)

    def get_target(self):
        target = KeyboardFocusTracker.last_input_widget
        try:
            # Check if the underlying C++ object is still valid
            import shiboken6
            if (
                target
                and shiboken6.isValid(target)
                and KeyboardFocusTracker._is_usable_target(target)
            ):
                return target
        except (RuntimeError, ImportError):
            pass

        fallback = QApplication.focusWidget()
        if KeyboardFocusTracker.track_widget(fallback, auto_open=False):
            return KeyboardFocusTracker.last_input_widget

        KeyboardFocusTracker.last_input_widget = None
        return None

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(4) 
        layout.setContentsMargins(8, 8, 8, 8)

        top_row = QHBoxLayout()
        self.display = QLineEdit()
        self.display.setProperty("is_vkb", True) 
        self.display.setFocusPolicy(Qt.NoFocus) 
        self.display.setMinimumHeight(40) 
        self.display.setStyleSheet("font-size: 18px; font-weight: bold; background-color: white; border: 2px solid #bdc3c7; border-radius: 6px; padding: 5px;")
        top_row.addWidget(self.display, stretch=4)

        self.btn_mode = QPushButton(" Direct ⚡")
        self.btn_mode.setProperty("is_vkb", True); self.btn_mode.setFocusPolicy(Qt.NoFocus); self.btn_mode.setCheckable(True); self.btn_mode.setChecked(True) 
        self.btn_mode.setMinimumHeight(40)
        self.btn_mode.setStyleSheet("QPushButton { background-color: #95a5a6; color: white; font-weight: bold; border-radius: 6px;} QPushButton:checked { background-color: #8e44ad; }")
        self.btn_mode.clicked.connect(self.toggle_direct_mode)
        top_row.addWidget(self.btn_mode, stretch=1)

        layout.addLayout(top_row)

        keys_layout = QVBoxLayout(); keys_layout.setSpacing(4)
        rows = [
            ['1', '2', '3', '4', '5', '6', '7', '8', '9', '0', '-', '_'],
            ['A', 'Z', 'E', 'R', 'T', 'Y', 'U', 'I', 'O', 'P'],
            ['Q', 'S', 'D', 'F', 'G', 'H', 'J', 'K', 'L', 'M'],
            ['W', 'X', 'C', 'V', 'B', 'N', '.', ',', '?', '!']
        ]

        btn_style = "QPushButton { background-color: white; border: 1px solid #dcdde1; border-radius: 6px; font-size: 18px; font-weight: bold; color: #2c3e50; } QPushButton:pressed { background-color: #bdc3c7; }"

        for row_chars in rows:
            row_layout = QHBoxLayout(); row_layout.setSpacing(4)
            if row_chars[0] == 'A': row_layout.addSpacing(20)
            elif row_chars[0] == 'Q': row_layout.addSpacing(40)
            elif row_chars[0] == 'W': row_layout.addSpacing(60)

            for char in row_chars:
                btn = QPushButton(char.lower() if char.isalpha() else char)
                btn.setProperty("is_vkb", True)
                btn.setFocusPolicy(Qt.NoFocus) 
                btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                
                # Add a minimum width to prevent horizontal squishing
                btn.setMinimumHeight(38) 
                btn.setMinimumWidth(35) 
                
                btn.setStyleSheet(btn_style)
                btn.clicked.connect(lambda checked, c=char: self.add_char(c))
                if char.isalpha(): self.letter_buttons.append((btn, char)) 
                row_layout.addWidget(btn)
            
            # row_layout.addStretch()  <--- REMOVE OR COMMENT THIS OUT
            keys_layout.addLayout(row_layout)
        bottom_row = QHBoxLayout(); bottom_row.setSpacing(4)

        self.btn_shift = QPushButton(" Maj")
        self.btn_shift.setProperty("is_vkb", True); self.btn_shift.setFocusPolicy(Qt.NoFocus); self.btn_shift.setMinimumHeight(40)
        self.btn_shift.setStyleSheet("background-color: #34495e; color: white; font-weight: bold; border-radius: 6px;")
        self.btn_shift.clicked.connect(self.toggle_shift)
        bottom_row.addWidget(self.btn_shift, stretch=2)

        btn_left = QPushButton(" ←")
        btn_left.setProperty("is_vkb", True); btn_left.setFocusPolicy(Qt.NoFocus); btn_left.setMinimumHeight(40)
        btn_left.setStyleSheet("background-color: #7f8c8d; color: white; font-weight: bold; border-radius: 6px;")
        btn_left.clicked.connect(self.move_left)
        bottom_row.addWidget(btn_left, stretch=1)

        btn_space = QPushButton("Espace")
        btn_space.setProperty("is_vkb", True); btn_space.setFocusPolicy(Qt.NoFocus); btn_space.setMinimumHeight(40)
        btn_space.setStyleSheet(btn_style); btn_space.clicked.connect(lambda: self.add_char(" "))
        bottom_row.addWidget(btn_space, stretch=4)

        btn_right = QPushButton(" →")
        btn_right.setProperty("is_vkb", True); btn_right.setFocusPolicy(Qt.NoFocus); btn_right.setMinimumHeight(40)
        btn_right.setStyleSheet("background-color: #7f8c8d; color: white; font-weight: bold; border-radius: 6px;")
        btn_right.clicked.connect(self.move_right)
        bottom_row.addWidget(btn_right, stretch=1)

        btn_backspace = QPushButton(" Effacer")
        btn_backspace.setProperty("is_vkb", True); btn_backspace.setFocusPolicy(Qt.NoFocus); btn_backspace.setMinimumHeight(40)
        try: btn_backspace.setIcon(qta.icon("fa5s.backspace", color="white"))
        except: pass
        btn_backspace.setStyleSheet("background-color: #e67e22; color: white; font-weight: bold; border-radius: 6px;")
        btn_backspace.clicked.connect(self.backspace)
        bottom_row.addWidget(btn_backspace, stretch=2)

        btn_enter = QPushButton(" Entrée ↵")
        btn_enter.setProperty("is_vkb", True); btn_enter.setFocusPolicy(Qt.NoFocus); btn_enter.setMinimumHeight(40)
        btn_enter.setStyleSheet("background-color: #2980b9; color: white; font-weight: bold; border-radius: 6px;")
        btn_enter.clicked.connect(self.simulate_enter)
        bottom_row.addWidget(btn_enter, stretch=2)

        keys_layout.addLayout(bottom_row)
        layout.addLayout(keys_layout, stretch=1)

        self.action_row = QHBoxLayout()
        self.btn_cancel = QPushButton(" Fermer")
        self.btn_cancel.setProperty("is_vkb", True); self.btn_cancel.setFocusPolicy(Qt.NoFocus); self.btn_cancel.setFixedHeight(40)
        self.btn_cancel.setStyleSheet("background-color: #c0392b; color: white; font-weight: bold; border-radius: 6px;")
        self.btn_cancel.clicked.connect(self.reject)
        
        self.btn_accept = QPushButton(" Valider")
        self.btn_accept.setProperty("is_vkb", True); self.btn_accept.setFocusPolicy(Qt.NoFocus); self.btn_accept.setFixedHeight(40)
        self.btn_accept.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; border-radius: 6px;")
        self.btn_accept.clicked.connect(self.accept)
        
        self.action_row.addWidget(self.btn_cancel)
        self.action_row.addWidget(self.btn_accept)
        layout.addLayout(self.action_row)

    def move_left(self):
        target = self.get_target()
        if self.direct_mode and target:
            try:
                target.setFocus()
                press = QKeyEvent(QEvent.KeyPress, Qt.Key_Left, Qt.NoModifier)
                release = QKeyEvent(QEvent.KeyRelease, Qt.Key_Left, Qt.NoModifier)
                QApplication.postEvent(target, press)
                QApplication.postEvent(target, release)
            except RuntimeError: 
                KeyboardFocusTracker.last_input_widget = None
        else: 
            self.display.cursorBackward(False)

    def move_right(self):
        target = self.get_target()
        if self.direct_mode and target:
            try:
                target.setFocus()
                press = QKeyEvent(QEvent.KeyPress, Qt.Key_Right, Qt.NoModifier)
                release = QKeyEvent(QEvent.KeyRelease, Qt.Key_Right, Qt.NoModifier)
                QApplication.postEvent(target, press)
                QApplication.postEvent(target, release)
            except RuntimeError: 
                KeyboardFocusTracker.last_input_widget = None
        else: 
            self.display.cursorForward(False)

    def toggle_direct_mode(self):
        self.direct_mode = self.btn_mode.isChecked()
        self.display.setVisible(not self.direct_mode)
        self.btn_accept.setVisible(not self.direct_mode)
        self.btn_cancel.setText(" Fermer" if self.direct_mode else " Annuler")

    def add_char(self, char):
        char_to_add = char.upper() if (char.isalpha() and self.is_shifted) else char.lower() if char.isalpha() else char
        target = self.get_target()
        if self.direct_mode:
            if target:
                try:
                    target.setFocus()
                    if hasattr(target, 'insert'): target.insert(char_to_add)
                    elif hasattr(target, 'insertPlainText'): target.insertPlainText(char_to_add)
                    else:
                        press = QKeyEvent(QEvent.KeyPress, 0, Qt.NoModifier, char_to_add)
                        release = QKeyEvent(QEvent.KeyRelease, 0, Qt.NoModifier, char_to_add)
                        QApplication.postEvent(target, press)
                        QApplication.postEvent(target, release)
                except RuntimeError: KeyboardFocusTracker.last_input_widget = None
        else: self.display.insert(char_to_add)

    def backspace(self):
        target = self.get_target()
        if self.direct_mode and target:
            try:
                target.setFocus()
                if hasattr(target, 'backspace'): target.backspace()
                elif hasattr(target, 'textCursor') and hasattr(target, 'setTextCursor'):
                    cursor = target.textCursor()
                    if cursor.hasSelection():
                        cursor.removeSelectedText()
                    else:
                        cursor.deletePreviousChar()
                    target.setTextCursor(cursor)
                else:
                    press = QKeyEvent(QEvent.KeyPress, Qt.Key_Backspace, Qt.NoModifier)
                    release = QKeyEvent(QEvent.KeyRelease, Qt.Key_Backspace, Qt.NoModifier)
                    QApplication.postEvent(target, press)
                    QApplication.postEvent(target, release)
            except RuntimeError: KeyboardFocusTracker.last_input_widget = None
        else: self.display.backspace()

    def simulate_enter(self):
        target = self.get_target()
        if self.direct_mode and target:
            try:
                target.setFocus()
                press = QKeyEvent(QEvent.KeyPress, Qt.Key_Return, Qt.NoModifier)
                release = QKeyEvent(QEvent.KeyRelease, Qt.Key_Return, Qt.NoModifier)
                QApplication.postEvent(target, press)
                QApplication.postEvent(target, release)
            except RuntimeError: KeyboardFocusTracker.last_input_widget = None
        else: self.accept()

    def toggle_shift(self):
        self.is_shifted = not self.is_shifted
        color = "#f1c40f" if self.is_shifted else "white"
        bg_color = "#2c3e50" if self.is_shifted else "#34495e"
        self.btn_shift.setStyleSheet(f"background-color: {bg_color}; color: {color}; font-weight: bold; border-radius: 6px;")
        for btn, char in self.letter_buttons:
            btn.setText(char.upper() if self.is_shifted else char.lower())

    def accept(self):
        if self.direct_mode:
            super().accept()
            return
        text_to_type = self.display.text()
        super().accept()
        if not text_to_type: return
        def simulate_typing():
            pyautogui.write(text_to_type, interval=0.005)
            pyautogui.press('enter')
        QTimer.singleShot(150, simulate_typing)
