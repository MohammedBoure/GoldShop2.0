import win32ui
import win32con
import win32print
import win32gui
import pywintypes
import logging
from config import print_settings

# إعداد التسجيل
logger = logging.getLogger(__name__)

def format_number(value):
    """
    تنسق الرقم: كرقم صحيح إذا لم يكن له جزء عشري،
    أو كرقم عشري بفاصلتين إذا كان له جزء عشري.
    """
    try:
        val_float = float(value)
        if val_float == int(val_float):
            return f"{int(val_float):,}"
        else:
            return f"{val_float:,.2f}"
    except (ValueError, TypeError):
        logger.error(f"خطأ في تنسيق الرقم: {value}")
        return str(value)

def get_column_anchors(page_width, margin, columns, columns_order, direction='rtl'):
    """
    يحسب مواقع الأعمدة بناءً على عرض الصفحة، الهوامش، وإعدادات الأعمدة.
    يعيد قاموساً يحتوي على إحداثيات x ومحاذاة كل عمود.
    """
    usable_width = page_width - 2 * margin
    col_anchors = {}
    total_width_percent = sum(col.get('width_percent', 0) for col in columns.values())
    
    # تحويل النسب المئوية إلى بكسل
    if total_width_percent <= 100:
        col_widths = {key: int(col['width_percent'] * usable_width / 100) for key, col in columns.items()}
    else:
        col_widths = {key: col['width_percent'] for key, col in columns.items()}
    
    x = page_width - margin if direction == 'rtl' else margin
    step = -1 if direction == 'rtl' else 1
    
    for col_key in columns_order:
        col = columns[col_key]
        width = col_widths[col_key]
        align = col['align']
        offset = col['offset']
        
        if align == 'center':
            anchor_x = x + (width / 2) * step + offset
            ta = win32con.TA_CENTER
        elif (align == 'right' and direction == 'rtl') or (align == 'left' and direction != 'rtl'):
            anchor_x = x + offset
            ta = win32con.TA_RIGHT if direction == 'rtl' else win32con.TA_LEFT
        else:
            anchor_x = x + width * step + offset
            ta = win32con.TA_LEFT if direction == 'rtl' else win32con.TA_RIGHT
        
        col_anchors[col_key] = {'x': anchor_x, 'ta': ta}
        x += width * step
    
    return col_anchors

def calculate_and_print(data, print_function, doc_name, printer_name, theme='default', language='ar'):
    """
    المدير العام للطباعة: يحسب الارتفاع، يجهز الورق الطويل، وينفذ الطباعة.
    """
    printer_name = str(printer_name or "").strip()
    if not printer_name:
        raise ValueError("Aucune imprimante n'a été sélectionnée.")
    logger.info(f"بدء عملية الطباعة على الطابعة: {printer_name} باستخدام الثيم: {theme} واللغة: {language}")
    theme_config = print_settings.get(theme, print_settings.get('default', {}))
    bottom_margin = theme_config.get('bottom_margin', 50)
    extra_bottom_feed_pixels = theme_config.get('extra_bottom_feed_pixels', 100)
    total_height = print_function(data, calculate_only=True, theme=theme, language=language)

    try:
        h_printer = win32print.OpenPrinter(printer_name)
        properties = win32print.GetPrinter(h_printer, 2)
        devmode = properties['pDevMode']
        
        paper_length_mm10 = int(((total_height + bottom_margin + extra_bottom_feed_pixels) / 96) * 25.4 * 10)

        devmode.PaperSize = 0
        devmode.PaperLength = paper_length_mm10
        devmode.Fields |= win32con.DM_PAPERSIZE | win32con.DM_PAPERLENGTH

        win32print.ClosePrinter(h_printer)

        hDC_handle = win32gui.CreateDC("WINSPOOL", printer_name, devmode)
        hDC = win32ui.CreateDCFromHandle(hDC_handle)
        
        hDC.StartDoc(doc_name)
        hDC.StartPage()
        
        try:
            print_function(data, calculate_only=False, hDC=hDC, theme=theme, language=language)
            logger.info(f"تمت الطباعة بنجاح: {doc_name}")
        finally:
            hDC.EndPage()
            hDC.EndDoc()
            hDC.DeleteDC()
    except Exception as e:
        logger.error(f"خطأ أثناء الطباعة على الطابعة {printer_name}: {e}", exc_info=True)
        raise
