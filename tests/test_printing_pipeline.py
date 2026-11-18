import os
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QApplication

import utils
from ui.dialogs.printer_label import LocalLabelPrinter
from ui.tools import print_functions


class TestPrintingPipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_thermal_receipt_draws_facture_and_versement_without_error(self):
        tc = {
            "printer_name": "XP-80C",
            "page_width": 576,
            "margin": 20,
            "center_x": 288,
            "font_title": 28,
            "font_norm": 20,
            "shop_name": "GoldShop Test",
            "shop_address": "Alger",
            "shop_phone": "0555000000",
            "footer_text": "Merci",
            "show_qr": False,
        }
        facture_data = {
            "facture_number": "FAC-20261118-0001",
            "client_name": "Client Test",
            "seller_name": "Vendeur 1",
            "total_brut": 50000.0,
            "discount": 2000.0,
            "net_to_pay": 48000.0,
            "cash_paid": 48000.0,
            "items": [
                {
                    "name": "Bague 18K",
                    "item_type": "WEIGHT",
                    "sold_weight_g": 2.5,
                    "sold_quantity": 1,
                    "total_price_da": 50000.0,
                }
            ],
        }
        versement_data = {
            "versement_number": "VRS-000012",
            "client_name": "Client Versement",
            "document_type": "VERSEMENT_PRODUIT",
            "facture_number": "00012",
            "versements": [
                {"date": "2026-11-18", "amount": 20000.0, "poids_deduit_g": 1.0}
            ],
            "items": [
                {
                    "designation": "Collier",
                    "item_type": "WEIGHT",
                    "weight": 4.0,
                    "selling_price": 80000.0,
                    "deducted_g": 1.0,
                    "remaining_g": 3.0,
                }
            ],
        }

        img = QImage(576, 1400, QImage.Format_RGB32)
        img.fill(0xFFFFFF)
        painter = QPainter(img)
        try:
            y1 = print_functions._draw_thermal_receipt(painter, 576, facture_data, tc, "Facture")
            y2 = print_functions._draw_thermal_receipt(painter, 576, versement_data, tc, "Versement")
        finally:
            painter.end()

        self.assertGreater(y1, 100)
        self.assertGreater(y2, 100)

    def test_execute_qpainter_print_validates_printer_and_calls_qprinter(self):
        with patch.object(print_functions, "get_thermal_config", return_value={"printer_name": ""}):
            with self.assertRaises(ValueError):
                print_functions.print_thermal_facture({"items": []})

        fake_printer = MagicMock()
        fake_printer.isValid.return_value = True
        fake_rect = MagicMock()
        fake_rect.width.return_value = 576
        fake_printer.pageRect.return_value = fake_rect

        fake_painter = MagicMock()
        fake_painter.begin.return_value = True

        with (
            patch.object(print_functions, "get_thermal_config", return_value={"printer_name": "XP-80C", "page_width": 576}),
            patch.object(print_functions, "QPrinter", return_value=fake_printer),
            patch.object(print_functions, "QPainter", return_value=fake_painter),
            patch.object(print_functions, "_draw_thermal_receipt", return_value=400) as mock_draw,
        ):
            res = print_functions.print_thermal_facture({"items": []}, printer_name="XP-80C")

        self.assertEqual(res, 1)
        fake_printer.setPrinterName.assert_called_once_with("XP-80C")
        fake_painter.begin.assert_called_once_with(fake_printer)
        fake_painter.end.assert_called_once()
        mock_draw.assert_called_once()

    def test_win32_calculate_and_print_lifecycle(self):
        fake_devmode = MagicMock()
        fake_devmode.Fields = 0
        fake_hdc = MagicMock()
        print_fn = MagicMock(side_effect=[600, None])

        with (
            patch.object(utils.win32print, "OpenPrinter", return_value=99) as mock_open,
            patch.object(utils.win32print, "GetPrinter", return_value={"pDevMode": fake_devmode}),
            patch.object(utils.win32print, "ClosePrinter") as mock_close,
            patch.object(utils.win32gui, "CreateDC", return_value=1234),
            patch.object(utils.win32ui, "CreateDCFromHandle", return_value=fake_hdc),
        ):
            utils.calculate_and_print(
                {"id": 1},
                print_fn,
                "Facture Test",
                "Thermal-80",
                theme="default",
                language="ar",
            )

        mock_open.assert_called_once_with("Thermal-80")
        mock_close.assert_called_once_with(99)
        fake_hdc.StartDoc.assert_called_once_with("Facture Test")
        fake_hdc.StartPage.assert_called_once()
        fake_hdc.EndPage.assert_called_once()
        fake_hdc.EndDoc.assert_called_once()
        fake_hdc.DeleteDC.assert_called_once()
        self.assertEqual(print_fn.call_count, 2)

    def test_label_printer_generates_tspl_and_sends_raw_bytes_via_win32print(self):
        label_config = {
            "label": {"width_mm": 60, "height_mm": 20, "gap_mm": 2},
            "print_area": {"x_pos_mm": 0, "y_pos_mm": 0},
            "elements": {
                "product_name": {"show": True, "center_x_mm": 30, "y_pos_mm": 2, "font_size": 14},
                "price": {"show": True, "center_x_mm": 30, "y_pos_mm": 7, "font_size": 14},
                "weight": {"show": True, "center_x_mm": 30, "y_pos_mm": 12, "font_size": 12, "decimals": 2},
                "barcode": {"show": True, "center_x_mm": 30, "y_pos_mm": 14, "module_width_mm": 0.2, "height_mm": 5},
            },
        }
        item_data = {
            "name": "Bague 18K",
            "selling_price": 45000,
            "weight": 3.45,
            "barcode": "GS12345678",
        }

        img = LocalLabelPrinter.create_jewelry_label(label_config, item_data)
        self.assertEqual(img.mode, "1")
        tspl = LocalLabelPrinter.get_tspl_for_image(label_config, img, copies=2)
        self.assertIn(b"SIZE 60 mm, 20 mm", tspl)
        self.assertIn(b"BITMAP 0,0,", tspl)
        self.assertIn(b"PRINT 2", tspl)

        with (
            patch("ui.dialogs.printer_label.win32print.OpenPrinter", return_value=77) as mock_open,
            patch("ui.dialogs.printer_label.win32print.StartDocPrinter") as mock_doc,
            patch("ui.dialogs.printer_label.win32print.StartPagePrinter") as mock_page,
            patch("ui.dialogs.printer_label.win32print.WritePrinter") as mock_write,
            patch("ui.dialogs.printer_label.win32print.EndPagePrinter") as mock_end_page,
            patch("ui.dialogs.printer_label.win32print.EndDocPrinter") as mock_end_doc,
            patch("ui.dialogs.printer_label.win32print.ClosePrinter") as mock_close,
        ):
            ok, msg = LocalLabelPrinter.send_to_printer("Xprinter-Label", tspl)

        self.assertTrue(ok, msg)
        mock_open.assert_called_once_with("Xprinter-Label")
        mock_doc.assert_called_once()
        mock_page.assert_called_once()
        mock_write.assert_called_once_with(77, tspl)
        mock_end_page.assert_called_once()
        mock_end_doc.assert_called_once()
        mock_close.assert_called_once_with(77)


if __name__ == "__main__":
    unittest.main()
