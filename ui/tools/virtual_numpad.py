# ui/tools/virtual_numpad.py

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLineEdit, QGridLayout, QPushButton, 
    QHBoxLayout, QSizePolicy, QApplication, QWidget, QLabel
)
from PySide6.QtCore import Qt, QPoint

class VirtualNumpad(QDialog):
    def __init__(self, title="Saisie Numérique", mode="dialog", target_widget=None, allow_decimal=True, allow_leading_zero=True, allow_negative=False, initial_value="", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)

        # إعدادات النافذة بدون حواف
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        self.setFixedSize(420, 620)

        self.mode = mode
        self.target_widget = target_widget
        self.allow_decimal = allow_decimal
        self.allow_leading_zero = allow_leading_zero
        self.allow_negative = allow_negative  
        self.is_negative = False              

        # متغيرات السحب المحسّنة
        self._drag_start_pos = None
        self._drag_window_pos = None

        if self.mode == "direct" and self.target_widget:
            if hasattr(self.target_widget, 'text'):
                initial_value = self.target_widget.text()
            elif hasattr(self.target_widget, 'value'):
                initial_value = self.target_widget.value()

        if isinstance(initial_value, float):
            self.value = f"{initial_value:.3f}".rstrip('0').rstrip('.')
        else:
            self.value = str(initial_value).replace(',', '.')

        if self.value.startswith('-'):
            self.is_negative = True
            self.value = self.value[1:]

        self.is_new_entry = True if self.value else False

        self.init_ui()

    def showEvent(self, event):
        super().showEvent(event)
        screen = QApplication.primaryScreen().availableGeometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)

    # ==========================================
    # أحداث السحب المحسّنة (تعمل بشكل ممتاز باللمس والماوس)
    # ==========================================
    def mousePressEvent(self, event):
        # نحفظ نقطة البداية وموقع النافذة
        self._drag_start_pos = event.globalPosition().toPoint()
        self._drag_window_pos = self.pos()
        event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_start_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            # حساب الفرق وتحريك النافذة مباشرة أثناء السحب
            delta = event.globalPosition().toPoint() - self._drag_start_pos
            self.move(self._drag_window_pos + delta)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        # عند رفع الإصبع/الماوس، نوقف السحب
        self._drag_start_pos = None
        self._drag_window_pos = None
        super().mouseReleaseEvent(event)

    def init_ui(self):
        # الحاوي الخارجي (شفاف تماماً ليعطي انحناء للنافذة)
        main_container = QVBoxLayout(self)
        main_container.setContentsMargins(5, 5, 5, 5)
        main_container.setSpacing(0)

        # الحاوي الداخلي (خلفية بيضاء مع حواف مستديرة)
        inner_card = QWidget()
        inner_card.setObjectName("InnerCard")
        inner_card.setStyleSheet("""
            QWidget#InnerCard {
                background-color: #f0f3f5;
                border-radius: 15px;
                border: 1px solid #dcdde1;
            }
        """)
        inner_layout = QVBoxLayout(inner_card)
        inner_layout.setContentsMargins(0, 0, 0, 0)
        inner_layout.setSpacing(0)

        # ==========================================
        # شريط السحب العلوي (Drag Handle)
        # ==========================================
        self.drag_handle = QWidget()
        self.drag_handle.setFixedHeight(35)
        self.drag_handle.setCursor(Qt.OpenHandCursor)
        self.drag_handle.setStyleSheet("""
            QWidget {
                background-color: transparent;
                border-top-left-radius: 15px;
                border-top-right-radius: 15px;
            }
        """)
        handle_layout = QHBoxLayout(self.drag_handle)
        handle_layout.setContentsMargins(10, 0, 10, 0)
        
        # مقبض بصري
        grip = QLabel("━━━  ⠿  ━━━")
        grip.setAlignment(Qt.AlignCenter)
        grip.setStyleSheet("color: #bdc3c7; font-size: 16px; background-color: transparent; border: none;")
        handle_layout.addWidget(grip)
        
        inner_layout.addWidget(self.drag_handle)

        # ==========================================
        # محتوى اللوحة
        # ==========================================
        content_layout = QVBoxLayout()
        content_layout.setSpacing(15)
        content_layout.setContentsMargins(20, 5, 20, 20)

        # شاشة العرض
        self.display = QLineEdit()
        self.display.setReadOnly(True)
        self.display.setAlignment(Qt.AlignCenter)
        self.display.setMinimumHeight(75)
        self.display.setStyleSheet("""
            QLineEdit {
                font-size: 42px; font-weight: bold; color: #2c3e50;
                background-color: #ffffff; border: 2px solid #dcdde1;
                border-radius: 12px; padding: 10px;
            }
        """)
        default_display = "" if self.allow_leading_zero else "0"
        self.display.setText(self.value if self.value else default_display)
        content_layout.addWidget(self.display)

        # خلفية الأزرار (Card Button Pad)
        pad_container = QWidget()
        pad_container.setObjectName("ButtonPad")
        pad_container.setStyleSheet("""
            QWidget#ButtonPad {
                background-color: #ffffff;
                border-radius: 12px;
                border: 1px solid #e0e0e0;
            }
        """)
        pad_layout = QVBoxLayout(pad_container)
        pad_layout.setContentsMargins(10, 10, 10, 10)
        pad_layout.setSpacing(8)

        grid = QGridLayout()
        grid.setSpacing(8)

        buttons = [
            ('7', 0, 0, 1, 1), ('8', 0, 1, 1, 1), ('9', 0, 2, 1, 1), ('⌫', 0, 3, 1, 1),
            ('4', 1, 0, 1, 1), ('5', 1, 1, 1, 1), ('6', 1, 2, 1, 1), ('✖', 1, 3, 1, 1),
            ('1', 2, 0, 1, 1), ('2', 2, 1, 1, 1), ('3', 2, 2, 1, 1),
            ('C', 3, 0, 1, 1), ('0', 3, 1, 1, 1), ('.', 3, 2, 1, 1),
        ]

        if self.allow_negative:
            grid.addWidget(self._create_btn("+/-", "#c0392b", "#96281b", 26, self.toggle_sign), 2, 3, 2, 1)

        for text, row, col, r_span, c_span in buttons:
            if text == '.' and not self.allow_decimal:
                continue

            if text == '⌫':
                btn = self._create_btn(text, "#f39c12", "#d68910", 24, self.backspace)
            elif text == '✖':
                btn = self._create_btn(text, "#95a5a6", "#7f8c8d", 24, self.reject)
            elif text == 'C':
                btn = self._create_btn(text, "#e74c3c", "#c0392b", 24, self.clear_display)
            else:
                btn = self._create_btn(text, "#f8f9fa", "#dcdde1", 30, lambda checked, t=text: self.append_char(t))

            grid.addWidget(btn, row, col, r_span, c_span)

        pad_layout.addLayout(grid)
        content_layout.addWidget(pad_container)

        # زر التحقق السفلي (Valider) - تم تكبيره وتحسينه لللمس
        btn_enter = QPushButton("✔  Valider")
        btn_enter.setMinimumHeight(70) # زيادة الارتفاع الأدنى
        btn_enter.setCursor(Qt.PointingHandCursor)
        btn_enter.setStyleSheet("""
            QPushButton { 
                background-color: #27ae60; color: white; 
                font-weight: bold; font-size: 26px; 
                border: none; border-radius: 12px;
                padding: 10px; /* مساحة داخلية لمنع ضيق الزر */
            }
            QPushButton:pressed { 
                background-color: #219150;
            }
        """)
        btn_enter.clicked.connect(self.accept)
        content_layout.addWidget(btn_enter)

        inner_layout.addLayout(content_layout)
        main_container.addWidget(inner_card)

    def _create_btn(self, text, bg_color, pressed_color, font_size, callback):
        btn = QPushButton(text)
        btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg_color}; 
                border: none;
                border-radius: 8px; 
                font-size: {font_size}px; 
                font-weight: bold; 
                color: {"white" if bg_color != "#f8f9fa" else "#2c3e50"}; 
            }}
            QPushButton:pressed {{ 
                background-color: {pressed_color}; 
            }}
        """)
        btn.clicked.connect(callback)
        return btn

    def toggle_sign(self):
        self.is_negative = not self.is_negative
        self._update_display()

    def _update_display(self):
        sign = "-" if self.is_negative else ""
        text_to_show = self.value if self.value else ("" if self.allow_leading_zero else "0")
        
        if self.is_negative:
            self.display.setStyleSheet("""
                QLineEdit {
                    font-size: 42px; font-weight: bold; color: #c0392b;
                    background-color: #fdedec; border: 2px solid #e74c3c;
                    border-radius: 12px; padding: 10px;
                }
            """)
        else:
            self.display.setStyleSheet("""
                QLineEdit {
                    font-size: 42px; font-weight: bold; color: #2c3e50;
                    background-color: #ffffff; border: 2px solid #dcdde1;
                    border-radius: 12px; padding: 10px;
                }
            """)
            
        self.display.setText(f"{sign}{text_to_show}")
        self._sync_with_target()

    def keyPressEvent(self, event):
        key = event.key()
        text = event.text()

        if Qt.Key_0 <= key <= Qt.Key_9:
            self.append_char(text)
        elif text in ['.', ',']:
            if self.allow_decimal:
                self.append_char('.')
        elif key == Qt.Key_Backspace:
            self.backspace()
        elif key == Qt.Key_Delete:
            self.clear_display()
        elif key in (Qt.Key_Return, Qt.Key_Enter):
            self.accept()
        elif key == Qt.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(event)

    def _sync_with_target(self):
        if self.mode == "direct" and self.target_widget:
            sign = "-" if self.is_negative else ""
            val_to_set = self.value
            if not val_to_set or val_to_set == '.':
                val_to_set = "" if self.allow_leading_zero else "0"

            final_text = f"{sign}{val_to_set}"

            if hasattr(self.target_widget, 'setText'):
                self.target_widget.setText(final_text)
            elif hasattr(self.target_widget, 'setValue'):
                try:
                    num_val = float(final_text) if final_text and final_text != '-' else 0.0
                    self.target_widget.setValue(num_val)
                except ValueError:
                    pass

    def append_char(self, char):
        if self.is_new_entry:
            self.value = ""
            self.is_new_entry = False

        if char == '.' and '.' in self.value:
            return

        if char == '.' and not self.value:
            self.value = "0"

        if not self.allow_leading_zero and self.value == "0" and char != '.':
            self.value = char
        else:
            self.value += char

        self._update_display()

    def clear_display(self):
        self.value = ""
        self.is_new_entry = False
        self.is_negative = False  
        self._update_display()

    def backspace(self):
        if self.is_new_entry:
            self.is_new_entry = False

        self.value = self.value[:-1]
        self._update_display()

    def get_value(self):
        sign = "-" if self.is_negative else ""
        val = self.value if (self.value and self.value != '.') else ("" if self.allow_leading_zero else "0")
        return f"{sign}{val}"