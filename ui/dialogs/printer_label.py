import os
import json
import random
import datetime
import io
import copy

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, 
    QHeaderView, QPushButton, QLineEdit, QFormLayout, QGroupBox, QDialog,
    QMessageBox, QComboBox, QDoubleSpinBox, QLabel, QFrame, QSpinBox,
    QCheckBox, QInputDialog, QTabWidget, QScrollArea, QApplication,
    QSplitter, QGridLayout, QSizePolicy, QAbstractSpinBox,
    QListWidget, QListWidgetItem 
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QColor, QFont, QIcon, QImage, QPixmap 
import qtawesome as qta

import win32print
import barcode
from barcode.writer import ImageWriter
from PIL import Image, ImageDraw, ImageFont, ImageOps




class LocalLabelPrinter:
    DPI_MULTIPLIER = 8  # 203 DPI

    @staticmethod
    def get_font(font_name, size):
        if size <= 0: return None
        try:
            return ImageFont.truetype(font_name, size)
        except:
            return ImageFont.load_default()

    @staticmethod
    def create_jewelry_label(label_config, item_data):
        W_raw = int(label_config['label']['width_mm'] * LocalLabelPrinter.DPI_MULTIPLIER)
        W = (W_raw + 7) // 8 * 8 
        H = int(label_config['label']['height_mm'] * LocalLabelPrinter.DPI_MULTIPLIER)
        
        img = Image.new('L', (W, H), 255)
        draw = ImageDraw.Draw(img)

        barcode_str = str(item_data.get('barcode') or '')
        product_name = str(item_data.get('name') or '')
        category_str = str(item_data.get('category_name') or '')
        price_val = float(item_data.get('selling_price') or 0)
        price_str = f"{price_val:,.0f} DA" if price_val > 0 else ""
        supplier_str = str(item_data.get('supplier_name') or '')
        metal_str = str(item_data.get('metal_type_name') or '')
        weight_val = item_data.get('weight')

        elements = label_config.get('elements', {})

        def draw_text_element(config_key, text_val):
            if not text_val: return
            cfg = elements.get(config_key, {})
            if cfg.get('show') and cfg.get('font_size', 0) > 0:
                font_family = cfg.get('font_family', 'arial.ttf')
                f = LocalLabelPrinter.get_font(font_family, cfg['font_size'])
                cx = int(cfg['center_x_mm'] * LocalLabelPrinter.DPI_MULTIPLIER)
                cy = int(cfg['y_pos_mm'] * LocalLabelPrinter.DPI_MULTIPLIER)
                try:
                    bbox = draw.textbbox((0, 0), text_val, font=f)
                    tw = bbox[2] - bbox[0]
                except AttributeError:
                    tw = f.getlength(text_val) if hasattr(f, 'getlength') else 40
                draw.text((cx - tw // 2, cy), text_val, font=f, fill=0)

        static_cfg = elements.get('static_text', {})
        if static_cfg.get('show'):
            draw_text_element('static_text', static_cfg.get('text', ''))

        draw_text_element('product_name', product_name)
        draw_text_element('category', category_str)
        draw_text_element('model_name', supplier_str) 
        draw_text_element('metal_type', metal_str)
        draw_text_element('price', price_str)
        draw_text_element('barcode_text', barcode_str)

        # Weight element
        cfg_w = elements.get('weight', {})
        if cfg_w.get('show') and weight_val is not None:
            try:
                decimals = int(cfg_w.get('decimals', 2))
                prefix = cfg_w.get('prefix', 'Poids: ')
                suffix = cfg_w.get('suffix', ' g')
                weight_str = f"{prefix}{float(weight_val):.{decimals}f}{suffix}"
                draw_text_element('weight', weight_str)
            except Exception as e:
                print(f"Weight label error: {e}")

        cfg_bc = elements.get('barcode', {})
        if cfg_bc.get('show') and barcode_str:
            try:
                writer = ImageWriter(format="PNG")
                if barcode_str.isdigit() and len(barcode_str) in (12, 13):
                    bc_class = barcode.get_barcode_class('ean13')
                else:
                    bc_class = barcode.get_barcode_class('code128')
                
                opts = {
                    "module_width": cfg_bc.get('module_width_mm', 0.2), 
                    "module_height": cfg_bc.get('height_mm', 10), 
                    "background": "white", "foreground": "black", 
                    "write_text": False, "quiet_zone": 0.0 
                }
                fp = io.BytesIO()
                bc_class(barcode_str, writer=writer).write(fp, options=opts)
                fp.seek(0)
                
                bc_img = Image.open(fp).convert("L")
                inv = ImageOps.invert(bc_img) 
                bbox = inv.getbbox()
                if bbox: bc_img = bc_img.crop(bbox)
                
                bc_cx = int(cfg_bc.get('center_x_mm', 20) * LocalLabelPrinter.DPI_MULTIPLIER)
                bc_y = int(cfg_bc.get('y_pos_mm', 20) * LocalLabelPrinter.DPI_MULTIPLIER)
                img.paste(bc_img, (bc_cx - bc_img.width//2, bc_y))
            except Exception as e:
                print(f"Barcode logic error: {e}")

        return img.point(lambda x: 0 if x < 128 else 255).convert('1', dither=Image.NONE)

    @staticmethod
    def get_tspl_for_image(label_config, pil_img, copies=1):
        w_mm = float(label_config['label']['width_mm'])
        h_mm = float(label_config['label']['height_mm'])
        gap = float(label_config['label']['gap_mm'])
        shift_x_mm = float(label_config['print_area']['x_pos_mm'])
        shift_y_mm = float(label_config['print_area']['y_pos_mm'])
        
        shift_x_dots = int(shift_x_mm * LocalLabelPrinter.DPI_MULTIPLIER)
        shift_y_dots = int(shift_y_mm * LocalLabelPrinter.DPI_MULTIPLIER)
        
        W, H = pil_img.size
        print_canvas = Image.new('1', (W, H), 255) 
        print_canvas.paste(pil_img, (shift_x_dots, shift_y_dots))
        
        Wb = W // 8  
        cmds = [
            f"SIZE {w_mm:g} mm, {h_mm:g} mm",
            f"GAP {gap:g} mm, 0 mm",
            "DIRECTION 1", "CLS",
            "SET PEEL OFF", "SET TEAR ON",   
            f"BITMAP 0,0,{Wb},{H},0," 
        ]
        data = print_canvas.tobytes()
        return "\r\n".join(cmds).encode("ascii") + data + f"\r\nPRINT {copies}\r\n".encode("ascii")

    @staticmethod
    def send_to_printer(printer_name, raw_data):
        if not printer_name: return False, "Nom d'imprimante vide."
        try:
            hprinter = win32print.OpenPrinter(printer_name)
            try:
                win32print.StartDocPrinter(hprinter, 1, ("Jewelry Label", None, "RAW"))
                win32print.StartPagePrinter(hprinter)
                win32print.WritePrinter(hprinter, raw_data)
                win32print.EndPagePrinter(hprinter)
                win32print.EndDocPrinter(hprinter)
            finally:
                win32print.ClosePrinter(hprinter)
            return True, "Impression réussie."
        except Exception as e:
            return False, str(e)


class LabelPrintPreviewDialog(QDialog):
    def __init__(self, label_config, item_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Aperçu et Ajustement de l'Étiquette")
        self.setWindowFlags(Qt.Window | Qt.WindowMaximizeButtonHint | Qt.WindowCloseButtonHint)
        
        self.original_config = label_config
        self.temp_config = copy.deepcopy(label_config) 
        self.temp_data = dict(item_data)
        self.zoom_factor = 2.5 
        
        self.init_ui()
        self.update_preview()

    def showEvent(self, event):
        super().showEvent(event)
        self.showMaximized()

    def init_ui(self):
        main_layout = QHBoxLayout(self)
        
        left_panel = QWidget()
        left_panel.setFixedWidth(450)
        left_layout = QVBoxLayout(left_panel)
        
        tabs = QTabWidget()
        tabs.setStyleSheet("QTabWidget::pane { border: 1px solid #bdc3c7; border-radius: 5px; } QTabBar::tab { font-weight: bold; padding: 10px; }")
        
        tab_data = QWidget()
        data_layout = QFormLayout(tab_data)
        data_layout.setVerticalSpacing(15)
        
        self.inp_name = QLineEdit(str(self.temp_data.get('name', '')))
        self.inp_category = QLineEdit(str(self.temp_data.get('category_name', '')))
        self.inp_supplier = QLineEdit(str(self.temp_data.get('supplier_name', '')))
        self.inp_metal = QLineEdit(str(self.temp_data.get('metal_type_name', '')))
        self.inp_barcode = QLineEdit(str(self.temp_data.get('barcode', '')))
        
        self.spin_price = QDoubleSpinBox()
        self.spin_price.setRange(0, 100000000)
        self.spin_price.setDecimals(2)
        self.spin_price.setSuffix(" DA")
        self.spin_price.setValue(float(self.temp_data.get('selling_price') or 0))

        self.spin_weight = QDoubleSpinBox()
        self.spin_weight.setRange(0, 100000)
        self.spin_weight.setDecimals(2)
        self.spin_weight.setSuffix(" g")
        self.spin_weight.setValue(float(self.temp_data.get('weight') or 0))
        
        self.spin_copies = QSpinBox()
        self.spin_copies.setRange(1, 500)
        self.spin_copies.setValue(1)
        self.spin_copies.setStyleSheet("font-size: 16px; font-weight: bold; padding: 5px;")
        
        data_layout.addRow("Article :", self.inp_name)
        data_layout.addRow("Catégorie :", self.inp_category)
        data_layout.addRow("Fournisseur / Modèle :", self.inp_supplier)
        data_layout.addRow("Métal :", self.inp_metal)
        data_layout.addRow("Code-barres :", self.inp_barcode)
        data_layout.addRow("Prix (DA) :", self.spin_price)
        data_layout.addRow("Poids :", self.spin_weight)
        data_layout.addRow(QLabel("<hr>"))
        data_layout.addRow("<b>Nombre de copies :</b>", self.spin_copies)
        
        tabs.addTab(tab_data, "📋 Données")
        
        tab_pos = QWidget()
        pos_layout = QVBoxLayout(tab_pos)
        
        scroll_pos = QScrollArea()
        scroll_pos.setWidgetResizable(True)
        scroll_pos.setFrameShape(QFrame.NoFrame)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(10)
        
        def add_pos_controls(title, key):
            grp = QGroupBox(title)
            grp.setStyleSheet("QGroupBox { font-weight: bold; border: 1px solid #bdc3c7; border-radius: 5px; margin-top: 10px; }")
            flay = QFormLayout(grp)
            cfg = self.temp_config['elements'].get(key, {})
            
            sp_x = QDoubleSpinBox(); sp_x.setRange(-100, 200); sp_x.setValue(cfg.get('center_x_mm', 0))
            sp_y = QDoubleSpinBox(); sp_y.setRange(-100, 200); sp_y.setValue(cfg.get('y_pos_mm', 0))
            
            sp_x.valueChanged.connect(lambda v, k=key: self.update_temp_config(k, 'center_x_mm', v))
            sp_y.valueChanged.connect(lambda v, k=key: self.update_temp_config(k, 'y_pos_mm', v))
            
            flay.addRow("Centre X (mm) :", sp_x)
            flay.addRow("Position Y (mm) :", sp_y)
            
            if 'font_size' in cfg:
                sp_size = QSpinBox(); sp_size.setRange(1, 100); sp_size.setValue(cfg.get('font_size', 10))
                sp_size.valueChanged.connect(lambda v, k=key: self.update_temp_config(k, 'font_size', v))
                flay.addRow("Taille Police :", sp_size)
            
            scroll_layout.addWidget(grp)

        add_pos_controls("Texte Statique (Boutique)", "static_text")
        add_pos_controls("Nom Produit", "product_name")
        add_pos_controls("Catégorie", "category")
        add_pos_controls("Fournisseur / Modèle", "model_name")
        add_pos_controls("Type Métal", "metal_type")
        add_pos_controls("Prix", "price")
        add_pos_controls("Poids", "weight")
        add_pos_controls("Code-barres (Lignes)", "barcode")
        add_pos_controls("Code-barres (Numéros)", "barcode_text")
        
        scroll_layout.addStretch()
        scroll_pos.setWidget(scroll_content)
        pos_layout.addWidget(scroll_pos)
        
        tabs.addTab(tab_pos, "📏 Ajustements")
        
        left_layout.addWidget(tabs)
        
        btn_box = QHBoxLayout()
        btn_cancel = QPushButton("Annuler (Quitter)")
        btn_cancel.clicked.connect(self.reject)
        
        btn_print = QPushButton("🖨️ Imprimer")
        btn_print.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; font-size: 16px; padding: 12px; border-radius: 5px;")
        btn_print.setCursor(Qt.PointingHandCursor)
        btn_print.clicked.connect(self.print_label)
        
        btn_box.addWidget(btn_cancel)
        btn_box.addWidget(btn_print)
        left_layout.addLayout(btn_box)
        
        right_panel = QGroupBox("Aperçu en direct")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setAlignment(Qt.AlignCenter)
        
        zoom_layout = QHBoxLayout()
        zoom_layout.setAlignment(Qt.AlignCenter)
        
        btn_zoom_out = QPushButton("➖ Dézoomer")
        btn_zoom_out.setCursor(Qt.PointingHandCursor)
        btn_zoom_out.setStyleSheet("padding: 8px; font-weight: bold; background-color: #ecf0f1; border-radius: 4px;")
        btn_zoom_out.clicked.connect(self.zoom_out)
        
        btn_zoom_in = QPushButton("➕ Zoomer")
        btn_zoom_in.setCursor(Qt.PointingHandCursor)
        btn_zoom_in.setStyleSheet("padding: 8px; font-weight: bold; background-color: #ecf0f1; border-radius: 4px;")
        btn_zoom_in.clicked.connect(self.zoom_in)
        
        zoom_layout.addWidget(btn_zoom_out)
        zoom_layout.addWidget(btn_zoom_in)
        
        right_layout.addLayout(zoom_layout)
        
        self.lbl_preview = QLabel("Génération...")
        self.lbl_preview.setAlignment(Qt.AlignCenter)
        self.lbl_preview.setStyleSheet("background-color: white; border: 2px dashed #bdc3c7; border-radius: 5px; padding: 15px;")
        
        scroll_preview = QScrollArea()
        scroll_preview.setWidgetResizable(True)
        scroll_preview.setAlignment(Qt.AlignCenter)
        scroll_preview.setFrameShape(QFrame.NoFrame)
        scroll_preview.setWidget(self.lbl_preview)
        
        right_layout.addWidget(scroll_preview)
        
        hint = QLabel("💡 <i>Note : Les ajustements de position ici sont temporaires.</i>")
        hint.setStyleSheet("color: #e67e22; font-size: 14px; font-weight: bold;")
        hint.setAlignment(Qt.AlignCenter)
        right_layout.addWidget(hint)
        
        main_layout.addWidget(left_panel)
        main_layout.addWidget(right_panel, stretch=1)
        
        self.inp_name.textChanged.connect(self.on_data_changed)
        self.inp_category.textChanged.connect(self.on_data_changed)
        self.inp_supplier.textChanged.connect(self.on_data_changed)
        self.inp_metal.textChanged.connect(self.on_data_changed)
        self.inp_barcode.textChanged.connect(self.on_data_changed)
        self.spin_price.valueChanged.connect(self.on_data_changed)
        self.spin_weight.valueChanged.connect(self.on_data_changed)

    def zoom_in(self):
        self.zoom_factor += 0.5
        self.update_preview()

    def zoom_out(self):
        if self.zoom_factor > 0.5:
            self.zoom_factor -= 0.5
            self.update_preview()

    def update_temp_config(self, elem_key, prop, value):
        if elem_key in self.temp_config['elements']:
            self.temp_config['elements'][elem_key][prop] = value
            self.update_preview()

    def on_data_changed(self):
        self.temp_data['name'] = self.inp_name.text()
        self.temp_data['category_name'] = self.inp_category.text()
        self.temp_data['supplier_name'] = self.inp_supplier.text()
        self.temp_data['metal_type_name'] = self.inp_metal.text()
        self.temp_data['barcode'] = self.inp_barcode.text()
        self.temp_data['selling_price'] = self.spin_price.value()
        self.temp_data['weight'] = self.spin_weight.value()
        self.update_preview()

    def update_preview(self):
        img_pil = LocalLabelPrinter.create_jewelry_label(self.temp_config, self.temp_data)
        if not img_pil: return
        
        W, H = img_pil.size
        grid_img = Image.new('RGB', (W, H), 'white')
        draw = ImageDraw.Draw(grid_img)
        
        w_mm = self.temp_config['label']['width_mm']
        h_mm = self.temp_config['label']['height_mm']
        
        for i in range(0, int(w_mm) + 1):
            x = int(i * LocalLabelPrinter.DPI_MULTIPLIER)
            if i % 10 == 0: draw.line([(x, 0), (x, H)], fill="#ffcccc", width=2)
            elif i % 5 == 0: draw.line([(x, 0), (x, H)], fill="#cceeff", width=1)
            else: draw.line([(x, 0), (x, H)], fill="#f0f0f0", width=1)

        for i in range(0, int(h_mm) + 1):
            y = int(i * LocalLabelPrinter.DPI_MULTIPLIER)
            if i % 10 == 0: draw.line([(0, y), (W, y)], fill="#ffcccc", width=2)
            elif i % 5 == 0: draw.line([(0, y), (W, y)], fill="#cceeff", width=1)
            else: draw.line([(0, y), (W, y)], fill="#f0f0f0", width=1)
            
        mask = ImageOps.invert(img_pil.convert("L"))
        black_layer = Image.new("RGB", img_pil.size, "black")
        grid_img.paste(black_layer, (0, 0), mask)
        
        data = grid_img.tobytes("raw", "RGB")
        qim = QImage(data, grid_img.width, grid_img.height, grid_img.width * 3, QImage.Format_RGB888).copy()
        pix = QPixmap.fromImage(qim)
        
        scaled_pix = pix.scaled(int(grid_img.width * self.zoom_factor), int(grid_img.height * self.zoom_factor), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.lbl_preview.setPixmap(scaled_pix)

    def get_print_data(self):
        return self.temp_data, self.spin_copies.value(), self.temp_config

    def print_label(self):
        printer_name = self.original_config.get("printer_name", "")
        if not printer_name:
            QMessageBox.warning(self, "Erreur", "Aucune imprimante sélectionnée.")
            return

        modified_data, copies, temp_config = self.get_print_data()

        try:
            img = LocalLabelPrinter.create_jewelry_label(temp_config, modified_data)
            tspl_data = LocalLabelPrinter.get_tspl_for_image(temp_config, img, copies)
            success, message = LocalLabelPrinter.send_to_printer(printer_name, tspl_data)
            
            if not success:
                QMessageBox.critical(self, "Erreur", str(message))
        except Exception as e:
            QMessageBox.critical(self, "Erreur Inattendue", str(e))