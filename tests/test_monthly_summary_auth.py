import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from ui.widgets.reports.monthly_summary_view import MonthlySummaryView
from ui.tools.virtual_keyboard import VirtualPasswordInputDialog


class TestMonthlySummaryAuth(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        # Reset class-level session before each test
        MonthlySummaryView._session_authenticated = False
        self.mock_manager = MagicMock()
        self.mock_manager.users.authenticate.return_value = True
        self.mock_manager.users.verify_admin_password.return_value = True

    def test_virtual_password_input_dialog_no_auto_keyboard(self):
        """التحقق من أن نافذة إدخال كلمة المرور لا تفتح الكيبورد الافتراضي تلقائياً بشكل مزعج"""
        dlg = VirtualPasswordInputDialog()
        self.assertFalse(dlg.auto_open_keyboard)

    def test_monthly_summary_session_persistence_and_navigation(self):
        """التحقق من حفظ جلسة المدير وعدم طلب كلمة المرور عند التنقل بين الواجهات"""
        view = MonthlySummaryView(self.mock_manager)
        self.assertFalse(view._is_authenticated)
        self.assertFalse(view.btn_unlock.isHidden())
        self.assertTrue(view.btn_logout.isHidden())

        # تسجيل الدخول بنجاح
        view._is_authenticated = True
        MonthlySummaryView._session_authenticated = True
        view._update_auth_ui_state()

        self.assertTrue(view.btn_unlock.isHidden())
        self.assertFalse(view.btn_logout.isHidden())

        # محاكاة التنقل خارج الواجهة والعودة (hideEvent -> showEvent)
        view.hide()
        self.assertTrue(view._is_authenticated, "hideEvent ne doit pas déconnecter l'administrateur")
        self.assertTrue(MonthlySummaryView._session_authenticated)

        view.show()
        self.assertTrue(view._is_authenticated, "showEvent doit conserver la session active sans redemander le mot de passe")

    def test_monthly_summary_lock_session(self):
        """التحقق من قفل الجلسة عبر زر تسجيل الخروج / القفل"""
        view = MonthlySummaryView(self.mock_manager)
        view._is_authenticated = True
        MonthlySummaryView._session_authenticated = True
        view._update_auth_ui_state()

        with patch("PySide6.QtWidgets.QMessageBox.information"):
            view.lock_session()

        self.assertFalse(view._is_authenticated)
        self.assertFalse(MonthlySummaryView._session_authenticated)
        self.assertFalse(view.btn_unlock.isHidden())
        self.assertTrue(view.btn_logout.isHidden())
        self.assertEqual(view.table.rowCount(), 1)
        self.assertIn("Accès Administrateur requis", view.table.item(0, 0).text())


    def test_inline_password_unlock_success(self):
        """التحقق من نجاح فك القفل عبر كتابة كلمة المرور مباشرة في حقل الواجهة"""
        view = MonthlySummaryView(self.mock_manager)
        self.assertFalse(view._is_authenticated)
        self.assertFalse(view.auth_container.isHidden())
        self.assertFalse(view.inp_password.isHidden())

        view.inp_password.setText("secret_admin_pass")
        with patch.object(view, "load_data") as mock_load:
            view._on_inline_unlock()
            mock_load.assert_called_once()

        self.assertTrue(view._is_authenticated)
        self.assertTrue(MonthlySummaryView._session_authenticated)
        self.assertTrue(view.auth_container.isHidden())
        self.assertFalse(view.btn_logout.isHidden())
        self.assertEqual(view.inp_password.text(), "")

    def test_inline_password_unlock_failure(self):
        """التحقق من ظهور رسالة الخطأ المضمنة في الواجهة عند إدخال كلمة مرور خاطئة دون فتح أي دايلوج"""
        self.mock_manager.users.authenticate.return_value = False
        self.mock_manager.users.verify_admin_password.return_value = False

        view = MonthlySummaryView(self.mock_manager)
        view.inp_password.setText("wrong_password")
        with patch.object(view, "load_data") as mock_load:
            view._on_inline_unlock()
            mock_load.assert_not_called()

        self.assertFalse(view._is_authenticated)
        self.assertFalse(MonthlySummaryView._session_authenticated)
        self.assertFalse(view.lbl_auth_error.isHidden())
        self.assertIn("Mot de passe incorrect", view.lbl_auth_error.text())

    def test_no_modal_dialog_on_show_when_locked(self):
        """التحقق من عدم ظهور أي دايلوج في منتصف الشاشة عند فتح الواجهة وهي مقفلة"""
        view = MonthlySummaryView(self.mock_manager)
        self.assertFalse(view._is_authenticated)

        with patch("ui.tools.virtual_keyboard.VirtualPasswordInputDialog.getText") as mock_dialog:
            view.show()
            mock_dialog.assert_not_called()

        # الواجهة تبقى مقفلة بدون إزعاج المستخدم بدايلوج منبثق
        self.assertFalse(view._is_authenticated)
        self.assertFalse(view.auth_container.isHidden())

    def test_toggle_password_visibility(self):
        """التحقق من زر إظهار وإخفاء كلمة المرور"""
        from PySide6.QtWidgets import QLineEdit
        view = MonthlySummaryView(self.mock_manager)
        self.assertEqual(view.inp_password.echoMode(), QLineEdit.Password)

        view._toggle_password_visibility()
        self.assertEqual(view.inp_password.echoMode(), QLineEdit.Normal)

        view._toggle_password_visibility()
        self.assertEqual(view.inp_password.echoMode(), QLineEdit.Password)


if __name__ == "__main__":
    unittest.main()
