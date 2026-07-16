# ui/tools/invoice_generator.py

import os
import json
import re  
import io
import base64
import copy
from html import escape
from datetime import datetime
from PySide6.QtGui import QTextDocument, QPageSize, QPageLayout, QDesktopServices, QImage, QColor
from PySide6.QtCore import Qt, QMarginsF, QUrl, QByteArray, QBuffer
from PySide6.QtPrintSupport import QPrinter

CREDIT_CLIENT_MARKERS = {
    "CREDIT_CLIENT",
    "LEGACY_CLIENT_CREDIT",
    "LEGACY_CLIENT_CREDIT_PAYMENT",
    "LEGACY_OPENING_BALANCE",
}


def _code(value):
    return str(value or "").strip().upper()


def _is_credit_client_entry(entry):
    return (
        _code(entry.get("document_type")) in CREDIT_CLIENT_MARKERS
        or _code(entry.get("client_document_type")) in CREDIT_CLIENT_MARKERS
        or _code(entry.get("payment_type")) in CREDIT_CLIENT_MARKERS
    )


def _contains_credit_client_document(data):
    if _is_credit_client_entry(data):
        return True
    return any(
        _is_credit_client_entry(payment)
        for payment in (data.get("versements") or data.get("payments_history") or [])
    )


def _safe_document_part(value, fallback="Sans_Numero"):
    text = re.sub(r"[^A-Za-z0-9_-]+", "_", str(value or "").strip()).strip("_")
    return text or fallback


def _looks_like_versement_number(value) -> bool:
    text = str(value or "").strip().upper()
    return text.startswith(("V-", "VL-", "VP-", "VRS-", "VERSEMENT"))


def _looks_like_facture_number(value) -> bool:
    text = str(value or "").strip().upper()
    return text.startswith("F-")


def _entry_versement_number(entry):
    for key in ("versement_operation_number", "operation_number"):
        number = str((entry or {}).get(key) or "").strip()
        if number:
            return number
    for key in ("document_number", "display_number", "receipt_number"):
        number = str((entry or {}).get(key) or "").strip()
        if number and _looks_like_versement_number(number):
            return number
    return ""


def _legacy_versement_document_number(value) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if _looks_like_versement_number(text):
        return text
    try:
        return f"VRS-{int(text):06d}"
    except (TypeError, ValueError):
        return ""


def _facture_document_number(value) -> str:
    text = str(value or "").strip()
    if not text or _looks_like_versement_number(text):
        return ""
    return text


def _safe_float(value, default=0.0):
    try:
        return float(value if value not in (None, "") else default)
    except (TypeError, ValueError):
        return float(default)


def _payment_rate_reference(payment: dict) -> float:
    rate = _safe_float(
        payment.get("metal_rate_reference")
        or payment.get("metal_rate_at_payment")
        or payment.get("current_gold_rate")
    )
    if rate > 0:
        return rate
    amount = _safe_float(payment.get("amount") or payment.get("amount_base"))
    weight = _safe_float(payment.get("weight") or payment.get("purchased_weight") or payment.get("paid_weight"))
    return round(amount / weight, 2) if amount > 0 and weight > 0 else 0.0


def _format_document_datetime(value) -> str:
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d %H:%M")
    text = str(value or "").strip()
    return text or datetime.now().strftime("%Y-%m-%d %H:%M")


def _header_style_colors(pdf_cfg: dict) -> tuple:
    colors = (pdf_cfg or {}).get("colors") or {}
    text_color = colors.get("header_text") or colors.get("text_primary", "#333333")
    background_color = colors.get("header_bg") or "transparent"
    return text_color, background_color


def _header_table_style(pdf_cfg: dict, margin_bottom: int = 20) -> str:
    text_color, background_color = _header_style_colors(pdf_cfg)
    padding = "8px" if background_color != "transparent" else "0"
    return (
        f"border: none; margin-bottom: {margin_bottom}px; "
        f"background-color: {background_color}; color: {text_color}; padding: {padding};"
    )


def _page_size_from_config(pdf_cfg: dict) -> QPageSize:
    page_size = str((pdf_cfg or {}).get("page_size") or "A5").upper()
    if page_size == "A4":
        return QPageSize(QPageSize.A4)
    if page_size == "A6":
        return QPageSize(QPageSize.A6)
    return QPageSize(QPageSize.A5)


def _render_html_document(html: str, pdf_cfg: dict, output_path: str = "", printer_name: str = ""):
    printer = QPrinter()
    printer_name = str(printer_name or "").strip()
    is_direct_print = bool(printer_name)

    if is_direct_print:
        printer.setPrinterName(printer_name)
        printer.setOutputFormat(QPrinter.NativeFormat)
    elif output_path:
        printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setOutputFileName(output_path)

    # تحضير حجم الصفحة والهوامش
    page_size = _page_size_from_config(pdf_cfg)
    margin_mm = (pdf_cfg or {}).get("margin_mm", 8)
    margins = QMarginsF(margin_mm, margin_mm, margin_mm, margin_mm)
    
    page_layout = QPageLayout(page_size, QPageLayout.Portrait, margins)
    
    # السطر السحري: يمنع الطابعة من فرض أبعادها الخاصة ويجبرها على الالتزام بكودك
    if is_direct_print:
        page_layout.setMode(QPageLayout.FullPage)

    printer.setPageLayout(page_layout)
    printer.setResolution(96)
    
    if is_direct_print and hasattr(printer, "isValid") and not printer.isValid():
        raise ValueError(f"Impossible de communiquer avec l'imprimante: {printer_name}")

    doc = QTextDocument()
    
    # في الطباعة المباشرة نلغي هوامش المستند لأن QPageLayout تولى الأمر
    # في حفظ الـ PDF نحافظ على الطريقة القديمة لتجنب أي تغيير في شكل الملفات العادية
    if is_direct_print:
        doc.setDocumentMargin(0)
    else:
        margin_px = int(margin_mm * 3.779527)
        doc.setDocumentMargin(margin_px)
        
    doc.setHtml(html)
    doc.setPageSize(printer.pageLayout().paintRectPixels(printer.resolution()).size())
    doc.print_(printer)
    return doc, printer


# ==========================================
# HELPER CLASS FOR PDF GENERATION
# ==========================================
class PdfHelper:
    @staticmethod
    def default_pdf_config():
        return {
            "printer_name": "",
            "page_size": "A5", "margin_mm": 8,
            "fonts": {"shop_name": 22, "doc_title": 18, "normal": 12, "table_header": 12, "qr_text": 10},
            "colors": {
                "text_primary": "#333333",
                "table_header_bg": "#f5f5f5",
                "paid_green": "#27ae60",
                "debt_red": "#c0392b",
                "header_text": "#333333",
                "header_bg": "transparent",
            },
            "logo": {"path": "", "width": 100, "use_bw_filter": False, "threshold": 127, "align": "À gauche du nom"},
            "codes": {"qr_link": "", "qr_text": "Notre Page", "qr_size": 60, "show_qr": True, "invoice_barcode_mode": "Code-Barres + Texte"},
            "display": {
                "show_rc_nif": True, "show_history": True, "show_weight_balance": True,
                "show_item_note": True, "show_item_code_column": True,
                "item_code_format": "Code-Barres", "reste_in_weight": True,
                "item_barcode_w": 70, "item_barcode_h": 20,
                "show_versement_items_section": True,
                "show_versement_payment_rate": True,
            },
            "texts": {
                "title_facture": "FACTURE",
                "title_versement": "BON DE VERSEMENT",
                "title_versement_libre": "BON DE VERSEMENT LIBRE",
                "title_versement_produit": "BON DE VERSEMENT SUR PRODUIT",
                "title_credit_client": "DOCUMENT CREDIT CLIENT",
                "text_arrete": "Arrêté la présente somme de :",
                "policy_paid": "Le produit vendu n'est ni repris ni échangé.",
                "policy_debt": "Les versements ne sont ni remboursés ni échangés.",
                "arabic_paid": "الوزن المدفوع",
                "arabic_debt": "هذه الوثيقة تثبت الدفعات المسبقة الخاصة بالزبون، ومن الضروري إحضارها.",
                "versement_items_section_title": "Détail des produits réservés",
                "versement_payments_section_title": "Versements sur produit",
                "versement_label_article": "Article",
                "versement_label_code": "Code Produit",
                "versement_label_total_weight": "Poids total",
                "versement_label_total_amount": "Montant total",
                "versement_label_paid_amount": "Montant payé",
                "versement_label_paid_weight": "Poids payé",
                "versement_label_remaining_amount": "Reste montant",
                "versement_label_remaining_weight": "Reste poids",
                "versement_label_payment_date": "Date",
                "versement_label_payment_amount": "Montant Versé",
                "versement_label_payment_weight": "Poids (غرام)",
                "versement_label_payment_rate": "Prix/g paiement",
                "versement_summary_invoice_amount": "Montant facture",
                "versement_summary_total_weight": "Poids Total d'article",
                "versement_summary_total_quantity": "Quantite totale",
                "versement_summary_remaining_quantity": "Reste quantite",
                "versement_summary_total_paid": "Total Payé",
                "versement_summary_paid_weight": "Poids Acquis",
                "versement_summary_remaining_weight": "Reste en Poids (الغرام المتبقي)",
            },
        }

    @staticmethod
    def _merge_config(defaults, values):
        merged = copy.deepcopy(defaults)
        if not isinstance(values, dict):
            return merged
        for key, value in values.items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = PdfHelper._merge_config(merged[key], value)
            else:
                merged[key] = value
        return merged

    @staticmethod
    def normalize_pdf_config(pdf_config):
        cfg = PdfHelper._merge_config(PdfHelper.default_pdf_config(), pdf_config or {})
        legacy_align = {
            "Ã€ gauche du nom": "À gauche du nom",
            "Ã€ droite du nom": "À droite du nom",
            "Au-dessus du nom (CentrÃ©)": "Au-dessus du nom (Centré)",
        }
        align = cfg.get("logo", {}).get("align", "")
        if align in legacy_align:
            cfg["logo"]["align"] = legacy_align[align]
        return cfg

    @staticmethod
    def get_base64_qr(data, size=60):
        try:
            import qrcode
            qr = qrcode.QRCode(version=1, box_size=5, border=0)
            qr.add_data(data); qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            fp = io.BytesIO(); img.save(fp, format="PNG")
            return f"data:image/png;base64,{base64.b64encode(fp.getvalue()).decode()}"
        except Exception:
            return ""

    @staticmethod
    def get_base64_barcode(data, height=10):
        try:
            import barcode
            from barcode.writer import ImageWriter
            CODE = barcode.get_barcode_class('code128')
            writer = ImageWriter()
            options = {'module_width': 0.2, 'module_height': height, 'font_size': 0, 'quiet_zone': 1.0}
            fp = io.BytesIO()
            CODE(str(data), writer=writer).write(fp, options)
            return f"data:image/png;base64,{base64.b64encode(fp.getvalue()).decode()}"
        except Exception:
            return ""

    @staticmethod
    def get_logo_html(cfg_logo):
        logo_html = ""
        if cfg_logo.get("path") and os.path.exists(cfg_logo["path"]):
            img = QImage(cfg_logo["path"]).scaledToWidth(cfg_logo.get("width", 100), Qt.SmoothTransformation)
            if cfg_logo.get("use_bw_filter", False):
                img = img.convertToFormat(QImage.Format_Grayscale8)
                thresh = cfg_logo.get("threshold", 127)
                for y in range(img.height()):
                    for x in range(img.width()):
                        val = img.pixelColor(x, y).red()
                        img.setPixelColor(x, y, QColor(0, 0, 0) if val <= thresh else QColor(255, 255, 255))
            ba = QByteArray()
            buffer = QBuffer(ba)
            buffer.open(QBuffer.WriteOnly)
            img.save(buffer, "PNG")
            logo_html = f"<img src='data:image/png;base64,{ba.toBase64().data().decode()}' />"
        return logo_html

    @staticmethod
    def load_pdf_config():
        config = {}
        if os.path.exists("config.json"):
            try:
                with open("config.json", 'r', encoding='utf-8') as f:
                    config = json.load(f)
            except Exception:
                pass
        return config, PdfHelper.normalize_pdf_config(config.get("pdf_config", {}))

    @staticmethod
    def build_qr_html(pdf_cfg):
        codes = pdf_cfg.get("codes", {})
        if not codes.get("show_qr", False) or not codes.get("qr_link", ""):
            return ""
        qr_b64 = PdfHelper.get_base64_qr(codes["qr_link"])
        if not qr_b64:
            return ""
        sz = codes.get("qr_size", 60)
        f_qr = pdf_cfg.get("fonts", {}).get("qr_text", 10)
        text = codes.get("qr_text", "")
        return (
            f"<div style='margin-top:10px;'><table style='border:none; padding:0;'><tr>"
            f"<td style='padding:0;'><img src='{qr_b64}' width='{sz}' height='{sz}' /></td>"
            f"<td style='vertical-align:middle; padding-left:8px; font-weight:bold; font-size:{f_qr}px;'>{text}</td>"
            f"</tr></table></div>"
        )

    @staticmethod
    def build_document_code_html(pdf_cfg, number, f_norm):
        doc_number = str(number or "").strip()
        if not doc_number:
            return ""
        if doc_number.isdigit():
            doc_number = f"{int(doc_number):05d}"
        visible_doc_number = escape(doc_number)
        mode = pdf_cfg.get("codes", {}).get("invoice_barcode_mode", "Code-Barres + Texte")
        barcode_b64 = PdfHelper.get_base64_barcode(doc_number, height=5)
        if mode == "Code-Barres + Texte" and barcode_b64:
            return (
                f"<div style='margin-top:8px;'><img src='{barcode_b64}' width='120' height='30'/>"
                f"<br><span style='font-size:{int(f_norm*0.8)}px; font-weight:bold;'>{visible_doc_number}</span></div>"
            )
        if mode == "Code-Barres uniquement" and barcode_b64:
            return f"<div style='margin-top:8px;'><img src='{barcode_b64}' width='120' height='30'/></div>"
        return f"<div style='margin-top:5px; font-size:{f_norm}px; font-weight:bold;'>N° {visible_doc_number}</div>"


# ==========================================
# 1. MAIN INVOICE GENERATOR (Sales / Factures)
# ==========================================
def generate_invoice_pdf(
    sale_id,
    client_name,
    items,
    total_brut,
    discount,
    net,
    cash_paid=0.0,
    tpe_paid=0.0,
    or_casse_g=0.0,
    show_discount=True,
    facture_number="",
    printed_at=None,
    direct_printer_name="",
    open_pdf=True,
):
    global_cfg, pdf_cfg = PdfHelper.load_pdf_config()

    shop_name = global_cfg.get("shop_name", "Mon Magasin")
    address = global_cfg.get("shop_address", "")
    phone = global_cfg.get("shop_phone", "")
    rc = global_cfg.get("shop_rc", "")
    nif = global_cfg.get("shop_nif", "")
    invoice_dir = global_cfg.get("invoice_path", "./factures")
    currency = global_cfg.get("currency", "DA")

    c_txt = pdf_cfg["colors"].get("text_primary", "#333")
    c_th = pdf_cfg["colors"].get("table_header_bg", "#f5f5f5")
    c_grn = pdf_cfg["colors"].get("paid_green", "#27ae60")
    c_red = pdf_cfg["colors"].get("debt_red", "#c0392b")
    c_header_txt, _c_header_bg = _header_style_colors(pdf_cfg)
    header_table_style = _header_table_style(pdf_cfg, margin_bottom=20)
    f_shop = pdf_cfg["fonts"].get("shop_name", 22)
    f_title = pdf_cfg["fonts"].get("doc_title", 18)
    f_norm = pdf_cfg["fonts"].get("normal", 12)
    f_th = pdf_cfg["fonts"].get("table_header", 12)

    bc_w = pdf_cfg["display"].get("item_barcode_w", 70)
    bc_h = pdf_cfg["display"].get("item_barcode_h", 20)

    title = pdf_cfg["texts"].get("title_facture", "FACTURE")
    file_prefix = "Facture"
    facture_document_number = _facture_document_number(facture_number)
    invoice_number = facture_document_number or sale_id
    printed_at_value = printed_at or datetime.now()
    printed_at_text = _format_document_datetime(printed_at_value)
    printed_at_stamp = (
        printed_at_value.strftime("%Y-%m-%d_%H-%M-%S")
        if hasattr(printed_at_value, "strftime")
        else datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    )

    logo_html = PdfHelper.get_logo_html(pdf_cfg["logo"])
    align_opt = pdf_cfg["logo"].get("align", "À gauche du nom")
    cell_logo_l = f"<td width='1%' style='padding-right:15px; vertical-align:top;'>{logo_html}</td>" if align_opt == "À gauche du nom" and logo_html else ""
    cell_logo_r = f"<td width='1%' style='padding-left:15px; vertical-align:top;'>{logo_html}</td>" if align_opt == "À droite du nom" and logo_html else ""
    block_logo_top = f"<div style='text-align:center; margin-bottom:10px;'>{logo_html}</div>" if align_opt == "Au-dessus du nom (Centré)" and logo_html else ""

    qr_html = PdfHelper.build_qr_html(pdf_cfg)
    header_extras = PdfHelper.build_document_code_html(pdf_cfg, invoice_number, f_norm)

    show_code = pdf_cfg["display"].get("show_item_code_column", True)
    code_format = pdf_cfg["display"].get("item_code_format", "Code-Barres")

    th_code = f'<th style="text-align:center; width:15%;">Code</th>' if show_code else ""
    table_headers = f"""
        {th_code}
        <th style="text-align: left;">Désignation</th>
        <th style="text-align: center;">Qté/Pds</th>
        <th style="text-align: right;">Total</th>
    """

    items_html = ""
    total_weight = 0.0
    for item in items:
        orig_name = str(item.get('name') or item.get('item_name') or 'Article').strip()
        barcode = str(item.get('barcode') or item.get('inventory_barcode') or '').strip()
        custom_note = str(item.get('custom_note') or '').strip()

        main_name = escape(orig_name)
        note_html = f"<br><span style='font-size:{int(f_norm*0.85)}px; color:#8e44ad; font-weight:bold;'>{escape(custom_note)}</span>" if custom_note else ""

        td_code_content = escape(barcode)
        if show_code and code_format == "Code-Barres" and barcode:
            b64_prod = PdfHelper.get_base64_barcode(barcode, height=4)
            if b64_prod:
                td_code_content = f'<img src="{b64_prod}" width="{bc_w}" height="{bc_h}"/>'
        td_code = f'<td style="text-align:center; vertical-align:middle; font-size:{int(f_norm*0.9)}px;">{td_code_content}</td>' if show_code else ""

        is_weight = (item.get('item_type', 'WEIGHT') == 'WEIGHT')
        qty_or_weight = float(item.get('cart_sold_weight', 0)) if is_weight else float(item.get('cart_sold_qty', 0))
        line_total = float(item.get('cart_line_total', 0))
        unit_label = "g" if is_weight else "pcs"
        if is_weight:
            total_weight += qty_or_weight

        items_html += f"""
        <tr>
            {td_code}
            <td style="vertical-align:middle;">{main_name}{note_html}</td>
            <td style="text-align:center; vertical-align:middle; font-weight:bold; white-space:nowrap;">{qty_or_weight:.2f} {unit_label}</td>
            <td style="text-align:right; vertical-align:middle; font-weight:bold; white-space:nowrap;">{line_total:,.2f} {currency}</td>
        </tr>
        """

    payment_summary = ""
    if show_discount and discount > 0.01:
        payment_summary += f"<tr><td style='padding:6px; text-align:right;'>Total Brut :</td><td style='padding:6px; text-align:right; font-weight:bold;'>{total_brut:,.2f} {currency}</td></tr>"
        payment_summary += f"<tr><td style='padding:6px; text-align:right;'>Remise :</td><td style='padding:6px; text-align:right; color:{c_red}; font-weight:bold;'>- {discount:,.2f} {currency}</td></tr>"

    payment_summary += f"<tr><td style='padding:10px 6px; text-align:right; font-weight:bold; font-size:{int(f_norm*1.1)}px;'>NET À PAYER :</td><td style='padding:10px 6px; text-align:right; font-weight:bold; border:1px solid #ddd; background-color:#f9f9f9; font-size:{int(f_norm*1.1)}px;'>{net:,.2f} {currency}</td></tr>"

    weight_html = ""
    if total_weight > 0:
        weight_html = f"""
        <div style="padding:10px; border:1px solid {c_grn}; border-radius:4px; width:85%; background-color:#f9fdfa; margin-top:10px; margin-bottom:15px;">
            <table width="100%" cellpadding="0" cellspacing="0" style="border:none; margin:0; padding:0;">
                <tr>
                    <td style="font-weight:bold; font-size:{int(f_norm*0.95)}px; color:{c_grn}; text-align:left;">Poids réglé en totalité :</td>
                    <td style="font-weight:bold; font-size:{int(f_norm*1.1)}px; color:{c_grn}; text-align:right; white-space:nowrap;">{total_weight:.3f} g</td>
                </tr>
                <tr>
                    <td colspan="2" style="font-size:{int(f_norm*0.95)}px; color:{c_grn}; text-align:right; font-weight:bold; padding-top:6px; white-space:nowrap;">
                        الوزن مدفوع بالكامل ({total_weight:.3f} غرام)
                    </td>
                </tr>
            </table>
        </div>
        """

    policy = pdf_cfg["texts"].get("policy_paid", "Le produit vendu n'est ni repris ni échangé.")
    rc_nif_txt = f"{'RC: '+rc+' | NIF: '+nif if pdf_cfg['display'].get('show_rc_nif', True) else ''}"

    html = f"""
    <html><head><style>
        body {{ font-family: Arial, sans-serif; color: {c_txt}; font-size: {f_norm}px; }}
        th {{ background-color: {c_th}; padding: 8px; border-bottom: 2px solid {c_txt}; font-size: {f_th}px; text-transform: uppercase; }}
        td {{ padding: 8px; border-bottom: 1px solid #eee; }}
    </style></head><body>
        {block_logo_top}
        <table width="100%" style="{header_table_style}">
            <tr>
                {cell_logo_l}
                <td style="border:none; padding:0; vertical-align:top;">
                    <div style="margin:0; font-weight:bold; font-size:{f_shop}px; color:{c_header_txt};">{shop_name}</div>
                    <div style="margin-top:5px; font-size:{f_norm}px;">{address}<br>Tél: {phone}<br>{rc_nif_txt}</div>
                    {qr_html}
                </td>
                {cell_logo_r}
                <td width="40%" style="text-align:right; border:none; padding:0; vertical-align:top;">
                    <div style="margin:0; font-weight:bold; font-size:{f_title}px; color:{c_header_txt};">{title}</div>
                    {header_extras}
                    <div style="margin-top:5px; font-size:{f_norm}px;">Date: {printed_at_text}</div>
                    <div style="margin-top:5px; font-weight:bold; font-size:{f_norm}px;">Client: {client_name}</div>
                </td>
            </tr>
        </table>

        <table width="100%" style="border-collapse: collapse; margin-bottom:15px;">
            <tr>{table_headers}</tr>
            {items_html}
        </table>

        <table width="100%" style="border: none;">
            <tr>
                <td width="55%" style="vertical-align: top; padding-right: 10px;">
                    <p style="font-size:{int(f_norm*0.9)}px;"><i>{pdf_cfg["texts"].get("text_arrete", "Arrêté la présente somme de :")}</i><br>.......................................................</p>
                    {weight_html}
                </td>
                <td width="45%" style="vertical-align: top; padding: 0;">
                    <table width="100%" style="border-collapse: collapse;">{payment_summary}</table>
                </td>
            </tr>
        </table>

        <div style='margin-top:25px; text-align:center; border-top:1px dashed #aaa; padding-top:15px;'><b style='font-size:{int(f_norm*0.9)}px;'>{policy}</b></div>
    </body></html>
    """

    safe_client_name = re.sub(r'[\\/*?:"<>|]', "", client_name).strip() or "Client_Inconnu"
    client_dir = os.path.join(invoice_dir, safe_client_name)
    os.makedirs(client_dir, exist_ok=True)
    invoice_file_number = (
        _safe_document_part(invoice_number)
        if facture_document_number
        else f"N{_safe_document_part(_formatted_sale_number(sale_id) or sale_id)}"
    )
    pdf_path = os.path.abspath(os.path.join(
        client_dir,
        f"{printed_at_stamp}_{file_prefix}_{invoice_file_number}.pdf",
    ))

    _render_html_document(html, pdf_cfg, output_path=pdf_path)

    direct_printer_name = str(direct_printer_name or "").strip()
    if direct_printer_name:
        _render_html_document(html, pdf_cfg, printer_name=direct_printer_name)

    if open_pdf:
        QDesktopServices.openUrl(QUrl.fromLocalFile(pdf_path))
    return pdf_path


def _versement_operation_number(data):
    number = _entry_versement_number(data)
    if number:
        return number
    for payment in data.get('versements') or data.get('payments_history') or []:
        number = _entry_versement_number(payment)
        if number:
            return number
    return ""


def _combine_versement_number(operation_number):
    return str(operation_number or "").strip()


def _versement_receipt_display_number(data):
    operation_number = _versement_operation_number(data)
    if operation_number:
        return operation_number
    for key in ("receipt_id", "id", "versement_id", "source_versement_id"):
        legacy_number = _legacy_versement_document_number(data.get(key))
        if legacy_number:
            return legacy_number
    for payment in data.get('versements') or data.get('payments_history') or []:
        for key in ("receipt_id", "id", "versement_id", "source_versement_id"):
            legacy_number = _legacy_versement_document_number((payment or {}).get(key))
            if legacy_number:
                return legacy_number
    return ""


def _payment_operation_prefix(payment, f_norm, document_operation_number=""):
    operation_number = _entry_versement_number(payment)
    if not operation_number or operation_number == str(document_operation_number or "").strip():
        return ""
    display_number = escape(_combine_versement_number(operation_number))
    return (
        f"<span style='color:#0f8f83; font-size:{int(f_norm*0.9)}px; "
        f"font-weight:bold;'>[{display_number}]</span> "
    )


def _formatted_sale_number(sale_id):
    if sale_id in (None, "", 0, "0"):
        return ""
    if _looks_like_versement_number(sale_id):
        return ""
    try:
        return f"{int(sale_id):05d}"
    except (TypeError, ValueError):
        return str(sale_id or "").strip()


def _facture_reference_number(data):
    facture_number = str(
        data.get("facture_number")
        or data.get("sale_number")
        or data.get("invoice_number")
        or ""
    ).strip()
    if _looks_like_facture_number(facture_number):
        return facture_number
    return ""


def _sale_reference_html(sale_id, f_norm, facture_number=""):
    sale_number = str(facture_number or "").strip()
    if not _looks_like_facture_number(sale_number):
        sale_number = ""
    if not sale_number:
        return ""
    return (
        f"<div style='margin-top:5px; font-size:{f_norm}px; font-weight:bold;'>"
        f"Facture N&deg;: {sale_number}</div>"
    )


def build_product_versement_filename(data, timestamp=""):
    operation_number = _versement_operation_number(data)
    document_number = _safe_document_part(operation_number or "Sans_Numero")
    prefix = f"{timestamp}_" if timestamp else ""
    facture_number = str(data.get("facture_number") or "").strip()
    sale_suffix = f"_Facture_{_safe_document_part(facture_number)}" if _looks_like_facture_number(facture_number) else ""
    return f"{prefix}Versement_Produit_{document_number}{sale_suffix}.pdf"


def build_free_versement_filename(data, timestamp=""):
    operation_number = _versement_operation_number(data)
    document_number = _safe_document_part(operation_number or data.get("receipt_id"))
    prefix = f"{timestamp}_" if timestamp else ""
    suffix = "_Global" if len(data.get("versements") or []) > 1 else ""
    return f"{prefix}Versement_Libre_{document_number}{suffix}.pdf"


def build_credit_client_filename(data, timestamp=""):
    credit_number = (
        data.get("credit_number")
        or data.get("receipt_number")
        or data.get("operation_number")
        or data.get("sale_id")
    )
    document_number = _safe_document_part(credit_number)
    prefix = f"{timestamp}_" if timestamp else ""
    return f"{prefix}Credit_Client_{document_number}.pdf"


# ==========================================
# 2. RECEIPT GENERATOR CLASS
# ==========================================
class ReceiptGenerator:

    @staticmethod
    def generate_global_versement_receipt(data, output_path="bon_versement.pdf", direct_printer_name=""):
        if _contains_credit_client_document(data):
            raise ValueError("Credit client documents require a dedicated credit-client template.")

        global_cfg, pdf_cfg = PdfHelper.load_pdf_config()

        shop_name = global_cfg.get("shop_name", "Mon Magasin")
        address = global_cfg.get("shop_address", "")
        phone = global_cfg.get("shop_phone", "")
        rc = global_cfg.get("shop_rc", "")
        nif = global_cfg.get("shop_nif", "")
        currency = global_cfg.get("currency", "DA")

        c_txt = pdf_cfg["colors"].get("text_primary", "#333")
        c_th = pdf_cfg["colors"].get("table_header_bg", "#f5f5f5")
        c_grn = pdf_cfg["colors"].get("paid_green", "#27ae60")
        c_header_txt, _c_header_bg = _header_style_colors(pdf_cfg)
        header_table_style = _header_table_style(pdf_cfg, margin_bottom=20)
        f_shop = pdf_cfg["fonts"].get("shop_name", 22)
        f_title = pdf_cfg["fonts"].get("doc_title", 18)
        f_norm = pdf_cfg["fonts"].get("normal", 12)
        f_th = pdf_cfg["fonts"].get("table_header", 12)

        title = pdf_cfg["texts"].get(
            "title_versement_libre",
            pdf_cfg["texts"].get("title_versement", "BON DE VERSEMENT LIBRE"),
        )

        customer_name = data.get('customer_name', 'Client')
        customer_phone = data.get('phone', 'N/A')

        logo_html = PdfHelper.get_logo_html(pdf_cfg["logo"])
        align_opt = pdf_cfg["logo"].get("align", "À gauche du nom")
        cell_logo_l = f"<td width='1%' style='padding-right:15px; vertical-align:top;'>{logo_html}</td>" if align_opt == "À gauche du nom" and logo_html else ""
        cell_logo_r = f"<td width='1%' style='padding-left:15px; vertical-align:top;'>{logo_html}</td>" if align_opt == "À droite du nom" and logo_html else ""
        block_logo_top = f"<div style='text-align:center; margin-bottom:10px;'>{logo_html}</div>" if align_opt == "Au-dessus du nom (Centré)" and logo_html else ""

        qr_html = PdfHelper.build_qr_html(pdf_cfg)

        operation_number = _versement_operation_number(data)
        receipt_number = _versement_receipt_display_number(data)
        header_extras = PdfHelper.build_document_code_html(pdf_cfg, receipt_number, f_norm)

        versements_html = ""
        if data.get('versements'):
            for v in data['versements']:
                date_val = v.get('payment_date') or v.get('activity_date') or v.get('sale_date') or datetime.now()
                date_str = date_val.strftime("%Y-%m-%d") if hasattr(date_val, 'strftime') else str(date_val).split(' ')[0]
                amount = _safe_float(
                    v.get('amount') or v.get('display_paid_amount')
                    or v.get('paid_amount') or v.get('total_amount') or 0
                )
                used = _safe_float(v.get('used_amount'))
                available = v.get('available_amount')
                remaining = v.get('remaining_amount')
                if remaining in (None, ""):
                    remaining = available if available not in (None, "") else max(0.0, amount - used)
                remaining = max(0.0, _safe_float(remaining))
                rate = _safe_float(v.get('metal_rate_at_payment'))
                weight_str = ""
                used_str = ""
                raw_id = v.get('id', '')
                v_id = abs(int(raw_id)) if str(raw_id).lstrip('-').isdigit() else ''
                operation_prefix = _payment_operation_prefix(v, f_norm, operation_number)
                id_str = f"<span style='color:#7f8c8d; font-size:{int(f_norm*0.9)}px;'>[N° {v_id}]</span> " if v_id else ""
                versements_html += f"<tr><td style='vertical-align:middle;'>{operation_prefix}{id_str}{date_str}</td><td style='text-align:center; vertical-align:middle; font-weight:bold;'>{amount:,.2f} {currency} {used_str}</td></tr>"
        else:
            versements_html = f"<tr><td colspan='2' style='text-align:center; font-style:italic;'>Aucun versement disponible</td></tr>"

        rc_nif_txt = f"{'RC: '+rc+' | NIF: '+nif if pdf_cfg['display'].get('show_rc_nif', True) else ''}"
        if qr_html:
            rc_nif_txt = f"{rc_nif_txt}{qr_html}"

        html = f"""
        <html><head><style>
            body {{ font-family: Arial, sans-serif; color: {c_txt}; font-size: {f_norm}px; }}
            th {{ background-color: {c_th}; padding: 8px; border-bottom: 2px solid {c_txt}; font-size: {f_th}px; text-transform: uppercase; }}
            td {{ padding: 8px; border-bottom: 1px solid #eee; }}
        </style></head><body>
            {block_logo_top}
            <table width="100%" style="{header_table_style}">
                <tr>
                    {cell_logo_l}
                    <td style="border:none; padding:0; vertical-align:top;">
                        <div style="margin:0; font-weight:bold; font-size:{f_shop}px; color:{c_header_txt};">{shop_name}</div>
                        <div style="margin-top:5px; font-size:{f_norm}px;">{address}<br>Tél: {phone}<br>{rc_nif_txt}</div>
                    </td>
                    {cell_logo_r}
                    <td width="40%" style="text-align:right; border:none; padding:0; vertical-align:top;">
                        <div style="margin:0; font-weight:bold; font-size:{f_title}px; color:{c_header_txt};">{title}</div>
                        {header_extras}
                        <div style="margin-top:5px; font-size:{f_norm}px;">Date: {datetime.now().strftime('%Y-%m-%d')}</div>
                        <div style="margin-top:5px; font-weight:bold; font-size:{f_norm}px;">Client: {customer_name}</div>
                        <div style="margin-top:5px; font-size:{f_norm}px;">Tél: {customer_phone}</div>
                    </td>
                </tr>
            </table>

            <table width="100%" style="border-collapse: collapse; margin-bottom:15px;">
                <tr><th style="text-align:left;">Date du Versement libre</th><th style="text-align:center;">Montant libre initial</th></tr>
                {versements_html}
            </table>

            <table width="100%" style="border: none;">
                <tr>
                    <td width="100%" style="vertical-align: top; padding-right: 10px;">
                        <p style="font-size:{int(f_norm*0.9)}px;"><i>{pdf_cfg["texts"].get("text_arrete", "Arrêté la présente somme de :")}</i><br>.......................................................</p>
                    </td>
                </tr>
            </table>
            <div style='margin-top:25px; text-align:center; border-top:1px dashed #aaa; padding-top:15px;'><b style='font-size:{int(f_norm*0.9)}px;'>{pdf_cfg["texts"].get("policy_debt", "")}</b><br><span dir='rtl' style='font-size:{f_norm}px;'>{pdf_cfg["texts"].get("arabic_debt", "")}</span></div>
        </body></html>
        """

        _render_html_document(html, pdf_cfg, output_path=output_path)
        direct_printer_name = str(direct_printer_name or "").strip()
        if direct_printer_name:
            _render_html_document(html, pdf_cfg, printer_name=direct_printer_name)
        return output_path

    @staticmethod
    def generate_product_versement_receipt(data, output_path="bon_versement_produit.pdf", direct_printer_name=""):
        if _contains_credit_client_document(data):
            raise ValueError("Credit client documents require a dedicated credit-client template.")

        global_cfg, pdf_cfg = PdfHelper.load_pdf_config()

        shop_name = global_cfg.get("shop_name", "Mon Magasin")
        address = global_cfg.get("shop_address", "")
        phone = global_cfg.get("shop_phone", "")
        rc = global_cfg.get("shop_rc", "")
        nif = global_cfg.get("shop_nif", "")
        currency = global_cfg.get("currency", "DA")

        c_txt = pdf_cfg["colors"].get("text_primary", "#333")
        c_th = pdf_cfg["colors"].get("table_header_bg", "#f5f5f5")
        c_grn = pdf_cfg["colors"].get("paid_green", "#27ae60")
        c_red = pdf_cfg["colors"].get("debt_red", "#c0392b")
        c_header_txt, _c_header_bg = _header_style_colors(pdf_cfg)
        header_table_style = _header_table_style(pdf_cfg, margin_bottom=15)
        f_shop = pdf_cfg["fonts"].get("shop_name", 22)
        f_title = pdf_cfg["fonts"].get("doc_title", 18)
        f_norm = pdf_cfg["fonts"].get("normal", 12)
        f_th = pdf_cfg["fonts"].get("table_header", 12)

        bc_w = pdf_cfg["display"].get("item_barcode_w", 70)
        bc_h = pdf_cfg["display"].get("item_barcode_h", 20)

        title = pdf_cfg["texts"].get(
            "title_versement_produit",
            pdf_cfg["texts"].get("title_versement", "BON DE VERSEMENT SUR PRODUIT"),
        )

        customer_name = data.get('customer_name', 'Client')
        sale_id = data.get('sale_id', 0)
        operation_number = _versement_operation_number(data)
        items = data.get('items', [])

        total_weight = _safe_float(data.get('total_weight', 0))
        total_quantity = _safe_float(data.get('total_quantity', 0))
        declared_total_paid = data.get('total_paid')
        declared_remaining_weight = data.get('remaining_weight')
        declared_remaining_quantity = data.get('remaining_quantity')

        show_code = pdf_cfg["display"].get("show_item_code_column", True)
        code_format = pdf_cfg["display"].get("item_code_format", "Code-Barres")
        has_item_notes = any(
            str(item.get("custom_note") or item.get("note") or "").strip() for item in items
        )
        show_items_section = bool(pdf_cfg["display"].get("show_versement_items_section", True)) or has_item_notes
        show_payment_rate = bool(pdf_cfg["display"].get("show_versement_payment_rate", True))

        def _label(key, default):
            return escape(str(pdf_cfg["texts"].get(key) or default))

        lbl_items_title = _label("versement_items_section_title", "Détail des produits réservés")
        lbl_payments_title = _label("versement_payments_section_title", "Versements sur produit")
        lbl_article = _label("versement_label_article", "Article")
        lbl_code = _label("versement_label_code", "Code Produit")
        lbl_total_weight = "Poids Restant (g)"
        lbl_payment_date = _label("versement_label_payment_date", "Date")
        lbl_payment_amount = _label("versement_label_payment_amount", "Montant Versé")
        lbl_payment_weight = _label("versement_label_payment_weight", "Poids")
        lbl_payment_rate = _label("versement_label_payment_rate", "Prix/g paiement")

        lbl_summary_total_weight = _label("versement_summary_total_weight", "Poids Total d'article")
        lbl_summary_total_quantity = _label("versement_summary_total_quantity", "Quantite totale")
        lbl_summary_remaining_quantity = _label("versement_summary_remaining_quantity", "Reste quantite")
        lbl_summary_total_paid = _label("versement_summary_total_paid", "Total Payé")
        lbl_summary_paid_weight = _label("versement_summary_paid_weight", "Poids Acquis")
        lbl_summary_remaining_weight = _label("versement_summary_remaining_weight", "Reste en Poids")

        th_code_detail = f'<th style="text-align:center; background-color:{c_th}; padding:8px 5px; border-bottom:2px solid #333;">{lbl_code}</th>' if show_code else ""

        default_names = " / ".join([str(i.get('item_name') or i.get('name') or 'Article').strip() for i in items]) if items else "Article"
        default_barcodes = " / ".join([str(i.get('barcode') or i.get('inventory_barcode') or '').strip() for i in items if str(i.get('barcode') or i.get('inventory_barcode') or '').strip()]) if items else "N/A"

        items_detail_html = ""
        if items:
            for item in items:
                item_name = escape(str(item.get('item_name') or item.get('name') or item.get('description') or 'Article').strip())
                item_note = escape(str(item.get('custom_note') or item.get('note') or '').strip())
                item_name_html = f"{item_name}<br><span style='font-size:{int(f_norm*0.85)}px; color:#8e44ad; font-weight:bold;'>{item_note}</span>" if item_note else item_name
                item_barcode = str(item.get('barcode') or item.get('inventory_barcode') or item.get('item_barcode') or '').strip()
                rem_item_w = _safe_float(item.get('remaining_weight', item.get('weight', 0)))

                code_td_item = ""
                if show_code:
                    code_content = escape(item_barcode)
                    if code_format == "Code-Barres" and item_barcode:
                        b64_prod = PdfHelper.get_base64_barcode(item_barcode, height=4)
                        if b64_prod:
                            code_content = (
                                f"<img src='{b64_prod}' width='{bc_w}' height='{bc_h}'/>"
                                f"<br><span style='font-size:{int(f_norm*0.8)}px;'>{escape(item_barcode)}</span>"
                            )
                    code_td_item = f"<td style='text-align:center; padding:5px; border-bottom:1px solid #eee;'>{code_content}</td>"

                items_detail_html += f"""
                <tr>
                    <td style="padding:6px 5px; border-bottom:1px solid #eee; font-size:{int(f_norm*0.9)}px; color:#2c3e50; font-weight:bold;">{item_name_html}</td>
                    {code_td_item}
                    <td style="padding:6px 5px; border-bottom:1px solid #eee; text-align:center; color:#c0392b; font-weight:bold;">{rem_item_w:.3f} g</td>
                </tr>
                """
        else:
            cols = 2 if show_code else 1
            items_detail_html = f"<tr><td colspan='{cols}' style='text-align:center; font-style:italic; padding:10px;'>Aucun article</td></tr>"

        versements_html = ""
        total_paid = 0.0
        total_paid_weight = 0.0

        if data.get('versements'):
            for v in data['versements']:
                date_val = v.get('payment_date') or v.get('activity_date') or v.get('date') or datetime.now()
                date_str = date_val.strftime("%Y-%m-%d") if hasattr(date_val, 'strftime') else str(date_val).split(' ')[0]
                amount = _safe_float(v.get('amount'))
                weight = _safe_float(v.get('weight', v.get('purchased_weight', v.get('paid_weight', 0))))
                rate = _payment_rate_reference(v)
                total_paid += amount
                total_paid_weight += weight
                pay_id = v.get('id', '')
                operation_prefix = _payment_operation_prefix(v, f_norm, operation_number)
                id_str = f"<span style='color:#7f8c8d; font-weight:bold;'>N°{pay_id}</span> - " if pay_id and pay_id != 'N/A' else ""

                v_name = str(v.get('product_name') or v.get('item_name') or default_names).strip()
                v_barcode = str(v.get('barcode') or v.get('product_barcode') or v.get('item_barcode') or default_barcodes).strip()

                td_code_content_v = v_barcode
                if show_code and code_format == "Code-Barres" and v_barcode and v_barcode != "N/A":
                    if " / " not in v_barcode:
                        b64_prod = PdfHelper.get_base64_barcode(v_barcode, height=4)
                        if b64_prod:
                            td_code_content_v = f"<img src='{b64_prod}' width='{bc_w}' height='{bc_h}'/><br><span style='font-size:{int(f_norm*0.8)}px;'>{v_barcode}</span>"

                code_td_v = f"<td style='text-align:center; padding:4px 5px; border-bottom:1px solid #eee;'>{td_code_content_v}</td>" if show_code else ""
                rate_td_v = (
                    f"<td style=\"padding:6px 5px; border-bottom:1px solid #eee; font-size:{int(f_norm*0.9)}px; color:#555; text-align:center;\">{rate:,.2f} {currency}/g</td>"
                    if show_payment_rate else ""
                )

                versements_html += f"""
                <tr>
                    <td style="padding:6px 5px; border-bottom:1px solid #eee; font-size:{int(f_norm*0.9)}px; color:#333333;">{operation_prefix}{id_str}{date_str}</td>
                    <td style="padding:6px 5px; border-bottom:1px solid #eee; font-size:{int(f_norm*0.9)}px; color:#2c3e50; font-weight:bold;">{v_name}</td>
                    {code_td_v}
                    <td style="padding:6px 5px; border-bottom:1px solid #eee; font-size:{int(f_norm*0.9)}px; color:{c_grn}; text-align:center; font-weight:bold;">{amount:,.2f} {currency}</td>
                    <td style="padding:6px 5px; border-bottom:1px solid #eee; font-size:{int(f_norm*0.9)}px; color:#2980b9; text-align:center;">+ {weight:.3f} g</td>
                    {rate_td_v}
                </tr>
                """
        else:
            cols = (6 if show_code else 5) if show_payment_rate else (5 if show_code else 4)
            versements_html = f"<tr><td colspan='{cols}' style='text-align:center; font-style:italic; padding:10px;'>Aucun versement</td></tr>"

        if declared_total_paid is not None:
            total_paid = _safe_float(declared_total_paid)
        if data.get('exact_paid_weight', 0) > 0:
            total_paid_weight = _safe_float(data['exact_paid_weight'])

        if declared_remaining_weight is not None:
            remainder_weight = max(0.0, _safe_float(declared_remaining_weight))
        else:
            remainder_weight = max(0.0, total_weight - total_paid_weight)

        if declared_remaining_quantity is not None:
            remainder_quantity = max(0.0, _safe_float(declared_remaining_quantity))
        else:
            paid_quantity = sum(_safe_float(v.get('quantity', v.get('paid_quantity', 0))) for v in data.get('versements') or [])
            remainder_quantity = max(0.0, total_quantity - paid_quantity)

        logo_html = PdfHelper.get_logo_html(pdf_cfg["logo"])
        align_opt = pdf_cfg["logo"].get("align", "À gauche du nom")
        cell_logo_l = f"<td width='1%' style='padding-right:15px; vertical-align:top;'>{logo_html}</td>" if align_opt == "À gauche du nom" and logo_html else ""
        cell_logo_r = f"<td width='1%' style='padding-left:15px; vertical-align:top;'>{logo_html}</td>" if align_opt == "À droite du nom" and logo_html else ""
        block_logo_top = f"<div style='text-align:center; margin-bottom:10px;'>{logo_html}</div>" if align_opt == "Au-dessus du nom (Centré)" and logo_html else ""
        rc_nif_txt = f"{'RC: '+rc+' | NIF: '+nif if pdf_cfg['display'].get('show_rc_nif', True) else ''}"
        qr_html = PdfHelper.build_qr_html(pdf_cfg)
        if qr_html:
            rc_nif_txt = f"{rc_nif_txt}{qr_html}"

        receipt_number = _versement_receipt_display_number(data)
        header_extras = PdfHelper.build_document_code_html(pdf_cfg, receipt_number, f_norm)
        sale_reference_html = _sale_reference_html(sale_id, f_norm, _facture_reference_number(data))

        th_code = f'<th style="text-align:center; background-color:{c_th}; padding:8px 5px; border-bottom:2px solid #333;">{lbl_code}</th>' if show_code else ""
        th_payment_rate = (
            f'<th style="text-align:center; background-color:{c_th}; padding:8px 5px; border-bottom:2px solid #333;">{lbl_payment_rate}</th>'
            if show_payment_rate else ""
        )

        # ─── ملخص بدون "montant facture" ───
        summary_rows = ""
        summary_rows += f"<tr><td style='padding:5px; border-bottom:1px solid #eee;'>{lbl_summary_total_weight}</td><td style='padding:5px; border-bottom:1px solid #eee; text-align:center; font-weight:bold;'>{total_weight:.3f} g</td></tr>"
        summary_rows += f"<tr><td style='padding:5px; border-bottom:1px solid #eee;'>{lbl_summary_total_paid}</td><td style='padding:5px; border-bottom:1px solid #eee; text-align:center; font-weight:bold; color:{c_grn};'>{total_paid:,.2f} {currency}</td></tr>"
        summary_rows += f"<tr><td style='padding:5px; border-bottom:1px solid #eee;'>{lbl_summary_paid_weight}</td><td style='padding:5px; border-bottom:1px solid #eee; text-align:center; font-weight:bold; color:#2980b9;'>{total_paid_weight:.3f} g</td></tr>"
        summary_rows += f"<tr><td style='padding:8px 5px; font-weight:bold; font-size:{int(f_norm*1.05)}px; color:{c_red};'>{lbl_summary_remaining_weight}</td><td style='padding:8px 5px; text-align:center; font-weight:bold; font-size:{int(f_norm*1.05)}px; color:{c_red}; background-color:#fdf5f5;'>{remainder_weight:.3f} g</td></tr>"

        items_section_html = ""
        if show_items_section:
            items_section_html = f"""
            <div style="margin-bottom:15px;">
                <div style="font-weight:bold; font-size:{int(f_norm*1.05)}px; margin-bottom:5px; color:#2c3e50;">{lbl_items_title}</div>
                <table width="100%" style="border-collapse: collapse;">
                    <tr>
                        <th style="text-align:left; background-color:{c_th}; padding:8px 5px; border-bottom:2px solid #333;">{lbl_article}</th>
                        {th_code_detail}
                        <th style="text-align:center; background-color:{c_th}; padding:8px 5px; border-bottom:2px solid #333;">{lbl_total_weight}</th>
                    </tr>
                    {items_detail_html}
                </table>
            </div>
            """

        html = f"""
        <html><head><style>
            body {{ font-family: Arial, sans-serif; color: {c_txt}; font-size: {f_norm}px; }}
            th {{ background-color: {c_th}; padding: 8px; border-bottom: 2px solid {c_txt}; font-size: {f_th}px; text-transform: uppercase; }}
            td {{ padding: 8px; border-bottom: 1px solid #eee; }}
        </style></head><body>
            {block_logo_top}
            <table width="100%" style="{header_table_style}">
                <tr>
                    {cell_logo_l}
                    <td style="border:none; padding:0; vertical-align:top;">
                        <div style="margin:0; font-weight:bold; font-size:{f_shop}px; color:{c_header_txt};">{shop_name}</div>
                        <div style="margin-top:5px; font-size:{f_norm}px;">{address}<br>Tél: {phone}<br>{rc_nif_txt}</div>
                    </td>
                    {cell_logo_r}
                    <td width="40%" style="text-align:right; border:none; padding:0; vertical-align:top;">
                        <div style="margin:0; font-weight:bold; font-size:{f_title}px; color:{c_header_txt};">{title}</div>
                        {header_extras}
                        {sale_reference_html}
                        <div style="margin-top:5px; font-size:{f_norm}px;">Date: {datetime.now().strftime('%Y-%m-%d')}</div>
                        <div style="margin-top:5px; font-weight:bold; font-size:{f_norm}px;">Client: {customer_name}</div>
                    </td>
                </tr>
            </table>

            {items_section_html}

            <div style="font-weight:bold; font-size:{int(f_norm*1.05)}px; margin-bottom:5px; color:#2c3e50;">{lbl_payments_title}</div>
            <table width="100%" style="border-collapse: collapse; margin-bottom:15px;">
                <tr>
                    <th style="text-align:left; background-color:{c_th}; padding:8px 5px; border-bottom:2px solid #333;">{lbl_payment_date}</th>
                    <th style="text-align:left; background-color:{c_th}; padding:8px 5px; border-bottom:2px solid #333;">{lbl_article}</th>
                    {th_code}
                    <th style="text-align:center; background-color:{c_th}; padding:8px 5px; border-bottom:2px solid #333;">{lbl_payment_amount}</th>
                    <th style="text-align:center; background-color:{c_th}; padding:8px 5px; border-bottom:2px solid #333;">{lbl_payment_weight}</th>
                    {th_payment_rate}
                </tr>
                {versements_html}
            </table>

            <table width="55%" style="border-collapse: collapse; float:right; margin-top:5px;">
                {summary_rows}
            </table>
            <div style="clear:both;"></div>

            <div style='margin-top:25px; text-align:center; border-top:1px dashed #aaa; padding-top:15px;'><b style='font-size:{int(f_norm*0.9)}px;'>{pdf_cfg["texts"].get("policy_debt", "")}</b><br><span dir='rtl' style='font-size:{f_norm}px;'>{pdf_cfg["texts"].get("arabic_debt", "")}</span></div>
        </body></html>
        """

        _render_html_document(html, pdf_cfg, output_path=output_path)
        direct_printer_name = str(direct_printer_name or "").strip()
        if direct_printer_name:
            _render_html_document(html, pdf_cfg, printer_name=direct_printer_name)
        return output_path

    @staticmethod
    def generate_credit_client_receipt(data, output_path="credit_client.pdf", direct_printer_name=""):
        global_cfg, pdf_cfg = PdfHelper.load_pdf_config()

        shop_name = global_cfg.get("shop_name", "Mon Magasin")
        address = global_cfg.get("shop_address", "")
        phone = global_cfg.get("shop_phone", "")
        rc = global_cfg.get("shop_rc", "")
        nif = global_cfg.get("shop_nif", "")
        currency = global_cfg.get("currency", "DA")

        c_txt = pdf_cfg["colors"].get("text_primary", "#333")
        c_th = pdf_cfg["colors"].get("table_header_bg", "#f5f5f5")
        c_grn = pdf_cfg["colors"].get("paid_green", "#27ae60")
        c_red = pdf_cfg["colors"].get("debt_red", "#c0392b")
        c_header_txt, _c_header_bg = _header_style_colors(pdf_cfg)
        header_table_style = _header_table_style(pdf_cfg, margin_bottom=20)
        f_shop = pdf_cfg["fonts"].get("shop_name", 22)
        f_title = pdf_cfg["fonts"].get("doc_title", 18)
        f_norm = pdf_cfg["fonts"].get("normal", 12)
        f_th = pdf_cfg["fonts"].get("table_header", 12)

        title = pdf_cfg["texts"].get("title_credit_client", "DOCUMENT CREDIT CLIENT")

        customer_name = data.get('customer_name', data.get('client_name', 'Client'))
        customer_phone = data.get('phone', data.get('client_phone', 'N/A'))

        logo_html = PdfHelper.get_logo_html(pdf_cfg["logo"])
        align_opt = pdf_cfg["logo"].get("align", "À gauche du nom")
        cell_logo_l = f"<td width='1%' style='padding-right:15px; vertical-align:top;'>{logo_html}</td>" if align_opt == "À gauche du nom" and logo_html else ""
        cell_logo_r = f"<td width='1%' style='padding-left:15px; vertical-align:top;'>{logo_html}</td>" if align_opt == "À droite du nom" and logo_html else ""
        block_logo_top = f"<div style='text-align:center; margin-bottom:10px;'>{logo_html}</div>" if align_opt == "Au-dessus du nom (Centré)" and logo_html else ""

        qr_html = PdfHelper.build_qr_html(pdf_cfg)

        credit_number = (
            data.get("credit_number")
            or data.get("receipt_number")
            or data.get("operation_number")
            or ""
        )
        header_extras = PdfHelper.build_document_code_html(pdf_cfg, credit_number, f_norm)

        credit_amount = _safe_float(data.get('amount') or data.get('credit_amount') or data.get('total_amount') or 0)
        credit_weight = _safe_float(data.get('weight') or data.get('purchased_weight') or 0)
        rate = _safe_float(data.get('metal_rate') or data.get('metal_rate_at_payment') or 0)

        details_html = f"<tr><td style='padding:6px; text-align:right;'>Montant du crédit :</td><td style='padding:6px; text-align:right; font-weight:bold;'>{credit_amount:,.2f} {currency}</td></tr>"
        if credit_weight > 0:
            details_html += f"<tr><td style='padding:6px; text-align:right;'>Poids :</td><td style='padding:6px; text-align:right; font-weight:bold;'>{credit_weight:.3f} g</td></tr>"
        if rate > 0:
            details_html += f"<tr><td style='padding:6px; text-align:right;'>Prix/g :</td><td style='padding:6px; text-align:right; font-weight:bold;'>{rate:,.2f} {currency}/g</td></tr>"

        reason = str(data.get('reason') or data.get('description') or '').strip()
        if reason:
            details_html += f"<tr><td style='padding:6px; text-align:right;'>Motif :</td><td style='padding:6px; text-align:right;'>{escape(reason)}</td></tr>"

        rc_nif_txt = f"{'RC: '+rc+' | NIF: '+nif if pdf_cfg['display'].get('show_rc_nif', True) else ''}"
        if qr_html:
            rc_nif_txt = f"{rc_nif_txt}{qr_html}"

        html = f"""
        <html><head><style>
            body {{ font-family: Arial, sans-serif; color: {c_txt}; font-size: {f_norm}px; }}
            th {{ background-color: {c_th}; padding: 8px; border-bottom: 2px solid {c_txt}; font-size: {f_th}px; text-transform: uppercase; }}
            td {{ padding: 8px; border-bottom: 1px solid #eee; }}
        </style></head><body>
            {block_logo_top}
            <table width="100%" style="{header_table_style}">
                <tr>
                    {cell_logo_l}
                    <td style="border:none; padding:0; vertical-align:top;">
                        <div style="margin:0; font-weight:bold; font-size:{f_shop}px; color:{c_header_txt};">{shop_name}</div>
                        <div style="margin-top:5px; font-size:{f_norm}px;">{address}<br>Tél: {phone}<br>{rc_nif_txt}</div>
                    </td>
                    {cell_logo_r}
                    <td width="40%" style="text-align:right; border:none; padding:0; vertical-align:top;">
                        <div style="margin:0; font-weight:bold; font-size:{f_title}px; color:{c_header_txt};">{title}</div>
                        {header_extras}
                        <div style="margin-top:5px; font-size:{f_norm}px;">Date: {datetime.now().strftime('%Y-%m-%d')}</div>
                        <div style="margin-top:5px; font-weight:bold; font-size:{f_norm}px;'>Client: {customer_name}</div>
                        <div style="margin-top:5px; font-size:{f_norm}px;">Tél: {customer_phone}</div>
                    </td>
                </tr>
            </table>

            <table width="60%" style="border-collapse: collapse; margin: 15px 0 15px auto;">
                {details_html}
            </table>

            <div style='margin-top:25px; text-align:center; border-top:1px dashed #aaa; padding-top:15px;'><b style='font-size:{int(f_norm*0.9)}px;'>{pdf_cfg["texts"].get("policy_debt", "")}</b><br><span dir='rtl' style='font-size:{f_norm}px;'>{pdf_cfg["texts"].get("arabic_debt", "")}</span></div>
        </body></html>
        """

        _render_html_document(html, pdf_cfg, output_path=output_path)
        direct_printer_name = str(direct_printer_name or "").strip()
        if direct_printer_name:
            _render_html_document(html, pdf_cfg, printer_name=direct_printer_name)
        return output_path