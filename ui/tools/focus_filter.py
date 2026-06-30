# ui/tools/focus_filter.py

from PySide6.QtCore import QObject, QEvent, QTimer
from PySide6.QtWidgets import QLineEdit, QAbstractSpinBox

class GlobalFocusSelectFilter(QObject):
    """
    فلتر أحداث شامل يراقب جميع حقول الإدخال في البرنامج.
    عندما يكتسب الحقل التركيز (Focus) أو يتم الضغط عليه، يقوم بتحديد محتواه بالكامل.
    """
    def eventFilter(self, obj, event):
        # نتحقق مما إذا كان الكائن هو حقل نصي أو حقل أرقام
        if isinstance(obj, (QLineEdit, QAbstractSpinBox)):
            
            # إذا تم الدخول إلى الحقل (بالماوس أو بزر Tab)
            if event.type() in (QEvent.FocusIn, QEvent.MouseButtonRelease):
                
                # نستخدم QTimer.singleShot بتأخير 0 ملي ثانية
                # هذا السر يضمن أن التحديد يحدث "بعد" أن ينهي النظام وضع المؤشر، 
                # مما يمنع النظام من إلغاء التحديد فوراً.
                if isinstance(obj, QLineEdit):
                    QTimer.singleShot(0, obj.selectAll)
                elif isinstance(obj, QAbstractSpinBox):
                    # في حقول الأرقام، المربع النصي الداخلي هو ما يجب تحديده
                    QTimer.singleShot(0, obj.lineEdit().selectAll)
                    
        # تمرير الحدث ليكمل مساره الطبيعي
        return super().eventFilter(obj, event)