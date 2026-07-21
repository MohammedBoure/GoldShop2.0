import logging
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

import mysql.connector

from database.versement_reservation import sellable_stock_condition_sql


class InventoryQueryMixin:
    def get_item_by_id(self, item_id: int) -> Optional[Dict]:
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = """
                    SELECT 
                        i.*, 
                        c.name as category_name, 
                        mt.name as metal_type_name,
                        s.name as supplier_name,
                        l.name as location_name,
                        cl.name as reserved_client_name
                    FROM Inventory i
                    LEFT JOIN Categories c ON i.category_id = c.id
                    LEFT JOIN MetalTypes mt ON i.metal_type_id = mt.id
                    LEFT JOIN Suppliers s ON i.supplier_id = s.id
                    LEFT JOIN StorageLocations l ON i.location_id = l.id
                    LEFT JOIN Clients cl ON i.reserved_for_client_id = cl.id
                    WHERE i.id = %s
                """
                cursor.execute(query, (item_id,))
                return cursor.fetchone()
        except mysql.connector.Error as e:
            logging.error(f"Erreur lors de la récupération de l'article {item_id}: {e}")
            return None

    def get_item_by_barcode(self, barcode: str) -> Optional[Dict]:
        conn = None
        cursor = None
        try:
            conn = self.db.get_raw_connection()
            cursor = conn.cursor(dictionary=True)
            conn.autocommit = True
            
            query = """
                SELECT i.*, 
                    c.name as category_name, 
                    mt.name as metal_type_name,
                    mt.purity_value as metal_purity,
                    cl.name as reserved_client_name,
                    s.name as supplier_name,
                    (SELECT COALESCE(SUM(COALESCE(vi.reserved_quantity, 1)), 0)
                     FROM Versement_Items vi
                     WHERE vi.inventory_id = i.id AND vi.item_status = 'EN_COURS') as active_reserved_quantity,
                    (SELECT COUNT(*) FROM Versement_Items vi
                     WHERE vi.inventory_id = i.id AND vi.item_status = 'EN_COURS') as active_versement_count
                FROM Inventory i
                LEFT JOIN Categories c ON i.category_id = c.id
                LEFT JOIN MetalTypes mt ON i.metal_type_id = mt.id
                LEFT JOIN Clients cl ON i.reserved_for_client_id = cl.id
                LEFT JOIN Suppliers s ON i.supplier_id = s.id
                WHERE i.barcode = %s
            """
            cursor.execute(query, (barcode,))
            result = cursor.fetchone()
            
            try:
                while cursor.nextset():
                    pass
            except:
                pass
            
            return result
        except Exception as e:
            logging.error(f"Erreur lors de la recherche par code-barres {barcode}: {e}")
            return None
        finally:
            if cursor: cursor.close()
            if conn: conn.close()

    def get_inventory_items(self, status: str = "Available", category_id: int = None, search_text: str = None) -> List[Dict]:
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                
                query = """
                    SELECT 
                        i.*, 
                        c.name as category_name, 
                        mt.name as metal_type_name,
                        mt.purity_value as metal_purity,
                        s.name as supplier_name,
                        cl.name as reserved_client_name,
                        
                        -- 🟢 تفاصيل الاسم الظاهر
                        CONCAT(i.name, ' - ', COALESCE(mt.name, ''), ' (', COALESCE(c.name, ''), ')') as display_name,
                        
                        -- 🟢 جلب تفاصيل العربون إذا كانت القطعة محجوزة
                        (SELECT vi2.versement_id FROM Versement_Items vi2
                         WHERE vi2.inventory_id = i.id AND vi2.item_status = 'EN_COURS'
                         ORDER BY vi2.id LIMIT 1) as linked_versement_id,
                        (SELECT COALESCE(SUM(vp.montant_da + vp.tpe_da + (vp.montant_euro * vp.taux_change_euro)), 0)
                         FROM Versement_Payments vp 
                         JOIN Versement_Items vi2 ON vi2.id = vp.versement_item_id
                         WHERE vi2.inventory_id = i.id AND vi2.item_status = 'EN_COURS') as total_versement_item
                        ,
                        (SELECT COALESCE(SUM(COALESCE(vi.reserved_quantity, 1)), 0) FROM Versement_Items vi WHERE vi.inventory_id = i.id AND vi.item_status = 'EN_COURS') as active_reserved_quantity,
                        (SELECT COUNT(*) FROM Versement_Items vi WHERE vi.inventory_id = i.id AND vi.item_status = 'EN_COURS') as active_versement_count
                         
                    FROM Inventory i
                    LEFT JOIN Categories c ON i.category_id = c.id
                    LEFT JOIN MetalTypes mt ON i.metal_type_id = mt.id
                    LEFT JOIN Suppliers s ON i.supplier_id = s.id
                    LEFT JOIN Clients cl ON i.reserved_for_client_id = cl.id
                    WHERE 1=1
                """
                params = []

                if status == "Available":
                    query += f" AND {sellable_stock_condition_sql('i')}"
                elif status:
                    query += " AND i.status = %s"
                    params.append(status)

                if category_id:
                    query += " AND i.category_id = %s"
                    params.append(category_id)

                if search_text:
                    query += " AND (i.barcode LIKE %s OR i.name LIKE %s)"
                    params.extend([f"%{search_text}%", f"%{search_text}%"])
                
                query += " ORDER BY i.id DESC"
                
                cursor.execute(query, tuple(params))
                return cursor.fetchall()
        except mysql.connector.Error as e:
            logging.error(f"Erreur listage stock: {e}")
            return []

    def get_inventory_paginated(self, limit: int, offset: int, search_text: str = None, 
                                show_zero_stock: bool = False, category_id: int = None,
                                metal_type_id: int = None, location_id: int = None,
                                sort_col: int = 0, sort_dir: str = 'DESC',
                                status_filter: str = 'ALL',
                                min_weight: float = None, max_weight: float = None,
                                include_totals: bool = True) -> Tuple[List[Dict], int, float]:
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                
                # أضفنا الربط مع Versement_Items لمعرفة ما إذا كانت القطعة محجوزة حالياً في عربون
                base_query = """
                    FROM Inventory i
                    LEFT JOIN Categories c ON i.category_id = c.id
                    LEFT JOIN MetalTypes mt ON i.metal_type_id = mt.id
                    LEFT JOIN Suppliers s ON i.supplier_id = s.id
                    LEFT JOIN StorageLocations l ON i.location_id = l.id
                    LEFT JOIN Clients cl ON i.reserved_for_client_id = cl.id
                    WHERE 1=1
                """
                params = []
                status_value = (status_filter or 'ALL').strip()
                normalized_status = status_value.upper()

                if not show_zero_stock:
                    base_query += f" AND {self._real_stock_condition('i')}"

                if normalized_status == 'SELLABLE':
                    base_query += f" AND {sellable_stock_condition_sql('i')}"
                elif normalized_status == 'IN_STOCK':
                    base_query += " AND i.status IN ('Available', 'Partially_Sold', 'Reserved')"
                elif normalized_status != 'ALL':
                    base_query += " AND i.status = %s"
                    params.append(status_value)
                elif not show_zero_stock:
                    base_query += " AND i.status IN ('Available', 'Partially_Sold', 'Reserved')"

                if category_id:
                    base_query += " AND i.category_id = %s"
                    params.append(category_id)

                if metal_type_id:
                    base_query += " AND i.metal_type_id = %s"
                    params.append(metal_type_id)

                if location_id:
                    base_query += " AND i.location_id = %s"
                    params.append(location_id)

                if search_text:
                    base_query += " AND (i.barcode LIKE %s OR i.name LIKE %s OR cl.name LIKE %s)"
                    params.extend([f"%{search_text}%", f"%{search_text}%", f"%{search_text}%"])

                if min_weight is not None:
                    base_query += " AND i.item_type = 'WEIGHT' AND COALESCE(i.remaining_weight, i.weight) >= %s"
                    params.append(min_weight)
                if max_weight is not None:
                    base_query += " AND i.item_type = 'WEIGHT' AND COALESCE(i.remaining_weight, i.weight) <= %s"
                    params.append(max_weight)

                sort_mapping = {
                    0: "i.id", 1: "i.barcode", 2: "i.name", 3: "c.name",
                    4: "mt.name", 5: "i.weight", 6: "i.remaining_weight",
                    7: "i.labor_cost_per_gram", 8: "i.margin_type", 9: "i.profit_margin",
                    10: "i.selling_price", 11: "cl.name", 12: "i.status"
                }
                order_by_clause = sort_mapping.get(sort_col, "i.id")
                direction = "ASC" if sort_dir.upper() == "ASC" else "DESC"

                total_count = 0
                total_weight = 0.0
                if include_totals:
                    count_query = """
                        SELECT
                            COUNT(*) as total,
                            SUM(IF(i.item_type = 'WEIGHT', i.remaining_weight, 0)) as total_weight
                    """ + base_query
                    cursor.execute(count_query, tuple(params))
                    count_res = cursor.fetchone()

                    total_count = count_res['total']
                    total_weight = float(count_res['total_weight'] or 0.0)

                # الاستعلام الرئيسي لجدول البيانات
                data_query = """
                    SELECT 
                        i.*, 
                        c.name as category_name, 
                        mt.name as metal_type_name,
                        mt.purity_value as metal_purity,
                        mt.metal_category as metal_category,
                        s.name as supplier_name,
                        l.name as location_name,
                        cl.name as reserved_client_name,
                        
                        -- 🟢 1. إنشاء اسم تفصيلي ومدمج للقطعة (الاسم - العيار (الصنف))
                        CONCAT(i.name, ' - ', COALESCE(mt.name, ''), ' (', COALESCE(c.name, ''), ')') as display_name,
                        
                        -- 🟢 2. جلب رقم العربون المربوط بهذه القطعة (إن وجد)
                        (SELECT vi2.versement_id FROM Versement_Items vi2
                         WHERE vi2.inventory_id = i.id AND vi2.item_status = 'EN_COURS'
                         ORDER BY vi2.id LIMIT 1) as linked_versement_id,
                        
                        -- 🟢 3. حساب إجمالي الدفعات الخاصة بهذه القطعة تحديداً (بالدينار والأورو)
                        (SELECT COALESCE(SUM(vp.montant_da + vp.tpe_da + (vp.montant_euro * vp.taux_change_euro)), 0)
                         FROM Versement_Payments vp 
                         JOIN Versement_Items vi2 ON vi2.id = vp.versement_item_id
                         WHERE vi2.inventory_id = i.id AND vi2.item_status = 'EN_COURS') as total_versement_item,
                         
                        -- 🟢 4. حساب إجمالي الدفعات للملف بالكامل (خيار إضافي)
                        (SELECT COALESCE(SUM(vp.montant_da + vp.tpe_da + (vp.montant_euro * vp.taux_change_euro)), 0)
                         FROM Versement_Payments vp
                         JOIN Versement_Items vi2 ON vi2.versement_id = vp.versement_id
                         WHERE vi2.inventory_id = i.id AND vi2.item_status = 'EN_COURS') as total_versement_global
                        ,
                        (SELECT COALESCE(SUM(COALESCE(vi.reserved_quantity, 1)), 0) FROM Versement_Items vi WHERE vi.inventory_id = i.id AND vi.item_status = 'EN_COURS') as active_reserved_quantity,
                        (SELECT COUNT(*) FROM Versement_Items vi WHERE vi.inventory_id = i.id AND vi.item_status = 'EN_COURS') as active_versement_count
                         
                """ + base_query + f" ORDER BY {order_by_clause} {direction} LIMIT %s OFFSET %s"
                
                params.extend([limit, offset])
                cursor.execute(data_query, tuple(params))
                items = cursor.fetchall()
                
                return items, total_count, total_weight
        except Exception as e:
            import logging
            logging.error(f"Error get_inventory_paginated: {e}")
            return [], 0, 0.0