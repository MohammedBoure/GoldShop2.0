# ui/tools/print_functions.py

import os
import io
import json
import logging
import datetime
import copy
from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QPainter, QFont, QColor, QPen, QImage
from PySide6.QtPrintSupport import QPrinterInfo, QPrinter

logger = logging.getLogger(__name__)

CREDIT_CLIENT_MARKERS = {
    "CREDIT_CLIENT",
    "LEGACY_CLIENT_CREDIT",
    "LEGACY_CLIENT_CREDIT_PAYMENT",
    "LEGACY_OPENING_BALANCE",
}
VERSEMENT_LIBRE_MARKERS = {"VERSEMENT_LIBRE", "LIBRE"}
VERSEMENT_PRODUIT_MARKERS = {
    "VERSEMENT_PRODUIT",
    "ACOMPTE_PRODUIT",
    "PAIEMENT_FACTURE",
    "PRODUIT",
    "FACTURE",
}


def _thermal_code(value):
    return str(value or "").strip().upper()


def _thermal_qr_is_disabled(value):
    text = _thermal_code(value)
    return text in {"DESACTIVE", "DÉSACTIVÉ", "DÃ©SACTIVÃ©", "DÃ‰SACTIVÃ‰"}


def _thermal_is_credit_client_entry(entry):
    return (
        _thermal_code(entry.get("document_type")) in CREDIT_CLIENT_MARKERS
        or _thermal_code(entry.get("client_document_type")) in CREDIT_CLIENT_MARKERS
        or _thermal_code(entry.get("payment_type")) in CREDIT_CLIENT_MARKERS
        or _thermal_code(entry.get("source_type")) in {"LEGACY_CLIENT_CREDIT", "LEGACY_OPENING_BALANCE"}
    )


def _thermal_payment_entries(data):
    return data.get("versements") or data.get("payments_history") or data.get("payments") or []


def _thermal_first_value(entry, *keys, default=None):
    for key in keys:
        value = entry.get(key)
        if value not in (None, ""):
            return value
    return default


def _thermal_safe_float(value, default=0.0):
    try:
        return float(value if value not in (None, "") else default)
    except (TypeError, ValueError):
        return float(default)


def _thermal_has_value(entry, *keys):
    return any(entry.get(key) not in (None, "") for key in keys)


def _thermal_format_datetime(value):
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d %H:%M")
    text = str(value or "").strip()
    return text


def _thermal_document_datetime(data, doc_type):
    if doc_type == "Facture":
        value = _thermal_first_value(
            data,
            "printed_at",
            "print_date",
            "printed_date",
            "date",
            "sale_date",
            default=datetime.datetime.now(),
        )
    else:
        value = _thermal_first_value(
            data,
            "printed_at",
            "date",
            "payment_date",
            "opened_at",
            default=datetime.datetime.now(),
        )
    return _thermal_format_datetime(value) or datetime.datetime.now().strftime("%Y-%m-%d %H:%M")


def _thermal_payment_datetime(entry):
    return _thermal_format_datetime(
        _thermal_first_value(entry, "payment_date", "activity_date", "date", "opened_at", "created_at", default="")
    )


def _thermal_payment_amount(entry):
    return _thermal_safe_float(
        _thermal_first_value(entry, "amount", "amount_base", "paid_amount", "total_amount", default=0)
    )


def _thermal_payment_weight(entry):
    return _thermal_safe_float(
        _thermal_first_value(entry, "weight", "purchased_weight", "paid_weight", default=0)
    )


def _thermal_payment_rate(entry):
    rate = _thermal_safe_float(
        _thermal_first_value(entry, "metal_rate_reference", "metal_rate_at_payment", "current_gold_rate", default=0)
    )
    if rate > 0:
        return rate
    amount = _thermal_payment_amount(entry)
    weight = _thermal_payment_weight(entry)
    return round(amount / weight, 2) if amount > 0 and weight > 0 else 0.0


def _thermal_facture_number_from_entry(entry):
    number = str(
        _thermal_first_value(entry, "facture_number", "invoice_number", "sale_number", default="")
    ).strip()
    return number if number.upper().startswith("F-") else ""


def _thermal_facture_document_number_from_entry(entry):
    number = str(
        _thermal_first_value(entry, "facture_number", "invoice_number", "sale_number", default="")
    ).strip()
    if not number or _thermal_code(number).startswith(("V-", "VL-", "VP-", "VRS-", "VERSEMENT")):
        return ""
    return number


def _thermal_contains_credit_client(data):
    if _thermal_is_credit_client_entry(data):
        return True
    return any(_thermal_is_credit_client_entry(payment) for payment in _thermal_payment_entries(data))


def _thermal_is_product_versement_entry(entry):
    document_type = _thermal_code(entry.get("document_type") or entry.get("client_document_type"))
    payment_type = _thermal_code(entry.get("payment_type"))
    return bool(
        entry.get("sale_id")
        or entry.get("invoice_id")
        or entry.get("facture_id")
        or document_type in VERSEMENT_PRODUIT_MARKERS
        or payment_type in VERSEMENT_PRODUIT_MARKERS
    )


def _thermal_sale_reference(data):
    facture_number = _thermal_facture_number_from_entry(data)
    if facture_number:
        return facture_number
    for payment in _thermal_payment_entries(data):
        facture_number = _thermal_facture_number_from_entry(payment)
        if facture_number:
            return facture_number
    return ""


def _thermal_versement_kind(data):
    if _thermal_contains_credit_client(data):
        return "CREDIT_CLIENT"

    if _thermal_is_product_versement_entry(data) or any(
        _thermal_is_product_versement_entry(payment) for payment in _thermal_payment_entries(data)
    ):
        return "VERSEMENT_PRODUIT"
    return "VERSEMENT_LIBRE"


def _validate_thermal_versement_payload(data):
    kind = _thermal_versement_kind(data)
    if kind == "CREDIT_CLIENT":
        raise ValueError("Credit client requires a dedicated thermal credit template.")

    versement_number = _thermal_versement_operation_number(data)
    if kind == "VERSEMENT_PRODUIT" and not versement_number:
        raise ValueError("A product versement thermal receipt requires a versement number.")
    if kind == "VERSEMENT_LIBRE" and not (versement_number or data.get("id") or data.get("receipt_id") or data.get("versements")):
        raise ValueError("A free versement thermal receipt requires a real free versement.")
    return kind

# =========================================================================
# 🟢 دوال مساعدة لتوليد الصور (QR و Barcode) 🟢
# =========================================================================
def generate_qr_image(link, size):
    try:
        import qrcode
        qr = qrcode.QRCode(version=1, box_size=10, border=1)
        qr.add_data(link); qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white").convert("RGBA")
        qimg = QImage(img.tobytes("raw", "RGBA"), img.size[0], img.size[1], QImage.Format_RGBA8888)
        return qimg.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    except Exception as e:
        logger.error(f"Erreur QR: {e}")
        return None

def generate_barcode_image(data, width, height, with_text=False):
    try:
        import barcode; from barcode.writer import ImageWriter
        CODE = barcode.get_barcode_class('code128')
        writer = ImageWriter()
        code = CODE(str(data), writer=writer)
        options = {'module_width': 0.3, 'module_height': 8.0, 'font_size': 0 if not with_text else 6, 'text_distance': 1.0, 'quiet_zone': 1.0}
        fp = io.BytesIO()
        code.write(fp, options); fp.seek(0)
        return QImage.fromData(fp.read()).scaled(width, height, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    except Exception as e:
        logger.error(f"Erreur Barcode: {e}")
        return None

def get_thermal_config():
    tc = {}
    if os.path.exists("config.json"):
        try:
            with open("config.json", 'r', encoding='utf-8') as f:
                tc = json.load(f).get("thermal_config", {})
        except: pass
    if not isinstance(tc, dict):
        return {}

    themes = tc.get("themes") if isinstance(tc.get("themes"), dict) else {}
    active_theme = str(tc.get("active_theme") or "").strip()
    theme = themes.get(active_theme) if active_theme else None
    if isinstance(theme, dict):
        merged = copy.deepcopy(tc)
        for key, value in theme.items():
            if key not in ("active_theme", "themes"):
                merged[key] = copy.deepcopy(value)
        merged["active_theme"] = active_theme
        merged["themes"] = themes
        tc = merged
    return tc


def _thermal_versement_operation_number(data):
    number = _thermal_entry_versement_number(data)
    if number:
        return number
    for payment in data.get('versements') or data.get('payments_history') or []:
        number = _thermal_entry_versement_number(payment)
        if number:
            return number
    return ""


def _thermal_entry_versement_number(entry):
    for key in ("versement_operation_number", "operation_number"):
        number = str((entry or {}).get(key) or "").strip()
        if number:
            return number
    for key in ("document_number", "display_number", "receipt_number"):
        number = str((entry or {}).get(key) or "").strip()
        if number.upper().startswith(("V-", "VL-", "VP-", "VRS-", "VERSEMENT")):
            return number
    return ""


def _thermal_display_number(number):
    return f"{int(number):05d}" if str(number).isdigit() else str(number or "")


def _thermal_facture_number(data):
    return _thermal_facture_document_number_from_entry(data)


def _thermal_product_name(data):
    direct_name = str(
        _thermal_first_value(data, "product_name", "item_name", "name", default="")
    ).strip()
    if direct_name:
        return direct_name

    names = []
    for item in data.get("items") or []:
        name = str(_thermal_first_value(item, "name", "item_name", "description", default="")).strip()
        if name:
            names.append(name)
    if len(names) == 1:
        return names[0]
    if len(names) > 1:
        return "Articles multiples"
    return ""


def _thermal_versement_summary_lines(data, currency):
    """ملخص versement بسيط للزبون: مدفوع + وزن مكتسب + باقي وزن"""
    payments = _thermal_payment_entries(data)
    
    total_paid = _thermal_safe_float(_thermal_first_value(data, "total_paid", "paid_amount", "paid", default=0))
    if not _thermal_has_value(data, "total_paid", "paid_amount", "paid"):
        total_paid = sum(_thermal_payment_amount(payment) for payment in payments)

    paid_weight = _thermal_safe_float(
        _thermal_first_value(data, "exact_paid_weight", "paid_weight", "paid_weight_equiv", default=0)
    )
    if not _thermal_has_value(data, "exact_paid_weight", "paid_weight", "paid_weight_equiv"):
        paid_weight = sum(_thermal_payment_weight(payment) for payment in payments)

    lines = []
    lines.append(("Total paye :", f"{total_paid:,.2f} {currency}"))

    if paid_weight > 0 or _thermal_has_value(data, "exact_paid_weight", "paid_weight", "paid_weight_equiv"):
        lines.append(("Poids acquis :", f"{paid_weight:.2f} Gr"))
    
    if _thermal_has_value(data, "remaining_weight", "remainder_weight"):
        remaining_weight = _thermal_safe_float(
            _thermal_first_value(data, "remaining_weight", "remainder_weight", default=0)
        )
        if remaining_weight > 0:
            lines.append(("Reste poids :", f"{remaining_weight:.2f} Gr"))
    return lines


def _thermal_product_summary_lines(data, currency):
    """ملخص منتج - يُستخدم فقط للطباعة الحرارية إذا احتجناه لاحقاً"""
    payments = _thermal_payment_entries(data)
    total_paid = _thermal_safe_float(_thermal_first_value(data, "total_paid", "paid_amount", "paid", default=0))
    if not _thermal_has_value(data, "total_paid", "paid_amount", "paid"):
        total_paid = sum(_thermal_payment_amount(payment) for payment in payments)

    paid_weight = _thermal_safe_float(
        _thermal_first_value(data, "exact_paid_weight", "paid_weight", "paid_weight_equiv", default=0)
    )
    if not _thermal_has_value(data, "exact_paid_weight", "paid_weight", "paid_weight_equiv"):
        paid_weight = sum(_thermal_payment_weight(payment) for payment in payments)

    lines = []
    if _thermal_has_value(data, "total_weight"):
        lines.append(("Poids total :", f"{_thermal_safe_float(data.get('total_weight')):.2f} Gr"))
    if _thermal_has_value(data, "total_quantity"):
        quantity = _thermal_safe_float(data.get("total_quantity"))
        if quantity > 0:
            lines.append(("Quantite totale :", f"{quantity:g}"))

    lines.append(("Total paye :", f"{total_paid:,.2f} {currency}"))

    if paid_weight > 0 or _thermal_has_value(data, "exact_paid_weight", "paid_weight", "paid_weight_equiv"):
        lines.append(("Poids acquis :", f"{paid_weight:.2f} Gr"))
    if _thermal_has_value(data, "remaining_weight", "remainder_weight"):
        remaining_weight = _thermal_safe_float(
            _thermal_first_value(data, "remaining_weight", "remainder_weight", default=0)
        )
        lines.append(("Reste poids :", f"{remaining_weight:.2f} Gr"))
    if _thermal_has_value(data, "remaining_quantity"):
        remaining_quantity = _thermal_safe_float(data.get("remaining_quantity"))
        if remaining_quantity > 0:
            lines.append(("Reste quantite :", f"{remaining_quantity:g}"))
    return lines


def _thermal_product_item_rows(data, currency):
    rows = []
    for item in data.get("items") or []:
        name = str(_thermal_first_value(item, "name", "item_name", "description", default="Article")).strip()
        total_weight = _thermal_safe_float(
            _thermal_first_value(item, "cart_sold_weight", "total_weight", "sold_weight", "weight", default=0)
        )
        total_amount = _thermal_safe_float(
            _thermal_first_value(item, "cart_line_total", "total_amount", "sold_price", default=0)
        )
        paid_weight = _thermal_safe_float(
            _thermal_first_value(item, "item_paid_weight", "paid_weight", default=0)
        )

        paid_amount_value = item.get("item_paid_amount")
        if paid_amount_value is None:
            paid_amount_value = item.get("allocated_payment")
        if paid_amount_value is None and total_weight > 0:
            paid_amount = total_amount * min(max(paid_weight, 0.0), total_weight) / total_weight
        else:
            paid_amount = _thermal_safe_float(paid_amount_value)
        paid_amount = min(max(paid_amount, 0.0), total_amount) if total_amount > 0 else max(paid_amount, 0.0)

        remaining_amount_value = item.get("item_remaining_amount")
        if remaining_amount_value is None:
            remaining_amount_value = item.get("remaining_amount")
        if remaining_amount_value is None:
            remaining_amount = max(0.0, total_amount - paid_amount)
        else:
            remaining_amount = max(0.0, _thermal_safe_float(remaining_amount_value))

        remaining_weight_value = item.get("item_remaining_weight")
        if remaining_weight_value is None:
            remaining_weight_value = item.get("remaining_weight")
        if remaining_weight_value is None:
            remaining_weight = max(0.0, total_weight - paid_weight)
        else:
            remaining_weight = max(0.0, _thermal_safe_float(remaining_weight_value))

        rows.append([
            name or "Article",
            f"{total_weight:.2f} Gr\n{total_amount:,.2f} {currency}",
            f"{paid_weight:.2f} Gr\n{paid_amount:,.2f} {currency}",
            f"{remaining_weight:.2f} Gr\n{remaining_amount:,.2f} {currency}",
            str(item.get("status") or "").strip(),
        ])
    return rows


def _thermal_versement_item_rows(data):
    rows = []
    for item in data.get("items") or []:
        code = str(
            _thermal_first_value(item, "barcode", "inventory_barcode", "item_barcode", default="")
            or ""
        ).strip()
        name = str(
            _thermal_first_value(item, "item_name", "name", "description", default="Article")
            or "Article"
        ).strip()
        remaining_weight = _thermal_safe_float(
            _thermal_first_value(item, "remaining_weight", "weight", "total_weight", default=0)
        )
        custom_note = str(_thermal_first_value(item, "custom_note", "note", default="") or "").strip()
        rows.append([code, name, f"{remaining_weight:.2f} Gr", custom_note])
    return rows


def _thermal_free_summary_lines(data, currency):
    payments = _thermal_payment_entries(data)
    if payments:
        total_amount = sum(_thermal_payment_amount(payment) for payment in payments)
        used_amount = sum(_thermal_safe_float(payment.get("used_amount")) for payment in payments)
        available_values = [
            _thermal_safe_float(value)
            for payment in payments
            for value in [_thermal_first_value(payment, "remaining_amount", "available_amount", default=None)]
            if value not in (None, "")
        ]
        available_amount = sum(available_values) if available_values else max(0.0, total_amount - used_amount)
    else:
        total_amount = _thermal_safe_float(_thermal_first_value(data, "total_amount", "amount", default=0))
        used_amount = _thermal_safe_float(data.get("used_amount"))
        available_value = _thermal_first_value(data, "remaining_amount", "available_amount", default=None)
        available_amount = (
            _thermal_safe_float(available_value)
            if available_value not in (None, "")
            else max(0.0, total_amount - used_amount)
        )

    lines = []
    if total_amount > 0:
        lines.append(("Montant libre :", f"{total_amount:,.2f} {currency}"))
    if used_amount > 0:
        lines.append(("Montant utilise :", f"{used_amount:,.2f} {currency}"))
    lines.append(("Disponible :", f"{max(0.0, available_amount):,.2f} {currency}"))
    return lines


def _thermal_document_numbers(data, doc_type):
    if doc_type == "Facture":
        primary_number = _thermal_facture_number(data) or data.get('sale_id', data.get('id', '0'))
        return _thermal_display_number(primary_number), "", ""

    if doc_type == "CreditClient":
        primary_number = (
            data.get("credit_number")
            or data.get("receipt_number")
            or data.get("operation_number")
            or data.get("sale_id")
            or data.get("id")
            or "0"
        )
        return _thermal_display_number(primary_number), "", ""

    versement_number = _thermal_versement_operation_number(data)
    sale_reference = _thermal_sale_reference(data)
    primary_number = versement_number or data.get('receipt_id') or data.get('id', '0')
    if (not primary_number or primary_number == "0") and data.get("versements"):
        primary_number = data["versements"][0].get("id", "0")
    return _thermal_display_number(primary_number), sale_reference, versement_number

# =========================================================================
# 🟢 محرك الرسم المركزي 🟢
# =========================================================================
def _draw_thermal_receipt(painter, width, data, tc, doc_type):
    cx = tc.get("center_x", 288)
    m = tc.get("margin", 20)
    ls = 6; y = 20 
    
    f_title = tc.get("font_title", 32)
    f_norm = tc.get("font_normal", 22)
    f_small = max(12, f_norm - 6)
    currency = data.get('currency', 'DA')

    def draw_text_absolute(text, x, y_abs, size, bold=False, align_right=False, limit=None, italic=False):
        font = QFont("Arial"); font.setPixelSize(size); font.setBold(bold); font.setItalic(italic); painter.setFont(font)
        fm = painter.fontMetrics(); tw = fm.horizontalAdvance(str(text))
        if align_right and limit: x = x + limit - tw
        painter.drawText(x, y_abs + fm.ascent(), str(text))
        return fm.height()

    def draw_text_center(text, size, bold=False):
        nonlocal y
        font = QFont("Arial"); font.setPixelSize(size); font.setBold(bold); painter.setFont(font)
        fm = painter.fontMetrics()
        for line in str(text).split('\n'):
            tw = fm.horizontalAdvance(line)
            painter.drawText(cx - (tw // 2), y + fm.ascent(), line)
            y += fm.height() + ls

    def wrap_text_to_lines(text, max_width, font):
        painter.setFont(font); fm = painter.fontMetrics()
        words = str(text).split(' ')
        lines = []; current_line = ""
        for word in words:
            test_line = f"{current_line} {word}".strip()
            if fm.horizontalAdvance(test_line) <= max_width: current_line = test_line
            else:
                if current_line: lines.append(current_line)
                current_line = word
        if current_line: lines.append(current_line)
        return lines

    # 🟢 دالة الجدول الديناميكية (تتعامل مع أي عدد أعمدة)
    def draw_table(headers, ratios, rows):
        nonlocal y
        num_cols = len(headers)
        table_w = width - (2 * m)
        cols = [int(table_w * r) for r in ratios]
        x_c = [m]
        for c in cols:
            x_c.append(x_c[-1] + c)
        
        painter.setPen(QPen(Qt.black, 1, Qt.SolidLine))
        painter.drawLine(m, y, width - m, y) 
        
        font_header = QFont("Arial"); font_header.setPixelSize(f_small); font_header.setBold(True)
        header_h = f_small + 10
        for i, h in enumerate(headers): 
            painter.setFont(font_header)
            painter.drawText(QRect(x_c[i] + 4, y + 2, cols[i] - 8, header_h), Qt.AlignLeft | Qt.AlignVCenter, str(h))
        y += header_h; painter.drawLine(m, y, width - m, y)

        start_y = y 
        font_cell = QFont("Arial"); font_cell.setPixelSize(f_small); font_cell.setBold(False)
        font_note = QFont("Arial"); font_note.setPixelSize(f_small - 2); font_note.setItalic(True)
        show_barcode = tc.get("show_item_barcode", True)

        for row in rows:
            cell_lines = []
            for i in range(num_cols):
                val = str(row[i]) if i < len(row) else ""
                lines = wrap_text_to_lines(val, cols[i] - 8, font_cell)
                cell_lines.append(lines)
            
            max_lines = max([len(lines) for lines in cell_lines]) if cell_lines else 1
            line_height = f_small + 4
            base_h = (max_lines * line_height) + 10
            
            # باركود في العمود الأول فقط إذا كان مفعّلاً
            if show_barcode and num_cols > 0:
                base_h = max(base_h, 45) 
            
            for i in range(num_cols):
                val = str(row[i]) if i < len(row) else ""
                if i == 0 and show_barcode and val and not any(c in val for c in '-/'):
                    b_w = cols[i] - 8; b_h = base_h - 10 
                    b_img = generate_barcode_image(val, b_w, b_h)
                    if b_img: painter.drawImage(x_c[i] + 4, y + 5, b_img)
                else:
                    painter.setFont(font_cell); fm = painter.fontMetrics(); text_y = y + 5
                    for line in cell_lines[i]:
                        painter.drawText(x_c[i] + 4, text_y + fm.ascent(), line); text_y += line_height
            
            y += base_h
            
            # الملاحظة بعد آخر عمود (إذا وُجدت)
            note_idx = num_cols
            if len(row) > note_idx and row[note_idx]:
                note_text = str(row[note_idx])
                note_col = min(1, num_cols - 1)
                note_w = cols[note_col] - 8 
                note_lines = wrap_text_to_lines(note_text, note_w, font_note)
                note_h = (len(note_lines) * (f_small + 2)) + 5
                painter.setFont(font_note); fm = painter.fontMetrics(); text_y = y
                for line in note_lines:
                    painter.drawText(x_c[note_col] + 4, text_y + fm.ascent(), line); text_y += f_small + 2
                y += note_h

            painter.drawLine(m, y, width - m, y) 

        for x_pos in x_c: painter.drawLine(x_pos, start_y, x_pos, y)
        y += 10

    # --- 1. HEADER & LOGO ---
    logo_path = tc.get("logo_path", "")
    if logo_path and os.path.exists(logo_path):
        img = QImage(logo_path)
        logo_settings = tc.get("logo_settings", {'scale': 100, 'threshold': 127})
        scale = logo_settings.get('scale', 100) / 100.0; thresh = logo_settings.get('threshold', 127)
        img = img.scaledToWidth(int(img.width() * scale), Qt.SmoothTransformation).convertToFormat(QImage.Format_Grayscale8)
        for iy in range(img.height()):
            for ix in range(img.width()):
                val = img.pixelColor(ix, iy).red()
                img.setPixelColor(ix, iy, QColor(0,0,0) if val <= thresh else QColor(255,255,255))
        painter.drawImage(cx - (img.width() // 2), y, img); y += img.height() + 5

    draw_text_center(tc.get("store_name", data.get("shopName", "Bijouterie")), f_title, bold=True)

    # --- 2. QR CODE & STORE INFO ---
    link = tc.get("qr_link", "")
    if link and not _thermal_qr_is_disabled(tc.get("qr_pos", "")):
        qr_size = tc.get("qr_size", 70)
        qimg = generate_qr_image(link, qr_size)
        if qimg: painter.drawImage(m, y, qimg)
        draw_text_absolute(tc.get("qr_text", ""), m + qr_size + 10, y + (qr_size//2) - (f_norm//2), f_norm, bold=True)
        y += qr_size + 10
    else:
        y += 10

    draw_text_center(tc.get("activity", ""), f_small)
    draw_text_center(tc.get("address", data.get("shopAddress", "")), f_small)
    y += 5
    draw_text_absolute(f"TEL : {tc.get('phone', '')}", m, y, f_small)
    draw_text_absolute(f"Mobile : {tc.get('mobile', '')}", cx, y, f_small)
    y += f_small + 15

    # --- 3. BARCODE ---
    inv_str, sale_reference, versement_number = _thermal_document_numbers(data, doc_type)
    versement_kind = _thermal_versement_kind(data) if doc_type == "Versement" else ""
    has_sale_number = bool(sale_reference)
    primary_number_visible = False
    
    if tc.get("show_barcode", True):
        bw = int(width * 0.85); bh = tc.get("barcode_height", 50)
        b_img = generate_barcode_image(inv_str, bw, bh)
        if b_img: 
            painter.drawImage(cx - (bw // 2), y, b_img)
            y += bh + 5
            draw_text_center(str(inv_str), f_small, bold=True)
            primary_number_visible = True
            y += 5
        
    if doc_type == "Facture":
        doc_title = "FACTURE"
    elif doc_type == "CreditClient":
        doc_title = "REGLEMENT CREDIT CLIENT"
    elif versement_kind == "VERSEMENT_PRODUIT":
        doc_title = "BON DE VERSEMENT PRODUIT"
    elif versement_kind == "VERSEMENT_LIBRE":
        doc_title = "BON DE VERSEMENT LIBRE"
    else:
        doc_title = "TICKET"
    draw_text_center(doc_title, f_norm, bold=True); y += 15

    # --- 4. DOC INFO ---
    if doc_type == "Versement":
        if has_sale_number:
            draw_text_absolute(f"Facture N° : {sale_reference}", m, y, f_small, bold=True)
            y += f_small + 5
        if not primary_number_visible and versement_number:
            draw_text_absolute(f"Versement N° : {versement_number}", m, y, f_small, bold=True)
        elif not primary_number_visible and not has_sale_number:
            draw_text_absolute(f"Versement N° : {inv_str}", m, y, f_small, bold=True)
    elif doc_type == "CreditClient":
        draw_text_absolute(f"Credit client N° : {inv_str}", m, y, f_small, bold=True)
    else:
        draw_text_absolute(f"Facture N° : {inv_str}", m, y, f_small, bold=True)
    date_val = _thermal_document_datetime(data, doc_type)
    date_only = str(date_val).split(' ')[0] if ' ' in str(date_val) else str(date_val)
    time_only = str(date_val).split(' ')[1][:5] if ' ' in str(date_val) else ""
    draw_text_absolute(date_only, width - m - 100, y, f_small, align_right=True, limit=100); y += f_small + 5
    if time_only: draw_text_absolute(time_only, width - m - 100, y, f_small, align_right=True, limit=100); y += f_small + 15

    client_name = data.get('client_name', data.get('customerFullName', 'Client Comptoir'))
    draw_text_absolute(f"Client : {client_name}", m, y, f_norm, bold=True); y += f_norm + 15

    # --- 5. TABLE & CONTENT ---
    totals_x = cx - 20; totals_w = (width - m) - totals_x

    if doc_type == "Facture":
        headers = ["Code", "Désignation", "Poids", "Montant"]
        ratios = [0.18, 0.40, 0.17, 0.25]
        rows = []
        for item in data.get('items', []):
            code = str(item.get('barcode', item.get('id', '')))
            name = str(item.get('name', item.get('itemName', 'Article')))
            is_w = (item.get('item_type', 'WEIGHT') == 'WEIGHT')
            qty = float(item.get('cart_sold_weight', item.get('weight', 0))) if is_w else float(item.get('cart_sold_qty', 0))
            unit = "Gr" if is_w else "Pcs"
            weight_str = f"{qty:.2f} {unit}"
            amt = float(item.get('cart_line_total', item.get('amount', 0)))
            amount_str = f"{amt:,.2f} {currency}"
            note = str(item.get('custom_note', item.get('note', '')))
            rows.append([code, name, weight_str, amount_str, note])

        if rows:
            draw_table(headers, ratios, rows)
            draw_text_absolute(f"Nombre des articles :       {len(rows)}", m, y, f_small, bold=True); y += 20
        
        total_brut = float(data.get('total_brut', data.get('total', 0)))
        remise = float(data.get('discount', 0))
        net = float(data.get('net', data.get('net_to_pay', total_brut - remise)))

        draw_text_absolute("Total TTC :", totals_x, y, f_norm)
        draw_text_absolute(f"{total_brut:,.2f} {currency}", totals_x, y, f_norm, align_right=True, limit=totals_w); y += f_norm + 10
        if remise > 0:
            draw_text_absolute("Remise :", totals_x, y, f_norm)
            draw_text_absolute(f"{remise:,.2f} {currency}", totals_x, y, f_norm, align_right=True, limit=totals_w); y += f_norm + 10
        draw_text_absolute("Net à payer :", totals_x, y, f_norm)
        draw_text_absolute(f"{net:,.2f} {currency}", totals_x, y, f_norm, align_right=True, limit=totals_w); y += f_norm + 25

        t_weight = float(data.get('total_weight', 0))
        if tc.get("show_weight", True) and t_weight > 0:
            painter.drawLine(m, y, width - m, y); y += 10
            draw_text_center("Bilan Poids / ميزان الوزن", f_norm, bold=True)
            p_weight = float(data.get('paid_weight_equiv', 0))
            r_weight = float(data.get('remainder_weight', t_weight - p_weight))
            
            draw_text_absolute("Poids Payé (الوزن المدفوع):", m, y, f_norm)
            draw_text_absolute(f"{p_weight:.2f} Gr", m, y, f_norm, align_right=True, limit=width-(2*m)); y += f_norm + 5
            
            draw_text_absolute("Poids Reste (الوزن الباقي):", m, y, f_norm)
            draw_text_absolute(f"{r_weight:.2f} Gr", m, y, f_norm, align_right=True, limit=width-(2*m)); y += f_norm + 15

        history = data.get('payments_history', [])
        if tc.get("show_history", True) and history:
            painter.drawLine(m, y, width - m, y); y += 10
            draw_text_center("Historique des versements sur produit", f_norm, bold=True)
            for p in history:
                d_str = str(p.get('payment_date', ''))[:10]
                amt = float(p.get('amount', 0))
                draw_text_absolute(d_str, m, y, f_small)
                draw_text_absolute(f"{amt:,.2f} {currency}", totals_x, y, f_small, align_right=True, limit=totals_w); y += f_small + 5

        y += 10
        draw_text_absolute("Arrêter la présente facture à la somme de:", m, y, f_small-2); y += f_small + 5
        draw_text_center(str(data.get('amount_in_words', '.............................................')), f_small)

    elif doc_type == "Versement":
        if versement_kind == "VERSEMENT_PRODUIT":
            product_rows = _thermal_versement_item_rows(data)
            if product_rows:
                draw_text_center("Produits réservés", f_norm, bold=True)
                draw_table(
                    ["Code", "Article", "Reste"], [0.25, 0.50, 0.25], product_rows
                )

        # 🟢 قراءة الإعداد ديناميكياً من thermal_config
        show_rate = tc.get("show_versement_rate", False)
        
        if versement_kind == "VERSEMENT_LIBRE":
            headers = ["Date", "Montant"]
            ratios = [0.45, 0.55]
            rows = []
            for v in data.get('versements', []):
                d_str = _thermal_payment_datetime(v)[:10]
                amt = f"{_thermal_payment_amount(v):,.2f} {currency}"
                rows.append([d_str, amt])
        else:
            if show_rate:
                headers = ["Date", "Opération", "Poids", "Prix/g", "Montant"]
                ratios = [0.20, 0.28, 0.14, 0.16, 0.22]
            else:
                headers = ["Date", "Opération", "Poids", "Montant"]
                ratios = [0.25, 0.35, 0.20, 0.20]

            rows = []
            for v in data.get('versements', []):
                d_str = _thermal_payment_datetime(v)[:10]
                op_num = _thermal_entry_versement_number(v)
                label = "Versement sur produit" if versement_kind == "VERSEMENT_PRODUIT" else "Versement libre"
                op = f"{label} {op_num}" if op_num else label
                w = _thermal_payment_weight(v)
                w_str = f"+{w:.2f} Gr" if w > 0 else "-"
                amt = f"{_thermal_payment_amount(v):,.2f} {currency}"
                
                if show_rate:
                    rate = _thermal_payment_rate(v)
                    rate_str = f"{rate:,.0f}" if rate > 0 else "-"
                    rows.append([d_str, op, w_str, rate_str, amt])
                else:
                    rows.append([d_str, op, w_str, amt])

        if rows:
            draw_table(headers, ratios, rows)

        # 🟢 ملخص الزبون فقط (بدون منتجات، بدون montant facture)
        painter.drawLine(m, y, width - m, y); y += 10

        if versement_kind == "VERSEMENT_PRODUIT":
            for label, value in _thermal_versement_summary_lines(data, currency):
                draw_text_absolute(label, totals_x, y, f_norm)
                draw_text_absolute(value, totals_x, y, f_norm, align_right=True, limit=totals_w)
                y += f_norm + 10
        else:
            for label, value in _thermal_free_summary_lines(data, currency):
                draw_text_absolute(label, totals_x, y, f_norm)
                draw_text_absolute(value, totals_x, y, f_norm, align_right=True, limit=totals_w)
                y += f_norm + 10
        y += 5

    elif doc_type == "CreditClient":
        headers = ["Date", "Opération", "Reste", "Montant"]
        ratios = [0.25, 0.35, 0.15, 0.25]
        rows = []
        for v in data.get('payments') or data.get('versements') or []:
            d_str = str(v.get('payment_date') or v.get('date') or '')[:10]
            amount = float(v.get('amount', 0))
            remaining = float(v.get('remaining_amount', v.get('reste', 0)) or 0)
            note = str(v.get('note') or v.get('notes') or '')
            rows.append([
                d_str,
                "Reglement credit client",
                f"{remaining:,.2f}",
                f"{amount:,.2f} {currency}",
                note,
            ])
        if rows:
            draw_table(headers, ratios, rows)
        else:
            amount = float(data.get('amount', 0))
            remaining = float(data.get('remaining_amount', data.get('reste', 0)) or 0)
            draw_text_absolute("Montant credit :", totals_x, y, f_norm)
            draw_text_absolute(f"{amount:,.2f} {currency}", totals_x, y, f_norm, align_right=True, limit=totals_w); y += f_norm + 10
            draw_text_absolute("Reste credit :", totals_x, y, f_norm)
            draw_text_absolute(f"{remaining:,.2f}", totals_x, y, f_norm, align_right=True, limit=totals_w); y += f_norm + 15

    elif doc_type == "Rapide":
        draw_text_absolute("Opération:", m, y, f_norm); draw_text_absolute(str(data.get('operationType', '')), m+100, y, f_norm, bold=True); y += f_norm + 5
        draw_text_absolute("Article:", m, y, f_norm); draw_text_absolute(str(data.get('itemName', '')), m+100, y, f_norm, bold=True, limit=width - (m+100+m)); y += f_norm + 5
        draw_text_absolute("Poids:", m, y, f_norm); draw_text_absolute(f"{float(data.get('weight', 0)):.2f} Gr", m+100, y, f_norm, bold=True); y += f_norm + 15
        draw_text_center("*** Paiement Comptant ***", f_norm, bold=True)

    y += 20; painter.drawLine(m, y, width - m, y); y += 10
    draw_text_center(tc.get("footer_text", "Merci de votre visite !"), f_small)
    
    # 🟢 نقطة واحدة في كل سطر (نظيفة وغير ظاهرة)
    painter.setPen(QPen(Qt.black, 2, Qt.SolidLine))
    for _ in range(10):
        y += 12
        painter.drawPoint(cx, y)
    return y

# =========================================================================
# 🟢 المحرك التوجيهي الرئيسي للطباعة 🟢
# =========================================================================
def _execute_qpainter_print(data, doc_type, printer_name=None):
    tc = get_thermal_config()
    printer_name = str(printer_name or tc.get("printer_name", "") or "").strip()
    
    if not printer_name:
        raise ValueError("Aucune imprimante thermique n'a été sélectionnée dans les paramètres.")
        
    printer = QPrinter(QPrinter.PrinterResolution)
    printer.setPrinterName(printer_name)
    if hasattr(printer, "isValid") and not printer.isValid():
        raise ValueError(f"Impossible de communiquer avec l'imprimante: {printer_name}")
    
    painter = QPainter()
    if not painter.begin(printer):
        raise ValueError(f"Impossible de communiquer avec l'imprimante: {printer_name}")
        
    real_w = printer.pageRect(QPrinter.DevicePixel).width()
    log_w = tc.get("page_width", 576)
    
    if real_w > 0:
        scale_f = real_w / log_w
        painter.scale(scale_f, scale_f)
        
    _draw_thermal_receipt(painter, log_w, data, tc, doc_type)
    painter.end()
    return 1

def print_thermal_facture(data, calculate_only=False, hDC=None, theme='default', language='ar', printer_name=None):
    if calculate_only: return 0
    return _execute_qpainter_print(data, "Facture", printer_name=printer_name)

def print_thermal_bon_versement(data, calculate_only=False, hDC=None, theme='default', language='ar', printer_name=None):
    if calculate_only: return 0
    _validate_thermal_versement_payload(data)
    return _execute_qpainter_print(data, "Versement", printer_name=printer_name)

def print_thermal_credit_client(data, calculate_only=False, hDC=None, theme='default', language='ar', printer_name=None):
    if calculate_only: return 0
    return _execute_qpainter_print(data, "CreditClient", printer_name=printer_name)

def print_jewelry_transaction(data, calculate_only=False, hDC=None, theme='default', language='ar'):
    if calculate_only: return 0
    return _execute_qpainter_print(data, "Rapide")